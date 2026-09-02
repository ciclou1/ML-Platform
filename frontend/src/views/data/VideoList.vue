<template>
  <div class="video-list">
    <div class="page-header">
      <div>
        <h3>视频接入</h3>
        <span class="subtle">上传视频并按间隔生成可标注的图片帧</span>
      </div>
      <div class="header-actions">
        <el-select v-model="selectedDatasetId" filterable placeholder="选择数据集" style="width: 240px" @change="loadVideos">
          <el-option v-for="dataset in datasets" :key="dataset.id" :label="dataset.name" :value="dataset.id" />
        </el-select>
        <el-button :loading="loading" @click="loadVideos">刷新</el-button>
        <el-upload
          v-if="selectedDatasetId"
          :show-file-list="false"
          accept=".mp4,.avi,.mov,.mkv,.wmv,.flv,.webm"
          :before-upload="handleUpload"
        >
          <el-button type="primary">上传视频</el-button>
        </el-upload>
      </div>
    </div>

    <el-alert type="info" :closable="false" show-icon class="info-alert">
      抽帧完成后，图片会写入当前数据集并可以直接在标注工作台中使用。处理中的视频不能重复创建抽帧任务。
    </el-alert>

    <el-table :data="videos" border stripe v-loading="loading" empty-text="暂无视频，请先选择数据集并上传">
      <el-table-column prop="filename" label="文件名" min-width="220" show-overflow-tooltip />
      <el-table-column label="状态" width="115">
        <template #default="{ row }"><el-tag :type="statusTag(row.status)">{{ statusLabel(row.status) }}</el-tag></template>
      </el-table-column>
      <el-table-column label="FPS" width="85"><template #default="{ row }">{{ row.fps ?? '--' }}</template></el-table-column>
      <el-table-column label="时长(s)" width="100"><template #default="{ row }">{{ row.duration_s ?? '--' }}</template></el-table-column>
      <el-table-column prop="frame_count" label="抽帧数" width="95" />
      <el-table-column label="抽帧进度" width="120">
        <template #default="{ row }">
          <template v-if="row.status === 'processing'"><el-progress :percentage="progressFor(row)" :stroke-width="8" :show-text="false" /><span class="progress-text">{{ progressFor(row) }}%</span></template>
          <span v-else>--</span>
        </template>
      </el-table-column>
      <el-table-column label="操作" min-width="210" fixed="right">
        <template #default="{ row }">
          <el-button size="small" link @click="openPreview(row)">预览视频</el-button>
          <el-button v-if="row.status !== 'processing'" size="small" type="primary" link @click="handleExtract(row)">抽帧</el-button>
          <el-button v-if="row.status === 'processed'" size="small" type="success" link @click="goAnnotate(row)">去标注</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog v-model="extractVisible" title="视频抽帧" width="460px">
      <el-form label-width="130px">
        <el-form-item label="帧间隔（帧）"><el-input-number v-model="frameInterval" :min="1" :max="600" /></el-form-item>
        <el-form-item label="归入数据划分"><el-select v-model="split" style="width: 100%"><el-option label="train" value="train" /><el-option label="val" value="val" /><el-option label="test" value="test" /></el-select></el-form-item>
      </el-form>
      <template #footer><el-button @click="extractVisible = false">取消</el-button><el-button type="primary" :loading="extracting" @click="confirmExtract">开始抽帧</el-button></template>
    </el-dialog>

    <el-dialog v-model="previewVisible" title="视频预览" width="820px">
      <video v-if="activeVideo" :src="videoFileUrl(activeVideo.id)" controls class="video-player" />
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { onMounted, onUnmounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { getDatasets } from '@/api/dataset'
import { extractVideoFrames, getVideos, uploadVideo, videoFileUrl } from '@/api/video'
import { getTaskProgress, getTasks, startTask, syncTask } from '@/api/task'
import type { Dataset, Video } from '@/types/dataset'

const datasets = ref<Dataset[]>([])
const selectedDatasetId = ref('')
const videos = ref<Video[]>([])
const loading = ref(false)
const extracting = ref(false)
const extractVisible = ref(false)
const previewVisible = ref(false)
const frameInterval = ref(1)
const split = ref('train')
const activeVideo = ref<Video | null>(null)
const taskByVideo = reactive<Record<string, string>>({})
const progressByVideo = reactive<Record<string, number>>({})
const router = useRouter()
let pollTimer: ReturnType<typeof setInterval> | null = null

onMounted(async () => {
  try {
    datasets.value = (await getDatasets()) || []
    if (datasets.value.length) {
      selectedDatasetId.value = datasets.value[0].id
      await loadVideos()
    }
  } catch (error) {
    ElMessage.error(readError(error) || '视频数据加载失败')
  }
})

onUnmounted(() => { if (pollTimer) clearInterval(pollTimer) })

async function loadVideos() {
  if (!selectedDatasetId.value) { videos.value = []; return }
  loading.value = true
  try {
    const [videoRows, taskRows] = await Promise.all([
      getVideos(selectedDatasetId.value),
      getTasks({ task_type: 'video_import', page: 1, page_size: 200 }),
    ])
    videos.value = videoRows || []
    for (const task of taskRows || []) {
      if (String(task.config?.dataset_id || '') !== selectedDatasetId.value) continue
      const videoId = String(task.config?.video_id || '')
      if (videoId && task.status === 'running') taskByVideo[videoId] = task.id
    }
    startPolling()
  } catch (error) {
    ElMessage.error(readError(error) || '视频列表加载失败')
  } finally { loading.value = false }
}

async function handleUpload(file: File) {
  try {
    await uploadVideo(selectedDatasetId.value, file)
    ElMessage.success('视频上传成功')
    await loadVideos()
  } catch (error) { ElMessage.error(readError(error) || '视频上传失败') }
  return false
}

function handleExtract(video: Video) { activeVideo.value = video; frameInterval.value = 1; split.value = 'train'; extractVisible.value = true }

async function confirmExtract() {
  if (!activeVideo.value) return
  extracting.value = true
  try {
    const task = await extractVideoFrames(activeVideo.value.id, { frame_interval_seconds: frameInterval.value, split: split.value })
    await startTask(task.id)
    taskByVideo[activeVideo.value.id] = task.id
    progressByVideo[activeVideo.value.id] = 0
    ElMessage.success('抽帧任务已启动')
    extractVisible.value = false
    startPolling()
    await loadVideos()
  } catch (error) { ElMessage.error(readError(error) || '抽帧任务启动失败')
  } finally { extracting.value = false }
}

function startPolling() {
  if (pollTimer || !Object.keys(taskByVideo).length) return
  pollTimer = setInterval(async () => {
    for (const [videoId, taskId] of Object.entries(taskByVideo)) {
      try {
        const progress = await getTaskProgress(taskId)
        progressByVideo[videoId] = progress.progress || 0
        const task = await syncTask(taskId)
        if (task.status !== 'running' && task.status !== 'pending') {
          delete taskByVideo[videoId]
          if (task.status === 'failed') ElMessage.error(`视频抽帧失败：${task.error_message || '请查看任务日志'}`)
          await loadVideos()
        }
      } catch { /* 下次轮询重试 */ }
    }
    if (!Object.keys(taskByVideo).length && pollTimer) { clearInterval(pollTimer); pollTimer = null }
  }, 2000)
}

function progressFor(video: Video) { return progressByVideo[video.id] || 0 }
function openPreview(video: Video) { activeVideo.value = video; previewVisible.value = true }
function goAnnotate(video: Video) { router.push(`/annotation/workspace/${video.dataset_id}`) }
function statusLabel(status: string) { return ({ uploaded: '已上传', processing: '抽帧中', processed: '已完成', failed: '失败' } as Record<string, string>)[status] || status }
function statusTag(status: string) { return ({ uploaded: 'info', processing: 'warning', processed: 'success', failed: 'danger' } as Record<string, 'info' | 'warning' | 'success' | 'danger'>)[status] || 'info' }
function readError(error: unknown) { return error instanceof Error ? error.message : '' }
</script>

<style scoped>
.page-header { display: flex; justify-content: space-between; align-items: center; gap: 16px; margin-bottom: 16px; }
.page-header h3 { margin: 0 0 4px; }
.subtle { color: #909399; font-size: 13px; }
.header-actions { display: flex; align-items: center; gap: 8px; }
.info-alert { margin-bottom: 12px; }
.progress-text { display: inline-block; margin-top: 3px; font-size: 11px; color: #909399; }
.video-player { display: block; width: 100%; max-height: 65vh; background: #000; }
.inline-fields { display: flex; align-items: center; gap: 8px; }
@media (max-width: 900px) { .page-header { align-items: stretch; flex-direction: column; } .header-actions { flex-wrap: wrap; } }
</style>

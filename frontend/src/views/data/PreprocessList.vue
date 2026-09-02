<template>
  <div class="preprocess-list">
    <div class="page-header">
      <div>
        <h3>预处理任务</h3>
        <span class="subtle">对数据集图片执行变换，并生成可下载的处理结果</span>
      </div>
      <div class="header-actions">
        <el-button :loading="loading" @click="loadData">刷新</el-button>
        <el-button type="primary" @click="openCreate">新建任务</el-button>
      </div>
    </div>

    <el-table :data="tasks" border stripe v-loading="loading" empty-text="暂无预处理任务">
      <el-table-column prop="name" label="任务名称" min-width="180" show-overflow-tooltip />
      <el-table-column label="数据集" min-width="150">
        <template #default="{ row }">{{ datasetName(row.dataset_id) }}</template>
      </el-table-column>
      <el-table-column label="处理类型" width="130">
        <template #default="{ row }">{{ preprocessLabel(String(row.config?.preprocess_type || '')) }}</template>
      </el-table-column>
      <el-table-column label="进度" width="135">
        <template #default="{ row }">
          <el-progress :percentage="taskProgress(row)" :status="progressStatus(row.status)" :stroke-width="8" :show-text="false" />
          <span class="progress-text">{{ taskProgress(row) }}%</span>
        </template>
      </el-table-column>
      <el-table-column label="结果" width="150">
        <template #default="{ row }">
          <span v-if="row.result?.processed_images !== undefined">{{ row.result.processed_images }} 张已处理</span>
          <span v-else-if="row.status === 'failed'" class="error-text">{{ row.error_message || '处理失败' }}</span>
          <span v-else>--</span>
        </template>
      </el-table-column>
      <el-table-column prop="status" label="状态" width="105">
        <template #default="{ row }"><el-tag :type="statusType(row.status)">{{ statusLabel(row.status) }}</el-tag></template>
      </el-table-column>
      <el-table-column prop="created_at" label="创建时间" width="175">
        <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
      </el-table-column>
      <el-table-column label="操作" width="180" fixed="right">
        <template #default="{ row }">
          <el-button v-if="row.status === 'pending'" size="small" type="primary" link @click="startPreprocess(row)">启动</el-button>
          <el-button v-if="['pending', 'running'].includes(row.status)" size="small" type="danger" link @click="cancelPreprocess(row)">取消</el-button>
          <el-button v-if="row.status === 'completed'" size="small" link @click="openResult(row)">查看产物</el-button>
          <el-button v-if="row.status === 'failed'" size="small" link @click="openResult(row)">查看错误</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog v-model="showForm" title="新建预处理任务" width="560px" @closed="resetForm">
      <el-form ref="formRef" :model="form" :rules="rules" label-width="100px">
        <el-form-item label="任务名称" prop="name"><el-input v-model="form.name" maxlength="255" placeholder="例如：训练集统一缩放" /></el-form-item>
        <el-form-item label="数据集" prop="dataset_id">
          <el-select v-model="form.dataset_id" filterable placeholder="选择数据集" style="width: 100%">
            <el-option v-for="dataset in datasets" :key="dataset.id" :label="dataset.name" :value="dataset.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="处理类型" prop="preprocess_type">
          <el-select v-model="form.preprocess_type" style="width: 100%">
            <el-option label="图片缩放" value="resize" />
            <el-option label="数据增强" value="augmentation" />
            <el-option label="格式转换" value="format_convert" />
            <el-option label="重新划分数据集" value="split" />
          </el-select>
        </el-form-item>
        <template v-if="form.preprocess_type === 'resize'">
          <el-form-item label="输出尺寸"><div class="inline-fields"><el-input-number v-model="form.width" :min="32" :max="4096" /><span>×</span><el-input-number v-model="form.height" :min="32" :max="4096" /></div></el-form-item>
        </template>
        <el-form-item v-if="form.preprocess_type !== 'split'" label="输出格式">
          <el-radio-group v-model="form.output_format"><el-radio value="jpg">JPG</el-radio><el-radio value="png">PNG</el-radio></el-radio-group>
        </el-form-item>
        <template v-if="form.preprocess_type === 'split'">
          <el-form-item label="划分比例"><div class="inline-fields"><el-input-number v-model="form.train_ratio" :min="0" :max="1" :step="0.05" :precision="2" /><span>训练</span><el-input-number v-model="form.val_ratio" :min="0" :max="1" :step="0.05" :precision="2" /><span>验证</span><el-input-number v-model="form.test_ratio" :min="0" :max="1" :step="0.05" :precision="2" /><span>测试</span></div></el-form-item>
        </template>
      </el-form>
      <template #footer><el-button @click="showForm = false">取消</el-button><el-button type="primary" :loading="saving" @click="handleCreate">创建并启动</el-button></template>
    </el-dialog>

    <el-dialog v-model="showResult" title="预处理任务结果" width="620px">
      <template v-if="selectedTask">
        <el-descriptions :column="2" border>
          <el-descriptions-item label="处理类型">{{ preprocessLabel(String(selectedTask.config?.preprocess_type || selectedTask.result?.preprocess_type || '')) }}</el-descriptions-item>
          <el-descriptions-item label="总图片">{{ selectedTask.result?.total_images ?? '--' }}</el-descriptions-item>
          <el-descriptions-item label="已处理">{{ selectedTask.result?.processed_images ?? '--' }}</el-descriptions-item>
          <el-descriptions-item label="跳过">{{ selectedTask.result?.skipped_images ?? '--' }}</el-descriptions-item>
          <el-descriptions-item v-if="selectedTask.status === 'failed'" label="错误" :span="2"><span class="error-text">{{ selectedTask.error_message || selectedTask.result?.error || '--' }}</span></el-descriptions-item>
        </el-descriptions>
        <div v-if="artifacts.length" class="artifact-links">
          <span>任务产物</span>
          <el-link v-for="artifact in artifacts" :key="artifact.key" :href="appendAccessToken(artifact.url)" target="_blank" type="primary">{{ artifact.filename }}</el-link>
        </div>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { onMounted, onUnmounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from 'element-plus'
import { appendAccessToken } from '@/api/accessToken'
import { getDatasets } from '@/api/dataset'
import { createTask, cancelTask, getTaskArtifacts, getTaskProgress, getTasks, startTask, syncTask } from '@/api/task'
import type { Dataset } from '@/types/dataset'
import type { Task, TaskArtifactItem } from '@/types/task'

const datasets = ref<Dataset[]>([])
const tasks = ref<Task[]>([])
const loading = ref(false)
const saving = ref(false)
const showForm = ref(false)
const showResult = ref(false)
const selectedTask = ref<Task | null>(null)
const artifacts = ref<TaskArtifactItem[]>([])
const formRef = ref<FormInstance>()
const form = reactive({
  name: '', dataset_id: '', preprocess_type: 'resize', width: 640, height: 640,
  output_format: 'jpg', train_ratio: 0.8, val_ratio: 0.1, test_ratio: 0.1,
})
const rules: FormRules = {
  name: [{ required: true, message: '请输入任务名称', trigger: 'blur' }],
  dataset_id: [{ required: true, message: '请选择数据集', trigger: 'change' }],
  preprocess_type: [{ required: true, message: '请选择处理类型', trigger: 'change' }],
}
let pollTimer: ReturnType<typeof setInterval> | null = null

onMounted(loadData)
onUnmounted(() => { if (pollTimer) clearInterval(pollTimer) })

async function loadData() {
  loading.value = true
  try {
    const [datasetRows, taskRows] = await Promise.all([getDatasets(), getTasks({ task_type: 'preprocess', page: 1, page_size: 200 })])
    datasets.value = datasetRows || []
    tasks.value = taskRows || []
    startPollingForActiveTasks()
  } catch (error) {
    ElMessage.error(readError(error) || '预处理任务加载失败')
  } finally { loading.value = false }
}

function openCreate() { resetForm(); showForm.value = true; if (!datasets.value.length) loadData() }

async function handleCreate() {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return
  if (form.preprocess_type === 'split' && form.train_ratio + form.val_ratio + form.test_ratio <= 0) {
    ElMessage.warning('划分比例之和必须大于 0'); return
  }
  saving.value = true
  try {
    const task = await createTask({
      name: form.name.trim(), task_type: 'preprocess', dataset_id: form.dataset_id,
      config: {
        preprocess_type: form.preprocess_type, width: form.width, height: form.height,
        output_format: form.output_format,
        split_ratios: { train: form.train_ratio, val: form.val_ratio, test: form.test_ratio },
      },
    })
    await startTask(task.id)
    showForm.value = false
    ElMessage.success('预处理任务已启动')
    await loadData()
  } catch (error) { ElMessage.error(readError(error) || '预处理任务启动失败')
  } finally { saving.value = false }
}

async function startPreprocess(task: Task) {
  try { await startTask(task.id); ElMessage.success('任务已启动'); await loadData() }
  catch (error) { ElMessage.error(readError(error) || '任务启动失败') }
}

async function cancelPreprocess(task: Task) {
  try {
    await ElMessageBox.confirm(`确认取消任务“${task.name}”吗？`, '操作确认', { type: 'warning' })
    await cancelTask(task.id); ElMessage.success('任务已取消'); await loadData()
  } catch (error) { if (error !== 'cancel' && error !== 'close') ElMessage.error(readError(error) || '取消失败') }
}

async function openResult(task: Task) {
  selectedTask.value = task
  artifacts.value = []
  showResult.value = true
  try { artifacts.value = (await getTaskArtifacts(task.id)).items || [] } catch (error) { ElMessage.error(readError(error) || '任务产物加载失败') }
}

function startPollingForActiveTasks() {
  const active = tasks.value.filter((task) => task.status === 'running')
  if (!active.length) { if (pollTimer) { clearInterval(pollTimer); pollTimer = null }; return }
  if (pollTimer) return
  pollTimer = setInterval(async () => {
    let changed = false
    for (const task of tasks.value.filter((item) => item.status === 'running')) {
      try {
        const progress = await getTaskProgress(task.id)
        task.progress = progress.progress || task.progress || 0
        const refreshed = await syncTask(task.id)
        if (refreshed.status !== task.status || refreshed.result) { Object.assign(task, refreshed); changed = true }
      } catch { /* 下次轮询重试 */ }
    }
    if (changed) tasks.value = [...tasks.value]
    if (!tasks.value.some((task) => task.status === 'running')) { clearInterval(pollTimer!); pollTimer = null }
  }, 2000)
}

function resetForm() { Object.assign(form, { name: '', dataset_id: '', preprocess_type: 'resize', width: 640, height: 640, output_format: 'jpg', train_ratio: 0.8, val_ratio: 0.1, test_ratio: 0.1 }) }
function datasetName(id: string | null) { return id ? datasets.value.find((dataset) => dataset.id === id)?.name || '--' : '--' }
function taskProgress(task: Task) { return task.status === 'completed' ? 100 : task.progress || 0 }
function preprocessLabel(type: string) { return ({ resize: '图片缩放', augmentation: '数据增强', format_convert: '格式转换', split: '重新划分' } as Record<string, string>)[type] || type || '--' }
function statusLabel(status: string) { return ({ pending: '等待中', running: '处理中', completed: '已完成', failed: '失败', cancelled: '已取消' } as Record<string, string>)[status] || status }
function statusType(status: string) { return ({ pending: 'info', running: 'warning', completed: 'success', failed: 'danger', cancelled: 'info' } as Record<string, 'info' | 'warning' | 'success' | 'danger'>)[status] || 'info' }
function progressStatus(status: string) { return status === 'failed' ? 'exception' : status === 'completed' ? 'success' : undefined }
function formatTime(value: string) { return value ? new Date(value).toLocaleString() : '--' }
function readError(error: unknown) { return error instanceof Error ? error.message : '' }
</script>

<style scoped>
.page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }
.page-header h3 { margin: 0 0 4px; }
.subtle { color: #909399; font-size: 13px; }
.header-actions { display: flex; gap: 8px; }
.progress-text { display: inline-block; margin-top: 3px; color: #909399; font-size: 11px; }
.error-text { color: #f56c6c; }
.inline-fields { display: flex; align-items: center; gap: 8px; }
.artifact-links { display: flex; align-items: center; gap: 14px; margin-top: 18px; }
</style>

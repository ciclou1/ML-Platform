<template>
  <div class="batch-list">
    <div class="page-header">
      <div>
        <h3>标注批次</h3>
        <span class="subtle">按批次分配图片、跟踪进度并提交质检</span>
      </div>
      <el-button type="primary" :disabled="!canWrite" @click="openCreate">新建批次</el-button>
    </div>

    <el-table :data="batches" border stripe v-loading="loading" empty-text="暂无标注批次">
      <el-table-column prop="name" label="批次名称" min-width="160" />
      <el-table-column prop="dataset_name" label="数据集" min-width="140">
        <template #default="{ row }">{{ row.dataset_name || row.dataset_id }}</template>
      </el-table-column>
      <el-table-column label="进度" width="120">
        <template #default="{ row }">{{ row.completed_count }} / {{ row.total_count }}</template>
      </el-table-column>
      <el-table-column prop="assignee_name" label="负责人" width="120">
        <template #default="{ row }">{{ row.assignee_name || '未分配' }}</template>
      </el-table-column>
      <el-table-column prop="status" label="状态" width="110">
        <template #default="{ row }">
          <el-tag :type="statusType(row.status)">{{ statusLabel(row.status) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="created_at" label="创建时间" width="175">
        <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
      </el-table-column>
      <el-table-column label="操作" min-width="270" fixed="right">
        <template #default="{ row }">
          <el-button size="small" link @click="openDetail(row.id)">明细</el-button>
          <el-button
            v-if="canWrite && ['draft', 'assigned'].includes(row.status)"
            size="small"
            type="primary"
            link
            @click="runAction(row, 'start')"
          >
            启动
          </el-button>
          <el-button
            v-if="canWrite && ['in_progress', 'submitted'].includes(row.status)"
            size="small"
            type="success"
            link
            @click="runAction(row, 'submit')"
          >
            提交质检
          </el-button>
          <el-button
            v-if="canWrite && !['completed', 'cancelled'].includes(row.status)"
            size="small"
            type="danger"
            link
            @click="runAction(row, 'cancel')"
          >
            取消
          </el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog v-model="showCreate" title="新建标注批次" width="760px" @closed="resetCreate">
      <el-form ref="formRef" :model="form" :rules="rules" label-width="90px">
        <el-form-item label="批次名称" prop="name">
          <el-input v-model="form.name" maxlength="255" show-word-limit placeholder="例如：水轮机叶片初标" />
        </el-form-item>
        <el-form-item label="数据集" prop="dataset_id">
          <el-select v-model="form.dataset_id" filterable placeholder="选择数据集" style="width: 100%" @change="loadImages">
            <el-option v-for="dataset in datasets" :key="dataset.id" :label="dataset.name" :value="dataset.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="负责人">
          <el-select v-model="form.assignee_user_id" clearable filterable placeholder="可选" style="width: 100%">
            <el-option
              v-for="user in activeUsers"
              :key="user.id"
              :label="user.display_name || user.username"
              :value="user.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="说明">
          <el-input v-model="form.description" type="textarea" :rows="2" maxlength="2000" show-word-limit />
        </el-form-item>
        <el-form-item label="图片" prop="image_ids">
          <div class="image-picker">
            <div class="picker-toolbar">
              <span>已选择 {{ selectedImageIds.length }} / {{ images.length }} 张</span>
              <el-button link type="primary" :disabled="!images.length" @click="selectAllImages">全选</el-button>
              <el-button link :disabled="!selectedImageIds.length" @click="selectedImageIds = []; form.image_ids = []">清空</el-button>
            </div>
            <el-table
              :data="images"
              border
              max-height="280"
              size="small"
              empty-text="请先选择有图片的数据集"
              @selection-change="onImageSelectionChange"
            >
              <el-table-column type="selection" width="48" />
              <el-table-column prop="filename" label="文件名" min-width="220" show-overflow-tooltip />
              <el-table-column prop="split" label="划分" width="90" />
              <el-table-column label="标注状态" width="100">
                <template #default="{ row }">{{ imageStatusLabel(row.annotation_status) }}</template>
              </el-table-column>
            </el-table>
          </div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showCreate = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="handleCreate">创建批次</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="showDetail" title="批次明细" width="760px">
      <template v-if="detail">
        <div class="detail-summary">
          <span>{{ detail.name }}</span>
          <el-tag :type="statusType(detail.status)">{{ statusLabel(detail.status) }}</el-tag>
          <span>进度 {{ detail.completed_count }} / {{ detail.total_count }}</span>
        </div>
        <el-table :data="detail.items" border stripe max-height="420" empty-text="暂无图片">
          <el-table-column prop="image_filename" label="图片" min-width="220" show-overflow-tooltip />
          <el-table-column prop="image_split" label="划分" width="80" />
          <el-table-column label="标注人" width="120">
            <template #default="{ row }">{{ detail.assignee_name || row.annotator_user_id || '未分配' }}</template>
          </el-table-column>
          <el-table-column prop="status" label="状态" width="100">
            <template #default="{ row }">
              <el-tag size="small" :type="itemStatusType(row.status)">{{ itemStatusLabel(row.status) }}</el-tag>
            </template>
          </el-table-column>
        </el-table>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from 'element-plus'
import {
  cancelAnnotationBatch,
  createAnnotationBatch,
  getAnnotationBatch,
  getAnnotationBatches,
  startAnnotationBatch,
  submitAnnotationBatch,
} from '@/api/annotationBatch'
import { getDatasets, getDatasetImages } from '@/api/dataset'
import { getUsers, type UserResponse } from '@/api/user'
import type { Dataset, DatasetImage } from '@/types/dataset'
import type { AnnotationBatch } from '@/types/annotation-batch'
import { useAuthStore } from '@/stores/auth'

const batches = ref<AnnotationBatch[]>([])
const datasets = ref<Dataset[]>([])
const users = ref<UserResponse[]>([])
const images = ref<DatasetImage[]>([])
const selectedImageIds = ref<string[]>([])
const loading = ref(false)
const saving = ref(false)
const showCreate = ref(false)
const showDetail = ref(false)
const detail = ref<AnnotationBatch | null>(null)
const formRef = ref<FormInstance>()
const auth = useAuthStore()
const canWrite = computed(() => auth.hasPermission('annotation:write'))
const form = reactive({
  name: '',
  dataset_id: '',
  assignee_user_id: '',
  description: '',
  image_ids: [] as string[],
})

const activeUsers = computed(() => users.value.filter((user) => user.status === 'active'))
const rules: FormRules = {
  name: [{ required: true, message: '请输入批次名称', trigger: 'blur' }],
  dataset_id: [{ required: true, message: '请选择数据集', trigger: 'change' }],
  image_ids: [{ type: 'array', required: true, min: 1, message: '至少选择一张图片', trigger: 'change' }],
}

onMounted(loadBatches)

async function loadBatches() {
  loading.value = true
  try {
    batches.value = await getAnnotationBatches()
  } catch (error) {
    ElMessage.error(readError(error) || '批次加载失败')
  } finally {
    loading.value = false
  }
}

async function openCreate() {
  resetCreate()
  showCreate.value = true
  try {
    const [datasetRows, userRows] = await Promise.all([getDatasets(), getUsers()])
    datasets.value = datasetRows
    users.value = userRows
  } catch (error) {
    ElMessage.error(readError(error) || '基础数据加载失败')
  }
}

async function loadImages() {
  images.value = []
  selectedImageIds.value = []
  form.image_ids = []
  if (!form.dataset_id) return
  try {
    images.value = await getDatasetImages(form.dataset_id, { page: 1, page_size: 500 })
  } catch (error) {
    ElMessage.error(readError(error) || '图片加载失败')
  }
}

function onImageSelectionChange(rows: DatasetImage[]) {
  selectedImageIds.value = rows.map((row) => row.id)
  form.image_ids = [...selectedImageIds.value]
}

function selectAllImages() {
  selectedImageIds.value = images.value.map((image) => image.id)
  form.image_ids = [...selectedImageIds.value]
}

async function handleCreate() {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return
  saving.value = true
  try {
    await createAnnotationBatch({
      dataset_id: form.dataset_id,
      name: form.name.trim(),
      description: form.description.trim() || undefined,
      image_ids: form.image_ids,
      assignee_user_id: form.assignee_user_id || undefined,
    })
    showCreate.value = false
    ElMessage.success('批次已创建')
    await loadBatches()
  } catch (error) {
    ElMessage.error(readError(error) || '批次创建失败')
  } finally {
    saving.value = false
  }
}

async function runAction(row: AnnotationBatch, action: 'start' | 'submit' | 'cancel') {
  const labels = { start: '启动', submit: '提交质检', cancel: '取消' }
  try {
    await ElMessageBox.confirm(`确认${labels[action]}批次“${row.name}”吗？`, '操作确认', { type: 'warning' })
    if (action === 'start') await startAnnotationBatch(row.id)
    if (action === 'submit') await submitAnnotationBatch(row.id)
    if (action === 'cancel') await cancelAnnotationBatch(row.id)
    ElMessage.success(`批次已${labels[action]}`)
    await loadBatches()
  } catch (error) {
    if (error !== 'cancel' && error !== 'close') ElMessage.error(readError(error) || '操作失败')
  }
}

async function openDetail(id: string) {
  try {
    detail.value = await getAnnotationBatch(id)
    showDetail.value = true
  } catch (error) {
    ElMessage.error(readError(error) || '批次详情加载失败')
  }
}

function resetCreate() {
  form.name = ''
  form.dataset_id = ''
  form.assignee_user_id = ''
  form.description = ''
  form.image_ids = []
  images.value = []
  selectedImageIds.value = []
}

function formatTime(value: string) {
  return value ? new Date(value).toLocaleString() : '--'
}

function statusLabel(status: string) {
  return ({ draft: '草稿', assigned: '已分配', in_progress: '标注中', submitted: '待质检', completed: '已完成', cancelled: '已取消' } as Record<string, string>)[status] || status
}

function statusType(status: string) {
  return ({ draft: 'info', assigned: 'warning', in_progress: 'primary', submitted: 'warning', completed: 'success', cancelled: 'danger' } as Record<string, 'info' | 'warning' | 'primary' | 'success' | 'danger'>)[status] || 'info'
}

function itemStatusLabel(status: string) {
  return ({ pending: '待标注', annotating: '标注中', submitted: '待审核', approved: '已通过', rejected: '已驳回' } as Record<string, string>)[status] || status
}

function itemStatusType(status: string) {
  return ({ pending: 'info', annotating: 'primary', submitted: 'warning', approved: 'success', rejected: 'danger' } as Record<string, 'info' | 'primary' | 'warning' | 'success' | 'danger'>)[status] || 'info'
}

function imageStatusLabel(status: string) {
  return ({ unannotated: '未标注', annotated: '已标注', approved: '已通过', rejected: '已驳回' } as Record<string, string>)[status] || status || '--'
}

function readError(error: unknown) {
  return error instanceof Error ? error.message : ''
}
</script>

<style scoped>
.page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }
.page-header h3 { margin: 0 0 4px; }
.subtle { color: #909399; font-size: 13px; }
.image-picker { width: 100%; }
.picker-toolbar { display: flex; align-items: center; gap: 4px; margin-bottom: 8px; color: #606266; font-size: 13px; }
.picker-toolbar span { margin-right: auto; }
.detail-summary { display: flex; align-items: center; gap: 16px; margin-bottom: 12px; color: #606266; }
.detail-summary span:first-child { color: #303133; font-weight: 600; }
</style>

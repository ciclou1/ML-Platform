<template>
  <div class="dataset-list">
    <div class="page-header">
      <h3>数据集管理</h3>
      <div>
        <el-button type="primary" @click="showCreate = true">新建数据集</el-button>
      </div>
    </div>

    <el-table :data="datasets" border stripe>
      <el-table-column prop="name" label="名称" />
      <el-table-column prop="data_type" label="类型" width="100" />
      <el-table-column prop="num_classes" label="类别数" width="80" />
      <el-table-column prop="train_count" label="训练集" width="80" />
      <el-table-column prop="val_count" label="验证集" width="80" />
      <el-table-column prop="test_count" label="测试集" width="80" />
      <el-table-column label="状态" width="100">
        <template #default="{ row }">
          <el-tag :type="statusType(row.status)">{{ statusLabel(row.status) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="260">
        <template #default="{ row }">
          <el-button size="small" type="primary" link @click="openUploadDialog(row.id)">
            上传数据
          </el-button>
          <el-button size="small" type="success" link @click="goAnnotate(row.id)">
            标注
          </el-button>
          <el-button size="small" type="danger" link @click="handleDelete(row.id)">
            删除
          </el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog v-model="showCreate" title="新建数据集" width="420px">
      <el-form label-width="80px">
        <el-form-item label="名称">
          <el-input v-model="createForm.name" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="createForm.description" type="textarea" />
        </el-form-item>
        <el-form-item label="标注类型">
          <el-checkbox-group v-model="createForm.annotation_types">
            <el-checkbox v-for="item in ANNOTATION_TYPE_OPTIONS" :key="item.value" :value="item.value">
              {{ item.label }}
            </el-checkbox>
          </el-checkbox-group>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showCreate = false">取消</el-button>
        <el-button type="primary" @click="handleCreate">创建</el-button>
      </template>
    </el-dialog>

    <el-dialog
      v-model="showUpload"
      title="上传数据集 ZIP"
      width="460px"
      @closed="resetUploadDialog"
    >
      <el-alert type="info" :closable="false" show-icon class="upload-tip">
        <template #default>
          <div class="upload-tip-content">
            <span>推荐上传 YOLO 检测标准 ZIP，支持 `data.yaml + images/labels` 目录结构。</span>
            <span>如果没有类别信息，也可以先导入图片，后续在标注工作台新增类别并完成标注。</span>
            <a
              href="/examples/dataset-zip-structure-example.txt"
              download="dataset-zip-structure-example.txt"
              target="_blank"
              rel="noopener"
            >
              下载支持的数据集结构示例
            </a>
          </div>
        </template>
      </el-alert>

      <el-upload
        ref="uploadRef"
        drag
        :auto-upload="false"
        :on-change="onZipSelected"
        accept=".zip"
        :show-file-list="true"
        :limit="1"
      >
        <el-icon :size="48"><UploadFilled /></el-icon>
        <div>拖拽或点击上传 ZIP 文件</div>
      </el-upload>

      <template #footer>
        <el-button @click="showUpload = false">取消</el-button>
        <el-button type="primary" :loading="uploading" @click="doUpload">上传</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { storeToRefs } from 'pinia'
import { useRouter } from 'vue-router'
import { UploadFilled } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import type { UploadInstance } from 'element-plus'
import { confirmDatasetImport, detectDatasetStructure, uploadDatasetZip } from '@/api/upload'
import type { DetectResult } from '@/api/upload'
import { useDatasetStore } from '@/stores/dataset'

const datasetStore = useDatasetStore()
const { datasets } = storeToRefs(datasetStore)
const showCreate = ref(false)
const showUpload = ref(false)
const uploading = ref(false)
const activeDatasetId = ref('')
const uploadRef = ref<UploadInstance>()
const router = useRouter()

const createForm = reactive({ name: '', description: '', annotation_types: [] as string[] })
let zipFile: File | null = null

const ANNOTATION_TYPE_OPTIONS = [
  { value: 'bbox', label: '检测框' },
  { value: 'polygon', label: '多边形' },
  { value: 'obb', label: '旋转框' },
  { value: 'keypoint', label: '关键点' },
  { value: 'classify', label: '整图分类' },
]

const STATUS_CONFIG: Record<string, { type: 'info' | 'success' | 'warning'; label: string }> = {
  ready: { type: 'info', label: '待标注' },
  annotated: { type: 'success', label: '已标注' },
  importing: { type: 'warning', label: '导入中' },
}

onMounted(() => datasetStore.load())

async function handleCreate() {
  if (!createForm.name) {
    ElMessage.warning('请输入数据集名称')
    return
  }

  try {
    const created = await datasetStore.create({
      ...createForm,
      annotation_types: createForm.annotation_types.length
        ? createForm.annotation_types
        : undefined,
    })
    showCreate.value = false
    createForm.name = ''
    createForm.description = ''
    createForm.annotation_types = []
    openUploadDialog(created.id)
  } catch (err: unknown) {
    ElMessage.error(readErrorDetail(err) || '创建失败')
  }
}

function openUploadDialog(datasetId: string) {
  activeDatasetId.value = datasetId
  showUpload.value = true
}

function onZipSelected(file: { raw?: File }) {
  zipFile = file.raw || null
}

function resetUploadDialog() {
  zipFile = null
  activeDatasetId.value = ''
  uploading.value = false
  uploadRef.value?.clearFiles()
}

async function doUpload() {
  if (!zipFile || !activeDatasetId.value) {
    return
  }

  uploading.value = true
  try {
    await uploadDatasetZip(activeDatasetId.value, zipFile)
    const result = await detectDatasetStructure(activeDatasetId.value)

    if (!Object.keys(result.splits || {}).length) {
      throw new Error('未识别到可导入的图片数据，请检查 ZIP 内是否包含图片文件')
    }

    await confirmImport(activeDatasetId.value, result)
    showUpload.value = false

    const classHint =
      Array.isArray(result.classes) && result.classes.length
        ? `，识别类别 ${result.classes.length} 个`
        : '，未识别到类别，可在标注工作台新增类别'

    ElMessage.success(
      `导入完成：train ${result.splits.train?.count || 0} / val ${result.splits.val?.count || result.splits.valid?.count || 0} / test ${result.splits.test?.count || 0}${classHint}`,
    )
  } catch (err: unknown) {
    ElMessage.error(readErrorDetail(err) || '上传导入失败')
  } finally {
    uploading.value = false
  }
}

async function confirmImport(datasetId: string, result: DetectResult) {
  await confirmDatasetImport(datasetId, {
    classes: Array.isArray(result.classes) ? result.classes : [],
    splits: result.splits,
  })
  await datasetStore.load()
}

function goAnnotate(datasetId: string) {
  router.push(`/annotation/workspace/${datasetId}`)
}

async function handleDelete(id: string) {
  try {
    await ElMessageBox.confirm('确定删除该数据集吗？', '确认', { type: 'warning' })
    await datasetStore.remove(id)
    ElMessage.success('已删除')
  } catch {
    // cancelled
  }
}

function readErrorDetail(err: unknown): string | undefined {
  if (typeof err === 'object' && err !== null && 'response' in err) {
    const response = (err as { response?: { data?: { detail?: string } } }).response
    if (response?.data?.detail) {
      return response.data.detail
    }
  }
  return err instanceof Error ? err.message : undefined
}

function statusType(status: string) {
  return STATUS_CONFIG[status]?.type || 'info'
}

function statusLabel(status: string) {
  return STATUS_CONFIG[status]?.label || status
}
</script>

<style scoped>
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.upload-tip {
  margin-bottom: 12px;
}

.upload-tip-content {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.upload-tip-content a {
  color: #2563eb;
  text-decoration: none;
}

.upload-tip-content a:hover {
  text-decoration: underline;
}
</style>

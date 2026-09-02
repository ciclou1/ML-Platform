<template>
  <div class="review-list">
    <div class="page-header">
      <div>
        <h3>质检审核</h3>
        <span class="subtle">审核标注结果，记录质量分和返工意见</span>
      </div>
      <el-button :loading="loading" @click="loadReviews">刷新</el-button>
    </div>

    <el-form inline class="filters" @submit.prevent>
      <el-form-item label="状态">
        <el-select v-model="filters.status" clearable placeholder="全部" style="width: 130px" @change="loadReviews">
          <el-option label="待审核" value="pending" />
          <el-option label="已通过" value="approved" />
          <el-option label="已驳回" value="rejected" />
        </el-select>
      </el-form-item>
      <el-form-item label="数据集">
        <el-select v-model="filters.dataset_id" clearable filterable placeholder="全部" style="width: 180px" @change="loadReviews">
          <el-option v-for="dataset in datasets" :key="dataset.id" :label="dataset.name" :value="dataset.id" />
        </el-select>
      </el-form-item>
      <el-form-item label="批次">
        <el-select v-model="filters.batch_id" clearable filterable placeholder="全部" style="width: 180px" @change="loadReviews">
          <el-option v-for="batch in filteredBatches" :key="batch.id" :label="batch.name" :value="batch.id" />
        </el-select>
      </el-form-item>
    </el-form>

    <el-alert
      v-if="reworkCount > 0"
      type="warning"
      :closable="false"
      show-icon
      class="rework-alert"
    >
      返工队列有 {{ reworkCount }} 条驳回记录。点击对应行的“去返工”可直接打开数据集标注工作台，审核意见会保留在本页。
    </el-alert>

    <el-table :data="reviews" border stripe v-loading="loading" empty-text="暂无审核记录">
      <el-table-column prop="batch_name" label="批次" min-width="150">
        <template #default="{ row }">{{ row.batch_name || row.batch_id }}</template>
      </el-table-column>
      <el-table-column prop="image_filename" label="图片" min-width="190" show-overflow-tooltip>
        <template #default="{ row }">
          <el-button link type="primary" @click="openImage(row)">{{ row.image_filename || row.image_id }}</el-button>
        </template>
      </el-table-column>
      <el-table-column label="标注人" width="120">
        <template #default="{ row }">{{ row.annotator_name || '未记录' }}</template>
      </el-table-column>
      <el-table-column prop="annotation_count" label="标注数" width="85" />
      <el-table-column prop="quality_score" label="质量分" width="90">
        <template #default="{ row }">{{ row.quality_score ?? '--' }}</template>
      </el-table-column>
      <el-table-column prop="status" label="审核状态" width="100">
        <template #default="{ row }"><el-tag :type="reviewStatusType(row.status)">{{ reviewStatusLabel(row.status) }}</el-tag></template>
      </el-table-column>
      <el-table-column prop="reviewed_at" label="审核时间" width="170">
        <template #default="{ row }">{{ formatTime(row.reviewed_at) }}</template>
      </el-table-column>
      <el-table-column label="操作" width="250" fixed="right">
        <template #default="{ row }">
          <template v-if="canWrite && row.status === 'pending'">
            <el-button size="small" type="success" link @click="openDecision(row, 'approve')">通过</el-button>
            <el-button size="small" type="danger" link @click="openDecision(row, 'reject')">驳回</el-button>
          </template>
          <template v-else>
            <el-button v-if="canRework(row)" size="small" type="warning" link @click="goToRework(row)">去返工</el-button>
            <el-button v-if="canWrite && canRework(row) && row.item_status === 'annotating'" size="small" type="primary" link @click="resubmit(row)">提交复审</el-button>
            <el-button size="small" link @click="openDecision(row, row.status === 'approved' ? 'approve' : 'reject')">查看记录</el-button>
          </template>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog v-model="showImage" title="标注预览" width="760px">
      <template v-if="selectedReview">
        <div class="image-preview">
          <canvas ref="previewCanvas" width="720" height="520" class="preview-canvas" />
        </div>
        <div class="preview-meta">
          <span>{{ selectedReview.image_filename || selectedReview.image_id }}</span>
          <span>标注数量：{{ selectedReview.annotation_count }}</span>
        </div>
      </template>
    </el-dialog>

    <el-dialog v-model="showDecision" :title="decision === 'approve' ? '审核通过' : '驳回并返工'" width="460px">
      <template v-if="selectedReview">
        <div class="decision-context">{{ selectedReview.batch_name }} / {{ selectedReview.image_filename }}</div>
        <el-form ref="decisionFormRef" :model="decisionForm" :rules="decisionRules" label-width="90px">
          <el-form-item label="质量分" prop="quality_score">
            <el-input-number v-model="decisionForm.quality_score" :min="0" :max="100" :precision="1" controls-position="right" style="width: 160px" />
          </el-form-item>
          <el-form-item label="审核意见" prop="comment">
            <el-input v-model="decisionForm.comment" type="textarea" :rows="4" maxlength="2000" show-word-limit :placeholder="decision === 'reject' ? '请填写返工原因' : '可选'" />
          </el-form-item>
        </el-form>
      </template>
      <template #footer>
        <el-button @click="showDecision = false">取消</el-button>
        <el-button v-if="selectedReview?.status === 'pending'" :type="decision === 'approve' ? 'success' : 'danger'" :loading="saving" @click="saveDecision">
          {{ decision === 'approve' ? '确认通过' : '确认驳回' }}
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, type FormInstance, type FormRules } from 'element-plus'
import {
  approveAnnotationReview,
  getAnnotationBatches,
  getAnnotationReviews,
  resubmitAnnotationReview,
  rejectAnnotationReview,
} from '@/api/annotationBatch'
import { getAnnotations } from '@/api/annotation'
import { getDatasets, imageFileUrl } from '@/api/dataset'
import { getDatasetLabels } from '@/api/label'
import { useCanvas, type Shape } from '@/composables/useCanvas'
import type { Annotation } from '@/types/annotation'
import type { Dataset } from '@/types/dataset'
import type { Label } from '@/types/label'
import type { AnnotationBatch, AnnotationReview } from '@/types/annotation-batch'
import { useAuthStore } from '@/stores/auth'

const reviews = ref<AnnotationReview[]>([])
const datasets = ref<Dataset[]>([])
const batches = ref<AnnotationBatch[]>([])
const loading = ref(false)
const saving = ref(false)
const showImage = ref(false)
const showDecision = ref(false)
const selectedReview = ref<AnnotationReview | null>(null)
const decision = ref<'approve' | 'reject'>('approve')
const decisionFormRef = ref<FormInstance>()
const auth = useAuthStore()
const route = useRoute()
const router = useRouter()
const canWrite = computed(() => auth.hasPermission('annotation:write'))
const filters = reactive({ status: '', dataset_id: '', batch_id: '' })
const decisionForm = reactive<{ quality_score: number | undefined; comment: string }>({ quality_score: undefined, comment: '' })
const decisionRules: FormRules = {
  comment: [{ validator: (_rule, value, callback) => decision.value === 'reject' && !String(value || '').trim() ? callback(new Error('驳回时必须填写审核意见')) : callback(), trigger: 'blur' }],
}
const filteredBatches = computed(() => filters.dataset_id ? batches.value.filter((batch) => batch.dataset_id === filters.dataset_id) : batches.value)
const reworkCount = computed(() => reviews.value.filter((review) => review.status === 'rejected').length)

onMounted(async () => {
  filters.status = typeof route.query.status === 'string' ? route.query.status : ''
  filters.batch_id = typeof route.query.batch_id === 'string' ? route.query.batch_id : ''
  try {
    const [datasetRows, batchRows] = await Promise.all([getDatasets(), getAnnotationBatches()])
    datasets.value = datasetRows
    batches.value = batchRows
  } catch (error) {
    ElMessage.error(readError(error) || '筛选数据加载失败')
  }
  await loadReviews()
})

async function loadReviews() {
  loading.value = true
  try {
    reviews.value = await getAnnotationReviews({
      status: filters.status || undefined,
      dataset_id: filters.dataset_id || undefined,
      batch_id: filters.batch_id || undefined,
    })
  } catch (error) {
    ElMessage.error(readError(error) || '审核记录加载失败')
  } finally {
    loading.value = false
  }
}

const previewCanvas = ref<HTMLCanvasElement | null>(null)
const canvas = useCanvas(previewCanvas)

async function openImage(row: AnnotationReview) {
  selectedReview.value = row
  showImage.value = true
  await renderPreview(row)
}

/** 加载原图与标注，并在预览画布上叠加渲染（只读）。 */
async function renderPreview(review: AnnotationReview) {
  try {
    await canvas.loadImage(imageFileUrl(review.image_id))
    const [annotations, labels] = await Promise.all([
      getAnnotations(review.image_id),
      review.dataset_id ? getDatasetLabels(review.dataset_id) : Promise.resolve([]),
    ])
    const shapes: Shape[] = []
    for (const annotation of annotations) {
      const shape = annotationToShape(annotation, labels)
      if (shape) {
        shapes.push(shape)
      }
    }
    canvas.setShapes(shapes)
  } catch {
    canvas.setShapes([])
  }
}

function annotationToShape(annotation: Annotation, labels: Label[]): Shape | null {
  const matchedLabel = labels.find((label) => label.id === annotation.label_id) || null
  const base = {
    id: annotation.id,
    labelId: annotation.label_id,
    labelName: matchedLabel?.name || annotation.label_id,
    color: matchedLabel?.color || '#FF0000',
  }
  const data = annotation.data as Record<string, unknown>

  if (annotation.annotation_type === 'classify') {
    return { ...base, type: 'classify' }
  }
  if (annotation.annotation_type === 'polygon') {
    const points = Array.isArray(data.points) ? data.points : null
    if (!points) return null
    return { ...base, type: 'polygon', points: points as [number, number][] }
  }
  if (annotation.annotation_type === 'obb') {
    if (!['cx', 'cy', 'w', 'h'].every((key) => typeof data[key] === 'number')) return null
    return {
      ...base,
      type: 'obb',
      cx: data.cx as number,
      cy: data.cy as number,
      w: data.w as number,
      h: data.h as number,
      angle: typeof data.angle === 'number' ? data.angle : 0,
    }
  }
  if (annotation.annotation_type === 'keypoint') {
    const bbox = data.bbox as { x: number; y: number; width: number; height: number } | undefined
    const points = Array.isArray(data.points) ? data.points : null
    if (!bbox || !points) return null
    return { ...base, type: 'keypoint', bbox, points: points as [number, number, number][] }
  }
  if (!['x', 'y', 'width', 'height'].every((key) => typeof data[key] === 'number')) return null
  return {
    ...base,
    type: 'bbox',
    x: data.x as number,
    y: data.y as number,
    width: data.width as number,
    height: data.height as number,
  }
}

function goToRework(row: AnnotationReview) {
  if (!canRework(row)) {
    ElMessage.info('该驳回记录已完成后续复审，当前图片无需再次返工')
    return
  }
  if (!row.dataset_id) {
    ElMessage.warning('该记录缺少数据集信息，无法打开标注工作台')
    return
  }
  router.push({
    path: `/annotation/workspace/${row.dataset_id}`,
    query: { image: row.image_id, batch: row.batch_id, review: row.id },
  })
}

async function resubmit(row: AnnotationReview) {
  if (!canRework(row)) {
    ElMessage.info('该驳回记录已完成后续复审，当前图片无需再次提交')
    return
  }
  try {
    await resubmitAnnotationReview(row.id)
    ElMessage.success('已提交复审，请等待质检审核')
    filters.status = 'pending'
    filters.batch_id = row.batch_id
    await loadReviews()
  } catch (error) {
    ElMessage.error(readError(error) || '提交复审失败')
  }
}

function canRework(row: AnnotationReview) {
  return row.status === 'rejected' && ['rejected', 'annotating'].includes(row.item_status || '')
}

function openDecision(row: AnnotationReview, mode: 'approve' | 'reject') {
  selectedReview.value = row
  decision.value = mode
  decisionForm.quality_score = row.quality_score ?? undefined
  decisionForm.comment = row.comment || ''
  showDecision.value = true
}

async function saveDecision() {
  if (!selectedReview.value) return
  const valid = await decisionFormRef.value?.validate().catch(() => false)
  if (!valid) return
  saving.value = true
  try {
    if (decision.value === 'approve') {
      await approveAnnotationReview(selectedReview.value.id, {
        comment: decisionForm.comment.trim() || undefined,
        quality_score: decisionForm.quality_score,
      })
    } else {
      await rejectAnnotationReview(selectedReview.value.id, {
        comment: decisionForm.comment.trim(),
        quality_score: decisionForm.quality_score,
      })
    }
    showDecision.value = false
    ElMessage.success(decision.value === 'approve' ? '审核已通过' : '已驳回并退回标注')
    await loadReviews()
  } catch (error) {
    ElMessage.error(readError(error) || '审核操作失败')
  } finally {
    saving.value = false
  }
}

function reviewStatusLabel(status: string) {
  return ({ pending: '待审核', approved: '已通过', rejected: '已驳回' } as Record<string, string>)[status] || status
}

function reviewStatusType(status: string) {
  return ({ pending: 'warning', approved: 'success', rejected: 'danger' } as Record<string, 'warning' | 'success' | 'danger'>)[status] || 'info'
}

function formatTime(value: string | null) {
  return value ? new Date(value).toLocaleString() : '--'
}

function readError(error: unknown) {
  return error instanceof Error ? error.message : ''
}
</script>

<style scoped>
.page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; }
.page-header h3 { margin: 0 0 4px; }
.subtle { color: #909399; font-size: 13px; }
.filters { padding: 12px 12px 0; margin-bottom: 12px; background: #f8fafc; border: 1px solid #ebeef5; }
.rework-alert { margin-bottom: 12px; }
.image-preview { height: 440px; display: flex; align-items: center; justify-content: center; background: #f5f7fa; }
.preview-canvas { max-width: 100%; max-height: 100%; }
.preview-meta { display: flex; justify-content: space-between; margin-top: 12px; color: #606266; }
.decision-context { padding: 8px 12px; margin-bottom: 16px; background: #f5f7fa; color: #606266; }
</style>

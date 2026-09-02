<template>
  <div class="annotation-workspace">
    <div v-if="!datasetId" class="dataset-selector">
      <el-card>
        <template #header>选择数据集进入标注</template>
        <el-select v-model="selectedDatasetId" placeholder="请选择数据集" style="width: 300px">
          <el-option
            v-for="dataset in datasetOptions"
            :key="dataset.id"
            :label="dataset.name"
            :value="dataset.id"
          />
        </el-select>
        <el-button type="primary" style="margin-left: 12px" @click="enterWorkspace">
          进入标注
        </el-button>
      </el-card>
    </div>

    <template v-else>
      <div class="workspace-left">
        <el-select v-model="datasetId" size="small" @change="onDatasetChange">
          <el-option
            v-for="dataset in datasetOptions"
            :key="dataset.id"
            :label="dataset.name"
            :value="dataset.id"
          />
        </el-select>

        <div class="progress-info">
          已标注 {{ annotatedCount }}/{{ images.length }}，标注框 {{ totalBoxCount }}
        </div>

        <div v-if="datasetDetail" class="dataset-summary">
          <div class="summary-row">
            <span>类别来源</span>
            <span>{{ labelSourceText }}</span>
          </div>
          <div class="summary-row">
            <span>数据划分</span>
            <span>{{ splitSummaryText }}</span>
          </div>
        </div>

        <div class="image-actions">
          <el-button size="small" @click="goPreviousImage" :disabled="!hasPreviousImage">
            上一张
          </el-button>
          <el-button size="small" @click="goNextImage" :disabled="!hasNextImage">
            下一张
          </el-button>
          <el-button size="small" type="primary" plain @click="goNextUnannotatedImage">
            跳到未标注
          </el-button>
        </div>

        <ImageList
          :images="imagesWithStatus"
          :selected-id="selectedImageId"
          :total-count="totalImageCount"
          :has-more="hasMoreImages"
          :loading-more="isLoadingMoreImages"
          @select="handleImageSelect"
          @delete="handleImageDelete"
          @load-more="loadMoreImages"
        />
      </div>

      <div class="workspace-center">
        <ImageCanvas
          ref="imageCanvasRef"
          :image-src="currentImageSrc"
          :annotations="currentAnnotations"
          :current-label="currentLabel"
          :can-draw="labels.length > 0 && !!currentLabel"
          @save="handleTempSave"
          @delete="handleDeleteAnnotation"
        />
        <div class="center-footer">
          <el-button type="success" size="large" :disabled="labels.length === 0" @click="handleOpenExport">
            导出数据集
          </el-button>
          <div v-if="reworkReview && selectedImageId === reworkReview.image_id" class="rework-submit">
            <el-alert type="warning" :closable="false" show-icon>
              <template #title>该图片曾被驳回，请完成修改后提交复审</template>
              <template #default>{{ reworkReview.comment || '请检查并完善图片标注' }}</template>
            </el-alert>
            <el-button
              type="warning"
              :loading="resubmitting"
              :disabled="!selectedImageId"
              @click="submitRework"
            >
              提交复审
            </el-button>
          </div>
        </div>
      </div>

      <div class="workspace-right">
        <LabelPanel
          :labels="labels"
          :selected-label-id="currentLabel?.id || ''"
          :can-create="!!datasetId"
          @select="handleLabelSelect"
          @create="handleCreateLabel"
          @delete="handleDeleteLabel"
        />
      </div>
    </template>

    <ExportDialog
      v-model:visible="showExport"
      :dataset-id="datasetId"
      :draft-store="draftStore"
      :annotated-count="annotatedCount"
      :total-box-count="totalBoxCount"
      @exported="onExported"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useRoute, useRouter } from 'vue-router'
import { getAnnotationReview, resubmitAnnotationReview } from '@/api/annotationBatch'
import { replaceImageAnnotations } from '@/api/annotation'
import { createDatasetLabel, deleteLabel } from '@/api/label'
import { useAnnotationWorkspace } from '@/composables/useAnnotationWorkspace'
import type { Shape } from '@/composables/useCanvas'
import type { AnnotationReview } from '@/types/annotation-batch'
import type {
  ImageCanvasExpose,
  WorkspaceImageItem,
  WorkspaceLabelItem,
} from '@/types/annotation-workspace'
import ExportDialog from './components/ExportDialog.vue'
import ImageCanvas from './components/ImageCanvas.vue'
import ImageList from './components/ImageList.vue'
import LabelPanel from './components/LabelPanel.vue'

const route = useRoute()
const router = useRouter()

const datasetId = ref(typeof route.params.datasetId === 'string' ? route.params.datasetId : '')
const selectedDatasetId = ref('')
const showExport = ref(false)
const imageCanvasRef = ref<ImageCanvasExpose | null>(null)
const reworkReview = ref<AnnotationReview | null>(null)
const resubmitting = ref(false)

const {
  datasetOptions,
  datasetDetail,
  images,
  labels,
  selectedImageId,
  currentImageSrc,
  currentAnnotations,
  currentLabel,
  draftStore,
  annotatedCount,
  totalBoxCount,
  totalImageCount,
  imagesWithStatus,
  hasPreviousImage,
  hasNextImage,
  hasMoreImages,
  isLoadingMoreImages,
  loadDatasetOptions,
  loadData,
  loadMoreImages,
  restoreSelection,
  focusImage,
  handleSelectImage,
  handleSelectLabel,
  handleTempSave,
  handleDeleteAnnotation,
  goPreviousImage,
  goNextImage,
  goNextUnannotatedImage,
  clearDatasetDraft,
  removeImage,
} = useAnnotationWorkspace(datasetId)

const labelSourceText = computed(() => {
  if (!datasetDetail.value) {
    return '--'
  }
  if (labels.value.length > 0) {
    return datasetDetail.value.num_classes > 0 ? '沿用当前数据集类别' : '当前工作台新建类别'
  }
  return '当前数据集暂无类别，需先创建'
})

const splitSummaryText = computed(() => {
  if (!datasetDetail.value) {
    return '--'
  }

  const { train_count, val_count, test_count } = datasetDetail.value
  const entries = [
    train_count > 0 ? `train ${train_count}` : '',
    val_count > 0 ? `val ${val_count}` : '',
    test_count > 0 ? `test ${test_count}` : '',
  ].filter(Boolean)

  return entries.length ? entries.join(' / ') : '原数据集未明确划分'
})

onMounted(async () => {
  await loadDatasetOptions()
  if (datasetId.value) {
    await loadData()
    await focusRouteImage()
    await loadRouteReview()
  }
})

watch(
  () => route.params.datasetId,
  async (value) => {
    datasetId.value = typeof value === 'string' ? value : ''
    if (datasetId.value) {
      await loadData()
      await focusRouteImage()
      await loadRouteReview()
    }
  },
)

watch(
  () => route.query.image,
  async () => {
    await focusRouteImage()
  },
)

watch(
  () => route.query.review,
  async () => {
    await loadRouteReview()
  },
)

async function focusRouteImage() {
  const imageId = typeof route.query.image === 'string' ? route.query.image : ''
  if (!imageId || !datasetId.value) {
    return
  }
  const focused = await focusImage(imageId)
  if (!focused) {
    ElMessage.warning('未找到需要返工的图片，可能已被删除或不属于当前数据集')
  }
}

async function loadRouteReview() {
  const reviewId = typeof route.query.review === 'string' ? route.query.review : ''
  if (!reviewId) {
    reworkReview.value = null
    return
  }
  try {
    const review = await getAnnotationReview(reviewId)
    reworkReview.value = review.status === 'rejected' ? review : null
  } catch {
    reworkReview.value = null
  }
}

function shapeToData(shape: Shape): Record<string, unknown> {
  if (shape.type === 'classify') return {}
  if (shape.type === 'bbox') {
    return { x: shape.x, y: shape.y, width: shape.width, height: shape.height }
  }
  if (shape.type === 'polygon') return { points: shape.points }
  if (shape.type === 'obb') {
    return { cx: shape.cx, cy: shape.cy, w: shape.w, h: shape.h, angle: shape.angle }
  }
  return { bbox: shape.bbox, points: shape.points }
}

async function submitRework() {
  if (
    !reworkReview.value ||
    !selectedImageId.value ||
    selectedImageId.value !== reworkReview.value.image_id
  ) {
    return
  }
  const shapes = draftStore.value.get(selectedImageId.value) || []
  resubmitting.value = true
  try {
    await replaceImageAnnotations(
      selectedImageId.value,
      shapes.map((shape) => ({
        image_id: selectedImageId.value,
        label_id: shape.labelId,
        annotation_type: shape.type,
        data: shapeToData(shape),
      })),
    )
    const batchId = reworkReview.value.batch_id
    await resubmitAnnotationReview(reworkReview.value.id)
    reworkReview.value = null
    ElMessage.success('已提交复审，请等待质检审核')
    router.push({ path: '/annotation/review', query: { batch_id: batchId, status: 'pending' } })
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '提交复审失败')
  } finally {
    resubmitting.value = false
  }
}

function enterWorkspace() {
  if (!selectedDatasetId.value) {
    return
  }
  datasetId.value = selectedDatasetId.value
  router.push(`/annotation/workspace/${datasetId.value}`)
}

async function onDatasetChange() {
  selectedImageId.value = ''
  currentImageSrc.value = null
  currentAnnotations.value = []
  router.push(`/annotation/workspace/${datasetId.value}`)
  await loadData()
}

function handleImageSelect(image: WorkspaceImageItem) {
  handleSelectImage(image)
  imageCanvasRef.value?.drawMode()
}

function handleLabelSelect(label: WorkspaceLabelItem) {
  handleSelectLabel(label)
  imageCanvasRef.value?.updateSelectedLabel(label.id, label.name, label.color)
}

async function handleCreateLabel(payload: { name: string; color: string }) {
  if (!datasetId.value) {
    return
  }
  await createDatasetLabel(datasetId.value, {
    name: payload.name,
    color: payload.color,
    sort_order: labels.value.length,
  })
  await loadData()
  if (labels.value.length > 0) {
    const latest = labels.value[labels.value.length - 1]
    handleLabelSelect(latest)
  }
  ElMessage.success('类别已创建')
}

async function handleDeleteLabel(label: WorkspaceLabelItem) {
  try {
    await ElMessageBox.confirm(
      `确定删除类别 ${label.name} 吗？该类别下已有标注也会失效。`,
      '确认删除',
      { type: 'warning' },
    )
    await deleteLabel(label.id)
    await loadData()

    if (labels.value.length > 0) {
      const nextLabel = labels.value.find((item) => item.id !== label.id) || labels.value[0]
      if (nextLabel) {
        handleLabelSelect(nextLabel)
      }
    }

    ElMessage.success('类别已删除')
  } catch {
    // 用户取消
  }
}

async function handleImageDelete(image: WorkspaceImageItem) {
  try {
    await ElMessageBox.confirm(
      `确定删除图片 ${image.filename} 吗？这会同时删除该图片的标注。`,
      '确认删除',
      { type: 'warning' },
    )
    await removeImage(image.id)
    ElMessage.success('图片已删除')
  } catch {
    // 用户取消
  }
}

function handleOpenExport() {
  if (labels.value.length === 0) {
    ElMessage.warning('请先创建类别并完成标注，再导出数据集')
    return
  }
  showExport.value = true
}

function onExported() {
  showExport.value = false
  clearDatasetDraft()
  restoreSelection()
}
</script>

<style scoped>
.annotation-workspace {
  display: flex;
  height: calc(100vh - 120px);
  min-height: 0;
  gap: 8px;
  overflow: hidden;
}

.dataset-selector {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  padding-top: 100px;
}

.workspace-left {
  width: 280px;
  background: #fff;
  border-radius: 4px;
  overflow-y: auto;
  min-height: 0;
  padding: 8px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.progress-info {
  font-size: 12px;
  color: #666;
  padding: 4px 0;
  border-bottom: 1px solid #eee;
}

.dataset-summary {
  padding: 8px;
  border-radius: 6px;
  background: #f8fafc;
  border: 1px solid #e5e7eb;
}

.summary-row {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  font-size: 12px;
  color: #475569;
}

.summary-row + .summary-row {
  margin-top: 6px;
}

.image-actions {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 8px;
}

.image-actions :deep(.el-button:last-child) {
  grid-column: 1 / -1;
}

.workspace-center {
  flex: 1;
  min-width: 0;
  min-height: 0;
  background: #2c2c2c;
  border-radius: 4px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: flex-start;
  overflow: auto;
  padding: 12px;
  gap: 12px;
}

.workspace-center :deep(.image-canvas) {
  flex: 0 0 auto;
}

.center-footer {
  flex-shrink: 0;
  width: min(800px, 100%);
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.center-footer > .el-button {
  align-self: flex-start;
}

.rework-submit {
  width: 100%;
  display: flex;
  align-items: stretch;
  gap: 8px;
}

.rework-submit :deep(.el-alert) {
  flex: 1;
  min-width: 0;
  text-align: left;
}

.rework-submit :deep(.el-button) {
  flex-shrink: 0;
}

.workspace-right {
  width: 280px;
  background: #fff;
  border-radius: 4px;
  padding: 12px;
  overflow-y: auto;
  min-height: 0;
}

@media (max-width: 900px) {
  .annotation-workspace {
    height: auto;
    min-height: calc(100vh - 120px);
    overflow: visible;
    flex-direction: column;
  }

  .workspace-left,
  .workspace-right {
    width: 100%;
    max-height: 260px;
  }

  .workspace-center {
    min-height: 700px;
  }

  .rework-submit {
    flex-direction: column;
  }
}
</style>

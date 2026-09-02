import { computed, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { getAnnotations } from '@/api/annotation'
import { deleteDatasetImage, getDataset, getDatasets, getDatasetImage, getDatasetImages, imageFileUrl } from '@/api/dataset'
import { getDatasetLabels } from '@/api/label'
import type { Shape } from '@/composables/useCanvas'
import { useAnnotationDraftStore } from '@/stores/annotationDraft'
import type { Annotation } from '@/types/annotation'
import type { Dataset } from '@/types/dataset'
import type {
  AnnotationViewData,
  DraftStore,
  WorkspaceDatasetOption,
  WorkspaceImageItem,
  WorkspaceImageListItem,
  WorkspaceLabelItem,
} from '@/types/annotation-workspace'

function shapesToAnnotations(shapes: Shape[]): AnnotationViewData[] {
  return shapes.map((shape) => ({
    id: shape.id,
    label_id: shape.labelId,
    label_name: shape.labelName,
    color: shape.color,
    annotation_type: shape.type,
    data: shapeToData(shape),
    bbox:
      shape.type === 'bbox'
        ? { x: shape.x, y: shape.y, width: shape.width, height: shape.height }
        : { x: 0, y: 0, width: 0, height: 0 },
  }))
}

function shapeToData(shape: Shape): Record<string, unknown> {
  if (shape.type === 'classify') {
    return {}
  }
  if (shape.type === 'bbox') {
    return { x: shape.x, y: shape.y, width: shape.width, height: shape.height }
  }
  if (shape.type === 'polygon') {
    return { points: shape.points }
  }
  if (shape.type === 'obb') {
    return { cx: shape.cx, cy: shape.cy, w: shape.w, h: shape.h, angle: shape.angle }
  }
  return { bbox: shape.bbox, points: shape.points }
}

function annotationToShape(annotation: Annotation, labels: WorkspaceLabelItem[]): Shape | null {
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
    if (
      !['cx', 'cy', 'w', 'h'].every((key) => typeof data[key] === 'number')
    ) {
      return null
    }
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
    return {
      ...base,
      type: 'keypoint',
      bbox,
      points: points as [number, number, number][],
    }
  }

  // bbox（含历史数据）
  if (
    !['x', 'y', 'width', 'height'].every((key) => typeof data[key] === 'number')
  ) {
    return null
  }
  return {
    ...base,
    type: 'bbox',
    x: data.x as number,
    y: data.y as number,
    width: data.width as number,
    height: data.height as number,
  }
}

export function useAnnotationWorkspace(datasetId: { value: string }) {
  const pageSize = 50
  const draftStoreApi = useAnnotationDraftStore()

  const datasetOptions = ref<WorkspaceDatasetOption[]>([])
  const datasetDetail = ref<Dataset | null>(null)
  const images = ref<WorkspaceImageItem[]>([])
  const labels = ref<WorkspaceLabelItem[]>([])
  const selectedImageId = ref('')
  const currentImageSrc = ref<string | null>(null)
  const currentAnnotations = ref<AnnotationViewData[]>([])
  const currentLabel = ref<WorkspaceLabelItem | null>(null)
  const persistedBoxes = ref<Map<string, Shape[]>>(new Map())
  const currentPage = ref(1)
  const hasMoreImages = ref(false)
  const isLoadingMoreImages = ref(false)

  const draftStore = computed<DraftStore>(() => {
    const entries = Object.entries(draftStoreApi.datasetDrafts(datasetId.value))
    return new Map(entries)
  })

  const totalImageCount = computed(() => {
    if (!datasetDetail.value) {
      return 0
    }

    return (
      Number(datasetDetail.value.train_count || 0) +
      Number(datasetDetail.value.val_count || 0) +
      Number(datasetDetail.value.test_count || 0)
    )
  })

  const annotatedCount = computed(() =>
    images.value.filter((image) => resolveImageBoxes(image.id).length > 0).length,
  )

  const totalBoxCount = computed(() => {
    let total = 0
    for (const image of images.value) {
      total += resolveImageBoxes(image.id).length
    }
    return total
  })

  const imagesWithStatus = computed<WorkspaceImageListItem[]>(() =>
    images.value.map((image) => ({
      ...image,
      draft_status: resolveImageBoxes(image.id).length > 0 ? 'annotated' : 'unannotated',
    })),
  )

  const selectedImageIndex = computed(() =>
    imagesWithStatus.value.findIndex((image) => image.id === selectedImageId.value),
  )

  const hasPreviousImage = computed(() => selectedImageIndex.value > 0)
  const hasNextImage = computed(
    () =>
      selectedImageIndex.value >= 0 &&
      selectedImageIndex.value < imagesWithStatus.value.length - 1,
  )

  async function loadDatasetOptions() {
    try {
      datasetOptions.value = await getDatasets()
    } catch {
      datasetOptions.value = []
    }
  }

  async function loadData() {
    try {
      const [imageList, labelList, dataset] = await Promise.all([
        getDatasetImages(datasetId.value, { page: 1, page_size: pageSize }),
        getDatasetLabels(datasetId.value),
        getDataset(datasetId.value),
      ])

      persistedBoxes.value = new Map()
      images.value = imageList
      labels.value = labelList
      datasetDetail.value = dataset
      currentPage.value = 1
      hasMoreImages.value = imageList.length < totalImageCount.value

      if (labels.value.length > 0) {
        currentLabel.value = labels.value[0]
      } else {
        currentLabel.value = null
      }

      await loadPersistedAnnotationsForImages(imageList)
      restoreSelection()
    } catch {
      datasetDetail.value = null
      images.value = []
      labels.value = []
      persistedBoxes.value = new Map()
      currentPage.value = 1
      hasMoreImages.value = false
      isLoadingMoreImages.value = false
    }
  }

  async function loadPersistedAnnotationsForImages(imageList: WorkspaceImageItem[]) {
    const entries: Array<[string, Shape[]]> = await Promise.all(
      imageList.map(async (image) => {
        try {
          const annotations = await getAnnotations(image.id)
          const shapes: Shape[] = []
          for (const annotation of annotations) {
            const shape = annotationToShape(annotation, labels.value)
            if (shape) {
              shapes.push(shape)
            }
          }
          return [image.id, shapes] as [string, Shape[]]
        } catch {
          return [image.id, []]
        }
      }),
    )
    persistedBoxes.value = new Map([...persistedBoxes.value.entries(), ...entries])
  }

  async function loadMoreImages() {
    if (!datasetId.value || !hasMoreImages.value || isLoadingMoreImages.value) {
      return
    }

    isLoadingMoreImages.value = true
    try {
      const nextPage = currentPage.value + 1
      const nextImages = await getDatasetImages(datasetId.value, {
        page: nextPage,
        page_size: pageSize,
      })

      if (nextImages.length === 0) {
        hasMoreImages.value = false
        return
      }

      images.value = [...images.value, ...nextImages]
      currentPage.value = nextPage
      hasMoreImages.value = images.value.length < totalImageCount.value
      await loadPersistedAnnotationsForImages(nextImages)
    } finally {
      isLoadingMoreImages.value = false
    }
  }

  function restoreSelection() {
    if (!images.value.length) {
      selectedImageId.value = ''
      currentImageSrc.value = null
      currentAnnotations.value = []
      return
    }

    const active =
      images.value.find((image) => image.id === selectedImageId.value) ??
      findFirstAnnotatedImage() ??
      images.value[0]
    handleSelectImage(active)
  }

  function findFirstAnnotatedImage(): WorkspaceImageItem | undefined {
    return images.value.find((image) => resolveImageBoxes(image.id).length > 0)
  }

  function resolveImageBoxes(imageId: string): Shape[] {
    if (draftStoreApi.hasImageDraft(datasetId.value, imageId)) {
      return draftStoreApi.getImageDraft(datasetId.value, imageId)
    }
    return persistedBoxes.value.get(imageId) || []
  }

  function handleSelectImage(image: WorkspaceImageItem) {
    selectedImageId.value = image.id
    currentImageSrc.value = imageFileUrl(image.id)
    currentAnnotations.value = shapesToAnnotations(resolveImageBoxes(image.id))
  }

  async function focusImage(imageId: string): Promise<boolean> {
    if (!imageId || !datasetId.value) {
      return false
    }
    let image = images.value.find((item) => item.id === imageId)
    if (!image) {
      try {
        const candidate = await getDatasetImage(imageId)
        if (candidate.dataset_id !== datasetId.value) {
          return false
        }
        image = candidate
        images.value = [...images.value, candidate]
        await loadPersistedAnnotationsForImages([candidate])
      } catch {
        return false
      }
    }
    handleSelectImage(image)
    return true
  }

  function handleSelectLabel(label: WorkspaceLabelItem) {
    currentLabel.value = label
  }

  function handleTempSave(shapes: Shape[]) {
    if (!selectedImageId.value) {
      return
    }
    draftStoreApi.setImageDraft(datasetId.value, selectedImageId.value, [...shapes])
    currentAnnotations.value = shapesToAnnotations(shapes)
    ElMessage.success('已保存当前图片草稿')
  }

  function handleDeleteAnnotation(annotationId: string) {
    currentAnnotations.value = currentAnnotations.value.filter(
      (item) => item.id !== annotationId,
    )
  }

  function goPreviousImage() {
    if (!hasPreviousImage.value) {
      return
    }
    const prev = imagesWithStatus.value[selectedImageIndex.value - 1]
    if (prev) {
      handleSelectImage(prev)
    }
  }

  function goNextImage() {
    if (!hasNextImage.value) {
      return
    }
    const next = imagesWithStatus.value[selectedImageIndex.value + 1]
    if (next) {
      handleSelectImage(next)
    }
  }

  function goNextUnannotatedImage() {
    const nextImage = imagesWithStatus.value.find(
      (image) => image.draft_status === 'unannotated',
    )
    if (nextImage) {
      handleSelectImage(nextImage)
      return
    }
    ElMessage.info('当前已加载的图片都已有标注或草稿')
  }

  function clearDatasetDraft() {
    draftStoreApi.clearDatasetDraft(datasetId.value)
  }

  async function removeImage(imageId: string) {
    await deleteDatasetImage(imageId)
    draftStoreApi.clearImageDraft(datasetId.value, imageId)
    await loadData()
  }

  return {
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
  }
}

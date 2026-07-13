import { computed, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { getAnnotations } from '@/api/annotation'
import { deleteDatasetImage, getDataset, getDatasets, getDatasetImages, imageFileUrl } from '@/api/dataset'
import { getDatasetLabels } from '@/api/label'
import type { BBox } from '@/composables/useCanvas'
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

function boxesToAnnotations(boxes: BBox[]): AnnotationViewData[] {
  return boxes.map((box) => ({
    id: box.id,
    label_id: box.labelId,
    label_name: box.labelName,
    color: box.color,
    bbox: { x: box.x, y: box.y, width: box.width, height: box.height },
  }))
}

function annotationToBox(annotation: Annotation, labels: WorkspaceLabelItem[]): BBox {
  const matchedLabel = labels.find((label) => label.id === annotation.label_id) || null
  return {
    id: annotation.id,
    x: Number(annotation.data.x || 0),
    y: Number(annotation.data.y || 0),
    width: Number(annotation.data.width || 0),
    height: Number(annotation.data.height || 0),
    labelId: annotation.label_id,
    labelName: matchedLabel?.name || annotation.label_id,
    color: matchedLabel?.color || '#FF0000',
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
  const persistedBoxes = ref<Map<string, BBox[]>>(new Map())
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
    const entries: Array<[string, BBox[]]> = await Promise.all(
      imageList.map(async (image) => {
        try {
          const annotations = await getAnnotations(image.id)
          return [
            image.id,
            annotations.map((annotation) => annotationToBox(annotation, labels.value)),
          ] as [string, BBox[]]
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

  function resolveImageBoxes(imageId: string): BBox[] {
    if (draftStoreApi.hasImageDraft(datasetId.value, imageId)) {
      return draftStoreApi.getImageDraft(datasetId.value, imageId)
    }
    return persistedBoxes.value.get(imageId) || []
  }

  function handleSelectImage(image: WorkspaceImageItem) {
    selectedImageId.value = image.id
    currentImageSrc.value = imageFileUrl(image.id)
    currentAnnotations.value = boxesToAnnotations(resolveImageBoxes(image.id))
  }

  function handleSelectLabel(label: WorkspaceLabelItem) {
    currentLabel.value = label
  }

  function handleTempSave(boxes: BBox[]) {
    if (!selectedImageId.value) {
      return
    }
    draftStoreApi.setImageDraft(datasetId.value, selectedImageId.value, [...boxes])
    currentAnnotations.value = boxesToAnnotations(boxes)
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

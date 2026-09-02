import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import type { Shape, ShapeType } from '@/composables/useCanvas'

type DraftDatasetMap = Record<string, Record<string, Shape[]>>

const STORAGE_KEY = 'annotation-draft-store'
const SHAPE_TYPES: ShapeType[] = ['bbox', 'polygon', 'obb', 'keypoint']

function isShape(value: unknown): value is Shape {
  if (!value || typeof value !== 'object') {
    return false
  }
  const row = value as Record<string, unknown>
  if (typeof row.id !== 'string' || typeof row.labelId !== 'string') {
    return false
  }
  if (!SHAPE_TYPES.includes(row.type as ShapeType)) {
    return false
  }
  if (row.type === 'bbox') {
    return typeof row.x === 'number' && typeof row.y === 'number'
      && typeof row.width === 'number' && typeof row.height === 'number'
  }
  if (row.type === 'polygon') {
    return Array.isArray(row.points)
  }
  if (row.type === 'obb') {
    return typeof row.cx === 'number' && typeof row.cy === 'number'
      && typeof row.w === 'number' && typeof row.h === 'number'
      && typeof row.angle === 'number'
  }
  return typeof row.bbox === 'object' && Array.isArray(row.points)
}

function normalizeDraftStore(raw: unknown): DraftDatasetMap {
  if (!raw || typeof raw !== 'object') {
    return {}
  }
  const source = raw as Record<string, unknown>
  const next: DraftDatasetMap = {}
  for (const [datasetId, datasetValue] of Object.entries(source)) {
    if (!datasetValue || typeof datasetValue !== 'object') {
      continue
    }
    const images = datasetValue as Record<string, unknown>
    next[datasetId] = {}
    for (const [imageId, shapesValue] of Object.entries(images)) {
      if (!Array.isArray(shapesValue)) {
        continue
      }
      next[datasetId][imageId] = shapesValue.filter(isShape)
    }
  }
  return next
}

function loadFromStorage(): DraftDatasetMap {
  const raw = localStorage.getItem(STORAGE_KEY)
  if (!raw) {
    return {}
  }
  try {
    return normalizeDraftStore(JSON.parse(raw))
  } catch {
    return {}
  }
}

export const useAnnotationDraftStore = defineStore('annotationDraft', () => {
  const drafts = ref<DraftDatasetMap>(loadFromStorage())

  const datasetDrafts = computed(() => (datasetId: string) => drafts.value[datasetId] || {})

  function persist() {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(drafts.value))
  }

  function setImageDraft(datasetId: string, imageId: string, shapes: Shape[]) {
    drafts.value = {
      ...drafts.value,
      [datasetId]: {
        ...(drafts.value[datasetId] || {}),
        [imageId]: shapes.map((shape) => ({ ...shape })),
      },
    }
    persist()
  }

  function getImageDraft(datasetId: string, imageId: string): Shape[] {
    return drafts.value[datasetId]?.[imageId] || []
  }

  function hasImageDraft(datasetId: string, imageId: string): boolean {
    return Object.prototype.hasOwnProperty.call(drafts.value[datasetId] || {}, imageId)
  }

  function clearDatasetDraft(datasetId: string) {
    const next = { ...drafts.value }
    delete next[datasetId]
    drafts.value = next
    persist()
  }

  function clearImageDraft(datasetId: string, imageId: string) {
    if (!drafts.value[datasetId]) {
      return
    }
    const datasetDraft = { ...drafts.value[datasetId] }
    delete datasetDraft[imageId]

    if (!Object.keys(datasetDraft).length) {
      const next = { ...drafts.value }
      delete next[datasetId]
      drafts.value = next
    } else {
      drafts.value = {
        ...drafts.value,
        [datasetId]: datasetDraft,
      }
    }
    persist()
  }

  function listDraftImageIds(datasetId: string): string[] {
    return Object.entries(drafts.value[datasetId] || {})
      .filter(([, shapes]) => shapes.length > 0)
      .map(([imageId]) => imageId)
  }

  return {
    datasetDrafts,
    setImageDraft,
    getImageDraft,
    hasImageDraft,
    clearDatasetDraft,
    clearImageDraft,
    listDraftImageIds,
  }
})

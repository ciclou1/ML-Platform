import request from './request'
import type { Annotation } from '@/types/annotation'

export function getAnnotations(imageId: string) {
  return request.get<never, Annotation[]>(`/images/${imageId}/annotations`)
}

export function createAnnotation(data: {
  image_id: string
  label_id: string
  annotation_type?: string
  data: Record<string, unknown>
}) {
  return request.post<never, Annotation>('/annotations', data)
}

export function updateAnnotation(id: string, data: Partial<Annotation>) {
  return request.put<never, Annotation>(`/annotations/${id}`, data)
}

export function deleteAnnotation(id: string) {
  return request.delete(`/annotations/${id}`)
}

export function replaceImageAnnotations(
  imageId: string,
  annotations: Array<{
    image_id: string
    label_id: string
    annotation_type: string
    data: Record<string, unknown>
  }>,
) {
  return request.post<never, Annotation[]>(`/images/${imageId}/annotations/batch`, {
    annotations,
  })
}

export function estimatePresetAlignment(imageId: string, referenceImageId: string) {
  return request.post<never, { dx: number; dy: number; confidence: number }>(
    `/images/${imageId}/preset-alignment/estimate`,
    undefined,
    { params: { reference_image_id: referenceImageId } },
  )
}

export function applyPresetAlignment(imageId: string, referenceImageId: string, minConfidence: number) {
  return request.post<never, { dx: number; dy: number; confidence: number; corrected_annotations: number }>(
    `/images/${imageId}/preset-alignment/apply`,
    undefined,
    { params: { reference_image_id: referenceImageId, min_confidence: minConfidence } },
  )
}

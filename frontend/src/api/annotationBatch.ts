import request from './request'
import type { AnnotationBatch, AnnotationBatchItem, AnnotationReview } from '@/types/annotation-batch'

export function getAnnotationBatches(params?: {
  page?: number
  page_size?: number
  dataset_id?: string
  status?: string
}) {
  return request.get<never, AnnotationBatch[]>('/annotation-batches', { params })
}

export function getAnnotationBatch(id: string) {
  return request.get<never, AnnotationBatch>(`/annotation-batches/${id}`)
}

export function createAnnotationBatch(data: {
  dataset_id: string
  name: string
  description?: string
  image_ids: string[]
  assignee_user_id?: string
}) {
  return request.post<never, AnnotationBatch>('/annotation-batches', data)
}

export function startAnnotationBatch(id: string) {
  return request.post<never, AnnotationBatch>(`/annotation-batches/${id}/start`, {})
}

export function submitAnnotationBatch(id: string) {
  return request.post<never, AnnotationBatch>(`/annotation-batches/${id}/submit`, {})
}

export function cancelAnnotationBatch(id: string) {
  return request.post<never, AnnotationBatch>(`/annotation-batches/${id}/cancel`, {})
}

export function getAnnotationBatchItems(id: string) {
  return request.get<never, AnnotationBatchItem[]>(`/annotation-batches/${id}/items`)
}

export function getAnnotationReviews(params?: {
  page?: number
  page_size?: number
  status?: string
  batch_id?: string
  dataset_id?: string
}) {
  return request.get<never, AnnotationReview[]>('/annotation-reviews', { params })
}

export function getAnnotationReview(id: string) {
  return request.get<never, AnnotationReview>(`/annotation-reviews/${id}`)
}

export function approveAnnotationReview(
  id: string,
  data: { comment?: string; quality_score?: number },
) {
  return request.post<never, AnnotationReview>(`/annotation-reviews/${id}/approve`, data)
}

export function rejectAnnotationReview(
  id: string,
  data: { comment: string; quality_score?: number },
) {
  return request.post<never, AnnotationReview>(`/annotation-reviews/${id}/reject`, data)
}

export function resubmitAnnotationReview(id: string) {
  return request.post<never, AnnotationReview>(`/annotation-reviews/${id}/resubmit`, {})
}

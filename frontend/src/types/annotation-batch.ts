export type AnnotationBatchStatus =
  | 'draft'
  | 'assigned'
  | 'in_progress'
  | 'submitted'
  | 'completed'
  | 'cancelled'

export type AnnotationBatchItemStatus =
  | 'pending'
  | 'annotating'
  | 'submitted'
  | 'approved'
  | 'rejected'

export interface AnnotationBatchItem {
  id: string
  batch_id: string
  image_id: string
  annotator_user_id: string | null
  status: AnnotationBatchItemStatus | string
  image_filename: string
  image_width: number
  image_height: number
  image_split: string
  created_at: string
  updated_at: string
}

export interface AnnotationBatch {
  id: string
  dataset_id: string
  name: string
  description: string | null
  status: AnnotationBatchStatus | string
  assignee_user_id: string | null
  created_by_user_id: string | null
  total_count: number
  completed_count: number
  dataset_name: string | null
  assignee_name: string | null
  created_by_name: string | null
  created_at: string
  updated_at: string
  items: AnnotationBatchItem[]
}

export interface AnnotationReview {
  id: string
  batch_item_id: string
  image_id: string
  annotator_user_id: string | null
  reviewer_user_id: string | null
  status: 'pending' | 'approved' | 'rejected' | string
  quality_score: number | null
  comment: string | null
  reviewed_at: string | null
  created_at: string
  updated_at: string
  batch_id: string
  batch_name: string | null
  dataset_id: string | null
  dataset_name: string | null
  image_filename: string | null
  annotation_count: number
  item_status: string | null
  annotator_name: string | null
  reviewer_name: string | null
}

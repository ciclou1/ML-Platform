import request from './request'

export interface DashboardTask {
  id: string
  name: string
  task_type: string
  status: string
  progress: number
  result: Record<string, unknown> | null
  error_message: string | null
  created_at: string
  updated_at: string
}

export interface DashboardOverview {
  dataset_count: number
  image_count: number
  annotated_image_count: number
  model_count: number
  training_task_count: number
  running_task_count: number
  pending_review_count: number
  rejected_review_count: number
  completed_review_count: number
  recent_tasks: DashboardTask[]
}

export function getDashboardOverview() {
  return request.get<never, DashboardOverview>('/stats/overview')
}

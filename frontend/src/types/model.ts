export interface MLModel {
  id: string
  name: string
  version: string | null
  framework: string
  description: string | null
  weight_path: string | null
  model_size_mb: number | null
  parameters: string | null
  status: string
  model_source: string
  dataset_id: string | null
  parent_model_id: string | null
  model_task: string
  metrics: Record<string, unknown> | null
  created_at: string
  updated_at: string
}

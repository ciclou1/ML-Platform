export interface Dataset {
  id: string
  name: string
  description: string | null
  data_type: string
  storage_path: string | null
  scene_category: string | null
  annotation_types: string[] | null
  num_classes: number
  train_count: number
  val_count: number
  test_count: number
  status: string
  created_at: string
  updated_at: string
}

export interface DatasetImage {
  id: string
  dataset_id: string
  filename: string
  file_path: string
  width: number
  height: number
  split: string
  annotation_status: string
  video_id?: string | null
  frame_index?: number | null
  created_at: string
}

export interface Video {
  id: string
  dataset_id: string
  filename: string
  fps: number | null
  duration_s: number | null
  frame_count: number
  status: string
  created_at: string
  updated_at: string
}

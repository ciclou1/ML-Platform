import request from './request'

export interface SystemConfig {
  app_name: string
  app_env: string
  storage_backend: string
  storage_root: string
  max_upload_size_mb: number
  postgres_host: string
  postgres_db: string
  versions: Record<string, string>
}

export function getSystemConfig() {
  return request.get<never, SystemConfig>('/system/config')
}

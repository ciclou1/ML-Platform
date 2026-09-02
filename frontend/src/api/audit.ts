import request from './request'

export interface AuditLog {
  id: string
  username: string | null
  method: string
  path: string
  query: string | null
  status_code: number
  ip: string | null
  duration_ms: number
  created_at: string
}

export function getAuditLogs(params?: { page?: number; page_size?: number; username?: string; method?: string }) {
  return request.get<never, { total: number; items: AuditLog[] }>('/audit-logs', { params })
}

export function clearAuditLogs() {
  return request.delete('/audit-logs')
}

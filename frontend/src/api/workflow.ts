import request from './request'
import type { Task } from '@/types/task'
import type { Workflow, WorkflowGraph } from '@/types/workflow'

export function getWorkflows() {
  return request.get<never, Workflow[]>('/workflows')
}

export function createWorkflow(data: { name: string; description?: string; graph: WorkflowGraph }) {
  return request.post<never, Workflow>('/workflows', data)
}

export function updateWorkflow(id: string, data: { name?: string; description?: string; graph?: WorkflowGraph }) {
  return request.put<never, Workflow>(`/workflows/${id}`, data)
}

export async function uploadWorkflowCsv(id: string, file: File): Promise<{ path: string }> {
  const form = new FormData()
  form.append('file', file)
  return request.post<never, { path: string }>(`/workflows/${id}/csv`, form)
}

export function runWorkflow(id: string, csvPath: string) {
  return request.post<never, Task>(`/workflows/${id}/run`, undefined, { params: { csv_path: csvPath } })
}

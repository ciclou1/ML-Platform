export interface EdgeNode {
  id: string
  name: string
  status: string
  last_heartbeat: string | null
  created_at: string
  updated_at: string
}

export interface NodeDeployment {
  id: string
  node_id: string
  package_version_id: string
  status: string
  pending_params: Record<string, unknown> | null
  last_result: Record<string, unknown> | null
  last_run_at: string | null
  created_at: string
}

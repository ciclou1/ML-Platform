export interface WorkflowGraph {
  nodes: Array<Record<string, unknown>>
  edges: Array<Record<string, unknown>>
}

export interface Workflow {
  id: string
  name: string
  description: string | null
  graph: WorkflowGraph
  created_at: string
  updated_at: string
}

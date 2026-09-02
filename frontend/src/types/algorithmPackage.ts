export interface AlgorithmPackage {
  id: string
  name: string
  framework: string
  description: string | null
  status: string
  created_at: string
  updated_at: string
}

export interface AlgorithmPackageVersion {
  id: string
  package_id: string
  version: string
  entrypoint: string
  runtime_config: Record<string, unknown> | null
  weights_path: string | null
  status: string
  created_at: string
  updated_at: string
}

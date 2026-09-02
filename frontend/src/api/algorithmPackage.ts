import request from './request'
import { appendAccessToken } from './accessToken'
import type { AlgorithmPackage, AlgorithmPackageVersion } from '@/types/algorithmPackage'

export function getAlgorithmPackages() {
  return request.get<never, AlgorithmPackage[]>('/algorithm-packages')
}

export function getAlgorithmPackage(id: string) {
  return request.get<never, AlgorithmPackage>(`/algorithm-packages/${id}`)
}

export function importAlgorithmPackage(payload: {
  name: string
  version: string
  framework?: string
  entrypoint?: string
  description?: string
  file: File
}) {
  const fd = new FormData()
  fd.append('name', payload.name)
  fd.append('version', payload.version)
  fd.append('framework', payload.framework ?? 'custom')
  fd.append('entrypoint', payload.entrypoint ?? 'inference.py:run')
  if (payload.description) fd.append('description', payload.description)
  fd.append('file', payload.file)
  return request.post<never, AlgorithmPackageVersion>('/algorithm-packages/import', fd, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
}

export function getAlgorithmPackageVersions(packageId: string) {
  return request.get<never, AlgorithmPackageVersion[]>(
    `/algorithm-packages/${packageId}/versions`,
  )
}

export function publishAlgorithmVersion(versionId: string) {
  return request.post<never, AlgorithmPackageVersion>(
    `/algorithm-packages/versions/${versionId}/publish`,
  )
}

export function deprecateAlgorithmVersion(versionId: string) {
  return request.post<never, AlgorithmPackageVersion>(
    `/algorithm-packages/versions/${versionId}/deprecate`,
  )
}

export function algorithmVersionDownloadUrl(versionId: string): string {
  return appendAccessToken(`/api/v1/algorithm-packages/versions/${versionId}/download`)
}

export function createAlgorithmInference(versionId: string, params: Record<string, unknown>) {
  return request.post<never, { id: string; task_type: string; status: string }>(
    `/algorithm-packages/versions/${versionId}/infer`,
    params,
  )
}

export function deleteAlgorithmPackage(id: string) {
  return request.delete(`/algorithm-packages/${id}`)
}

import request from './request'
import type { EdgeNode, NodeDeployment } from '@/types/node'

export function getNodes() {
  return request.get<never, EdgeNode[]>('/nodes')
}

export function registerNode(name: string) {
  return request.post<never, { id: string; name: string; token: string }>('/nodes/register', {
    name,
  })
}

export function getNodeDeployments(nodeId: string) {
  return request.get<never, NodeDeployment[]>(`/nodes/${nodeId}/deployments`)
}

export function deployToNode(nodeId: string, packageVersionId: string) {
  return request.post<never, NodeDeployment>(`/nodes/${nodeId}/deploy`, {
    package_version_id: packageVersionId,
  })
}

export function undeployFromNode(deploymentId: string) {
  return request.delete(`/nodes/deployments/${deploymentId}`)
}

export function pushNodeInfer(deploymentId: string, params: Record<string, unknown>) {
  return request.post<never, { status: string }>(
    `/nodes/deployments/${deploymentId}/infer`,
    params,
  )
}

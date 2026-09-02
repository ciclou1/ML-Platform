import request from './request'

export interface RoleResponse {
  id: string
  name: string
  description: string | null
  permissions: string[]
  is_builtin: boolean
  user_count: number
  created_at: string
  updated_at: string
}

export interface UserResponse {
  id: string
  username: string
  display_name: string | null
  role_id: string
  role_name: string | null
  status: string
  last_login_at: string | null
  created_at: string
  updated_at: string
}

export function getRoles() {
  return request.get<never, RoleResponse[]>('/roles')
}

export function createRole(data: { name: string; description?: string; permissions: string[] }) {
  return request.post<never, RoleResponse>('/roles', data)
}

export function updateRole(
  id: string,
  data: { name?: string; description?: string; permissions?: string[] }
) {
  return request.put<never, RoleResponse>(`/roles/${id}`, data)
}

export function deleteRole(id: string) {
  return request.delete(`/roles/${id}`)
}

export function getUsers(page = 1, pageSize = 50) {
  return request.get<never, UserResponse[]>('/users', { params: { page, page_size: pageSize } })
}

export function createUser(data: {
  username: string
  password: string
  display_name?: string
  role_id: string
}) {
  return request.post<never, UserResponse>('/users', data)
}

export function updateUser(
  id: string,
  data: { display_name?: string; role_id?: string }
) {
  return request.put<never, UserResponse>(`/users/${id}`, data)
}

export function resetUserPassword(id: string, password: string) {
  return request.put<never, UserResponse>(`/users/${id}/password`, { password })
}

export function setUserStatus(id: string, status: 'active' | 'disabled') {
  return request.put<never, UserResponse>(`/users/${id}/status`, { status })
}

export function deleteUser(id: string) {
  return request.delete(`/users/${id}`)
}

import request from './request'
import type { RoleResponse, UserResponse } from './user'

export interface LoginResult {
  token: string
  user: UserResponse
  permissions: string[]
}

export function login(data: { username: string; password: string }) {
  return request.post<never, LoginResult>('/auth/login', data)
}

export function getMe() {
  return request.get<never, UserResponse>('/auth/me')
}

export function changePassword(data: { old_password: string; new_password: string }) {
  return request.post('/auth/change-password', data)
}

export type { RoleResponse, UserResponse }

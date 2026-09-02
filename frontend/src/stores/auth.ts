import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { login as loginApi } from '@/api/auth'
import { WILDCARD_PERMISSION } from '@/config/auth'

export interface AuthUser {
  id: string
  username: string
  display_name: string | null
  role_name: string | null
  status: string
}

const TOKEN_KEY = 'auth-token'
const USER_KEY = 'auth-user'
const PERMISSIONS_KEY = 'auth-permissions'

function readStorage(key: string): string {
  try {
    return localStorage.getItem(key) || ''
  } catch {
    return ''
  }
}

function writeStorage(key: string, value: string) {
  try {
    localStorage.setItem(key, value)
  } catch {
    /* 存储不可用时静默降级 */
  }
}

function removeStorage(key: string) {
  try {
    localStorage.removeItem(key)
  } catch {
    /* 忽略 */
  }
}

export const useAuthStore = defineStore('auth', () => {
  const token = ref(readStorage(TOKEN_KEY))
  const user = ref<AuthUser | null>(parseUser(readStorage(USER_KEY)))
  const permissions = ref<string[]>(parsePermissions(readStorage(PERMISSIONS_KEY)))

  const isLoggedIn = computed(() => !!token.value)

  function parseUser(raw: string): AuthUser | null {
    if (!raw) return null
    try {
      return JSON.parse(raw) as AuthUser
    } catch {
      return null
    }
  }

  function parsePermissions(raw: string): string[] {
    if (!raw) return []
    try {
      const value = JSON.parse(raw)
      return Array.isArray(value) ? value.map(String) : []
    } catch {
      return []
    }
  }

  async function login(username: string, password: string) {
    const result = await loginApi({ username, password })
    token.value = result.token
    user.value = {
      id: result.user.id,
      username: result.user.username,
      display_name: result.user.display_name,
      role_name: result.user.role_name,
      status: result.user.status,
    }
    permissions.value = result.permissions
    writeStorage(TOKEN_KEY, result.token)
    writeStorage(USER_KEY, JSON.stringify(user.value))
    writeStorage(PERMISSIONS_KEY, JSON.stringify(result.permissions))
  }

  function logout() {
    token.value = ''
    user.value = null
    permissions.value = []
    removeStorage(TOKEN_KEY)
    removeStorage(USER_KEY)
    removeStorage(PERMISSIONS_KEY)
  }

  function hasPermission(permission: string): boolean {
    return permissions.value.includes(WILDCARD_PERMISSION) || permissions.value.includes(permission)
  }

  return { token, user, permissions, isLoggedIn, login, logout, hasPermission }
})

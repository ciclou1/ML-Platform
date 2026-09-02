import axios from 'axios'
import type { AxiosError, AxiosInstance, AxiosResponse, InternalAxiosRequestConfig } from 'axios'
import { resolveApiBaseUrl } from './baseUrl'
import { useLoadingStore } from '@/stores/loading'

const baseURL = resolveApiBaseUrl(import.meta.env.VITE_API_BASE_URL, import.meta.env.DEV)

const request: AxiosInstance = axios.create({
  baseURL,
  timeout: 30000,
})

request.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  try {
    const token = localStorage.getItem('auth-token')
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
  } catch {
    /* 存储不可用时按匿名请求处理 */
  }
  useLoadingStore().start()
  return config
})

request.interceptors.response.use(
  (response: AxiosResponse) => {
    useLoadingStore().finish()
    return response.data
  },
  (error: AxiosError<{ detail?: string }>) => {
    useLoadingStore().finish()
    const message = error.response?.data?.detail || error.message || '请求失败'
    if (error.response?.status === 401) {
      try {
        localStorage.removeItem('auth-token')
        localStorage.removeItem('auth-user')
        localStorage.removeItem('auth-permissions')
      } catch {
        /* 忽略 */
      }
      if (!window.location.pathname.startsWith('/login')) {
        const redirect = encodeURIComponent(window.location.pathname + window.location.search)
        window.location.href = `/login?redirect=${redirect}`
      }
    }
    error.message = message
    console.error('[API Error]', message)
    return Promise.reject(error)
  }
)

export default request

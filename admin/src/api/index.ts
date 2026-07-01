import axios from 'axios'
import { useAdminAuthStore } from '@/stores/adminAuthStore'

const api = axios.create({
  baseURL: '/api',
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
})

api.interceptors.request.use(
  (config) => {
    const token = useAdminAuthStore.getState().token
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error) => Promise.reject(error)
)

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      useAdminAuthStore.getState().logout()
      window.location.href = '/admin/login'
    }
    return Promise.reject(error)
  }
)

export default api

// Types
export interface User {
  id: number
  username: string
  email: string
  is_active: boolean
  is_admin: boolean
  daily_image_quota: number
  daily_video_quota: number
  used_image_quota: number
  used_video_quota: number
  created_at: string
}

export interface Task {
  id: number
  user_id: number
  username?: string  // 用户名
  task_type: 'image_generation' | 'video_generation'
  status: 'pending' | 'processing' | 'completed' | 'failed'
  input_data: Record<string, unknown>
  result_data: Record<string, unknown> | null
  error_message: string | null
  created_at: string
  started_at: string | null
  completed_at: string | null
}

export interface DashboardStats {
  total_users: number
  active_users: number
  total_tasks: number
  pending_tasks: number
  completed_tasks: number
  failed_tasks: number
  total_images: number
  total_videos: number
}

export interface SystemConfig {
  id: number
  key: string
  value: string
  description: string | null
  updated_at: string
}

// Auth API
export const authApi = {
  login: (data: { username: string; password: string }) =>
    api.post<{ access_token: string; user: User }>('/auth/login', data),
  getMe: () => api.get<User>('/auth/me'),
}

// Admin API
export const adminApi = {
  getDashboard: () => api.get<DashboardStats>('/admin/dashboard'),

  // Users
  getUsers: (params?: { skip?: number; limit?: number; is_active?: boolean; is_admin?: boolean }) =>
    api.get<User[]>('/admin/users', { params }),
  getUser: (id: number) => api.get<User>(`/admin/users/${id}`),
  updateUser: (id: number, data: Partial<User>) => api.put<User>(`/admin/users/${id}`, data),
  deleteUser: (id: number) => api.delete(`/admin/users/${id}`),
  changeUserPassword: (id: number, new_password: string) =>
    api.post<MessageResponse>(`/admin/users/${id}/change-password`, { new_password }),

  // Tasks
  getTasks: (params?: { skip?: number; limit?: number; task_type?: string; status?: string; user_id?: number; username?: string; prompt?: string }) =>
    api.get<Task[]>('/admin/tasks', { params }),
  getTask: (id: number) => api.get<Task>(`/admin/tasks/${id}`),
  deleteTask: (id: number) => api.delete<MessageResponse>(`/admin/tasks/${id}`),
  clearAllTasks: () => api.delete<MessageResponse>('/admin/tasks'),

  // Config
  getConfigs: () => api.get<SystemConfig[]>('/admin/config'),
  updateConfig: (data: { key: string; value: string }) => api.put<SystemConfig>('/admin/config', data),
  initConfigs: () => api.post('/admin/config/init'),

  // Task preview
  getTaskPreviewUrl: (taskId: number, token: string) => `/api/admin/tasks/${taskId}/preview?token=${token}`,
}

export interface MessageResponse {
  message: string
  success?: boolean
}

import axios from 'axios'
import { useAuthStore } from '@/stores/authStore'

const api = axios.create({
  baseURL: '/api',
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
})

// Request interceptor
api.interceptors.request.use(
  (config) => {
    const token = useAuthStore.getState().token
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error) => {
    return Promise.reject(error)
  }
)

// Response interceptor
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      useAuthStore.getState().logout()
      window.location.href = '/front/login'
    }
    return Promise.reject(error)
  }
)

export default api

// API Types
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

export interface LoginRequest {
  username: string
  password: string
}

export interface RegisterRequest {
  username: string
  email: string
  password: string
}

export interface SendVerifyCodeRequest {
  email: string
}

export interface ChangePasswordRequest {
  old_password: string
  new_password: string
}

export interface TokenResponse {
  access_token: string
  token_type: string
  user: User
}

export interface ReferenceImage {
  id: number
  filename: string
  original_filename: string
  file_size: number
  created_at: string
  url?: string
}

export interface Task {
  id: number
  task_type: 'image_generation' | 'video_generation'
  status: 'pending' | 'processing' | 'completed' | 'failed'
  input_data: Record<string, unknown>
  result_data: Record<string, unknown> | null
  error_message: string | null
  created_at: string
  started_at: string | null
  completed_at: string | null
}

export interface GeneratedWork {
  id: number
  work_type: string
  filename: string
  prompt: string | null
  created_at: string
  file_size: number
  url?: string
}

export interface ImageGenerationRequest {
  prompt: string
  negative_prompt?: string
  reference_image_ids: number[]
  width?: number
  height?: number
}

export interface VideoGenerationRequest {
  image_id: number
  prompt: string
  duration?: number
  region?: { x: number; y: number; width: number; height: number }
}

// Auth API
export const authApi = {
  login: (data: LoginRequest) => api.post<TokenResponse>('/auth/login', data),
  register: (data: RegisterRequest) => api.post<TokenResponse>('/auth/register', data),
  getMe: () => api.get<User>('/auth/me'),
  sendVerifyCode: (data: SendVerifyCodeRequest) => api.post<MessageResponse>('/auth/send-verify-code', data),
  changePassword: (data: ChangePasswordRequest) => api.post<MessageResponse>('/auth/change-password', data),
}

export interface MessageResponse {
  message: string
  success: boolean
}

// Image API
export const imageApi = {
  uploadReference: (file: File) => {
    const formData = new FormData()
    formData.append('file', file)
    return api.post<ReferenceImage>('/images/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  },
  listReferences: () => api.get<ReferenceImage[]>('/images/reference'),
  deleteReference: (id: number) => api.delete(`/images/reference/${id}`),
  generateImage: (data: ImageGenerationRequest) => api.post<Task>('/images/generate', data),
  generateVideo: (data: VideoGenerationRequest) => api.post<Task>('/images/generate-video', data),
  listTasks: (params?: { task_type?: string; status?: string }) =>
    api.get<Task[]>('/images/tasks', { params }),
  getTask: (id: number) => api.get<Task>(`/images/tasks/${id}`),
  listWorks: (params?: { work_type?: string }) => api.get<GeneratedWork[]>('/images/works', { params }),
  downloadWork: (id: number) => api.get(`/images/works/${id}/download`, { responseType: 'blob' }),
  deleteWork: (id: number) => api.delete(`/images/works/${id}`),
}

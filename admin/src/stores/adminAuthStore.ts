import { create } from 'zustand'
import { persist } from 'zustand/middleware'

interface AdminUser {
  id: number
  username: string
  email: string
  is_admin: boolean
}

interface AdminAuthState {
  token: string | null
  admin: AdminUser | null
  setAuth: (token: string, admin: AdminUser) => void
  logout: () => void
}

export const useAdminAuthStore = create<AdminAuthState>()(
  persist(
    (set) => ({
      token: null,
      admin: null,
      setAuth: (token, admin) => set({ token, admin }),
      logout: () => set({ token: null, admin: null }),
    }),
    {
      name: 'admin-auth-storage',
    }
  )
)

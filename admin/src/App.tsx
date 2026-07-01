import React from 'react'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { ConfigProvider } from 'antd'
import zhCN from 'antd/locale/zh_CN'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'

import Login from '@/pages/Login'
import Dashboard from '@/pages/Dashboard'
import { useAdminAuthStore } from '@/stores/adminAuthStore'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      retry: 1,
    },
  },
})

const ProtectedRoute: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const token = useAdminAuthStore((state) => state.token)
  const admin = useAdminAuthStore((state) => state.admin)

  if (!token || !admin?.is_admin) {
    return <Navigate to="/login" replace />
  }
  return <>{children}</>
}

const PublicRoute: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const token = useAdminAuthStore((state) => state.token)
  const admin = useAdminAuthStore((state) => state.admin)

  if (token && admin?.is_admin) {
    return <Navigate to="/" replace />
  }
  return <>{children}</>
}

const App: React.FC = () => {
  return (
    <ConfigProvider locale={zhCN}>
      <QueryClientProvider client={queryClient}>
        <BrowserRouter basename="/admin">
          <Routes>
            <Route
              path="/login"
              element={
                <PublicRoute>
                  <Login />
                </PublicRoute>
              }
            />
            <Route
              path="/"
              element={
                <ProtectedRoute>
                  <Dashboard />
                </ProtectedRoute>
              }
            />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </BrowserRouter>
      </QueryClientProvider>
    </ConfigProvider>
  )
}

export default App

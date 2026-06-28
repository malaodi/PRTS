import { useEffect } from 'react'
import { Routes, Route, Navigate } from 'react-router-dom'
import { useAuthStore } from '@/stores'
import LoginPage from '@/pages/LoginPage'
import RegisterPage from '@/pages/RegisterPage'
import ChatPage from '@/pages/ChatPage'
import SpacesPage from '@/pages/SpacesPage'
import AssetsPage from '@/pages/AssetsPage'
import ExplorePage from '@/pages/ExplorePage'
import PipelinesPage from '@/pages/PipelinesPage'
import SessionsPage from '@/pages/SessionsPage'
import AppLayout from '@/layouts/AppLayout'

export default function App() {
  const { isAuthenticated, fetchMe, user } = useAuthStore()

  useEffect(() => {
    if (isAuthenticated && !user) {
      fetchMe()
    }
  }, [isAuthenticated])

  if (isAuthenticated && !user) {
    return (
      <div className="flex items-center justify-center h-screen">
        <div className="animate-spin h-8 w-8 border-4 border-primary-500 border-t-transparent rounded-full" />
      </div>
    )
  }

  return (
    <Routes>
      <Route path="/login" element={isAuthenticated ? <Navigate to="/" /> : <LoginPage />} />
      <Route path="/register" element={isAuthenticated ? <Navigate to="/" /> : <RegisterPage />} />
      <Route path="/" element={isAuthenticated ? <AppLayout /> : <Navigate to="/login" />}>
        <Route index element={<ChatPage />} />
        <Route path="chat" element={<ChatPage />} />
        <Route path="pipelines" element={<PipelinesPage />} />
        <Route path="assets" element={<AssetsPage />} />
        <Route path="explore" element={<ExplorePage />} />
        <Route path="sessions" element={<SessionsPage />} />
        <Route path="spaces" element={<SpacesPage />} />
      </Route>
    </Routes>
  )
}

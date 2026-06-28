import { useEffect, useState } from 'react'
import { Outlet, Link, useNavigate, useLocation } from 'react-router-dom'
import { useAuthStore, useSpaceStore } from '@/stores'
import {
  MessageSquare,
  Users,
  Settings,
  LogOut,
  ChevronDown,
  Plus,
  Home,
  Compass,
} from 'lucide-react'

export default function AppLayout() {
  const { user, logout } = useAuthStore()
  const { spaces, currentSpace, fetchSpaces, setCurrentSpace } = useSpaceStore()
  const [showSpaceMenu, setShowSpaceMenu] = useState(false)
  const navigate = useNavigate()
  const location = useLocation()

  useEffect(() => {
    fetchSpaces()
  }, [fetchSpaces])

  const handleLogout = () => {
    logout()
    navigate('/login')
  }

  return (
    <div className="flex h-screen bg-gray-50">
      {/* Left Sidebar */}
      <aside className="w-64 bg-white border-r border-gray-200 flex flex-col">
        {/* Logo */}
        <div className="p-4 border-b border-gray-100">
          <Link to="/" className="flex items-center gap-2">
            <div className="w-8 h-8 bg-primary-600 rounded-lg flex items-center justify-center">
              <MessageSquare className="w-4 h-4 text-white" />
            </div>
            <span className="font-bold text-lg text-gray-900">PRTS</span>
          </Link>
        </div>

        {/* Space Switcher */}
        <div className="p-3 border-b border-gray-100">
          <button
            onClick={() => setShowSpaceMenu(!showSpaceMenu)}
            className="w-full flex items-center justify-between px-3 py-2 rounded-lg hover:bg-gray-50 transition-colors"
          >
            <div className="flex items-center gap-2 min-w-0">
              <div className="w-6 h-6 bg-primary-100 text-primary-700 rounded-md flex items-center justify-center text-xs font-bold shrink-0">
                {currentSpace?.name?.[0] || '?'}
              </div>
              <span className="text-sm font-medium text-gray-700 truncate">
                {currentSpace?.name || '选择空间'}
              </span>
            </div>
            <ChevronDown className="w-4 h-4 text-gray-400 shrink-0" />
          </button>

          {showSpaceMenu && (
            <div className="mt-1 border border-gray-200 rounded-lg bg-white shadow-lg overflow-hidden">
              {spaces.map((space) => (
                <button
                  key={space.id}
                  onClick={() => {
                    setCurrentSpace(space.id)
                    setShowSpaceMenu(false)
                  }}
                  className={`w-full text-left px-3 py-2 text-sm hover:bg-gray-50 flex items-center gap-2 ${
                    currentSpace?.id === space.id ? 'bg-primary-50 text-primary-700' : 'text-gray-600'
                  }`}
                >
                  <div className="w-5 h-5 bg-primary-100 text-primary-700 rounded flex items-center justify-center text-xs font-bold">
                    {space.name[0]}
                  </div>
                  <span className="truncate">{space.name}</span>
                </button>
              ))}
              <Link
                to="/spaces"
                onClick={() => setShowSpaceMenu(false)}
                className="w-full text-left px-3 py-2 text-sm text-primary-600 hover:bg-primary-50 flex items-center gap-2 border-t border-gray-100"
              >
                <Plus className="w-4 h-4" />
                创建/管理空间
              </Link>
            </div>
          )}
        </div>

        {/* Navigation */}
        <nav className="flex-1 p-3 space-y-1">
          <Link
            to="/chat"
            className={`sidebar-item ${location.pathname === '/chat' || location.pathname === '/' ? 'active' : ''}`}
          >
            <MessageSquare className="w-4 h-4" />
            对话
          </Link>
          <Link
            to="/spaces"
            className={`sidebar-item ${location.pathname === '/spaces' ? 'active' : ''}`}
          >
            <Users className="w-4 h-4" />
            空间管理
          </Link>
          <Link
            to="/assets"
            className={`sidebar-item ${location.pathname === '/assets' ? 'active' : ''}`}
          >
            <Settings className="w-4 h-4" />
            资产管理
          </Link>
          <Link
            to="/explore"
            className={`sidebar-item ${location.pathname === '/explore' ? 'active' : ''}`}
          >
            <Compass className="w-4 h-4" />
            探索市场
          </Link>
        </nav>

        {/* User Footer */}
        <div className="p-3 border-t border-gray-100">
          <div className="flex items-center gap-2 mb-2">
            <div className="w-8 h-8 bg-gray-200 rounded-full flex items-center justify-center text-sm font-medium text-gray-600">
              {user?.display_name?.[0] || user?.username?.[0] || 'U'}
            </div>
            <div className="min-w-0">
              <div className="text-sm font-medium text-gray-700 truncate">
                {user?.display_name || user?.username}
              </div>
              <div className="text-xs text-gray-400 truncate">{user?.email}</div>
            </div>
          </div>
          <button
            onClick={handleLogout}
            className="sidebar-item w-full text-red-500 hover:bg-red-50"
          >
            <LogOut className="w-4 h-4" />
            退出登录
          </button>
        </div>
      </aside>

      {/* Main Content */}
      <main className="flex-1 flex flex-col overflow-hidden">
        <Outlet />
      </main>
    </div>
  )
}

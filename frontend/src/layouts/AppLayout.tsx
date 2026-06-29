import { useEffect, useState } from 'react'
import { Outlet, Link, useNavigate, useLocation } from 'react-router-dom'
import { useAuthStore, useSpaceStore } from '@/stores'
import {
  MessageSquare,
  Zap,
  Bot,
  Compass,
  ClipboardList,
  Users,
  LogOut,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  Plus,
  Folder,
} from 'lucide-react'

const NAV_ITEMS = [
  { key: '/chat', label: '新任务', icon: MessageSquare },
  { key: '/pipelines', label: '自动化', icon: Zap },
  { key: '/assets', label: '智能体', icon: Bot },
  { key: '/explore', label: '探索', icon: Compass },
  { key: '/sessions', label: '任务记录', icon: ClipboardList },
]

export default function AppLayout() {
  const { user, logout } = useAuthStore()
  const { spaces, currentSpace, fetchSpaces, setCurrentSpace } = useSpaceStore()
  const [showSpaceMenu, setShowSpaceMenu] = useState(false)

  const [collapsed, setCollapsed] = useState(() => {
    return localStorage.getItem('sidebar_collapsed') === 'true'
  })

  useEffect(() => {
    fetchSpaces()
  }, [fetchSpaces])

  useEffect(() => {
    localStorage.setItem('sidebar_collapsed', String(collapsed))
  }, [collapsed])

  const navigate = useNavigate()
  const location = useLocation()

  const handleLogout = () => {
    logout()
    navigate('/login')
  }

  const isActive = (path: string) => {
    if (path === '/chat' && (location.pathname === '/' || location.pathname === '/chat')) return true
    return location.pathname.startsWith(path)
  }

  return (
    <div className="flex h-screen bg-gray-50">
      {/* Left Sidebar */}
      <aside
        className={`flex flex-col bg-white border-r border-gray-200 transition-all duration-200 shrink-0 ${
          collapsed ? 'w-16' : 'w-56'
        }`}
      >
        {/* Logo */}
        <div className={`p-3 border-b border-gray-100 ${collapsed ? 'px-2' : 'px-4'}`}>
          <Link to="/chat" className="flex items-center gap-2 overflow-hidden">
            <div className="w-8 h-8 bg-primary-600 rounded-lg flex items-center justify-center shrink-0">
              <MessageSquare className="w-4 h-4 text-white" />
            </div>
            {!collapsed && <span className="font-bold text-lg text-gray-900 whitespace-nowrap">PRTS</span>}
          </Link>
        </div>

        {/* Space Switcher */}
        <div className={`border-b border-gray-100 ${collapsed ? 'px-1 py-2' : 'p-3'}`}>
          <button
            onClick={() => setShowSpaceMenu(!showSpaceMenu)}
            className={`w-full flex items-center rounded-lg hover:bg-gray-50 transition-colors ${
              collapsed ? 'justify-center p-1.5' : 'justify-between px-3 py-2'
            }`}
            title={currentSpace?.name || '选择空间'}
          >
            <div className="flex items-center gap-2 min-w-0">
              <div className="w-6 h-6 bg-primary-100 text-primary-700 rounded-md flex items-center justify-center text-xs font-bold shrink-0">
                {currentSpace?.name?.[0] || '?'}
              </div>
              {!collapsed && (
                <span className="text-sm font-medium text-gray-700 truncate">
                  {currentSpace?.name || '选择空间'}
                </span>
              )}
            </div>
            {!collapsed && <ChevronDown className="w-4 h-4 text-gray-400 shrink-0" />}
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
                  <div className="w-5 h-5 bg-primary-100 text-primary-700 rounded flex items-center justify-center text-xs font-bold shrink-0">
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
                <Users className="w-4 h-4 shrink-0" />
                <span>空间管理</span>
              </Link>
            </div>
          )}
        </div>

        {/* Navigation */}
        <nav className={`flex-1 overflow-y-auto ${collapsed ? 'px-1 py-2 space-y-1' : 'p-3 space-y-1'}`}>
          {NAV_ITEMS.map((item) => (
            <Link
              key={item.key}
              to={item.key}
              className={`flex items-center rounded-lg text-sm transition-colors group relative ${
                collapsed
                  ? 'justify-center px-0 py-2.5'
                  : 'gap-2 px-3 py-2'
              } ${
                isActive(item.key)
                  ? 'bg-primary-50 text-primary-700 font-medium'
                  : 'text-gray-600 hover:bg-gray-100'
              }`}
              title={collapsed ? item.label : undefined}
            >
              <item.icon className="w-4 h-4 shrink-0" />
              {!collapsed && <span>{item.label}</span>}
              {collapsed && (
                <div className="absolute left-full ml-2 px-2 py-1 bg-gray-800 text-white text-xs rounded opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none whitespace-nowrap z-50">
                  {item.label}
                </div>
              )}
            </Link>
          ))}
        </nav>

        {/* Collapse Toggle */}
        <div className={`border-t border-gray-100 ${collapsed ? 'px-1 py-2' : 'p-2'}`}>
          <button
            onClick={() => setCollapsed(!collapsed)}
            className={`w-full flex items-center rounded-lg text-gray-400 hover:text-gray-600 hover:bg-gray-100 transition-colors ${
              collapsed ? 'justify-center p-1.5' : 'gap-2 px-3 py-2'
            }`}
          >
            {collapsed ? <ChevronRight className="w-4 h-4" /> : <ChevronLeft className="w-4 h-4" />}
            {!collapsed && <span className="text-sm">收起菜单</span>}
          </button>
        </div>

        {/* User Footer */}
        <div className={`border-t border-gray-100 ${collapsed ? 'px-1 py-2' : 'p-3'}`}>
          {!collapsed && (
            <div className="flex items-center gap-2 mb-2">
              <div className="w-8 h-8 bg-gray-200 rounded-full flex items-center justify-center text-sm font-medium text-gray-600 shrink-0">
                {user?.display_name?.[0] || user?.username?.[0] || 'U'}
              </div>
              <div className="min-w-0">
                <div className="text-sm font-medium text-gray-700 truncate">
                  {user?.display_name || user?.username}
                </div>
                <div className="text-xs text-gray-400 truncate">{user?.email}</div>
              </div>
            </div>
          )}
          <button
            onClick={handleLogout}
            className={`w-full flex items-center rounded-lg text-red-500 hover:bg-red-50 transition-colors ${
              collapsed ? 'justify-center p-1.5' : 'gap-2 px-3 py-2'
            }`}
            title={collapsed ? '退出登录' : undefined}
          >
            <LogOut className="w-4 h-4 shrink-0" />
            {!collapsed && <span className="text-sm">退出登录</span>}
          </button>
        </div>
      </aside>

      {/* Main Content */}
      <main className="flex-1 flex flex-col overflow-hidden">
        {/* Header bar */}
        <div className="flex items-center justify-end px-4 py-1.5 border-b border-gray-200 bg-white shrink-0">
          <Link
            to="/studio"
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm text-gray-500 hover:bg-gray-100 hover:text-gray-700 transition-colors"
            title="工作室"
          >
            <Folder className="w-4 h-4" />
            <span>工作室</span>
          </Link>
        </div>
        <div className="flex-1 overflow-hidden flex flex-col">
          <Outlet />
        </div>
      </main>
    </div>
  )
}

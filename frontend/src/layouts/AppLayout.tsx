import { useEffect, useState } from 'react'
import { Outlet, Link, useNavigate, useLocation } from 'react-router-dom'
import { useAuthStore, useSpaceStore } from '@/stores'
import api from '@/api/client'
import {
  MessageSquare, Zap, Bot, Compass, ClipboardList, Users, LogOut, ChevronDown, ChevronLeft, ChevronRight, Plus, Folder, Trash2,
} from 'lucide-react'

const NAV_ITEMS = [
  { key: '/chat', label: '新任务', icon: MessageSquare },
  { key: '/pipelines', label: '自动化', icon: Zap },
  { key: '/assets', label: '智能体', icon: Bot },
  { key: '/explore', label: '探索', icon: Compass },
]

interface Session {
  id: string
  thread_id: string
  title: string | null
  created_at: string | null
}

export default function AppLayout() {
  const { user, logout } = useAuthStore()
  const { spaces, currentSpace, fetchSpaces, setCurrentSpace } = useSpaceStore()
  const [showSpaceMenu, setShowSpaceMenu] = useState(false)
  const [sessions, setSessions] = useState<Session[]>([])
  const [activeThread, setActiveThread] = useState<string>('')

  const [collapsed, setCollapsed] = useState(() => localStorage.getItem('sidebar_collapsed') === 'true')

  useEffect(() => { fetchSpaces() }, [fetchSpaces])
  useEffect(() => { localStorage.setItem('sidebar_collapsed', String(collapsed)) }, [collapsed])

  const navigate = useNavigate()
  const location = useLocation()

  const fetchSessions = async () => {
    try { const res = await api.get('/agent/sessions'); setSessions(res.data) } catch { setSessions([]) }
  }

  useEffect(() => { fetchSessions() }, [currentSpace])
  // Refresh session list when path changes (new chat creates new session)
  useEffect(() => { fetchSessions() }, [location.pathname])

  const handleNewChat = () => {
    setActiveThread('')
    localStorage.removeItem('current_thread_id')
    navigate('/chat')
  }

  const handleSelectSession = (s: Session) => {
    if (!s.thread_id) return
    setActiveThread(s.thread_id)
    localStorage.setItem('current_thread_id', s.thread_id)
    navigate(`/chat?session=${encodeURIComponent(s.thread_id)}`)
  }

  const handleDeleteSession = async (e: React.MouseEvent, id: string) => {
    e.stopPropagation(); e.preventDefault()
    if (!confirm('删除此会话？')) return
    try {
      await api.delete(`/agent/sessions/${id}`)
      if (activeThread && sessions.find((s) => s.id === id)?.thread_id === activeThread) {
        setActiveThread('')
      }
      fetchSessions()
    } catch {}
  }

  const handleLogout = () => { logout(); navigate('/login') }

  const isActive = (path: string) => {
    if (path === '/chat' && (location.pathname === '/' || location.pathname === '/chat')) return true
    return location.pathname.startsWith(path)
  }

  const formatTime = (s: string | null) => {
    if (!s) return ''
    const diff = Date.now() - new Date(s).getTime()
    const days = Math.floor(diff / 86400000)
    if (days === 0) { const h = Math.floor(diff / 3600000); return h === 0 ? '刚刚' : `${h}h前` }
    if (days < 7) return `${days}d前`
    return new Date(s).toLocaleDateString('zh-CN', { month: 'short', day: 'numeric' })
  }

  return (
    <div className="flex h-screen bg-gray-50">
      {/* Sidebar */}
      <aside className={`flex flex-col bg-white border-r border-gray-200 transition-all duration-200 shrink-0 ${collapsed ? 'w-16' : 'w-56'}`}>
        {/* Logo */}
        <div className={`p-3 border-b border-gray-100 ${collapsed ? 'px-2' : 'px-4'}`}>
          <Link to="/chat" className="flex items-center gap-2 overflow-hidden" onClick={handleNewChat}>
            <div className="w-8 h-8 bg-primary-600 rounded-lg flex items-center justify-center shrink-0">
              <MessageSquare className="w-4 h-4 text-white" />
            </div>
            {!collapsed && <span className="font-bold text-lg text-gray-900 whitespace-nowrap">PRTS</span>}
          </Link>
        </div>

        {/* Space Switcher */}
        <div className={`border-b border-gray-100 ${collapsed ? 'px-1 py-2' : 'p-3'}`}>
          <button onClick={() => setShowSpaceMenu(!showSpaceMenu)}
            className={`w-full flex items-center rounded-lg hover:bg-gray-50 transition-colors ${collapsed ? 'justify-center p-1.5' : 'justify-between px-3 py-2'}`}>
            <div className="flex items-center gap-2 min-w-0">
              <div className="w-6 h-6 bg-primary-100 text-primary-700 rounded-md flex items-center justify-center text-xs font-bold shrink-0">
                {currentSpace?.name?.[0] || '?'}
              </div>
              {!collapsed && <span className="text-sm font-medium text-gray-700 truncate">{currentSpace?.name || '选择空间'}</span>}
            </div>
            {!collapsed && <ChevronDown className="w-4 h-4 text-gray-400 shrink-0" />}
          </button>
          {showSpaceMenu && (
            <div className="mt-1 border border-gray-200 rounded-lg bg-white shadow-lg overflow-hidden">
              {spaces.map((space) => (
                <button key={space.id} onClick={() => { setCurrentSpace(space.id); setShowSpaceMenu(false) }}
                  className={`w-full text-left px-3 py-2 text-sm hover:bg-gray-50 flex items-center gap-2 ${currentSpace?.id === space.id ? 'bg-primary-50 text-primary-700' : 'text-gray-600'}`}>
                  <div className="w-5 h-5 bg-primary-100 text-primary-700 rounded flex items-center justify-center text-xs font-bold shrink-0">{space.name[0]}</div>
                  <span className="truncate">{space.name}</span>
                </button>
              ))}
              <Link to="/spaces" onClick={() => setShowSpaceMenu(false)} className="w-full text-left px-3 py-2 text-sm text-primary-600 hover:bg-primary-50 flex items-center gap-2 border-t border-gray-100">
                <Users className="w-4 h-4 shrink-0" /><span>空间管理</span>
              </Link>
            </div>
          )}
        </div>

        {/* Navigation */}
        <nav className={`${collapsed ? 'px-1 py-2 space-y-1' : 'p-3 space-y-1'}`}>
          {NAV_ITEMS.map((item) => (
            <Link key={item.key} to={item.key} onClick={item.key === '/chat' ? handleNewChat : undefined}
              className={`flex items-center rounded-lg text-sm transition-colors group relative ${collapsed ? 'justify-center px-0 py-2.5' : 'gap-2 px-3 py-2'} ${isActive(item.key) ? 'bg-primary-50 text-primary-700 font-medium' : 'text-gray-600 hover:bg-gray-100'}`}
              title={collapsed ? item.label : undefined}>
              <item.icon className="w-4 h-4 shrink-0" />
              {!collapsed && <span>{item.label}</span>}
              {collapsed && <div className="absolute left-full ml-2 px-2 py-1 bg-gray-800 text-white text-xs rounded opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none whitespace-nowrap z-50">{item.label}</div>}
            </Link>
          ))}
        </nav>

        {/* Session History */}
        {!collapsed && (
          <>
            <div className="px-3 py-1.5 text-[10px] font-semibold text-gray-400 uppercase tracking-wider border-t border-gray-100 mt-1">
              历史会话
            </div>
            <div className="flex-1 overflow-y-auto px-2 pb-1 space-y-0.5">
              {sessions.map((s) => (
                <button key={s.id}
                  onClick={() => handleSelectSession(s)}
                  className={`w-full text-left px-2.5 py-1.5 rounded-lg text-xs transition-colors group flex items-center gap-1.5 ${s.thread_id === activeThread ? 'bg-primary-50 text-primary-700' : 'text-gray-600 hover:bg-gray-100'}`}>
                  <MessageSquare className="w-3 h-3 shrink-0 text-gray-400" />
                  <span className="truncate flex-1">{s.title || '未命名'}</span>
                  <span className="text-[9px] text-gray-300 shrink-0">{formatTime(s.created_at)}</span>
                  <button onClick={(e) => handleDeleteSession(e, s.id)}
                    className="hidden group-hover:block shrink-0 ml-0.5 p-0.5 text-gray-300 hover:text-red-500 rounded">
                    <Trash2 className="w-2.5 h-2.5" />
                  </button>
                </button>
              ))}
              {sessions.length === 0 && (
                <div className="text-[10px] text-gray-300 px-2.5 py-4 text-center">暂无历史会话</div>
              )}
            </div>
          </>
        )}

        {/* Collapse Toggle */}
        <div className={`border-t border-gray-100 ${collapsed ? 'px-1 py-2' : 'p-2'}`}>
          <button onClick={() => setCollapsed(!collapsed)}
            className={`w-full flex items-center rounded-lg text-gray-400 hover:text-gray-600 hover:bg-gray-100 transition-colors ${collapsed ? 'justify-center p-1.5' : 'gap-2 px-3 py-2'}`}>
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
                <div className="text-sm font-medium text-gray-700 truncate">{user?.display_name || user?.username}</div>
                <div className="text-xs text-gray-400 truncate">{user?.email}</div>
              </div>
            </div>
          )}
          <button onClick={handleLogout}
            className={`w-full flex items-center rounded-lg text-red-500 hover:bg-red-50 transition-colors ${collapsed ? 'justify-center p-1.5' : 'gap-2 px-3 py-2'}`}>
            <LogOut className="w-4 h-4 shrink-0" />
            {!collapsed && <span className="text-sm">退出登录</span>}
          </button>
        </div>
      </aside>

      {/* Main Content */}
      <main className="flex-1 flex flex-col overflow-hidden">
        <div className="flex items-center justify-end px-4 py-1.5 border-b border-gray-200 bg-white shrink-0">
          <Link to="/studio" className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm text-gray-500 hover:bg-gray-100 hover:text-gray-700 transition-colors" title="工作室">
            <Folder className="w-4 h-4" /><span>工作室</span>
          </Link>
        </div>
        <div className="flex-1 overflow-hidden flex flex-col">
          <Outlet />
        </div>
      </main>
    </div>
  )
}

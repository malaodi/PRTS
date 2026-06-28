import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import api from '@/api/client'
import { ClipboardList, MessageSquare, Trash2, ArrowRight } from 'lucide-react'

interface Session {
  id: string
  thread_id: string
  title: string | null
  created_at: string | null
}

export default function SessionsPage() {
  const [sessions, setSessions] = useState<Session[]>([])
  const [loading, setLoading] = useState(true)
  const navigate = useNavigate()

  const fetchSessions = async () => {
    try {
      setLoading(true)
      const res = await api.get('/agent/sessions')
      setSessions(res.data)
    } catch {
      setSessions([])
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchSessions()
  }, [])

  const handleDelete = async (id: string) => {
    if (!confirm('确定删除此会话？')) return
    try {
      await api.delete(`/agent/sessions/${id}`)
      fetchSessions()
    } catch {}
  }

  const handleContinue = (session: Session) => {
    if (!session.thread_id) {
      navigate('/chat')
      return
    }
    localStorage.setItem(`thread_${session.thread_id}`, session.thread_id)
    navigate(`/chat`)
  }

  const formatTime = (s: string | null) => {
    if (!s) return ''
    const d = new Date(s)
    const now = new Date()
    const diff = now.getTime() - d.getTime()
    const days = Math.floor(diff / (1000 * 60 * 60 * 24))

    if (days === 0) {
      const hours = Math.floor(diff / (1000 * 60 * 60))
      if (hours === 0) {
        const mins = Math.floor(diff / (1000 * 60))
        return mins <= 1 ? '刚刚' : `${mins} 分钟前`
      }
      return `${hours} 小时前`
    } else if (days === 1) {
      return '昨天 ' + d.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
    } else if (days < 7) {
      return `${days} 天前`
    } else {
      return d.toLocaleDateString('zh-CN', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
    }
  }

  return (
    <div className="flex-1 overflow-y-auto p-6">
      <div className="max-w-4xl mx-auto">
        <div className="mb-6">
          <h2 className="text-xl font-bold text-gray-900">
            <ClipboardList className="w-5 h-5 inline mr-2" />
            任务记录
          </h2>
          <p className="text-sm text-gray-500 mt-1">查看和管理历史会话</p>
        </div>

        {loading ? (
          <div className="text-center py-12 text-gray-400">加载中...</div>
        ) : sessions.length === 0 ? (
          <div className="text-center py-16">
            <ClipboardList className="w-12 h-12 mx-auto mb-3 text-gray-300" />
            <h3 className="text-sm font-medium text-gray-500">暂无任务记录</h3>
            <p className="text-xs text-gray-400 mt-1">开始新任务后，会话记录会出现在这里</p>
          </div>
        ) : (
          <div className="space-y-2">
            {sessions.map((session) => (
              <div
                key={session.id}
                className="card flex items-center justify-between group hover:border-primary-200 transition-colors cursor-pointer"
                onClick={() => handleContinue(session)}
              >
                <div className="flex items-center gap-3 min-w-0 flex-1">
                  <div className="w-10 h-10 rounded-lg bg-gray-100 flex items-center justify-center shrink-0">
                    <MessageSquare className="w-5 h-5 text-gray-400" />
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="text-sm font-medium text-gray-800 truncate">
                      {session.title || '未命名会话'}
                    </div>
                    <div className="text-xs text-gray-400 mt-0.5">
                      {formatTime(session.created_at)}
                      <span className="mx-1.5">·</span>
                      <span className="font-mono text-gray-300 text-[10px]">{session.thread_id?.slice(0, 12)}</span>
                    </div>
                  </div>
                </div>
                <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity shrink-0">
                  <button
                    onClick={(e) => {
                      e.stopPropagation()
                      handleContinue(session)
                    }}
                    className="p-1.5 text-gray-300 hover:text-primary-500 rounded-lg hover:bg-primary-50 transition-colors"
                    title="继续对话"
                  >
                    <ArrowRight className="w-4 h-4" />
                  </button>
                  <button
                    onClick={(e) => {
                      e.stopPropagation()
                      handleDelete(session.id)
                    }}
                    className="p-1.5 text-gray-300 hover:text-red-500 rounded-lg hover:bg-red-50 transition-colors"
                    title="删除"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

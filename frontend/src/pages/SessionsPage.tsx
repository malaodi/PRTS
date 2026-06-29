import { useState, useEffect, useRef, useCallback } from 'react'
import api from '@/api/client'
import { ClipboardList, MessageSquare, Trash2, Send, Loader2, ArrowDown, Check, X, Wrench, ChevronDown, ChevronUp } from 'lucide-react'

interface Session {
  id: string
  thread_id: string
  title: string | null
  created_at: string | null
}

interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  widget?: WidgetData | null
  widgetResolved?: boolean
}

interface WidgetData {
  type: string
  title: string
  message: string
  confirm_label?: string
  cancel_label?: string
  danger?: boolean
  options?: Array<{ value: string; label: string; description?: string }>
  multiple?: boolean
  content?: string
  fields?: Array<{
    key: string; label: string; field_type: string; placeholder?: string; required?: boolean; default?: string
    options?: Array<{ value: string; label: string }>
  }>
  _source?: string
  _creation_id?: string
  _cards?: any[]
}

export default function SessionsPage() {
  const [sessions, setSessions] = useState<Session[]>([])
  const [loading, setLoading] = useState(true)
  const [selectedSession, setSelectedSession] = useState<Session | null>(null)
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [streaming, setStreaming] = useState(false)
  const [loadedMsgs, setLoadedMsgs] = useState(false)
  const [activeTools, setActiveTools] = useState<string[]>([])
  const [toolHistory, setToolHistory] = useState<string[]>([])
  const [showToolPanel, setShowToolPanel] = useState(false)
  const [showScrollBtn, setShowScrollBtn] = useState(false)
  const chatContainerRef = useRef<HTMLDivElement>(null)
  const chatEndRef = useRef<HTMLDivElement>(null)
  const userScrolledUpRef = useRef(false)

  const fetchSessions = async () => {
    try { setLoading(true); const res = await api.get('/agent/sessions'); setSessions(res.data) } catch { setSessions([]) } finally { setLoading(false) }
  }

  useEffect(() => { fetchSessions() }, [])

  const handleSelect = async (session: Session) => {
    if (!session.thread_id) return
    setSelectedSession(session)
    setMessages([])
    setLoadedMsgs(false)
    setActiveTools([])
    setToolHistory([])
    setShowToolPanel(false)
    try {
      const res = await api.get(`/agent/messages?thread_id=${encodeURIComponent(session.thread_id)}`)
      const msgs = (res.data || []).map((m: any, i: number) => ({ id: `hist-${i}`, role: m.role as 'user' | 'assistant', content: m.content || '' }))
      setMessages(msgs)
    } catch { setMessages([]) }
    finally { setLoadedMsgs(true) }
  }

  const handleDelete = async (id: string) => {
    if (!confirm('确定删除此会话？')) return
    try {
      await api.delete(`/agent/sessions/${id}`)
      if (selectedSession?.id === id) setSelectedSession(null)
      fetchSessions()
    } catch {}
  }

  const isNearBottom = useCallback(() => {
    const el = chatContainerRef.current; if (!el) return true
    return el.scrollHeight - el.scrollTop - el.clientHeight < 100
  }, [])

  const handleChatScroll = useCallback(() => {
    if (isNearBottom()) { userScrolledUpRef.current = false; setShowScrollBtn(false) }
    else { userScrolledUpRef.current = true; setShowScrollBtn(true) }
  }, [isNearBottom])

  useEffect(() => {
    if (!userScrolledUpRef.current) chatEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const handleSend = async () => {
    if (!input.trim() || streaming || !selectedSession?.thread_id) return
    const userMsg: Message = { id: Date.now().toString(), role: 'user', content: input.trim() }
    setMessages((prev) => [...prev, userMsg])
    setInput('')
    setStreaming(true)
    setActiveTools([])
    setToolHistory([])
    setShowToolPanel(false)
    userScrolledUpRef.current = false

    const assistantMsg: Message = { id: (Date.now() + 1).toString(), role: 'assistant', content: '' }
    setMessages((prev) => [...prev, assistantMsg])

    try {
      const token = localStorage.getItem('access_token')
      const spaceId = localStorage.getItem('current_space_id')
      const resp = await fetch('/api/v1/agent/chat', {
        method: 'POST', headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}`, 'X-Space-Id': spaceId || '' },
        body: JSON.stringify({ message: userMsg.content, thread_id: selectedSession.thread_id }),
      })
      if (!resp.ok) throw new Error('Failed')
      const reader = resp.body?.getReader()
      if (!reader) throw new Error('No body')
      const decoder = new TextDecoder()
      let content = ''
      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        const text = decoder.decode(value, { stream: true })
        for (const line of text.split('\n')) {
          if (!line.startsWith('data: ')) continue
          const data = line.slice(6).trim()
          if (data === '[DONE]') continue
          try {
            const parsed = JSON.parse(data)
            if (parsed.type === 'metadata') continue
            if (parsed.type === 'tool_start' && parsed.name) { setActiveTools((p) => [...p, parsed.name]); setToolHistory((p) => [...p, parsed.name]); continue }
            if (parsed.type === 'tool_end' && parsed.name) { setActiveTools((p) => p.filter((t) => t !== parsed.name)); continue }
            if (parsed.content) { content += parsed.content; setMessages((prev) => prev.map((m) => m.id === assistantMsg.id ? { ...m, content } : m)) }
            if (parsed.error) { content = `错误: ${parsed.error}`; setMessages((prev) => prev.map((m) => m.id === assistantMsg.id ? { ...m, content } : m)) }
          } catch {}
        }
      }
      setMessages((prev) => prev.map((m) => {
        if (m.id !== assistantMsg.id || !m.content) return m
        const w = extractWidget(m.content)
        if (w) return { ...m, widget: w, content: stripWidgetMarker(m.content) }
        return m
      }))
    } catch {
      setMessages((prev) => prev.map((m) => m.id === assistantMsg.id ? { ...m, content: '抱歉，发生了错误。请稍后重试。' } : m))
    } finally { setStreaming(false) }
  }

  const handleWidgetAction = async (msgId: string, action: 'confirm' | 'cancel', formData?: Record<string, string>) => {
    setMessages((prev) => prev.map((m) => m.id === msgId ? { ...m, widgetResolved: true } : m))
    const msg = messages.find((m) => m.id === msgId)
    const widget = msg?.widget
    if (!widget) return
    if (action === 'cancel') { setMessages((prev) => prev.map((m) => m.id === msgId ? { ...m, content: (m.content || '') + '\n\n*已取消*' } : m)); return }
    const source = widget._source
    if (source === 'asset_creator' && widget._creation_id) {
      try {
        const params = new URLSearchParams()
        if (selectedSession?.thread_id) params.set('thread_id', selectedSession.thread_id)
        if (widget._creation_id) params.set('creation_id', widget._creation_id)
        const res = await api.post(`/assets/confirm-pending?${params}`)
        setMessages((prev) => prev.map((m) => m.id === msgId ? { ...m, content: (m.content || '') + `\n\n> ${widget.title || '资产'}已创建 (${res.data.id})` } : m))
      } catch { setMessages((prev) => prev.map((m) => m.id === msgId ? { ...m, content: (m.content || '') + '\n\n*创建失败*' } : m)) }
      return
    }
    if (source === 'inspiration') {
      const selected = widget._cards?.filter((c: any) => Array.isArray(formData?.selected) ? (formData?.selected as string[])?.includes(c.id) : false)
      if (selected?.length) { setMessages((prev) => prev.map((m) => m.id === msgId ? { ...m, content: (m.content || '') + `\n\n> 已选择: ${selected.map((s: any) => s.name).join(', ')}` } : m)) }
      return
    }
    if (widget.type === 'form' && formData) {
      const payload: any = { name: formData.name || 'auto', description: formData.description || '', trigger_type: formData.trigger_type || 'cron', trigger_config: { expression: formData.cron_expr || '0 9 * * *' }, task_design: formData.task_design || '', visibility: formData.visibility || 'private' }
      try {
        const res = await api.post('/pipelines/from-conversation', payload)
        setMessages((prev) => prev.map((m) => m.id === msgId ? { ...m, content: (m.content || '') + `\n\n> 自动化「${res.data.name}」已创建` } : m))
      } catch (e: any) { setMessages((prev) => prev.map((m) => m.id === msgId ? { ...m, content: (m.content || '') + `\n\n*创建失败: ${e?.response?.data?.detail || '未知'}'*` } : m)) }
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSend() }
  }

  const formatTime = (s: string | null) => {
    if (!s) return ''
    const d = new Date(s); const now = new Date(); const diff = now.getTime() - d.getTime(); const days = Math.floor(diff / 86400000)
    if (days === 0) { const h = Math.floor(diff / 3600000); if (h === 0) { const m = Math.floor(diff / 60000); return m <= 1 ? '刚刚' : `${m} 分钟前` }; return `${h} 小时前` }
    if (days === 1) return '昨天 ' + d.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
    if (days < 7) return `${days} 天前`
    return d.toLocaleDateString('zh-CN', { month: 'short', day: 'numeric' })
  }

  return (
    <div className="flex-1 flex overflow-hidden">
      {/* Left: session list */}
      <div className="w-72 border-r border-gray-200 flex flex-col shrink-0 bg-white">
        <div className="p-4 border-b border-gray-100">
          <h2 className="text-sm font-semibold text-gray-900 flex items-center gap-2">
            <ClipboardList className="w-4 h-4" />任务记录
          </h2>
        </div>
        <div className="flex-1 overflow-y-auto p-2 space-y-1">
          {loading ? <div className="text-center py-8 text-gray-400 text-sm">加载中...</div> : sessions.length === 0 ? (
            <div className="text-center py-8 text-gray-400 text-sm">暂无记录</div>
          ) : sessions.map((s) => (
            <button
              key={s.id}
              onClick={() => handleSelect(s)}
              className={`w-full text-left px-3 py-2.5 rounded-lg text-sm transition-colors group ${
                selectedSession?.id === s.id ? 'bg-primary-50 text-primary-700' : 'hover:bg-gray-50 text-gray-700'
              }`}
            >
              <div className="flex items-center gap-2">
                <MessageSquare className="w-4 h-4 shrink-0 text-gray-400" />
                <span className="truncate font-medium">{s.title || '未命名会话'}</span>
              </div>
              <div className="text-[10px] text-gray-400 mt-0.5 ml-6">{formatTime(s.created_at)}</div>
              <button
                onClick={(e) => { e.stopPropagation(); handleDelete(s.id) }}
                className="hidden group-hover:block absolute right-2 top-2 p-1 text-gray-300 hover:text-red-500 rounded"
              >
                <Trash2 className="w-3.5 h-3.5" />
              </button>
            </button>
          ))}
        </div>
      </div>

      {/* Right: chat area */}
      <div className="flex-1 flex flex-col overflow-hidden bg-gray-50">
        {!selectedSession ? (
          <div className="flex-1 flex items-center justify-center text-gray-400 text-sm">
            <div className="text-center">
              <ClipboardList className="w-12 h-12 mx-auto mb-3 text-gray-300" />
              <p>选择左侧会话查看对话记录</p>
            </div>
          </div>
        ) : (
          <>
            {/* Chat header */}
            <div className="px-4 py-2 border-b border-gray-200 bg-white shrink-0 flex items-center justify-between">
              <span className="text-sm font-medium text-gray-700 truncate">{selectedSession.title || '未命名会话'}</span>
              <span className="text-[10px] text-gray-400 ml-2 shrink-0">{selectedSession.thread_id?.slice(-20)}</span>
            </div>

            {/* Messages */}
            <div ref={chatContainerRef} onScroll={handleChatScroll} className="flex-1 overflow-y-auto px-4 py-3 space-y-3">
              {!loadedMsgs ? (
                <div className="flex items-center justify-center h-full"><Loader2 className="w-5 h-5 animate-spin text-gray-300" /></div>
              ) : messages.length === 0 ? (
                <div className="flex items-center justify-center h-full text-gray-400 text-sm">此会话暂无消息</div>
              ) : (
                messages.map((msg) => <MsgBubble key={msg.id} msg={msg} onWidgetAction={(a, d) => handleWidgetAction(msg.id, a, d)} />)
              )}
              <div ref={chatEndRef} />
              {showScrollBtn && (
                <div className="sticky bottom-0 flex justify-center pb-1">
                  <button onClick={() => { userScrolledUpRef.current = false; chatEndRef.current?.scrollIntoView({ behavior: 'smooth' }); setShowScrollBtn(false) }}
                    className="bg-primary-600 text-white rounded-full px-3 py-1 text-xs shadow-lg">↓ 回到底部</button>
                </div>
              )}
            </div>

            {/* Tool status */}
            {(activeTools.length > 0 || (toolHistory.length > 0 && !streaming)) && (
              <div className="shrink-0 bg-gray-100 border-t border-gray-200">
                <button onClick={() => setShowToolPanel(!showToolPanel)} className="w-full flex items-center gap-2 px-4 py-1 text-xs text-gray-400 hover:text-gray-600">
                  <Wrench className={`w-3 h-3 ${activeTools.length > 0 ? 'animate-spin' : 'text-green-400'}`} />
                  <span className="truncate">{activeTools.length > 0 ? `执行: ${activeTools.join(', ')}...` : `工具记录 (${toolHistory.length})`}</span>
                  <span className="ml-auto">{showToolPanel ? <ChevronDown className="w-3 h-3" /> : <ChevronUp className="w-3 h-3" />}</span>
                </button>
                {showToolPanel && (
                  <div className="px-4 pb-2 max-h-24 overflow-y-auto">
                    {toolHistory.map((t, i) => (
                      <div key={`${t}-${i}`} className="flex items-center gap-1.5 text-xs py-0.5">
                        {activeTools.includes(t) ? <Loader2 className="w-2.5 h-2.5 animate-spin text-blue-400 shrink-0" /> : <Check className="w-2.5 h-2.5 text-green-400 shrink-0" />}
                        <span className="text-gray-500">{t}</span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}

            {/* Input */}
            <div className="border-t border-gray-200 bg-white px-4 py-3 shrink-0">
              <div className="flex items-end gap-2">
                <textarea value={input} onChange={(e) => setInput(e.target.value)} onKeyDown={handleKeyDown}
                  placeholder="继续对话... (Enter 发送)" rows={1} disabled={streaming}
                  className="input-field resize-none min-h-[36px] max-h-[120px] py-2 flex-1" />
                <button onClick={handleSend} disabled={!input.trim() || streaming}
                  className="shrink-0 w-9 h-9 bg-primary-600 text-white rounded-lg hover:bg-primary-700 disabled:opacity-50 flex items-center justify-center">
                  {streaming ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
                </button>
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  )
}

// ─── Message bubble (compact) ──────────────────────────────

function MsgBubble({ msg, onWidgetAction }: { msg: Message; onWidgetAction: (a: 'confirm' | 'cancel', d?: Record<string, string>) => void }) {
  const [selectedOpts, setSelectedOpts] = useState<string[]>([])
  if (!msg.widget || msg.widgetResolved) {
    return (
      <div className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
        <div className={`max-w-[80%] rounded-xl px-3 py-2 text-sm ${msg.role === 'user' ? 'bg-primary-600 text-white' : 'bg-white border border-gray-200 text-gray-800'}`}>
          <div className="whitespace-pre-wrap">{msg.content}</div>
        </div>
      </div>
    )
  }
  const w = msg.widget!
  return (
    <div className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
      <div className={`max-w-[80%] rounded-xl px-3 py-2 text-sm bg-white border border-gray-200 text-gray-800`}>
        {msg.content ? <div className="whitespace-pre-wrap mb-2">{msg.content}</div> : null}
        {w.type === 'confirm' && (
          <div className={`p-2.5 rounded-lg border ${w.danger ? 'border-red-200 bg-red-50' : 'border-primary-200 bg-primary-50'}`}>
            <div className="font-medium text-xs mb-1">{w.title}</div>
            <div className="text-xs text-gray-600 whitespace-pre-wrap mb-2">{w.message}</div>
            <div className="flex gap-2">
              <button onClick={() => onWidgetAction('confirm')} className={`flex-1 px-3 py-1.5 rounded text-xs font-medium text-white ${w.danger ? 'bg-red-600' : 'bg-primary-600'}`}><Check className="w-3 h-3 inline mr-1" />{w.confirm_label || '确认'}</button>
              <button onClick={() => onWidgetAction('cancel')} className="flex-1 px-3 py-1.5 rounded text-xs font-medium border border-gray-300 text-gray-600"><X className="w-3 h-3 inline mr-1" />{w.cancel_label || '取消'}</button>
            </div>
          </div>
        )}
        {w.type === 'form' && w.fields && (
          <FormWidget fields={w.fields} onSubmit={(d) => onWidgetAction('confirm', d)} onCancel={() => onWidgetAction('cancel')} />
        )}
        {w.type === 'select' && w.options && (
          <div className="p-2.5 rounded-lg border border-primary-200 bg-primary-50">
            <div className="font-medium text-xs mb-1">{w.title}</div>
            <div className="space-y-1 mb-2">
              {w.options.map((o: any) => (
                <button key={o.value} onClick={() => { if (w.multiple) setSelectedOpts((p) => p.includes(o.value) ? p.filter((v) => v !== o.value) : [...p, o.value]); else setSelectedOpts([o.value]) }}
                  className={`w-full text-left px-2.5 py-1.5 rounded text-xs border ${selectedOpts.includes(o.value) ? 'border-primary-500 bg-primary-100' : 'border-gray-200 bg-white'}`}>{o.label}</button>
              ))}
            </div>
            <button onClick={() => onWidgetAction('confirm', { selected: selectedOpts })} disabled={selectedOpts.length === 0} className="w-full px-3 py-1.5 rounded text-xs font-medium text-white bg-primary-600 disabled:opacity-50">确认</button>
          </div>
        )}
      </div>
    </div>
  )
}

function FormWidget({ fields, onSubmit, onCancel }: { fields: WidgetData['fields']; onSubmit: (d: Record<string, string>) => void; onCancel: () => void }) {
  const [fd, setFd] = useState<Record<string, string>>({})
  if (!fields) return null
  return (
    <form onSubmit={(e) => { e.preventDefault(); onSubmit(fd) }} className="space-y-2 p-2.5 rounded-lg border border-primary-200 bg-primary-50">
      <div className="font-medium text-xs mb-1">请填写信息</div>
      {fields.map((f) => (
        <div key={f.key}>
          <label className="block text-[10px] font-medium text-gray-500 mb-0.5">{f.label}{f.required && <span className="text-red-500">*</span>}</label>
          {f.field_type === 'select' ? (
            <select className="w-full border border-gray-200 rounded px-2 py-1 text-xs bg-white" value={fd[f.key] || f.default || ''} onChange={(e) => setFd({ ...fd, [f.key]: e.target.value })} required={f.required}>
              <option value="">请选择</option>
              {f.options?.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
            </select>
          ) : f.field_type === 'textarea' ? (
            <textarea className="w-full border border-gray-200 rounded px-2 py-1 text-xs resize-none" rows={2} placeholder={f.placeholder} value={fd[f.key] || f.default || ''} onChange={(e) => setFd({ ...fd, [f.key]: e.target.value })} required={f.required} />
          ) : (
            <input className="w-full border border-gray-200 rounded px-2 py-1 text-xs" placeholder={f.placeholder} value={fd[f.key] || f.default || ''} onChange={(e) => setFd({ ...fd, [f.key]: e.target.value })} required={f.required} />
          )}
        </div>
      ))}
      <div className="flex gap-2">
        <button type="submit" className="flex-1 bg-primary-600 text-white rounded px-3 py-1.5 text-xs font-medium">提交</button>
        <button type="button" onClick={onCancel} className="px-3 py-1.5 text-xs text-gray-500 border rounded">取消</button>
      </div>
    </form>
  )
}

function extractWidget(content: string): WidgetData | null {
  const start = content.lastIndexOf('[WIDGET:')
  if (start === -1) return null
  const jsonStart = start + 8
  const end = content.indexOf(']', jsonStart)
  if (end === -1) return null
  try { return JSON.parse(content.substring(jsonStart, end)) } catch { return null }
}

function stripWidgetMarker(content: string): string {
  const start = content.lastIndexOf('[WIDGET:')
  if (start === -1) return content
  const end = content.indexOf(']', start)
  if (end === -1) return content
  return (content.substring(0, start) + content.substring(end + 1)).trim()
}

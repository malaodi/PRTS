import { useState, useRef, useEffect, useCallback } from 'react'
import { Send, Loader2, ArrowDown, Check, X, Wrench, ChevronDown, ChevronUp } from 'lucide-react'
import { useSpaceStore } from '@/stores'
import api from '@/api/client'

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
  fields?: Array<{
    key: string; label: string; field_type: string; placeholder?: string; required?: boolean; default?: string
    options?: Array<{ value: string; label: string }>
  }>
  _source?: string
  _creation_id?: string
  _cards?: any[]
}

export default function ChatPage() {
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [streaming, setStreaming] = useState(false)
  const [showScrollBtn, setShowScrollBtn] = useState(false)
  const [activeTools, setActiveTools] = useState<string[]>([])
  const [toolHistory, setToolHistory] = useState<string[]>([])
  const [showToolPanel, setShowToolPanel] = useState(false)
  const [threadId, setThreadId] = useState('')
  const messagesContainerRef = useRef<HTMLDivElement>(null)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const currentSpace = useSpaceStore((s) => s.currentSpace)
  const userScrolledUpRef = useRef(false)

  // Clear any stored session on mount — fresh chat
  useEffect(() => {
    localStorage.removeItem('current_thread_id')
  }, [])

  const isNearBottom = useCallback(() => {
    const el = messagesContainerRef.current; if (!el) return true
    return el.scrollHeight - el.scrollTop - el.clientHeight < 100
  }, [])

  const handleContainerScroll = useCallback(() => {
    if (isNearBottom()) { userScrolledUpRef.current = false; setShowScrollBtn(false) }
    else { userScrolledUpRef.current = true; setShowScrollBtn(true) }
  }, [isNearBottom])

  useEffect(() => {
    if (!userScrolledUpRef.current) messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const handleSend = async () => {
    if (!input.trim() || streaming) return
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
        body: JSON.stringify({ message: userMsg.content }),
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
            if (parsed.type === 'metadata' && parsed.thread_id) { setThreadId(parsed.thread_id); localStorage.setItem('current_thread_id', parsed.thread_id); continue }
            if (parsed.type === 'tool_start' && parsed.name) { setActiveTools((p) => [...p, parsed.name]); setToolHistory((p) => [...p, parsed.name]); continue }
            if (parsed.type === 'tool_end' && parsed.name) { setActiveTools((p) => p.filter((t) => t !== parsed.name)); continue }
            if (parsed.content) { content += parsed.content; setMessages((prev) => prev.map((m) => m.id === assistantMsg.id ? { ...m, content } : m)) }
            if (parsed.error) { content = `错误: ${parsed.error}`; setMessages((prev) => prev.map((m) => m.id === assistantMsg.id ? { ...m, content } : m)) }
          } catch {}
        }
      }
      setMessages((prev) => prev.map((m) => {
        if (m.id !== assistantMsg.id || !m.content) return m
        const match = m.content.match(/\[WIDGET:({[\s\S]*?})\]/)
        if (match) { try { return { ...m, widget: JSON.parse(match[1]), content: m.content.replace(/\[WIDGET:{[\s\S]*?}\]/, '').trim() } } catch {} }
        return m
      }))
    } catch {
      setMessages((prev) => prev.map((m) => m.id === assistantMsg.id ? { ...m, content: '抱歉，发生了错误。请稍后重试。' } : m))
    } finally { setStreaming(false) }
  }

  const handleWidgetAction = async (msgId: string, action: 'confirm' | 'cancel', formData?: Record<string, string>) => {
    setMessages((prev) => prev.map((m) => m.id === msgId ? { ...m, widgetResolved: true } : m))
    const msg = messages.find((m) => m.id === msgId)
    const w = msg?.widget; if (!w) return
    if (action === 'cancel') { setMessages((prev) => prev.map((m) => m.id === msgId ? { ...m, content: (m.content || '') + '\n\n*已取消*' } : m)); return }
    if (w._source === 'asset_creator' && w._creation_id) {
      try { const p = new URLSearchParams(); if (threadId) p.set('thread_id', threadId); if (w._creation_id) p.set('creation_id', w._creation_id); const r = await api.post(`/assets/confirm-pending?${p}`); setMessages((prev) => prev.map((m) => m.id === msgId ? { ...m, content: (m.content || '') + `\n\n> ${w.title || '资产'}已创建 (${r.data.id})` } : m)) }
      catch { setMessages((prev) => prev.map((m) => m.id === msgId ? { ...m, content: (m.content || '') + '\n\n*创建失败*' } : m)) }
      return
    }
    if (w.type === 'form' && formData) {
      const payload: any = { name: formData.name || 'auto', description: formData.description || '', trigger_type: formData.trigger_type || 'cron', trigger_config: { expression: formData.cron_expr || '0 9 * * *' }, task_design: formData.task_design || '', visibility: formData.visibility || 'private' }
      try { const r = await api.post('/pipelines/from-conversation', payload); setMessages((prev) => prev.map((m) => m.id === msgId ? { ...m, content: (m.content || '') + `\n\n> 自动化「${r.data.name}」已创建` } : m)) }
      catch (e: any) { setMessages((prev) => prev.map((m) => m.id === msgId ? { ...m, content: (m.content || '') + `\n\n*创建失败: ${e?.response?.data?.detail || '未知'}*` } : m)) }
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSend() } }

  return (
    <div className="flex-1 flex flex-col overflow-hidden">
      <header className="bg-white border-b border-gray-200 px-6 py-3 shrink-0">
        <h2 className="text-sm font-semibold text-gray-900">{currentSpace ? currentSpace.name : 'PRTS Assistant'}</h2>
        <p className="text-xs text-gray-400">新会话</p>
      </header>

      <div ref={messagesContainerRef} onScroll={handleContainerScroll} className="flex-1 overflow-y-auto px-6 py-4 space-y-4">
        {messages.length === 0 && (
          <div className="flex items-center justify-center h-full">
            <div className="text-center">
              <div className="w-16 h-16 bg-primary-100 rounded-2xl flex items-center justify-center mx-auto mb-4"><Send className="w-8 h-8 text-primary-500" /></div>
              <h3 className="text-lg font-semibold text-gray-700">开始对话</h3>
              <p className="text-sm text-gray-400 mt-1">在下方输入你的问题，AI Agent 会帮你解决任务</p>
            </div>
          </div>
        )}
        {messages.map((msg) => <MsgB key={msg.id} msg={msg} onWidgetAction={(a, d) => handleWidgetAction(msg.id, a, d)} />)}
        <div ref={messagesEndRef} />
        {showScrollBtn && (
          <div className="sticky bottom-0 flex justify-center pb-2">
            <button onClick={() => { userScrolledUpRef.current = false; messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' }); setShowScrollBtn(false) }}
              className="bg-primary-600 text-white rounded-full px-4 py-1.5 text-xs shadow-lg flex items-center gap-1.5"><ArrowDown className="w-3.5 h-3.5" />回到底部</button>
          </div>
        )}
      </div>

      {(activeTools.length > 0 || (toolHistory.length > 0 && !streaming)) && (
        <div className="shrink-0 bg-gray-50 border-t border-gray-100">
          <button onClick={() => setShowToolPanel(!showToolPanel)} className="w-full flex items-center gap-2 px-4 py-1.5 text-xs text-gray-400 hover:text-gray-600">
            <Wrench className={`w-3 h-3 ${activeTools.length > 0 ? 'animate-spin' : 'text-green-400'}`} />
            <span className="truncate">{activeTools.length > 0 ? `正在执行: ${activeTools.join(', ')}...` : `工具调用记录 (${toolHistory.length})`}</span>
            <span className="ml-auto">{showToolPanel ? <ChevronDown className="w-3 h-3" /> : <ChevronUp className="w-3 h-3" />}</span>
          </button>
          {showToolPanel && (
            <div className="px-4 pb-2 max-h-32 overflow-y-auto">
              {toolHistory.map((t, i) => (
                <div key={`${t}-${i}`} className="flex items-center gap-2 text-xs py-0.5">
                  {activeTools.includes(t) ? <Loader2 className="w-3 h-3 animate-spin text-blue-400 shrink-0" /> : <Check className="w-3 h-3 text-green-400 shrink-0" />}
                  <span className={activeTools.includes(t) ? 'text-gray-600' : 'text-gray-400'}>{t}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      <div className="border-t border-gray-200 bg-white px-6 py-4 shrink-0">
        <div className="flex items-end gap-3 max-w-4xl mx-auto">
          <textarea value={input} onChange={(e) => setInput(e.target.value)} onKeyDown={handleKeyDown} placeholder="输入消息... (Enter 发送, Shift+Enter 换行)"
            className="input-field resize-none min-h-[44px] max-h-[200px] py-3" rows={1} disabled={streaming} />
          <button onClick={handleSend} disabled={!input.trim() || streaming}
            className="shrink-0 w-11 h-11 bg-primary-600 text-white rounded-xl hover:bg-primary-700 disabled:opacity-50 flex items-center justify-center">
            {streaming ? <Loader2 className="w-5 h-5 animate-spin" /> : <Send className="w-5 h-5" />}
          </button>
        </div>
      </div>
    </div>
  )
}

function MsgB({ msg, onWidgetAction }: { msg: Message; onWidgetAction: (a: 'confirm' | 'cancel', d?: Record<string, string>) => void }) {
  const [sel, setSel] = useState<string[]>([])
  if (!msg.widget || msg.widgetResolved) return (
    <div className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
      <div className={`max-w-[75%] rounded-2xl px-4 py-3 text-sm ${msg.role === 'user' ? 'bg-primary-600 text-white' : 'bg-white border border-gray-200 text-gray-800'}`}>
        {msg.role === 'assistant' && !msg.content ? <div className="flex items-center gap-2 text-gray-400"><Loader2 className="w-4 h-4 animate-spin" />思考中...</div> : <div className="whitespace-pre-wrap">{msg.content}</div>}
      </div>
    </div>
  )
  const w = msg.widget!
  return (
    <div className="flex justify-start">
      <div className="max-w-[75%] rounded-2xl px-4 py-3 text-sm bg-white border border-gray-200 text-gray-800">
        {msg.content ? <div className="whitespace-pre-wrap mb-2">{msg.content}</div> : null}
        {w.type === 'confirm' && (
          <div className={`p-3 rounded-xl border ${w.danger ? 'border-red-200 bg-red-50' : 'border-primary-200 bg-primary-50'}`}>
            <div className="font-medium text-sm mb-1">{w.title}</div>
            <div className="text-xs text-gray-600 whitespace-pre-wrap mb-3">{w.message}</div>
            <div className="flex gap-2">
              <button onClick={() => onWidgetAction('confirm')} className={`flex-1 px-4 py-2 rounded-lg text-sm font-medium text-white ${w.danger ? 'bg-red-600' : 'bg-primary-600'}`}><Check className="w-4 h-4 inline mr-1" />{w.confirm_label || '确认'}</button>
              <button onClick={() => onWidgetAction('cancel')} className="flex-1 px-4 py-2 rounded-lg text-sm font-medium border border-gray-300 text-gray-600"><X className="w-4 h-4 inline mr-1" />{w.cancel_label || '取消'}</button>
            </div>
          </div>
        )}
        {w.type === 'form' && w.fields && (
          <div className="p-3 rounded-xl border border-primary-200 bg-primary-50">
            <div className="font-medium text-sm mb-1">{w.title}</div>
            <form onSubmit={(e) => { e.preventDefault(); const fd: Record<string, string> = {}; new FormData(e.currentTarget).forEach((v, k) => fd[k] = v.toString()); onWidgetAction('confirm', fd) }} className="space-y-2">
              {w.fields.map((f) => (
                <div key={f.key}>
                  <label className="block text-xs font-medium text-gray-600 mb-1">{f.label}{f.required && <span className="text-red-500">*</span>}</label>
                  {f.field_type === 'select' ? (
                    <select name={f.key} className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm bg-white" defaultValue={f.default} required={f.required}>
                      <option value="">请选择</option>
                      {f.options?.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
                    </select>
                  ) : f.field_type === 'textarea' ? (
                    <textarea name={f.key} className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm resize-none" rows={3} placeholder={f.placeholder} defaultValue={f.default} required={f.required} />
                  ) : (
                    <input name={f.key} className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm" placeholder={f.placeholder} defaultValue={f.default} required={f.required} />
                  )}
                </div>
              ))}
              <div className="flex gap-2 pt-2">
                <button type="submit" className="flex-1 bg-primary-600 text-white rounded-lg px-4 py-2 text-sm font-medium">提交</button>
                <button type="button" onClick={() => onWidgetAction('cancel')} className="px-4 py-2 text-sm text-gray-500 border border-gray-200 rounded-lg">取消</button>
              </div>
            </form>
          </div>
        )}
      </div>
    </div>
  )
}

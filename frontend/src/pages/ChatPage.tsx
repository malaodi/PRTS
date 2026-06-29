import { useState, useRef, useEffect, useCallback } from 'react'
import { Send, Loader2, ArrowDown, Check, X } from 'lucide-react'
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
  content?: string
  fields?: Array<{
    key: string
    label: string
    field_type: string
    placeholder?: string
    required?: boolean
    default?: string
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
  const messagesContainerRef = useRef<HTMLDivElement>(null)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const currentSpace = useSpaceStore((s) => s.currentSpace)
  const userScrolledUpRef = useRef(false)

  const isNearBottom = useCallback(() => {
    const el = messagesContainerRef.current
    if (!el) return true
    return el.scrollHeight - el.scrollTop - el.clientHeight < 100
  }, [])

  const scrollToBottom = useCallback((force = false) => {
    if (!force && userScrolledUpRef.current) return
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [])

  const handleContainerScroll = useCallback(() => {
    if (isNearBottom()) {
      userScrolledUpRef.current = false
      setShowScrollBtn(false)
    } else {
      userScrolledUpRef.current = true
      setShowScrollBtn(true)
    }
  }, [isNearBottom])

  // Auto-scroll only when new messages arrive and user is at bottom
  useEffect(() => {
    if (!userScrolledUpRef.current) {
      messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
    }
  }, [messages])

  const handleSend = async () => {
    if (!input.trim() || streaming) return

    const userMsg: Message = {
      id: Date.now().toString(),
      role: 'user',
      content: input.trim(),
    }
    setMessages((prev) => [...prev, userMsg])
    setInput('')
    setStreaming(true)
    userScrolledUpRef.current = false

    const assistantMsg: Message = {
      id: (Date.now() + 1).toString(),
      role: 'assistant',
      content: '',
    }
    setMessages((prev) => [...prev, assistantMsg])

    try {
      const token = localStorage.getItem('access_token')
      const spaceId = localStorage.getItem('current_space_id')
      const response = await fetch('/api/v1/agent/chat', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
          'X-Space-Id': spaceId || '',
        },
        body: JSON.stringify({ message: userMsg.content }),
      })

      if (!response.ok) throw new Error('Chat request failed')

      const reader = response.body?.getReader()
      const decoder = new TextDecoder()
      if (!reader) throw new Error('No response body')

      let content = ''
      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        const text = decoder.decode(value, { stream: true })
        const lines = text.split('\n')
        for (const line of lines) {
          if (!line.startsWith('data: ')) continue
          const data = line.slice(6).trim()
          if (data === '[DONE]') continue

          try {
            const parsed = JSON.parse(data)
            if (parsed.type === 'metadata' && parsed.thread_id) {
              localStorage.setItem('current_thread_id', parsed.thread_id)
              continue
            }
            if (parsed.type === 'tool_start') {
              // Tool call started - could show indicator
              continue
            }
            if (parsed.type === 'tool_end') {
              continue
            }
            if (parsed.content) {
              content += parsed.content
              setMessages((prev) =>
                prev.map((m) =>
                  m.id === assistantMsg.id ? { ...m, content } : m,
                ),
              )
            }
            if (parsed.error) {
              content = `错误: ${parsed.error}`
              setMessages((prev) =>
                prev.map((m) =>
                  m.id === assistantMsg.id ? { ...m, content } : m,
                ),
              )
            }
          } catch {
            // skip partial JSON
          }
        }
      }

      // After streaming ends, check for widgets in content
      setMessages((prev) =>
        prev.map((m) => {
          if (m.id !== assistantMsg.id || !m.content) return m
          const widget = extractWidget(m.content)
          if (widget) {
            return {
              ...m,
              widget,
              content: stripWidgetMarker(m.content),
            }
          }
          return m
        }),
      )
    } catch {
      setMessages((prev) =>
        prev.map((m) =>
          m.id === assistantMsg.id
            ? { ...m, content: '抱歉，发生了错误。请稍后重试。' }
            : m,
        ),
      )
    } finally {
      setStreaming(false)
    }
  }

  const handleWidgetAction = async (msgId: string, action: 'confirm' | 'cancel', formData?: Record<string, string>) => {
    setMessages((prev) =>
      prev.map((m) =>
        m.id === msgId ? { ...m, widgetResolved: true } : m,
      ),
    )

    const msg = messages.find((m) => m.id === msgId)
    const widget = msg?.widget
    if (!widget) return

    if (action === 'cancel') {
      setMessages((prev) =>
        prev.map((m) =>
          m.id === msgId ? { ...m, content: m.content + '\n\n*已取消*' } : m,
        ),
      )
      return
    }

    const source = widget._source

    if (source === 'asset_creator' && widget._creation_id) {
      try {
        const threadId = localStorage.getItem('current_thread_id') || ''
        const params = new URLSearchParams()
        if (threadId) params.set('thread_id', threadId)
        if (widget._creation_id) params.set('creation_id', widget._creation_id)
        const res = await api.post(`/assets/confirm-pending?${params}`)
        const typeLabel = widget.title || '资产'
        setMessages((prev) =>
          prev.map((m) =>
            m.id === msgId
              ? { ...m, content: m.content + `\n\n> ${typeLabel}已创建成功 (ID: ${res.data.id})` }
              : m,
          ),
        )
      } catch {
        setMessages((prev) =>
          prev.map((m) =>
            m.id === msgId ? { ...m, content: m.content + '\n\n*创建失败，请重试*' } : m,
          ),
        )
      }
      return
    }

    if (source === 'inspiration') {
      const selected = widget._cards?.filter((c: any) =>
        Array.isArray(formData?.selected)
          ? (formData?.selected as string[])?.includes(c.id)
          : false,
      )
      if (selected?.length) {
        setMessages((prev) =>
          prev.map((m) =>
            m.id === msgId
              ? { ...m, content: m.content + `\n\n> 已选择安装: ${selected.map((s: any) => s.name).join(', ')}（功能待实现）` }
              : m,
          ),
        )
      }
      return
    }

    // Generic form submit -> create pipeline
    if (widget.type === 'form' && formData) {
      const payload: any = {
        name: formData.name || '自动化',
        description: formData.description || '',
        trigger_type: formData.trigger_type || 'cron',
        trigger_config: { expression: formData.cron_expr || '0 9 * * *' },
        task_design: formData.task_design || '',
        visibility: formData.visibility || 'private',
      }
      try {
        const res = await api.post('/pipelines/from-conversation', payload)
        setMessages((prev) =>
          prev.map((m) =>
            m.id === msgId
              ? { ...m, content: m.content + `\n\n> 自动化「${res.data.name}」已创建` }
              : m,
          ),
        )
      } catch (e: any) {
        setMessages((prev) =>
          prev.map((m) =>
            m.id === msgId
              ? { ...m, content: m.content + `\n\n*创建失败: ${e?.response?.data?.detail || '未知错误'}*` }
              : m,
          ),
        )
      }
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  return (
    <div className="flex-1 flex flex-col overflow-hidden">
      {/* Header */}
      <header className="bg-white border-b border-gray-200 px-6 py-3 shrink-0">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-sm font-semibold text-gray-900">
              {currentSpace ? currentSpace.name : 'PRTS Assistant'}
            </h2>
            <p className="text-xs text-gray-400">Agent 对话</p>
          </div>
        </div>
      </header>

      {/* Messages */}
      <div
        ref={messagesContainerRef}
        onScroll={handleContainerScroll}
        className="flex-1 overflow-y-auto px-6 py-4 space-y-4"
      >
        {messages.length === 0 && (
          <div className="flex items-center justify-center h-full">
            <div className="text-center">
              <div className="w-16 h-16 bg-primary-100 rounded-2xl flex items-center justify-center mx-auto mb-4">
                <Send className="w-8 h-8 text-primary-500" />
              </div>
              <h3 className="text-lg font-semibold text-gray-700">开始对话</h3>
              <p className="text-sm text-gray-400 mt-1">
                在下方输入你的问题，AI Agent 会帮你解决任务
              </p>
            </div>
          </div>
        )}

        {messages.map((msg) => (
          <MessageBubble
            key={msg.id}
            msg={msg}
            onWidgetAction={(action, formData) => handleWidgetAction(msg.id, action, formData)}
          />
        ))}
        <div ref={messagesEndRef} />

        {/* Scroll to bottom button */}
        {showScrollBtn && (
          <div className="sticky bottom-0 flex justify-center">
            <button
              onClick={() => {
                userScrolledUpRef.current = false
                scrollToBottom(true)
                setShowScrollBtn(false)
              }}
              className="bg-primary-600 text-white rounded-full px-4 py-1.5 text-xs shadow-lg hover:bg-primary-700 flex items-center gap-1.5"
            >
              <ArrowDown className="w-3.5 h-3.5" />
              回到底部
            </button>
          </div>
        )}
      </div>

      {/* Input */}
      <div className="border-t border-gray-200 bg-white px-6 py-4 shrink-0">
        <div className="flex items-end gap-3 max-w-4xl mx-auto">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="输入消息... (Enter 发送, Shift+Enter 换行)"
            className="input-field resize-none min-h-[44px] max-h-[200px] py-3"
            rows={1}
            disabled={streaming}
          />
          <button
            onClick={handleSend}
            disabled={!input.trim() || streaming}
            className="shrink-0 w-11 h-11 bg-primary-600 text-white rounded-xl hover:bg-primary-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center transition-colors"
          >
            {streaming ? (
              <Loader2 className="w-5 h-5 animate-spin" />
            ) : (
              <Send className="w-5 h-5" />
            )}
          </button>
        </div>
      </div>
    </div>
  )
}

// ─── Widget parser ──────────────────────────────────────────

function extractWidget(content: string): WidgetData | null {
  const match = content.match(/\[WIDGET:({[\s\S]*?})\]/)
  if (!match) return null
  try {
    return JSON.parse(match[1])
  } catch {
    return null
  }
}

function stripWidgetMarker(content: string): string {
  return content.replace(/\[WIDGET:{[\s\S]*?}\]/, '').trim()
}

// ─── Widget form state ──────────────────────────────────────

function WidgetFormFields({
  fields,
  onSubmit,
  onCancel,
}: {
  fields: Array<{ key: string; label: string; field_type: string; placeholder?: string; required?: boolean; default?: string; options?: Array<{ value: string; label: string }> }>
  onSubmit: (data: Record<string, string>) => void
  onCancel: () => void
}) {
  const [formData, setFormData] = useState<Record<string, string>>({})

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    onSubmit(formData)
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-3">
      {fields.map((field) => (
        <div key={field.key}>
          <label className="block text-xs font-medium text-gray-600 mb-1">
            {field.label}
            {field.required && <span className="text-red-500 ml-0.5">*</span>}
          </label>
          {field.field_type === 'select' || field.field_type === 'credential' ? (
            <select
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm bg-white"
              value={formData[field.key] || field.default || ''}
              onChange={(e) => setFormData({ ...formData, [field.key]: e.target.value })}
              required={field.required}
            >
              <option value="">请选择</option>
              {field.options?.map((opt) => (
                <option key={opt.value} value={opt.value}>{opt.label}</option>
              ))}
            </select>
          ) : field.field_type === 'multiselect' ? (
            <div className="space-y-1 max-h-32 overflow-y-auto border border-gray-200 rounded-lg p-2">
              {field.options?.map((opt) => {
                const selected = (formData[field.key] || '').split(',').includes(opt.value)
                return (
                  <label key={opt.value} className="flex items-center gap-2 text-sm py-0.5 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={selected}
                      onChange={() => {
                        const prev = (formData[field.key] || '').split(',').filter(Boolean)
                        const next = selected ? prev.filter((v) => v !== opt.value) : [...prev, opt.value]
                        setFormData({ ...formData, [field.key]: next.join(',') })
                      }}
                    />
                    {opt.label}
                  </label>
                )
              })}
            </div>
          ) : field.field_type === 'textarea' ? (
            <textarea
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm resize-none"
              rows={3}
              placeholder={field.placeholder}
              value={formData[field.key] || field.default || ''}
              onChange={(e) => setFormData({ ...formData, [field.key]: e.target.value })}
              required={field.required}
            />
          ) : (
            <input
              type={field.field_type === 'number' ? 'number' : 'text'}
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm"
              placeholder={field.placeholder}
              value={formData[field.key] || field.default || ''}
              onChange={(e) => setFormData({ ...formData, [field.key]: e.target.value })}
              required={field.required}
            />
          )}
        </div>
      ))}
      <div className="flex gap-2 pt-2">
        <button
          type="submit"
          className="flex-1 bg-primary-600 text-white rounded-lg px-4 py-2 text-sm font-medium hover:bg-primary-700"
        >
          提交
        </button>
        <button
          type="button"
          onClick={onCancel}
          className="px-4 py-2 text-sm text-gray-500 hover:text-gray-700 border border-gray-200 rounded-lg"
        >
          取消
        </button>
      </div>
    </form>
  )
}

// ─── Message bubble with widget support ─────────────────────

function MessageBubble({
  msg,
  onWidgetAction,
}: {
  msg: Message
  onWidgetAction: (action: 'confirm' | 'cancel', formData?: Record<string, string>) => void
}) {
  const [selectedOptions, setSelectedOptions] = useState<string[]>([])

  const renderWidget = () => {
    if (!msg.widget || msg.widgetResolved) return null
    const w = msg.widget

    if (w.type === 'confirm') {
      return (
        <div className={`mt-3 p-3 rounded-xl border ${w.danger ? 'border-red-200 bg-red-50' : 'border-primary-200 bg-primary-50'}`}>
          <div className="font-medium text-sm mb-2">{w.title}</div>
          <div className="text-xs text-gray-600 whitespace-pre-wrap mb-3">{w.message}</div>
          <div className="flex gap-2">
            <button
              onClick={() => onWidgetAction('confirm')}
              className={`flex-1 px-4 py-2 rounded-lg text-sm font-medium text-white ${
                w.danger ? 'bg-red-600 hover:bg-red-700' : 'bg-primary-600 hover:bg-primary-700'
              }`}
            >
              <Check className="w-4 h-4 inline mr-1" />
              {w.confirm_label || '确认'}
            </button>
            <button
              onClick={() => onWidgetAction('cancel')}
              className="flex-1 px-4 py-2 rounded-lg text-sm font-medium border border-gray-300 text-gray-600 hover:bg-gray-50"
            >
              <X className="w-4 h-4 inline mr-1" />
              {w.cancel_label || '取消'}
            </button>
          </div>
        </div>
      )
    }

    if (w.type === 'select' && w.options) {
      const toggleOption = (value: string) => {
        if (w.multiple) {
          setSelectedOptions((prev) =>
            prev.includes(value) ? prev.filter((v) => v !== value) : [...prev, value],
          )
        } else {
          setSelectedOptions([value])
        }
      }

      return (
        <div className="mt-3 p-3 rounded-xl border border-primary-200 bg-primary-50">
          <div className="font-medium text-sm mb-1">{w.title}</div>
          <div className="text-xs text-gray-500 mb-2">{w.message}</div>
          <div className="space-y-1 mb-3">
            {w.options.map((opt: any) => (
              <button
                key={opt.value}
                onClick={() => toggleOption(opt.value)}
                className={`w-full text-left px-3 py-2 rounded-lg text-sm border transition-colors ${
                  selectedOptions.includes(opt.value)
                    ? 'border-primary-500 bg-primary-100 text-primary-700'
                    : 'border-gray-200 bg-white text-gray-700 hover:border-gray-300'
                }`}
              >
                <div className="font-medium">{opt.label}</div>
                {opt.description && <div className="text-xs text-gray-400">{opt.description}</div>}
              </button>
            ))}
          </div>
          <button
            onClick={() => onWidgetAction('confirm', { selected: selectedOptions })}
            disabled={selectedOptions.length === 0}
            className="w-full px-4 py-2 rounded-lg text-sm font-medium text-white bg-primary-600 hover:bg-primary-700 disabled:opacity-50"
          >
            确认选择
          </button>
        </div>
      )
    }

    if (w.type === 'form' && w.fields) {
      return (
        <div className="mt-3 p-3 rounded-xl border border-primary-200 bg-primary-50">
          <div className="font-medium text-sm mb-1">{w.title}</div>
          <div className="text-xs text-gray-500 mb-3">{w.message}</div>
          <WidgetFormFields
            fields={w.fields}
            onSubmit={(data) => onWidgetAction('confirm', data)}
            onCancel={() => onWidgetAction('cancel')}
          />
        </div>
      )
    }

    return null
  }

  return (
    <div className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
      <div
        className={`max-w-[75%] rounded-2xl px-4 py-3 text-sm leading-relaxed ${
          msg.role === 'user'
            ? 'bg-primary-600 text-white'
            : 'bg-white border border-gray-200 text-gray-800'
        }`}
      >
        {msg.role === 'assistant' && !msg.content && !msg.widget ? (
          <div className="flex items-center gap-2 text-gray-400">
            <Loader2 className="w-4 h-4 animate-spin" />
            思考中...
          </div>
        ) : (
          <>
            {msg.content && <div className="whitespace-pre-wrap">{msg.content}</div>}
            {renderWidget()}
          </>
        )}
      </div>
    </div>
  )
}

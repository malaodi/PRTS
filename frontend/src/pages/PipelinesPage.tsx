import { useState, useEffect } from 'react'
import api from '@/api/client'
import { useSpaceStore } from '@/stores'
import { Zap, Plus, Trash2, Play, Pause, Clock, Webhook, Bell, ChevronDown, ChevronRight } from 'lucide-react'

interface Pipeline {
  id: string
  name: string
  description: string | null
  trigger_type: string
  trigger_config: any
  task_design: string
  status: string
  visibility: string | null
  tags: string | null
  created_at: string | null
  last_run_at: string | null
}

interface PipelineRun {
  id: string
  pipeline_id: string
  status: string
  result_summary: string | null
  error_message: string | null
  started_at: string | null
  completed_at: string | null
}

const TRIGGER_LABELS: Record<string, { label: string; icon: typeof Zap }> = {
  cron: { label: 'Cron 定时', icon: Clock },
  webhook: { label: 'Webhook', icon: Webhook },
  event: { label: 'Event 事件', icon: Bell },
}

export default function PipelinesPage() {
  const [pipelines, setPipelines] = useState<Pipeline[]>([])
  const [loading, setLoading] = useState(true)
  const [showCreate, setShowCreate] = useState(false)
  const [expandedPipeline, setExpandedPipeline] = useState<string | null>(null)
  const [pipelineRuns, setPipelineRuns] = useState<Record<string, PipelineRun[]>>({})
  const currentSpace = useSpaceStore((s) => s.currentSpace)

  const [form, setForm] = useState({
    name: '',
    description: '',
    trigger_type: 'cron',
    cron_expr: '0 9 * * *',
    task_design: '',
    visibility: 'private',
  })

  const fetchPipelines = async () => {
    try {
      setLoading(true)
      const res = await api.get('/pipelines')
      setPipelines(res.data)
    } catch {
      setPipelines([])
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchPipelines()
  }, [currentSpace])

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!form.name.trim() || !form.task_design.trim()) return
    try {
      await api.post('/pipelines', {
        name: form.name,
        description: form.description,
        trigger_type: form.trigger_type,
        trigger_config: { expression: form.cron_expr },
        task_design: form.task_design,
        visibility: form.visibility,
      })
      setForm({ name: '', description: '', trigger_type: 'cron', cron_expr: '0 9 * * *', task_design: '', visibility: 'private' })
      setShowCreate(false)
      fetchPipelines()
    } catch {}
  }

  const handleDelete = async (id: string) => {
    if (!confirm('确定删除此管道？')) return
    try {
      await api.delete(`/pipelines/${id}`)
      fetchPipelines()
    } catch {}
  }

  const handleStatusToggle = async (pipeline: Pipeline) => {
    const newStatus = pipeline.status === 'active' ? 'paused' : 'active'
    try {
      await api.patch(`/pipelines/${pipeline.id}`, { status: newStatus })
      fetchPipelines()
    } catch {}
  }

  const toggleRuns = async (pipelineId: string) => {
    if (expandedPipeline === pipelineId) {
      setExpandedPipeline(null)
      return
    }
    setExpandedPipeline(pipelineId)
    try {
      const res = await api.get(`/pipelines/${pipelineId}/runs`)
      setPipelineRuns((prev) => ({ ...prev, [pipelineId]: res.data }))
    } catch {}
  }

  const formatTime = (s: string | null) => {
    if (!s) return '—'
    return new Date(s).toLocaleString('zh-CN')
  }

  const statusBadge = (status: string) => {
    const map: Record<string, string> = {
      active: 'bg-green-100 text-green-700',
      paused: 'bg-amber-100 text-amber-700',
      error: 'bg-red-100 text-red-700',
    }
    const labels: Record<string, string> = { active: '运行中', paused: '已暂停', error: '异常' }
    return (
      <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${map[status] || 'bg-gray-100 text-gray-600'}`}>
        {labels[status] || status}
      </span>
    )
  }

  const runStatusBadge = (status: string) => {
    const map: Record<string, string> = {
      running: 'bg-blue-100 text-blue-700',
      completed: 'bg-green-100 text-green-700',
      failed: 'bg-red-100 text-red-700',
    }
    const labels: Record<string, string> = { running: '运行中', completed: '已完成', failed: '失败' }
    return (
      <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${map[status] || 'bg-gray-100 text-gray-600'}`}>
        {labels[status] || status}
      </span>
    )
  }

  return (
    <div className="flex-1 overflow-y-auto p-6">
      <div className="max-w-4xl mx-auto">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h2 className="text-xl font-bold text-gray-900">自动化</h2>
            <p className="text-sm text-gray-500 mt-1">配置定时任务、Webhook 或事件触发，让 Agent 自动执行</p>
          </div>
          <button onClick={() => setShowCreate(!showCreate)} className="btn-primary">
            <Plus className="w-4 h-4 inline mr-1" />
            新建管道
          </button>
        </div>

        {/* Create Form */}
        {showCreate && (
          <form onSubmit={handleCreate} className="card mb-6 space-y-3">
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">管道名称</label>
                <input
                  className="input-field"
                  placeholder="每日站会摘要"
                  value={form.name}
                  onChange={(e) => setForm({ ...form, name: e.target.value })}
                  required
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">触发类型</label>
                <select
                  className="input-field"
                  value={form.trigger_type}
                  onChange={(e) => setForm({ ...form, trigger_type: e.target.value })}
                >
                  <option value="cron">Cron 定时</option>
                  <option value="webhook">Webhook</option>
                  <option value="event">Event 事件</option>
                </select>
              </div>
            </div>
            {form.trigger_type === 'cron' && (
              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">Cron 表达式</label>
                <input
                  className="input-field font-mono text-sm"
                  placeholder="0 9 * * *"
                  value={form.cron_expr}
                  onChange={(e) => setForm({ ...form, cron_expr: e.target.value })}
                />
                <p className="text-xs text-gray-400 mt-1">
                  分 时 日 月 周。例：0 9 * * * 每天9点；0 */2 * * * 每2小时
                </p>
              </div>
            )}
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">描述</label>
                <input
                  className="input-field"
                  placeholder="管道功能描述"
                  value={form.description}
                  onChange={(e) => setForm({ ...form, description: e.target.value })}
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">可见性</label>
                <select
                  className="input-field"
                  value={form.visibility}
                  onChange={(e) => setForm({ ...form, visibility: e.target.value })}
                >
                  <option value="private">仅自己</option>
                  <option value="team">团队可见</option>
                  <option value="public">公开（广场）</option>
                </select>
              </div>
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">任务描述</label>
              <textarea
                className="input-field"
                rows={3}
                placeholder="Agent 需要执行的任务描述，如：从 GitHub 获取昨日 commit 记录并生成摘要"
                value={form.task_design}
                onChange={(e) => setForm({ ...form, task_design: e.target.value })}
                required
              />
            </div>
            <div className="flex gap-2">
              <button type="submit" className="btn-primary text-sm">创建</button>
              <button type="button" onClick={() => setShowCreate(false)} className="btn-secondary text-sm">取消</button>
            </div>
          </form>
        )}

        {/* Pipeline List */}
        {loading ? (
          <div className="text-center py-12 text-gray-400">加载中...</div>
        ) : pipelines.length === 0 ? (
          <div className="text-center py-16">
            <Zap className="w-12 h-12 mx-auto mb-3 text-gray-300" />
            <h3 className="text-sm font-medium text-gray-500">暂无自动化管道</h3>
            <p className="text-xs text-gray-400 mt-1">创建第一个管道，让 Agent 自动执行任务</p>
          </div>
        ) : (
          <div className="space-y-3">
            {pipelines.map((pipeline) => {
              const trigger = TRIGGER_LABELS[pipeline.trigger_type] || TRIGGER_LABELS.cron
              const TIcon = trigger.icon
              return (
                <div key={pipeline.id} className="card">
                  <div className="flex items-start justify-between">
                    <div className="flex items-start gap-3 min-w-0 flex-1">
                      <div className="w-10 h-10 rounded-lg bg-primary-50 flex items-center justify-center shrink-0 mt-0.5">
                        <TIcon className="w-5 h-5 text-primary-600" />
                      </div>
                      <div className="min-w-0 flex-1">
                        <div className="flex items-center gap-2 flex-wrap">
                          <span className="text-sm font-medium text-gray-800">{pipeline.name}</span>
                          {statusBadge(pipeline.status)}
                          <span className="text-xs text-gray-400 bg-gray-50 px-1.5 py-0.5 rounded">
                            {trigger.label}
                          </span>
                        </div>
                        {pipeline.description && (
                          <p className="text-xs text-gray-500 mt-0.5 line-clamp-1">{pipeline.description}</p>
                        )}
                        <p className="text-xs text-gray-400 mt-1">
                          上次运行：{formatTime(pipeline.last_run_at)}
                        </p>
                      </div>
                    </div>
                    <div className="flex items-center gap-1 shrink-0">
                      <button
                        onClick={() => handleStatusToggle(pipeline)}
                        className={`p-1.5 rounded-lg transition-colors ${
                          pipeline.status === 'active'
                            ? 'text-amber-500 hover:bg-amber-50'
                            : 'text-green-500 hover:bg-green-50'
                        }`}
                        title={pipeline.status === 'active' ? '暂停' : '启用'}
                      >
                        {pipeline.status === 'active' ? <Pause className="w-4 h-4" /> : <Play className="w-4 h-4" />}
                      </button>
                      <button
                        onClick={() => handleDelete(pipeline.id)}
                        className="p-1.5 text-gray-300 hover:text-red-500 rounded-lg hover:bg-red-50 transition-colors"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                      <button
                        onClick={() => toggleRuns(pipeline.id)}
                        className="p-1.5 text-gray-300 hover:text-gray-500 rounded-lg hover:bg-gray-50 transition-colors"
                      >
                        {expandedPipeline === pipeline.id ? (
                          <ChevronDown className="w-4 h-4" />
                        ) : (
                          <ChevronRight className="w-4 h-4" />
                        )}
                      </button>
                    </div>
                  </div>

                  {/* Runs Sub-panel */}
                  {expandedPipeline === pipeline.id && (
                    <div className="mt-3 pt-3 border-t border-gray-100">
                      {(pipelineRuns[pipeline.id] || []).length === 0 ? (
                        <p className="text-xs text-gray-400 py-2">暂无运行记录</p>
                      ) : (
                        <div className="space-y-2 max-h-64 overflow-y-auto">
                          {pipelineRuns[pipeline.id].map((run) => (
                            <div key={run.id} className="flex items-start justify-between bg-gray-50 rounded-lg p-2.5">
                              <div className="min-w-0 flex-1">
                                <div className="flex items-center gap-2 mb-0.5">
                                  {runStatusBadge(run.status)}
                                  <span className="text-xs text-gray-400">{formatTime(run.started_at)}</span>
                                </div>
                                {run.result_summary && (
                                  <p className="text-xs text-gray-600 line-clamp-2">{run.result_summary}</p>
                                )}
                                {run.error_message && (
                                  <p className="text-xs text-red-500 line-clamp-2">{run.error_message}</p>
                                )}
                              </div>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        )}
      </div>
    </div>
  )
}

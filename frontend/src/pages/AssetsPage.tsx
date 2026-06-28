import { useState, useEffect } from 'react'
import api from '@/api/client'
import { useSpaceStore } from '@/stores'
import { Box, Plus, Trash2, Link as LinkIcon, Wrench, Bot, Plug, Layout } from 'lucide-react'

interface Asset {
  id: string
  space_id: string
  asset_type: string
  name: string
  description: string | null
  config: any
  created_at: string | null
}

const ASSET_TYPES = [
  { key: 'skill', label: '技能', icon: Box, color: 'text-blue-600 bg-blue-50' },
  { key: 'tool', label: '工具', icon: Wrench, color: 'text-green-600 bg-green-50' },
  { key: 'subagent', label: '伙伴', icon: Bot, color: 'text-purple-600 bg-purple-50' },
  { key: 'mcp', label: 'MCP', icon: Plug, color: 'text-orange-600 bg-orange-50' },
  { key: 'widget', label: '卡片', icon: Layout, color: 'text-pink-600 bg-pink-50' },
]

export default function AssetsPage() {
  const [assets, setAssets] = useState<Asset[]>([])
  const [filter, setFilter] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [showCreate, setShowCreate] = useState(false)
  const [newAsset, setNewAsset] = useState({ asset_type: 'skill', name: '', description: '' })
  const currentSpace = useSpaceStore((s) => s.currentSpace)

  const fetchAssets = async () => {
    try {
      setLoading(true)
      const params = filter ? `?asset_type=${filter}` : ''
      const res = await api.get(`/assets${params}`)
      setAssets(res.data)
    } catch {
      setAssets([])
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchAssets()
  }, [filter, currentSpace])

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!newAsset.name.trim()) return
    try {
      await api.post('/assets', newAsset)
      setNewAsset({ asset_type: 'skill', name: '', description: '' })
      setShowCreate(false)
      fetchAssets()
    } catch {}
  }

  const handleDelete = async (id: string) => {
    if (!confirm('确定删除此资产？')) return
    try {
      await api.delete(`/assets/${id}`)
      fetchAssets()
    } catch {}
  }

  return (
    <div className="flex-1 overflow-y-auto p-6">
      <div className="max-w-4xl mx-auto">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h2 className="text-xl font-bold text-gray-900">智能体资产</h2>
            <p className="text-sm text-gray-500 mt-1">管理空间内的技能、工具、伙伴、MCP 和卡片</p>
          </div>
          <button onClick={() => setShowCreate(!showCreate)} className="btn-primary">
            <Plus className="w-4 h-4 inline mr-1" />
            创建资产
          </button>
        </div>

        {/* Create Form */}
        {showCreate && (
          <form onSubmit={handleCreate} className="card mb-4 space-y-3">
            <div className="flex gap-2">
              {ASSET_TYPES.map((t) => (
                <button
                  key={t.key}
                  type="button"
                  onClick={() => setNewAsset({ ...newAsset, asset_type: t.key })}
                  className={`flex items-center gap-1 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
                    newAsset.asset_type === t.key ? t.color : 'text-gray-500 bg-gray-50'
                  }`}
                >
                  <t.icon className="w-3 h-3" />
                  {t.label}
                </button>
              ))}
            </div>
            <input
              className="input-field"
              placeholder="资产名称"
              value={newAsset.name}
              onChange={(e) => setNewAsset({ ...newAsset, name: e.target.value })}
              required
            />
            <textarea
              className="input-field"
              placeholder="描述（可选）"
              value={newAsset.description}
              onChange={(e) => setNewAsset({ ...newAsset, description: e.target.value })}
              rows={2}
            />
            <div className="flex gap-2">
              <button type="submit" className="btn-primary text-sm">创建</button>
              <button type="button" onClick={() => setShowCreate(false)} className="btn-secondary text-sm">取消</button>
            </div>
          </form>
        )}

        {/* Filter */}
        <div className="flex gap-2 mb-4">
          <button
            onClick={() => setFilter(null)}
            className={`px-3 py-1.5 rounded-lg text-xs font-medium ${
              filter === null ? 'bg-primary-50 text-primary-700' : 'text-gray-500 hover:bg-gray-50'
            }`}
          >
            全部
          </button>
          {ASSET_TYPES.map((t) => (
            <button
              key={t.key}
              onClick={() => setFilter(t.key)}
              className={`flex items-center gap-1 px-3 py-1.5 rounded-lg text-xs font-medium ${
                filter === t.key ? t.color : 'text-gray-500 hover:bg-gray-50'
              }`}
            >
              <t.icon className="w-3 h-3" />
              {t.label}
            </button>
          ))}
        </div>

        {/* Asset List */}
        {loading ? (
          <div className="text-center py-12 text-gray-400">加载中...</div>
        ) : assets.length === 0 ? (
          <div className="text-center py-12 text-gray-400">
            <Box className="w-12 h-12 mx-auto mb-3 text-gray-300" />
            尚无资产，创建您的第一个资产开始使用
          </div>
        ) : (
          <div className="space-y-2">
            {assets.map((asset) => {
              const typeInfo = ASSET_TYPES.find((t) => t.key === asset.asset_type) || ASSET_TYPES[0]
              const Icon = typeInfo.icon
              return (
                <div key={asset.id} className="card flex items-center justify-between group hover:border-primary-200 transition-colors">
                  <div className="flex items-center gap-3 min-w-0">
                    <div className={`w-10 h-10 rounded-lg flex items-center justify-center ${typeInfo.color}`}>
                      <Icon className="w-5 h-5" />
                    </div>
                    <div className="min-w-0">
                      <div className="text-sm font-medium text-gray-800">{asset.name}</div>
                      <div className="text-xs text-gray-400 truncate">
                        {typeInfo.label} · {asset.description || '无描述'}
                      </div>
                    </div>
                  </div>
                  <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                    <button
                      onClick={() => handleDelete(asset.id)}
                      className="p-1.5 text-gray-300 hover:text-red-500 rounded-lg hover:bg-red-50 transition-colors"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                </div>
              )
            })}
          </div>
        )}
      </div>
    </div>
  )
}

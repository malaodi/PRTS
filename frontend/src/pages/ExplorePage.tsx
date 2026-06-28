import { useState, useEffect } from 'react'
import api from '@/api/client'
import { useSpaceStore } from '@/stores'
import { Compass, Search, Download, Box, Wrench, Bot, Plug, Layout, Star } from 'lucide-react'

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
  { key: 'all', label: '全部', icon: Star, color: 'text-gray-600 bg-gray-50' },
  { key: 'skill', label: '技能', icon: Box, color: 'text-blue-600 bg-blue-50' },
  { key: 'tool', label: '工具', icon: Wrench, color: 'text-green-600 bg-green-50' },
  { key: 'subagent', label: '伙伴', icon: Bot, color: 'text-purple-600 bg-purple-50' },
  { key: 'mcp', label: 'MCP', icon: Plug, color: 'text-orange-600 bg-orange-50' },
  { key: 'widget', label: '卡片', icon: Layout, color: 'text-pink-600 bg-pink-50' },
]

export default function ExplorePage() {
  const [assets, setAssets] = useState<Asset[]>([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [filter, setFilter] = useState('all')
  const [installing, setInstalling] = useState<string | null>(null)
  const currentSpace = useSpaceStore((s) => s.currentSpace)

  const fetchAssets = async () => {
    try {
      setLoading(true)
      const params = filter !== 'all' ? `?asset_type=${filter}` : ''
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

  const handleInstall = async (asset: Asset) => {
    try {
      setInstalling(asset.id)
      await api.post('/assets', {
        asset_type: asset.asset_type,
        name: asset.name,
        description: asset.description || '',
        config: asset.config,
      })
      setInstalling(null)
    } catch {
      setInstalling(null)
    }
  }

  const filtered = assets.filter((a) =>
    search ? a.name.toLowerCase().includes(search.toLowerCase()) ||
             (a.description || '').toLowerCase().includes(search.toLowerCase()) : true
  )

  return (
    <div className="flex-1 overflow-y-auto p-6">
      <div className="max-w-4xl mx-auto">
        <div className="mb-6">
          <h2 className="text-xl font-bold text-gray-900">
            <Compass className="w-5 h-5 inline mr-2" />
            探索市场
          </h2>
          <p className="text-sm text-gray-500 mt-1">浏览和安装社区发布的 Agent、技能、工具等资产</p>
        </div>

        {/* Search */}
        <div className="relative mb-4">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
          <input
            className="input-field pl-9"
            placeholder="搜索资产..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>

        {/* Filter Tabs */}
        <div className="flex gap-2 mb-6 overflow-x-auto">
          {ASSET_TYPES.map((t) => (
            <button
              key={t.key}
              onClick={() => setFilter(t.key)}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium whitespace-nowrap transition-colors ${
                filter === t.key ? t.color : 'text-gray-500 hover:bg-gray-50'
              }`}
            >
              <t.icon className="w-3.5 h-3.5" />
              {t.label}
            </button>
          ))}
        </div>

        {/* Asset Grid */}
        {loading ? (
          <div className="text-center py-12 text-gray-400">加载中...</div>
        ) : filtered.length === 0 ? (
          <div className="text-center py-16">
            <Compass className="w-12 h-12 mx-auto mb-3 text-gray-300" />
            <h3 className="text-sm font-medium text-gray-500">暂无资产</h3>
            <p className="text-xs text-gray-400 mt-1">
              {search ? '没有找到匹配的资产' : '当前空间还没有资产，去资产管理页创建或从 Hub 安装'}
            </p>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {filtered.map((asset) => {
              const typeInfo = ASSET_TYPES.find((t) => t.key === asset.asset_type) || ASSET_TYPES[0]
              const Icon = typeInfo.icon
              return (
                <div key={asset.id} className="card hover:border-primary-200 transition-colors">
                  <div className="flex items-start gap-3">
                    <div className={`w-10 h-10 rounded-lg flex items-center justify-center shrink-0 ${typeInfo.color}`}>
                      <Icon className="w-5 h-5" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-1">
                        <span className="text-sm font-medium text-gray-800">{asset.name}</span>
                        <span className={`text-[10px] px-1.5 py-0.5 rounded-full ${typeInfo.color}`}>
                          {typeInfo.label}
                        </span>
                      </div>
                      <p className="text-xs text-gray-500 line-clamp-2 mb-3">
                        {asset.description || '无描述'}
                      </p>
                      <div className="flex items-center justify-between">
                        <span className="text-[10px] text-gray-400">
                          {asset.created_at ? new Date(asset.created_at).toLocaleDateString('zh-CN') : ''}
                        </span>
                        <button
                          onClick={() => handleInstall(asset)}
                          disabled={installing === asset.id}
                          className="flex items-center gap-1 text-xs text-primary-600 hover:text-primary-700 font-medium disabled:opacity-50"
                        >
                          <Download className="w-3.5 h-3.5" />
                          {installing === asset.id ? '安装中...' : '安装到空间'}
                        </button>
                      </div>
                    </div>
                  </div>
                </div>
              )
            })}
          </div>
        )}

        {/* Hub Info */}
        <div className="mt-8 p-4 bg-primary-50 rounded-xl">
          <div className="flex items-center gap-2 mb-2">
            <Compass className="w-4 h-4 text-primary-600" />
            <span className="text-sm font-medium text-primary-700">LangSmith Hub 集成</span>
          </div>
          <p className="text-xs text-primary-600/70">
            配置 LANGCHAIN_API_KEY 环境变量后可启用 LangSmith Hub 市场功能：
            hub.pull() 安装社区资产 · hub.push() 发布你的资产 · commit 历史版本管理
          </p>
        </div>
      </div>
    </div>
  )
}

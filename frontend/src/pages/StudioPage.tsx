import { useState, useEffect } from 'react'
import api from '@/api/client'
import { useSpaceStore } from '@/stores'
import { Folder, File, ChevronRight, ChevronDown, User, RefreshCw } from 'lucide-react'

interface FileEntry {
  name: string
  type: 'file' | 'directory'
  size: number | null
  modified: string
}

interface TeamMember {
  user_id: string
  display_name: string
  role: string
}

const ASSET_FOLDERS = ['skills', 'tools', 'subagents', 'mcp', 'widgets', 'pipelines', 'packs', 'shared', 'sessions']

const FOLDER_LABELS: Record<string, string> = {
  skills: '技能 Skills',
  tools: '工具 Tools',
  subagents: '伙伴 SubAgents',
  mcp: 'MCP',
  widgets: '卡片 Widgets',
  pipelines: '自动化 Pipelines',
  packs: '能力套件 Packs',
  shared: '共享文件',
  sessions: '会话记录',
}

export default function StudioPage() {
  const [entries, setEntries] = useState<FileEntry[]>([])
  const [currentPath, setCurrentPath] = useState('')
  const [pathStack, setPathStack] = useState<string[]>([])
  const [loading, setLoading] = useState(true)
  const [fileContent, setFileContent] = useState<string | null>(null)
  const [viewingFile, setViewingFile] = useState<string | null>(null)
  const [teamMode, setTeamMode] = useState(false)
  const [members, setMembers] = useState<TeamMember[]>([])
  const [selectedUser, setSelectedUser] = useState<string | null>(null)
  const currentSpace = useSpaceStore((s) => s.currentSpace)

  const fetchEntries = async (path: string = '', user?: string | null) => {
    try {
      setLoading(true)
      const params = new URLSearchParams()
      params.set('path', path)
      if (user) params.set('user', user)
      const res = await api.get(`/studio/browse?${params}`)
      if ('file' in res.data) {
        setFileContent(res.data.content)
        setViewingFile(res.data.file || res.data.path)
        setEntries([])
      } else {
        setEntries(res.data.entries || [])
        setFileContent(null)
        setViewingFile(null)
      }
    } catch {
      setEntries([])
    } finally {
      setLoading(false)
    }
  }

  const fetchTeamMembers = async () => {
    try {
      const res = await api.get('/studio/team')
      setMembers(res.data.members || [])
    } catch {
      setMembers([])
    }
  }

  useEffect(() => {
    if (teamMode) {
      fetchTeamMembers()
      if (selectedUser) {
        fetchEntries('', selectedUser)
        setCurrentPath('')
        setPathStack([])
      }
    } else {
      fetchEntries('')
      setCurrentPath('')
      setPathStack([])
    }
  }, [currentSpace, teamMode, selectedUser])

  const handleNavigate = (entry: FileEntry) => {
    if (entry.type === 'directory') {
      const newPath = currentPath ? `${currentPath}/${entry.name}` : entry.name
      setPathStack([...pathStack, entry.name])
      setCurrentPath(newPath)
      fetchEntries(newPath, selectedUser)
    } else {
      const filePath = currentPath ? `${currentPath}/${entry.name}` : entry.name
      const params = new URLSearchParams()
      params.set('path', filePath)
      if (selectedUser) params.set('user', selectedUser)
      api.get(`/studio/browse?${params}`).then((res) => {
        if ('file' in res.data) {
          setFileContent(res.data.content)
          setViewingFile(filePath)
        }
      }).catch(() => {})
    }
  }

  const handleGoBack = () => {
    if (pathStack.length === 0) return
    const newStack = [...pathStack]
    newStack.pop()
    const newPath = newStack.join('/')
    setPathStack(newStack)
    setCurrentPath(newPath)
    fetchEntries(newPath, selectedUser)
    setFileContent(null)
    setViewingFile(null)
  }

  const handleGoRoot = () => {
    setCurrentPath('')
    setPathStack([])
    fetchEntries('', selectedUser)
    setFileContent(null)
    setViewingFile(null)
  }

  const formatSize = (bytes: number | null) => {
    if (bytes === null) return ''
    if (bytes < 1024) return `${bytes} B`
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
  }

  return (
    <div className="flex flex-col h-full bg-white">
      {/* Header */}
      <div className="flex items-center gap-3 px-4 py-3 border-b border-gray-200 shrink-0">
        <Folder className="w-5 h-5 text-primary-600" />
        <h2 className="text-lg font-semibold text-gray-800">工作室</h2>

        <div className="flex-1" />

        {/* Breadcrumb */}
        <div className="flex items-center gap-1 text-sm text-gray-500">
          <button onClick={handleGoRoot} className="hover:text-primary-600">
            根目录
          </button>
          {pathStack.map((p, i) => (
            <span key={i} className="flex items-center gap-1">
              <ChevronRight className="w-3 h-3" />
              <span>{p}</span>
            </span>
          ))}
        </div>

        {/* Team mode toggle */}
        <button
          onClick={() => setTeamMode(!teamMode)}
          className={`px-3 py-1.5 rounded-lg text-sm flex items-center gap-1.5 transition-colors ${
            teamMode ? 'bg-primary-100 text-primary-700' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
          }`}
        >
          <User className="w-4 h-4" />
          {teamMode ? '团队模式' : '个人模式'}
        </button>

        <button
          onClick={() => fetchEntries(currentPath, selectedUser)}
          className="p-1.5 rounded-lg text-gray-400 hover:text-gray-600 hover:bg-gray-100"
          title="刷新"
        >
          <RefreshCw className="w-4 h-4" />
        </button>
      </div>

      {/* User selector for team mode */}
      {teamMode && (
        <div className="px-4 py-2 border-b border-gray-100 bg-gray-50 flex items-center gap-2">
          <span className="text-sm text-gray-500">团队成员:</span>
          <select
            value={selectedUser || ''}
            onChange={(e) => setSelectedUser(e.target.value || null)}
            className="text-sm border border-gray-200 rounded px-2 py-1 bg-white"
          >
            <option value="">选择成员</option>
            {members.map((m) => (
              <option key={m.user_id} value={m.user_id}>
                {m.display_name} ({m.role})
              </option>
            ))}
          </select>
        </div>
      )}

      {/* Content */}
      <div className="flex-1 overflow-auto flex">
        {/* Left: File tree */}
        <div className="w-80 border-r border-gray-100 overflow-y-auto p-2">
          {/* Back button */}
          {pathStack.length > 0 && (
            <button
              onClick={handleGoBack}
              className="w-full text-left px-3 py-2 rounded-lg text-sm text-gray-500 hover:bg-gray-100 flex items-center gap-2 mb-1"
            >
              <ChevronDown className="w-4 h-4 rotate-90" />
              返回上级
            </button>
          )}

          {/* Root level: show asset folders */}
          {currentPath === '' && (
            <div className="text-xs text-gray-400 px-3 py-1 mb-1">资产分类</div>
          )}
          {currentPath === '' && ASSET_FOLDERS.map((folder) => (
            <button
              key={folder}
              onClick={() => handleNavigate({ name: folder, type: 'directory', size: null, modified: '' })}
              className="w-full text-left px-3 py-1.5 rounded-lg text-sm hover:bg-primary-50 text-gray-700 flex items-center gap-2"
            >
              <Folder className="w-4 h-4 text-yellow-500 shrink-0" />
              <span>{FOLDER_LABELS[folder] || folder}</span>
            </button>
          ))}

          {loading && (
            <div className="flex items-center justify-center py-8">
              <div className="animate-spin h-5 w-5 border-2 border-primary-500 border-t-transparent rounded-full" />
            </div>
          )}

          {/* Directory entries */}
          {entries.map((entry) => (
            <button
              key={entry.name}
              onClick={() => handleNavigate(entry)}
              className={`w-full text-left px-3 py-1.5 rounded-lg text-sm hover:bg-gray-100 flex items-center gap-2 ${
                viewingFile === (currentPath ? `${currentPath}/${entry.name}` : entry.name)
                  ? 'bg-primary-50 text-primary-700'
                  : 'text-gray-700'
              }`}
            >
              {entry.type === 'directory' ? (
                <Folder className="w-4 h-4 text-yellow-500 shrink-0" />
              ) : (
                <File className="w-4 h-4 text-gray-400 shrink-0" />
              )}
              <span className="truncate">{entry.name}</span>
              {entry.type === 'file' && entry.size && (
                <span className="text-xs text-gray-400 ml-auto shrink-0">{formatSize(entry.size)}</span>
              )}
            </button>
          ))}

          {!loading && entries.length === 0 && currentPath !== '' && (
            <div className="text-sm text-gray-400 text-center py-8">空目录</div>
          )}
        </div>

        {/* Right: File preview */}
        <div className="flex-1 overflow-auto p-4">
          {fileContent ? (
            <div>
              <div className="text-sm text-gray-400 mb-2">{viewingFile}</div>
              <pre className="text-sm font-mono bg-gray-50 rounded-lg p-4 overflow-auto whitespace-pre-wrap max-h-full">
                {fileContent}
              </pre>
            </div>
          ) : (
            <div className="flex items-center justify-center h-full text-gray-400 text-sm">
              选择文件预览内容
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

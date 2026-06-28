import { useState, useEffect } from 'react'
import { useSpaceStore } from '@/stores'
import api from '@/api/client'
import { Plus, Trash2, Users, Settings, Crown } from 'lucide-react'

interface Space {
  id: string
  name: string
  type: string
  owner_id: string
  team_context: string | null
  member_count: number
}

interface Member {
  id: string
  user_id: string
  username: string
  email: string
  display_name: string | null
  role: string
  joined_at: string | null
}

export default function SpacesPage() {
  const { spaces, currentSpace, fetchSpaces, setCurrentSpace } = useSpaceStore()
  const [showCreate, setShowCreate] = useState(false)
  const [newSpaceName, setNewSpaceName] = useState('')
  const [selectedSpace, setSelectedSpace] = useState<Space | null>(null)
  const [members, setMembers] = useState<Member[]>([])
  const [inviteEmail, setInviteEmail] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    fetchSpaces()
  }, [fetchSpaces])

  const handleCreateSpace = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!newSpaceName.trim()) return
    setLoading(true)
    setError('')
    try {
      await api.post('/spaces', { name: newSpaceName.trim(), type: 'team' })
      setNewSpaceName('')
      setShowCreate(false)
      await fetchSpaces()
    } catch (err: any) {
      setError(err.response?.data?.detail || '创建失败')
    } finally {
      setLoading(false)
    }
  }

  const handleSelectSpace = async (space: Space) => {
    setSelectedSpace(space)
    setError('')
    try {
      const res = await api.get(`/spaces/${space.id}/members`)
      setMembers(res.data)
    } catch {
      setMembers([])
    }
  }

  const handleInviteMember = async () => {
    if (!inviteEmail.trim() || !selectedSpace) return
    setLoading(true)
    setError('')
    try {
      await api.post(`/spaces/${selectedSpace.id}/members/invite`, {
        email: inviteEmail.trim(),
        role: 'member',
      })
      setInviteEmail('')
      const res = await api.get(`/spaces/${selectedSpace.id}/members`)
      setMembers(res.data)
      await fetchSpaces()
    } catch (err: any) {
      setError(err.response?.data?.detail || '邀请失败')
    } finally {
      setLoading(false)
    }
  }

  const handleRemoveMember = async (memberId: string) => {
    if (!selectedSpace) return
    try {
      await api.delete(`/spaces/${selectedSpace.id}/members/${memberId}`)
      setMembers((prev) => prev.filter((m) => m.id !== memberId))
      await fetchSpaces()
    } catch (err: any) {
      setError(err.response?.data?.detail || '移除失败')
    }
  }

  const handleDeleteSpace = async (spaceId: string) => {
    if (!confirm('确定要删除此空间吗？此操作不可撤销。')) return
    try {
      await api.delete(`/spaces/${spaceId}`)
      if (selectedSpace?.id === spaceId) setSelectedSpace(null)
      await fetchSpaces()
    } catch (err: any) {
      setError(err.response?.data?.detail || '删除失败')
    }
  }

  const roleLabel = (role: string) => {
    switch (role) {
      case 'owner': return '所有者'
      case 'admin': return '管理员'
      case 'member': return '成员'
      case 'viewer': return '访客'
      default: return role
    }
  }

  const roleColor = (role: string) => {
    switch (role) {
      case 'owner': return 'bg-amber-100 text-amber-700'
      case 'admin': return 'bg-blue-100 text-blue-700'
      case 'member': return 'bg-green-100 text-green-700'
      case 'viewer': return 'bg-gray-100 text-gray-600'
      default: return 'bg-gray-100'
    }
  }

  return (
    <div className="flex-1 flex overflow-hidden">
      {/* Space List */}
      <div className="w-80 bg-white border-r border-gray-200 flex flex-col">
        <div className="p-4 border-b border-gray-100 flex items-center justify-between">
          <h2 className="text-sm font-semibold text-gray-900">空间</h2>
          <button
            onClick={() => setShowCreate(!showCreate)}
            className="btn-primary text-xs py-1.5 px-3"
          >
            <Plus className="w-3 h-3 inline mr-1" />
            创建
          </button>
        </div>

        {showCreate && (
          <form onSubmit={handleCreateSpace} className="p-3 border-b border-gray-100">
            {error && <p className="text-xs text-red-600 mb-2">{error}</p>}
            <input
              type="text"
              className="input-field text-sm mb-2"
              placeholder="团队空间名称"
              value={newSpaceName}
              onChange={(e) => setNewSpaceName(e.target.value)}
              required
            />
            <div className="flex gap-2">
              <button type="submit" className="btn-primary text-xs flex-1" disabled={loading}>
                {loading ? '创建中...' : '创建团队'}
              </button>
              <button
                type="button"
                onClick={() => setShowCreate(false)}
                className="btn-secondary text-xs flex-1"
              >
                取消
              </button>
            </div>
          </form>
        )}

        <div className="flex-1 overflow-y-auto">
          {spaces.map((space) => (
            <div
              key={space.id}
              onClick={() => handleSelectSpace(space)}
              className={`px-4 py-3 cursor-pointer hover:bg-gray-50 border-b border-gray-50 transition-colors ${
                selectedSpace?.id === space.id ? 'bg-primary-50 border-l-2 border-l-primary-500' : ''
              }`}
            >
              <div className="flex items-center justify-between">
                <div className="min-w-0">
                  <div className="text-sm font-medium text-gray-800 truncate">
                    {space.name}
                  </div>
                  <div className="text-xs text-gray-400 mt-0.5">
                    {space.type === 'personal' ? '个人空间' : `${space.member_count} 名成员`}
                  </div>
                </div>
                {space.type === 'team' && (
                  <button
                    onClick={(e) => {
                      e.stopPropagation()
                      handleDeleteSpace(space.id)
                    }}
                    className="text-gray-300 hover:text-red-500 transition-colors"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Space Detail */}
      <div className="flex-1 overflow-y-auto p-6">
        {selectedSpace ? (
          <div className="max-w-2xl">
            <div className="mb-6">
              <h3 className="text-xl font-bold text-gray-900">{selectedSpace.name}</h3>
              <p className="text-sm text-gray-500 mt-1">
                {selectedSpace.type === 'personal' ? '个人空间' : `团队空间 · ${selectedSpace.member_count} 名成员`}
              </p>
              {selectedSpace.team_context && (
                <div className="mt-3 p-3 bg-gray-50 rounded-lg text-sm text-gray-600">
                  {selectedSpace.team_context}
                </div>
              )}
            </div>

            {/* Members */}
            {selectedSpace.type === 'team' && (
              <>
                <div className="flex items-center justify-between mb-4">
                  <h4 className="text-sm font-semibold text-gray-900">
                    <Users className="w-4 h-4 inline mr-1" />
                    成员 ({members.length})
                  </h4>
                </div>

                {/* Invite */}
                <div className="flex gap-2 mb-4">
                  <input
                    type="email"
                    className="input-field text-sm flex-1"
                    placeholder="输入邮箱邀请成员..."
                    value={inviteEmail}
                    onChange={(e) => setInviteEmail(e.target.value)}
                    onKeyDown={(e) => e.key === 'Enter' && handleInviteMember()}
                  />
                  <button
                    onClick={handleInviteMember}
                    disabled={loading || !inviteEmail.trim()}
                    className="btn-primary text-sm"
                  >
                    {loading ? '邀请中...' : '邀请'}
                  </button>
                </div>
                {error && <p className="text-sm text-red-600 mb-3">{error}</p>}

                {/* Member List */}
                <div className="space-y-2">
                  {members.map((member) => (
                    <div
                      key={member.id}
                      className="flex items-center justify-between p-3 bg-white border border-gray-100 rounded-lg"
                    >
                      <div className="flex items-center gap-3 min-w-0">
                        <div className="w-8 h-8 bg-gray-200 rounded-full flex items-center justify-center text-sm font-medium text-gray-600 shrink-0">
                          {(member.display_name || member.username)[0].toUpperCase()}
                        </div>
                        <div className="min-w-0">
                          <div className="text-sm font-medium text-gray-800 truncate">
                            {member.display_name || member.username}
                          </div>
                          <div className="text-xs text-gray-400 truncate">{member.email}</div>
                        </div>
                      </div>
                      <div className="flex items-center gap-2">
                        <span className={`text-xs px-2 py-1 rounded-full ${roleColor(member.role)}`}>
                          {member.role === 'owner' && <Crown className="w-3 h-3 inline mr-0.5" />}
                          {roleLabel(member.role)}
                        </span>
                        {member.role !== 'owner' && (
                          <button
                            onClick={() => handleRemoveMember(member.id)}
                            className="text-gray-300 hover:text-red-500 transition-colors"
                          >
                            <Trash2 className="w-3 h-3" />
                          </button>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </>
            )}
          </div>
        ) : (
          <div className="flex items-center justify-center h-full text-gray-400 text-sm">
            选择一个空间查看详情
          </div>
        )}
      </div>
    </div>
  )
}

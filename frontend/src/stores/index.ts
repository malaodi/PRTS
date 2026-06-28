import { create } from 'zustand'
import api from '@/api/client'

interface User {
  id: string
  email: string
  username: string
  display_name: string | null
  is_active: boolean
}

interface Space {
  id: string
  name: string
  type: string
  owner_id: string
  team_context: string | null
  member_count: number
}

interface AuthState {
  token: string | null
  user: User | null
  isAuthenticated: boolean
  login: (username: string, password: string) => Promise<void>
  register: (email: string, username: string, password: string) => Promise<void>
  logout: () => void
  fetchMe: () => Promise<void>
}

export const useAuthStore = create<AuthState>((set) => ({
  token: localStorage.getItem('access_token'),
  user: null,
  isAuthenticated: !!localStorage.getItem('access_token'),

  login: async (username: string, password: string) => {
    const res = await api.post('/auth/login', { username, password })
    localStorage.setItem('access_token', res.data.access_token)
    set({ token: res.data.access_token, isAuthenticated: true })
    await useAuthStore.getState().fetchMe()
  },

  register: async (email: string, username: string, password: string) => {
    const res = await api.post('/auth/register', { email, username, password })
    localStorage.setItem('access_token', res.data.access_token)
    set({ token: res.data.access_token, isAuthenticated: true })
    await useAuthStore.getState().fetchMe()
  },

  logout: () => {
    localStorage.removeItem('access_token')
    localStorage.removeItem('current_space_id')
    set({ token: null, user: null, isAuthenticated: false })
  },

  fetchMe: async () => {
    try {
      const res = await api.get('/auth/me')
      set({ user: res.data, isAuthenticated: true })
    } catch {
      localStorage.removeItem('access_token')
      set({ token: null, user: null, isAuthenticated: false })
    }
  },
}))

interface SpaceState {
  spaces: Space[]
  currentSpaceId: string | null
  currentSpace: Space | null
  fetchSpaces: () => Promise<void>
  setCurrentSpace: (spaceId: string) => void
}

export const useSpaceStore = create<SpaceState>((set, get) => ({
  spaces: [],
  currentSpaceId: localStorage.getItem('current_space_id'),
  currentSpace: null,

  fetchSpaces: async () => {
    try {
      const res = await api.get('/spaces')
      const spaces = res.data
      set({ spaces })
      const currentId = get().currentSpaceId
      if (currentId) {
        const space = spaces.find((s: Space) => s.id === currentId)
        if (space) set({ currentSpace: space })
      } else if (spaces.length > 0) {
        set({
          currentSpaceId: spaces[0].id,
          currentSpace: spaces[0],
        })
        localStorage.setItem('current_space_id', spaces[0].id)
      }
    } catch {
      // spaces will be empty
    }
  },

  setCurrentSpace: (spaceId: string) => {
    localStorage.setItem('current_space_id', spaceId)
    const space = get().spaces.find((s) => s.id === spaceId) || null
    set({ currentSpaceId: spaceId, currentSpace: space })
  },
}))

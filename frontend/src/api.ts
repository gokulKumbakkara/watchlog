import type { Series, TVMazeResult, SeasonCheckResult, User } from './types'
import { getToken, clearAuth } from './auth'

const BASE = '/api/v1'

async function apiFetch(url: string, options: RequestInit = {}): Promise<Response> {
  const token = getToken()
  const headers: Record<string, string> = {
    ...(options.headers as Record<string, string>),
  }
  if (token) headers['Authorization'] = `Bearer ${token}`
  if (options.body && typeof options.body === 'string') {
    headers['Content-Type'] = 'application/json'
  }

  const res = await fetch(url, { ...options, headers })

  if (res.status === 401) {
    clearAuth()
    window.location.reload()
  }

  return res
}

export const api = {
  auth: {
    register: async (username: string, email: string, password: string) => {
      const res = await fetch(`${BASE}/auth/register`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, email, password }),
      })
      if (!res.ok) {
        const err = await res.json().catch(() => ({}))
        throw new Error(err.detail || 'Registration failed')
      }
      return res.json() as Promise<{ access_token: string; user: User }>
    },

    login: async (email: string, password: string) => {
      const res = await fetch(`${BASE}/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password }),
      })
      if (!res.ok) {
        const err = await res.json().catch(() => ({}))
        throw new Error(err.detail || 'Login failed')
      }
      return res.json() as Promise<{ access_token: string; user: User }>
    },
  },

  series: {
    list: async (status?: string): Promise<Series[]> => {
      const url = status ? `${BASE}/series?status=${encodeURIComponent(status)}` : `${BASE}/series`
      const res = await apiFetch(url)
      if (!res.ok) throw new Error('Failed to fetch series')
      return res.json()
    },

    get: async (id: number): Promise<Series> => {
      const res = await apiFetch(`${BASE}/series/${id}`)
      if (!res.ok) throw new Error('Series not found')
      return res.json()
    },

    add: async (tvmaze_id: number): Promise<Series> => {
      const res = await apiFetch(`${BASE}/series`, {
        method: 'POST',
        body: JSON.stringify({ tvmaze_id }),
      })
      if (res.status === 409) throw new Error('already_exists')
      if (!res.ok) throw new Error('Failed to add series')
      return res.json()
    },

    update: async (id: number, data: Partial<Series>): Promise<Series> => {
      const res = await apiFetch(`${BASE}/series/${id}`, {
        method: 'PUT',
        body: JSON.stringify(data),
      })
      if (!res.ok) throw new Error('Failed to update series')
      return res.json()
    },

    remove: async (id: number): Promise<void> => {
      const res = await apiFetch(`${BASE}/series/${id}`, { method: 'DELETE' })
      if (!res.ok) throw new Error('Failed to delete series')
    },

    search: async (q: string): Promise<TVMazeResult[]> => {
      const res = await apiFetch(`${BASE}/series/search?q=${encodeURIComponent(q)}`)
      if (!res.ok) throw new Error('Search failed')
      return res.json()
    },

    checkSeasons: async (): Promise<SeasonCheckResult> => {
      const res = await apiFetch(`${BASE}/series/check-seasons`, { method: 'POST' })
      if (!res.ok) throw new Error('Season check failed')
      return res.json()
    },
  },
}

export function makeSessionId(): string {
  const stored = localStorage.getItem('wl_session')
  if (stored) return stored
  const id = 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, c => {
    const r = (Math.random() * 16) | 0
    return (c === 'x' ? r : (r & 0x3) | 0x8).toString(16)
  })
  localStorage.setItem('wl_session', id)
  return id
}

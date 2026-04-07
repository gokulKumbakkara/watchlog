import { useState, useRef, useEffect, useCallback } from 'react'
import { api } from '../api'
import type { TVMazeResult } from '../types'
import styles from './SearchBar.module.css'

interface Props {
  onAdded: () => void
  onToast: (msg: string, type?: 'success' | 'error') => void
}

export function SearchBar({ onAdded, onToast }: Props) {
  const [query, setQuery] = useState('')
  const [results, setResults] = useState<TVMazeResult[]>([])
  const [open, setOpen] = useState(false)
  const [loading, setLoading] = useState(false)
  const [adding, setAdding] = useState<number | null>(null)
  const timerRef = useRef<ReturnType<typeof setTimeout>>()
  const containerRef = useRef<HTMLDivElement>(null)

  const search = useCallback(async (q: string) => {
    if (!q.trim()) { setResults([]); setOpen(false); return }
    setLoading(true)
    try {
      const data = await api.series.search(q)
      setResults(data)
      setOpen(true)
    } catch {
      setResults([])
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    clearTimeout(timerRef.current)
    timerRef.current = setTimeout(() => search(query), 400)
    return () => clearTimeout(timerRef.current)
  }, [query, search])

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false)
      }
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  const handleAdd = async (r: TVMazeResult) => {
    setAdding(r.tvmaze_id)
    setOpen(false)
    setQuery('')
    try {
      await api.series.add(r.tvmaze_id)
      onAdded()
      onToast(`Added "${r.name}"`, 'success')
    } catch (e: unknown) {
      if (e instanceof Error && e.message === 'already_exists') {
        onToast(`"${r.name}" is already in your watchlist`)
      } else {
        onToast('Failed to add series', 'error')
      }
    } finally {
      setAdding(null)
    }
  }

  return (
    <div className={styles.wrap} ref={containerRef}>
      <div className={styles.inputWrap}>
        <svg className={styles.icon} viewBox="0 0 20 20" fill="none">
          <circle cx="9" cy="9" r="6" stroke="currentColor" strokeWidth="1.5" />
          <path d="M15 15l-3-3" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
        </svg>
        <input
          className={styles.input}
          value={query}
          onChange={e => setQuery(e.target.value)}
          placeholder="Search TVMaze to add a show…"
          onFocus={() => results.length > 0 && setOpen(true)}
        />
        {loading && <div className={styles.loader} />}
      </div>

      {open && results.length > 0 && (
        <div className={styles.dropdown}>
          {results.map(r => (
            <button
              key={r.tvmaze_id}
              className={styles.result}
              onClick={() => handleAdd(r)}
              disabled={adding === r.tvmaze_id}
            >
              <div className={styles.thumb}>
                {r.poster_url ? (
                  <img src={r.poster_url} alt={r.name} />
                ) : (
                  <span>{r.name.slice(0, 2).toUpperCase()}</span>
                )}
              </div>
              <div className={styles.resultInfo}>
                <strong>{r.name}</strong>
                <span>
                  {[r.network, r.genre?.split(',')[0]].filter(Boolean).join(' · ')}
                </span>
                {r.status && <span className={styles.status}>{r.status}</span>}
              </div>
              <span className={styles.add}>
                {adding === r.tvmaze_id ? '…' : '+'}
              </span>
            </button>
          ))}
        </div>
      )}
    </div>
  )
}

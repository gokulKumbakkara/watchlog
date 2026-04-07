import { useState, useEffect, useCallback } from 'react'
import type { Series, User } from './types'
import { api } from './api'
import { getToken, getStoredUser, clearAuth } from './auth'
import { SeriesGrid } from './components/SeriesGrid'
import { SearchBar } from './components/SearchBar'
import { EditModal } from './components/EditModal'
import { Chat } from './components/Chat'
import { AuthPage } from './pages/AuthPage'
import styles from './App.module.css'

interface Toast { id: number; msg: string; type?: 'success' | 'error' }

export default function App() {
  const [user, setUser] = useState<User | null>(() => getStoredUser())
  const [series, setSeries] = useState<Series[]>([])
  const [loading, setLoading] = useState(true)
  const [selected, setSelected] = useState<Series | null>(null)
  const [toasts, setToasts] = useState<Toast[]>([])
  const [checking, setChecking] = useState(false)

  const loadSeries = useCallback(async () => {
    try {
      const data = await api.series.list()
      setSeries(data)
    } catch {
      showToast('Failed to load watchlist', 'error')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    if (user && getToken()) {
      loadSeries()
    } else {
      setLoading(false)
    }
  }, [user, loadSeries])

  const showToast = (msg: string, type?: 'success' | 'error') => {
    const id = Date.now()
    setToasts(t => [...t, { id, msg, type }])
    setTimeout(() => setToasts(t => t.filter(x => x.id !== id)), 3500)
  }

  const handleLogin = (loggedInUser: User) => {
    setUser(loggedInUser)
    setLoading(true)
  }

  const handleLogout = () => {
    clearAuth()
    setUser(null)
    setSeries([])
    setLoading(false)
  }

  const handleCheckSeasons = async () => {
    setChecking(true)
    try {
      const res = await api.series.checkSeasons()
      await loadSeries()
      if (res.shows_with_new.length > 0) {
        showToast(`New seasons: ${res.shows_with_new.join(', ')}`, 'success')
      } else if (res.shows_with_upcoming?.length > 0) {
        showToast(`Upcoming: ${res.shows_with_upcoming.join(' · ')}`, 'success')
      } else {
        showToast(`Checked ${res.checked} shows — nothing new`)
      }
    } catch {
      showToast('Season check failed', 'error')
    } finally {
      setChecking(false)
    }
  }

  // Not logged in — show auth page
  if (!user || !getToken()) {
    return <AuthPage onLogin={handleLogin} />
  }

  const newSeasonCount = series.filter(s => s.has_new_season).length

  return (
    <div className={styles.app}>
      {/* Header */}
      <header className={styles.header}>
        <div className={styles.logo}>
          <span className={styles.logoMark}>✦</span>
          <span className={styles.logoText}>WatchLog</span>
        </div>
        <div className={styles.headerRight}>
          {newSeasonCount > 0 && (
            <span className={styles.newBadge}>{newSeasonCount} new season{newSeasonCount > 1 ? 's' : ''}</span>
          )}
          <span className={styles.headerCount}>{series.length} shows</span>
          <span className={styles.userChip}>{user.username}</span>
          <button className={`btn btn-ghost ${styles.logoutBtn}`} onClick={handleLogout}>
            Sign out
          </button>
        </div>
      </header>

      {/* Main layout */}
      <div className={styles.layout}>
        {/* Left: Watchlist */}
        <div className={styles.left}>
          <div className={styles.toolbar}>
            <SearchBar onAdded={loadSeries} onToast={showToast} />
            <button
              className={`btn btn-ghost ${styles.checkBtn}`}
              onClick={handleCheckSeasons}
              disabled={checking}
              title="Check all shows for new seasons and upcoming episodes"
            >
              {checking ? (
                <span className={styles.btnSpinner} />
              ) : (
                <svg viewBox="0 0 20 20" fill="none" width="14" height="14">
                  <path d="M4 4v5h5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
                  <path d="M19.5 10a9.5 9.5 0 11-2.5-6.5L19.5 6" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
                </svg>
              )}
              {checking ? 'Checking…' : 'Check'}
            </button>
          </div>

          <SeriesGrid
            series={series}
            loading={loading}
            onSelect={s => setSelected(s)}
          />
        </div>

        {/* Divider */}
        <div className={styles.divider} />

        {/* Right: Chat */}
        <div className={styles.right}>
          <div className={styles.panelHeader}>
            <span className={styles.panelTitle}>AI Agent</span>
            <span className={styles.panelHint}>Powered by Llama 3.3</span>
          </div>
          <Chat />
        </div>
      </div>

      {/* Edit Modal */}
      {selected && (
        <EditModal
          series={selected}
          onClose={() => setSelected(null)}
          onSaved={loadSeries}
          onToast={showToast}
        />
      )}

      {/* Toasts */}
      <div className="toast-container">
        {toasts.map(t => (
          <div key={t.id} className={`toast${t.type ? ` ${t.type}` : ''}`}>
            {t.msg}
          </div>
        ))}
      </div>
    </div>
  )
}

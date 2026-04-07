import { useState } from 'react'
import type { User } from '../types'
import { api } from '../api'
import { setAuth } from '../auth'
import styles from './AuthPage.module.css'

interface Props {
  onLogin: (user: User) => void
}

type Tab = 'login' | 'register'

export function AuthPage({ onLogin }: Props) {
  const [tab, setTab] = useState<Tab>('login')
  const [username, setUsername] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const reset = () => { setError(''); setUsername(''); setEmail(''); setPassword('') }
  const switchTab = (t: Tab) => { setTab(t); reset() }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      const res = tab === 'login'
        ? await api.auth.login(email, password)
        : await api.auth.register(username, email, password)
      setAuth(res.access_token, res.user)
      onLogin(res.user)
    } catch (err: any) {
      setError(err.message || 'Something went wrong')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className={styles.page}>
      <div className={styles.card}>
        {/* Logo */}
        <div className={styles.logo}>
          <span className={styles.logoMark}>✦</span>
          <span className={styles.logoText}>WatchLog</span>
        </div>
        <p className={styles.tagline}>Your personal TV tracker</p>

        {/* Tabs */}
        <div className={styles.tabs}>
          <button
            className={`${styles.tab} ${tab === 'login' ? styles.tabActive : ''}`}
            onClick={() => switchTab('login')}
          >Sign In</button>
          <button
            className={`${styles.tab} ${tab === 'register' ? styles.tabActive : ''}`}
            onClick={() => switchTab('register')}
          >Create Account</button>
        </div>

        {/* Form */}
        <form className={styles.form} onSubmit={handleSubmit}>
          {tab === 'register' && (
            <div className={styles.field}>
              <label>Username</label>
              <input
                type="text"
                placeholder="yourname"
                value={username}
                onChange={e => setUsername(e.target.value)}
                required
                autoFocus
              />
            </div>
          )}

          <div className={styles.field}>
            <label>Email</label>
            <input
              type="email"
              placeholder="you@example.com"
              value={email}
              onChange={e => setEmail(e.target.value)}
              required
              autoFocus={tab === 'login'}
            />
          </div>

          <div className={styles.field}>
            <label>Password</label>
            <input
              type="password"
              placeholder={tab === 'register' ? 'At least 6 characters' : '••••••••'}
              value={password}
              onChange={e => setPassword(e.target.value)}
              required
            />
          </div>

          {error && <p className={styles.error}>{error}</p>}

          <button
            type="submit"
            className={`btn btn-primary ${styles.submit}`}
            disabled={loading}
          >
            {loading
              ? (tab === 'login' ? 'Signing in…' : 'Creating account…')
              : (tab === 'login' ? 'Sign In' : 'Create Account')
            }
          </button>
        </form>

        <p className={styles.switch}>
          {tab === 'login' ? "Don't have an account? " : 'Already have an account? '}
          <button className={styles.switchBtn} onClick={() => switchTab(tab === 'login' ? 'register' : 'login')}>
            {tab === 'login' ? 'Create one' : 'Sign in'}
          </button>
        </p>
      </div>
    </div>
  )
}

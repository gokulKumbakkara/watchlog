import { useState } from 'react'
import type { Series, SeriesStatus, NoteEntry } from '../types'
import { api } from '../api'
import styles from './EditModal.module.css'

type Tab = 'progress' | 'notes'

const STATUSES: SeriesStatus[] = [
  'Watching', 'Completed', 'On Hold', 'Dropped', 'Plan to Watch', 'Waiting for Next Season',
]

function parseNotes(raw: string | null): NoteEntry[] {
  if (!raw) return []
  try {
    const parsed = JSON.parse(raw)
    if (Array.isArray(parsed)) return parsed
    return [{ season: 0, episode: 0, content: raw }]
  } catch {
    return raw.trim() ? [{ season: 0, episode: 0, content: raw }] : []
  }
}

function serializeNotes(entries: NoteEntry[]): string | null {
  const clean = entries.filter(e => e.content.trim())
  return clean.length > 0 ? JSON.stringify(clean) : null
}

interface Props {
  series: Series
  onClose: () => void
  onSaved: () => void
  onToast: (msg: string, type?: 'success' | 'error') => void
}

export function EditModal({ series, onClose, onSaved, onToast }: Props) {
  const [tab, setTab] = useState<Tab>('progress')
  const [status, setStatus] = useState<SeriesStatus>(series.status as SeriesStatus)
  const [season, setSeason] = useState(series.current_season)
  const [episode, setEpisode] = useState(series.current_episode)
  const [notes, setNotes] = useState<NoteEntry[]>(() => parseNotes(series.notes))
  const [saving, setSaving] = useState(false)
  const [deleting, setDeleting] = useState(false)
  const [addingEpFor, setAddingEpFor] = useState<number | null>(null)
  const [newEpNum, setNewEpNum] = useState('')

  const progress = series.total_episodes > 0
    ? Math.round((episode / series.total_episodes) * 100)
    : null

  const noteCount = notes.filter(n => n.content.trim()).length

  // ── Note helpers ─────────────────────────────────────────────────────────
  const getNote = (s: number, e: number) =>
    notes.find(n => n.season === s && n.episode === e)?.content ?? ''

  const setNote = (s: number, e: number, content: string) => {
    setNotes(prev => {
      const idx = prev.findIndex(n => n.season === s && n.episode === e)
      if (idx >= 0) {
        const updated = [...prev]
        updated[idx] = { ...updated[idx], content }
        return updated
      }
      return [...prev, { season: s, episode: e, content }]
    })
  }

  const removeNote = (s: number, e: number) =>
    setNotes(prev => prev.filter(n => !(n.season === s && n.episode === e)))

  const getEpisodeNotes = (s: number) =>
    notes.filter(n => n.season === s && n.episode > 0).sort((a, b) => a.episode - b.episode)

  const handleAddEpisodeNote = (s: number) => {
    const ep = parseInt(newEpNum)
    if (!ep || ep < 1) return
    setNotes(prev =>
      prev.find(n => n.season === s && n.episode === ep)
        ? prev
        : [...prev, { season: s, episode: ep, content: '' }]
    )
    setAddingEpFor(null)
    setNewEpNum('')
  }

  // ── Actions ───────────────────────────────────────────────────────────────
  const handleSave = async () => {
    setSaving(true)
    try {
      await api.series.update(series.id, {
        status,
        current_season: season,
        current_episode: episode,
        notes: serializeNotes(notes),
      })
      onSaved()
      onToast('Saved', 'success')
      onClose()
    } catch {
      onToast('Save failed', 'error')
    } finally {
      setSaving(false)
    }
  }

  const handleJustWatched = async () => {
    const newEp = episode + 1
    setEpisode(newEp)
    try {
      await api.series.update(series.id, {
        current_season: season,
        current_episode: newEp,
        last_watched: new Date().toISOString(),
      })
      onSaved()
      onToast('Progress updated', 'success')
    } catch {
      onToast('Update failed', 'error')
    }
  }

  const handleDelete = async () => {
    if (!confirm(`Remove "${series.name}" from your watchlist?`)) return
    setDeleting(true)
    try {
      await api.series.remove(series.id)
      onSaved()
      onToast(`Removed "${series.name}"`)
      onClose()
    } catch {
      onToast('Delete failed', 'error')
    } finally {
      setDeleting(false)
    }
  }

  const seasons = Array.from({ length: series.total_seasons }, (_, i) => i + 1)

  return (
    <div className={styles.overlay} onClick={e => e.target === e.currentTarget && onClose()}>
      <div className={styles.modal}>

        {/* Header */}
        <div className={styles.header}>
          {series.poster_url && (
            <img className={styles.poster} src={series.poster_url} alt={series.name} />
          )}
          <div className={styles.headerInfo}>
            <h2 className={styles.title}>{series.name}</h2>
            <p className={styles.meta}>
              {[series.network, series.genre?.split(',')[0]].filter(Boolean).join(' · ')}
            </p>
            {series.next_ep_airdate && (
              <p className={styles.nextEp}>
                Next: S{String(series.next_ep_season).padStart(2, '0')}E{String(series.next_ep_number).padStart(2, '0')} · {series.next_ep_airdate}
              </p>
            )}
            <p className={styles.totals}>
              {series.total_seasons} seasons · {series.total_episodes} episodes
              {progress !== null && ` · ${progress}% watched`}
            </p>
          </div>
          <button className={styles.close} onClick={onClose}>✕</button>
        </div>

        {/* Tabs */}
        <div className={styles.tabs}>
          <button
            className={`${styles.tab} ${tab === 'progress' ? styles.tabActive : ''}`}
            onClick={() => setTab('progress')}
          >
            Progress
          </button>
          <button
            className={`${styles.tab} ${tab === 'notes' ? styles.tabActive : ''}`}
            onClick={() => setTab('notes')}
          >
            Notes
            {noteCount > 0 && <span className={styles.noteBadge}>{noteCount}</span>}
          </button>
        </div>

        {/* ── Progress tab ─────────────────────────────────────────────────── */}
        {tab === 'progress' && (
          <div className={styles.body}>
            <div className={styles.field}>
              <label>Status</label>
              <select value={status} onChange={e => setStatus(e.target.value as SeriesStatus)}>
                {STATUSES.map(s => <option key={s} value={s}>{s}</option>)}
              </select>
            </div>

            <div className={styles.row}>
              <div className={styles.field}>
                <label>Season</label>
                <input
                  type="number" min={1} value={season}
                  onChange={e => setSeason(Number(e.target.value))}
                />
              </div>
              <div className={styles.field}>
                <label>Episode</label>
                <input
                  type="number" min={0} value={episode}
                  onChange={e => setEpisode(Number(e.target.value))}
                />
              </div>
            </div>

            <button className={`btn btn-ghost ${styles.justWatched}`} onClick={handleJustWatched}>
              ▶ Just Watched — advance episode
            </button>
          </div>
        )}

        {/* ── Notes tab ────────────────────────────────────────────────────── */}
        {tab === 'notes' && (
          <div className={styles.notesPanel}>

            {/* General */}
            <div className={styles.notesSection}>
              <div className={styles.notesSectionHeader}>
                <span className={styles.notesSectionTitle}>General</span>
                <span className={styles.notesSectionHint}>Characters, storylines, overall thoughts</span>
              </div>
              <textarea
                className={styles.noteTextarea}
                rows={3}
                value={getNote(0, 0)}
                onChange={e => setNote(0, 0, e.target.value)}
                placeholder="Add general notes about this show…"
              />
            </div>

            {/* Per-season sections */}
            {seasons.map(s => (
              <div key={s} className={styles.notesSection}>
                <div className={styles.notesSectionHeader}>
                  <span className={styles.notesSectionTitle}>Season {s}</span>
                  {s === series.current_season && (
                    <span className={styles.currentBadge}>watching</span>
                  )}
                </div>

                <textarea
                  className={styles.noteTextarea}
                  rows={2}
                  value={getNote(s, 0)}
                  onChange={e => setNote(s, 0, e.target.value)}
                  placeholder={`Season ${s} recap, key events…`}
                />

                {/* Episode-level notes */}
                {getEpisodeNotes(s).map(entry => (
                  <div key={entry.episode} className={styles.episodeNote}>
                    <span className={styles.epLabel}>E{entry.episode}</span>
                    <textarea
                      className={styles.noteTextarea}
                      rows={2}
                      value={entry.content}
                      onChange={e => setNote(s, entry.episode, e.target.value)}
                      placeholder={`S${s}E${entry.episode} notes…`}
                    />
                    <button
                      className={styles.removeEpNote}
                      onClick={() => removeNote(s, entry.episode)}
                      title="Remove"
                    >×</button>
                  </div>
                ))}

                {/* Add episode note row */}
                {addingEpFor === s ? (
                  <div className={styles.addEpRow}>
                    <span className={styles.epLabel}>E</span>
                    <input
                      className={styles.epNumInput}
                      type="number" min={1}
                      placeholder="ep #"
                      value={newEpNum}
                      onChange={e => setNewEpNum(e.target.value)}
                      onKeyDown={e => e.key === 'Enter' && handleAddEpisodeNote(s)}
                      autoFocus
                    />
                    <button
                      className="btn btn-primary"
                      style={{ padding: '4px 10px', fontSize: '12px' }}
                      onClick={() => handleAddEpisodeNote(s)}
                    >Add</button>
                    <button
                      className="btn btn-ghost"
                      style={{ padding: '4px 10px', fontSize: '12px' }}
                      onClick={() => { setAddingEpFor(null); setNewEpNum('') }}
                    >Cancel</button>
                  </div>
                ) : (
                  <button className={styles.addEpBtn} onClick={() => setAddingEpFor(s)}>
                    + Episode note
                  </button>
                )}
              </div>
            ))}

            {seasons.length === 0 && (
              <p className={styles.noSeasons}>Season data not available — add general notes above.</p>
            )}
          </div>
        )}

        {/* Footer */}
        <div className={styles.footer}>
          <button className="btn btn-danger" onClick={handleDelete} disabled={deleting}>
            {deleting ? 'Removing…' : 'Remove'}
          </button>
          <div className={styles.footerRight}>
            <button className="btn btn-ghost" onClick={onClose}>Cancel</button>
            <button className="btn btn-primary" onClick={handleSave} disabled={saving}>
              {saving ? 'Saving…' : 'Save'}
            </button>
          </div>
        </div>

      </div>
    </div>
  )
}

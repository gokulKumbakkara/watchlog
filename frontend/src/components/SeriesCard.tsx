import type { Series, SeriesStatus } from '../types'
import styles from './SeriesCard.module.css'

interface Props {
  series: Series
  onClick: () => void
}

const STATUS_CLASS: Record<SeriesStatus, string> = {
  'Watching':               'badge-watching',
  'Completed':              'badge-completed',
  'On Hold':                'badge-onhold',
  'Dropped':                'badge-dropped',
  'Plan to Watch':          'badge-plan',
  'Waiting for Next Season': 'badge-waiting',
}

export function SeriesCard({ series, onClick }: Props) {
  const progress =
    series.total_episodes > 0
      ? Math.round((series.current_episode / series.total_episodes) * 100)
      : 0

  const ep = `S${String(series.current_season).padStart(2, '0')}E${String(series.current_episode).padStart(2, '0')}`

  return (
    <div className={styles.card} onClick={onClick}>
      {/* Poster */}
      <div className={styles.poster}>
        {series.poster_url ? (
          <img src={series.poster_url} alt={series.name} loading="lazy" />
        ) : (
          <div className={styles.posterFallback}>
            <span>{series.name.slice(0, 2).toUpperCase()}</span>
          </div>
        )}
        {series.has_new_season && (
          <div className={styles.newBadge}>NEW</div>
        )}
        <div className={styles.overlay} />
      </div>

      {/* Info */}
      <div className={styles.info}>
        <p className={styles.name}>{series.name}</p>
        <div className={styles.meta}>
          <span className={`badge ${STATUS_CLASS[series.status]}`}>
            {series.status}
          </span>
          <span className={styles.ep}>{ep}</span>
        </div>
        {series.total_episodes > 0 && (
          <div className={styles.progressBar}>
            <div className={styles.progressFill} style={{ width: `${progress}%` }} />
          </div>
        )}
      </div>
    </div>
  )
}

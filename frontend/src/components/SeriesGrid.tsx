import type { Series } from '../types'
import { SeriesCard } from './SeriesCard'
import styles from './SeriesGrid.module.css'

interface Props {
  series: Series[]
  loading: boolean
  onSelect: (s: Series) => void
}

export function SeriesGrid({ series, loading, onSelect }: Props) {
  if (loading) {
    return (
      <div className={styles.empty}>
        <div className={styles.spinner} />
        <p>Loading watchlist…</p>
      </div>
    )
  }

  if (series.length === 0) {
    return (
      <div className={styles.empty}>
        <p className={styles.emptyIcon}>📺</p>
        <p className={styles.emptyTitle}>Your watchlist is empty</p>
        <p className={styles.emptyHint}>Search above to add your first show</p>
      </div>
    )
  }

  return (
    <div className={styles.grid}>
      {series.map(s => (
        <SeriesCard key={s.id} series={s} onClick={() => onSelect(s)} />
      ))}
    </div>
  )
}

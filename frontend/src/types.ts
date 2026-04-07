export interface Series {
  id: number
  tvmaze_id: number
  name: string
  poster_url: string | null
  network: string | null
  genre: string | null
  status: SeriesStatus
  current_season: number
  current_episode: number
  total_seasons: number
  total_episodes: number
  has_new_season: boolean
  notes: string | null
  last_watched: string | null
  last_season_check: string | null
  next_ep_season: number | null
  next_ep_number: number | null
  next_ep_airdate: string | null
  extension_source: string | null
  rag_indexed: boolean
  added_at: string
  updated_at: string | null
}

export type SeriesStatus =
  | 'Watching'
  | 'Completed'
  | 'On Hold'
  | 'Dropped'
  | 'Plan to Watch'
  | 'Waiting for Next Season'

export interface NoteEntry {
  season: number   // 0 = general show note
  episode: number  // 0 = season-level, >0 = specific episode
  content: string
}

export interface User {
  id: number
  username: string
  email: string
  is_active: boolean
  created_at: string
}

export interface TVMazeResult {
  tvmaze_id: number
  name: string
  poster_url: string | null
  network: string | null
  genre: string | null
  status: string | null
  summary: string | null
  score: number
}

export interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  toolCalls?: string[]
  streaming?: boolean
}

export interface SeasonCheckResult {
  checked: number
  updated: number
  shows_with_new: string[]
  shows_with_upcoming: string[]
}

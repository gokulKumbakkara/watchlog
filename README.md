# WatchLog

A full-stack personal TV series tracker with JWT-based multi-user auth, a LangChain ReAct AI agent, hybrid RAG search, and a dark React UI.

![Stack](https://img.shields.io/badge/FastAPI-0.111-009688?style=flat-square&logo=fastapi)
![Stack](https://img.shields.io/badge/React-18-61DAFB?style=flat-square&logo=react)
![Stack](https://img.shields.io/badge/LangChain-0.2-1C3C3C?style=flat-square)
![Stack](https://img.shields.io/badge/Groq-llama--3.3--70b-orange?style=flat-square)
![Stack](https://img.shields.io/badge/Docker-Compose-2496ED?style=flat-square&logo=docker)

---

## What We Built

| Layer | Tech |
|---|---|
| **Backend API** | FastAPI + SQLAlchemy async + PostgreSQL + Alembic |
| **Auth** | JWT (PyJWT) — register/login, per-user isolated data |
| **AI Agent** | LangChain ReAct + Groq llama-3.3-70b, SSE streaming |
| **RAG** | ChromaDB (vector) + BM25Okapi, merged via Reciprocal Rank Fusion |
| **Season monitoring** | APScheduler + TVMaze API + DuckDuckGo fallback |
| **Frontend** | React 18 + Vite + TypeScript + CSS Modules, dark theme |
| **Infra** | Docker multi-stage build (Node → Python → runtime) |
| **Code intelligence** | Repowise MCP — graph, git signals, dead code, wiki |

---

## Features

### Multi-User Auth
- JWT-based register / login — tokens valid for 7 days
- Every user's watchlist, notes, and chat history is fully isolated
- Sign out clears the session

### Watchlist Management
- Search TVMaze to add shows — poster, network, genre auto-populated
- Track progress by season + episode
- **Statuses:** Watching · Completed · On Hold · Dropped · Plan to Watch · Waiting for Next Season
- "Just Watched" button advances episode in one click
- Per-show progress bar and status badge

### AI Agent (Chat)
- Conversational interface powered by Groq llama-3.3-70b via LangChain ReAct
- Streams token-by-token via SSE — shows tool call pills while thinking
- Only the final answer is shown (reasoning chain is filtered out)
- Rate limit errors surface as "Limit reached" instead of raw API errors

**What you can ask:**

| Example | Tool |
|---|---|
| "Add Breaking Bad to my list" | `search_and_add` |
| "I just finished S03E05 of Succession" | `update_progress` |
| "Show me everything I'm watching" | `get_watchlist` |
| "Has The Boys gotten a new season?" | `check_season_update` |
| "Check all my shows for new seasons" | `check_all_seasons` |
| "What happened in the finale of Ozark S4?" | `search_series_knowledge` |
| "Recommend something dark" | `recommend` |
| "Mark Severance as completed" | `mark_status` |
| "Remove Euphoria from my list" | `remove_series` |
| "Add a note for The Boys: Homelander is the villain" | `manage_notes` |
| "What are my notes for The Boys?" | `manage_notes` |

### Structured Notes
- Per-show notes tab in the edit modal
- **General** section + per-season sections (auto-generated from total seasons)
- Episode-level notes within each season (add by episode number, delete with ×)
- Notes are included as high-priority context when the agent answers questions
- Notes badge on tab shows count of filled entries

### Season Monitoring
- **Check button** re-fetches TVMaze for all your shows
- Flags shows with new seasons (NEW badge on card)
- Also detects upcoming episodes within the next 7 days — shows "tomorrow", "in N days"
- APScheduler runs this automatically every 6 months in the background

### Hybrid RAG
When a show is added, all episode summaries are indexed into two stores:
1. **ChromaDB** — sentence-transformer embeddings (`all-MiniLM-L6-v2`) for semantic search
2. **BM25Okapi** — keyword index persisted per show

At query time both are searched, then merged with **Reciprocal Rank Fusion** (k=60). Top 5 chunks + user notes → Groq for synthesis.

---

## Quickstart — Docker

```bash
git clone https://github.com/gokulKumbakkara/watchlog
cd watchlog

cp .env.example .env
# Edit .env — fill in GROQ_API_KEY (get one free at console.groq.com)

docker compose up
```

Open [http://localhost:8000](http://localhost:8000), register an account, and start tracking.

> Alembic migrations run automatically on startup. No manual `alembic upgrade head` needed.

---

## Quickstart — Local (no Docker)

```bash
# Prerequisites: Python 3.11+, PostgreSQL, Redis

pip install uv
uv sync

cp .env.example .env
# Edit DATABASE_URL and REDIS_URL to point to local services

alembic upgrade head
uvicorn app.main:app --reload
```

For the frontend (dev mode with hot reload):
```bash
cd frontend
npm install
npm run dev   # proxies /api → localhost:8000
```

---

## Environment Variables

Copy `.env.example` to `.env` and fill in:

| Variable | Required | Description |
|---|---|---|
| `DATABASE_URL` | yes | `postgresql+asyncpg://user:pass@host:5432/db` |
| `REDIS_URL` | yes | `redis://localhost:6379` |
| `GROQ_API_KEY` | yes | Get free at [console.groq.com](https://console.groq.com) |
| `JWT_SECRET_KEY` | yes | Any long random string — `openssl rand -hex 32` |
| `EXTENSION_API_KEY` | no | For Chrome extension — `openssl rand -hex 32` |
| `TVMAZE_CACHE_TTL` | no | TVMaze cache TTL in seconds (default: 21600) |
| `SEASON_CHECK_MONTHS` | no | Months between auto season checks (default: 6) |
| `EMBEDDING_MODEL` | no | Sentence-transformer model (default: `all-MiniLM-L6-v2`) |
| `AGENT_RATE_LIMIT` | no | slowapi rate limit (default: `20/minute`) |
| `ACCESS_TOKEN_EXPIRE_DAYS` | no | JWT token lifetime (default: 7) |

---

## Project Structure

```
watchlog/
├── app/
│   ├── api/v1/
│   │   ├── auth.py          # register, login, /me
│   │   ├── series.py        # watchlist CRUD + season check
│   │   └── agent.py         # SSE streaming chat endpoint
│   ├── agent/
│   │   ├── agent.py         # LangChain ReAct executor + system prompt
│   │   └── tools.py         # 11 async tools (ContextVar for user isolation)
│   ├── db/
│   │   └── models.py        # User, Series, ConversationHistory
│   ├── services/
│   │   ├── auth.py          # JWT + bcrypt
│   │   ├── crud.py          # all DB ops (user-scoped)
│   │   ├── rag.py           # hybrid search (ChromaDB + BM25 + RRF)
│   │   ├── ingestion.py     # episode summary indexing
│   │   └── tvmaze.py        # TVMaze API + Redis cache
│   └── core/
│       ├── config.py        # pydantic-settings
│       └── lifespan.py      # startup: migrations, Redis, ChromaDB, scheduler
├── frontend/
│   └── src/
│       ├── pages/AuthPage.tsx       # login / register form
│       ├── components/
│       │   ├── SeriesCard.tsx       # poster card with progress bar
│       │   ├── EditModal.tsx        # progress tab + structured notes tab
│       │   ├── SearchBar.tsx        # TVMaze search with poster dropdown
│       │   └── Chat.tsx             # SSE streaming chat UI
│       ├── auth.ts                  # token management (localStorage)
│       └── api.ts                   # typed fetch wrapper with auth headers
├── alembic/versions/
│   ├── 0001_initial.py
│   └── 0002_add_users.py
├── Dockerfile                # multi-stage: Node build → Python build → runtime
├── docker-compose.yml
└── pyproject.toml
```

---

## API Reference

All routes under `/api/v1`. Protected routes require `Authorization: Bearer <token>`.

### Auth
| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `/auth/register` | — | Register new user, returns JWT |
| POST | `/auth/login` | — | Login, returns JWT |
| GET | `/auth/me` | ✓ | Current user info |

### Series
| Method | Path | Description |
|---|---|---|
| GET | `/series` | List watchlist (`?status=` filter) |
| POST | `/series` | Add show by `tvmaze_id` |
| GET | `/series/{id}` | Get single show |
| PUT | `/series/{id}` | Update progress / status / notes |
| DELETE | `/series/{id}` | Remove show + RAG data |
| GET | `/series/search?q=` | Search TVMaze (top 8) |
| POST | `/series/{id}/reindex` | Re-ingest episode summaries |
| POST | `/series/check-seasons` | Check all shows for new seasons + upcoming eps |

### Agent
| Method | Path | Description |
|---|---|---|
| POST | `/agent/chat` | SSE streaming ReAct agent |

### Other
| Method | Path | Description |
|---|---|---|
| GET | `/health` | DB + Redis + ChromaDB health check |
| POST | `/extension/now-playing` | Chrome extension progress update |

---

## Architecture Decisions

- **ContextVar for user isolation in agent tools** — Module-level globals would cause race conditions with concurrent users. `contextvars.ContextVar` scopes `user_id` per async task safely.
- **LangChain pinned to `<0.3.0`** — `create_react_agent` was removed in 1.x. Pinned to 0.2.x.
- **All agent tools are `async def`** — Sync wrappers with `ThreadPoolExecutor` caused "Future attached to a different loop" errors with DB connections. Rewrote all 10 tools as native async.
- **Final Answer filtering in SSE** — The LLM streams its full reasoning chain (Thought/Action/Observation). Only tokens after `"Final Answer:"` are forwarded to the browser.
- **`TIMESTAMP WITHOUT TIME ZONE` + tz-aware datetimes** — Frontend sends ISO strings with UTC offset. FastAPI/Pydantic parses them as tz-aware. asyncpg rejects tz-aware datetimes for naive columns. Fixed by stripping `tzinfo` in CRUD before writing.

---

## Chrome Extension Integration

The `/api/v1/extension/now-playing` endpoint auto-updates your progress from streaming services.

```json
POST /api/v1/extension/now-playing
Headers: { "X-Extension-Key": "<EXTENSION_API_KEY>" }
Body: { "show_name": "The Boys", "season": 4, "episode": 3, "source": "amazon" }
```

Tab title regexes to parse in `content.js`:
- Netflix: `/^(.+) - S(\d+):E(\d+)/`
- Disney+: `/^(.+) \| Season (\d+) \| Episode (\d+)/`
- Prime Video: `/^(.+) - Season (\d+), Episode (\d+)/`
- Hotstar: `/^(.+) - S(\d+) E(\d+)/`

---

## Codebase Intelligence (Repowise)

This repo is indexed by [Repowise](https://github.com/repowise-dev/repowise) — code graph, git history, dead code detection, and auto-generated wiki pages.

```bash
pip install repowise
cd watchlog

# Uses Groq via OpenAI-compatible endpoint
OPENAI_API_KEY=<your_groq_key> OPENAI_BASE_URL=https://api.groq.com/openai/v1 \
  repowise init --provider openai --model llama-3.3-70b-versatile --embedder mock -y

repowise serve   # local dashboard
```

---

## License

MIT

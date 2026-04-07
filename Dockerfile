# ── Stage 1: Build React frontend ────────────────────────────────────────────
FROM node:20-alpine AS frontend-builder
WORKDIR /frontend
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm install
COPY frontend/ .
RUN npm run build
# vite outDir is ../static, so output lands at /static (one level up from /frontend)
RUN mkdir -p /app/static && cp -r /static/* /app/static/

# ── Stage 2: Build Python deps ────────────────────────────────────────────────
FROM python:3.11-slim AS builder
WORKDIR /app
RUN pip install uv
COPY pyproject.toml .
RUN uv sync --no-dev

# ── Stage 3: Runtime ──────────────────────────────────────────────────────────
FROM python:3.11-slim AS runtime
WORKDIR /app

COPY --from=builder /app/.venv /app/.venv
COPY --from=frontend-builder /app/static /app/static
COPY app/ app/
COPY alembic/ alembic/
COPY alembic.ini .

RUN mkdir -p chroma_db bm25_indexes logs

ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONPATH="/app"

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

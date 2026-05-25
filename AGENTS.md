# Chat Agent - Agent Guide

## Cursor Cloud specific instructions

### Services overview

| Service | Port | Start command | Notes |
|---------|------|---------------|-------|
| **PostgreSQL** (pgvector) | 5432 | `sudo docker start chat-agent-postgres` | Docker container `chat-agent-postgres`; must be running before backend |
| **Backend** (FastAPI) | 8000 | `cd backend && make dev` | Requires `backend/.env` with all config (see below) |
| **Frontend** (React/Vite+) | 3000 | `cd frontend && vp dev` | Requires `vp` CLI (`source ~/.vite-plus/env`) |

### PostgreSQL

- Runs as a Docker container named `chat-agent-postgres` using `pgvector/pgvector:pg18`.
- Credentials: `postgres:postgres`, database `ai_assistant_db`.
- Start Docker daemon first: `sudo dockerd &>/tmp/dockerd.log &` then `sudo docker start chat-agent-postgres`.
- The `vector` extension must be enabled: `sudo docker exec chat-agent-postgres psql -U postgres -d ai_assistant_db -c "CREATE EXTENSION IF NOT EXISTS vector;"`.

### Backend configuration gotchas

- The backend loads config from Nacos (config center), but gracefully falls back to empty config when Nacos is unreachable. All config can be provided via env vars in `backend/.env` using `__` as nested delimiter (e.g. `DATABASE__HOST=localhost`).
- JWT keys must use `\n` for line breaks within a double-quoted `.env` value, e.g. `SECURITY__JWT__PRIVATE_KEY="-----BEGIN PRIVATE KEY-----\nMIIE..."`.
- The initial Alembic migration (`6fc87d2a678f`) assumes tables already exist (it only alters columns). For a fresh DB, first let the app create tables via `SQLModel.metadata.create_all` (i.e. start the backend once or run `uv run python -c "import app.models; from app.core.db import create_db_and_tables; create_db_and_tables()"`), then stamp: `uv run alembic stamp head`.
- Set `DATABASE__HOST=localhost` as an env var when running locally (the Nacos config may return a remote host).

### Frontend

- Uses **Vite+** CLI (`vp`). Source the env before using: `source ~/.vite-plus/env`.
- Do **not** use `npm`/`pnpm` directly; always use `vp install`, `vp dev`, `vp lint .`, `vp build`.
- Dev server proxies `/api` to `http://localhost:8000` (see `vite.config.ts`).

### User data layout (v4)

Per-user disk layout under `backend/data/user_data/{user_id}/`:

```
conversations/{conversation_id}/
  workspace/   # Agent read/write work area
  uploads/     # Session uploads (+ derived/ for PDF markdown)
  outputs/     # Final deliverables
```

Agent virtual paths (not disk directory names): `/mnt/user-data/workspace/`, `/mnt/user-data/uploads/`, `/mnt/user-data/outputs/`, `/mnt/skills/`. Path helpers live in `app/vfs/paths.py`. Alembic revision `b4c5d6e7f8a9` migrates v3 `workspaces/{conv}` and `uploads/{conv}` into the layout above.

### Running tests

- **Backend**: `cd backend && make lint` (ruff), `make test` (pytest, but `tests/mcp_demo/` requires real API keys—exclude with `--ignore=tests/mcp_demo`).
- **Frontend**: `cd frontend && vp lint .` (oxlint), `vp build` (build check).

### Pre-commit hooks

- `.husky/pre-commit` runs `vp staged` (frontend) and `uv run pre-commit run` (backend).
- These require `vp` and `uv` on PATH.

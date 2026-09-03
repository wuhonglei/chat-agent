# Chat Agent - Agent Guide

## Cursor Cloud specific instructions

### Services overview

| Service | Port | Start command | Notes |
|---------|------|---------------|-------|
| **PostgreSQL** (pgvector + zhparser) | 5432 | `docker compose up -d postgres` | 容器 `chat-agent-postgres`；换镜像勿 `down -v` |
| **Backend** (FastAPI) | 8000 | `cd backend && make dev` | Requires `backend/.env` with all config (see below) |
| **Frontend** (React/Vite+) | 3000 | `cd frontend && vp dev` | Requires `vp` CLI (`source ~/.vite-plus/env`) |

### PostgreSQL

- Runs as Docker container `chat-agent-postgres`，镜像为自建 `chat-agent-postgres:pg18-zhparser`（`docker/postgres/Dockerfile`：`pgvector/pgvector:pg18` + SCWS + zhparser）。
- 构建/换镜像（**勿** `docker compose down -v`，会删 `postgres_data` 丢数据）：
  `docker compose build postgres && docker compose up -d --force-recreate postgres`
- Credentials: `postgres:postgres`, database `ai_assistant_db`.
- Start Docker daemon first: `sudo dockerd &>/tmp/dockerd.log &` then start/recreate the container as above.
- Extensions: `vector`（pgvector）与 `zhparser`（会话搜索 `zhcfg`）需可用；迁移 `i2j3k4l5m6n7` 会 `CREATE EXTENSION IF NOT EXISTS`，扩展文件不存在则失败。搜索实现见 `docs/CONVERSATION_SEARCH_OPTIMIZATION.md`。

### Deploy (`deploy.sh`)

- 首次 `compose up`：若 CLI 支持，使用 `--wait --wait-timeout 300`（默认约 60s，后端冷启动 / 迁移经常不够）。
- 零停机更新：`zero_downtime_deploy` 对 backend 默认等健康检查最多 120s（容器内 `curl -f http://127.0.0.1:8000/`）。
- 脚本末尾「最终健康检查」对 backend 再重试最多 12 次、间隔 5s，避免冷启动被误判失败。仅检查本次部署范围内的服务（只更 backend 不会因未起 frontend 失败）。

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
skills/                          # User custom skills (virtual /mnt/skills/custom/)
conversations/{conversation_id}/
  workspace/   # Agent read/write work area
  uploads/     # Session uploads (+ derived/ for PDF markdown)
  outputs/     # Final deliverables
```

Agent virtual paths (not disk directory names): `/mnt/user-data/workspace/`, `/mnt/user-data/uploads/`, `/mnt/user-data/outputs/`, `/mnt/skills/public/` (built-in, read-only), `/mnt/skills/custom/` (per-user, read-write). Path helpers live in `app/vfs/paths.py`; operational details for VFS, file/shell MCP, and sandbox backends live in `backend/docs/VFS_AND_SANDBOX.md`. Alembic revision `b4c5d6e7f8a9` migrates v3 `workspaces/{conv}` and `uploads/{conv}` into the layout above.

### Running tests

- **Backend**: `cd backend && make lint` (ruff), `make test` (pytest, but `tests/mcp_demo/` requires real API keys—exclude with `--ignore=tests/mcp_demo`).
- **Frontend**: `cd frontend && vp lint .` (oxlint), `vp build` (build check).

### Pre-commit hooks

- `.husky/pre-commit` runs `vp staged` (frontend) and `uv run pre-commit run` (backend).
- These require `vp` and `uv` on PATH.

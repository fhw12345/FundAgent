# Getting Started — Fund Agent Development

A single-user, docker-compose-only setup. Everything runs on your machine.

## Prerequisites

- **Docker Desktop** (Compose v2). Verify: `docker compose version`.
- **Python 3.12** (only needed for running tests / linters outside the container).
- **Node 20+** (only for IDE tooling — runtime lives in the frontend container).
- **VS Code with the Agent Maestro extension running on `localhost:23333`** — the backend routes every LLM call through it. Without Agent Maestro running, the app starts but chat / analysis / screenshot import will fail.

Verify Agent Maestro: `curl http://localhost:23333/health` should return 200.

## Clone and run

```bash
git clone https://github.com/<you>/FundAgent.git
cd FundAgent
make dev          # docker compose up
```

After ~30 seconds:

| Service | URL |
|---|---|
| Frontend | http://localhost:3000 |
| Backend API | http://localhost:8000 |
| Backend OpenAPI docs | http://localhost:8000/docs |
| MongoDB | localhost:27017 (db: `fund_agent`) |
| Redis | localhost:6379 |

### Optional: Langfuse (LLM tracing dev tool)

```bash
docker compose --profile observability up -d
# Langfuse UI: http://localhost:3001
# MinIO console: http://localhost:9003
```

Langfuse is **not required**. It captures traces of LLM calls when you want to debug agent behavior; turn it off otherwise.

## First login

The app is single-user. Default credentials are seeded on first run by the auth service — check `backend/.env` (`SEED_USERNAME` / `SEED_PASSWORD`) or look at the backend logs on first start. Change them by editing `.env` and recreating the backend container (see env-vars rule below).

## Daily Development Loop

```bash
# Make code changes — hot reload covers most of them
# Backend hot reload: uvicorn watches ./backend/src
# Frontend hot reload: Vite dev server inside the frontend container

# Run tests + linters
cd backend && make test && make lint
docker compose exec frontend npm run lint && npm test

# Format
make fmt

# Tail logs
docker compose logs -f backend
docker compose logs -f frontend
```

## 🚨 Env Var Rule (the bug that bites everyone)

`docker compose restart` does **not** reload `.env`. Containers bake env vars at create time.

```bash
# After editing .env or backend/.env
docker compose up -d --force-recreate <service>
docker compose exec <service> printenv | grep <VAR_PREFIX>     # verify
```

See [docs/troubleshooting/docker-env-reload-issue.md](../troubleshooting/docker-env-reload-issue.md).

## Adding a Python dependency

```bash
docker compose run --rm backend pip install <pkg>
# Then add it to backend/pyproject.toml dependencies = [...]
# Next make dev rebuild will pick it up.
```

## Adding a frontend dependency

```bash
docker compose exec frontend npm install <pkg>
# package.json + package-lock.json get updated inside the container,
# but the bind mount surfaces them to your repo.
```

## Common Issues

| Symptom | Likely cause |
|---|---|
| Chat returns 500 with `connection refused 23333` | Agent Maestro not running in VS Code |
| Backend can't reach MongoDB | The `mongodb` service hasn't finished initializing — `docker compose logs mongodb` |
| AkShare timeouts on first run | Some endpoints are slow / rate-limited; Redis cache catches up after the first call |
| Pre-commit blocks commit with version error | You didn't bump the version. Run `./scripts/bump-version.sh [backend|frontend] [patch|minor|major]` |
| Stale env after `.env` change | Use `--force-recreate`, not `restart` (see rule above) |

## Next Steps

- [CONTRIBUTING.md](../../CONTRIBUTING.md) — full PR / branching / commit conventions
- [docs/architecture/system-design.md](../architecture/system-design.md) — how the pieces fit together
- [docs/architecture/agent-architecture.md](../architecture/agent-architecture.md) — LangGraph + sub-agents + tools
- [docs/architecture/database-schema.md](../architecture/database-schema.md) — MongoDB collections

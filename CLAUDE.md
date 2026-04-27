# Fund Agent - Development Guide

> Concise actionable rules. Details live in [docs/](docs/).

Fund Agent is a **personal-use AI assistant for Chinese onshore mutual funds (场外基金)**. Local-only: docker-compose for dev, no production cluster, no CI/CD deploy. Frontend in 中文; backend talks to AkShare + 天天基金 + multi-vendor LLMs via Agent Maestro proxy.

## 🎯 Recent Architecture Changes

**Portfolio + Fund Detail Redesign** (2026-04-27, shipped) — Alipay-style UI rework.
- 7 new components under `frontend/src/components/{portfolio,fund}/`
- `PortfolioDashboard.tsx` slimmed ~700 → ~290 lines; `FundDetailPage.tsx` rebuilt with tabs
- Backend: NAV history extended 90 → 250 trading days for client-side week/month/year toggle
- Versions: backend v0.12.1, frontend v0.13.0
- See [spec](docs/superpowers/specs/2026-04-27-portfolio-fund-detail-redesign-design.md), [plan](docs/superpowers/plans/2026-04-27-portfolio-fund-detail-redesign.md)

**Rebrand FinancialAgent → FundAgent** (2026-04-24, completed in commit `eec9e53`) — repo refocused from US stock technical analysis to CN mutual fund analysis. Removed: Fibonacci/Stochastic/Market Structure analysis, Alpha Vantage/Alpaca/yfinance integrations, credit/billing system, feedback platform, K8s production deployment, Langfuse production stack. See [docs/specs/2026-04-24-fundagent-design.md](docs/specs/2026-04-24-fundagent-design.md).

## 🔐 Security Rules

**🚨 NEVER COMMIT SECRETS** — API keys, passwords, tokens, credentials, certificates.
- Use placeholders in commits: `<REDACTED>`, `YOUR_KEY_HERE`
- Real values go in untracked `backend/.env` (loaded by docker-compose)
- Before commit: `git diff --staged | grep -iE 'key|secret|password|token'`

## Tech Stack

| Layer | Technology |
|---|---|
| **Backend** | Python 3.12 + FastAPI + Motor (MongoDB) + Redis |
| **Frontend** | React 18 + TypeScript 5 + Vite + TailwindCSS |
| **LLM** | LangChain + LangGraph; routed through **Agent Maestro proxy** (localhost:23333) to Claude Opus 4.7 / GPT-5.4 / Gemini 3.1 Pro |
| **Data** | AkShare + 天天基金 (eastmoney) crawler |
| **Deployment** | Docker Compose (local only) |

> 📖 **See [System Design](docs/architecture/system-design.md) for architecture details**

## 🌍 Environment

**Single environment: local docker-compose.** No production cluster, no test cluster, no CI deploy.

### Prerequisites
- Docker Desktop running
- **Agent Maestro extension running in VS Code on `localhost:23333`** — backend routes all LLM calls through it. `make dev` starts but chat will fail without it.

### How to run
```bash
make dev              # docker compose up
# Frontend: http://localhost:3000
# Backend:  http://localhost:8000   (OpenAPI: /docs)
# MongoDB:  localhost:27017
# Redis:    localhost:6379
```

### Optional Langfuse profile (LLM tracing, dev tool only)
```bash
docker compose --profile observability up -d
# Langfuse UI: http://localhost:3001
```

## 🧪 Testing & Iteration

**When iterating on a feature**:
1. Run the change through docker-compose locally.
2. Use Playwright + Chromium for browser flows; verify backend logs + MongoDB state + UI all line up.
3. Don't stop at the first fix — keep iterating until logs, DB, and UI are all consistent.

**Browser automation setup** (when needed):
```bash
pip install playwright && python -m playwright install chromium
```

> 📖 [E2E Automation Guide](docs/testing/e2e-automation-guide.md) · [E2E Reference](docs/testing/e2e-reference.md) · [Testing Strategy](docs/development/testing-strategy.md)

## Development Workflow

> 📖 **Full process**: [CONTRIBUTING.md](CONTRIBUTING.md)

```bash
# 1. Make changes
# 2. Test
cd backend && make test && make lint
docker compose exec frontend npm run lint && npm test

# 3. Bump version (pre-commit enforces this)
./scripts/bump-version.sh backend patch
./scripts/bump-version.sh frontend minor

# 4. Update CHANGELOG entry under docs/project/versions/{backend,frontend}/CHANGELOG.md
# 5. Commit
git add . && git commit -m "feat(scope): description"
```

### Key Rules
- **Frontend commands** always via `docker compose exec frontend npm ...` — `node_modules` lives in the container.
- **Pre-commit hook enforces version bump** on every commit.
- **Don't recreate venvs** — reuse `/tmp/webtesting/*/venv` if you've made one before.

## Code Standards

- Max 500 lines per Python/TS/JS file.
- Black + Ruff + mypy (Python); ESLint + Prettier + eslint-plugin-security + eslint-plugin-perf-standard (TS).

> 📖 [docs/development/coding-standards.md](docs/development/coding-standards.md)

## Quick Reference Commands

```bash
make dev                                    # Start all services
make test                                   # All tests
make fmt && make lint                       # Format + lint
docker compose logs -f backend              # Tail backend logs
docker compose logs -f frontend             # Tail frontend logs
curl http://localhost:8000/api/health       # Health check
docker compose exec mongodb mongosh fund_agent  # DB shell
```

## Pre-Commit Checklist

- [ ] Tested locally in docker-compose (clicked through the actual flow)
- [ ] `make fmt && make test && make lint` clean
- [ ] Bumped version: `./scripts/bump-version.sh [component] [patch|minor|major]`
- [ ] CHANGELOG entry added under `docs/project/versions/{component}/CHANGELOG.md`
- [ ] Pydantic ↔ TypeScript contracts aligned
- [ ] No secrets in diff

## Debugging Tips

1. Check `docker compose logs -f backend` first.
2. Verify Pydantic ↔ TypeScript contracts.
3. Hit backend directly: `docker compose exec backend python -c "..."`.
4. Inspect Redis: `docker compose exec redis redis-cli`.
5. **Missing Python pkg**: `docker compose run --rm backend pip install <pkg>` and add it to `pyproject.toml` — don't rebuild the whole image.
6. **🚨 .env changes don't reload via `restart`** — see Critical Docker Rules below.

## 💡 Development Principles

- Find the root cause; don't patch the symptom.
- Try the simplest fix first (10 seconds) before reaching for the complex one (20+ minutes).
- Less code is more. Three similar lines beat a premature abstraction.
- No half-finished implementations or speculative future-proofing.

---

## 🚨 Critical Docker Rule: env vars

**`docker compose restart` does NOT reload `.env`.** Containers bake in env at create time.

```bash
# After editing .env or backend/.env
docker compose up -d --force-recreate <service>

# Verify the new value landed
docker compose exec <service> printenv | grep <VAR_PREFIX>
```

> 📖 [docs/troubleshooting/docker-env-reload-issue.md](docs/troubleshooting/docker-env-reload-issue.md)

---

**Always start by reading [docs/README.md](docs/README.md) for context.**

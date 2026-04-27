# Fund Agent — Project Specifications

> **Reflects backend v0.12.1 / frontend v0.13.0.**

This is the canonical "what is this project" document. For the higher-level product framing, see [`prd.md`](prd.md). For architecture, see [`architecture/system-design.md`](architecture/system-design.md).

## Project Goal

A private, single-user AI assistant for managing a personal portfolio of Chinese onshore mutual funds (场外基金), with multi-vendor LLM debate to reduce single-model bias.

## Project Layout

```
FundAgent/
├── README.md
├── CLAUDE.md                              development rules
├── CONTRIBUTING.md
├── Makefile
├── docker-compose.yml
├── backend/
│   ├── pyproject.toml
│   ├── src/
│   │   ├── api/                           FastAPI routes
│   │   ├── agent/                         LangGraph + sub-agents + tools
│   │   ├── services/                      domain logic
│   │   ├── database/                      Motor + redis-py + repositories
│   │   ├── models/                        Pydantic models
│   │   └── main.py
│   └── tests/
├── frontend/
│   ├── package.json
│   ├── vite.config.ts
│   └── src/
│       ├── pages/
│       ├── components/
│       └── public/locales/                i18n (en / zh-CN)
├── docs/                                  documentation
├── scripts/                               version bump, pre-commit, etc.
├── .pipeline/                             legacy K8s manifests (unused)
└── .github/workflows/                     PR checks only (no deploy)
```

## Backend

### Framework
Python 3.12, FastAPI (async), Motor (MongoDB), redis-py.

### Routes (under `backend/src/api/`)

| Prefix | Source | Notes |
|---|---|---|
| `/api/health/*` | `health.py` | Liveness, readiness, mongodb, redis |
| `/api/admin/*` | `admin.py` | DB stats, cache, timing metrics |
| `/api/funds/{fund_code}` | `fund_detail.py` | NAV history, holdings, basic info |
| `/api/portfolio` | `portfolio.py` | Holdings CRUD, screenshot import, daily analysis |
| `/api/transactions` | `transactions.py` | 买入 / 卖出 / 分红再投, supports `fund_code` filter |
| `/api/dca-plans` | `transactions.py` | 定投 plan management |
| `/api/jobs/*` | `jobs.py` | Background analysis run records |
| `/api/quarterly-report/*` | `quarterly_report.py` | PDF / text fund quarterly report analysis |
| `/api/models` | `llm_models.py` | List Agent Maestro-routed models |
| `/api/chat/*` | `chat/` | SSE streaming chat |

### Agent Layer (under `backend/src/agent/`)

- **Orchestrators**: `chat_agent.py`, `langgraph_react_agent.py`, `deep_react_agent.py`
- **Sub-agents**: `subagents/financial.py`, `subagents/technical.py`, `subagents/news.py`, `subagents/debater.py`
- **Tools**: `tools/akshare_fund_tools.py`, `tools/eastmoney_tools.py`, `tools/analysis_cache.py`, `tools/categorization.py`
- **Routing**: `llm_client.py` → Agent Maestro proxy at `localhost:23333`

### Auth
Simplified single-user JWT (access + refresh). No OIDC, no multi-tenant.

### Storage
- **MongoDB** (`fund_agent` db, configurable). Collections: `users`, `refresh_tokens`, `chats`, `messages`, `portfolios` (embedded `holdings[]`), `transactions`, `dca_plans`, `job_runs`, `fund_sector_mapping`. See [`architecture/database-schema.md`](architecture/database-schema.md).
- **Redis**. Caching for AkShare results, sector lookups, analysis memoization. TTL per data type.

### Containerization
Multi-stage Dockerfile. Image registered in Azure ACR for users who choose to push (project itself does not auto-deploy).

## Frontend

React 18 + TypeScript 5 + Vite + TailwindCSS. Pages under `frontend/src/pages/`, components under `frontend/src/components/{portfolio,fund,chat,...}/`, i18n under `public/locales/`.

State: React Query (TanStack Query) for server state.

Build output is served by the dev container in dev. There is no separate static-hosting deploy.

## LLM

All calls funnel through **Agent Maestro** (VS Code extension running locally on `localhost:23333`). Per-role default models:

| Role | Model | Vendor |
|---|---|---|
| Main analyst | claude-opus-4-7 | Anthropic |
| Vision (screenshot import) | gpt-5.4 | OpenAI |
| Fundamentals | gpt-5.4 | OpenAI |
| News | gemini-3.1-pro-preview | Google |
| Debater | gemini-3.1-pro-preview | Google |
| PDF / quarterly report | gemini-3.1-pro-preview | Google |

Debater must use a different vendor than the main analyst.

## Data Sources

- **AkShare** — primary. Fund NAV, rankings, holdings, manager info, sector exposure, macro indicators.
- **EastMoney (天天基金) crawler** — supplementary, polite/rate-limited (`backend/src/services/eastmoney_crawler.py`).

No Alpha Vantage, Alpaca, yfinance, EXA, FRED — all removed in the rebrand (`c6e45f3 refactor(backend): delete US market modules and simplify to fund-only architecture`).

## Infrastructure

**Local docker-compose only.** No production cluster, no test cluster, no auto-deploy.

`docker-compose.yml` services:
- `backend` (uvicorn)
- `frontend` (Vite dev server)
- `mongodb`
- `redis`
- Optional `langfuse-*` profile for LLM tracing during development

The `.pipeline/` directory contains legacy Kubernetes manifests retained for reference but unused in the current workflow.

## CI/CD

`.github/workflows/` runs PR checks only:
- Branch name policy (`users/{user}/{feature}`)
- Backend pytest
- Frontend tests
- Linting (Ruff, Black, ESLint, mypy, TypeScript)
- Pre-commit version-bump validation

There is no deploy workflow.

## Observability

- **Structured logs** via `structlog` on the backend. Output to stdout (Docker captures it).
- **Optional Langfuse** dev tool. Activate with `docker compose --profile observability up -d`. Not required.

No production metrics, alerts, or aggregated logging. This is a single-user project running on the user's machine.

## Security

- All secrets in untracked `.env` / `backend/.env` files (gitignored).
- LLM API keys live in Agent Maestro's VS Code config — backend never sees them.
- Single-user JWT for the local app.
- No external network exposure intended; bind only to `localhost`.

## Out of Scope

- Real trading
- Multi-user / SaaS
- US-stock technical analysis (Fibonacci / Stochastic / Market Structure) — removed in rebrand
- Credit / billing
- Public feedback platform

## Roadmap (informal)

This is a personal project; the roadmap is whatever the user wants to ship next. Current themes:

- Quarterly report PDF interpretation (M3) — landed in `feat(quarterly-report): add PDF quarterly report analysis module`
- Polite eastmoney crawler — landed in `feat(crawler): add eastmoney polite crawler + agent tools`
- Portfolio + fund detail UI redesign — landed in commit `422fd4d` (Apr 2026)

## References

- [PRD](prd.md)
- [System Design](architecture/system-design.md)
- [Agent Architecture](architecture/agent-architecture.md)
- [Database Schema](architecture/database-schema.md)
- [Rebrand spec](specs/2026-04-24-fundagent-design.md)

# Fund Agent — System Design

## Executive Summary

Fund Agent is a single-user, docker-compose application. The backend is a FastAPI service that talks to MongoDB and Redis, calls AkShare / eastmoney for fund data, and routes all LLM calls through a local Agent Maestro proxy. The frontend is a React + Vite SPA in 中文.

There is no Kubernetes deployment, no CDN, no message queue, no managed cloud infra. Everything runs on the user's machine.

## High-Level Topology

```
                      ┌─────────────────────┐
                      │  VS Code            │
                      │  Agent Maestro      │  ← user's API keys live here
                      │  localhost:23333    │
                      └──────────▲──────────┘
                                 │  HTTPS (multi-vendor: Claude / GPT / Gemini)
                                 │
┌─────────────┐     HTTP    ┌────┴───────────┐    Motor    ┌────────────┐
│  Browser    │◀───────────▶│  Backend       │◀───────────▶│  MongoDB   │
│  React SPA  │   :3000     │  FastAPI       │             │  fund_agent│
│  (Vite)     │             │  :8000         │             └────────────┘
└─────────────┘             │                │    redis-py ┌────────────┐
                            │                │◀───────────▶│  Redis     │
                            │                │             └────────────┘
                            │                │   AkShare / eastmoney HTTP
                            │                │◀──────────────────────────▶ data sources
                            └────────────────┘
```

## Backend Layout

```
backend/src/
├── api/                    HTTP routes
│   ├── admin.py              /api/admin/* — health, db stats, cache
│   ├── chat/                 /api/chat/*  — SSE streaming chat
│   ├── fund_detail.py        /api/funds/{code} — NAV / holdings / info
│   ├── health.py             /api/health/*
│   ├── jobs.py               /api/jobs/* — background job runs
│   ├── llm_models.py         /api/models — list available models
│   ├── portfolio.py          /api/portfolio — holdings, screenshot import, daily analysis
│   ├── quarterly_report.py   /api/quarterly-report — PDF / text analysis
│   ├── transactions.py       /api/transactions, /api/dca-plans
│   ├── dependencies/         FastAPI deps (auth, repos)
│   └── schemas/              request / response models
│
├── agent/                  LLM orchestration
│   ├── chat_agent.py         simple chat agent
│   ├── langgraph_react_agent.py  primary ReAct loop
│   ├── deep_react_agent.py   debate-enabled flow
│   ├── deep_agent_adapter.py adapter for deepagents lib
│   ├── debate_types.py       structured concern/rebuttal types
│   ├── llm_client.py         Agent Maestro routing (per-role model picks)
│   ├── subagents/            financial / technical / news / debater
│   ├── tools/                akshare_fund_tools, eastmoney_tools, analysis_cache, categorization
│   └── skills/               markdown SKILL.md files for sub-agents
│
├── services/               domain logic
│   ├── auth_service.py       single-user JWT
│   ├── chat_service.py
│   ├── portfolio_service.py
│   ├── cost_basis.py
│   ├── eastmoney_crawler.py  polite rate-limited fetcher
│   ├── sector_classifier.py
│   ├── confirmation_scheduler.py
│   ├── dca_scheduler.py
│   ├── settlement.py
│   ├── token_service.py
│   ├── quarterly_report_service.py
│   ├── portfolio_enrichment.py
│   ├── market_data.py
│   ├── context_window_manager.py
│   └── database_stats_service.py
│
├── database/
│   ├── mongodb.py            Motor connection (config-driven db name)
│   ├── redis.py              redis-py async cache
│   └── repositories/         one file per collection
│
├── models/                 Pydantic models (chat, message, transaction, user, refresh_token)
└── main.py                 FastAPI app + lifespan
```

## Frontend Layout

```
frontend/src/
├── pages/
│   ├── PortfolioDashboard.tsx   landing — hero + holdings cards
│   ├── FundDetailPage.tsx       per-fund page with tabs
│   ├── TransactionHistory.tsx
│   ├── TransactionsPage.tsx
│   ├── HealthPage.tsx
│   ├── InsightsPage.tsx         (legacy, low-traffic)
│   └── FeedbackPage.tsx         (legacy, low-traffic)
│
├── components/
│   ├── portfolio/   HeroCard, FundCard, AddHoldingModal
│   ├── fund/        NavChart, TransactionList, MyHoldingTab, FundInfoTab
│   ├── chat/        SSE streaming chat UI
│   └── ...
│
└── public/locales/  i18n (en / zh-CN)
```

See the recent redesign: [docs/superpowers/specs/2026-04-27-portfolio-fund-detail-redesign-design.md](../superpowers/specs/2026-04-27-portfolio-fund-detail-redesign-design.md).

## Data Flow: Daily Analysis

1. User clicks "Analyze" in PortfolioDashboard.
2. `POST /api/portfolio/daily-analysis` → background task in `portfolio_service`.
3. For each holding: `agent/langgraph_react_agent` runs with tools from `agent/tools/akshare_fund_tools`.
4. The deep variant (`deep_react_agent`) adds debate: main analyst → debater (different vendor) → rebuttal → verdict.
5. Result persisted to MongoDB; UI polls `/api/jobs/recent` for status, then renders the verdict.

## Data Flow: Screenshot Import

1. User uploads Alipay / 天天基金 screenshot via `AddHoldingModal`.
2. `POST /api/portfolio/import-screenshot` → GPT-5.4 vision (via Agent Maestro) parses fund codes + amounts.
3. `portfolio_service` upserts into `portfolios` / `holdings`.
4. `eastmoney_crawler` enriches each new fund with metadata.

## Storage

- **MongoDB** (`fund_agent` database, configurable). Collections owned by repositories under `backend/src/database/repositories/`. See [database-schema.md](database-schema.md).
- **Redis**. Caching layer for AkShare results, sector lookups, and analysis. TTLs vary by data type.
- **No object storage**. Screenshot uploads are processed in-memory and discarded.

## Deployment

Local docker-compose only. See [CLAUDE.md → Environment](../../CLAUDE.md#-environment).

There is no production cluster. The `.pipeline/` directory contains legacy K8s manifests retained for reference but unused.

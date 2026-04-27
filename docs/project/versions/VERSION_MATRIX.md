# Version Compatibility Matrix

> **Last updated:** 2026-04-27 — backend v0.12.1, frontend v0.13.0.

Fund Agent ships backend and frontend independently. They communicate over a stable REST + SSE contract; the matrix below records when paired versions were known to work end-to-end on local docker-compose.

## Current

| Component | Version | Released | Notes |
|---|---|---|---|
| Backend | 0.12.1 | 2026-04-27 | NAV history extended 90 → 250 trading days |
| Frontend | 0.13.0 | 2026-04-27 | Portfolio + fund detail redesign (Alipay-style) |

## Recent compatible pairs

| Backend | Frontend | Notes |
|---|---|---|
| 0.12.1 | 0.13.0 | UI redesign; required for week/month/year NAV toggle |
| 0.12.0 | 0.12.0 | Fund platform foundation (transactions, DCA, jobs, sectors, simplified auth) |
| 0.11.0 | 0.11.5 | Cross-vendor debate flow (`deep_react_agent`) baseline |

For older pairs, see git history of `backend/pyproject.toml` and `frontend/package.json`.

## Runtime requirements

| Component | Engine | Version |
|---|---|---|
| Backend | Python | 3.12+ |
| Backend | MongoDB | 7.0+ (works with Cosmos DB MongoDB API ≥ 4.2; see [troubleshooting/mongodb-cosmos-db.md](../../troubleshooting/mongodb-cosmos-db.md)) |
| Backend | Redis | 7.2+ |
| Frontend | Node | 20+ (only for IDE tooling — Vite dev server runs in container) |
| Both | Docker Compose | v2 |

## External services

| Service | Purpose | Required? |
|---|---|---|
| Agent Maestro (VS Code) | Routes all LLM calls (Claude / GPT / Gemini) | **Required** — backend can't reach LLMs without it |
| AkShare | Fund NAV, rankings, holdings, manager info | Required (Python lib, no API key) |
| EastMoney (天天基金) | Fund metadata fallback | Required (HTTP, polite crawler with rate limit) |
| Langfuse | LLM trace visualization | Optional (`--profile observability`) |

There is no Alpha Vantage, Alpaca, yfinance, EXA, FRED, DashScope, or Tencent SES dependency. All removed in the FundAgent rebrand.

## API contract — current

Routes (paths only — request/response schemas live in `backend/src/api/schemas/`):

```
GET    /api/health                          /health/{ready,live,mongodb,redis}
GET    /api/admin/{health,database,timing-metrics,cache/stats}
GET    /api/funds/{fund_code}
GET    /api/portfolio                       PUT /api/portfolio
POST   /api/portfolio/import-screenshot
POST   /api/portfolio/daily-analysis
POST   /api/transactions                    GET /api/transactions
DELETE /api/transactions/{tx_id}            GET /api/transactions/summary
*      /api/dca-plans/...                   (DCA CRUD)
GET    /api/jobs/recent                     GET /api/jobs/summary
POST   /api/jobs/tplus1/run
POST   /api/quarterly-report/{analyze-image,analyze-text}
GET    /api/models
*      /api/chat/...                        (SSE streaming chat)
```

## Breaking change history

### Rebrand (commit `eec9e53`, 2026-04-24)

This was a hard fork of the API surface, not a versioned migration:

- All US-stock analysis endpoints removed: `/api/analysis/{fibonacci,stochastic,macro,news-sentiment}`, `/api/market/{search,price/{symbol},movers}`, etc.
- Credit / billing endpoints removed.
- Feedback platform endpoints removed.
- Symbol search → fund_code-based lookup.
- DashScope LLM client → Agent Maestro multi-vendor routing.
- Auth simplified from OIDC + email-verification → single-user JWT.

There is no upgrade path from pre-rebrand versions; pinning anything before the rebrand is treated as legacy.

## Reporting incompatibility

If you find a backend/frontend pair that breaks an end-to-end flow, add a CHANGELOG note in the failing component and link the symptom from a new file under `docs/troubleshooting/`.

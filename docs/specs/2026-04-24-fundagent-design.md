# FundAgent Design Spec

**Date**: 2026-04-24
**Author**: Auto-generated
**Status**: Approved
**Scope**: MVP (M1) + Quarterly Reports (M3), ~1.5-2 weeks

---

## 1. Project Overview

FundAgent is a **private, personal-use** AI assistant for Chinese onshore mutual funds (场外基金). It transforms the FinancialAgent codebase from a US stock analysis platform into a CN fund analysis tool with:

- Multi-vendor LLM debate architecture (cross-vendor for quality)
- AkShare + 天天基金 data sources
- Screenshot-based portfolio import (multi-modal vision)
- Quarterly report PDF interpretation
- Manual-trigger daily analysis with explicit buy/sell/hold recommendations

**Target user**: Single private user (the developer). No multi-user, no billing, no complex auth.

---

## 2. What to Delete

| Module | Reason |
|--------|--------|
| Credit/billing system | Private use, no billing |
| Complex auth (JWT refresh rotation, registration, email verification) | Single user, simplify to basic login |
| Feedback system | Not needed |
| Alpaca trading integration | US broker, not applicable |
| US data sources (yfinance, EXA news) | Replace with CN sources |
| Langfuse observability stack | Overkill for private use |
| K8s deployment configs (.pipeline/) | Docker Compose only |
| Market Insights dashboard (7 US metrics) | Replace with fund-specific views |
| Portfolio CronJob | Manual trigger only |

**Files to delete**: `backend/src/services/credit/`, `backend/src/api/credit/`, `backend/src/services/feedback/`, `backend/src/services/alpaca/`, `backend/src/services/exa/`, `backend/src/workers/`, `.pipeline/`, langfuse docker-compose services, and related tests.

---

## 3. What to Keep

| Module | Notes |
|--------|-------|
| React 18 + TypeScript frontend | Adapt to Chinese, fund-focused UI |
| FastAPI backend | Core framework stays |
| MongoDB | Chat history, fund data cache |
| Redis | Data source caching (24h TTL) |
| Docker Compose | Simplified (backend + frontend + mongo + redis) |
| LangGraph Deep Agent + ReAct Agent | Core architecture preserved |
| Sub-agent debate loop | Enhanced with cross-vendor models |
| SSE streaming | Keep for chat responses |
| Basic JWT auth | Simplify to single-user |

---

## 4. LLM Layer Refactor — Agent Maestro

### 4.1 Agent Maestro Integration

All LLM calls route through **Agent Maestro** (VS Code extension, local proxy at `localhost:23333`).

**Base URLs for LangChain SDKs**:

| Vendor | Local URL | Docker URL |
|--------|-----------|------------|
| OpenAI | `http://localhost:23333/api/openai/v1` | `http://host.docker.internal:23333/api/openai/v1` |
| Anthropic | `http://localhost:23333/api/anthropic` | `http://host.docker.internal:23333/api/anthropic` |
| Gemini | `http://localhost:23333/api/gemini` | `http://host.docker.internal:23333/api/gemini` |

**API keys**: Dummy values (e.g., `"agent-maestro"`) — Agent Maestro handles real auth.

### 4.2 Role-Based Model Routing

Each sub-agent role maps to a specific model+vendor. The **debater MUST use a different vendor** than the main analyst to avoid echo-chamber bias.

```python
DEFAULT_ROLE_MODELS = {
    "main_analyst":  "claude-opus-4.7",       # Anthropic
    "technical":     "claude-opus-4.7",       # Anthropic
    "fundamentals":  "gpt-5.4",              # OpenAI
    "news":          "gemini-3.1-pro-preview", # Google
    "holdings":      "claude-opus-4.7",       # Anthropic
    "debater":       "gemini-3.1-pro-preview", # Google (differs from main)
    "summarize":     "claude-opus-4.7",       # Anthropic
    "vision":        "gpt-5.4",              # OpenAI (multi-modal)
    "pdf_reader":    "gemini-3.1-pro-preview", # Google (long context)
}
```

### 4.3 Factory Function

```python
def get_chat_model(role: str, settings: Settings) -> BaseChatModel:
    """Return the appropriate LangChain chat model for a given agent role."""
    model_name = settings.role_models.get(role, DEFAULT_ROLE_MODELS[role])
    vendor = infer_vendor(model_name)  # claude→anthropic, gpt→openai, gemini→google
    base_url = settings.agent_maestro_urls[vendor]
    
    if vendor == "openai":
        return ChatOpenAI(model=model_name, base_url=base_url, api_key="agent-maestro")
    elif vendor == "anthropic":
        return ChatAnthropic(model=model_name, base_url=base_url, api_key="agent-maestro")
    elif vendor == "google":
        return ChatGoogleGenerativeAI(model=model_name, ...)
```

### 4.4 Settings UI

Frontend `ModelSettings.tsx` simplified to show role→model mapping table. User can change any role's model via dropdown (populated from Agent Maestro's `/api/v1/lm/chatModels` endpoint). Pre-configured with defaults above.

---

## 5. Data Sources

### 5.1 AkShare (Primary)

Free Python library for CN financial data. No API key required.

| Data | AkShare Function | Cache TTL |
|------|-----------------|-----------|
| Fund NAV history | `ak.fund_open_fund_info_em()` | 24h |
| Fund rankings | `ak.fund_open_fund_rank_em()` | 24h |
| Fund holdings | `ak.fund_portfolio_hold_em()` | 7d |
| Fund manager info | `ak.fund_manager()` | 7d |
| Index data (沪深300 etc) | `ak.index_zh_a_hist()` | 24h |
| Macro indicators | `ak.macro_china_*()` | 24h |

### 5.2 天天基金 Friendly Crawler (M3)

For data not available via AkShare (e.g., real-time estimates, detailed fee structures).

**Rate limiting rules**:
- Minimum 1s between requests
- Custom User-Agent identifying the tool
- Redis cache with 24h TTL
- ETag/If-Modified-Since support
- Respect robots.txt

---

## 6. New Features

### 6.1 Screenshot Portfolio Import (M2)

User uploads screenshots from Alipay/天天基金/蛋卷基金/雪球 showing their fund holdings. GPT-5.4 vision model extracts:

- Fund codes (6-digit)
- Fund names
- Current value
- Profit/loss
- Share count

**Supported screenshot types**: Alipay fund page, 天天基金 holdings, 蛋卷基金 portfolio, 雪球基金组合.

**Flow**: Upload image → GPT-5.4 vision extraction → Structured JSON → Save to MongoDB → Enrich via AkShare.

### 6.2 Daily Analysis Orchestrator (M2)

Manual-trigger (button click) analysis that:

1. Loads user's portfolio (from screenshot import or manual entry)
2. For each fund: fetch latest NAV, holdings, sector exposure via AkShare
3. Run Deep Agent analysis with cross-vendor debate
4. Produce explicit recommendations: **买入 / 持有 / 卖出** with:
   - Signal strength (strong/moderate/weak)
   - Key reasoning (3-5 bullet points)
   - Risk factors
   - Suggested action amount (% of position)

### 6.3 Quarterly Report PDF Interpreter (M3)

Upload fund quarterly report PDF → Gemini 3.1 Pro (long context, 136k+) extracts:

- Top 10 holdings changes
- Sector allocation shifts
- Manager commentary highlights
- Performance attribution
- Risk metric changes

---

## 7. Sub-Agent Architecture (Fund Domain)

Replace US stock sub-agents with fund-specific ones:

| Sub-Agent | Role | Default Model |
|-----------|------|---------------|
| **fund_analyst** | NAV trends, performance vs benchmark | claude-opus-4.7 |
| **holdings_analyst** | Portfolio holdings, sector exposure | claude-opus-4.7 |
| **macro_analyst** | CN macro indicators, policy impact | gpt-5.4 |
| **news_analyst** | Fund/manager news, regulatory changes | gemini-3.1-pro-preview |
| **debater** | Challenge conclusions, find blind spots | gemini-3.1-pro-preview |

---

## 8. Frontend Changes

- **Default language**: Chinese (zh-CN)
- **Remove**: Market Insights dashboard, US stock components, credit display
- **Add**: Fund holdings page (from screenshot import), daily analysis trigger button, PDF upload for quarterly reports
- **Keep**: Chat interface, model settings, streaming responses
- **Simplify**: Auth to single-user login

---

## 9. Docker Compose (Simplified)

```yaml
services:
  backend:
    build: ./backend
    ports: ["8000:8000"]
    extra_hosts: ["host.docker.internal:host-gateway"]
    depends_on: [mongodb, redis]
  frontend:
    build: ./frontend
    ports: ["3000:3000"]
  mongodb:
    image: mongo:7
    ports: ["27017:27017"]
  redis:
    image: redis:7-alpine
    ports: ["6379:6379"]
```

No Langfuse, no ClickHouse, no MinIO, no PostgreSQL.

---

## 10. Milestones

### M0: Foundation (Day 1)
- [x] Write design spec (this document)
- [ ] Rebrand FinancialAgent → FundAgent (package names, titles, README)

### M1: Core Refactor (Days 2-5)
- [ ] LLM layer refactor — Agent Maestro multi-provider factory
- [ ] Delete unused modules (credit, complex auth, feedback, Alpaca, US sources, Langfuse, K8s)
- [ ] AkShare data source integration (fund NAV, rankings, holdings)
- [ ] Sub-agent rebuild for fund domain (5 fund-specific sub-agents)

### M2: Key Features (Days 6-9)
- [ ] Screenshot portfolio import (GPT-5.4 vision)
- [ ] Daily analysis orchestrator (manual trigger, buy/sell/hold output)
- [ ] Frontend rebuild (Chinese default, holdings page, screenshot upload, analysis trigger)

### M3: Advanced (Days 10-12)
- [ ] Quarterly report PDF interpreter (Gemini long context)
- [ ] 天天基金 friendly crawler
- [ ] Docker Compose simplification (remove unused services)

### Validation Criteria

**M1 complete when**: Backend starts, Agent Maestro LLM calls work for all 3 vendors, AkShare returns fund data, sub-agents produce fund analysis via chat.

**M2 complete when**: Screenshot upload extracts fund holdings, daily analysis produces buy/sell/hold for each fund, frontend shows holdings and analysis results.

**M3 complete when**: PDF upload extracts quarterly report insights, 天天基金 crawler fetches supplementary data, docker-compose.yml is minimal (4 services).

---

## 11. Configuration

### Settings (backend/src/core/config.py)

```python
class Settings(BaseSettings):
    # Agent Maestro
    agent_maestro_base_url: str = "http://localhost:23333"
    
    # Role → Model mapping (user-configurable via Settings UI)
    role_models: dict = DEFAULT_ROLE_MODELS
    
    # Data
    mongodb_url: str = "mongodb://localhost:27017"
    redis_url: str = "redis://localhost:6379"
    
    # Auth (simplified)
    secret_key: str = "change-me"
    default_username: str = "admin"
    default_password_hash: str = "..."
```

### Environment Variables (.env)

```env
AGENT_MAESTRO_BASE_URL=http://localhost:23333
MONGODB_URL=mongodb://mongodb:27017
REDIS_URL=redis://redis:6379
SECRET_KEY=your-secret-key
```

# API Performance Baseline

**Collected**: 2025-12-23
**Environment**: Production (https://klinecubic.cn)

---

## API Endpoint Inventory

### Router Registrations (from `backend/src/main.py`)

| Router | Prefix | Description |
|--------|--------|-------------|
| `health_router` | `/api` | Health checks |
| `admin_router` | `/api/admin` | Admin monitoring |
| `auth_router` | `/api/auth` | Authentication |
| `analysis_router` | `/api/analysis` | Technical analysis |
| `market_data_router` | `/api/market` | Market data |
| `chat_router` | `/api/chat` | Conversations |
| `portfolio_router` | `/api/portfolio` | Portfolio management |
| `watchlist_router` | `/api/watchlist` | Symbol tracking |
| `credits_router` | `/api/credits` | Credit economy |
| `llm_models_router` | `/api/llm-models` | Model selection |
| `feedback_router` | `/api/feedback` | Feedback platform |
| `insights_router` | `/api/insights` | Market insights |

---

## Response Time Measurements

### Production Health Endpoint

```
Endpoint: GET https://klinecubic.cn/api/health
Total Time: 220ms
Connect Time: 143ms
TTFB: 220ms
```

**Analysis**:
- 143ms is connection overhead (TLS handshake, network latency from China)
- 77ms actual backend processing
- Backend processing is acceptable

### Endpoint Categories by Expected Latency

| Category | Endpoints | Expected P95 | Notes |
|----------|-----------|--------------|-------|
| **Fast** (<100ms) | `/api/health`, `/api/credits/balance` | <100ms | Simple queries |
| **Medium** (100-500ms) | `/api/market/*`, `/api/portfolio/*` | <500ms | DB queries + caching |
| **Slow** (500ms-5s) | `/api/analysis/*`, `/api/insights/*` | <3s | Complex calculations |
| **Streaming** | `/api/chat/stream-react` | N/A (SSE) | LLM-dependent |

---

## Identified Bottlenecks

### High Priority

1. **Network Latency (143ms connect)**
   - Cause: Cross-region TLS handshake
   - Mitigation: CDN for static assets, keep-alive connections

### Medium Priority

2. **Streaming Endpoints**
   - `/api/chat/stream-react` - LLM processing
   - Need Langfuse traces to measure accurately

### Needs Data

3. **Analysis Endpoints** - Require production load testing
4. **Market Data Endpoints** - Need Alpha Vantage timing

---

## Recommendations

1. **Add Timing Middleware** - Log P50/P95/P99 for all endpoints
2. **Langfuse Integration** - Already enabled, need to export metrics
3. **Rate Limiting Check** - SlowAPI configured, verify impact

---

## Data Collection Method

```bash
# Production timing
curl -s -w "\nTotal: %{time_total}s\nConnect: %{time_connect}s\nTTFB: %{time_starttransfer}s\n" \
  https://klinecubic.cn/api/health
```

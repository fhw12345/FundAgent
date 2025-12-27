# Sprint Change Proposal: AI Sector Risk Trend Visualization

> **Created**: 2025-12-27
> **Status**: Pending Approval
> **Epic**: Market Insights Platform
> **Priority**: High

---

## 1. Executive Summary

### Issue Identified

The AI Sector Risk feature currently displays **point-in-time** metrics only. Users need:
- Historical trend visualization (30+ days)
- Fast AI tool access via cached data
- Consistent data access across all application features

### Recommended Solution

Build a **Data Manager Layer (DML)** as foundational infrastructure, then implement trend visualization and caching on top. This creates reusable patterns for all future insight categories.

### Impact

| Aspect | Change |
|--------|--------|
| **Epic Stories** | 6 → 11 (+5 new stories) |
| **Timeline** | +2 sprints |
| **Architecture** | New DML layer (foundational) |
| **Risk** | Low - incremental, testable |

---

## 2. Problem Statement

### Current State

```
User Request: "Show me the AI sector risk trend"

Current Flow:
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Frontend  │ ──► │   Backend   │ ──► │ Alpha Vantage│
│   (Chart)   │     │ (Calculate) │     │    (API)    │
└─────────────┘     └─────────────┘     └─────────────┘
                           │
                    15-30 seconds
                    (sequential calls)
                           │
                           ▼
                    Single point-in-time
                    (no history)
```

**Problems**:
1. No historical data persistence
2. Slow calculation (sequential API calls)
3. No caching for AI tools
4. Scattered data access (no single source of truth)
5. Duplicate API calls across features

### Desired State

```
User Request: "Show me the AI sector risk trend"

Desired Flow:
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Frontend  │ ──► │     DML     │ ──► │    Redis    │
│   (Chart)   │     │  (Manager)  │     │   (Cache)   │
└─────────────┘     └─────────────┘     └─────────────┘
                           │
                       < 100ms
                    (cache hit)
                           │
                           ▼
                    30-day trend
                    + today highlighted
```

---

## 3. Technical Analysis

### 3.1 Data Manager Layer (DML)

**Purpose**: Single source of truth for ALL data access

```
┌─────────────────────────────────────────────────────────────────┐
│                     APPLICATION LAYER                            │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐        │
│  │ Insights │  │  Charts  │  │ AI Tools │  │ Analysis │        │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘        │
│       └─────────────┴─────────────┴─────────────┘               │
│                            │                                     │
│                            ▼                                     │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │              DATA MANAGER LAYER (DML)                    │    │
│  │          *** SINGLE SOURCE OF TRUTH ***                  │    │
│  └─────────────────────────┬───────────────────────────────┘    │
│                            │                                     │
│            ┌───────────────┼───────────────┐                    │
│            ▼               ▼               ▼                    │
│       ┌────────┐     ┌──────────┐    ┌──────────┐              │
│       │ Redis  │     │ MongoDB  │    │  APIs    │              │
│       └────────┘     └──────────┘    └──────────┘              │
└─────────────────────────────────────────────────────────────────┘
```

**Key Principles**:
- All data access goes through `DataManager`
- Consistent cache key naming: `{domain}:{granularity}:{symbol}`
- Tiered caching: Hot (Redis) → Warm (MongoDB)
- No direct API calls outside DML

### 3.2 Cache Strategy

| Data Type | Granularity | Cache? | TTL | Key Pattern |
|-----------|-------------|--------|-----|-------------|
| OHLCV Bars | 1min-15min | ❌ No | - | - |
| OHLCV Bars | 30min-60min | ⚠️ Short | 5-15 min | `market:60min:AAPL` |
| OHLCV Bars | Daily+ | ✅ Yes | 1-4 hours | `market:daily:AAPL` |
| Treasury Yields | Daily | ✅ Yes | 1 hour | `macro:treasury:2y` |
| News Sentiment | Hourly | ✅ Yes | 1 hour | `sentiment:news:technology` |
| ETF Holdings | Daily | ✅ Yes | 24 hours | `etf:holdings:AIQ` |
| Computed Insights | Daily | ✅ Yes | 24 hours | `insights:ai_sector_risk:latest` |

### 3.3 Performance Optimization

**Before** (Sequential):
```python
for metric in metrics:
    result = await calculate_metric()  # 2-5 seconds each
# Total: 12-30 seconds
```

**After** (Parallel with shared data):
```python
# Phase 1: Pre-fetch all shared data (parallel)
shared_data = await asyncio.gather(
    fetch_daily_bars(ai_symbols),
    fetch_treasury_2y(),        # Fetched ONCE
    fetch_treasury_10y(),
    fetch_news_sentiment(),
    fetch_ipo_calendar(),
)

# Phase 2: Calculate metrics (parallel)
results = await asyncio.gather(
    calculate_ai_price_anomaly(shared_data),
    calculate_news_sentiment(shared_data),
    calculate_yield_curve(shared_data),      # Uses shared treasury_2y
    calculate_fed_expectations(shared_data), # Uses shared treasury_2y
    ...
)
# Total: 3-5 seconds
```

### 3.4 Database Schema Addition

**New Collection**: `insight_snapshots`

```javascript
// Collection: insight_snapshots
{
  "_id": ObjectId,
  "category_id": "ai_sector_risk",
  "date": ISODate("2025-12-27"),
  "composite_score": 72.5,
  "composite_status": "elevated",
  "metrics": {
    "ai_price_anomaly": { "score": 85, "status": "high" },
    "news_sentiment": { "score": 78, "status": "elevated" },
    "smart_money_flow": { "score": 52, "status": "normal" },
    "ipo_heat": { "score": 35, "status": "normal" },
    "yield_curve": { "score": 70, "status": "elevated" },
    "fed_expectations": { "score": 62, "status": "elevated" }
  },
  "created_at": ISODate
}

// Index for trend queries
db.insight_snapshots.createIndex({ "category_id": 1, "date": -1 })
```

---

## 4. Proposed Stories

### Story 7: Data Manager Layer (DML) 🏗️

**Goal**: Create single source of truth for all data access

**Deliverables**:
```
backend/src/services/data_manager/
├── __init__.py
├── manager.py          # DataManager class
├── cache.py            # Redis operations
├── keys.py             # Naming conventions
└── types.py            # OHLCVData, TrendPoint, etc.
```

**Acceptance Criteria**:
- [ ] `DataManager.get_ohlcv()` returns cached data for daily+ granularity
- [ ] `DataManager.get_ohlcv()` returns fresh data for intraday (no cache)
- [ ] Key convention: `market:{granularity}:{symbol}` consistently applied
- [ ] Existing AI tools migrated to use DML
- [ ] Existing chart APIs migrated to use DML
- [ ] `AlphaVantageMarketDataService` marked deprecated
- [ ] No direct Alpha Vantage calls outside DML

**Effort**: 3-4 days

---

### Story 8: Daily Snapshot Cron Job ⏰

**Goal**: Automated daily data collection with optimized performance

**Deliverables**:
- K8s CronJob manifest: `.pipeline/k8s/base/insights-cron.yaml`
- Parallel calculation with `asyncio.gather()`
- Pre-fetch shared data pattern
- MongoDB snapshot persistence
- Redis cache update

**Acceptance Criteria**:
- [ ] Cron runs daily at 9:30 AM ET (14:30 UTC)
- [ ] All 6 metrics calculated in parallel (< 10 seconds total)
- [ ] Treasury 2Y fetched ONCE (shared by yield_curve + fed_expectations)
- [ ] Snapshot saved to `insight_snapshots` collection
- [ ] Redis key `insights:ai_sector_risk:latest` updated with 24hr TTL
- [ ] Graceful handling of partial API failures

**Effort**: 2-3 days

---

### Story 9: Trend API Endpoints 📈

**Goal**: API endpoints for historical trend data

**Deliverables**:
- `GET /api/insights/{category}/trend?days=30`
- `TrendDataPoint` response model
- MongoDB date range query

**API Response**:
```json
{
  "category_id": "ai_sector_risk",
  "days": 30,
  "trend": [
    {"date": "2025-12-27", "composite_score": 72.5, "status": "elevated"},
    {"date": "2025-12-26", "composite_score": 70.2, "status": "elevated"}
  ],
  "metrics": {
    "ai_price_anomaly": [
      {"date": "2025-12-27", "score": 85, "status": "high"}
    ]
  }
}
```

**Acceptance Criteria**:
- [ ] Endpoint returns 30 days by default
- [ ] Supports `?days=7|14|30|60|90` parameter
- [ ] Each datapoint includes date, score, status
- [ ] Includes both composite and individual metric trends
- [ ] Returns empty array gracefully if < 30 days of data

**Effort**: 1-2 days

---

### Story 10: Frontend Trend Visualization 📊

**Goal**: Interactive trend display with swipe and scale

**Deliverables**:
```
frontend/src/components/insights/
├── TrendSparkline.tsx      # Sparkline chart component
├── TrendChart.tsx          # Full trend chart with zoom
├── SwipeContainer.tsx      # Swipe gesture handler
└── hooks/useInsightTrend.ts
```

**UX Requirements**:
- Default: 30 days displayed
- Swipe left: Load more history (60, 90 days)
- Scale/zoom: Pinch to show more/fewer datapoints
- Today: Highlighted with different color/marker

**Acceptance Criteria**:
- [ ] Sparkline shows 30-day trend in metric cards
- [ ] Today's datapoint highlighted (different color/marker)
- [ ] Swipe left loads more history (60, 90 days)
- [ ] Pinch/zoom scales chart to show more/fewer datapoints
- [ ] Loading skeleton while fetching
- [ ] Responsive on mobile

**Effort**: 3-4 days

---

### Story 11: AI Tools Redis Integration 🤖

**Goal**: Fast AI tool access via DML cache

**Deliverables**:
- Update `insights_tools.py` to use DML
- New `get_insight_trend` tool
- Response time < 100ms for cached data

**New Tool**:
```python
@tool
async def get_insight_trend(category_id: str, days: int = 30) -> str:
    """
    Get historical trend for a market insight category.

    Shows how the composite score and individual metrics
    have changed over the specified number of days.

    Args:
        category_id: Category identifier (e.g., "ai_sector_risk")
        days: Number of days of history (default: 30, max: 90)

    Returns:
        Trend analysis with score changes and patterns
    """
```

**Acceptance Criteria**:
- [ ] `get_insight_category()` reads from Redis (no API calls)
- [ ] `get_insight_trend()` returns 30-day history
- [ ] Tool response time < 100ms when cached
- [ ] Graceful fallback if cache miss (trigger calculation)

**Effort**: 1-2 days

---

## 5. Artifact Updates Required

| Artifact | Change | Priority |
|----------|--------|----------|
| `docs/epics/market-insights-platform.md` | Add Stories 7-11 | High |
| `docs/architecture/database-schema.md` | Add `insight_snapshots` collection | High |
| `frontend/src/types/insights.ts` | Add `TrendDataPoint` interface | High |
| `backend/src/api/schemas/insights_models.py` | Add trend response models | High |
| `.pipeline/k8s/base/insights-cron.yaml` | New CronJob manifest | High |

---

## 6. Timeline & Dependencies

```
Week 1:
├── Story 7: DML Foundation (3-4 days)
│   └── Blocks: All other stories

Week 2:
├── Story 8: Cron Job (2-3 days)
│   └── Depends: Story 7
├── Story 11: AI Tools (1-2 days)
│   └── Depends: Story 7, 8

Week 3:
├── Story 9: Trend API (1-2 days)
│   └── Depends: Story 7, 8
├── Story 10: Frontend (3-4 days)
│   └── Depends: Story 9
```

**Total Estimated Duration**: ~2 sprints (12-15 working days)

---

## 7. Verification Plan

### Story 7 (DML) Verification
```bash
# Cache hit test
redis-cli GET "market:daily:AAPL" | jq 'length'

# No bypass check
grep -r "AlphaVantageMarketDataService" backend/src/ | grep -v "deprecated"
# Expected: 0 matches
```

### Story 8 (Cron) Verification
```bash
# Manual trigger
kubectl create job insights-manual --from=cronjob/insights-cron

# Check MongoDB
mongosh --eval "db.insight_snapshots.findOne({date: ISODate('2025-12-27')})"

# Check Redis
redis-cli GET "insights:ai_sector_risk:latest" | jq .composite_score

# Data consistency
REDIS=$(redis-cli GET "insights:ai_sector_risk:latest" | jq .composite_score)
MONGO=$(mongosh --eval "db.insight_snapshots.find().sort({date:-1}).limit(1)" | jq .composite_score)
[ "$REDIS" == "$MONGO" ] && echo "✅ Consistent" || echo "❌ Mismatch"
```

### Story 9-10 (Trend) Verification
```bash
# API test
curl "/api/insights/ai_sector_risk/trend?days=30" | jq 'length'
# Expected: 30

# Frontend: Visual verification of sparkline + swipe behavior
```

### Story 11 (AI Tools) Verification
```bash
# Performance test
time curl -X POST /api/chat -d '{"message": "What is the AI sector risk?"}'
# Expected: < 2 seconds (vs 15-30 seconds without cache)
```

---

## 8. Rollback Plan

Each story is independently deployable and reversible:

| Story | Rollback Action |
|-------|-----------------|
| Story 7 | Revert DML, restore direct service calls |
| Story 8 | Delete CronJob, no data collection |
| Story 9 | Remove trend endpoint, 404 on /trend |
| Story 10 | Hide sparkline component, show static gauge |
| Story 11 | Revert tools to real-time calculation |

---

## 9. Approval

- [ ] **Product Owner**: Approve scope and priority
- [ ] **Tech Lead**: Approve architecture (DML pattern)
- [ ] **Scrum Master**: Update sprint backlog

---

## 10. Next Steps

Upon approval:
1. Update epic document with Stories 7-11
2. Create story tickets in backlog
3. Begin Story 7 (DML) implementation
4. Schedule daily standups to track progress

---

*Generated by Scrum Master Agent*
*Sprint Change Proposal v1.0*

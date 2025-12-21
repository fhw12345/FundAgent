# Epic: Market Insights Platform

> **Epic Type**: Brownfield Enhancement
> **Created**: 2025-12-20
> **Status**: Draft
> **Estimated Stories**: 6

---

## Epic Goal

Create an extensible **Market Insights Platform** - a dedicated page (`/insights`) for visualizing customized financial metrics across multiple categories. The platform emphasizes **explainability** for both human users and AI agents, with a pluggable architecture that starts with "AI Sector Risk" and can expand to additional categories (Sector Rotation, Macro Environment, Market Breadth, etc.).

---

## Design Principles

| Principle | Implementation |
|-----------|----------------|
| **Explainability First** | Every metric has plain-language explanation, methodology, and historical context |
| **Category Extensibility** | New metric categories can be added without changing core architecture |
| **AI-Native** | Every visualization is "talkable" - LLM can interpret and explain to users |
| **Performance** | Aggressive caching with incremental updates; <3s initial load |
| **Clear Labeling** | Category hierarchy and metric names are self-documenting |

---

## Existing System Context

| Aspect | Current State |
|--------|---------------|
| **Frontend Charting** | `lightweight-charts` v4.1.3 (TradingView) |
| **Backend Services** | `src/services/market_data/` with macro endpoints |
| **Alpha Vantage** | Premium key (75 calls/min), existing service abstraction |
| **Caching** | Redis with TTL strategies in `cache_utils.py` |
| **Agent Tools** | LangChain tools in `agent/tools/alpha_vantage/` |
| **Pages** | React Router at `src/pages/` |

---

## Architecture Overview

### Page Structure

```
/insights
│
├── [Header: "Market Insights" + Last Updated + Refresh Button]
│
├── [Category Tabs]
│   ├── 🎯 AI Sector Risk (v1 - This Epic)
│   ├── 🏭 Sector Rotation (Future)
│   ├── 🌍 Macro Environment (Future)
│   └── 📈 Market Breadth (Future)
│
├── [Composite Score Card]
│   └── Large gauge with weighted score + interpretation
│
├── [Metrics Grid]
│   └── 2x3 grid of individual metric cards
│
└── [Footer: Data Sources + Methodology Link]
```

### Metric Card Design (Explanation-First)

```
┌─────────────────────────────────────────────────────────────────┐
│  📊 AI Price Anomaly                              Score: 85/100 │
│  ───────────────────────────────────────────────────────────────│
│                                                                 │
│  [════════════════════════════════●══════]                      │
│  0          25          50         75        100                │
│  ▲ Accumulation    ▲ Normal    ▲ Caution   ▲ Euphoria          │
│                                                                 │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │ 💡 WHAT THIS MEANS                                        │ │
│  │                                                           │ │
│  │ AI stocks (NVDA, MSFT, AMD, PLTR) are trading 2.3        │ │
│  │ standard deviations above their 200-day moving average.  │ │
│  │ This level of extension historically precedes            │ │
│  │ corrections 70% of the time within 30 days.              │ │
│  └───────────────────────────────────────────────────────────┘ │
│                                                                 │
│  [📖 Methodology]  [📈 History]  [🤖 Ask AI About This]        │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Data Model

```typescript
// Category Definition
interface InsightCategory {
  id: string;                    // "ai_sector_risk"
  name: string;                  // "AI Sector Risk"
  icon: string;                  // "🎯"
  description: string;           // "Measures bubble risk..."
  metrics: InsightMetric[];
  compositeWeights: Record<string, number>;
}

// Individual Metric
interface InsightMetric {
  id: string;                    // "ai_price_anomaly"
  name: string;                  // "AI Price Anomaly"
  score: number;                 // 0-100
  status: "low" | "normal" | "elevated" | "high";
  explanation: MetricExplanation;
  dataSources: string[];         // ["TIME_SERIES_DAILY"]
  lastUpdated: string;           // ISO 8601
}

// Explanation (Core UX Feature)
interface MetricExplanation {
  summary: string;               // One-liner for quick scan
  detail: string;                // 2-3 sentences with specifics
  methodology: string;           // How it's calculated
  formula?: string;              // Optional math formula
  historicalContext: string;     // "Last time this high..."
  actionableInsight: string;     // "Consider..."
  thresholds: {                  // For visualization
    low: number;                 // 0-25
    normal: number;              // 25-50
    elevated: number;            // 50-75
    high: number;                // 75-100
  };
}
```

### API Structure

```
/api/insights
│
├── GET /categories
│   └── Returns: List of available categories with metadata
│
├── GET /{category_id}
│   └── Returns: All metrics for category + composite score
│
├── GET /{category_id}/{metric_id}
│   └── Returns: Single metric with full explanation
│
├── GET /{category_id}/composite
│   └── Returns: Weighted composite with breakdown
│
└── POST /{category_id}/refresh
    └── Forces cache invalidation and recalculation
```

---

## First Category: AI Sector Risk

### Metrics Definition

| # | Metric ID | Name | Data Source | Calculation | Weight |
|---|-----------|------|-------------|-------------|--------|
| 1 | `ai_price_anomaly` | AI Price Anomaly | TIME_SERIES_DAILY | Z-score of NVDA,MSFT,AMD,PLTR vs 200 SMA | 20% |
| 2 | `news_sentiment` | News Sentiment | NEWS_SENTIMENT | Normalized avg sentiment (-0.35 to +0.35 → 0-100) | 20% |
| 3 | `smart_money_flow` | Smart Money Flow | TIME_SERIES_INTRADAY | First hour vs last hour volume divergence | 20% |
| 4 | `ipo_heat` | IPO Heat | IPO_CALENDAR | Count of IPOs in next 90 days | 10% |
| 5 | `yield_curve` | Yield Curve | TREASURY_YIELD | 10Y-2Y spread (loose money indicator) | 15% |
| 6 | `fed_expectations` | Fed Expectations | TREASURY_YIELD | 2Y yield slope over 20 days | 15% |

### Interpretation Zones

| Score Range | Status | Color | Meaning |
|-------------|--------|-------|---------|
| 0-25 | Low | 🟢 Green | Fear / Accumulation Zone |
| 25-50 | Normal | 🔵 Blue | Normal Bull Market |
| 50-75 | Elevated | 🟡 Yellow | Caution / Late Cycle |
| 75-100 | High | 🔴 Red | Euphoria / Bubble Risk |

---

## Stories

### Story 1: Backend - Insights Service Architecture

**Goal**: Create extensible service layer for insights platform

**Deliverables**:
- `src/services/insights/` module structure:
  ```
  insights/
  ├── __init__.py
  ├── base.py              # Abstract InsightCategory class
  ├── models.py            # Pydantic models for metrics/explanations
  ├── registry.py          # Category registry (plugin system)
  └── categories/
      └── ai_sector_risk.py  # First category implementation
  ```
- Category registry pattern for adding new categories
- Explanation generation for each metric
- Redis caching with category-level TTL

**Acceptance Criteria**:
- [ ] Abstract base class defines metric interface
- [ ] New categories can be added by creating single file
- [ ] All metrics return full explanation objects
- [ ] Registry auto-discovers categories on startup

---

### Story 2: Backend - AI Sector Risk Implementation

**Goal**: Implement all 6 metrics for the first category

**Deliverables**:
- Add missing Alpha Vantage endpoints:
  - `TREASURY_YIELD` (10Y, 2Y) in `market_data/macro.py`
  - `IPO_CALENDAR` (CSV parsing) in `market_data/macro.py`
- Implement calculation logic:
  - Z-score calculation with 200 SMA
  - Sentiment normalization
  - Intraday volume divergence detection
  - IPO count with date filtering
  - Yield spread and slope calculations
- Explanation templates for each metric
- Rate limiter integration (queue for free tier)

**Acceptance Criteria**:
- [ ] All 6 metrics return valid 0-100 scores
- [ ] Each metric has complete explanation object
- [ ] Rate limiting prevents API quota exhaustion
- [ ] Graceful degradation on partial API failure

---

### Story 3: Backend - Insights API Endpoints

**Goal**: Create REST API for frontend consumption

**Deliverables**:
- `src/api/insights.py` router:
  - `GET /api/insights/categories`
  - `GET /api/insights/{category_id}`
  - `GET /api/insights/{category_id}/{metric_id}`
  - `GET /api/insights/{category_id}/composite`
  - `POST /api/insights/{category_id}/refresh`
- Response models with full explanation schemas
- OpenAPI documentation with examples
- Error responses with helpful messages

**Acceptance Criteria**:
- [ ] All endpoints return proper JSON with explanations
- [ ] Swagger docs show example responses
- [ ] 404 for invalid category/metric IDs
- [ ] Refresh endpoint invalidates cache correctly

---

### Story 4: Frontend - Insights Page & Category System

**Goal**: Create the `/insights` page with category navigation

**Deliverables**:
- `src/pages/InsightsPage.tsx` - Main page component
- `src/components/insights/` module:
  ```
  insights/
  ├── CategoryTabs.tsx        # Tab navigation
  ├── CompositeScoreCard.tsx  # Large central gauge
  ├── MetricsGrid.tsx         # 2x3 grid layout
  ├── MetricCard.tsx          # Individual metric with explanation
  ├── ScoreGauge.tsx          # SVG arc gauge component
  ├── ExplanationPanel.tsx    # Expandable explanation section
  └── MethodologyModal.tsx    # Full methodology popup
  ```
- Route configuration in `App.tsx`
- Navigation link in header/sidebar
- Responsive layout (mobile: stack, desktop: grid)

**Acceptance Criteria**:
- [ ] Page loads at `/insights` route
- [ ] Category tabs switch content
- [ ] All 6 metrics display with gauges
- [ ] Explanations visible by default (not hidden)
- [ ] Mobile responsive layout works

---

### Story 5: Frontend - Explanation UX & Interactivity

**Goal**: Rich explanation experience with AI integration

**Deliverables**:
- Explanation panel with sections:
  - Summary (always visible)
  - Methodology (expandable)
  - Historical context (expandable)
  - Actionable insight (highlighted)
- "Ask AI About This" button:
  - Opens chat panel with pre-loaded context
  - Message template: "Explain the {metric_name} indicator showing {score}"
- History sparkline (last 30 days trend)
- Threshold markers on gauge
- Loading/skeleton states
- Error states with retry

**Acceptance Criteria**:
- [ ] All explanation sections render correctly
- [ ] "Ask AI" opens chat with correct context
- [ ] Sparkline shows 30-day history
- [ ] Threshold zones visually distinguished
- [ ] Loading states don't flash

---

### Story 6: LLM Integration - Talkable Insights

**Goal**: Enable LLM to interpret and discuss any insight metric

**Deliverables**:
- `src/agent/tools/insights_tools.py`:
  - `get_market_insights` - Overview of all categories
  - `get_category_insights` - All metrics for a category
  - `explain_insight_metric` - Deep dive on specific metric
  - `compare_insight_history` - Trend analysis
- Response formatters with rich markdown:
  - Score + status emoji
  - Explanation in conversational tone
  - Historical comparison
  - Actionable recommendations
- Tool registration in ReAct agent
- Example prompts for CLAUDE.md

**Acceptance Criteria**:
- [ ] "What's the AI bubble risk?" returns formatted insights
- [ ] "Explain the yield curve indicator" gives methodology
- [ ] "How has sentiment changed this week?" gives trend
- [ ] Tool responses cached appropriately

---

## Future Categories (Backlog)

These categories can be added by implementing the `InsightCategory` base class:

| Category | Metrics (Examples) | Priority |
|----------|-------------------|----------|
| **Sector Rotation** | Tech/Value ratio, Cyclical/Defensive, Growth/Value | Medium |
| **Macro Environment** | Inflation trend, GDP growth, Dollar index | Medium |
| **Market Breadth** | Advance/Decline, New Highs/Lows, McClellan | Low |
| **Volatility Regime** | VIX term structure, Put/Call ratio, SKEW | Low |
| **Credit Conditions** | HY spreads, TED spread, Bank lending | Low |

---

## Technical Architecture

### Caching Strategy

```
┌─────────────────────────────────────────────────────────────┐
│                     CACHING LAYERS                          │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Layer 1: Raw API Data (Alpha Vantage)                      │
│  ├── Price data: 5 min TTL                                  │
│  ├── News sentiment: 1 hour TTL                             │
│  ├── IPO calendar: 24 hour TTL                              │
│  └── Treasury yields: 1 hour TTL                            │
│                                                             │
│  Layer 2: Calculated Metrics                                │
│  ├── Individual metrics: 30 min TTL                         │
│  └── Composite scores: 30 min TTL                           │
│                                                             │
│  Layer 3: Historical Snapshots (MongoDB)                    │
│  └── Daily snapshots for trend analysis                     │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### Database Schema

```javascript
// Collection: insight_snapshots
{
  "_id": ObjectId,
  "category_id": "ai_sector_risk",
  "date": ISODate("2025-12-20"),
  "composite_score": 72.5,
  "metrics": {
    "ai_price_anomaly": { "score": 85, "status": "high" },
    "news_sentiment": { "score": 78, "status": "elevated" },
    // ... other metrics
  },
  "created_at": ISODate
}

// Index for efficient queries
db.insight_snapshots.createIndex({ "category_id": 1, "date": -1 })
```

---

## Compatibility Requirements

- [x] Existing APIs remain unchanged
- [x] New MongoDB collection (additive)
- [x] UI follows existing TailwindCSS patterns
- [x] No changes to existing pages
- [x] Agent tools extend existing pattern

---

## Risk Mitigation

| Risk | Mitigation | Rollback |
|------|------------|----------|
| **API Rate Limits** | Queue with delay, aggressive caching | Use cached data only |
| **Calculation Errors** | Unit tests, validation | Show "unavailable" |
| **Complex UX** | User testing, iterative design | Simplify explanations |
| **Performance** | Lazy loading, skeleton states | Reduce metrics shown |

---

## Definition of Done

- [ ] All 6 stories completed with acceptance criteria
- [ ] Insights page accessible at `/insights`
- [ ] All 6 AI Risk metrics functional
- [ ] Explanations clear and helpful
- [ ] LLM can discuss any metric
- [ ] Documentation complete
- [ ] No regression in existing features

---

## Technical References

| Reference | Location |
|-----------|----------|
| Alpha Vantage Service | `backend/src/services/market_data/` |
| Lightweight Charts | `frontend/src/components/chart/` |
| Agent Tools Pattern | `backend/src/agent/tools/alpha_vantage/` |
| Cache Utils | `backend/src/core/utils/cache_utils.py` |
| Page Components | `frontend/src/pages/` |
| API Router Pattern | `backend/src/api/` |

---

## Handoff to Story Manager

**Key considerations for story development:**

1. This is an **extensible platform** - architecture must support future categories
2. **Explainability is core UX** - not an afterthought
3. **AI integration** - every metric must be "talkable"
4. Follow existing patterns in `market_data/` and `agent/tools/`
5. Each story should verify no regression in existing features

The epic delivers a **Market Insights Platform** starting with AI Sector Risk, designed for expansion to additional categories over time.

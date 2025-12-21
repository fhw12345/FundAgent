# Epic: Meitou AI Risk Model Dashboard

> **Epic Type**: Brownfield Enhancement
> **Created**: 2025-12-20
> **Status**: Draft
> **Estimated Stories**: 5

---

## Epic Goal

Create a dedicated page for visualizing the **Meitou AI Risk Model** - a composite index measuring AI sector bubble risk using 6 quantitative indicators from Alpha Vantage data. The visualizations must be "talkable" - each can be interpreted by the LLM agent for conversational analysis.

---

## Existing System Context

| Aspect | Current State |
|--------|---------------|
| **Frontend Charting** | `lightweight-charts` v4.1.3 (TradingView) |
| **Backend Services** | `src/services/market_data/` with macro endpoints (GDP, CPI, Inflation) |
| **Alpha Vantage** | Premium key (75 calls/min), existing service abstraction |
| **Caching** | Redis with TTL strategies in `cache_utils.py` |
| **Agent Tools** | LangChain tools in `agent/tools/alpha_vantage/` |
| **Navigation** | React Router with pages in `src/pages/` |

**Missing Components**:
- TREASURY_YIELD endpoint (2Y, 10Y)
- IPO_CALENDAR endpoint
- Intraday volume analysis for Smart Money Flow
- Gauge/meter visualization components
- Composite risk index calculation

---

## Enhancement Details

### 6 Indicators to Implement

| # | Indicator | Data Source | Visualization | Risk Logic |
|---|-----------|-------------|---------------|------------|
| 1 | **AI Price Anomaly** | TIME_SERIES_DAILY (NVDA, MSFT, AMD, PLTR) | Gauge (0-100) | Z-score > 2 = High Risk |
| 2 | **News Sentiment** | NEWS_SENTIMENT | Gauge + Trend | Euphoria (>75) = High Risk |
| 3 | **Smart Money Flow** | TIME_SERIES_INTRADAY (60min) | Divergence Indicator | Retail↑ + Pro↓ = High Risk |
| 4 | **IPO Heat** | IPO_CALENDAR | Count + Bar | >20 IPOs/90d = Overheated |
| 5 | **Yield Curve** | TREASURY_YIELD (10Y, 2Y) | Spread Chart | Steep (>1.5%) = Loose Money |
| 6 | **Fed Expectations** | TREASURY_YIELD (2Y history) | Slope Indicator | Rapid drop = Rate Cut Hopes |

### Composite Index Formula

```
FINAL_INDEX = (
  AI_Price_Anomaly × 0.20 +
  News_Sentiment × 0.20 +
  Smart_Money_Flow × 0.20 +
  IPO_Heat × 0.10 +
  Yield_Curve × 0.15 +
  Fed_Expectations × 0.15
)
```

### Interpretation Zones

| Score | Zone | Interpretation |
|-------|------|----------------|
| 0-40 | Green | Accumulation Zone (Fear) |
| 40-70 | Yellow | Normal Bull Market |
| 70-100 | Red | Euphoria / Bubble Risk |

---

## Stories

### Story 1: Backend - AI Risk Model Service & API

**Goal**: Create service and API endpoints for calculating the 6 indicators

**Tasks**:
- Add `TREASURY_YIELD` method to `market_data/macro.py`
- Add `IPO_CALENDAR` method (CSV parsing with date filtering)
- Create `src/services/ai_risk_model.py` with:
  - `calculate_ai_basket_zscore()` - Z-score of AI stocks vs 200 SMA
  - `calculate_sentiment_score()` - NEWS_SENTIMENT normalization
  - `calculate_smart_money_flow()` - Intraday volume divergence
  - `calculate_ipo_heat()` - IPO count in 90-day window
  - `calculate_yield_curve()` - 10Y-2Y spread analysis
  - `calculate_fed_expectations()` - 2Y yield slope (20-day)
- Create `src/api/risk_model.py` router with:
  - `GET /api/risk-model/indicators` - All 6 indicators
  - `GET /api/risk-model/composite` - Final index with weights
- Implement Redis caching (30-min TTL for composite)

**Acceptance Criteria**:
- [ ] All 6 indicators return valid 0-100 scores
- [ ] Rate limiting handled (12s between calls for free tier)
- [ ] Redis caching reduces API calls by 80%+
- [ ] Error handling for API failures (graceful degradation)

---

### Story 2: Frontend - Risk Model Dashboard Page

**Goal**: Create dedicated page with gauge visualizations

**Tasks**:
- Create `src/pages/RiskModelPage.tsx`
- Create gauge component using SVG/Canvas:
  - Arc meter with color zones (green/yellow/red)
  - Current value pointer with animation
  - Min/max labels and current score
- Create `src/components/risk-model/`:
  - `RiskGauge.tsx` - Reusable gauge component
  - `RiskIndicatorCard.tsx` - Card wrapper with title/description
  - `CompositeRiskMeter.tsx` - Large central gauge
  - `IndicatorGrid.tsx` - 6-indicator layout
- Add route to `App.tsx`: `/risk-model`
- Add navigation link to sidebar/header

**Acceptance Criteria**:
- [ ] Page loads with 6 indicator gauges + 1 composite
- [ ] Gauges animate on data load
- [ ] Color zones match interpretation (green/yellow/red)
- [ ] Responsive layout (mobile + desktop)
- [ ] Loading/error states handled

---

### Story 3: Performance - Incremental Data & Caching

**Goal**: Optimize data fetching and enable incremental updates

**Tasks**:
- Create MongoDB collection `risk_model_snapshots`:
  - Store daily indicator snapshots
  - Enable historical trend visualization
- Implement incremental calculation:
  - Check cache for recent calculation (< 30 min)
  - Only fetch changed data (intraday, news)
  - Reuse cached static data (GDP, baseline stats)
- Add background calculation option:
  - Optional CronJob for pre-calculation
  - Endpoint to trigger manual refresh
- Frontend: Add refresh button with rate limit indicator

**Acceptance Criteria**:
- [ ] Initial load completes in < 5 seconds
- [ ] Subsequent loads use cache (< 1 second)
- [ ] Historical snapshots stored daily
- [ ] Memory usage stable under repeated refreshes

---

### Story 4: LLM Integration - Talkable Visualizations

**Goal**: Enable LLM agent to interpret and discuss risk metrics

**Tasks**:
- Create `src/agent/tools/risk_model_tools.py`:
  - `get_ai_risk_assessment` - Returns structured markdown
  - `explain_risk_indicator` - Explains specific indicator
  - `compare_historical_risk` - Trend analysis
- Create response formatter for rich markdown output:
  - Include indicator values and interpretations
  - Add actionable insights based on thresholds
  - Format for conversational response
- Register tools with ReAct agent
- Add prompts to CLAUDE.md for risk model queries

**Acceptance Criteria**:
- [ ] LLM can answer "What's the current AI bubble risk?"
- [ ] LLM can explain individual indicators
- [ ] Responses include specific values and interpretation
- [ ] Tool caching prevents redundant API calls

---

### Story 5: Algorithm Validation & Testing

**Goal**: Ensure calculation accuracy and API reliability

**Tasks**:
- Create unit tests for each indicator calculation:
  - `test_ai_risk_model.py` with mocked API responses
  - Edge case handling (missing data, API errors)
  - Z-score calculation validation
- Add Alpha Vantage API health check:
  - Validate API key on startup
  - Check rate limit status
  - Graceful degradation on quota exhaustion
- Create integration tests:
  - End-to-end API test with real data (staging only)
  - Frontend component tests with mock data
- Document algorithm in `docs/features/ai-risk-model.md`

**Acceptance Criteria**:
- [ ] 90%+ code coverage for risk model service
- [ ] API health check runs on startup
- [ ] Rate limit errors handled gracefully
- [ ] Algorithm documented with formulas

---

## Compatibility Requirements

- [x] Existing APIs remain unchanged
- [x] Database schema changes are additive (new collection)
- [x] UI follows existing TailwindCSS patterns
- [x] Performance impact minimal (cached calculations)

---

## Risk Mitigation

| Risk | Mitigation | Rollback |
|------|------------|----------|
| **Alpha Vantage Rate Limits** | Implement rate limiter with queue | Disable real-time, use cached data |
| **Calculation Errors** | Unit tests with known datasets | Show "unavailable" instead of wrong data |
| **Frontend Performance** | Lazy load gauge components | Remove animations if slow |
| **LLM Misinterpretation** | Structured tool outputs | Disable tool if unreliable |

---

## Definition of Done

- [ ] All 5 stories completed with acceptance criteria met
- [ ] Existing functionality verified through testing
- [ ] Integration points working correctly
- [ ] Documentation updated (feature spec + API docs)
- [ ] No regression in existing features
- [ ] Code reviewed and merged to main

---

## Technical References

| Reference | Location |
|-----------|----------|
| Alpha Vantage Service | `backend/src/services/market_data/` |
| Lightweight Charts | `frontend/src/components/chart/` |
| Agent Tools Pattern | `backend/src/agent/tools/alpha_vantage/` |
| Cache Utils | `backend/src/core/utils/cache_utils.py` |
| API Router Pattern | `backend/src/api/analysis.py` |

---

## Handoff Notes

**For Story Manager (SM):**

Please develop detailed user stories for this brownfield epic. Key considerations:

- This is an enhancement to an existing Financial Agent platform (Python/FastAPI + React/TypeScript)
- Integration points: Alpha Vantage API, Redis cache, LangGraph agent
- Existing patterns to follow: market_data service structure, lightweight-charts usage
- Critical compatibility: Must not affect existing analysis features

Each story should include verification that existing functionality remains intact.

The epic should maintain system integrity while delivering **AI market bubble risk assessment capabilities**.

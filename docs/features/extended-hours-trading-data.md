# Feature: Extended Hours Trading Data (Pre-Market & After-Hours)

> **Status**: Draft
> **Created**: 2025-10-30
> **Last Updated**: 2025-10-30
> **Owner**: Financial Agent Team

## Context

Active traders need access to pre-market and after-hours trading data to make informed decisions outside regular trading hours (9:30 AM - 4:00 PM ET). Currently, KlineMatrix only shows regular market hours data.

**User Story**:
As an active trader, I want to view pre-market and after-hours price movements, so that I can react to overnight news and earnings announcements before the market opens.

**Background**:
- Current implementation uses yfinance (Yahoo Finance), which only provides regular hours data
- Trading sessions:
  - **Pre-Market**: 4:00 AM - 9:30 AM ET
  - **Regular Hours**: 9:30 AM - 4:00 PM ET
  - **After-Hours**: 4:00 PM - 8:00 PM ET
- User feedback: "要不要考虑加入盘前/盘后的数据" (Should we add pre/post-market data?)

**Related Features**:
- Market Data API (`/api/market_data.py`)
- Chart Panel (`ChartPanel.tsx`)
- Ticker Data Service (`ticker_data_service.py`)

---

## Problem Statement

**Current Limitations**:
1. ❌ No visibility into pre-market price movements (earnings reports, news)
2. ❌ No after-hours data (earnings calls, analyst upgrades/downgrades)
3. ❌ Incomplete picture of stock volatility and momentum
4. ❌ Traders cannot identify gap-up/gap-down opportunities

**Impact**:
- Users miss critical trading signals from extended hours
- Cannot plan entry/exit strategies around pre-market moves
- Competitive disadvantage vs. platforms with extended hours data

---

## Proposed Solution

### High-Level Approach

Add extended hours trading data by integrating **Alpha Vantage API** as a secondary data source alongside yfinance. Provide session-based filtering in the UI to toggle between All/Pre-Market/Regular/After-Hours.

**Key Components**:
1. **Data Provider**: Alpha Vantage Intraday API (extended hours enabled)
2. **Backend Service**: New `ExtendedHoursDataService`
3. **API Endpoint**: `GET /api/market/price/{symbol}/extended`
4. **Session Splitter**: Classify data by time into 3 sessions
5. **Frontend UI**: Session toggle buttons above chart
6. **Chart Rendering**: Color-coded candlesticks by session

### Technical Architecture

```
User Browser
    ↓ (Request AAPL with extended hours)
Frontend ChartPanel.tsx
    ↓ (GET /api/market/price/AAPL/extended?interval=5min)
Backend Market Data API (/api/market_data.py)
    ↓ (Call ExtendedHoursDataService)
Extended Hours Service (/core/data/extended_hours_service.py)
    ↓ (Fetch from Alpha Vantage)
Alpha Vantage API (TIME_SERIES_INTRADAY + extended_hours=true)
    ↓ (Return raw data)
Session Splitter (_split_by_session)
    ↓ (Classify by time)
Response: { pre_market: [...], regular: [...], after_hours: [...] }
    ↓ (Render chart)
Frontend Chart (color-coded by session)
```

### Data Flow

1. **Fetch Phase**:
   - User searches for "AAPL" → Frontend requests extended hours data
   - Backend calls Alpha Vantage with `extended_hours=true`
   - Receives intraday data with timestamps

2. **Processing Phase**:
   - Backend splits data by session based on Eastern Time:
     - 04:00-09:30 → Pre-Market
     - 09:30-16:00 → Regular Hours
     - 16:00-20:00 → After-Hours
   - Returns structured JSON with 3 arrays

3. **Display Phase**:
   - Frontend shows session toggle buttons
   - User selects "All Sessions" → Display all data
   - Color-code candlesticks:
     - Pre-Market: Blue
     - Regular Hours: Green/Red (bull/bear)
     - After-Hours: Orange

---

## Implementation Plan

### Phase 1: Alpha Vantage Integration (Day 1-2)

**Files to Create**:
- `backend/src/core/data/extended_hours_service.py`
  - `ExtendedHoursDataService` class
  - `get_extended_hours_data(symbol, interval) -> dict`
  - `_split_by_session(data) -> {pre_market, regular, after_hours}`
  - `_classify_session(timestamp) -> "pre" | "regular" | "after"`

**Configuration** (`backend/src/core/config.py`):
```python
# Add Alpha Vantage credentials
alpha_vantage_api_key: str = Field(..., env="ALPHA_VANTAGE_API_KEY")
alpha_vantage_base_url: str = Field(
    default="https://www.alphavantage.co/query"
)
enable_extended_hours: bool = Field(default=True, env="ENABLE_EXTENDED_HOURS")
```

**Environment Variables** (`.env.test`, K8s secrets):
```bash
ALPHA_VANTAGE_API_KEY=<YOUR_API_KEY>
ENABLE_EXTENDED_HOURS=true
```

**Alpha Vantage Setup**:
- Sign up at https://www.alphavantage.co/support/#api-key
- Free tier: 25 API calls per day (sufficient for testing)
- Premium tier: 75 calls/min, $50/month (for production)

### Phase 2: Backend API Endpoint (Day 2-3)

**Files to Modify**:
- `backend/src/api/market_data.py`
  - Add `GET /api/market/price/{symbol}/extended` endpoint
  - Validate interval (1min, 5min, 15min, 30min, 60min)
  - Call `ExtendedHoursDataService.get_extended_hours_data()`
  - Return structured response

**API Endpoint**:
```python
@router.get("/price/{symbol}/extended")
async def get_extended_hours_price(
    symbol: str,
    interval: str = Query(
        default="5min",
        regex="^(1min|5min|15min|30min|60min)$"
    ),
    extended_hours_service: ExtendedHoursDataService = Depends(),
) -> dict[str, Any]:
    """
    Get price data including pre-market and after-hours sessions.

    Returns:
        {
            "symbol": "AAPL",
            "interval": "5min",
            "sessions": {
                "pre_market": [...],
                "regular": [...],
                "after_hours": [...]
            },
            "metadata": {
                "timezone": "US/Eastern",
                "last_refreshed": "2025-10-30 16:00:00"
            }
        }
    """
    data = await extended_hours_service.get_extended_hours_data(
        symbol, interval
    )
    return data
```

**Response Format**:
```json
{
  "symbol": "AAPL",
  "interval": "5min",
  "sessions": {
    "pre_market": [
      {
        "time": "2025-10-30T04:00:00-04:00",
        "open": 275.00,
        "high": 275.50,
        "low": 274.80,
        "close": 275.20,
        "volume": 125000
      }
    ],
    "regular": [...],
    "after_hours": [...]
  },
  "metadata": {
    "timezone": "US/Eastern",
    "last_refreshed": "2025-10-30T16:00:00-04:00"
  }
}
```

### Phase 3: Session Classification Logic (Day 3)

**Algorithm** (`_classify_session()`):
```python
from datetime import datetime
from zoneinfo import ZoneInfo

def _classify_session(timestamp: str) -> str:
    """
    Classify timestamp into trading session.

    Args:
        timestamp: ISO format "2025-10-30T08:15:00-04:00"

    Returns:
        "pre_market" | "regular" | "after_hours" | "closed"
    """
    dt = datetime.fromisoformat(timestamp)

    # Convert to Eastern Time (market timezone)
    et = dt.astimezone(ZoneInfo("America/New_York"))
    hour = et.hour
    minute = et.minute

    # Pre-Market: 4:00 AM - 9:29 AM ET
    if hour < 4:
        return "closed"
    if hour < 9 or (hour == 9 and minute < 30):
        return "pre_market"

    # Regular Hours: 9:30 AM - 3:59 PM ET
    if hour < 16:
        return "regular"

    # After-Hours: 4:00 PM - 8:00 PM ET
    if hour < 20:
        return "after_hours"

    # Outside all trading hours
    return "closed"
```

**Edge Cases**:
- Handle daylight saving time transitions (use `zoneinfo`)
- Weekends/holidays return "closed" (future enhancement)
- Handle missing data points gracefully

### Phase 4: Frontend Session Toggle (Day 4-5)

**Files to Modify**:
- `frontend/src/components/chat/ChartPanel.tsx`
  - Add session toggle buttons
  - Add `session` state: `'all' | 'pre' | 'regular' | 'after'`
  - Filter chart data based on selected session
  - Color-code candlesticks by session

**UI Component**:
```typescript
const [session, setSession] = useState<'all' | 'pre' | 'regular' | 'after'>('all');

// In render:
<div className="flex gap-2 mb-4 items-center">
  <span className="text-sm text-gray-600 font-medium">Sessions:</span>
  <button
    onClick={() => setSession('all')}
    className={`px-3 py-1 rounded ${
      session === 'all'
        ? 'bg-blue-500 text-white'
        : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
    }`}
  >
    All
  </button>
  <button
    onClick={() => setSession('pre')}
    className={`px-3 py-1 rounded ${
      session === 'pre'
        ? 'bg-blue-500 text-white'
        : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
    }`}
  >
    Pre-Market
  </button>
  <button
    onClick={() => setSession('regular')}
    className={`px-3 py-1 rounded ${
      session === 'regular'
        ? 'bg-blue-500 text-white'
        : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
    }`}
  >
    Regular
  </button>
  <button
    onClick={() => setSession('after')}
    className={`px-3 py-1 rounded ${
      session === 'after'
        ? 'bg-blue-500 text-white'
        : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
    }`}
  >
    After-Hours
  </button>
</div>
```

**Data Filtering**:
```typescript
const filteredData = useMemo(() => {
  if (session === 'all') {
    return [
      ...extendedData.sessions.pre_market,
      ...extendedData.sessions.regular,
      ...extendedData.sessions.after_hours,
    ];
  }

  const sessionMap = {
    pre: 'pre_market',
    regular: 'regular',
    after: 'after_hours',
  };

  return extendedData.sessions[sessionMap[session]];
}, [session, extendedData]);
```

### Phase 5: Chart Styling by Session (Day 5-6)

**Color Scheme**:
```typescript
const getSessionColor = (time: string) => {
  const sessionType = classifySession(time);

  return {
    pre_market: {
      up: '#3B82F6',    // Blue (bullish pre-market)
      down: '#1E40AF',  // Dark Blue (bearish pre-market)
    },
    regular: {
      up: '#10B981',    // Green (bullish regular)
      down: '#EF4444',  // Red (bearish regular)
    },
    after_hours: {
      up: '#F59E0B',    // Orange (bullish after-hours)
      down: '#D97706',  // Dark Orange (bearish after-hours)
    },
  }[sessionType];
};
```

**Chart Legend**:
```typescript
<div className="flex gap-4 text-xs text-gray-600 mb-2">
  <div className="flex items-center gap-1">
    <div className="w-3 h-3 bg-blue-500 rounded"></div>
    <span>Pre-Market</span>
  </div>
  <div className="flex items-center gap-1">
    <div className="w-3 h-3 bg-green-500 rounded"></div>
    <span>Regular Hours</span>
  </div>
  <div className="flex items-center gap-1">
    <div className="w-3 h-3 bg-orange-500 rounded"></div>
    <span>After-Hours</span>
  </div>
</div>
```

---

## Data Models

### Backend Response

```python
class ExtendedHoursDataResponse(BaseModel):
    symbol: str
    interval: str
    sessions: dict[str, list[PricePoint]]
    metadata: dict[str, Any]

class PricePoint(BaseModel):
    time: str  # ISO 8601 format
    open: float
    high: float
    low: float
    close: float
    volume: int
    session: str  # "pre_market" | "regular" | "after_hours"
```

### Frontend Types

```typescript
interface ExtendedHoursData {
  symbol: string;
  interval: string;
  sessions: {
    pre_market: PricePoint[];
    regular: PricePoint[];
    after_hours: PricePoint[];
  };
  metadata: {
    timezone: string;
    last_refreshed: string;
  };
}

interface PricePoint {
  time: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  session: 'pre_market' | 'regular' | 'after_hours';
}
```

---

## API Endpoints

### 1. Get Extended Hours Data (NEW)

```http
GET /api/market/price/{symbol}/extended?interval=5min

Response:
{
  "symbol": "AAPL",
  "interval": "5min",
  "sessions": {
    "pre_market": [
      {
        "time": "2025-10-30T04:00:00-04:00",
        "open": 275.00,
        "high": 275.50,
        "low": 274.80,
        "close": 275.20,
        "volume": 125000,
        "session": "pre_market"
      }
    ],
    "regular": [...],
    "after_hours": [...]
  },
  "metadata": {
    "timezone": "US/Eastern",
    "last_refreshed": "2025-10-30T16:00:00-04:00"
  }
}

Status Codes:
- 200: Success
- 400: Invalid symbol or interval
- 429: Rate limit exceeded (Alpha Vantage)
- 500: API error
```

### 2. Regular Data Endpoint (Unchanged)

```http
GET /api/market/price/{symbol}?interval=1d&period=6mo

# Keeps existing behavior (yfinance, regular hours only)
```

---

## Trading Hours Reference

### US Stock Market Sessions (Eastern Time)

| Session | Start | End | Duration | Description |
|---------|-------|-----|----------|-------------|
| Pre-Market | 4:00 AM | 9:30 AM | 5.5 hours | Early trading, lower volume |
| Regular Hours | 9:30 AM | 4:00 PM | 6.5 hours | Main trading session |
| After-Hours | 4:00 PM | 8:00 PM | 4 hours | Post-close trading, earnings reactions |

**Key Characteristics**:
- **Pre-Market**: Reacts to overnight news, earnings reports (released before open)
- **Regular Hours**: Highest liquidity, tightest spreads
- **After-Hours**: Lower volume, wider spreads, earnings call reactions

**Holidays**: Market closed on US federal holidays (future enhancement: holiday calendar)

---

## Alpha Vantage Integration

### API Details

**Endpoint**: `https://www.alphavantage.co/query`

**Parameters**:
- `function=TIME_SERIES_INTRADAY`
- `symbol=AAPL`
- `interval=5min` (1min, 5min, 15min, 30min, 60min)
- `extended_hours=true` (KEY: enables pre/post-market data)
- `outputsize=full` (last 30 days) or `compact` (last 100 data points)
- `apikey=YOUR_API_KEY`

**Example Request**:
```bash
curl "https://www.alphavantage.co/query?function=TIME_SERIES_INTRADAY&symbol=AAPL&interval=5min&extended_hours=true&apikey=demo"
```

**Response Format**:
```json
{
  "Meta Data": {
    "1. Information": "Intraday (5min) open, high, low, close prices and volume",
    "2. Symbol": "AAPL",
    "3. Last Refreshed": "2025-10-30 16:00:00",
    "4. Interval": "5min",
    "5. Output Size": "Compact",
    "6. Time Zone": "US/Eastern"
  },
  "Time Series (5min)": {
    "2025-10-30 16:00:00": {
      "1. open": "275.00",
      "2. high": "275.50",
      "3. low": "274.80",
      "4. close": "275.20",
      "5. volume": "125000"
    }
  }
}
```

### Rate Limits

| Tier | Calls/Day | Calls/Minute | Cost |
|------|-----------|--------------|------|
| Free | 25 | 5 | $0 |
| Premium | Unlimited | 75 | $50/month |

**Rate Limit Handling**:
```python
# Cache responses in Redis (same as existing market data)
# TTL: 5 minutes for intraday data
# Fallback to regular hours data if rate limit exceeded
```

---

## Security Considerations

### API Key Management

1. **Environment Variable**: Store API key in K8s secret
   ```yaml
   apiVersion: v1
   kind: Secret
   metadata:
     name: alpha-vantage-secret
   data:
     ALPHA_VANTAGE_API_KEY: <base64-encoded-key>
   ```

2. **Azure Key Vault**: Use External Secrets Operator (existing setup)
   ```bash
   az keyvault secret set \
     --vault-name financial-agent-kv \
     --name alpha-vantage-api-key \
     --value "<YOUR_API_KEY>"
   ```

3. **Access Control**: API key only accessible to backend service

### Data Validation

```python
# Validate timestamps are in expected range
# Reject data points outside 4:00 AM - 8:00 PM ET
# Verify price/volume values are positive
# Sanitize symbol input (prevent injection)
```

---

## Performance Considerations

### Caching Strategy

```python
# Redis cache key: f"extended_hours:{symbol}:{interval}:latest"
# TTL: 5 minutes (balance freshness vs. API calls)
# Cache by session: Separate keys for pre/regular/after

async def get_extended_hours_data(symbol, interval):
    cache_key = f"extended_hours:{symbol}:{interval}:latest"

    # Try cache first
    cached = await redis.get(cache_key)
    if cached:
        return json.loads(cached)

    # Fetch from Alpha Vantage
    data = await self._fetch_from_alpha_vantage(symbol, interval)

    # Cache for 5 minutes
    await redis.setex(cache_key, 300, json.dumps(data))

    return data
```

### Optimization

1. **Background Refresh**: Pre-fetch data for popular symbols
2. **Parallel Requests**: Fetch regular + extended data simultaneously
3. **Data Compression**: Use Redis compression for large datasets
4. **Progressive Loading**: Load regular hours first, extended hours second

---

## Testing Strategy

### Unit Tests

```python
# backend/tests/test_extended_hours_service.py

def test_classify_pre_market():
    """Test 4:00 AM - 9:29 AM ET classification."""
    timestamp = "2025-10-30T08:15:00-04:00"
    assert _classify_session(timestamp) == "pre_market"

def test_classify_regular_hours():
    """Test 9:30 AM - 3:59 PM ET classification."""
    timestamp = "2025-10-30T14:30:00-04:00"
    assert _classify_session(timestamp) == "regular"

def test_classify_after_hours():
    """Test 4:00 PM - 8:00 PM ET classification."""
    timestamp = "2025-10-30T18:45:00-04:00"
    assert _classify_session(timestamp) == "after_hours"

def test_classify_closed():
    """Test outside trading hours."""
    timestamp = "2025-10-30T21:00:00-04:00"
    assert _classify_session(timestamp) == "closed"

def test_split_by_session():
    """Test data splitting into 3 sessions."""
    data = {
        "Time Series (5min)": {
            "2025-10-30 08:00:00": {...},  # Pre-market
            "2025-10-30 14:00:00": {...},  # Regular
            "2025-10-30 18:00:00": {...},  # After-hours
        }
    }
    result = _split_by_session(data)
    assert len(result["pre_market"]) == 1
    assert len(result["regular"]) == 1
    assert len(result["after_hours"]) == 1
```

### Integration Tests

```typescript
// frontend/tests/chart-extended-hours.test.tsx

test('Session toggle filters data correctly', () => {
  render(<ChartPanel extendedData={mockData} />);

  // Default: All sessions
  expect(screen.getByText('All')).toHaveClass('bg-blue-500');

  // Click "Pre-Market"
  fireEvent.click(screen.getByText('Pre-Market'));
  // Verify only pre-market data displayed

  // Click "Regular"
  fireEvent.click(screen.getByText('Regular'));
  // Verify only regular hours data displayed
});

test('Chart colors match session', () => {
  render(<ChartPanel extendedData={mockData} />);

  // Pre-market candles should be blue
  const preMarketCandles = screen.getAllByTestId('pre-market-candle');
  expect(preMarketCandles[0]).toHaveStyle('fill: #3B82F6');

  // Regular candles should be green/red
  const regularCandles = screen.getAllByTestId('regular-candle');
  expect(regularCandles[0]).toHaveStyle('fill: #10B981');
});
```

### Manual Testing Checklist

- [ ] Fetch extended hours data for AAPL, TSLA, MSFT
- [ ] Verify pre-market data shows 4:00 AM - 9:29 AM ET
- [ ] Verify regular hours data shows 9:30 AM - 3:59 PM ET
- [ ] Verify after-hours data shows 4:00 PM - 8:00 PM ET
- [ ] Toggle session buttons → Chart updates correctly
- [ ] Color-coding matches session (blue, green/red, orange)
- [ ] Handle missing data gracefully (weekends, holidays)
- [ ] Rate limit handling (exhaust free tier, verify fallback)
- [ ] Mobile responsive (session buttons stack vertically)

---

## Acceptance Criteria

### Must Have (MVP)

- [x] Backend fetches extended hours data from Alpha Vantage
- [x] Data split into 3 sessions (pre-market, regular, after-hours)
- [x] New API endpoint: `GET /api/market/price/{symbol}/extended`
- [x] Frontend session toggle buttons (All, Pre, Regular, After)
- [x] Chart displays filtered data based on selected session
- [x] Color-coded candlesticks by session
- [x] Caching with 5-minute TTL (reduce API calls)
- [x] Error handling (rate limits, API errors)

### Nice to Have (Future)

- [ ] Automatic session detection (show current session by default)
- [ ] Volume profile by session (compare liquidity)
- [ ] Gap analysis (overnight gap between after-hours close and pre-market open)
- [ ] Holiday calendar (disable extended hours on market holidays)
- [ ] Real-time streaming (WebSocket) for live extended hours data
- [ ] Alerts for significant pre-market moves (>5% price change)

---

## Risks & Mitigation

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| Alpha Vantage rate limits | High | High | Aggressive caching (5 min), fallback to regular hours |
| API cost escalation | Medium | Medium | Monitor usage, upgrade to Premium only if needed |
| Data accuracy concerns | High | Low | Validate against Bloomberg/Reuters, user feedback loop |
| Session classification errors | Medium | Low | Comprehensive unit tests, edge case handling |
| User confusion (3 session toggles) | Low | Medium | Clear UI labels, tooltips, onboarding guide |

---

## Rollout Plan

### Development Phase (1-2 weeks)

1. **Week 1**:
   - Day 1-2: Alpha Vantage integration + session splitter
   - Day 3: Backend API endpoint + caching
   - Day 4-5: Frontend session toggle + data filtering
   - Day 6: Chart styling by session

2. **Week 2**:
   - Day 1-2: Testing + bug fixes
   - Day 3: Documentation
   - Day 4: Deploy to test environment
   - Day 5: User testing + feedback

### Deployment Strategy

1. **Alpha Phase** (Test Environment):
   - Deploy backend with Alpha Vantage integration
   - Test with free tier (25 calls/day)
   - Gather feedback from 5-10 active traders
   - Monitor API usage and costs

2. **Beta Phase** (Production Soft Launch):
   - Enable for 50% of users (A/B test)
   - Upgrade to Premium tier ($50/month) if needed
   - Collect metrics (usage, satisfaction, API costs)

3. **General Availability**:
   - Roll out to 100% of users
   - Add to onboarding flow (educate users on sessions)

### Monitoring

```bash
# Metrics to track:
- Extended hours API call count (daily)
- Session toggle click distribution (All vs. Pre vs. Regular vs. After)
- Alpha Vantage API errors (rate limits, downtime)
- User engagement (time spent viewing extended hours)
- Cost per API call ($50/month ÷ calls)
```

---

## Dependencies

### External Services

- **Alpha Vantage API**: Extended hours intraday data
  - Free tier: 25 calls/day, 5 calls/min
  - Premium tier: $50/month, 75 calls/min
  - Signup: https://www.alphavantage.co/support/#api-key

### Python Libraries

- `aiohttp`: Async HTTP client (already installed)
- `zoneinfo`: Timezone handling (Python 3.9+ standard library)

### Frontend Libraries

- No new dependencies needed
- Use existing chart library (lightweight-charts)

---

## Success Metrics

### Quantitative

- **Target**: 30% of active users view extended hours data within 30 days
- **Session Toggle Engagement**: >50% of users click session toggles
- **API Success Rate**: >99% (accounting for rate limits)
- **User Retention**: Extended hours users have 20% higher retention

### Qualitative

- Users report better understanding of overnight price movements
- Positive feedback on session toggle UX
- Traders identify more pre-market trading opportunities
- Reduced requests for "add pre-market data" in feedback

---

## Future Enhancements

1. **Level 2 Pre-Market Quotes**: Real-time bid/ask spreads
2. **Earnings Calendar Integration**: Highlight pre-market earnings reports
3. **News Feed by Session**: Show news articles that triggered moves
4. **Gap Scanner**: Identify stocks with largest overnight gaps
5. **Volume Analysis**: Compare pre/regular/after-hours volume
6. **Social Sentiment**: Track Twitter/Reddit buzz during extended hours

---

## References

- Alpha Vantage Documentation: https://www.alphavantage.co/documentation/
- Intraday Extended Hours API: https://www.alphavantage.co/documentation/#intraday-extended
- US Stock Market Hours: https://www.nasdaq.com/stock-market-trading-hours-for-nasdaq
- Trading Sessions Guide: https://www.investopedia.com/terms/e/extended_trading.asp
- Existing Market Data API: `/backend/src/api/market_data.py`
- yfinance Utils: `/backend/src/core/utils/yfinance_utils.py`

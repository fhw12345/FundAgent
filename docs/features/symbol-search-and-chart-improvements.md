# Symbol Search and Chart Visualization Improvements

**Status**: Planning
**Priority**: High
**Complexity**: Medium-High
**Estimated Effort**: 8-12 days

## Context

The current symbol search and chart visualization have several UX issues:
1. Search returns duplicates (AAPL appears multiple times)
2. Irrelevant results (Apple Hospitality REIT when searching "apple")
3. Hardcoded symbol mappings (not scalable)
4. Chart tooltip only shows close price (no OHLC data)
5. No custom date range selection
6. Analysis buttons use default periods, not user-selected ranges

## Problem Statement

### Symbol Search Issues

**Root Cause:**
- `yfinance.search()` returns ALL matching tickers across all exchanges without filtering
- Same company appears on multiple exchanges (AAPL on NMS, FRA, NEO, etc.)
- No relevance ranking beyond simple string matching
- Hardcoded mappings like `"meituan" → "3690.HK"` are not scalable

**Current Flow:**
```
User types "apple"
  → yfinance.search("apple")
  → Returns: AAPL (NMS), AAPL (NEO), 48T.F (FRA), AAPL.NE, etc.
  → Frontend shows all results (duplicates + irrelevant)
```

### Chart Visualization Issues

**Current Limitations:**
- Tooltip only shows: `"Jul 17, 2025 | $209.78"`
- No OHLC (Open, High, Low, Close) information
- No volume data
- No color coding for candle direction
- Fixed time periods (1H, 1D, 1W, 1M)
- No custom date range selection
- Analysis buttons use backend defaults, not user selection

## Proposed Solution

### Phase 1: Quick Wins (2-3 days)

#### 1.1 Fix Symbol Search Deduplication

**Backend Changes** (`backend/src/api/market_data.py`):

```python
def search_symbols(query: str) -> list[SymbolSearchResult]:
    """
    Search for stock symbols with intelligent filtering.

    Improvements:
    - Deduplicate by company name
    - Prioritize primary exchanges (US: NMS, NAS, NYQ)
    - Filter by relevance score
    - Limit to top 10 results
    """
    results = yf.Ticker(query).search(query)

    # Deduplicate by company name
    seen_companies = set()
    unique_results = []

    # Priority order: US exchanges first
    exchange_priority = ["NMS", "NAS", "NYQ", "NYE", "PCX"]

    # Sort by: 1) Exchange priority, 2) Name match score
    sorted_results = sorted(
        results,
        key=lambda x: (
            exchange_priority.index(x.exchange)
            if x.exchange in exchange_priority else 999,
            -x.score  # Higher score = better match
        )
    )

    for result in sorted_results:
        company_key = result.longName.lower()
        if company_key not in seen_companies:
            seen_companies.add(company_key)
            unique_results.append(result)
            if len(unique_results) >= 10:
                break

    return unique_results
```

**Expected Result:**
```
Search "apple":
  ✅ AAPL - Apple Inc. (NMS)
  ❌ AAPL - Apple Inc. (NEO) [removed - duplicate]
  ❌ 48T.F - Apple Hospitality REIT [removed - low relevance]
```

#### 1.2 Add OHLC to Chart Tooltip

**Frontend Changes** (`frontend/src/components/Chart.tsx`):

```typescript
// Update tooltip formatter
const tooltipFormatter = (data: CandlestickData) => {
  const isGreen = data.close >= data.open;
  const arrow = isGreen ? '↑' : '↓';
  const color = isGreen ? 'text-green-600' : 'text-red-600';

  return `
    <div class="chart-tooltip">
      <div class="font-bold">${formatDate(data.time)}</div>
      <div class="${color}">
        Open:  ${formatPrice(data.open)}
        High:  ${formatPrice(data.high)}
        Low:   ${formatPrice(data.low)}
        Close: ${formatPrice(data.close)} ${arrow}
      </div>
      <div class="text-gray-600">
        Volume: ${formatVolume(data.volume)}
      </div>
    </div>
  `;
};
```

**Expected Result:**
```
Tooltip shows:
┌─────────────────────────┐
│ Jul 17, 2025 14:30 EST │
│ Open:  $209.50  ↑      │
│ High:  $210.20         │
│ Low:   $208.90         │
│ Close: $209.78         │
│ Volume: 2.5M           │
└─────────────────────────┘
```

#### 1.3 Show Date Range Labels

**Frontend Changes**:

```typescript
// Add below chart
<div className="text-sm text-gray-600 mt-2">
  Showing data from {formatDate(startDate)} to {formatDate(endDate)}
  ({diffInDays} days)
</div>
```

**Expected Result:**
```
[Chart visualization]
Showing data from Jul 1, 2025 to Oct 10, 2025 (101 days)
```

---

### Phase 2: Date Range Selection (3-4 days)

#### 2.1 Add Custom Date Range Picker UI

**Design Principles:**
- Simple and native (HTML5 date inputs)
- Quick presets for common periods
- Visible date range at all times
- Flexible and intuitive

**UI Mockup:**
```
┌───────────────────────────────────────────────────────────┐
│ Trading Charts: AAPL                    $ 245.27 ▼ -2.3% │
├───────────────────────────────────────────────────────────┤
│ Date Range:                                               │
│ ┌─────────────┐     ┌─────────────┐                      │
│ │ 2025-07-01 ▼│  to │ 2025-10-10 ▼│  [Apply]            │
│ └─────────────┘     └─────────────┘                      │
│ Quick: [1W] [1M] [3M] [6M] [1Y] [YTD] [Max]             │
├───────────────────────────────────────────────────────────┤
│ [Chart with selected date range]                          │
│                                                           │
│ Actions: [📊 Fibonacci] [📈 Stochastic] [📋 Fundamental]│
└───────────────────────────────────────────────────────────┘
```

**Frontend Implementation** (`frontend/src/components/DateRangePicker.tsx`):

```typescript
interface DateRangePickerProps {
  onRangeChange: (start: Date, end: Date) => void;
  defaultRange?: { start: Date; end: Date };
}

export function DateRangePicker({ onRangeChange, defaultRange }: DateRangePickerProps) {
  const [startDate, setStartDate] = useState(defaultRange?.start || getDefaultStart());
  const [endDate, setEndDate] = useState(defaultRange?.end || new Date());

  const quickPresets = [
    { label: '1W', days: 7 },
    { label: '1M', days: 30 },
    { label: '3M', days: 90 },
    { label: '6M', days: 180 },
    { label: '1Y', days: 365 },
    { label: 'YTD', days: daysSinceYearStart() },
    { label: 'Max', days: 365 * 5 },  // 5 years max
  ];

  const handlePreset = (days: number) => {
    const end = new Date();
    const start = subDays(end, days);
    setStartDate(start);
    setEndDate(end);
    onRangeChange(start, end);
  };

  return (
    <div className="date-range-picker">
      <div className="flex items-center gap-4 mb-2">
        <label>From:</label>
        <input
          type="date"
          value={format(startDate, 'yyyy-MM-dd')}
          onChange={(e) => setStartDate(new Date(e.target.value))}
          max={format(endDate, 'yyyy-MM-dd')}
        />
        <label>To:</label>
        <input
          type="date"
          value={format(endDate, 'yyyy-MM-dd')}
          onChange={(e) => setEndDate(new Date(e.target.value))}
          max={format(new Date(), 'yyyy-MM-dd')}
        />
        <button onClick={() => onRangeChange(startDate, endDate)}>
          Apply
        </button>
      </div>

      <div className="quick-presets">
        <span className="text-sm text-gray-600">Quick:</span>
        {quickPresets.map(preset => (
          <button
            key={preset.label}
            onClick={() => handlePreset(preset.days)}
            className="preset-btn"
          >
            {preset.label}
          </button>
        ))}
      </div>
    </div>
  );
}
```

#### 2.2 Update Backend APIs for Date Range

**API Changes** (`backend/src/api/schemas/analysis_models.py`):

```python
from datetime import date
from typing import Optional

class AnalysisRequest(BaseModel):
    """Base analysis request with optional date range."""

    symbol: str = Field(..., description="Stock symbol (e.g., AAPL)")
    interval: str = Field("1d", description="Data interval (1d, 1h, 5m)")
    start_date: Optional[date] = Field(None, description="Start date (YYYY-MM-DD)")
    end_date: Optional[date] = Field(None, description="End date (YYYY-MM-DD)")

    @property
    def period(self) -> str:
        """Calculate yfinance period from date range."""
        if not self.start_date or not self.end_date:
            return "6mo"  # Default

        days = (self.end_date - self.start_date).days
        if days <= 7:
            return "7d"
        elif days <= 30:
            return "1mo"
        elif days <= 90:
            return "3mo"
        elif days <= 180:
            return "6mo"
        elif days <= 365:
            return "1y"
        elif days <= 730:
            return "2y"
        else:
            return "5y"
```

**Endpoint Updates** (`backend/src/api/analysis.py`):

```python
@router.post("/fibonacci")
async def analyze_fibonacci(request: AnalysisRequest) -> FibonacciResponse:
    """
    Fibonacci retracement analysis with optional date range.

    If start_date and end_date provided, uses custom range.
    Otherwise, falls back to period parameter.
    """
    # Fetch data with date range
    if request.start_date and request.end_date:
        data = yf.download(
            request.symbol,
            start=request.start_date,
            end=request.end_date,
            interval=request.interval
        )
    else:
        data = yf.download(
            request.symbol,
            period=request.period,
            interval=request.interval
        )

    # Perform analysis on date-filtered data
    result = fibonacci_analyzer.analyze(data)
    return result
```

#### 2.3 Wire Analysis Buttons to Date Range

**Frontend Changes** (`frontend/src/components/AnalysisButtons.tsx`):

```typescript
interface AnalysisButtonsProps {
  symbol: string;
  dateRange: { start: Date; end: Date };
}

export function AnalysisButtons({ symbol, dateRange }: AnalysisButtonsProps) {
  const handleFibonacci = async () => {
    const response = await api.post('/api/analysis/fibonacci', {
      symbol,
      interval: '1d',
      start_date: format(dateRange.start, 'yyyy-MM-dd'),
      end_date: format(dateRange.end, 'yyyy-MM-dd'),
    });

    // Display results...
  };

  return (
    <div className="analysis-buttons">
      <button onClick={handleFibonacci}>
        📊 Fibonacci Analysis
      </button>
      <button onClick={handleStochastic}>
        📈 Stochastic Analysis
      </button>
      <button onClick={handleFundamental}>
        📋 Fundamental Analysis
      </button>

      <span className="text-sm text-gray-500">
        Analysis will use data from {format(dateRange.start, 'MMM d')}
        to {format(dateRange.end, 'MMM d, yyyy')}
      </span>
    </div>
  );
}
```

---

### Phase 3: Better Symbol Search (4-5 days)

#### 3.1 Integrate Financial Modeling Prep (FMP) API

**Why FMP?**
- Clean, deduplicated symbol data
- Company profiles with exchange info
- 250 requests/day free tier (sufficient for beta)
- $15/month for production (affordable)
- Better than yfinance search quality

**Alternative Evaluation:**

| Data Source | Free Tier | Quality | Cost (Prod) | Verdict |
|-------------|-----------|---------|-------------|---------|
| yfinance | Unlimited | Poor (duplicates) | Free | ❌ Current issues |
| FMP API | 250/day | Excellent | $15/mo | ✅ **Recommended** |
| Alpha Vantage | 25/day | Good | Free | ❌ Too limited |
| Polygon.io | Limited | Excellent | $200/mo | ❌ Too expensive |
| IEX Cloud | 50k/mo | Good | $9/mo | ✅ Alternative |

**Implementation** (`backend/src/services/symbol_search_service.py`):

```python
import httpx
from typing import List, Optional
import structlog

logger = structlog.get_logger()

class SymbolSearchService:
    """Enhanced symbol search using FMP API with yfinance fallback."""

    def __init__(self, fmp_api_key: str, redis_client: Redis):
        self.fmp_api_key = fmp_api_key
        self.redis = redis_client
        self.fmp_base_url = "https://financialmodelingprep.com/api/v3"

    async def search(
        self,
        query: str,
        limit: int = 10
    ) -> List[SymbolSearchResult]:
        """
        Search for stock symbols with intelligent filtering.

        Strategy:
        1. Check Redis cache first (24hr TTL)
        2. Try FMP API (primary source)
        3. Fallback to yfinance if FMP unavailable
        4. Post-process and deduplicate results
        5. Cache in Redis
        """
        cache_key = f"symbol_search:{query.lower()}"

        # Check cache
        cached = await self.redis.get(cache_key)
        if cached:
            logger.info("Symbol search cache hit", query=query)
            return json.loads(cached)

        # Try FMP first
        try:
            results = await self._search_fmp(query, limit)
            if results:
                await self.redis.setex(cache_key, 86400, json.dumps(results))
                return results
        except Exception as e:
            logger.warning("FMP search failed, falling back to yfinance",
                         error=str(e))

        # Fallback to yfinance
        results = await self._search_yfinance(query, limit)
        await self.redis.setex(cache_key, 86400, json.dumps(results))
        return results

    async def _search_fmp(
        self,
        query: str,
        limit: int
    ) -> List[SymbolSearchResult]:
        """Search using FMP API."""
        url = f"{self.fmp_base_url}/search"
        params = {
            "query": query,
            "limit": limit,
            "apikey": self.fmp_api_key,
            "exchange": "NASDAQ,NYSE",  # US exchanges only
        }

        async with httpx.AsyncClient() as client:
            response = await client.get(url, params=params, timeout=5.0)
            response.raise_for_status()
            data = response.json()

        return [
            SymbolSearchResult(
                symbol=item["symbol"],
                name=item["name"],
                exchange=item["exchangeShortName"],
                type=item.get("type", "stock"),
                currency=item.get("currency", "USD"),
                score=self._calculate_relevance(query, item["name"])
            )
            for item in data
        ]

    async def _search_yfinance(
        self,
        query: str,
        limit: int
    ) -> List[SymbolSearchResult]:
        """Fallback search using yfinance with post-processing."""
        # ... (implementation from Phase 1.1)

    def _calculate_relevance(self, query: str, name: str) -> float:
        """Calculate relevance score (0-1) for search result."""
        query_lower = query.lower()
        name_lower = name.lower()

        # Exact match
        if query_lower == name_lower:
            return 1.0

        # Starts with query
        if name_lower.startswith(query_lower):
            return 0.9

        # Contains query
        if query_lower in name_lower:
            return 0.7

        # Fuzzy match using Levenshtein distance
        distance = levenshtein_distance(query_lower, name_lower)
        max_len = max(len(query_lower), len(name_lower))
        return max(0, 1 - (distance / max_len))
```

**Configuration** (`backend/src/core/config.py`):

```python
class Settings(BaseSettings):
    # ... existing settings ...

    # Symbol search
    FMP_API_KEY: Optional[str] = Field(None, description="Financial Modeling Prep API key")
    SYMBOL_SEARCH_CACHE_TTL: int = Field(86400, description="Symbol search cache TTL (seconds)")
```

#### 3.2 Add Symbol Alias Database

**Purpose:**
- Support alternate names (e.g., "meituan" → "3690.HK")
- Community-driven symbol mappings
- Scalable alternative to hardcoded mappings

**MongoDB Schema** (`backend/src/models/symbol_alias.py`):

```python
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field

class SymbolAlias(BaseModel):
    """Alternate names/aliases for stock symbols."""

    alias_id: str = Field(default_factory=lambda: f"alias_{uuid4().hex[:12]}")
    alias: str = Field(..., description="Alternate name (e.g., 'meituan')")
    symbol: str = Field(..., description="Official symbol (e.g., '3690.HK')")
    exchange: str = Field(..., description="Exchange (e.g., 'HKEX')")
    company_name: str = Field(..., description="Official company name")
    priority: int = Field(0, description="Priority for disambiguation (higher = preferred)")
    source: str = Field("manual", description="Source: manual, community, ai")
    created_by: Optional[str] = Field(None, description="User who created this alias")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    verified: bool = Field(False, description="Whether alias is verified/curated")

    class Config:
        collection_name = "symbol_aliases"
```

**Alias Search Integration**:

```python
async def search_with_aliases(
    self,
    query: str,
    limit: int = 10
) -> List[SymbolSearchResult]:
    """Search with alias expansion."""

    # Check if query matches any alias
    alias = await self.alias_repo.find_by_alias(query.lower())

    if alias:
        # Direct match - return the target symbol
        logger.info("Alias match found", alias=query, symbol=alias.symbol)
        return [
            SymbolSearchResult(
                symbol=alias.symbol,
                name=alias.company_name,
                exchange=alias.exchange,
                score=1.0,  # Perfect match
                matched_via_alias=True
            )
        ]

    # No alias match - proceed with normal search
    return await self.search(query, limit)
```

**Example Usage:**
```
User searches "meituan"
  → Check symbol_aliases collection
  → Find: {alias: "meituan", symbol: "3690.HK"}
  → Return: 3690.HK - Meituan (HKEX)
```

#### 3.3 Admin Interface for Symbol Aliases

**API Endpoints** (`backend/src/api/admin.py`):

```python
@router.post("/aliases")
async def create_alias(
    alias: SymbolAliasCreate,
    _: None = Depends(require_admin),
) -> SymbolAlias:
    """Create a new symbol alias (admin only)."""
    return await alias_repo.create(alias)

@router.get("/aliases")
async def list_aliases(
    _: None = Depends(require_admin),
    skip: int = 0,
    limit: int = 100,
) -> List[SymbolAlias]:
    """List all symbol aliases (admin only)."""
    return await alias_repo.find_all(skip=skip, limit=limit)

@router.delete("/aliases/{alias_id}")
async def delete_alias(
    alias_id: str,
    _: None = Depends(require_admin),
) -> dict:
    """Delete a symbol alias (admin only)."""
    await alias_repo.delete(alias_id)
    return {"status": "deleted", "alias_id": alias_id}
```

**Frontend Admin Panel** (`frontend/src/pages/AdminAliasesPage.tsx`):

```typescript
export function AdminAliasesPage() {
  const [aliases, setAliases] = useState<SymbolAlias[]>([]);
  const [newAlias, setNewAlias] = useState({
    alias: '',
    symbol: '',
    exchange: '',
    company_name: '',
  });

  const handleCreate = async () => {
    await api.post('/api/admin/aliases', newAlias);
    // Refresh list...
  };

  return (
    <div className="admin-aliases-page">
      <h1>Symbol Aliases Management</h1>

      <div className="create-alias-form">
        <h2>Add New Alias</h2>
        <input
          placeholder="Alias (e.g., meituan)"
          value={newAlias.alias}
          onChange={e => setNewAlias({...newAlias, alias: e.target.value})}
        />
        <input
          placeholder="Symbol (e.g., 3690.HK)"
          value={newAlias.symbol}
          onChange={e => setNewAlias({...newAlias, symbol: e.target.value})}
        />
        <button onClick={handleCreate}>Create Alias</button>
      </div>

      <div className="aliases-list">
        <h2>Existing Aliases</h2>
        <table>
          <thead>
            <tr>
              <th>Alias</th>
              <th>Symbol</th>
              <th>Company</th>
              <th>Exchange</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {aliases.map(alias => (
              <tr key={alias.alias_id}>
                <td>{alias.alias}</td>
                <td>{alias.symbol}</td>
                <td>{alias.company_name}</td>
                <td>{alias.exchange}</td>
                <td>
                  <button onClick={() => handleDelete(alias.alias_id)}>
                    Delete
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
```

---

## Implementation Roadmap

### Week 1: Quick Wins

**Days 1-2: Symbol Search Fixes**
- [ ] Implement deduplication logic
- [ ] Add exchange prioritization
- [ ] Limit results to top 10
- [ ] Add unit tests
- [ ] Deploy and verify

**Days 3: Chart OHLC Enhancement**
- [ ] Update frontend tooltip formatter
- [ ] Add color coding (green/red)
- [ ] Format volume display
- [ ] Test with various symbols
- [ ] Deploy and verify

### Week 2: Date Range Selection

**Days 4-5: UI Components**
- [ ] Create DateRangePicker component
- [ ] Add quick preset buttons
- [ ] Integrate with chart state
- [ ] Add date range labels
- [ ] Test on mobile

**Days 6-7: Backend API Updates**
- [ ] Add start_date/end_date to analysis schemas
- [ ] Update Fibonacci endpoint
- [ ] Update Stochastic endpoint
- [ ] Update Fundamental endpoint
- [ ] Add date range validation
- [ ] Write integration tests

**Day 8: Integration**
- [ ] Wire analysis buttons to date range
- [ ] Add loading states
- [ ] Handle errors gracefully
- [ ] E2E testing
- [ ] Deploy to staging

### Week 3: Better Search Integration

**Days 9-10: FMP API Integration**
- [ ] Sign up for FMP API account
- [ ] Implement FMP search service
- [ ] Add Redis caching layer
- [ ] Implement fallback logic
- [ ] Load test (rate limits)
- [ ] Deploy with feature flag

**Days 11-12: Symbol Aliases**
- [ ] Create MongoDB collection
- [ ] Implement alias repository
- [ ] Add alias search logic
- [ ] Create admin API endpoints
- [ ] Build admin UI
- [ ] Seed with common aliases

## Success Metrics

### Symbol Search Quality
- **Duplicate Rate**: < 5% (currently ~30%)
- **Relevance Score**: > 90% for top result
- **Search Speed**: < 200ms p95

### Chart UX
- **Tooltip Information**: OHLC + Volume visible
- **Date Range Adoption**: > 30% of analysis uses custom range
- **Analysis Accuracy**: Uses correct date range 100% of time

### Alias Coverage
- **Common Aliases**: Top 100 stocks have alternate names
- **Admin Usage**: > 50 aliases created in first month
- **Search Success Rate**: > 95% (alias + regular search)

## Migration Strategy

### Phase 1 (No Breaking Changes)
- Deploy symbol search improvements
- Add OHLC tooltip
- Add date labels
- **No data migration needed**

### Phase 2 (Additive Changes)
- Deploy date range picker
- Update APIs to accept optional date params
- **Backward compatible** (defaults to existing behavior)

### Phase 3 (New Services)
- Deploy FMP integration with feature flag
- Create symbol_aliases collection
- Roll out to admins first
- Gradual rollout to all users

## Testing Strategy

### Unit Tests
- Symbol search deduplication logic
- OHLC tooltip formatting
- Date range validation
- Alias matching logic

### Integration Tests
- End-to-end symbol search flow
- Analysis with custom date range
- FMP API integration with fallback
- Alias CRUD operations

### Manual Testing
- Search for common stocks (AAPL, TSLA, MSFT)
- Search for international stocks (3690.HK, 600519.SS)
- Test date range picker on mobile
- Test analysis with various date ranges
- Verify OHLC data accuracy

## Risks and Mitigation

### Risk 1: FMP API Rate Limits
**Mitigation**:
- Redis caching (24hr TTL)
- Fallback to yfinance
- Monitor usage via logging

### Risk 2: Date Range Performance
**Mitigation**:
- Limit max range (e.g., 5 years)
- Show loading indicators
- Cache analysis results

### Risk 3: Breaking Changes
**Mitigation**:
- All changes backward compatible
- Feature flags for new functionality
- Gradual rollout

## Follow-Up Work

### Phase 4 (Future Enhancements)
- Fuzzy search with Levenshtein distance
- User-contributed aliases (with moderation)
- Multiple chart comparison
- Technical indicator overlays
- Export chart as image
- Share analysis links

## Questions for Discussion

1. **FMP API Cost**: Comfortable with $15/month for production?
2. **Date Range Limits**: Should we cap at 5 years or allow "Max"?
3. **Alias Moderation**: Admin-only or community-driven with approval?
4. **Mobile UX**: Native date picker or custom component?
5. **Analytics**: What metrics should we track for search quality?

---

**Last Updated**: 2025-10-11
**Document Owner**: Engineering Team
**Reviewers**: Product, Design, Backend Lead, Frontend Lead

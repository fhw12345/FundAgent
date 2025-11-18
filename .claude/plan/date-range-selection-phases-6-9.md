# Date Range Selection - Phases 6-9 Implementation Plan

## Context

Phases 0-5 complete (backend + API layer). Remaining work is frontend UI implementation.

**Completed:**
- ✅ Backend: market status endpoint, date validation, custom filtering
- ✅ Frontend: TypeScript types, API service methods

**Remaining:**
- ⏳ Phase 6: Date picker UI in ChartHeader
- ⏳ Phase 7: Market session indicators on chart
- ⏳ Phase 8: Integration in TradingChart
- ⏳ Phase 9: End-to-end testing

---

## Phase 6: Date Picker UI in ChartHeader

**File:** `frontend/src/components/chart/ChartHeader.tsx`

**Changes:**

1. **Add state for custom date range:**
```typescript
const [customDateRange, setCustomDateRange] = useState<{
  startDate: string;
  endDate: string;
} | null>(null);
```

2. **Add props:**
```typescript
interface ChartHeaderProps {
  ...existing props...
  onCustomDateRangeChange?: (startDate: string, endDate: string) => void;
  isIntradayInterval: boolean; // 1m or 1h
  marketStatus: MarketStatus | null;
}
```

3. **Add JSX for date pickers** (after interval buttons):
```typescript
<div className="flex gap-2 items-center ml-4">
  <label className="text-sm text-gray-600">From:</label>
  <input
    type="date"
    value={customDateRange?.startDate || ""}
    onChange={(e) => handleStartDateChange(e.target.value)}
    disabled={isIntradayInterval && !marketStatus?.is_open}
    className="text-xs border border-gray-300 rounded px-2 py-1"
  />
  <label className="text-sm text-gray-600">To:</label>
  <input
    type="date"
    value={customDateRange?.endDate || ""}
    onChange={(e) => handleEndDateChange(e.target.value)}
    disabled={isIntradayInterval && !marketStatus?.is_open}
    className="text-xs border border-gray-300 rounded px-2 py-1"
  />
  {isIntradayInterval && !marketStatus?.is_open && (
    <span className="text-xs text-red-600 ml-2">🔴 Market Closed</span>
  )}
</div>
```

4. **Add handlers:**
```typescript
const handleStartDateChange = (date: string) => {
  setCustomDateRange(prev => ({ ...prev, startDate: date, endDate: prev?.endDate || date }));
};

const handleEndDateChange = (date: string) => {
  if (customDateRange?.startDate) {
    setCustomDateRange({ ...customDateRange, endDate: date });
    onCustomDateRangeChange?.(customDateRange.startDate, date);
  }
};
```

---

## Phase 7: Market Session Indicators on Chart

**File:** `frontend/src/components/chart/useChart.ts` (or new file)

**Purpose:** Render shaded regions and labels for market sessions

**Approach:**

1. **Detect session ranges from data:**
```typescript
function detectSessionRanges(data: PriceDataPoint[]): SessionRange[] {
  const sessions: SessionRange[] = [];
  let currentSession = data[0]?.market_session;
  let sessionStart = data[0]?.time;

  data.forEach((point, index) => {
    if (point.market_session !== currentSession) {
      // Session changed, save the range
      sessions.push({
        session: currentSession,
        start: sessionStart,
        end: data[index - 1].time,
        color: getSessionColor(currentSession),
        label: getSessionLabel(currentSession),
      });
      currentSession = point.market_session;
      sessionStart = point.time;
    }
  });

  // Add final session
  sessions.push({
    session: currentSession,
    start: sessionStart,
    end: data[data.length - 1].time,
    color: getSessionColor(currentSession),
    label: getSessionLabel(currentSession),
  });

  return sessions;
}

function getSessionColor(session: string): string {
  const colors = {
    pre: 'rgba(59, 130, 246, 0.1)',      // Blue
    regular: 'rgba(34, 197, 94, 0.1)',   // Green
    post: 'rgba(249, 115, 22, 0.1)',     // Orange
    closed: 'rgba(156, 163, 175, 0.1)',  // Gray
  };
  return colors[session] || colors.closed;
}

function getSessionLabel(session: string): string {
  const labels = {
    pre: 'Pre-Market',
    regular: 'Regular Hours',
    post: 'After-Hours',
    closed: 'Closed',
  };
  return labels[session] || '';
}
```

2. **Add shaded regions using lightweight-charts:**
```typescript
sessions.forEach(session => {
  // Add background shading (using price line hack or custom plugin)
  const priceLine = series.createPriceLine({
    price: 0,
    color: 'transparent',
    lineWidth: 0,
    // Note: Lightweight charts doesn't support background shading natively
    // May need to use time scale markers or custom rendering
  });

  // Add text markers
  const marker = {
    time: session.start,
    position: 'aboveBar',
    text: session.label,
    color: session.color.replace('0.1', '1'),
    shape: 'text',
  };
  series.setMarkers([...existingMarkers, marker]);
});
```

**Note:** Lightweight Charts has limited support for background regions. May need to:
- Use time scale markers with custom rendering
- Or use HTML overlay divs positioned absolutely
- Or upgrade to TradingView Charting Library (paid)

---

## Phase 8: Integration in TradingChart

**File:** `frontend/src/components/TradingChart.tsx`

**Changes:**

1. **Add state:**
```typescript
const [marketStatus, setMarketStatus] = useState<MarketStatus | null>(null);
const [customDateRange, setCustomDateRange] = useState<{start: string; end: string} | null>(null);
```

2. **Fetch market status on mount:**
```typescript
useEffect(() => {
  marketStatusService.getMarketStatus()
    .then(setMarketStatus)
    .catch(err => console.error('Failed to fetch market status:', err));
}, []);
```

3. **Add handler for custom date change:**
```typescript
const handleCustomDateRangeChange = async (start: string, end: string) => {
  setCustomDateRange({ start, end });

  // Refetch data with custom dates
  const newData = await marketService.getPriceData(symbol, {
    interval,
    start_date: start,
    end_date: end,
  });

  // Update chart data
  setData(newData.data);
};
```

4. **Update ChartHeader props:**
```typescript
<ChartHeader
  symbol={symbol}
  interval={interval}
  selectedTimezone={selectedTimezone}
  dateSelection={dateSelection}
  onIntervalChange={onIntervalChange}
  onTimezoneChange={setSelectedTimezone}
  onCustomDateRangeChange={handleCustomDateRangeChange}  // NEW
  isIntradayInterval={["1m", "1h"].includes(interval)}    // NEW
  marketStatus={marketStatus}                              // NEW
/>
```

5. **Pass session data to chart:**
```typescript
useChart(
  chartContainerRef,
  chartType,
  handleDateRangeSelect,
  setTooltip,
  interval,
  fibonacciAnalysis,
  data,
  marketStatus,      // NEW: pass for session rendering
  customDateRange,   // NEW: for reference
);
```

---

## Phase 9: End-to-End Testing

**Test Script:** `/tmp/test_complete_workflow.sh`

**Test Cases:**

### 1. Market Status Display
- [ ] Status badge shows correct session (pre/regular/post/closed)
- [ ] Badge color matches session (blue/green/orange/gray)
- [ ] Updates when market opens/closes

### 2. Date Picker Validation
- [ ] Daily interval: date pickers enabled, any range allowed
- [ ] Intraday + market open: date pickers enabled, today only
- [ ] Intraday + market closed: date pickers disabled, "Market Closed" shown

### 3. Custom Date Range
- [ ] Selecting valid range fetches correct data
- [ ] Invalid range (start > end) shows error
- [ ] Invalid format (2025/11/01) shows error
- [ ] Intraday with yesterday shows error

### 4. Market Session Indicators
- [ ] Pre-market bars have blue shading/label
- [ ] Regular hours have green shading/label
- [ ] After-hours have orange shading/label
- [ ] Labels clearly visible and positioned correctly

### 5. Default Behavior
- [ ] Interval buttons still work with default periods
- [ ] Default behavior unchanged when no custom dates

### 6. Edge Cases
- [ ] Empty date range (weekend) handled gracefully
- [ ] API errors show user-friendly messages
- [ ] Market status fetch failure doesn't break UI

---

## Files to Modify

1. `frontend/src/components/chart/ChartHeader.tsx` - Date pickers
2. `frontend/src/components/chart/useChart.ts` - Session indicators
3. `frontend/src/components/TradingChart.tsx` - Integration
4. `frontend/src/services/market.ts` - May need to update getPriceData

---

## Estimated Time

- Phase 6 (Date pickers): 30 min
- Phase 7 (Session indicators): 45 min (depends on charting library capabilities)
- Phase 8 (Integration): 20 min
- Phase 9 (Testing): 15 min

**Total:** ~2 hours

---

## Notes

- Market session indicators may be challenging with lightweight-charts
- Consider using HTML overlay divs as fallback
- Test thoroughly with different market hours scenarios
- Document any limitations in session visualization

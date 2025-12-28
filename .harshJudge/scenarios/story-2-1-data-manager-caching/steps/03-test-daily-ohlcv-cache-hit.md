# Step 03: Test daily OHLCV cache hit

## Description


## Preconditions


## Actions
1. Call GET /api/market/price/AAPL?interval=1d&period=1mo
2. Check Redis for key 'market:daily:AAPL' or similar
3. Call same endpoint again
4. Verify response time < 50ms on second call (cache hit)

**Playwright:**
```javascript
// Add Playwright code here
```

## Expected Outcome
Second call returns cached data with sub-50ms response time

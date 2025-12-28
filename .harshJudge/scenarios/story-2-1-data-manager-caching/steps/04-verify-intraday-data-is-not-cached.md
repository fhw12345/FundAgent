# Step 04: Verify intraday data is NOT cached

## Description


## Preconditions


## Actions
1. Call GET /api/market/price/AAPL?interval=1m&period=1d
2. Check Redis - should NOT have intraday cache key
3. Intraday data should always be fresh (no caching)

**Playwright:**
```javascript
// Add Playwright code here
```

## Expected Outcome
Intraday requests bypass cache and return fresh data each time

# Step 01: Test trend endpoint with default days

## Description


## Preconditions


## Actions
1. Call GET /api/insights/ai_sector_risk/trend
2. Verify response has category_id, days, trend array, metrics object

**Playwright:**
```javascript
// Add Playwright code here
```

## Expected Outcome
Returns TrendResponse with days=30 (default), trend array, and metrics object

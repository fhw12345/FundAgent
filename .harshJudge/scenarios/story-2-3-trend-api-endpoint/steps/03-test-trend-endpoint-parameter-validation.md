# Step 03: Test trend endpoint parameter validation

## Description


## Preconditions


## Actions
1. Call GET /api/insights/ai_sector_risk/trend?days=5 (below minimum)
2. Verify 422 validation error
3. Call GET /api/insights/ai_sector_risk/trend?days=100 (above maximum)
4. Verify 422 validation error

**Playwright:**
```javascript
// Add Playwright code here
```

## Expected Outcome
Returns 422 Unprocessable Entity for days < 7 or > 90

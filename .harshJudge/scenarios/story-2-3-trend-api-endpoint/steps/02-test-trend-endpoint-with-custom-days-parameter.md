# Step 02: Test trend endpoint with custom days parameter

## Description


## Preconditions


## Actions
1. Call GET /api/insights/ai_sector_risk/trend?days=7
2. Verify days=7 in response
3. Call GET /api/insights/ai_sector_risk/trend?days=90
4. Verify days=90 in response

**Playwright:**
```javascript
// Add Playwright code here
```

## Expected Outcome
Endpoint respects days parameter for 7, 14, 30, 60, 90 values

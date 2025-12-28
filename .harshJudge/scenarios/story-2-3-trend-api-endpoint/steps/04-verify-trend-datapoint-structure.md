# Step 04: Verify trend datapoint structure

## Description


## Preconditions


## Actions
1. Parse response from successful trend call
2. Each datapoint should have: date (YYYY-MM-DD), score (0-100), status
3. Verify metrics object has entries for all 6 metrics

**Playwright:**
```javascript
// Add Playwright code here
```

## Expected Outcome
Each TrendDataPoint has date, score, status fields; all 6 metrics present

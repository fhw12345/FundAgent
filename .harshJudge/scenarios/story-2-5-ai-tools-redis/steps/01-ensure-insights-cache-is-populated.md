# Step 01: Ensure insights cache is populated

## Description


## Preconditions


## Actions
1. Trigger snapshot if not already cached: POST /api/admin/insights/trigger-snapshot
2. Wait 10 seconds for completion
3. Verify Redis has 'insights:ai_sector_risk:latest'

**Playwright:**
```javascript
// Add Playwright code here
```

## Expected Outcome
Redis cache contains latest insights snapshot

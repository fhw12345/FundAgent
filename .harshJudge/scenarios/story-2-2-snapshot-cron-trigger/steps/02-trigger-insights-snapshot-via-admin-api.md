# Step 02: Trigger insights snapshot via admin API

## Description


## Preconditions


## Actions
1. Get auth token from localStorage or session
2. Call POST /api/admin/insights/trigger-snapshot with admin header
3. Verify 202 Accepted response with run_id

**Playwright:**
```javascript
// Add Playwright code here
```

## Expected Outcome
Returns 202 Accepted with run_id like 'snapshot_20251228_143000'

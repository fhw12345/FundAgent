# Step 03: Verify MongoDB snapshot created

## Description


## Preconditions


## Actions
1. Wait 10 seconds for background task to complete
2. Execute: docker compose exec mongodb mongosh --eval "db.insight_snapshots.findOne({category_id: 'ai_sector_risk'})"
3. Verify document has composite_score, composite_status, metrics fields

**Playwright:**
```javascript
// Add Playwright code here
```

## Expected Outcome
MongoDB contains snapshot with all 6 metrics and composite score

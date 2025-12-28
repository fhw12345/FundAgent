# Step 04: Verify Redis cache updated

## Description


## Preconditions


## Actions
1. Execute: docker compose exec redis redis-cli GET 'insights:ai_sector_risk:latest'
2. Verify JSON data present with composite_score, metrics
3. Check TTL: redis-cli TTL 'insights:ai_sector_risk:latest' (should be ~86400)

**Playwright:**
```javascript
// Add Playwright code here
```

## Expected Outcome
Redis has cached snapshot with 24-hour TTL

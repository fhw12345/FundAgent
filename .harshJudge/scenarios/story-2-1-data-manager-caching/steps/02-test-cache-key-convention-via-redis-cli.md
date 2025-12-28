# Step 02: Test cache key convention via Redis CLI

## Description


## Preconditions


## Actions
1. Execute: docker compose exec redis redis-cli KEYS '*'
2. Verify keys follow pattern: {domain}:{granularity}:{symbol}
3. Look for keys like 'market:daily:*', 'macro:treasury:*', 'insights:*'

**Playwright:**
```javascript
// Add Playwright code here
```

## Expected Outcome
Redis keys follow the {domain}:{type}:{identifier} naming convention

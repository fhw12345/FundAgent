# Step 02: Clear PCR cache and verify cache miss

## Description


## Preconditions


## Actions
1. Connect to Redis container
2. Delete any existing PCR cache keys: DEL market:pcr:NVDA
3. Verify the key is deleted

**Playwright:**
```javascript
// Add Playwright code here
```

## Expected Outcome
Redis key market:pcr:NVDA is deleted (returns 0 or 1)

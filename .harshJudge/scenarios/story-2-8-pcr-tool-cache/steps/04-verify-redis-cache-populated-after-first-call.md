# Step 04: Verify Redis cache populated after first call

## Description


## Preconditions


## Actions
1. Check Redis for key: market:pcr:NVDA
2. Verify the cached data structure contains:
   - symbol, current_price, atm_zone_low, atm_zone_high
   - put_notional_mm, call_notional_mm, contracts_analyzed
   - pcr, interpretation, calculated_at
3. Check TTL is approximately 3600 seconds

**Playwright:**
```javascript
// Add Playwright code here
```

## Expected Outcome
Redis contains market:pcr:NVDA with valid PCR data structure and ~1 hour TTL

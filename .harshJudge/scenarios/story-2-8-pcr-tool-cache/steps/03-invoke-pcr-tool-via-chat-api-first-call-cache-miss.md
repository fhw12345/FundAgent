# Step 03: Invoke PCR tool via chat API - first call (cache miss)

## Description


## Preconditions


## Actions
1. Login to get auth token
2. Create a new chat session
3. Send message: 'What is the put/call ratio for NVDA?'
4. Capture the agent's tool call and response
5. Check backend logs for 'pcr' cache miss indication

**Playwright:**
```javascript
// Add Playwright code here
```

## Expected Outcome
Agent invokes get_put_call_ratio tool, returns rich markdown with PCR value, ATM zone, notionals

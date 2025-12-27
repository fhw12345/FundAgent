# Step 05: Verify Database Message Records

## Description


## Preconditions
Agent query completed

## Actions
1. Connect to MongoDB: docker compose exec mongodb mongosh
2. Use financial_agent database
3. Query messages collection for recent messages
4. Verify user message and assistant response exist

**Playwright:**
```javascript
// Add Playwright code here
```

## Expected Outcome
Database contains:
- User message with 'AAPL' query
- Assistant message with price response
- Proper chat_id linking
Capture query results as JSON evidence.

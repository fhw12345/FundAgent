# Fixed Bugs

## Tencent Cloud SES Authentication Failure - Fixed 2025-10-07

**Problem**: Email verification failing in test environment with `AuthFailure.SignatureFailure` but working locally

**Root Cause**: Different Tencent Cloud credentials between environments:
- Local: `AKID*****` (configured with domain/sender/template)
- Test: `AKID*****` (unconfigured account)

**Solution**: Updated Kubernetes secret directly with working credentials
```bash
# Check current credentials
kubectl get secret app-secrets -n klinematrix-test -o jsonpath='{.data.tencent-secret-id}' | base64 -d

# Update with working credentials from local environment
kubectl delete secret app-secrets -n klinematrix-test
kubectl create secret generic app-secrets -n klinematrix-test \
  --from-literal=tencent-secret-id='<working-secret-id>' \
  --from-literal=tencent-secret-key='<working-secret-key>' \
  # ... other secrets

# Restart backend
kubectl rollout restart deployment/backend -n klinematrix-test
```

**Lesson**: When cloud environment diverges from local, compare credentials/config first. Don't overengineer - direct secret update was sufficient. ExternalSecrets was already broken; use manual update until workload identity is properly configured.

**Verification**:
```bash
curl -X POST https://klinematrix.com/api/auth/send-code \
  -H "Content-Type: application/json" \
  -d '{"auth_type": "email", "identifier": "test@example.com"}'
# Expected: {"message":"Verification code sent to test@example.com","code":null}
```

---

## MongoDB Database Name Parsing with Query Parameters - Fixed 2025-10-07

**Problem**: Registration failing with "Database name contains invalid character" error in Cosmos DB

**Root Cause**: Database name extraction didn't strip MongoDB URL query parameters:
- Local: `mongodb://host/financial_agent` → Works ✅ (no query params)
- Cosmos DB: `mongodb://host/klinematrix_test?ssl=true&...` → Fails ❌ (has query params)

**Bug existed in TWO places**:
1. `backend/src/core/config.py` line 89: `return self.mongodb_url.split("/")[-1]`
2. `backend/src/database/mongodb.py` line 25: `database_name = mongodb_url.split("/")[-1]`

**Solution**: Strip query parameters in both files
```python
# Before
database_name = mongodb_url.split("/")[-1]
# Returns: "klinematrix_test?ssl=true&replicaSet=globaldb&..."

# After
db_with_params = mongodb_url.split("/")[-1]
database_name = db_with_params.split("?")[0] if "?" in db_with_params else db_with_params
# Returns: "klinematrix_test"
```

**Files Changed**:
- `backend/src/core/config.py` (config property - line 89-91)
- `backend/src/database/mongodb.py` (connection logic - line 24-46)
- `backend/src/core/exceptions.py` (NEW - custom exception hierarchy)

**Why it worked locally**: Local MongoDB URLs don't have query parameters, hiding the bug. Cosmos DB requires `?ssl=true&replicaSet=globaldb` which exposed the issue.

**Additional Improvements** (v0.4.1):
- Added `ConfigurationError` exception for invalid database name detection
- Added validation to check for `?`, `&`, `=` characters in database name
- Enhanced logging with `raw_url_suffix` and `parsed_db_name` fields
- Log when query parameters are stripped: `"Database name extracted from URL"`
- Proper error categorization (ConfigurationError vs DatabaseError)

**Verification**:
```bash
# Check logs show correct database name
kubectl logs deployment/backend -n klinematrix-test | grep database
# Should show: "database": "klinematrix_test" (not "klinematrix_test?ssl=...")

# Test registration
curl -X POST https://klinematrix.com/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","code":"123456","username":"testuser","password":"password123"}'
# Should work without "Database name contains invalid character" error
```

---

## Frontend API URL Fallback to Localhost - Fixed 2025-10-07

**Problem**: Frontend showing CORS error trying to reach `http://localhost:8000` instead of using relative URLs

**Root Cause**: JavaScript falsy check treated empty string as falsy:
```typescript
const API_BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";
// VITE_API_URL="" is falsy, so fallback to localhost:8000
```

**Why it happened**:
- Docker build sets `VITE_API_URL=""` for relative URLs
- Empty string is falsy in JavaScript
- Code falls back to localhost:8000
- Browser tries to connect to user's local machine instead of backend API

**Solution**: Change fallback to empty string
```typescript
// Before
const API_BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

// After
const API_BASE_URL = import.meta.env.VITE_API_URL || "";
```

**File Changed**: `frontend/src/services/authService.ts`

**Architecture reminder**:
```
User Browser → https://klinematrix.com (Ingress)
    ├─ /api/* → backend-service:8000 → backend pod
    └─ /* → frontend-service:80 → frontend pod (static files only)
```

Frontend and backend run in **separate pods**. Frontend JavaScript runs in **user's browser**, not in the pod.

**Verification**:
```bash
# Rebuild frontend
az acr build --registry financialAgent \
  --image klinematrix/frontend:test-v0.4.0 \
  --build-arg VITE_API_URL="" \
  --target production \
  --file frontend/Dockerfile frontend/

# Restart frontend
kubectl delete pod -l app=frontend -n klinematrix-test

# Test - should use relative URL (no CORS error)
# Check browser DevTools: Network tab should show requests to /api/auth/send-code (relative)
```

---

## Chat Restoration Not Working - Symbol/Chart/Overlays Not Syncing - Fixed 2025-10-07

**Problem**: When switching between chats, the symbol, chart data, and Fibonacci overlays were not restoring correctly

**Symptoms**:
1. Symbol in search bar not updating when switching chats
2. Fibonacci overlay not rendering even after button click
3. Chart showing wrong stock or empty

**Root Causes** (3 separate issues):

### Issue 1: Metadata Not Being Saved to MongoDB

**Root Cause**: Complete data flow gap - metadata extracted but never sent to backend
```typescript
// Frontend extracted metadata ✅
const metadata = extractFibonacciMetadata(result);

// But API call didn't include it ❌
chatService.sendMessageStreamPersistent(
  response.content,
  chatId || null,
  // ... no metadata parameter!
);
```

**Solution Chain** (5 files):
1. `frontend/src/utils/analysisMetadataExtractor.ts` - NEW FILE
   - Extract only visualization-critical data (1.2KB vs 20KB+)
   - Exclude large price arrays, store only params + results
   - Include `raw_data` with `top_trends` for chart overlay

2. `frontend/src/components/chat/useAnalysis.ts:274-280`
   - Pass metadata to backend via options parameter

3. `frontend/src/services/api.ts:329-360`
   - Add `metadata` field to request body

4. `backend/src/api/schemas/chat_models.py:40-43`
   - Add `metadata: MessageMetadata | dict | None` to ChatRequest

5. `backend/src/api/chat.py:287-294`
   - Pass metadata to `add_message()`

**Compact Metadata Example**:
```javascript
{
  symbol: "AAPL",
  timeframe: "1d",
  start_date: "2024-10-01",
  end_date: "2024-10-07",
  fibonacci_levels: [{level: 0.236, price: 225.5}, ...],
  swing_high: {price: 235, date: "2024-10-05"},
  swing_low: {price: 220, date: "2024-10-01"},
  trend_direction: "uptrend",
  raw_data: {
    top_trends: [...] // For chart overlay visualization
  }
  // Explicitly exclude: price_data (large array ~20KB)
}
```

### Issue 2: Backend Not Auto-Updating UI State

**Root Cause**: UI state `current_symbol` remained `null` even after saving analysis metadata

**Why**: Backend saved message metadata but didn't update chat-level UI state

**Solution**: `backend/src/api/chat.py:297-337`
```python
# Auto-update UI state from analysis metadata
if request.metadata and hasattr(request.metadata, "raw_data"):
    raw_data = request.metadata.raw_data or {}
    symbol = raw_data.get("symbol")
    timeframe = raw_data.get("timeframe")

    if symbol or timeframe:
        # Build active_overlays based on analysis source
        active_overlays = {}
        if request.source == "fibonacci":
            active_overlays["fibonacci"] = {"enabled": True}

        ui_state = UIState(
            current_symbol=symbol,
            current_interval=timeframe or "1d",
            current_date_range={...},
            active_overlays=active_overlays,
        )
        await chat_service.update_ui_state(chat_id, user_id, ui_state)
```

### Issue 3: Conditional State Updates Causing Stale Data

**Root Cause**: Frontend only updated symbol IF new chat had one
```typescript
// BEFORE (BUG)
if (uiState.current_symbol) {
  setCurrentSymbol(uiState.current_symbol);
}
// Chat A: AAPL → Chat B: (no symbol) = Still shows AAPL! ❌
```

**Solution**: `frontend/src/hooks/useChatRestoration.ts:67-74`
```typescript
// Always set symbol (even if empty) to clear old state
setCurrentSymbol(uiState.current_symbol || "");
setCurrentCompanyName(uiState.current_symbol || "");
setSelectedInterval((uiState.current_interval as TimeInterval) || "1d");
```

**Files Changed**:
- NEW: `frontend/src/utils/analysisMetadataExtractor.ts` (metadata extraction)
- NEW: `frontend/src/utils/dateRangeCalculator.ts` (DRY - eliminated 148 lines of duplicate code)
- NEW: `frontend/src/hooks/useChatRestoration.ts` (chat restoration logic)
- NEW: `backend/src/api/schemas/chat_models.py` (API request/response models)
- Modified: `backend/src/api/chat.py` (auto-update UI state)
- Modified: `frontend/src/components/chat/useAnalysis.ts` (use metadata extractors)
- Modified: `frontend/src/services/api.ts` (send metadata to backend)
- Modified: `frontend/src/hooks/useChatRestoration.ts` (always set state with fallback)

**Verification**:
```bash
# Click Fibonacci button - should see in browser console:
📦 Extracting Fibonacci metadata: {hasRawData: true, rawDataKeys: Array(8)}
✅ Button analysis complete: {type: 'fibonacci', hasAnalysisData: true}
🎯 Top trends for overlay: (3) [{…}, {…}, {…}]

# Switch to another chat and back - should see:
🔄 Restoring chat UI state: {symbol: 'AAPL', interval: '1d', overlays: {fibonacci: {enabled: true}}}
✅ Symbol restored to search bar: AAPL
📊 Fibonacci analysis result: {found: true, fibonacciData: {...}}
📈 useChart: Rendering Fibonacci overlay: {hasFibonacciAnalysis: true, topTrendsCount: 3}
```

---

## CORS Blocking PATCH Requests - Fixed 2025-10-07

**Problem**: Frontend unable to sync UI state to MongoDB - CORS error on PATCH requests

**Error**:
```
Access to XMLHttpRequest at 'http://localhost:8000/api/chat/chats/{chatId}/ui-state'
from origin 'http://localhost:3000' has been blocked by CORS policy:
Response to preflight request doesn't pass access control check
```

**Root Cause**: PATCH method not in CORS allowed methods list

`backend/src/main.py:114`
```python
allow_methods=["GET", "POST", "PUT", "DELETE"],  # ❌ Missing PATCH!
```

**Solution**: Add PATCH to allowed methods
```python
allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
```

**Why it happened**: UI state sync endpoint uses PATCH (RFC 5789 - partial updates), but CORS middleware didn't allow it

**Verification**:
```bash
# Backend logs should show:
INFO: OPTIONS /api/chat/chats/{chatId}/ui-state HTTP/1.1" 200 OK  ✅
INFO: PATCH /api/chat/chats/{chatId}/ui-state HTTP/1.1" 200 OK   ✅

# Browser console should show:
💾 UI state synced to MongoDB: {chatId: '...', symbol: 'AAPL', interval: '1d'}
# (No CORS error)
```

---

## Infinite Loop in UI State Sync - Fixed 2025-10-07

**Problem**: UI state sync triggering infinitely, flooding backend with PATCH requests

**Symptom**:
```
💾 UI state synced to MongoDB: {chatId: '...'}
💾 UI state synced to MongoDB: {chatId: '...'}
💾 UI state synced to MongoDB: {chatId: '...'}
... (repeating indefinitely)
```

**Root Cause**: `updateMutation` object in useEffect dependency array

`frontend/src/hooks/useUIStateSync.ts:76-81` (BEFORE):
```typescript
useEffect(() => {
  // Debounce and sync logic...
}, [
  activeChatId,
  currentSymbol,
  selectedInterval,
  selectedDateRange,
  updateMutation,  // ❌ This changes on every mutation!
]);
```

**Why it looped**:
1. Effect runs → calls `updateMutation.mutate()`
2. Mutation creates NEW `updateMutation` object
3. Dependency changed → effect runs again
4. Infinite loop! 🔁

**Solution**: Remove `updateMutation` from dependencies
```typescript
useEffect(() => {
  // Debounce and sync logic...
  // eslint-disable-next-line react-hooks/exhaustive-deps
}, [
  activeChatId,
  currentSymbol,
  selectedInterval,
  selectedDateRange.start,  // Track actual values
  selectedDateRange.end,    // not object reference
  // Note: updateMutation.mutate is stable, no need to include
]);
```

**File Changed**: `frontend/src/hooks/useUIStateSync.ts:76-84`

**Verification**:
```bash
# Browser console should show ONCE per change:
💾 UI state synced to MongoDB: {chatId: '...', symbol: 'AAPL', interval: '1d'}
# (Not repeating)
```

**Lesson**: React Query mutation objects are recreated on every mutation. Use `mutate` function directly or exclude from dependencies.

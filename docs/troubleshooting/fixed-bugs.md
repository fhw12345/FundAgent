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

---

## Render Loop in Chat Input - Fixed 2025-10-07

**Problem**: Typing in chat input triggered 6+ renders per keystroke, causing laggy typing experience and poor performance

**Symptom**:
```
🚨 RENDER LOOP DETECTED: 6 renders in 1 second
🚨 RENDER LOOP DETECTED: 12 renders in 1 second
```

**Root Cause**: Unstable object references and callbacks causing cascade re-renders

1. **Unstable Object State**: `selectedDateRange` object recreated on every render
   ```typescript
   // BEFORE (BUG)
   const [selectedDateRange, setSelectedDateRange] = useState<{
     start: string;
     end: string;
   }>({ start: "", end: "" });
   // Every render creates NEW object with same values → triggers effects!
   ```

2. **Unstable Callbacks**: Event handlers recreated on every render
   ```typescript
   // BEFORE (BUG)
   const handleSymbolSelect = (symbol: string, name: string) => {
     // New function instance every render
   };
   ```

3. **Cascade Effect**:
   - User types → `message` state updates → parent re-renders
   - New `selectedDateRange` object created → `useUIStateSync` effect sees "change"
   - Effect runs → triggers mutation → parent re-renders again
   - Loop continues! 🔁

**Solution**: Stabilize all object references and callbacks

`frontend/src/components/EnhancedChatInterface.tsx`:
```typescript
// 1. Split object state into primitives
const [dateRangeStart, setDateRangeStart] = useState("");
const [dateRangeEnd, setDateRangeEnd] = useState("");

// 2. Memoize derived object (only recreates when primitives change)
const selectedDateRange = useMemo(
  () => ({ start: dateRangeStart, end: dateRangeEnd }),
  [dateRangeStart, dateRangeEnd],
);

// 3. Stable setter with useCallback
const setSelectedDateRange = useCallback(
  (range: { start: string; end: string }) => {
    setDateRangeStart(range.start);
    setDateRangeEnd(range.end);
  },
  [],
);

// 4. Stabilize all event handlers
const handleSymbolSelect = useCallback((symbol: string, name: string) => {
  setCurrentSymbol(symbol);
  setCurrentCompanyName(name);
  setDateRangeStart("");
  setDateRangeEnd("");
}, []);

const handleQuickAnalysis = useCallback(
  (type: "fibonacci" | "fundamentals" | "macro" | "stochastic") => {
    buttonMutation.mutate(type);
  },
  [buttonMutation.mutate], // Use stable .mutate reference
);
```

**Additional Optimizations**:
- Reduced duplicate query invalidations (only invalidate once after completion)
- Combined MongoDB indexes (user_id + is_archived + last_message_at)
- Skip UI state sync on chat restoration

**Files Changed**:
- `frontend/src/components/EnhancedChatInterface.tsx` (memoization, useCallback)
- `frontend/src/hooks/useUIStateSync.ts` (skip sync on restoration)
- `frontend/src/components/chat/useAnalysis.ts` (optimize invalidations)
- `frontend/src/components/chat/useChatManager.ts` (rename sessionId → chatId)
- `backend/scripts/init_indexes.py` (optimize indexes)

**Verification**:
```bash
# Browser console should show:
✅ Render #1 (1 in last 1s)  # One render per keystroke
✅ Render #2 (1 in last 1s)
✅ Render #3 (1 in last 1s)
# (Not 6+ renders per keystroke)

# When selecting chat:
🔄 Chat changed, skipping initial sync
# (Not "💾 UI state synced" on restoration)
```

**Version**: Frontend v0.4.3, Backend v0.4.2

---

## Concurrent Chat Restoration Request Spam - Fixed 2025-10-07

**Problem**: Massive OPTIONS preflight request spam when switching between chats rapidly

**Symptom**:
```
INFO: 183.47.101.192 - "OPTIONS /api/chat/chats/chat_01a08def1afc HTTP/1.1" 200 OK
INFO: 183.47.101.192 - "OPTIONS /api/chat/chats/chat_01a08def1afc HTTP/1.1" 200 OK
INFO: 183.47.101.192 - "OPTIONS /api/chat/chats/chat_01a08def1afc HTTP/1.1" 200 OK
... (10+ duplicate requests per second)
```

**Root Cause**: No concurrent request protection allowing overlapping chat restoration requests

1. **Double-click/Rapid Switching**: User rapidly clicking chat items
2. **Component Re-renders**: State updates triggering handleChatSelect multiple times
3. **React Query Aggressive Refetching**: useChatDetail refetching on mount/focus/reconnect

**Solution**: Add concurrent request protection and optimize query behavior

`frontend/src/components/EnhancedChatInterface.tsx`:
```typescript
const isRestoringRef = useRef(false);

const handleChatSelect = useCallback(
  async (chatId: string) => {
    // Prevent concurrent restoration requests
    if (isRestoringRef.current) {
      console.log("⏭️ Skipping chat select: restoration in progress");
      return;
    }

    isRestoringRef.current = true;
    try {
      await restoreChat(chatId);
    } finally {
      isRestoringRef.current = false;
    }
  },
  [restoreChat],
);
```

`frontend/src/hooks/useChats.ts`:
```typescript
export function useChatDetail(chatId: string | null, limit?: number) {
  return useQuery({
    queryKey: chatId ? chatKeys.detail(chatId) : [],
    queryFn: () => {
      if (!chatId) throw new Error("Chat ID is required");
      return chatService.getChatDetail(chatId, limit);
    },
    enabled: !!chatId,
    staleTime: 2 * 60 * 1000,
    gcTime: 5 * 60 * 1000,
    refetchOnMount: false,      // Prevent refetch on mount
    refetchOnWindowFocus: false, // Prevent refetch on focus
    refetchOnReconnect: false,   // Prevent refetch on reconnect
  });
}
```

**Files Changed**:
- `frontend/src/components/EnhancedChatInterface.tsx` (concurrent protection)
- `frontend/src/hooks/useChats.ts` (disable aggressive refetching)

**Verification**:
```bash
# Backend logs should show clean flow:
INFO: Chat detail retrieved {"chat_id": "chat_b30b1155b888", "message_count": 1}
INFO: GET /api/chat/chats/chat_b30b1155b888 HTTP/1.1" 200 OK
INFO: GET /api/market/price/MSFT?interval=1d&period=6mo HTTP/1.1" 200 OK
# (Single request per chat selection, not 10+)

# Browser console:
⏭️ Skipping chat select: restoration in progress
# (If user rapidly clicks)
```

**Version**: Frontend v0.4.4

---

## Backend Chat Legacy Import Error - Fixed 2025-10-07

**Problem**: Backend container restarting in loop, failing to start

**Error**:
```
ModuleNotFoundError: No module named 'src.api.chat_legacy'
```

**Root Cause**: main.py still importing chat_legacy_router which was removed in previous refactoring (replaced with persistent MongoDB chat)

`backend/src/main.py` (BEFORE):
```python
from .api.chat_legacy import router as chat_legacy_router  # ❌ Module doesn't exist
...
app.include_router(chat_legacy_router)  # ❌ Trying to register removed router
```

**Solution**: Remove chat_legacy import and router registration

```python
# Removed import
# Removed: from .api.chat_legacy import router as chat_legacy_router

# Removed router registration
# Removed: app.include_router(chat_legacy_router)
```

**Why it happened**: chat_legacy.py was removed during MongoDB persistent chat migration, but main.py references weren't cleaned up

**Files Changed**:
- `backend/src/main.py` (remove import and router registration)

**Verification**:
```bash
# Backend should start successfully:
docker compose ps backend
# STATUS: Up 10 seconds (healthy)

# Health check should pass:
curl https://klinematrix.com/api/health
# {"status": "healthy"}
```

**Version**: Backend v0.4.2

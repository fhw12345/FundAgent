# Symbol Injection Race Condition Fix

**Date**: 2025-11-28
**Issue**: Agent analyzed wrong symbol (AAPL instead of GOOG)
**Root Cause**: Race condition between UI state sync and chat message
**Solution**: Pass symbol directly in chat request body

## Problem Description

### Symptom
User selects GOOG in the UI, chart loads successfully, then sends message "should I buy it". The Agent responds with analysis of **AAPL** instead of GOOG.

### Investigation
Checking MongoDB for `chat_df77c60769b7`:
```javascript
db.chats.findOne({chat_id: "chat_df77c60769b7"}, {ui_state: 1, last_message_preview: 1})
// Result: ui_state.current_symbol = "GOOG", but last_message_preview mentions AAPL
```

Backend logs revealed the timing issue:
```
00:31:00.123 - POST /api/chat/stream (message: "should I buy it")
00:31:00.125 - PATCH /api/chat/chats/{id}/ui-state (symbol: GOOG)
00:31:00.130 - Agent reads ui_state from DB → empty/stale value
00:31:00.200 - PATCH completes, GOOG saved to DB
```

### Root Cause
The frontend had two independent operations:
1. `flushUIState()` - PATCH request to save symbol to MongoDB
2. `chatMutation.mutate()` - POST request to send chat message

These fired simultaneously. The Agent read `ui_state` from DB **before** the PATCH completed, resulting in empty/stale symbol context.

## Solution

### Approach: Request-Based Symbol Injection

Instead of relying on DB state synchronization, pass the symbol **directly in the chat request body**. This eliminates timing dependencies entirely.

**Priority Order:**
1. `request.current_symbol` (from request body) - **Primary**
2. `chat.ui_state.current_symbol` (from DB) - **Fallback** for page reload restoration

### Implementation

#### 1. Backend Schema (`backend/src/api/schemas/chat_models.py`)

```python
class ChatRequest(BaseModel):
    message: str
    chat_id: str | None = None
    # ... other fields ...

    # Symbol Context (eliminates race condition)
    current_symbol: str | None = Field(
        None,
        description="Current symbol selected in UI. Takes priority over DB ui_state.",
    )
```

#### 2. Backend Logic (`backend/src/api/chat.py`)

```python
async def _get_active_symbol_instruction(
    chat_id: str,
    user_id: str,
    chat_service: ChatService,
    request_symbol: str | None = None,  # NEW parameter
) -> str:
    # Priority 1: Use request symbol (avoids race condition)
    if request_symbol:
        logger.info("Using symbol from request (priority)", symbol=request_symbol)
        # Also update DB for future restoration
        await chat_service.update_ui_state(
            chat_id, user_id, UIState(current_symbol=request_symbol)
        )
        return _build_symbol_context_instruction(request_symbol)

    # Priority 2: Fallback to DB ui_state
    chat = await chat_service.get_chat(chat_id, user_id)
    if chat and chat.ui_state and chat.ui_state.current_symbol:
        logger.info("Using symbol from DB (fallback)", symbol=chat.ui_state.current_symbol)
        return _build_symbol_context_instruction(chat.ui_state.current_symbol)

    return ""
```

#### 3. Frontend API (`frontend/src/services/api.ts`)

```typescript
sendMessageStreamPersistent(
  message: string,
  chatId: string | null,
  // ... callbacks ...
  options?: {
    // ... other options ...
    current_symbol?: string;  // NEW: Symbol context
  },
): () => void {
  // ...
  body: JSON.stringify({
    message,
    chat_id: chatId,
    // Symbol Context (priority over DB ui_state)
    current_symbol: options?.current_symbol,
  }),
}
```

#### 4. Frontend Hook (`frontend/src/components/chat/useAnalysis.ts`)

```typescript
const { sendAnalysisMessage } = useSendMessage({
  // ... config ...
  options: {
    // ... other options ...
    current_symbol: currentSymbol || undefined,  // Pass symbol in request
  },
});
```

#### 5. Remove Unnecessary Flush (`frontend/src/components/EnhancedChatInterface.tsx`)

```typescript
// Before: Race condition
const handleSendMessage = useCallback(() => {
  flushUIState();  // PATCH fires
  chatMutation.mutate(message);  // POST fires simultaneously
}, [...]);

// After: No race condition
const handleSendMessage = useCallback(() => {
  // Symbol passed directly in request body (current_symbol field)
  // No need to flush UI state
  chatMutation.mutate(message);
  setMessage("");
}, [message, chatMutation]);
```

## Data Flow Comparison

### Before (Race Condition)
```
User selects GOOG → UI state updated locally
User sends message → Two parallel requests:
  ├─ PATCH /ui-state {symbol: GOOG}     ─┐
  └─ POST /chat/stream {message: "..."}  ├─ RACE!
                                         │
Agent reads DB ui_state ←────────────────┘ (may be empty/stale)
```

### After (Fixed)
```
User selects GOOG → UI state updated locally
User sends message → Single request:
  └─ POST /chat/stream {message: "...", current_symbol: "GOOG"}
                                         │
Agent uses request.current_symbol ←──────┘ (always correct)
Backend also saves to DB (for page reload restoration)
```

## Testing

### Local Verification
```bash
# Get auth token
TOKEN=$(docker compose exec backend curl -s -X POST "http://localhost:8000/api/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"username":"allenpan","password":"admin123"}' | jq -r '.access_token')

# Test with current_symbol
docker compose exec backend curl -s -X POST "http://localhost:8000/api/chat/stream" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"message":"should i buy this stock?","current_symbol":"MSFT","agent_version":"v3"}' | head -20
```

Expected output shows all tools using MSFT:
```json
{"type": "tool_start", "tool_name": "get_company_overview", "symbol": "MSFT", ...}
{"type": "tool_start", "tool_name": "get_news_sentiment", "symbol": "MSFT", ...}
```

### MongoDB Verification
```javascript
// After sending message with current_symbol: "MSFT"
db.chats.findOne({chat_id: "chat_xxx"}, {ui_state: 1})
// Should show: ui_state.current_symbol = "MSFT"
```

## Deployment

| Component | Version | Image Tag |
|-----------|---------|-----------|
| Backend   | 0.8.2   | `prod-v0.8.2` |
| Frontend  | 0.11.2  | `prod-v0.11.2` |

## Related Files

- `backend/src/api/schemas/chat_models.py` - ChatRequest schema
- `backend/src/api/chat.py` - `_get_active_symbol_instruction()` function
- `frontend/src/services/api.ts` - `sendMessageStreamPersistent()` method
- `frontend/src/components/chat/useAnalysis.ts` - Symbol passing
- `frontend/src/components/EnhancedChatInterface.tsx` - Message handler

## Lessons Learned

1. **Avoid relying on DB state for real-time operations** - Pass critical context directly in requests
2. **Debounced syncs are unreliable for immediate operations** - Even with `flush`, race conditions can occur
3. **Request parameters > DB state** - For time-sensitive data, request body is always more reliable
4. **DB sync is for restoration, not real-time** - Use DB for page reload restoration, not immediate operations

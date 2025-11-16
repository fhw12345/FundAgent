# Streaming Issues Troubleshooting Guide

> **Status:** Active
> **Last Updated:** 2025-01-16
> **Applies To:** Backend v0.5.14+, Frontend v0.10.1+

This guide covers common issues with Server-Sent Events (SSE) streaming in the chat interface, particularly with ReAct Agent (v3) tool execution.

---

## Quick Reference

| Issue ID | Symptom | Quick Fix |
|----------|---------|-----------|
| [STREAM001](#stream001-sse-streaming-stops-prematurely) | LLM response missing after tool execution | Check generator loops, add agent completion checks |
| [PERF001](#perf001-high-sse-event-count) | Slow streaming, high network overhead | Implement batch chunk streaming (CHUNK_SIZE=10) |
| [RELI001](#reli001-memory-exhaustion-queue-overflow) | Memory growth, system slowdown | Add circuit breaker (MAX_QUEUE_SIZE=100) |

---

## STREAM001: SSE Streaming Stops Prematurely

### Symptoms
- Tool progress cards appear correctly
- Final LLM response never streams
- Browser shows "❌ Error: network error" or connection timeout
- Backend logs show "Starting tool event streaming loop" but no completion message

### Environment
- Agent mode v3 with tool execution enabled
- User sends chat message triggering ReAct agent
- Occurs intermittently or consistently after tool execution

### Root Cause
**Multiple potential causes (check in this order):**

1. **Generator Early Exit** - Break statement in outer loop exits entire generator function before streaming final answer
2. **Deadlock in Background Streaming** - Background task stuck in infinite loop after last tool event, never checking agent completion
3. **Assistant Message Displacement** - Tool progress messages inserted displacing assistant placeholder, causing state corruption

### Diagnosis

**Step 1: Check Backend Logs**
```bash
docker compose logs backend --tail=100 | grep -E "Starting tool event|Agent completed|Finished streaming"
```

Expected output:
```
Starting tool event streaming loop
Agent completed, stopping tool event stream
Tool event streaming completed
Starting to stream final answer
Finished streaming final answer
```

If you see "Starting tool event streaming loop" without "Agent completed", you have a **deadlock**.

**Step 2: Check Generator Loop Structure**
```bash
grep -A20 "async for tool_event in stream_tool_events_background" backend/src/api/chat.py
```

Look for:
- ❌ `break` statement in outer loop (exits entire generator)
- ✅ Generator should naturally exit when background task completes

**Step 3: Check Timeout Handler**
```bash
grep -A10 "except asyncio.TimeoutError" backend/src/api/chat.py
```

Required pattern:
```python
except asyncio.TimeoutError:
    if agent_task and agent_task.done():
        stream_active = False
        break
    continue
```

### Resolution

#### Fix 1: Remove Early Break (Generator Exit)
**File:** `backend/src/api/chat.py`

```python
# ❌ WRONG: Break exits entire generator
async for tool_event in stream_tool_events_background():
    yield tool_event
    if agent_task.done():
        break  # Exits generator - final answer never streams!

# ✅ CORRECT: Let generator auto-exit when background completes
async for tool_event in stream_tool_events_background():
    yield tool_event
# Generator continues after loop, streams final answer
```

#### Fix 2: Add Agent Completion Check (Deadlock)
**File:** `backend/src/api/chat.py:783-789`

```python
async def stream_tool_events_background():
    while stream_active:
        try:
            event = await asyncio.wait_for(tool_event_queue.get(), timeout=0.1)
            yield f"data: {json.dumps(event)}\n\n"
        except asyncio.TimeoutError:
            # CRITICAL: Check if agent completed
            if agent_task and agent_task.done():
                logger.info("Agent completed, stopping tool event stream")
                stream_active = False
                break
            continue  # Keep waiting for events
```

#### Fix 3: Preserve Assistant Placeholder
**File:** `frontend/src/components/chat/useAnalysis.ts:168-175`

```typescript
setMessages((prev) => {
  // Find and preserve assistant placeholder (may have accumulated content)
  const placeholder = prev.find(msg => msg._id === assistantMessageId);
  const withoutPlaceholder = prev.filter(msg => msg._id !== assistantMessageId);

  // Insert tool message, then re-add placeholder at end
  return [...withoutPlaceholder, toolProgressMessage, placeholder || assistantMessageObj];
});
```

### Verification

1. **Restart Backend**
   ```bash
   docker compose restart backend
   ```

2. **Test in Browser**
   - Open http://localhost:3000
   - Login (allenpan/admin123)
   - Enable Agent Mode v3 in settings
   - Send: "Analyze AAPL stock"
   - **Expected:** Tool cards appear → Final LLM response streams

3. **Monitor Logs**
   ```bash
   docker compose logs -f backend | grep -E "tool event|Agent|streaming"
   ```

### Prevention Tips
- Always add debug logging at each streaming pipeline step
- Monitor for "Starting" without corresponding "Completed" messages
- Test agent mode after any changes to streaming logic
- Use flushSync() in React for immediate state updates

---

## PERF001: High SSE Event Count

### Symptoms
- Streaming works but feels slow
- Browser DevTools → Network shows 1000+ SSE events per response
- High CPU usage during streaming
- Network tab shows excessive HTTP/2 frames

### Environment
- Production with long LLM responses (>1000 characters)
- Any chat request with substantial response
- More noticeable on slower networks

### Root Cause
**Character-by-character streaming** creates one SSE event per character:
- 1300-character response = 1300 SSE events
- Each event has HTTP/2 frame overhead
- Frontend processes 1300 state updates

### Diagnosis

**Check Current Implementation**
```bash
grep -A5 "for char in final_answer" backend/src/api/chat.py
```

If you see character-by-character loop, you have this issue.

**Measure Event Count in Browser**
1. Open DevTools → Network
2. Filter by "Fetch/XHR"
3. Send chat message
4. Click streaming request → Preview tab
5. Count events (scroll to see total)

**Benchmark:** Typical 1300-char response should produce ~130 events, not 1300.

### Resolution

**Implement Batch Chunk Streaming**

**File:** `backend/src/api/chat.py:928-943`

```python
# ❌ OLD: Character-by-character (1300 events)
for char in final_answer:
    chunk = {"type": "chunk", "content": char}
    yield f"data: {json.dumps(chunk)}\n\n"
    await asyncio.sleep(0.01)

# ✅ NEW: Batched chunks (130 events - 90% reduction)
CHUNK_SIZE = 10
for i in range(0, len(final_answer), CHUNK_SIZE):
    chunk_text = final_answer[i : i + CHUNK_SIZE]
    chunk = {"type": "chunk", "content": chunk_text}
    yield f"data: {json.dumps(chunk)}\n\n"
    await asyncio.sleep(0.03)  # Proportional delay (10 chars → 0.03s)
```

**Why CHUNK_SIZE=10?**
- Still maintains smooth "typewriter" effect
- 90% reduction in events (1300 → 130)
- Proportional delay feels natural (0.03s for 10 chars ≈ 0.01s × 10)
- Balance between batching efficiency and UX smoothness

### Verification

**Before/After Comparison**

```bash
# Before: Count events manually
# Open browser DevTools → Network → filter "chat"

# After: Should see ~90% reduction
# 1300-char response: 1300 events → 130 events
```

**Performance Metrics**
- Network overhead: 90% reduction in HTTP/2 frames
- CPU usage: Lower frontend state update frequency
- Memory: Fewer React renders
- UX: Still smooth (indistinguishable from char-by-char)

### Prevention Tips
- Always batch streaming data when possible
- Individual character streaming only for extreme typewriter effect
- Monitor network DevTools during development
- Set CHUNK_SIZE based on response length expectations

---

## RELI001: Memory Exhaustion / Queue Overflow

### Symptoms
- Backend memory usage grows continuously
- System slowdown over time
- Queue size warnings in logs
- Eventual crashes or OOM errors

### Environment
- Production with slow consumers or network congestion
- Multiple concurrent agent invocations
- High-load scenarios (many simultaneous users)

### Root Cause
**Unbounded Event Queue** - Producer (agent) generates events faster than consumer (SSE stream) can process:
- Each tool execution adds events to queue
- If network slow or client disconnected, queue grows
- No circuit breaker to stop growth
- Memory exhaustion inevitable

### Diagnosis

**Check Queue Size Monitoring**
```bash
grep -A10 "tool_event_queue.qsize()" backend/src/api/chat.py
```

If no queue size checks exist, you're vulnerable.

**Monitor Production Logs**
```bash
docker compose logs backend | grep -E "queue|overflow|memory"
```

**Check Memory Usage**
```bash
docker stats backend --no-stream
```

Look for growing MEM USAGE over time.

### Resolution

**Add Circuit Breaker**

**File:** `backend/src/api/chat.py:752-770`

```python
async def stream_tool_events_background():
    nonlocal stream_active, agent_task
    MAX_QUEUE_SIZE = 100  # Circuit breaker threshold

    while stream_active:
        try:
            # Circuit breaker: Check queue size to prevent overflow
            queue_size = tool_event_queue.qsize()
            if queue_size > MAX_QUEUE_SIZE:
                logger.error(
                    "Event queue overflow - circuit breaker triggered",
                    queue_size=queue_size,
                    max_size=MAX_QUEUE_SIZE,
                )
                # Drain queue to prevent memory exhaustion
                while not tool_event_queue.empty():
                    try:
                        tool_event_queue.get_nowait()
                    except asyncio.QueueEmpty:
                        break
                stream_active = False
                break

            # Normal event processing
            event = await asyncio.wait_for(tool_event_queue.get(), timeout=0.1)
            yield f"data: {json.dumps(event)}\n\n"
        except asyncio.TimeoutError:
            if agent_task and agent_task.done():
                stream_active = False
                break
            continue
```

**Why MAX_QUEUE_SIZE=100?**
- Expected burst: 10 tools × 10 events/tool = 100 max
- Allows normal operation while preventing runaway growth
- Threshold based on realistic worst-case scenarios

### Verification

**Test Circuit Breaker**

1. **Simulate Slow Consumer**
   ```python
   # In test environment, add artificial delay
   await asyncio.sleep(1)  # Before yielding events
   ```

2. **Trigger Agent with Many Tools**
   ```
   User: "Analyze AAPL, GOOGL, MSFT, TSLA, AMZN - give me full reports"
   ```

3. **Monitor Logs for Circuit Breaker**
   ```bash
   docker compose logs backend | grep "circuit breaker"
   ```

4. **Verify Queue Drains**
   - Should see "Event queue overflow" message
   - Queue should be drained (qsize → 0)
   - stream_active set to False
   - No memory growth

### Prevention Tips
- Always implement circuit breakers for async queues
- Set threshold based on expected burst size
- Monitor queue metrics in production
- Use bounded queues (maxsize parameter) when possible
- Consider backpressure mechanisms for production

---

## Related Documentation

- [Chat Streaming Architecture](../features/chat-streaming-architecture.md)
- [Agent Architecture](../architecture/agent-architecture.md)
- [Deployment Issues](./deployment-issues.md)
- [Frontend Issues](./frontend-issues.md)

---

## Contributing

Found a new streaming issue? Please update this guide:

1. Add issue ID (STREAM00X, PERF00X, RELI00X)
2. Follow template: Symptoms → Root Cause → Resolution → Verification
3. Include code snippets with file paths and line numbers
4. Test resolution before documenting
5. Add to Quick Reference table at top

# Frontend Issues Troubleshooting Guide

> **Status:** Active
> **Last Updated:** 2025-01-16
> **Applies To:** Frontend v0.10.1+

This guide covers common frontend issues in the Financial Agent platform.

---

## Quick Reference

| Issue ID | Symptom | Quick Fix |
|----------|---------|-----------|
| [UX001](#ux001-duplicate-requests-from-rapid-clicks) | Multiple agent invocations from rapid clicks | Add isPending check before mutation |

---

## UX001: Duplicate Requests from Rapid Clicks

### Symptoms
- User rapidly clicks "Send" button multiple times
- Multiple identical chat messages appear
- Multiple agent invocations in backend logs
- User charged credits multiple times for same query
- Concurrent "Analyzing..." indicators

### Environment
- Frontend - any environment (dev/test/prod)
- React Query mutations without deduplication
- Button click handlers without pending state checks

### Root Cause
**No Request Deduplication Check** - `mutation.mutate()` called even if previous request still pending:
- User clicks send button
- First request starts (isPending = true)
- User clicks again before response completes
- Second request starts simultaneously
- Both invoke backend agent
- Double charging, wasted compute

### Diagnosis

**Step 1: Reproduce in Browser**
1. Open http://localhost:3000
2. Login and navigate to chat
3. Type message and **rapidly click Send button 3-5 times**
4. Observe: Multiple duplicate messages appear

**Step 2: Check Backend Logs**
```bash
docker compose logs backend --tail=50 | grep "Agent invocation"
```

Expected (bug): Multiple "Agent invocation" entries with same message
Expected (fixed): Single "Agent invocation", console logs showing "Skipping message submit"

**Step 3: Check Frontend Code**
```bash
grep -B5 -A5 "mutation.mutate" frontend/src/components/EnhancedChatInterface.tsx
```

Look for missing isPending check before mutate().

### Resolution

**Add Request Deduplication**

**File:** `frontend/src/components/EnhancedChatInterface.tsx:201-210`

```typescript
// ❌ OLD: No deduplication check
const handleSendMessage = useCallback(() => {
  if (!message.trim()) return;
  chatMutation.mutate(message);
  setMessage("");
}, [message, chatMutation]);

// ✅ NEW: Request deduplication with isPending check
const handleSendMessage = useCallback(() => {
  if (!message.trim()) return;

  // Request deduplication: Prevent concurrent agent invocations
  if (chatMutation.isPending) {
    console.log("⏭️ Skipping message submit: request already in progress");
    return;
  }

  chatMutation.mutate(message);
  setMessage("");
}, [message, chatMutation]);
```

**Optional Enhancement: Disable Button UI**

```typescript
<Button
  onClick={handleSendMessage}
  disabled={chatMutation.isPending || !message.trim()}
  className="..."
>
  {chatMutation.isPending ? "Sending..." : "Send"}
</Button>
```

### Verification

**Test Deduplication**

1. **Restart Frontend**
   ```bash
   docker compose restart frontend
   ```

2. **Test in Browser**
   - Open http://localhost:3000
   - Login and open chat
   - Type message
   - **Rapidly click Send button 5 times**
   - **Expected:**
     - Only 1 message sent
     - Console shows "⏭️ Skipping message submit" 4 times
     - Only 1 "Analyzing..." indicator

3. **Verify Backend Logs**
   ```bash
   docker compose logs backend --tail=20 | grep "Agent invocation"
   ```
   - Should see only 1 invocation

4. **Verify Credits**
   - Check credit deduction in profile
   - Should be charged once, not multiple times

### Prevention Tips
- **Always check `mutation.isPending`** before calling `mutation.mutate()`
- Apply pattern to ALL mutation handlers (not just chat):
  - Portfolio operations
  - Watchlist updates
  - Feedback submissions
  - Analysis button clicks
- Consider UI-level protection (disabled button state)
- Add rate limiting for additional protection
- Test by rapid-clicking all interactive buttons

### Related Patterns

**Generic Deduplication Pattern**
```typescript
const handleAction = useCallback(() => {
  // Early return if mutation in progress
  if (mutation.isPending) {
    console.log("⏭️ Action already in progress");
    return;
  }

  mutation.mutate(data);
}, [mutation, data]);
```

**Button Analysis Click (Already Protected)**

Note: Button analysis mutations already have deduplication via `mutationKey`:

```typescript
// In useButtonAnalysis hook
const mutation = useMutation({
  mutationKey: ["button-analysis", currentSymbol, selectedInterval, ...],
  // React Query automatically deduplicates mutations with same key
});
```

No additional isPending check needed for button clicks because:
1. React Query deduplicates by `mutationKey`
2. Button disabled state already managed via `isPending`

---

## Related Documentation

- [Streaming Issues](./streaming-issues.md)
- [Chat Architecture](../features/chat-streaming-architecture.md)
- [React Query Best Practices](../development/coding-standards.md)

---

## Contributing

Found a new frontend issue? Please update this guide:

1. Add issue ID (UX00X, UI00X, STATE00X)
2. Follow template: Symptoms → Root Cause → Resolution → Verification
3. Include code snippets with file paths and line numbers
4. Test resolution before documenting
5. Add to Quick Reference table at top

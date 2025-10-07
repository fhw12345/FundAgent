# Architecture Improvements TODO

**Created**: 2025-10-07
**Status**: Deferred from v0.4.0 (critical bugs fixed first)
**Priority**: Medium (non-blocking, improves maintainability)

This document tracks architectural improvements identified during comprehensive code review. These are deferred to future PRs to focus on critical bug fixes first.

## Overview

During the v0.4.0 persistent chat implementation, a comprehensive code review identified several architectural improvements that would enhance code maintainability, reduce complexity, and improve performance. While not critical bugs, addressing these will prevent future issues and make the codebase easier to work with.

## High Priority Improvements

### 1. Reduce Redundant Query Invalidations

**Problem**: Currently invalidating `chatKeys.lists()` 6 times per chat interaction:
- `useAnalysis.ts`: 2x (onChatCreated, onDone)
- `useButtonAnalysis.ts`: 2x (onChatCreated, onDone)
- `chat.py` backend: 2x (after chat creation, after completion)

**Impact**: Unnecessary API calls, wasted bandwidth, potential race conditions

**Solution**:
- Add debounced query invalidation with 500ms delay
- Consolidate to single invalidation per user interaction
- Move invalidation logic to single location (ChatMessages component)

**Files to modify**:
- `frontend/src/hooks/useQueryInvalidation.ts` (new)
- `frontend/src/components/chat/useAnalysis.ts`
- `frontend/src/components/chat/useButtonAnalysis.ts`

**Estimated effort**: 2-3 hours

---

### 2. Fix Backend Service Boundary Confusion

**Problem**: `chat_agent.py` and `chat_service.py` have unclear separation of concerns:
- Agent handles both LLM calls AND business logic
- Service sometimes calls agent, sometimes bypasses it
- Unclear where to add new features

**Impact**: Hard to maintain, unclear where to add features, potential bugs

**Solution**:
- **Agent layer**: ONLY handles LLM streaming (LangChain/LangGraph)
- **Service layer**: ALL business logic (validation, title generation, persistence)
- Service calls Agent for LLM, never the reverse

**Files to modify**:
- `backend/src/agent/chat_agent.py`
- `backend/src/services/chat_service.py`
- `backend/src/api/chat.py`

**Estimated effort**: 4-6 hours

---

### 3. Add Loading States to Async Operations

**Problem**: No loading indicators for:
- Chat restoration from sidebar (can take 1-2 seconds)
- Initial chat list load
- Message send operations

**Impact**: User sees frozen UI, doesn't know if action succeeded

**Solution**:
- Add `isRestoring` state to `useChatRestoration`
- Add loading skeleton for chat list
- Show "Sending..." state in ChatInput

**Files to modify**:
- `frontend/src/hooks/useChatRestoration.ts`
- `frontend/src/components/chat/ChatSidebar.tsx`
- `frontend/src/components/chat/ChatInput.tsx`

**Estimated effort**: 2-3 hours

---

## Medium Priority Improvements

### 4. Extract Magic Numbers to Constants

**Problem**: Hard-coded values scattered throughout code:
- Date calculations: `30 * 24 * 60 * 60 * 1000`
- Intervals: "1h", "1d", "1w", "1mo"
- K/D periods for stochastic: 14, 3

**Impact**: Hard to maintain, easy to make mistakes, unclear meaning

**Solution**:
- Create `frontend/src/constants/intervals.ts`
- Create `frontend/src/constants/analysisDefaults.ts`
- Replace all magic numbers with named constants

**Files to modify**:
- `frontend/src/constants/intervals.ts` (new)
- `frontend/src/constants/analysisDefaults.ts` (new)
- `frontend/src/utils/dateRangeCalculator.ts`
- `frontend/src/components/chat/useAnalysis.ts`

**Estimated effort**: 1-2 hours

---

### 5. Split Bloated EnhancedChatInterface Component

**Problem**: `EnhancedChatInterface.tsx` is 218 lines and does too much:
- Manages all state (symbol, interval, date range, chat)
- Handles all event callbacks
- Renders entire UI structure

**Impact**: Hard to test, hard to understand, violates SRP

**Solution**:
- Extract `useChatState` hook for state management
- Extract `ChatControls` component for symbol/interval selection
- Keep `EnhancedChatInterface` as layout orchestrator only

**Files to create**:
- `frontend/src/hooks/useChatState.ts`
- `frontend/src/components/chat/ChatControls.tsx`

**Files to modify**:
- `frontend/src/components/EnhancedChatInterface.tsx`

**Estimated effort**: 3-4 hours

---

### 6. Fix Company Name Fetching

**Problem**: `useChatRestoration` sets company name to ticker symbol:
```typescript
// TODO: Fetch company name from symbol
setCurrentCompanyName(uiState.current_symbol);
```

**Impact**: UI shows "AAPL" instead of "Apple Inc."

**Solution**:
- Add `GET /api/market/company-info/{symbol}` endpoint
- Fetch company name during chat restoration
- Cache results in React Query

**Files to modify**:
- `backend/src/api/market_data.py`
- `frontend/src/services/market.ts`
- `frontend/src/hooks/useChatRestoration.ts`

**Estimated effort**: 2 hours

---

## Low Priority Improvements

### 7. Add Debounce Cleanup to useUIStateSync

**Problem**: `useUIStateSync` creates debounced function but never cleans up:
```typescript
useEffect(() => {
  const debouncedSync = debounce(syncUIState, 1000);
  debouncedSync();
  // MISSING: return () => debouncedSync.cancel();
}, [dependencies]);
```

**Impact**: Potential memory leak, pending API calls after unmount

**Solution**:
- Add cleanup function to cancel pending debounces
- Use `useCallback` to memoize debounced function

**Files to modify**:
- `frontend/src/hooks/useUIStateSync.ts`

**Estimated effort**: 30 minutes

---

### 8. Create Error Boundaries for React Components

**Problem**: No error boundaries, any error crashes entire app

**Impact**: Poor user experience, no error recovery

**Solution**:
- Create `ErrorBoundary` component
- Wrap main sections (Chat, Chart, Sidebar)
- Show user-friendly error messages with retry

**Files to create**:
- `frontend/src/components/ErrorBoundary.tsx`

**Files to modify**:
- `frontend/src/App.tsx`

**Estimated effort**: 2-3 hours

---

### 9. Delete Backup Files from Repository

**Problem**: Backup files committed to git:
- `*.bak` files
- `*_old.ts` files
- Unused legacy code

**Impact**: Clutters repository, confuses developers

**Solution**:
- Delete all `.bak` and `_old.ts` files
- Add to `.gitignore`
- Update `.gitignore` patterns

**Files to delete**:
- (Run: `find . -name "*.bak" -o -name "*_old.ts"`)

**Files to modify**:
- `.gitignore`

**Estimated effort**: 15 minutes

---

## Implementation Plan

**Recommended order**:
1. **Quick wins** (delete backups, debounce cleanup, magic numbers) - 2 hours total
2. **User-visible improvements** (loading states, company name) - 4-5 hours
3. **Code quality** (reduce query invalidations, split component) - 5-7 hours
4. **Architecture** (backend boundaries, error boundaries) - 6-9 hours

**Total estimated effort**: 17-23 hours

**Suggested approach**: Tackle 1-2 items per PR to keep changes focused and reviewable.

---

## Success Metrics

After completing these improvements:
- [ ] Fewer than 2 query invalidations per user interaction
- [ ] All async operations show loading states
- [ ] No magic numbers in business logic
- [ ] All components under 200 lines
- [ ] Company names display correctly in UI
- [ ] No memory leaks from debounced functions
- [ ] Errors don't crash the entire app
- [ ] Clean git history without backup files

---

## Notes

- These improvements were deferred from v0.4.0 to prioritize critical bug fixes
- All critical bugs (dead code, race conditions, duplicate logic) have been fixed in v0.4.0
- This document should be reviewed and updated as improvements are completed
- New architectural issues should be added to this list as they're discovered

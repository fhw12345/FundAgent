# Transaction Reconciliation Worker - Datetime Deprecation Fix

**Date:** 2025-10-15
**Versions:** Backend v0.5.4
**Severity:** Low (deprecation warning)
**Status:** ✅ Fixed
**Commit:** `debedbc`

## Problem

The transaction reconciliation worker (`src/workers/reconcile_transactions.py`) was using deprecated `datetime.utcnow()` which triggers a DeprecationWarning in Python 3.12:

```
DeprecationWarning: datetime.utcnow() is deprecated and scheduled for removal in a future version. Use timezone-aware objects to represent datetimes in UTC: datetime.datetime.now(datetime.UTC).
```

## Root Cause

Python 3.12 deprecated naive UTC datetime methods in favor of timezone-aware alternatives:
- `datetime.utcnow()` → Deprecated (naive datetime)
- `datetime.now(UTC)` → Modern, timezone-aware

The worker was using the old API, resulting in:
1. Deprecation warnings polluting logs
2. Naive timestamps without timezone information
3. Future incompatibility with Python 3.13+

## Solution

**Code Changes:**
```python
# Before:
from datetime import datetime, timedelta
cutoff_time = datetime.utcnow() - timedelta(minutes=age_minutes)

# After:
from datetime import UTC, datetime, timedelta
cutoff_time = datetime.now(UTC) - timedelta(minutes=age_minutes)
```

**Timestamp Output:**
- Before: `2025-10-15T14:30:52.042490` (naive, no timezone)
- After: `2025-10-15T14:32:37.056411+00:00` (timezone-aware) ✅

## Verification

Tested reconciliation worker with 8 stuck PENDING transactions from 2025-10-14:

**Test Results:**
```
Database: financial_agent
Found 8 PENDING transactions (all from user_57dde4922766)

Transaction Processing:
- txn_fd1267309cf6 → FAILED (no message found)
- txn_31a5a7ffb985 → FAILED (no message found)
- txn_269450dfa4ad → FAILED (no message found)
- txn_e9a57c61c307 → FAILED (no message found)
- txn_dfcc08b2b2d0 → FAILED (no message found)
- txn_f48ad315d206 → FAILED (no message found)
- txn_772d7c5e2d80 → FAILED (no message found)
- txn_356668941680 → FAILED (no message found)

Summary:
✅ Processed: 8 transactions
✅ Failed: 8 (no messages found - LLM calls failed before message saved)
✅ Completed: 0
✅ Skipped: 0
```

**Worker Output (No Warnings):**
```
2025-10-15 14:37:37 [info] MongoDB connection established connection_verified=True database=financial_agent
2025-10-15 14:37:37 [info] MongoDB connected
2025-10-15 14:37:37 [info] Starting transaction reconciliation age_minutes=5 cutoff_time=2025-10-15T14:32:37.056411+00:00
2025-10-15 14:37:37 [info] No stuck transactions found
2025-10-15 14:37:37 [info] Reconciliation worker finished successfully stats={'completed': 0, 'failed': 0, 'skipped': 0}
```

**Second Run (After Cleanup):**
- No stuck transactions found (all 8 were successfully marked as FAILED)
- No deprecation warnings
- Clean logs ✅

## Impact

**Positive:**
- **Logs:** Cleaner output without deprecation warnings
- **Future-Proof:** Compatible with Python 3.13+
- **Precision:** Timezone-aware timestamps provide better accuracy
- **Standards:** Aligns with modern Python datetime best practices

**No Negative Impact:**
- Functionality identical (same behavior, just better timestamps)
- No breaking changes
- No database schema changes needed

## How the Reconciliation Worker Works

**Purpose:**
Cleans up stuck PENDING transactions by completing them with actual token usage or marking them as FAILED.

**Process:**
1. **Find Stuck Transactions** - Queries transactions with status=PENDING older than 5 minutes
2. **Look Up Messages** - Checks if messages exist for each transaction
3. **Decide Action**:
   - ✅ **Message found with tokens** → Complete transaction + deduct credits
   - ❌ **No message found** → Mark as FAILED (LLM call failed before message saved)
   - ⏭️ **Already processed** → Skip (another worker already handled it)

**Deployment:**
- Runs as Kubernetes CronJob (planned)
- Can be run manually: `python -m src.workers.reconcile_transactions`
- Default threshold: 5 minutes (transactions older than this are considered stuck)

## Transaction Status Flow

```
PENDING (created when user sends message)
   ↓
   ├─ LLM call succeeds → Message saved with tokens → COMPLETED
   ├─ LLM call fails → No message → Worker marks as FAILED
   └─ Stuck (no completion after 5 min) → Worker reconciles
```

**Why Transactions Get Stuck:**
1. **LLM API timeout** - DashScope didn't respond in time
2. **Network failure** - Connection lost before message saved
3. **Backend crash** - Pod restarted mid-request
4. **Database error** - Message save failed

## Related Files

**Fixed:**
- `backend/src/workers/reconcile_transactions.py` (datetime.now(UTC) fix)

**Still Using Deprecated API (Future Cleanup):**
- `backend/src/models/*.py` - Pydantic models use utcnow() in validators
- `backend/tests/test_*.py` - Test fixtures use utcnow()

**Note:** These other files generate warnings but are lower priority (not in hot path).

## Prevention

To prevent similar issues in the future:

1. **Pre-commit Hook:** Add ruff rule to detect `datetime.utcnow()` usage
2. **Code Review:** Check for deprecated datetime APIs
3. **Testing:** Run with Python warnings enabled (`python -W default`)
4. **CI/CD:** Add step to fail on deprecation warnings in production code

## References

- **Python Docs:** [datetime.now()](https://docs.python.org/3.12/library/datetime.html#datetime.datetime.now)
- **PEP 615:** Timezone-aware datetime handling
- **Commit:** `debedbc` - fix: replace deprecated datetime.utcnow() with datetime.now(UTC)

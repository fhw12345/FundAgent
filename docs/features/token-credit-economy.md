# Feature Specification: Token-Based Credit Economy

**Status**: Planning
**Priority**: High
**Target Version**: v0.6.0
**Created**: 2025-01-13
**Author**: System Architecture Team

---

## Executive Summary

Implement a token-based credit economy where users pay for AI operations based on actual token consumption. This creates a fair, transparent billing system with ~84% gross margin while providing detailed transaction tracking for support and refunds.

**Key Metrics**:
- **Currency Conversion**: 1元 = 100 Credits
- **Work Conversion**: 1 Credit = 200 Tokens
- **Target Margin**: ~84% gross profit
- **New User Grant**: 1,000 free credits (~10-15 AI conversations)

---

## Context & Problem Statement

### Current State
- ✅ LLM integration working (Alibaba DashScope Qwen-plus)
- ✅ Token usage logged but not persisted
- ✅ User authentication with JWT
- ❌ **No billing system** - unlimited free usage
- ❌ **No cost tracking** - can't calculate expenses
- ❌ **No usage limits** - potential for abuse

### Business Problem
1. **Unsustainable**: Free unlimited AI usage is not viable long-term
2. **No Transparency**: Users don't know what they're consuming
3. **No Revenue**: Cannot monetize premium AI features
4. **Resource Risk**: No protection against abuse or runaway costs

### User Problem
Users need:
- Fair pricing based on actual usage (not flat subscription)
- Transparency on what each request costs
- History of their spending
- Protection from unexpected charges

---

## Proposed Solution

### Economic Model

**Two-Tier Conversion System**:

```
User Money ──→ Credits ──→ AI Work
   1元          100        20,000 tokens
```

**Pricing Examples**:
| Scenario | Input Tokens | Output Tokens | Total | Credits | Cost (元) |
|----------|-------------|---------------|-------|---------|----------|
| Simple query | 100 | 150 | 250 | 1.25 | ¥0.0125 |
| Complex analysis | 500 | 2,000 | 2,500 | 12.5 | ¥0.125 |
| Long conversation | 1,000 | 3,500 | 4,500 | 22.5 | ¥0.225 |

**Free Tier**: New users get 1,000 credits (≈ 200,000 tokens ≈ 10-15 conversations)

### Architecture: Stateful API with Reconciliation

We use a **Stateful API Pattern** where the API endpoint handles:
1. Real-time streaming (user experience)
2. Immediate transaction creation (safety net)
3. Atomic credit deduction (revenue protection)

A lightweight **Reconciliation Worker** handles edge cases (server crashes, network failures).

---

## Technical Design

### System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    POST /api/chat/stream-v2                 │
│                   (User sends message)                       │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│  Step 1: Preliminary Credit Check                           │
│  - Check: user.credits >= MIN_CREDIT_THRESHOLD (10)        │
│  - If insufficient: Reject with 402 Payment Required        │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│  Step 2: Create PENDING Transaction (Safety Net)            │
│  - Generate unique transaction_id                            │
│  - Insert into transactions collection:                      │
│    {                                                         │
│      transaction_id: "txn_abc123",                          │
│      user_id: "user_xyz",                                   │
│      status: "PENDING",                                     │
│      estimated_cost: 10.0,  // Conservative estimate        │
│      created_at: timestamp                                   │
│    }                                                         │
│  - This ensures we never lose a billable request            │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│  Step 3: Call LLM & Stream Response                         │
│  - Add system prompt + conversation history                  │
│  - Call DashScope Qwen-plus with streaming=True             │
│  - Stream chunks to client via Server-Sent Events           │
│  - Accumulate full response                                  │
│  - Capture token usage from final response                   │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│  Step 4: Save Assistant Message with Transaction Link       │
│  - Save message to messages collection                       │
│  - Include transaction_id in metadata                        │
│  - This creates audit trail for refunds/disputes            │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│  Step 5: ACID Transaction - Deduct Credits & Complete       │
│  MongoDB Transaction:                                        │
│    1. Calculate cost: tokens_used / 200 = credits           │
│    2. Update user: credits -= cost (atomic)                 │
│    3. Update transaction:                                    │
│       - status = "COMPLETED"                                 │
│       - actual_tokens = input + output                       │
│       - actual_cost = calculated cost                        │
│       - completed_at = timestamp                             │
│    4. Commit or Rollback (all-or-nothing)                   │
│  - Backend does NOT send balance back to client             │
│  - Frontend uses optimistic updates (see below)             │
└─────────────────────────────────────────────────────────────┘
```

### Reconciliation Worker (Failure Safety Net)

**Purpose**: Handle rare cases where server crashes after streaming but before billing

**Trigger**: Kubernetes CronJob every 10 minutes

**Logic**:
```python
def reconcile_stuck_transactions():
    # Find transactions stuck in PENDING for >10 minutes
    stuck = transactions.find({
        "status": "PENDING",
        "created_at": {"$lt": now() - timedelta(minutes=10)}
    })

    for txn in stuck:
        # Check if user was actually served
        message = messages.find_one({
            "metadata.transaction_id": txn.transaction_id
        })

        if message:
            # User got response but wasn't billed - complete now
            complete_transaction(txn.transaction_id, message.metadata.tokens)
            logger.warning("Reconciled stuck transaction", txn_id=txn.transaction_id)
        else:
            # No response found - mark as FAILED (no charge)
            fail_transaction(txn.transaction_id)
            logger.info("Failed incomplete transaction", txn_id=txn.transaction_id)
```

**Deployment**:
- Local Dev: Python scheduler runs every 5 minutes (for testing)
- Test/Prod: Kubernetes CronJob with image: `klinematrix/backend:test-v0.6.0`

---

## Database Schema

### 1. Users Collection (Modified)

**Changes**: Add credit balance field

```python
class User(BaseModel):
    user_id: str
    email: str | None
    username: str
    # ... existing fields ...

    # NEW FIELDS
    credits: float = 1000.0  # Free credits on signup
    total_tokens_used: int = 0  # Lifetime usage (analytics)
    total_credits_spent: float = 0.0  # Lifetime spending
```

**Indexes**:
- Existing: `_id` (default)
- Recommended: `email`, `username` (for lookups)

---

### 2. Transactions Collection (New)

**Purpose**: Immutable audit trail for all credit operations

```python
class CreditTransaction(BaseModel):
    transaction_id: str  # Format: "txn_{uuid4()}"
    user_id: str
    chat_id: str
    message_id: str | None  # Links to assistant message

    # Status tracking
    status: Literal["PENDING", "COMPLETED", "FAILED"]

    # Cost details
    estimated_cost: float  # Conservative estimate at start
    actual_tokens: int | None  # Actual input + output tokens
    actual_cost: float | None  # Exact cost: actual_tokens / 200

    # Timestamps
    created_at: datetime
    completed_at: datetime | None

    # Metadata
    model: str = "qwen-plus"
    request_type: str = "chat"  # "chat", "analysis", etc.
```

**Indexes**:
- `transaction_id` (unique)
- `user_id` (for user history)
- `(status, created_at)` compound (for reconciliation queries)
- `chat_id` (for chat-level analytics)

**Retention**: Keep forever (legal/accounting requirement)

---

### 3. Messages Collection (Modified)

**Changes**: Add transaction link to metadata

```python
class MessageMetadata(BaseModel):
    # ... existing fields ...

    # NEW FIELDS
    transaction_id: str | None  # Links to credit transaction
    tokens_used: int | None  # Quick reference (also in transaction)
```

---

## API Endpoints

### 1. Modified Endpoints

#### `POST /api/chat/stream-v2` (Modified)

**Changes**:
- Add credit check before LLM call
- Create transaction record
- Deduct credits after streaming (server-side only)
- No SSE event for credit balance (frontend uses optimistic updates)

**NO NEW SSE EVENTS**: Backend does NOT send credit balance back.
Frontend uses optimistic updates and periodic refetch to sync with backend truth.

**Error Responses**:
```json
// Insufficient credits
{
  "type": "error",
  "error": "Insufficient credits. Required: ~10, Available: 5.2",
  "error_code": "INSUFFICIENT_CREDITS"
}
```

---

### 2. New Endpoints

#### `GET /api/users/me`

**Purpose**: Get current user profile including credit balance

**Response**:
```json
{
  "user_id": "user_abc",
  "username": "alice",
  "email": "alice@example.com",
  "credits": 987.5,
  "total_tokens_used": 12500,
  "total_credits_spent": 62.5,
  "created_at": "2025-01-01T00:00:00Z"
}
```

**Auth**: Required (JWT)

---

#### `GET /api/credits/transactions`

**Purpose**: Get user's credit transaction history

**Query Params**:
- `page` (default: 1)
- `page_size` (default: 20, max: 100)
- `status` (optional: filter by PENDING/COMPLETED/FAILED)

**Response**:
```json
{
  "transactions": [
    {
      "transaction_id": "txn_abc123",
      "chat_id": "chat_xyz",
      "status": "COMPLETED",
      "actual_tokens": 1700,
      "actual_cost": 8.5,
      "created_at": "2025-01-13T10:30:00Z",
      "completed_at": "2025-01-13T10:30:15Z"
    }
  ],
  "pagination": {
    "page": 1,
    "page_size": 20,
    "total": 45,
    "total_pages": 3
  }
}
```

**Auth**: Required (JWT)

---

#### `POST /api/credits/purchase` (Placeholder)

**Purpose**: Purchase credits (future payment integration)

**Request**:
```json
{
  "amount": 5000,  // Credits to purchase
  "payment_method": "alipay"  // "alipay", "wechat", "card"
}
```

**Status**: Not implemented in v0.6.0 (return 501 Not Implemented)

---

#### `POST /api/admin/credits/adjust` (Admin Only)

**Purpose**: Manually adjust user credits (refunds, corrections)

**Request**:
```json
{
  "user_id": "user_abc",
  "amount": 50.0,  // Positive = add, negative = deduct
  "reason": "Refund for system error on 2025-01-13"
}
```

**Auth**: Admin required (`require_admin` dependency)

---

## Frontend Changes

### 1. Credit Balance Display

**Location**: Header area in `App.tsx`

**Design**:
```tsx
// Current:
<span className="text-sm text-gray-700">👤 {username}</span>

// New:
<div className="flex items-center gap-4">
  <span className="text-sm text-gray-700">👤 {username}</span>
  <CreditBalance balance={user.credits} />
</div>
```

**Component** (`src/components/CreditBalance.tsx`):
```tsx
interface CreditBalanceProps {
  balance: number;
}

// Shows:
// - Current balance with coin icon
// - Color coding: green (>100), yellow (10-100), red (<10)
// - Click to view transaction history
```

---

### 2. Cost Indicators

**Location**: Chat input area

**Design**: Show estimated cost before sending

```tsx
<div className="text-xs text-gray-500 mb-2">
  Estimated cost: ~5-10 credits
</div>
```

---

### 3. Transaction History Page

**Route**: `/credits/history`

**Features**:
- Paginated transaction list
- Filters: Status, date range
- Export to CSV (future)

---

### 4. State Management (Optimistic Updates)

**Pattern**: Optimistically deduct credits immediately, backend is source of truth

**New Hook**: `useUserProfile()`

```typescript
export function useUserProfile() {
  return useQuery({
    queryKey: ['user', 'profile'],
    queryFn: () => api.get('/api/users/me'),
    staleTime: 30000, // Refetch every 30s to sync with backend
    refetchOnWindowFocus: true
  });
}
```

**Optimistic Updates**: Deduct credits immediately when sending message

```typescript
const mutation = useMutation({
  mutationFn: (message: string) => api.sendMessageStreamPersistent(message, chatId, ...),
  onMutate: async (message) => {
    // Cancel in-flight refetches
    await queryClient.cancelQueries({ queryKey: ['user', 'profile'] });

    // Snapshot previous value
    const previous = queryClient.getQueryData(['user', 'profile']);

    // Optimistically deduct estimated cost
    const estimatedCost = estimateCost(message); // ~10 credits average
    queryClient.setQueryData(['user', 'profile'], (old) => ({
      ...old,
      credits: old.credits - estimatedCost
    }));

    return { previous }; // For rollback
  },
  onError: (err, variables, context) => {
    // Rollback on error
    if (context?.previous) {
      queryClient.setQueryData(['user', 'profile'], context.previous);
    }
  },
  onSuccess: () => {
    // Invalidate to sync with backend truth (actual cost may differ)
    queryClient.invalidateQueries({ queryKey: ['user', 'profile'] });
  }
});
```

**Cost Estimation Function**:
```typescript
function estimateCost(message: string): number {
  // Conservative estimate based on message length
  const baseTokens = 300; // System prompt + history average
  const messageTokens = Math.ceil(message.length / 4); // ~4 chars per token
  const estimatedOutput = 500; // Average response length
  const totalTokens = baseTokens + messageTokens + estimatedOutput;
  return Math.ceil(totalTokens / 200); // Convert to credits, round up
}
```

**Benefits**:
- ✅ Instant UI feedback (no waiting for backend)
- ✅ Backend remains simple (no need to send balance)
- ✅ Eventually consistent (refetch syncs with truth)
- ✅ Follows existing optimistic pattern in codebase

---

## Edge Cases & Error Handling

### 1. Insufficient Credits

**Scenario**: User has 5 credits, tries to send message (estimated 10 credits)

**Handling**:
1. Preliminary check blocks request
2. Return 402 Payment Required
3. Frontend shows: "Insufficient credits. Please purchase more."
4. Suggest credit purchase (future)

---

### 2. Token Estimate vs Actual

**Scenario**: Estimated 10 credits, actual usage 12 credits

**Handling**:
- **Allow once as goodwill** (don't block mid-stream)
- Deduct actual cost (may go slightly negative)
- Block next request if balance < MIN_THRESHOLD
- Log warning for review

---

### 3. Stream Cancellation

**Scenario**: User closes browser mid-stream

**Handling**:
- Backend detects client disconnect
- Still complete transaction (user consumed tokens from DashScope)
- Mark transaction COMPLETED with actual tokens used
- Transaction appears in history as "incomplete response"

---

### 4. LLM Provider Error

**Scenario**: DashScope returns 500 error

**Handling**:
1. Don't deduct credits
2. Mark transaction FAILED
3. Show user-friendly error
4. Log for investigation

---

### 5. Missing Token Count

**Scenario**: DashScope response doesn't include `usage` field

**Handling**:
- Fallback: Use `tiktoken` library to count tokens manually
- Conservative estimate (round up)
- Log warning for investigation
- Still complete transaction

---

### 6. Concurrent Requests

**Scenario**: User sends 2 messages before first completes

**Handling**:
- MongoDB transactions ensure atomic credit deduction
- Both requests check balance independently
- If combined cost exceeds balance, second may fail
- Use optimistic locking: `findOneAndUpdate` with version field

---

### 7. Reconciliation Race Condition

**Scenario**: Worker tries to complete transaction while API is completing it

**Handling**:
```python
# Use atomic update with status condition
result = transactions.find_one_and_update(
    {"transaction_id": txn_id, "status": "PENDING"},  # Only if still PENDING
    {"$set": {"status": "COMPLETED", ...}},
    return_document=ReturnDocument.AFTER
)

if result is None:
    # Already completed by API - skip
    return
```

---

## Testing Strategy

### Unit Tests

**CreditService** (`test_credit_service.py`):
- `test_calculate_cost()` - Token to credit conversion
- `test_check_balance_sufficient()` - Balance validation
- `test_check_balance_insufficient()` - Rejection logic
- `test_deduct_credits_atomic()` - Transaction isolation
- `test_deduct_credits_insufficient_rollback()` - Rollback on failure

**TransactionRepository** (`test_transaction_repository.py`):
- `test_create_transaction()` - PENDING transaction creation
- `test_complete_transaction()` - Status update
- `test_fail_transaction()` - Failure marking
- `test_find_stuck_transactions()` - Reconciliation query

---

### Integration Tests

**Transaction Flow** (`test_transaction_flow.py`):
- `test_full_chat_flow_with_credits()` - End-to-end
- `test_insufficient_credits_rejection()` - 402 error
- `test_concurrent_requests()` - Race conditions
- `test_stream_cancellation()` - Client disconnect

---

### Manual Testing Checklist

**Kubernetes Test Environment**:
- [ ] New user gets 1000 credits
- [ ] Send message deducts correct credits
- [ ] Balance updates in UI after message
- [ ] Transaction history shows correct records
- [ ] Insufficient credits blocks request
- [ ] Reconciliation worker completes stuck transactions
- [ ] Admin can adjust credits
- [ ] MongoDB transactions work (Cosmos DB)

**Local Development**:
- [ ] Transaction fallback works (no MongoDB replica set)
- [ ] Token counting accurate
- [ ] Error handling graceful

---

## Rollout Plan

### Phase 1: Backend Infrastructure (v0.6.0-alpha)

**Changes**:
- Database schema updates
- CreditService implementation
- Transaction repository
- Modified chat endpoint
- Unit tests

**Deployment**: Test environment only
**Users**: Internal testing only
**Risk**: Low (no user impact)

---

### Phase 2: API + Frontend (v0.6.0-beta)

**Changes**:
- New credit endpoints
- Frontend credit display
- Transaction history page
- Integration tests

**Deployment**: Test environment
**Users**: Beta testers (5-10 users)
**Risk**: Medium (user-facing changes)

---

### Phase 3: Reconciliation + Polish (v0.6.0)

**Changes**:
- Reconciliation worker
- CronJob deployment
- Edge case handling
- Performance optimization

**Deployment**: Test environment → Production
**Users**: All users
**Risk**: Medium (billing correctness critical)

---

## Monitoring & Observability

### Metrics to Track

**Business Metrics**:
- Total credits purchased (per day/week/month)
- Total credits spent (per day/week/month)
- Average cost per conversation
- Credit balance distribution (how many users < 100 credits)
- Conversion rate (free → paid)

**Technical Metrics**:
- Transaction completion rate (COMPLETED / TOTAL)
- Transaction failure rate (FAILED / TOTAL)
- Reconciliation corrections per day
- Average tokens per request
- Token estimate accuracy (estimated vs actual)

**Alerts**:
- Transaction failure rate > 1%
- Reconciliation corrections > 10/hour
- User balance < 0 (should never happen)
- Token counting errors

---

### Logging

**Structured Logs** (via structlog):

```python
# Transaction creation
logger.info("Transaction created",
    transaction_id=txn_id,
    user_id=user_id,
    estimated_cost=cost)

# Credit deduction
logger.info("Credits deducted",
    transaction_id=txn_id,
    user_id=user_id,
    tokens=tokens,
    cost=cost,
    new_balance=new_balance)

# Reconciliation
logger.warning("Transaction reconciled",
    transaction_id=txn_id,
    age_minutes=age)

# Errors
logger.error("Credit deduction failed",
    transaction_id=txn_id,
    error=str(e),
    balance=user.credits)
```

---

## Security Considerations

### 1. Credit Injection Prevention

**Risk**: Malicious user tries to modify credit balance

**Mitigation**:
- All credit operations server-side only
- No client-side balance updates (only display)
- Admin endpoints require `is_admin=True` check
- Audit log for all manual adjustments

---

### 2. Token Counting Manipulation

**Risk**: User tries to manipulate token count to pay less

**Mitigation**:
- Token count comes from DashScope API (trusted source)
- Fallback to server-side counting (tiktoken)
- Never trust client-provided counts
- Log discrepancies for investigation

---

### 3. Transaction Replay

**Risk**: Replay attack to deduct credits multiple times

**Mitigation**:
- Unique transaction_id per request
- Idempotent updates (check status=PENDING)
- MongoDB transaction isolation

---

### 4. Balance Race Conditions

**Risk**: Concurrent requests bypass balance check

**Mitigation**:
- Atomic credit deduction with MongoDB transactions
- Conservative estimate at request start
- Reconciliation catches inconsistencies

---

## Open Questions & Decisions Needed

### 1. Pricing Validation
**Question**: Does 1 Credit = 200 Tokens achieve 84% margin with Qwen-plus pricing?

**Action Required**:
- Confirm Alibaba DashScope Qwen-plus pricing
- Calculate actual cost per token
- Adjust conversion rate if needed

**Recommendation**: Document actual costs in this spec before launch

---

### 2. Negative Balance Handling
**Question**: Should we allow users to go slightly negative?

**Options**:
- A) Strict: Never allow negative (block mid-stream if needed)
- B) Lenient: Allow one "goodwill" negative, then block
- C) Credit limit: Allow up to -50 credits (like credit card)

**Recommendation**: Option B - balances user experience with revenue protection

---

### 3. Credit Purchase Integration
**Question**: Which payment providers to support?

**Options**:
- Alipay (most common in China)
- WeChat Pay (mobile-first)
- Credit card (international)
- Cryptocurrency (future)

**Recommendation**: Start with Alipay + WeChat Pay (v0.7.0)

---

### 4. Free Credit Replenishment
**Question**: Should users get periodic free credits?

**Options**:
- A) One-time 1000 credits, then must purchase
- B) 100 credits per month (retention strategy)
- C) Earn credits by referrals/feedback

**Recommendation**: Start with Option A, evaluate retention metrics

---

### 5. Admin Credit Adjustment Limits
**Question**: Should there be limits on manual credit adjustments?

**Options**:
- A) Unlimited (full trust in admins)
- B) Max 1000 credits per adjustment (require multiple for large refunds)
- C) Require two-person approval for >500 credits

**Recommendation**: Option B with audit logging

---

## Success Criteria

### Business Success
- ✅ 80%+ of users stay above 0 credits (healthy engagement)
- ✅ <5% support tickets related to billing
- ✅ Transaction failure rate <0.1%
- ✅ Gross margin ≥75% (target 84%)

### Technical Success
- ✅ Zero double-charging incidents
- ✅ Zero credit loss incidents (reconciliation catches all)
- ✅ 99.9% transaction completion rate
- ✅ <100ms latency added to chat endpoint

### User Experience Success
- ✅ Users understand credit costs (survey)
- ✅ No "surprise" out-of-credits errors
- ✅ Transaction history page used by 30%+ users
- ✅ NPS score ≥8/10 for billing transparency

---

## Risks & Mitigation

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| Double charging | High | Low | ACID transactions + reconciliation audit |
| Credit loss (not charging) | High | Low | Reconciliation worker + alerts |
| Token counting errors | Medium | Medium | Fallback to tiktoken + logging |
| Race conditions | Medium | Medium | MongoDB transactions + testing |
| Reconciliation bugs | Medium | Low | Dry-run mode + monitoring |
| User confusion | Medium | Medium | Clear UI + transaction history |

---

## Future Enhancements (Post v0.6.0)

### v0.7.0: Payment Integration
- Alipay integration
- WeChat Pay integration
- Purchase credits flow
- Invoice generation

### v0.8.0: Advanced Features
- Credit packages (bulk discounts)
- Subscription plans (monthly credits)
- Referral credits
- Credit gifting

### v0.9.0: Analytics & Optimization
- Cost prediction models
- Usage optimization suggestions
- Credit usage dashboard
- Budget alerts

---

## References

### Internal Documents
- [System Design](../architecture/system-design.md)
- [Development Workflow](../deployment/workflow.md)
- [Coding Standards](../development/coding-standards.md)

### External Resources
- [Alibaba DashScope Pricing](https://help.aliyun.com/zh/dashscope/developer-reference/tongyi-thousand-questions-metering-and-billing)
- [MongoDB Transactions](https://www.mongodb.com/docs/manual/core/transactions/)
- [Azure Cosmos DB Transactions](https://learn.microsoft.com/en-us/azure/cosmos-db/mongodb/feature-support-42#transactions)

---

## Appendix A: File Structure

```
backend/src/
├── models/
│   ├── user.py (modify - add credits field)
│   ├── transaction.py (new)
│   └── message.py (modify - add transaction_id)
├── database/repositories/
│   ├── user_repository.py (modify - credit operations)
│   └── transaction_repository.py (new)
├── services/
│   └── credit_service.py (new)
├── api/
│   ├── chat.py (modify - transaction logic)
│   └── credits.py (new - endpoints)
├── scripts/
│   └── reconciliation_worker.py (new)
└── tests/
    ├── test_credit_service.py (new)
    └── test_transaction_flow.py (new)

frontend/src/
├── types/
│   └── api.ts (modify - add credits to User)
├── components/
│   ├── CreditBalance.tsx (new)
│   └── TransactionHistory.tsx (new)
├── hooks/
│   └── useUserProfile.ts (new)
└── services/
    └── api.ts (modify - credit endpoints)

.pipeline/k8s/base/
└── cronjob-reconciliation.yaml (new)
```

---

## Appendix B: Cost Calculation Examples

**Scenario 1: Simple Question**
```
User: "What's the current price of AAPL?"
Input tokens: 100 (prompt + history)
Output tokens: 50 (short answer)
Total: 150 tokens
Cost: 150 / 200 = 0.75 credits = ¥0.0075
```

**Scenario 2: Technical Analysis Request**
```
User: "Analyze AAPL Fibonacci levels with detailed explanation"
Input tokens: 500 (prompt + history + analysis data)
Output tokens: 2000 (detailed explanation)
Total: 2500 tokens
Cost: 2500 / 200 = 12.5 credits = ¥0.125
```

**Scenario 3: Long Conversation (10 messages)**
```
Average per message:
- Input: 300 tokens (growing history)
- Output: 500 tokens
- Per message: 800 tokens = 4 credits

Total for 10 messages: 40 credits = ¥0.40
```

**Free Credit Utilization**:
- 1000 free credits = ~10-15 conversations
- Enough for 2-3 weeks of casual usage
- Conversion point: When users get value, they'll pay

---

**End of Feature Specification**

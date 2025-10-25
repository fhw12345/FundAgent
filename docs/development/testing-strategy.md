# Testing Strategy & Coverage Improvement Plan

**Last Updated**: 2025-10-25
**Current Coverage**: Backend 43%, Frontend minimal
**Target**: Backend 60%+, Frontend 50%+

---

## Current State

### Backend Testing (187 → 205 tests, 43% coverage)

**Well-Tested Modules** (>80% coverage):
- ✅ `rate_limiter.py`: **100%** (18 tests) - Completed 2025-10-25
- ✅ `stochastic_analyzer.py`: 83%
- ✅ `stock_analyzer.py`: 85%
- ✅ `credit_service.py`: 90%
- ✅ `llm_models.py`: 82%
- ✅ All Pydantic models: 100%
- ✅ `transaction_repository.py`: 100%
- ✅ `ticker_data_service.py`: 100%

**Critical Gaps** (<50% coverage):
1. **Infrastructure Layer** (High Priority):
   - `mongodb.py`: 22% (45 statements, 35 untested)
   - `redis.py`: 19% (81 statements, 66 untested)
   - `main.py`: 54% (84 statements, 39 untested)

2. **Security & Authentication** (High Priority):
   - `auth.py`: 26% (140 statements, 104 untested)
   - `auth_service.py`: 20% (130 statements, 104 untested)
   - `token_service.py`: 24% (115 statements, 87 untested)
   - `auth_providers/email_provider.py`: 28%

3. **Business Logic** (Medium Priority):
   - `chat.py`: 14% (230 statements, 198 untested)
   - `chat_service.py`: 27%
   - `chat_repository.py`: 22%
   - `feedback.py`: 23%
   - `feedback_service.py`: 11%

4. **Data Repositories** (Medium Priority):
   - `refresh_token_repository.py`: 15% (110 statements)
   - `user_repository.py`: 20% (105 statements)
   - `message_repository.py`: 25%

5. **Analysis Modules** (Low Priority):
   - `fibonacci/analyzer.py`: 19%
   - `fibonacci/trend_detector.py`: 14%
   - `macro_analyzer.py`: 13%

6. **Admin & Operations** (Low Priority):
   - `admin.py`: 37%
   - `kubernetes_metrics_service.py`: 9%
   - `workers/reconcile_transactions.py`: 0%

### Frontend Testing (Minimal)

**Existing Tests**:
- `tokenEstimator.test.ts`: CJK-aware token estimation (11 tests)

**Requirements**:
- ⚠️ **Docker Required**: Frontend tests must run via `docker compose exec frontend npm test`
- Testing stack: Vitest + React Testing Library + jsdom
- Config: `vite.config.ts` test section
- Setup file: `frontend/src/test/setup.ts`

**Critical Gaps**:
- API clients (axios wrappers)
- React hooks (useCh ats, useAnalysis, useCredits)
- Components (ChatPanel, AnalysisPanel, etc.)
- State management (React Query)
- Utilities (date formatters, chart helpers)

---

## Strategic Test Plan

### Phase 1: Infrastructure Foundation (Target: +5% coverage)

**Priority 1A: Redis Connection & Caching**
- **File**: `src/database/redis.py`
- **Current**: 19% coverage (81 statements, 66 untested)
- **Target**: 65% coverage
- **Test Cases Needed**:
  - Connection establishment (success/failure)
  - Connection pooling
  - `get()` with hit/miss/error
  - `set()` with/without expiry
  - `delete()` operations
  - `incr()` for counters
  - `expire()` for TTL
  - Connection retry logic
  - Graceful degradation when unavailable

**Priority 1B: MongoDB Connection & Operations**
- **File**: `src/database/mongodb.py`
- **Current**: 22% coverage (45 statements, 35 untested)
- **Target**: 65% coverage
- **Test Cases Needed**:
  - Connection establishment
  - Database selection
  - Collection access
  - Connection error handling
  - Reconnection logic
  - Graceful shutdown

**Priority 1C: Application Lifespan**
- **File**: `src/main.py`
- **Current**: 54% coverage (39 untested statements in lifespan)
- **Target**: 75% coverage
- **Test Cases Needed**:
  - App initialization
  - Database connection startup
  - Index creation flow
  - Graceful shutdown
  - Error handling during startup

### Phase 2: Security & Authentication (Target: +8% coverage)

**Priority 2A: Auth Endpoints**
- **File**: `src/api/auth.py`
- **Current**: 26% coverage (140 statements)
- **Target**: 55% coverage
- **Test Cases Needed**:
  - Registration endpoint (email/phone)
  - Verification code generation
  - Login with credentials
  - Token refresh flow
  - Logout and token revocation
  - Password reset flow
  - Error handling (invalid credentials, expired tokens)

**Priority 2B: Auth Service**
- **File**: `src/services/auth_service.py`
- **Current**: 20% coverage (130 statements)
- **Target**: 55% coverage
- **Test Cases Needed**:
  - User registration flow
  - Email verification
  - Login validation
  - Token generation/validation
  - Password hashing/verification
  - Multi-provider support

**Priority 2C: Token Service**
- **File**: `src/services/token_service.py`
- **Current**: 24% coverage (115 statements)
- **Target**: 60% coverage
- **Test Cases Needed**:
  - JWT encoding/decoding
  - Token validation (expiry, signature)
  - Refresh token rotation
  - Token revocation
  - Claims extraction

### Phase 3: Chat & Business Logic (Target: +6% coverage)

**Priority 3A: Chat Endpoints**
- **File**: `src/api/chat.py`
- **Current**: 14% coverage (230 statements)
- **Target**: 45% coverage
- **Test Cases Needed**:
  - Create chat
  - List chats (with pagination)
  - Get chat by ID
  - Update chat (rename)
  - Delete/archive chat
  - Send message
  - Stream LLM response
  - Error handling (not found, permission denied)

**Priority 3B: Chat Service**
- **File**: `src/services/chat_service.py`
- **Current**: 27% coverage
- **Target**: 60% coverage
- **Test Cases Needed**:
  - Chat CRUD operations
  - Message persistence
  - LLM integration
  - UI state management
  - Context window management

**Priority 3C: Chat Repository**
- **File**: `src/database/repositories/chat_repository.py`
- **Current**: 22% coverage
- **Target**: 65% coverage
- **Test Cases Needed**:
  - CRUD operations with mocked MongoDB
  - Pagination and sorting
  - Archive/unarchive
  - Query optimization

### Phase 4: Frontend Testing (Target: 50%+ coverage)

**Priority 4A: API Clients**
- **Files**: `frontend/src/services/*.ts`
- **Current**: No tests
- **Test Cases Needed**:
  - `chatApi.ts`: CRUD operations, streaming
  - `analysisApi.ts`: Fibonacci, stochastic requests
  - `authApi.ts`: Login, registration, token refresh
  - `creditsApi.ts`: Balance, transactions
  - Error handling (network errors, 401, 429)

**Priority 4B: React Hooks**
- **Files**: `frontend/src/hooks/*.ts`
- **Current**: No tests
- **Test Cases Needed**:
  - `useChats`: List, create, update, delete
  - `useAnalysis`: Trigger analysis, handle results
  - `useCredits`: Balance updates, transaction tracking
  - `useAuth`: Login, logout, token refresh
  - React Query integration

**Priority 4C: Critical Components**
- **Files**: `frontend/src/components/**/*.tsx`
- **Current**: No tests
- **Test Cases Needed**:
  - `ChatPanel`: Message list, input, streaming
  - `AnalysisPanel`: Chart rendering, Fibonacci overlays
  - `CreditBalance`: Display, updates
  - User interactions (clicks, form submissions)

**Priority 4D: Utilities**
- **Files**: `frontend/src/utils/*.ts`
- **Current**: `tokenEstimator.test.ts` only
- **Test Cases Needed**:
  - Date formatters
  - Chart data transformers
  - Analysis metadata extractors
  - Validation helpers

---

## Testing Best Practices

### Backend (pytest)

**Test Structure**:
```python
"""
Module docstring explaining what's being tested.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock

class TestFeatureName:
    """Test suite for specific feature."""

    @pytest.mark.asyncio
    async def test_happy_path(self):
        """Test normal successful operation."""
        # Arrange
        mock_dependency = AsyncMock()
        service = Service(mock_dependency)

        # Act
        result = await service.method()

        # Assert
        assert result == expected_value
        mock_dependency.method.assert_called_once()

    @pytest.mark.asyncio
    async def test_error_case(self):
        """Test error handling."""
        # Arrange: Setup to trigger error

        # Act & Assert: Expect exception
        with pytest.raises(HTTPException) as exc_info:
            await service.method()

        assert exc_info.value.status_code == 400
```

**Mocking Guidelines**:
- Use `AsyncMock` for async methods
- Use `MagicMock` for sync objects
- Mock external dependencies (DB, Redis, LLM APIs)
- Don't mock internal logic

**Coverage Goals**:
- **Critical paths**: 100% (auth, payments, security)
- **Business logic**: 80%+ (services, repositories)
- **Infrastructure**: 70%+ (database, cache connections)
- **Utilities**: 90%+ (pure functions)
- **Integration points**: 60%+ (API endpoints)

### Frontend (Vitest + React Testing Library)

**Test Structure**:
```typescript
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

describe('ComponentName', () => {
  it('should render correctly', () => {
    // Arrange
    const queryClient = new QueryClient();

    // Act
    render(
      <QueryClientProvider client={queryClient}>
        <ComponentName />
      </QueryClientProvider>
    );

    // Assert
    expect(screen.getByText('Expected Text')).toBeInTheDocument();
  });

  it('should handle user interaction', async () => {
    // Arrange
    const handleClick = vi.fn();
    render(<Button onClick={handleClick}>Click Me</Button>);

    // Act
    fireEvent.click(screen.getByText('Click Me'));

    // Assert
    await waitFor(() => {
      expect(handleClick).toHaveBeenCalledOnce();
    });
  });
});
```

**Mocking API Calls**:
```typescript
import { rest } from 'msw';
import { setupServer } from 'msw/node';

const server = setupServer(
  rest.get('/api/chats', (req, res, ctx) => {
    return res(ctx.json({ chats: [] }));
  })
);

beforeAll(() => server.listen());
afterEach(() => server.resetHandlers());
afterAll(() => server.close());
```

---

## Execution Plan

### Immediate (This Session)
1. ✅ Rate limiter tests: 36% → 100% (COMPLETED)
2. ✅ Create this testing strategy document
3. ⏳ Commit rate limiter tests
4. ⏳ Create example frontend tests (even if Docker not running)

### Short-Term (Next PR)
1. Redis infrastructure tests: 19% → 65%
2. MongoDB infrastructure tests: 22% → 65%
3. Auth endpoint tests: 26% → 55%
4. Target: Backend 43% → 52% (+9%)

### Medium-Term (Following PRs)
1. Chat endpoints & service: 14-27% → 50%
2. Feedback endpoints & service: 11-23% → 50%
3. Token service: 24% → 60%
4. Frontend API clients & hooks
5. Target: Backend 55%, Frontend 30%

### Long-Term (Future Milestones)
1. Repository layer: 15-25% → 70%
2. Analysis modules: 13-19% → 60%
3. Frontend components: 0% → 60%
4. Admin & operations: 0-37% → 50%
5. Target: Backend 65%+, Frontend 55%+

---

## Running Tests

### Backend Tests

**Run all tests**:
```bash
cd backend
make test                    # Run all tests
make test-cov               # With coverage report
python -m pytest tests/     # Direct pytest
```

**Run specific test file**:
```bash
python -m pytest tests/test_rate_limiter.py -v
```

**Run with coverage for specific module**:
```bash
python -m pytest --cov=src.core.rate_limiter --cov-report=term-missing tests/test_rate_limiter.py
```

**Generate HTML coverage report**:
```bash
python -m pytest --cov=src --cov-report=html
open htmlcov/index.html
```

### Frontend Tests

**⚠️ IMPORTANT**: Frontend tests MUST run via Docker Compose.

**Start Docker Compose** (if not running):
```bash
make dev  # or: docker compose up -d
```

**Run frontend tests**:
```bash
docker compose exec frontend npm test          # Run all tests
docker compose exec frontend npm run test:ui   # Interactive UI
docker compose exec frontend npm run test:coverage  # With coverage
```

**Common Issues**:
- ❌ **Error**: `sh: vitest: command not found`
  - **Cause**: Trying to run `npm test` outside Docker
  - **Fix**: Use `docker compose exec frontend npm test`

- ❌ **Error**: `Cannot connect to Docker daemon`
  - **Cause**: Docker not running
  - **Fix**: Start Docker Desktop, then `make dev`

---

## Test Coverage Metrics

### Current Baseline (2025-10-25)
- **Backend**: 43% (2,615 / 4,591 statements covered)
- **Frontend**: <5% (1 test file)
- **Total Tests**: 205 backend, 11 frontend

### Target Milestones
- **Sprint 1**: Backend 50%, Frontend 20%
- **Sprint 2**: Backend 58%, Frontend 35%
- **Sprint 3**: Backend 65%, Frontend 50%
- **Production**: Backend 70%+, Frontend 60%+

### Coverage by Layer (Target)
| Layer | Current | Target | Priority |
|-------|---------|--------|----------|
| Security/Auth | 20-26% | 60% | 🔴 Critical |
| Infrastructure | 19-22% | 65% | 🔴 Critical |
| Business Logic | 14-27% | 55% | 🟡 High |
| Repositories | 15-25% | 70% | 🟡 High |
| API Endpoints | 14-62% | 60% | 🟡 High |
| Services | 11-90% | 65% | 🟢 Medium |
| Analysis Modules | 13-85% | 60% | 🟢 Medium |
| Models (Pydantic) | 94-100% | 100% | ✅ Done |

---

## Continuous Improvement

### Pre-Commit Requirements
- All new code must include tests
- Coverage cannot decrease
- All tests must pass

### Code Review Checklist
- [ ] Tests cover happy path
- [ ] Tests cover error cases
- [ ] Tests cover edge cases
- [ ] Mocks used appropriately
- [ ] Test names are descriptive
- [ ] No commented-out tests
- [ ] Coverage increased or maintained

### Quarterly Goals
- Review coverage gaps
- Update this strategy document
- Identify new high-priority areas
- Celebrate wins! 🎉

---

**Next Steps**: See commit history for rate_limiter tests as a reference implementation.

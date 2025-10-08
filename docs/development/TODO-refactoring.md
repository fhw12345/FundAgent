# Code Refactoring TODO

## File Length Violations (500 Line Limit)

These files exceed the 500-line limit and need refactoring:

### 🔴 HIGH PRIORITY

#### 1. `frontend/src/components/ChatInterface.tsx` (835 lines)
**Current size**: 835 lines
**Target**: < 500 lines
**Complexity**: High

**Recommended refactoring**:
1. Extract chat message handling → `hooks/useChatMessages.ts`
2. Extract analysis intent parsing → `utils/intentParser.ts`
3. Extract quick analysis buttons → `components/chat/QuickAnalysisPanel.tsx`
4. Extract symbol/interval controls → `components/chat/ChatControls.tsx`

**Benefits**:
- Better separation of concerns
- Easier testing
- Reusable components

---

#### 2. `frontend/src/components/LoginPage.tsx` (724 lines)
**Current size**: 724 lines
**Target**: < 500 lines
**Complexity**: Medium

**Recommended refactoring**:
1. Extract login form → `components/auth/LoginForm.tsx`
2. Extract registration flow → `components/auth/RegistrationFlow.tsx`
3. Extract forgot password flow → `components/auth/ForgotPasswordFlow.tsx`
4. Shared form validation → `utils/authValidation.ts`

**Benefits**:
- Cleaner component structure
- Easier to test individual flows
- Better code reuse

---

## Pre-commit Hook Status

✅ **Passing** (15/16 hooks):
- Version validation
- Black formatting
- Ruff linting
- Mypy type checking
- Prettier formatting
- All general checks
- Bandit security scanning
- Gitleaks secret detection
- Hadolint Dockerfile linting

⚠️ **Failing** (1/16 hooks):
- File length check (2 files above limit)

---

## Action Items

- [ ] Refactor `ChatInterface.tsx` to < 500 lines
- [ ] Refactor `LoginPage.tsx` to < 500 lines
- [ ] Update tests for new component structure
- [ ] Verify all functionality after refactoring

---

## Notes

**Test files excluded**: Test files (`test_*.py`, `*.test.ts`) are intentionally excluded from the 500-line limit as they naturally contain many test cases.

**Current enforcement**: Pre-commit hook blocks commits with oversized **production** files.

---

*Last updated: 2025-10-08*

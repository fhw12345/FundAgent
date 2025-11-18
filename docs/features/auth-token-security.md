# Feature: JWT Token Refresh & Security

> **Status**: Draft
> **Created**: 2025-10-08
> **Last Updated**: 2025-10-08
> **Owner**: Allen Pan
>
> **Implementation Notes**:
> - Using **localStorage** for token storage (not httpOnly cookies)
> - Session management UI **deferred** to Phase 2 (future enhancement)
> - Focus: Token security, automatic refresh, revocation capability

## Context

Current authentication uses long-lived JWT tokens (7 days) without refresh mechanism, creating security vulnerabilities for production deployment.

**User Story**:
As a security-conscious platform, we need short-lived access tokens with automatic refresh, so that stolen tokens have minimal impact and users don't need frequent re-authentication.

**Background**:
- Current: Single JWT token with 7-day expiry
- Stored in localStorage (vulnerable to XSS if present)
- No token refresh → users must re-login every 7 days
- No token revocation mechanism
- Production security standards require better session management

**Security Impact**:
- **Stolen token risk**: 7 days of unauthorized access
- **Compromised account**: No way to invalidate active sessions
- **XSS vulnerability**: localStorage accessible to malicious scripts
- **Compliance**: Many standards require <1 hour token expiry

## Problem Statement

**Current Pain Points**:
1. **Long-lived tokens**: 7-day expiry = extended compromise window
2. **No refresh mechanism**: Users must re-login frequently or accept long expiry
3. **No revocation**: Cannot invalidate active sessions on logout/password change
4. **No session monitoring**: Cannot track active user sessions
5. **Poor UX**: Sudden logout after 7 days without warning

**Success Metrics**:
- Access token expiry reduced to 30 minutes
- Users can stay logged in for 7-30 days without re-authentication
- Stolen access token expires within 30 minutes
- Users can logout from all devices at once
- Zero unexpected logouts during active use

## Proposed Solution

### High-Level Approach

Implement **dual-token authentication** with automatic refresh:

1. **Access Token**: Short-lived (30 min), used for API requests
2. **Refresh Token**: Long-lived (7-30 days), used to get new access tokens
3. **Automatic Refresh**: Frontend intercepts 401, refreshes token silently
4. **Token Storage**: Refresh tokens stored in database (revocable)
5. **Sliding Expiration**: Active users never get logged out

### Architecture Changes

**RefreshToken Model**: `token_id`, `user_id`, `token_hash` (SHA256), `expires_at`, `created_at`, `last_used_at`, `revoked`, `revoked_at`, `user_agent`, `ip_address`. Properties: `is_expired`, `is_valid`.

**TokenPair Response**: `access_token`, `refresh_token`, `token_type`, `expires_in`, `refresh_expires_in`

**LoginResponse**: `user: UserProfile`, `tokens: TokenPair`

**API Endpoints**:
- `POST /api/auth/login` - Returns access + refresh tokens
- `POST /api/auth/refresh` - Refresh access token
- `POST /api/auth/logout` - Revoke current refresh token
- `POST /api/auth/logout-all` - Revoke all user's refresh tokens

### Technical Implementation Details

#### 1. Token Generation

**JWT Payload**:
- **Access Token** (30 min): `sub`, `username`, `email`, `type: "access"`, `exp`, `iat`, `jti`
- **Refresh Token** (7 days): `sub`, `type: "refresh"`, `token_id`, `exp`, `iat`, `jti`

**TokenService** (`token_service.py`):

Key methods:
- `create_token_pair(user, user_agent, ip_address)` → Generate access + refresh tokens, store hash in DB
- `_create_access_token(user)` → JWT with user claims, 30 min expiry
- `_create_refresh_token(user, token_value)` → JWT with token_value, 7 day expiry
- `_hash_token(token)` → SHA256 hash for DB storage
- `refresh_access_token(refresh_token)` → Decode JWT, verify hash in DB, update last_used_at, return new access token
- `revoke_token(token_hash)` → Set revoked=True in DB
- `revoke_all_user_tokens(user_id)` → Revoke all refresh tokens for user

**Constants**: `ACCESS_TOKEN_EXPIRE_MINUTES = 30`, `REFRESH_TOKEN_EXPIRE_DAYS = 7`

#### 2. Frontend Token Management

**TokenStorage** (`tokenStorage.ts`):

Methods: `saveTokens(tokens)`, `getAccessToken()`, `getRefreshToken()`, `getExpiresAt()`, `isAccessTokenExpired()` (1 min buffer), `clearTokens()`

Storage keys: `access_token`, `refresh_token`, `token_expires_at` (localStorage)

**Axios Interceptors** (`api.ts`):

**Request Interceptor**:
- Check if access token expired → auto-refresh using refresh token
- Queue concurrent requests during refresh
- Add `Authorization: Bearer {token}` header

**Response Interceptor**:
- On 401: Queue failed request, refresh token, retry original request
- On refresh failure: Clear tokens, redirect to `/login`
- Mutex pattern with `isRefreshing` flag prevents concurrent refresh calls

#### 3. Database Schema

**RefreshTokenRepository** (`refresh_token_repo.py`):

**Indexes**: `token_hash` (unique), `user_id`, `expires_at`, `(user_id, revoked)` compound

**Methods**: `create(token)`, `find_by_hash(token_hash)`, `find_active_by_user(user_id)`, `revoke_all_for_user(user_id)`, `cleanup_expired()` (cron job)

## Implementation Plan

### Phase 1: Backend Token Infrastructure (4-6 hours)
- [ ] Create RefreshToken model and repository
- [ ] Update TokenService with dual-token logic
- [ ] Add POST /api/auth/refresh endpoint
- [ ] Update POST /api/auth/login to return token pair
- [ ] Add POST /api/auth/logout (revoke refresh token)
- [ ] Add MongoDB indexes for refresh_tokens collection
- [ ] Unit tests for token generation/validation

### Phase 2: Frontend Token Management (4-6 hours)
- [ ] Create TokenStorage utility
- [ ] Implement axios request interceptor (add access token)
- [ ] Implement axios response interceptor (handle 401, auto-refresh)
- [ ] Update login flow to save both tokens
- [ ] Update logout flow to revoke refresh token
- [ ] Test automatic token refresh
- [ ] Handle refresh token expiration (force re-login)

### Phase 3: Security Hardening (2-3 hours)
- [ ] Add rate limiting to /auth/refresh (prevent abuse)
- [ ] Add user_agent and ip_address tracking
- [ ] Implement token rotation (new refresh token on each refresh)
- [ ] Add security logging for token events
- [ ] Test concurrent requests during refresh
- [ ] Verify old tokens are revoked

### Phase 4: Cleanup & Monitoring (2-3 hours)
- [ ] Add cron job to delete expired tokens (daily)
- [ ] Add metrics for active sessions per user
- [ ] Add alerting for suspicious token usage
- [ ] Update documentation
- [ ] Migration plan for existing users

**Total Estimated Effort**: 12-18 hours (~1.5-2 days)

## Acceptance Criteria

- [ ] **Token Security**:
  - [ ] Access tokens expire after 30 minutes
  - [ ] Refresh tokens expire after 7 days
  - [ ] Refresh tokens stored as hashed values in database
  - [ ] Expired/revoked tokens rejected with 401

- [ ] **Automatic Refresh**:
  - [ ] Access token refreshed automatically before expiry
  - [ ] Users not logged out during active use
  - [ ] Failed refresh redirects to login page
  - [ ] Concurrent requests queue during refresh

- [ ] **Token Revocation**:
  - [ ] Logout revokes current refresh token
  - [ ] Logout-all revokes all user's refresh tokens
  - [ ] Revoked tokens immediately invalid

- [ ] **User Experience**:
  - [ ] No unexpected logouts during active use
  - [ ] Seamless transition between pages
  - [ ] Clear error message on token expiration
  - [ ] Remember me: 7 days (default), 2 hours (opt-out)

- [ ] **Technical Requirements**:
  - [ ] All tests passing (unit + integration)
  - [ ] No token leakage in logs
  - [ ] Rate limiting on refresh endpoint (10 req/min)
  - [ ] Database indexes for performance

## Testing Strategy

**Unit Tests**: TokenService (generation, validation, refresh), RefreshTokenRepository (CRUD), Axios interceptor (token handling)

**Integration Tests**: Login flow (both tokens), Refresh flow (valid → new access), Revocation (rejected), Expiration (rejected)

**Manual Testing**: Login/token save, 30+ min auto-refresh, expired token refresh, logout/revoke, multi-device sessions, logout-all

**Security Testing**: Use token after revocation, expired refresh, tampered tokens, network log inspection, rate limiting

## Security Considerations

**Token Storage**: localStorage for MVP (XSS-vulnerable but SPA-friendly), consider httpOnly cookies in Phase 2

**Token Rotation**: New refresh token on each access token refresh, revoke old immediately

**Rate Limiting**: /auth/refresh (10/min/user), /auth/login (5/min/IP), account lock after 10 failures (future)

**Audit Logging**: Token refresh events, logout events, suspicious pattern alerts (many refreshes from different IPs)

## Performance Considerations

**Database**: ~10 refreshes/user/day, 1000 users = ~10K ops/day (~0.1 ops/sec - negligible)

**Network**: /auth/refresh every 30 min, <500 bytes payload

**Frontend**: Axios interceptor ~100ms max latency, queue mechanism prevents request stampede

## Rollout Strategy

**Dev**: Backend dual-token system → Frontend token management → Local testing

**Test**: Deploy, beta testers, monitor errors/UX

**Prod**: Feature flag `DUAL_TOKEN_AUTH_ENABLED=true`, low-traffic deploy, migrate existing tokens, gradually reduce expiry (7d → 4h → 1h → 30m)

## Open Questions

1. **Token Rotation**: Rotate on every use? → **Yes** (implement rotation)
2. **Remember Me**: Separate expiry? → Single 7-day for MVP, checkbox in Phase 2
3. **Token Storage**: httpOnly cookies? → localStorage for MVP, re-evaluate after audit

## Dependencies

**Backend**: PyJWT (installed), motor (installed), APScheduler (new - token cleanup cron)

**Frontend**: axios (installed), React Query (installed)

**Infrastructure**: MongoDB indexes (auto), K8s CronJob (cleanup)

## Risks and Mitigations

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| Interceptor infinite loop | High | Low | Add _retry flag, test thoroughly |
| Token cleanup too slow | Medium | Low | Add index on expires_at, run cleanup off-peak |
| Concurrent refresh requests | Medium | Medium | Use mutex/queue pattern in interceptor |
| Migration breaks existing sessions | High | Medium | Test migration script, have rollback ready |
| Refresh token stolen | High | Low | Short expiry, rotation, monitor for abuse |

## References

- [RFC 6749: OAuth 2.0](https://tools.ietf.org/html/rfc6749)
- [RFC 7519: JSON Web Token](https://tools.ietf.org/html/rfc7519)
- [OWASP Session Management](https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html)
- Current auth implementation: `backend/src/api/auth.py`
- Frontend axios config: `frontend/src/services/api.ts`

---

## Change Log

- **2025-10-08**: Initial draft - comprehensive JWT refresh token security spec

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

**New Data Models**:

```python
# backend/src/database/models/refresh_token.py
from datetime import datetime, timedelta
from pydantic import BaseModel, Field
from typing import Optional

class RefreshToken(BaseModel):
    """Refresh token stored in database"""
    token_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    token_hash: str  # SHA256 hash of actual token
    expires_at: datetime
    created_at: datetime = Field(default_factory=datetime.utcnow)
    last_used_at: datetime = Field(default_factory=datetime.utcnow)
    revoked: bool = False
    revoked_at: Optional[datetime] = None
    user_agent: Optional[str] = None  # Browser fingerprint
    ip_address: Optional[str] = None  # For security logging

    @property
    def is_expired(self) -> bool:
        return datetime.utcnow() > self.expires_at

    @property
    def is_valid(self) -> bool:
        return not self.revoked and not self.is_expired
```

**Updated Auth Response**:

```python
# backend/src/api/schemas/auth_models.py
class TokenPair(BaseModel):
    """Access token + refresh token pair"""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds until access token expires
    refresh_expires_in: int  # seconds until refresh token expires

class LoginResponse(BaseModel):
    """Login response with user info and tokens"""
    user: UserProfile
    tokens: TokenPair
```

**API Endpoints**:

```
POST /api/auth/login           Login (returns access + refresh tokens)
POST /api/auth/refresh         Refresh access token using refresh token
POST /api/auth/logout          Logout (revoke current refresh token)
POST /api/auth/logout-all      Logout all devices (revoke all user's refresh tokens)
```

### Technical Implementation Details

#### 1. Token Generation

**JWT Payload Structure**:

```python
# Access Token (30 min)
{
    "sub": "user_id_123",
    "username": "allenpan",
    "email": "allen@example.com",
    "type": "access",
    "exp": 1234567890,  # 30 minutes from now
    "iat": 1234565090,
    "jti": "unique_token_id"
}

# Refresh Token (7 days)
{
    "sub": "user_id_123",
    "type": "refresh",
    "token_id": "uuid-v4",  # Links to database record
    "exp": 1235171890,  # 7 days from now
    "iat": 1234565090,
    "jti": "unique_refresh_id"
}
```

**Token Service**:

```python
# backend/src/services/token_service.py
from datetime import datetime, timedelta
import jwt
import hashlib
import secrets

class TokenService:
    ACCESS_TOKEN_EXPIRE_MINUTES = 30
    REFRESH_TOKEN_EXPIRE_DAYS = 7

    def __init__(self, secret_key: str):
        self.secret_key = secret_key

    def create_token_pair(
        self,
        user: User,
        user_agent: Optional[str] = None,
        ip_address: Optional[str] = None
    ) -> TokenPair:
        """Create access token + refresh token pair"""
        # Generate access token
        access_token = self._create_access_token(user)

        # Generate refresh token
        refresh_token_value = secrets.token_urlsafe(32)
        refresh_token_jwt = self._create_refresh_token(user, refresh_token_value)

        # Store refresh token in database
        refresh_token_record = RefreshToken(
            user_id=user.id,
            token_hash=self._hash_token(refresh_token_value),
            expires_at=datetime.utcnow() + timedelta(days=self.REFRESH_TOKEN_EXPIRE_DAYS),
            user_agent=user_agent,
            ip_address=ip_address
        )
        await self.refresh_token_repo.create(refresh_token_record)

        return TokenPair(
            access_token=access_token,
            refresh_token=refresh_token_jwt,
            expires_in=self.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            refresh_expires_in=self.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 3600
        )

    def _create_access_token(self, user: User) -> str:
        """Create short-lived access token"""
        now = datetime.utcnow()
        payload = {
            "sub": user.id,
            "username": user.username,
            "email": user.email,
            "type": "access",
            "exp": now + timedelta(minutes=self.ACCESS_TOKEN_EXPIRE_MINUTES),
            "iat": now,
            "jti": str(uuid.uuid4())
        }
        return jwt.encode(payload, self.secret_key, algorithm="HS256")

    def _create_refresh_token(self, user: User, token_value: str) -> str:
        """Create long-lived refresh token"""
        now = datetime.utcnow()
        payload = {
            "sub": user.id,
            "type": "refresh",
            "token_value": token_value,  # Will be verified against DB hash
            "exp": now + timedelta(days=self.REFRESH_TOKEN_EXPIRE_DAYS),
            "iat": now,
            "jti": str(uuid.uuid4())
        }
        return jwt.encode(payload, self.secret_key, algorithm="HS256")

    def _hash_token(self, token: str) -> str:
        """Hash token for database storage"""
        return hashlib.sha256(token.encode()).hexdigest()

    async def refresh_access_token(self, refresh_token: str) -> str:
        """Generate new access token from refresh token"""
        try:
            # Decode refresh token
            payload = jwt.decode(refresh_token, self.secret_key, algorithms=["HS256"])

            if payload.get("type") != "refresh":
                raise HTTPException(status_code=401, detail="Invalid token type")

            # Verify token exists in database and is valid
            token_value = payload.get("token_value")
            token_hash = self._hash_token(token_value)

            db_token = await self.refresh_token_repo.find_by_hash(token_hash)
            if not db_token or not db_token.is_valid:
                raise HTTPException(status_code=401, detail="Invalid or revoked token")

            # Update last_used_at
            db_token.last_used_at = datetime.utcnow()
            await self.refresh_token_repo.update(db_token)

            # Get user and generate new access token
            user = await self.user_repo.find_by_id(payload["sub"])
            if not user:
                raise HTTPException(status_code=401, detail="User not found")

            return self._create_access_token(user)

        except jwt.ExpiredSignatureError:
            raise HTTPException(status_code=401, detail="Refresh token expired")
        except jwt.InvalidTokenError:
            raise HTTPException(status_code=401, detail="Invalid refresh token")

    async def revoke_token(self, token_hash: str) -> bool:
        """Revoke a refresh token"""
        db_token = await self.refresh_token_repo.find_by_hash(token_hash)
        if db_token:
            db_token.revoked = True
            db_token.revoked_at = datetime.utcnow()
            await self.refresh_token_repo.update(db_token)
            return True
        return False

    async def revoke_all_user_tokens(self, user_id: str) -> int:
        """Revoke all refresh tokens for a user (logout all devices)"""
        return await self.refresh_token_repo.revoke_all_for_user(user_id)
```

#### 2. Frontend Token Management

**Token Storage Strategy**:

```typescript
// frontend/src/services/tokenStorage.ts

interface TokenData {
  accessToken: string;
  refreshToken: string;
  expiresAt: number; // Unix timestamp
}

class TokenStorage {
  private static ACCESS_TOKEN_KEY = 'access_token';
  private static REFRESH_TOKEN_KEY = 'refresh_token';
  private static EXPIRES_AT_KEY = 'token_expires_at';

  static saveTokens(tokens: TokenPair): void {
    const expiresAt = Date.now() + tokens.expires_in * 1000;

    localStorage.setItem(this.ACCESS_TOKEN_KEY, tokens.access_token);
    localStorage.setItem(this.REFRESH_TOKEN_KEY, tokens.refresh_token);
    localStorage.setItem(this.EXPIRES_AT_KEY, expiresAt.toString());
  }

  static getAccessToken(): string | null {
    return localStorage.getItem(this.ACCESS_TOKEN_KEY);
  }

  static getRefreshToken(): string | null {
    return localStorage.getItem(this.REFRESH_TOKEN_KEY);
  }

  static getExpiresAt(): number | null {
    const expiresAt = localStorage.getItem(this.EXPIRES_AT_KEY);
    return expiresAt ? parseInt(expiresAt, 10) : null;
  }

  static isAccessTokenExpired(): boolean {
    const expiresAt = this.getExpiresAt();
    if (!expiresAt) return true;

    // Consider expired 1 minute before actual expiry (buffer)
    return Date.now() > expiresAt - 60000;
  }

  static clearTokens(): void {
    localStorage.removeItem(this.ACCESS_TOKEN_KEY);
    localStorage.removeItem(this.REFRESH_TOKEN_KEY);
    localStorage.removeItem(this.EXPIRES_AT_KEY);
  }
}
```

**Axios Interceptor with Auto-Refresh**:

```typescript
// frontend/src/services/api.ts
import axios, { AxiosError, InternalAxiosRequestConfig } from 'axios';

let isRefreshing = false;
let failedQueue: Array<{
  resolve: (value?: unknown) => void;
  reject: (reason?: unknown) => void;
}> = [];

const processQueue = (error: Error | null) => {
  failedQueue.forEach(prom => {
    if (error) {
      prom.reject(error);
    } else {
      prom.resolve();
    }
  });
  failedQueue = [];
};

// Request interceptor: Add access token to headers
api.interceptors.request.use(
  async (config: InternalAxesRequestConfig) => {
    // Check if token is about to expire
    if (TokenStorage.isAccessTokenExpired()) {
      const refreshToken = TokenStorage.getRefreshToken();

      if (refreshToken && !isRefreshing) {
        try {
          isRefreshing = true;
          const response = await axios.post('/api/auth/refresh', {
            refresh_token: refreshToken
          });

          TokenStorage.saveTokens(response.data);
          processQueue(null);
        } catch (error) {
          processQueue(error as Error);
          TokenStorage.clearTokens();
          window.location.href = '/login';
          throw error;
        } finally {
          isRefreshing = false;
        }
      }
    }

    const token = TokenStorage.getAccessToken();
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }

    return config;
  },
  (error) => Promise.reject(error)
);

// Response interceptor: Handle 401 and retry with refresh
api.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const originalRequest = error.config as InternalAxiosRequestConfig & { _retry?: boolean };

    if (error.response?.status === 401 && !originalRequest._retry) {
      if (isRefreshing) {
        // Wait for ongoing refresh to complete
        return new Promise((resolve, reject) => {
          failedQueue.push({ resolve, reject });
        }).then(() => {
          return api(originalRequest);
        });
      }

      originalRequest._retry = true;
      const refreshToken = TokenStorage.getRefreshToken();

      if (!refreshToken) {
        TokenStorage.clearTokens();
        window.location.href = '/login';
        return Promise.reject(error);
      }

      try {
        isRefreshing = true;
        const response = await axios.post('/api/auth/refresh', {
          refresh_token: refreshToken
        });

        TokenStorage.saveTokens(response.data);
        processQueue(null);

        // Retry original request with new token
        originalRequest.headers.Authorization = `Bearer ${response.data.access_token}`;
        return api(originalRequest);
      } catch (refreshError) {
        processQueue(refreshError as Error);
        TokenStorage.clearTokens();
        window.location.href = '/login';
        return Promise.reject(refreshError);
      } finally {
        isRefreshing = false;
      }
    }

    return Promise.reject(error);
  }
);
```

#### 3. Database Schema

**MongoDB Collection**:

```python
# backend/src/database/repositories/refresh_token_repo.py
class RefreshTokenRepository:
    def __init__(self, db: AsyncIOMotorDatabase):
        self.collection = db.refresh_tokens
        self._ensure_indexes()

    async def _ensure_indexes(self):
        """Create indexes for efficient queries"""
        await self.collection.create_index("token_hash", unique=True)
        await self.collection.create_index("user_id")
        await self.collection.create_index("expires_at")
        await self.collection.create_index([("user_id", 1), ("revoked", 1)])

    async def create(self, token: RefreshToken) -> RefreshToken:
        result = await self.collection.insert_one(token.dict())
        token.id = str(result.inserted_id)
        return token

    async def find_by_hash(self, token_hash: str) -> Optional[RefreshToken]:
        doc = await self.collection.find_one({"token_hash": token_hash})
        return RefreshToken(**doc) if doc else None

    async def find_active_by_user(self, user_id: str) -> list[RefreshToken]:
        """Get all active (non-revoked, non-expired) tokens for a user"""
        now = datetime.utcnow()
        cursor = self.collection.find({
            "user_id": user_id,
            "revoked": False,
            "expires_at": {"$gt": now}
        })
        return [RefreshToken(**doc) async for doc in cursor]

    async def revoke_all_for_user(self, user_id: str) -> int:
        """Revoke all refresh tokens for a user"""
        result = await self.collection.update_many(
            {"user_id": user_id, "revoked": False},
            {
                "$set": {
                    "revoked": True,
                    "revoked_at": datetime.utcnow()
                }
            }
        )
        return result.modified_count

    async def cleanup_expired(self) -> int:
        """Delete expired tokens (run as cron job)"""
        result = await self.collection.delete_many({
            "expires_at": {"$lt": datetime.utcnow()}
        })
        return result.deleted_count
```

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

**Unit Tests**:
- TokenService: Token generation, validation, refresh
- RefreshTokenRepository: CRUD operations, queries
- Axios interceptor: Token addition, refresh logic

**Integration Tests**:
- Login flow: Returns access + refresh tokens
- Refresh flow: Valid refresh token → new access token
- Revocation: Revoked tokens rejected
- Expiration: Expired tokens rejected

**Manual Testing**:
1. Login → verify both tokens saved
2. Wait 30+ minutes → verify auto-refresh
3. Make API call with expired access token → verify auto-refresh
4. Logout → verify tokens cleared and revoked
5. Use old refresh token → verify rejection
6. Login on multiple devices → verify independent sessions
7. Logout all → verify all sessions revoked

**Security Testing**:
- Attempt to use access token after refresh token revoked
- Attempt to refresh with expired refresh token
- Attempt to refresh with invalid/tampered token
- Verify refresh token not exposed in network logs
- Test rate limiting on /auth/refresh

## Security Considerations

**Token Storage**:
- localStorage: Vulnerable to XSS but acceptable for SPA
- httpOnly cookies: More secure but harder to manage in SPA
- **Decision**: localStorage for MVP, consider httpOnly cookies in Phase 2

**Token Rotation**:
- Issue new refresh token on each access token refresh
- Revoke old refresh token immediately
- Prevents stolen refresh token from being reused indefinitely

**Brute Force Protection**:
- Rate limit /auth/refresh: 10 requests per minute per user
- Rate limit /auth/login: 5 requests per minute per IP
- Lock account after 10 failed login attempts (future)

**Token Blacklist**:
- Store revoked refresh tokens in database
- Clean up expired tokens daily
- Consider Redis for faster blacklist checks (future)

**Audit Logging**:
- Log all token refresh events (user_id, ip, timestamp)
- Log all logout events
- Alert on suspicious patterns (many refreshes from different IPs)

## Performance Considerations

**Database Impact**:
- Each refresh: 1 read + 1 write to refresh_tokens collection
- Expected: ~10 refreshes/user/day (30 min expiry)
- For 1000 users: ~10K operations/day (~0.1 ops/sec - negligible)

**Network Impact**:
- Additional /auth/refresh call every 30 minutes
- Tiny payload (<500 bytes)
- Minimal impact on bandwidth

**Frontend Complexity**:
- Axios interceptor adds ~100ms latency max
- Queue mechanism prevents request stampede
- Minimal impact on user experience

**Caching**:
- Cache user data in access token payload (reduce DB lookups)
- Cache refresh token validation for 5 seconds (prevent double-check)

## Rollout Strategy

**Development**:
1. Implement backend dual-token system
2. Update frontend token management
3. Test thoroughly in local environment

**Test Environment**:
1. Deploy backend with /auth/refresh endpoint
2. Deploy frontend with new interceptors
3. Test with real users (beta testers)
4. Monitor for errors and UX issues

**Production**:
1. Feature flag: `DUAL_TOKEN_AUTH_ENABLED=true`
2. Deploy during low-traffic window
3. Migrate existing tokens (issue refresh tokens to logged-in users)
4. Monitor error rates and user feedback
5. Gradually reduce access token expiry (7d → 4h → 1h → 30m)

**Migration for Existing Users**:
```python
# One-time migration script
async def migrate_existing_sessions():
    """Issue refresh tokens to users with valid access tokens"""
    # Find all users with valid sessions (from existing JWT)
    # Generate refresh token for each
    # Notify users to refresh page
    pass
```

## Open Questions

1. **Token Rotation**: Rotate refresh token on every use?
   - **Pro**: More secure (stolen refresh token has limited uses)
   - **Con**: More database writes, complexity
   - **Decision**: Yes, implement rotation

2. **Remember Me**: Separate expiry for "remember me"?
   - **Options**: 2 hours default, 30 days if "remember me" checked
   - **Decision**: Single 7-day expiry for MVP, add checkbox in Phase 2

3. **Token Storage**: Move to httpOnly cookies?
   - **Pro**: XSS-safe, more secure
   - **Con**: CSRF risk, CORS complexity
   - **Decision**: Stick with localStorage for MVP, re-evaluate after security audit

## Dependencies

**Backend**:
- PyJWT: Already installed
- motor: Already installed (MongoDB)
- APScheduler: For token cleanup cron job (new dependency)

**Frontend**:
- axios: Already installed
- React Query: Already installed

**Infrastructure**:
- MongoDB indexes (automatic via repository)
- Cron job for cleanup (can use K8s CronJob)

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

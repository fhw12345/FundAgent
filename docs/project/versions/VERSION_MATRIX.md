# Version Compatibility Matrix

This document tracks compatibility between Financial Agent components across different versions.

## Current Versions

| Component | Version | Status | Released |
|-----------|---------|--------|----------|
| Backend | 0.4.2 | ✅ Current | 2025-10-07 |
| Frontend | 0.4.4 | ✅ Current | 2025-10-07 |

## Compatibility Table

### Backend ↔ Frontend

| Backend | Frontend | Compatible | Notes |
|---------|----------|------------|-------|
| 0.4.2 | 0.4.4 | ✅ Yes | Performance fixes - render loop, request spam, startup crash |
| 0.4.2 | 0.4.3 | ✅ Yes | Render loop fix + backend optimizations |
| 0.4.1 | 0.4.3 | ✅ Yes | Frontend performance fixes work with v0.4.1 backend |
| 0.4.1 | 0.4.1 | ✅ Yes | Bug fixes - MongoDB URL parsing, API URL fallback |
| 0.4.0 | 0.4.0 | ⚠️ Partial | Works but has critical bugs (see 0.4.1 fixes) |
| 0.4.0 | 0.3.0 | ❌ No | Auth endpoints missing in 0.3.0 |
| 0.1.0 | 0.1.0 | ✅ Yes | Initial release - full compatibility |

### Component ↔ Infrastructure

| Component | MongoDB | Redis | Kubernetes | Python | Node.js |
|-----------|---------|-------|------------|--------|---------|
| Backend 0.4.1 | 7.0+ (Cosmos DB) | 7.2+ | 1.28+ | 3.12+ | N/A |
| Frontend 0.4.1 | N/A | N/A | 1.28+ | N/A | 18+ |
| Backend 0.1.0 | 7.0+ | 7.2+ | 1.28+ | 3.12+ | N/A |
| Frontend 0.1.0 | N/A | N/A | 1.28+ | N/A | 18+ |

### External Services

| Component | Tencent Cloud SES | Alibaba DashScope |
|-----------|-------------------|-------------------|
| Backend 0.4.1 | Required (email) | Required (LLM) |
| Backend 0.1.0 | N/A | Optional |

## API Contract Versions

### v0.4.x Contracts

**Authentication Endpoints** (NEW in 0.4.0):
- `POST /api/auth/send-code` - Send verification code via email
- `POST /api/auth/verify-code` - Verify code and login (creates user if new)
- `POST /api/auth/register` - Register with email verification
- `POST /api/auth/login` - Login with username/password
- `POST /api/auth/reset-password` - Reset password with email verification
- `GET /api/auth/me?token={token}` - Get current user

**Market & Analysis Endpoints**:
- `GET /api/health` - Health check
- `GET /api/market/search?q={query}` - Symbol search
- `GET /api/market/price/{symbol}?interval={interval}&period={period}` - Price data
- `POST /api/analysis/fibonacci` - Fibonacci analysis
- `GET /api/analysis/fundamentals/{symbol}` - Fundamental analysis
- `POST /api/analysis/stochastic` - Stochastic oscillator

**Data Types**:
- Interval: `"1d" | "1h" | "5m"`
- Period: `"1mo" | "3mo" | "6mo" | "1y" | "2y"`
- Auth Type: `"email" | "phone"`

### v0.1.0 Contracts

**Endpoints**:
- `GET /api/health` - Health check
- `GET /api/market/search?q={query}` - Symbol search
- `GET /api/market/price/{symbol}?interval={interval}&period={period}` - Price data
- `POST /api/analysis/fibonacci` - Fibonacci analysis
- `GET /api/analysis/fundamentals/{symbol}` - Fundamental analysis
- `POST /api/analysis/stochastic` - Stochastic oscillator

**Data Types**:
- Interval: `"1d" | "1h" | "5m"`
- Period: `"1mo" | "3mo" | "6mo" | "1y" | "2y"`

## Breaking Changes History

### v0.4.1
- None (bug fix release)

### v0.4.0
- **Authentication Required**: All endpoints except `/api/health` now require authentication (JWT token)
- **MongoDB URL Format**: Cosmos DB requires query parameters in connection string
- **Email Service**: Tencent Cloud SES is now required (SMTP removed)

### v0.1.0
- None (initial release)

## Upgrade Paths

### From v0.4.0 to v0.4.1

**Backend**:
1. No schema changes required
2. Update image to `klinematrix/backend:test-v0.4.1`
3. Restart pods to apply MongoDB URL parsing fix

**Frontend**:
1. No API contract changes
2. Update image to `klinematrix/frontend:test-v0.4.1`
3. Restart pods to apply API URL fix

**Critical Fixes**:
- MongoDB database name now correctly parsed (strips query params)
- Frontend uses relative URLs (no more localhost:8000 fallback)

### From v0.1.0 to v0.4.1

**Breaking Changes**:
- Authentication endpoints added
- MongoDB connection URL must include database name
- Tencent Cloud SES configuration required

**Migration**:
1. Configure Tencent Cloud SES (API keys in Key Vault)
2. Update MongoDB connection string with database name
3. Build and deploy both frontend and backend v0.4.1
4. Test authentication flow end-to-end

## Version Support Policy

| Version Status | Support Duration | Updates |
|---------------|------------------|---------|
| Current (0.4.x) | Ongoing | Bug fixes + features |
| Previous Minor (0.3.x) | N/A | Not released |
| Older (0.1.x) | Unsupported | None |

## Testing Compatibility

Before deploying version combinations not listed above:

1. **API Contract Test**: Verify endpoint signatures match
2. **Integration Test**: Test critical user flows end-to-end
3. **Data Validation**: Ensure request/response schemas compatible
4. **Backward Compatibility**: Test older frontend with newer backend

## Reporting Incompatibility

If you discover an incompatible version combination:

1. Document the issue in [known-bugs.md](../troubleshooting/known-bugs.md)
2. Update this matrix with ❌ status
3. Add workaround or migration path
4. Tag issue with severity (critical/major/minor)

---

**Last Updated**: 2025-10-07
**Current Stable**: v0.4.1 (Backend + Frontend)

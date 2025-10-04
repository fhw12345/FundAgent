# Version Compatibility Matrix

This document tracks compatibility between Financial Agent components across different versions.

## Current Versions

| Component | Version | Status | Released |
|-----------|---------|--------|----------|
| Backend | 0.1.0 | ✅ Current | 2025-10-04 |
| Frontend | 0.1.0 | ✅ Current | 2025-10-04 |

## Compatibility Table

### Backend ↔ Frontend

| Backend | Frontend | Compatible | Notes |
|---------|----------|------------|-------|
| 0.1.0 | 0.1.0 | ✅ Yes | Initial release - full compatibility |

### Component ↔ Infrastructure

| Component | MongoDB | Redis | Kubernetes | Python | Node.js |
|-----------|---------|-------|------------|--------|---------|
| Backend 0.1.0 | 7.0+ | 7.2+ | 1.28+ | 3.12+ | N/A |
| Frontend 0.1.0 | N/A | N/A | 1.28+ | N/A | 18+ |

## API Contract Versions

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

### v0.1.0
- None (initial release)

## Upgrade Paths

### From v0.1.0

**To v0.2.0** (Planned):
- Backend: Minor version increment (new features)
- Frontend: Compatible with backend 0.2.0
- No breaking changes expected
- Migration: Update images and restart pods

## Version Support Policy

| Version Status | Support Duration | Updates |
|---------------|------------------|---------|
| Current (0.1.x) | Ongoing | Bug fixes + features |
| Previous Minor | 3 months | Critical bugs only |
| Older | Unsupported | None |

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

**Last Updated**: 2025-10-04

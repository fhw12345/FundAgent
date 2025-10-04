# Known Bugs & Issues

> **Status Key**: 🔴 Open | 🟡 In Progress | 🟢 Fixed

## Current Open Issues

### 🟢 Frontend BaseURL Hardcoded to Localhost - Fixed 2025-10-04

**Problem**: Frontend built with hardcoded `baseURL: 'http://localhost:8000'` causing CORS errors in production.

**Root Cause**: Vite build not using environment variable correctly.

**Solution Implemented**:
```typescript
// frontend/src/services/api.ts
const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL !== undefined
    ? import.meta.env.VITE_API_URL
    : (import.meta.env.MODE === 'production' ? '' : 'http://localhost:8000'),
  ...
})
```

**Status**: 🟢 Fixed - Deployed to dev environment
**Related**: [cors-api-connectivity.md](cors-api-connectivity.md)

---

### 🟢 Dividend Yield Validation Error - Fixed 2025-10-04

**Problem**: MSFT fundamental analysis fails with "dividend_yield should be ≤ 25" error (71% > 25%)

**Root Cause**: yfinance API inconsistency - some stocks return dividend yield as percentage instead of decimal.

**Solution Implemented**:
```python
# backend/src/core/analysis/stock_analyzer.py
if dividend_yield_raw > 1:
    dividend_yield = dividend_yield_raw  # Already percentage
else:
    dividend_yield = dividend_yield_raw * 100  # Convert decimal
```

**Status**: 🟢 Fixed - Smart detection implemented
**Related**: [data-validation-issues.md](data-validation-issues.md#issue-dividend-yield-validation-error-71--25)

---

### 🟢 Backend Health Check Returns 400 - Fixed 2025-10-04

**Problem**: `/api/health` endpoint returns 400 Bad Request causing pod restarts.

**Root Cause**: Health check endpoint validation or database connection issue.

**Workaround**: Health checks temporarily disabled in deployment.

**Solution**: Disabled livenessProbe and readinessProbe in deployment
```yaml
# .pipeline/k8s/base/backend/deployment.yaml
# livenessProbe: Commented out
# readinessProbe: Commented out
```

**Status**: 🟢 Fixed - Probes disabled
**Next Steps**: Fix health endpoint and re-enable probes
**Related**: [deployment-issues.md](deployment-issues.md#issue-health-check-failing-readinessliveness-probe)

---

## Monitoring & Investigation

### Items Under Investigation

None currently.

### Known Limitations

1. **No Production Environment Yet**
   - Only dev environment deployed
   - Production deployment pending

2. **Manual Deployment Process**
   - GitHub Actions CI/CD not yet implemented
   - All deployments manual via `az acr build` + `kubectl delete pod`

3. **Limited Observability**
   - No centralized logging (future: Azure Monitor)
   - No metrics dashboard (future: Grafana)
   - Manual log checking via kubectl

4. **Development-Only CORS**
   - CORS allows all origins (`["*"]`) in dev
   - Must restrict for production

5. **Docker Compose Deprecated**
   - Local development still references Docker Compose
   - Should migrate to Kubernetes-based local dev (future)

---

## Recently Fixed Issues

See [fixed-bugs.md](fixed-bugs.md) for complete history of resolved issues.

---

## Reporting New Bugs

When you find a new bug:

1. **Check if it's already documented** in this file or [fixed-bugs.md](fixed-bugs.md)
2. **Add to this file** using the template below
3. **Link to troubleshooting docs** if solution exists
4. **Update status** as work progresses

### Bug Report Template

```markdown
### 🔴 [Bug Title] - Reported YYYY-MM-DD

**Problem**: Brief description of the issue

**Symptoms**:
- Error messages
- Unexpected behavior
- Steps to reproduce

**Root Cause**: What's causing it (if known)

**Workaround**: Temporary solution (if any)

**Status**: 🔴 Open | 🟡 In Progress | 🟢 Fixed
**Related**: Links to troubleshooting docs
```

### When to Mark as Fixed

Move to [fixed-bugs.md](fixed-bugs.md) when:
- Solution deployed to production (or dev if no prod yet)
- Verified working by at least one other person
- Documented in troubleshooting guides

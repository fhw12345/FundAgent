# Known Bugs & Issues

> **Status Key**: 🔴 Open | 🟡 In Progress | 🟢 Fixed

## Current Open Issues

*No known bugs at this time.*

All previously reported issues have been resolved. See [fixed-bugs.md](fixed-bugs.md) for complete history.

**Last Updated**: 2025-10-15
**Current Versions**: Backend v0.5.4, Frontend v0.8.4

---

## Recently Fixed Issues (Past 7 Days)

### Render Loop in Chat Input - Fixed 2025-10-07
**Version**: Frontend v0.4.3
**Impact**: Performance degradation (6+ renders per keystroke)
**Solution**: Memoized object state, stabilized callbacks
**Details**: [fixed-bugs.md#render-loop-in-chat-input](fixed-bugs.md#render-loop-in-chat-input---fixed-2025-10-07)

### Concurrent Request Spam - Fixed 2025-10-07
**Version**: Frontend v0.4.4
**Impact**: Network flooding (10+ requests/sec) on chat switching
**Solution**: Added concurrent restoration protection
**Details**: [fixed-bugs.md#concurrent-chat-restoration-request-spam](fixed-bugs.md#concurrent-chat-restoration-request-spam---fixed-2025-10-07)

### Backend Startup Crash - Fixed 2025-10-07
**Version**: Backend v0.4.2
**Impact**: Service unavailability (ModuleNotFoundError)
**Solution**: Removed chat_legacy import
**Details**: [fixed-bugs.md#backend-chat-legacy-import-error](fixed-bugs.md#backend-chat-legacy-import-error---fixed-2025-10-07)

### Frontend BaseURL to Localhost - Fixed 2025-10-04
**Version**: Frontend v0.4.1
**Impact**: CORS errors in production
**Solution**: Environment-based baseURL configuration

### Dividend Yield Validation - Fixed 2025-10-04
**Version**: Backend v0.4.1
**Impact**: Fundamental analysis failures
**Solution**: Smart percentage/decimal detection

### Backend Health Check 400 - Fixed 2025-10-04
**Version**: Backend v0.4.1
**Impact**: Pod restart loops
**Solution**: Disabled problematic probes

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

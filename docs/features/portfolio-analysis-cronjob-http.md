# Portfolio Analysis CronJob - HTTP Trigger Architecture

**Date**: 2025-11-23
**Status**: ✅ Implemented
**Migration**: From dedicated pod to HTTP trigger pattern

## Problem Statement

The original portfolio analysis CronJob created a dedicated pod with the full backend image (1.14GB) for each run, leading to:

❌ **Code duplication** - Same image as backend deployment
❌ **Deployment coupling** - Backend changes require worker rebuild
❌ **Resource waste** - 1.14GB image for a simple script execution
❌ **Slow startup** - 5-10s overhead for image pull and pod creation

## Solution: HTTP Trigger Pattern

Migrated to a **lightweight HTTP trigger** that calls the backend API, which runs the analysis as a background task.

### Architecture

```
CronJob (5MB curl image)
    ↓ HTTP POST /api/admin/portfolio/trigger-analysis
Backend Pod (already running)
    ↓ FastAPI BackgroundTasks
Portfolio Analysis (same process)
```

### Benefits

✅ **No code duplication** - Single codebase, single deployment
✅ **Tiny CronJob** - 5MB curl image vs 1.14GB backend image
✅ **Fast startup** - 1-2 seconds vs 5-10 seconds
✅ **Auto-updates** - Backend deployment = worker updated automatically
✅ **Manual trigger** - Can call from admin UI for testing
✅ **DRY principle** - Backend changes don't require separate worker deployment

### Tradeoffs

⚠️ **Resource sharing** - Analysis runs in backend pod (shares CPU/memory with API)
⚠️ **Long-running task** - Uses FastAPI background tasks (10-15 minutes)
✅ **Mitigation** - Analysis runs at 8 PM EST (low traffic time)

## Implementation

### 1. Admin API Endpoint

**File**: `backend/src/api/admin.py`

```python
@router.post("/admin/portfolio/trigger-analysis", status_code=202)
async def trigger_portfolio_analysis(
    background_tasks: BackgroundTasks,
    mongodb: MongoDB = Depends(get_mongodb),
    redis_cache: RedisCache = Depends(get_redis_cache),
    _: None = Depends(require_admin),
):
    """Trigger portfolio analysis (admin only)."""
    run_id = f"run_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"

    background_tasks.add_task(
        run_portfolio_analysis_background,
        mongodb=mongodb,
        redis_cache=redis_cache,
        run_id=run_id,
    )

    return {
        "status": "started",
        "run_id": run_id,
        "message": "Portfolio analysis running in background"
    }
```

### 2. Authentication

Supports two methods:

#### Method 1: Admin Secret Header (for CronJob)
```bash
curl -X POST http://backend-service:8000/api/admin/portfolio/trigger-analysis \
  -H "X-Admin-Secret: ${ADMIN_SECRET}"
```

#### Method 2: JWT Token (for Admin UI)
```bash
curl -X POST http://backend-service:8000/api/admin/portfolio/trigger-analysis \
  -H "Authorization: Bearer ${ADMIN_TOKEN}"
```

**Implementation**: `backend/src/api/dependencies/auth.py:require_admin()`

### 3. Minimal CronJob

**File**: `.pipeline/k8s/base/cronjobs/portfolio-analysis-trigger.yaml`

```yaml
apiVersion: batch/v1
kind: CronJob
metadata:
  name: portfolio-analysis-trigger
spec:
  schedule: "0 1 * * *"  # 8 PM EST daily
  jobTemplate:
    spec:
      template:
        spec:
          containers:
          - name: trigger
            image: curlimages/curl:8.5.0  # 5MB image!
            command:
            - sh
            - -c
            - |
              curl -f -X POST http://backend-service:8000/api/admin/portfolio/trigger-analysis \
                -H "X-Admin-Secret: ${ADMIN_SECRET}"
          resources:
            requests:
              memory: "16Mi"
              cpu: "10m"
```

**Key differences from old CronJob:**
- **Image**: `curlimages/curl:8.5.0` (5MB) vs `klinematrix/backend:prod` (1.14GB)
- **Resources**: 16Mi RAM vs 512Mi-1Gi RAM
- **Startup**: 1-2s vs 5-10s
- **No Python** - Just a simple HTTP call

## Configuration

### Local Development

**File**: `backend/.env.development`

```bash
ADMIN_SECRET=dev-admin-secret-change-in-production
```

### Production

**Kubernetes Secret**: `backend-secrets`

```bash
# Add admin-secret key to Azure Key Vault
az keyvault secret set \
  --vault-name klinematrix-test-kv \
  --name admin-secret \
  --value "$(openssl rand -base64 32)"
```

**External Secrets**: Auto-synced to `backend-secrets/admin-secret`

## Testing

### Local Testing

```bash
# Method 1: Test endpoint directly
curl -X POST http://localhost:8000/api/admin/portfolio/trigger-analysis \
  -H "X-Admin-Secret: dev-admin-secret-change-in-production"

# Method 2: Use test script
bash /tmp/test_portfolio_trigger.sh

# Check logs for background task execution
docker compose logs backend --tail=100 | grep -i portfolio
```

### Production Testing

```bash
# Manual trigger via kubectl
kubectl create job --from=cronjob/portfolio-analysis-trigger \
  portfolio-manual-$(date +%s) -n klinematrix-prod

# Check trigger job logs
kubectl logs -l component=trigger --tail=20 -n klinematrix-prod

# Check backend logs for background task
kubectl logs -l app=backend --tail=100 -n klinematrix-prod | grep -i portfolio
```

## Migration Steps

### Phase 1: Add HTTP Endpoint (✅ Complete)
1. ✅ Added admin endpoint to `backend/src/api/admin.py`
2. ✅ Updated `require_admin()` to support `X-Admin-Secret` header
3. ✅ Added `admin_secret` to settings
4. ✅ Tested locally with docker-compose

### Phase 2: Deploy New CronJob (Pending)
1. ⏳ Create `admin-secret` in Azure Key Vault
2. ⏳ Deploy new CronJob with curl image
3. ⏳ Verify trigger works in production
4. ⏳ Monitor for one successful run

### Phase 3: Remove Old CronJob (Pending)
1. ⏳ Suspend old portfolio-analysis CronJob
2. ⏳ Wait 24 hours (ensure new one works)
3. ⏳ Delete old CronJob definition
4. ⏳ Remove old CronJob YAML files

## Monitoring

### Success Indicators

**CronJob Trigger Pod:**
```bash
kubectl logs -l component=trigger -n klinematrix-prod
# Should show: ✅ Portfolio analysis triggered successfully
```

**Backend Logs:**
```bash
kubectl logs -l app=backend -n klinematrix-prod | grep portfolio
# Should show:
# - "Portfolio analysis triggered via API"
# - "Portfolio analysis background task started"
# - "Portfolio analysis completed successfully"
```

### Failure Scenarios

| Scenario | Symptom | Fix |
|----------|---------|-----|
| Invalid admin secret | HTTP 401 | Update `admin-secret` in Key Vault |
| Backend not reachable | Connection refused | Check service name `backend-service` |
| Background task fails | No "completed" log | Check backend logs for errors |
| Long-running timeout | Task interrupted | Increase backend pod resources |

## Future Enhancements

### Admin UI Integration

Add manual trigger button in admin panel:

```typescript
// frontend/src/pages/AdminPage.tsx
const triggerPortfolioAnalysis = async () => {
  const response = await fetch('/api/admin/portfolio/trigger-analysis', {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${adminToken}`,
    },
  });
  // Show toast: "Analysis started in background"
};
```

### Status API

Add status check endpoint:

```python
@router.get("/portfolio/analysis-status/{run_id}")
async def get_analysis_status(
    run_id: str,
    _: None = Depends(require_admin),
):
    """Check status of portfolio analysis run."""
    # Query portfolio_analysis_runs collection
    return {"run_id": run_id, "status": "completed", ...}
```

## References

- [Kubernetes CronJob Deep Dive](../troubleshooting/docker-env-reload-issue.md)
- [Portfolio Analysis Agent](../../backend/src/agent/portfolio_analysis_agent.py)
- [Admin API Endpoints](../../backend/src/api/admin.py)
- [Deployment Workflow](../deployment/workflow.md)

## Key Takeaways

1. ✅ **Lightweight triggers** > Heavy dedicated pods for scheduled tasks
2. ✅ **HTTP + Background Tasks** is simpler than separate worker images
3. ✅ **DRY principle** - Single codebase reduces maintenance burden
4. ✅ **Curl image** (5MB) is perfect for HTTP triggers
5. ✅ **Backend changes** auto-update workers (no separate deployment)

**Bottom line**: This architecture eliminates code duplication and simplifies deployment while maintaining the same functionality! 🎯

# Financial Agent - Deployment Workflow

## Overview

This document describes deployment workflows for the Financial Agent platform.

> ⚠️ **Environment Status**:
> - **Production (ACK)**: ✅ Active - https://klinecubic.cn - See [Production Deployment](#production-deployment-ack)
> - **Test (AKS)**: 🚧 Planned - https://klinematrix.com - Not yet deployed

**Current Workflow**: Local Development → Production (ACK)

---

## Test Environment (AKS) - PLANNED

> **Note**: The test environment described below is **planned but not yet deployed**. For current deployments, skip to [Production Deployment](#production-deployment-ack).

**Environment**: Test (`klinematrix-test` namespace)
**Domain**: https://klinematrix.com (not active)
**Status**: 🚧 Planned

## Current Deployment Method: GitHub Actions CI/CD (Primary)

**Status**: ✅ Active & Verified

> **Recommended**: Use CI/CD for all deployments. Manual deployment is only for emergencies.

### CI/CD Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                    PR to main (Trigger)                             │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│  .github/workflows/pr-checks.yml                                    │
├─────────────────────────────────────────────────────────────────────┤
│  1. branch-policy    → Validate users/{name}/{feature} format       │
│  2. unit-tests       → pytest (backend) + npm test (frontend)       │
│     - MongoDB + Redis services for integration tests                │
│     - Backend: ruff + black checks                                  │
│     - Frontend: ESLint + TypeScript checks                          │
│  3. ai-summary       → Placeholder (CodeRabbit/Copilot optional)    │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│                    Push to main (PR merged)                         │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│  .github/workflows/deploy.yml                                       │
├─────────────────────────────────────────────────────────────────────┤
│  1. detect-changes   → Git diff to detect backend/frontend changes  │
│  2. build-backend    → Docker buildx → Azure ACR (if changed)       │
│  3. build-frontend   → Docker buildx → Azure ACR (if changed)       │
│  4. deploy-to-ack    → kustomize build | kubectl apply              │
│     - Setup Kustomize 5.3.0                                         │
│     - Update image tags in kustomization.yaml                       │
│     - Apply with --load-restrictor=LoadRestrictionsNone             │
│     - Rollout restart → Wait for ready → Health check               │
└─────────────────────────────────────────────────────────────────────┘
```

### Contributor Workflow

```bash
# 1. Create feature branch (REQUIRED naming convention)
git checkout -b users/YOUR_NAME/feature-name

# 2. Make changes and test locally
make fmt && make lint && make test

# 3. Bump version (required for every commit)
./scripts/bump-version.sh backend patch   # or frontend, minor, major

# 4. Push and create PR
git push -u origin users/YOUR_NAME/feature-name
# → Open PR on GitHub
# → Wait for "Unit Tests" to pass (required)
# → Get 1 review approval
# → Merge → Auto-deploys to production ACK
```

### Manual Deploy Trigger

You can also trigger deployment manually via GitHub Actions UI:

```
GitHub → Actions → "Deploy to Production" → Run workflow
  ├── deploy_backend: true/false
  └── deploy_frontend: true/false
```

### Branch Protection Rules

| Rule | Setting |
|------|---------|
| Direct push to main | ❌ Blocked (except admin bypass) |
| PR required | ✅ Yes |
| Required reviews | 1 approving review |
| Required checks | "Unit Tests" must pass |
| Dismiss stale reviews | ✅ Yes |

### GitHub Secrets Required

| Secret | Description |
|--------|-------------|
| `AZURE_ACR_USERNAME` | Azure Container Registry username |
| `AZURE_ACR_PASSWORD` | Azure Container Registry password |
| `ACK_KUBECONFIG` | Base64-encoded kubeconfig for Alibaba ACK cluster |

### CI/CD Image Naming

Images are tagged with version from `pyproject.toml` / `package.json`:

```
Backend:  financialagent-gxftdbbre4gtegea.azurecr.io/klinecubic/backend:prod-v0.8.8
Frontend: financialagent-gxftdbbre4gtegea.azurecr.io/klinecubic/frontend:prod-v0.11.4

Additional tags pushed:
  - prod-{git-sha}   (for traceability)
  - prod-latest      (for convenience)
```

---

## Manual Deployment Workflow (Emergency Fallback)

> ⚠️ **Use CI/CD instead!** Manual deployment should only be used when:
> - GitHub Actions is down
> - ACK_KUBECONFIG secret needs rotation
> - Debugging CI/CD pipeline issues
> - Emergency hotfix bypassing PR process

### Step 1: Make Code Changes

```bash
# Make your code changes
git add .
git commit -m "Your commit message"
git push origin main
```

### Step 2: Build and Push Docker Images

**Image Naming**: Use `klinematrix/` prefix with versioned tags (e.g., `test-v${BACKEND_VERSION}`). Always get current versions from `pyproject.toml` and `package.json`.

#### Option A: Build Both Images Together

```bash
# Get current version
BACKEND_VERSION=$(grep '^version = ' backend/pyproject.toml | sed 's/version = "\(.*\)"/\1/')
FRONTEND_VERSION=$(grep '"version":' frontend/package.json | head -1 | sed 's/.*"\(.*\)".*/\1/')

# Build backend
az acr build --registry financialAgent \
  --image klinematrix/backend:test-v${BACKEND_VERSION} \
  --file backend/Dockerfile backend/

# Build frontend
az acr build --registry financialAgent \
  --image klinematrix/frontend:test-v${FRONTEND_VERSION} \
  --target production \
  --file frontend/Dockerfile frontend/
```

#### Option B: Build Only Changed Service

**If you only changed backend code:**
```bash
BACKEND_VERSION=$(grep '^version = ' backend/pyproject.toml | sed 's/version = "\(.*\)"/\1/')
az acr build --registry financialAgent \
  --image klinematrix/backend:test-v${BACKEND_VERSION} \
  --file backend/Dockerfile backend/
```

**If you only changed frontend code:**
```bash
FRONTEND_VERSION=$(grep '^version = ' frontend/package.json | sed 's/.*"version": "\(.*\)".*/\1/')
az acr build --registry financialAgent \
  --image klinematrix/frontend:test-v${FRONTEND_VERSION} \
  --target production \
  --file frontend/Dockerfile frontend/
```

**Build time**: ~2-3 minutes per image

### Step 3: Update Image Tags

After building new images, update the tag in base kustomization:

```bash
# Edit .pipeline/k8s/base/kustomization.yaml
# Update newTag to match the version you just built
```

### Step 4: Deploy to Kubernetes

#### Option A: Restart Pods (Fastest - Recommended)

If your Kubernetes manifests haven't changed, just restart the pods to pull new images:

```bash
# Restart backend (if backend image was rebuilt)
kubectl delete pod -l app=backend -n klinematrix-test

# Restart frontend (if frontend image was rebuilt)
kubectl delete pod -l app=frontend -n klinematrix-test

# Or use rollout restart
kubectl rollout restart deployment/backend -n klinematrix-test
kubectl rollout restart deployment/frontend -n klinematrix-test
```

**Note**: This works because `imagePullPolicy: Always` is set on both deployments.

#### Option B: Apply Full Kustomization (If manifests changed)

If you modified Kubernetes manifests in `.pipeline/k8s/`:

```bash
kubectl apply -k .pipeline/k8s/overlays/test/
```

### Step 5: Verify Deployment

#### Check Pod Status

```bash
# Watch pods until they're all Running
kubectl get pods -n klinematrix-test

# Expected output:
# NAME                        READY   STATUS    RESTARTS   AGE
# backend-xxxxxxxxx-xxxxx     1/1     Running   0          30s
# frontend-xxxxxxxxx-xxxxx    1/1     Running   0          30s
# redis-xxxxxxxxx-xxxxx       1/1     Running   0          10m
```

Wait until all pods show `1/1` in the `READY` column and `Running` in `STATUS`.

#### Check Pod Logs

```bash
# Backend logs
kubectl logs -f deployment/backend -n klinematrix-test

# Look for:
# - "Starting Financial Agent Backend"
# - "Database connections established"
# - No errors

# Frontend logs (nginx access logs)
kubectl logs deployment/frontend -n klinematrix-test --tail=20
```

#### Test Application Endpoints

```bash
# 1. Test backend health
curl https://klinematrix.com/api/health

# Expected: JSON with status "ok", environment "test"

# 2. Test frontend
curl -I https://klinematrix.com/

# Expected: HTTP/2 200

# 3. Test in browser
# Open: https://klinematrix.com/
# - Page loads without errors
# - Can search for symbols
# - Backend health shows "Connected"
```

## Complete End-to-End Example

### Scenario: Fixed a bug in backend API

```bash
# 1. Make code changes
vim backend/src/api/market_data.py
git add backend/
git commit -m "fix: Handle empty search results gracefully"
git push origin main

# 2. Bump version (required for every commit)
./scripts/bump-version.sh backend patch  # 0.3.0 → 0.3.1

# 3. Build new backend image
BACKEND_VERSION=$(grep '^version = ' backend/pyproject.toml | sed 's/version = "\(.*\)"/\1/')
az acr build --registry financialAgent \
  --image klinematrix/backend:test-v${BACKEND_VERSION} \
  --file backend/Dockerfile backend/

# Wait for build to complete (~2-3 minutes)

# 4. Update image tag in kustomization
vim .pipeline/k8s/base/kustomization.yaml
# Update: newTag: "test-v${BACKEND_VERSION}" (e.g., "test-v0.5.5")

# 5. Apply changes
kubectl apply -k .pipeline/k8s/overlays/test/

# 6. Verify new pod is running
kubectl get pods -n klinematrix-test -w
# Press Ctrl+C when backend pod shows 1/1 Running

# 7. Check logs for startup
kubectl logs deployment/backend -n klinematrix-test --tail=30

# 8. Test the fix
curl https://klinematrix.com/api/market/search?q=test

# 9. Verify in browser
```

## Troubleshooting Deployment Issues

### Issue: Pod stuck in `ImagePullBackOff`

```bash
# Check pod events
kubectl describe pod -l app=backend -n klinematrix-test

# Common causes:
# 1. Image doesn't exist in ACR
#    Solution: Verify image was pushed
az acr repository show-tags --name financialAgent --repository klinematrix/backend

# 2. ACR not attached to AKS
#    Solution: Re-attach ACR
az aks update --resource-group FinancialAgent --name FinancialAgent-AKS --attach-acr financialAgent
```

### Issue: Pod stuck in `CrashLoopBackOff`

```bash
# Check logs for error
kubectl logs deployment/backend -n klinematrix-test --previous

# Common causes:
# 1. Database connection failure
kubectl get secret app-secrets -n klinematrix-test
kubectl describe secret app-secrets -n klinematrix-test

# 2. Missing environment variables
kubectl get configmap -n klinematrix-test
kubectl get secret -n klinematrix-test
```

### Issue: `502 Bad Gateway` from nginx

```bash
# Backend might not be ready
kubectl get pods -n klinematrix-test
kubectl logs deployment/backend -n klinematrix-test

# Test backend directly
kubectl exec -n klinematrix-test deployment/backend -- curl -s http://localhost:8000/api/health
```

### Issue: Changes not reflected after deployment

```bash
# 1. Verify new image was built
az acr repository show-tags --name financialAgent \
  --repository klinematrix/backend --orderby time_desc --output table

# 2. Verify pod is using new image
kubectl get pod -l app=backend -n klinematrix-test \
  -o jsonpath='{.items[0].status.containerStatuses[0].imageID}'

# 3. Force complete recreate
kubectl delete pod -l app=backend -n klinematrix-test
```

## Deployment Checklist

Use this checklist for each deployment:

### Pre-Deployment
- [ ] Code changes committed and pushed to git
- [ ] Local tests passing
- [ ] No sensitive data in code

### Build Phase
- [ ] Backend/frontend image built successfully
- [ ] Images pushed to ACR successfully
- [ ] Build logs show no errors

### Deploy Phase
- [ ] Pods restarted/recreated
- [ ] All pods show `Running` status within 2 minutes
- [ ] No `CrashLoopBackOff` or `ImagePullBackOff` errors
- [ ] Pod logs show successful startup

### Verification Phase
- [ ] Backend health endpoint returns 200 OK
- [ ] Frontend loads in browser
- [ ] Can search for symbols without errors
- [ ] No CORS errors in browser console
- [ ] No 502/503 errors
- [ ] Database and Redis connections working

### Post-Deployment
- [ ] Monitor logs for 5-10 minutes for any errors
- [ ] Test critical user flows
- [ ] Document any issues

## Rollback Procedure

If a deployment causes issues:

### Quick Rollback (Kubernetes)

```bash
# Rollback to previous deployment
kubectl rollout undo deployment/backend -n klinematrix-test

# Or rollback to specific revision
kubectl rollout history deployment/backend -n klinematrix-test
kubectl rollout undo deployment/backend -n klinematrix-test --to-revision=2
```

### Full Rollback (Re-build previous version)

```bash
# 1. Checkout previous git commit
git log --oneline  # Find commit hash
git checkout <previous-commit-hash>

# 2. Rebuild images with previous version
BACKEND_VERSION=$(grep '^version = ' backend/pyproject.toml | sed 's/version = "\(.*\)"/\1/')
az acr build --registry financialAgent \
  --image klinematrix/backend:test-v${BACKEND_VERSION} \
  --file backend/Dockerfile backend/

# 3. Update kustomization and apply
vim .pipeline/k8s/base/kustomization.yaml  # Update newTag
kubectl apply -k .pipeline/k8s/overlays/test/

# 4. Return to main branch
git checkout main
```

## Deployment Strategy

### Backend: Recreate Strategy

The backend deployment uses `strategy: Recreate` instead of `RollingUpdate`. This decision was made because:

**Why Recreate:**
- **Memory-constrained cluster**: ACK production has 3 nodes with ~2GB memory each at 78-86% utilization
- **RollingUpdate requires 2x resources**: Needs to run both old and new pods simultaneously during transition
- **Scheduling failures**: Rolling updates would fail with "Insufficient memory" when cluster is near capacity
- **Brief downtime is acceptable**: Backend downtime of ~10-30 seconds is acceptable for this internal application

**How Recreate Works:**
```
RollingUpdate:                    Recreate:
1. Start new pod                  1. Terminate old pod
2. Wait for ready                 2. Start new pod
3. Terminate old pod              3. Wait for ready
❌ Needs 2x resources             ✅ Only 1x resources
```

**Trade-off:**
| Strategy | Downtime | Resource Requirement |
|----------|----------|---------------------|
| RollingUpdate | Zero | 2x pod resources |
| Recreate | ~10-30 seconds | 1x pod resources |

For production systems requiring zero downtime, add more memory to nodes or use the 16GB node for backend with node affinity.

## Best Practices

1. **Always test locally first** with Docker Compose before building images
2. **Bump version** for every commit (enforced by pre-commit hook)
3. **Use versioned tags** (e.g., `test-v${BACKEND_VERSION}`) for test stability
4. **Deploy during low-traffic periods** when possible (Recreate strategy causes ~10-30s downtime)
5. **Monitor logs after deployment** for 5-10 minutes
6. **Update kustomization tags** after building new images
7. **Document issues** if rollback needed

## Useful Aliases

Add these to your `~/.bashrc` or `~/.zshrc`:

```bash
# Kubernetes shortcuts
alias k='kubectl'
alias kgp='kubectl get pods -n klinematrix-test'
alias kgpw='kubectl get pods -n klinematrix-test -w'
alias klb='kubectl logs -f deployment/backend -n klinematrix-test'
alias krb='kubectl delete pod -l app=backend -n klinematrix-test'
alias krf='kubectl delete pod -l app=frontend -n klinematrix-test'

# Deployment shortcuts
alias build-backend='BACKEND_VERSION=$(grep "^version = " backend/pyproject.toml | sed "s/version = \"\(.*\)\"/\1/"); az acr build --registry financialAgent --image klinematrix/backend:test-v${BACKEND_VERSION} --file backend/Dockerfile backend/'
alias build-frontend='FRONTEND_VERSION=$(grep "\"version\":" frontend/package.json | sed "s/.*\"version\": \"\(.*\)\".*/\1/"); az acr build --registry financialAgent --image klinematrix/frontend:test-v${FRONTEND_VERSION} --target production --file frontend/Dockerfile frontend/'
alias deploy-test='kubectl apply -k .pipeline/k8s/overlays/test/'

# Health check
alias health='curl -s https://klinematrix.com/api/health | jq .'
```

## Production Deployment (ACK - Alibaba Cloud)

### Overview

**Environment**: Production (`klinematrix-prod` namespace)
**Platform**: Alibaba Cloud Container Service for Kubernetes (ACK)
**Domain**: https://klinecubic.cn
**Cluster**: `klinecubic-financialagent` (Shanghai/华东2)

### Prerequisites

1. **ACK kubeconfig**: `~/.kube/config-ack-prod`
2. **Azure CLI**: For ACR image builds

### Step 1: Build Images in ACR

```bash
# Get current versions
BACKEND_VERSION=$(grep '^version = ' backend/pyproject.toml | sed 's/version = "\(.*\)"/\1/')
FRONTEND_VERSION=$(grep '"version":' frontend/package.json | head -1 | sed 's/.*"\(.*\)".*/\1/')

# Build images with prod prefix
az acr build --registry financialAgent \
  --image klinecubic/backend:prod-v${BACKEND_VERSION} \
  --file backend/Dockerfile backend/

az acr build --registry financialAgent \
  --image klinecubic/frontend:prod-v${FRONTEND_VERSION} \
  --target production --file frontend/Dockerfile frontend/
```

### Step 2: Update Kustomization

Edit `.pipeline/k8s/overlays/prod/kustomization.yaml`:

```yaml
images:
- name: klinematrix/backend
  newName: financialagent-gxftdbbre4gtegea.azurecr.io/klinecubic/backend
  newTag: "prod-v${BACKEND_VERSION}"
- name: klinematrix/frontend
  newName: financialagent-gxftdbbre4gtegea.azurecr.io/klinecubic/frontend
  newTag: "prod-v${FRONTEND_VERSION}"
```

### Step 3: Deploy to ACK

**Important**: Use `--load-restrictor=LoadRestrictionsNone` to handle relative paths in kustomization.

```bash
# Apply kustomization (from project root)
KUBECONFIG=/Users/allenpan/.kube/config-ack-prod kubectl kustomize \
  .pipeline/k8s/overlays/prod --load-restrictor=LoadRestrictionsNone | \
  KUBECONFIG=/Users/allenpan/.kube/config-ack-prod kubectl apply -f -

# Restart deployments to pull new images
KUBECONFIG=~/.kube/config-ack-prod kubectl rollout restart deployment/backend deployment/frontend -n klinematrix-prod

# Wait for rollout
KUBECONFIG=~/.kube/config-ack-prod kubectl rollout status deployment/backend -n klinematrix-prod --timeout=120s
KUBECONFIG=~/.kube/config-ack-prod kubectl rollout status deployment/frontend -n klinematrix-prod --timeout=120s
```

### Step 4: Verify Production Deployment

```bash
# Check pod status
KUBECONFIG=~/.kube/config-ack-prod kubectl get pods -n klinematrix-prod

# Health check (bypass proxy)
HTTP_PROXY="" HTTPS_PROXY="" http_proxy="" https_proxy="" \
  curl -s https://klinecubic.cn/api/health | jq .

# Check logs
KUBECONFIG=~/.kube/config-ack-prod kubectl logs -f deployment/backend -n klinematrix-prod --tail=50
```

### Production Rollback

```bash
# Quick rollback
KUBECONFIG=~/.kube/config-ack-prod kubectl rollout undo deployment/backend -n klinematrix-prod
KUBECONFIG=~/.kube/config-ack-prod kubectl rollout undo deployment/frontend -n klinematrix-prod
```

## Langfuse Observability Stack (Production)

Langfuse is deployed as part of the production kustomization. See [langfuse-observability.md](../features/langfuse-observability.md) for full details.

### Quick Commands

```bash
# Check Langfuse pods
KUBECONFIG=~/.kube/config-ack-prod kubectl get pods -n klinematrix-prod -l component=observability

# View Langfuse server logs
KUBECONFIG=~/.kube/config-ack-prod kubectl logs -f deployment/langfuse-server -n klinematrix-prod

# Test health endpoint
HTTP_PROXY="" HTTPS_PROXY="" curl -s https://monitor.klinecubic.cn/api/public/health
```

### Access

- **UI**: https://monitor.klinecubic.cn
- **API**: Internal `http://langfuse-server:3000` (backend uses this)

## CronJob Management

Production CronJobs for scheduled tasks.

### Current CronJobs

| Name | Schedule (UTC) | Status | Purpose |
|------|----------------|--------|---------|
| `insights-snapshot-trigger` | 14:30 daily | ✅ Enabled | Creates daily Market Insights snapshots |
| `portfolio-analysis-trigger` | 14:30 daily | ❌ Suspended | Portfolio analysis (disabled in prod) |

### Check CronJob Status

```bash
KUBECONFIG=~/.kube/config-ack-prod kubectl get cronjob -n klinematrix-prod -o wide
```

### Suspend/Resume CronJobs

**Runtime (immediate, lost on next deploy):**
```bash
# Suspend
KUBECONFIG=~/.kube/config-ack-prod kubectl patch cronjob <name> \
  -n klinematrix-prod -p '{"spec":{"suspend":true}}'

# Resume
KUBECONFIG=~/.kube/config-ack-prod kubectl patch cronjob <name> \
  -n klinematrix-prod -p '{"spec":{"suspend":false}}'
```

**Permanent (via YAML):**

Edit the overlay patch file:
```yaml
# .pipeline/k8s/overlays/prod/cronjob-<name>-patch.yaml
spec:
  suspend: true  # Add this line
```

Then apply:
```bash
KUBECONFIG=~/.kube/config-ack-prod kubectl apply -k .pipeline/k8s/overlays/prod
```

### Manual Trigger

Trigger a CronJob manually without waiting for schedule:

```bash
# Create a one-off Job from CronJob template
KUBECONFIG=~/.kube/config-ack-prod kubectl create job \
  --from=cronjob/insights-snapshot-trigger \
  manual-insights-$(date +%Y%m%d%H%M) \
  -n klinematrix-prod
```

Or via Admin API (requires auth):
```bash
curl -X POST https://klinecubic.cn/api/admin/insights/trigger-snapshot \
  -H "Authorization: Bearer $TOKEN"
```

### View CronJob History

```bash
# List completed/failed jobs
KUBECONFIG=~/.kube/config-ack-prod kubectl get jobs -n klinematrix-prod

# View logs from last run
KUBECONFIG=~/.kube/config-ack-prod kubectl logs job/<job-name> -n klinematrix-prod
```

---

## Related Documentation

- [Resource Inventory](RESOURCE_INVENTORY.md) - All Azure and K8s resources
- [Migration Guide](MIGRATION_DEV_TO_TEST.md) - How we got to test environment
- [Infrastructure](infrastructure.md) - Architecture overview
- [Langfuse Observability](../features/langfuse-observability.md) - LLM tracing setup
- [Market Insights Trend](../features/market-insights-trend-visualization.md) - Insights snapshot workflow

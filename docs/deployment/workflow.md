# Financial Agent - Deployment Workflow

## Overview

This document describes the complete workflow for deploying code changes to the Financial Agent test environment on Azure Kubernetes Service (AKS).

**Environment**: Test (`klinematrix-test` namespace)
**Domain**: https://klinematrix.com
**Users**: 10 beta testers

## Current Deployment Method: Manual

**Note**: GitHub Actions CI/CD is planned but not yet implemented. All deployments are currently manual.

## Manual Deployment Workflow

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
FRONTEND_VERSION=$(grep '^version = ' frontend/package.json | sed 's/.*"version": "\(.*\)".*/\1/')

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

## Best Practices

1. **Always test locally first** with Docker Compose before building images
2. **Bump version** for every commit (enforced by pre-commit hook)
3. **Use versioned tags** (e.g., `test-v${BACKEND_VERSION}`) for test stability
4. **Deploy during low-traffic periods** when possible (pod restart causes ~5-10s downtime)
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

## Related Documentation

- [Resource Inventory](RESOURCE_INVENTORY.md) - All Azure and K8s resources
- [Migration Guide](MIGRATION_DEV_TO_TEST.md) - How we got to test environment
- [Infrastructure](infrastructure.md) - Architecture overview

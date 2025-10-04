# Financial Agent - Deployment Workflow

## Overview

This document describes the complete workflow for deploying code changes to the Financial Agent application on Azure Kubernetes Service (AKS).

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

#### Option A: Build Both Images Together

```bash
# Build backend
az acr build --registry financialAgent \
  --image financial-agent/backend:dev-latest \
  --file backend/Dockerfile backend/

# Build frontend
az acr build --registry financialAgent \
  --image financial-agent/frontend:dev-latest \
  --target production \
  --file frontend/Dockerfile frontend/
```

#### Option B: Build Only Changed Service

**If you only changed backend code:**
```bash
az acr build --registry financialAgent \
  --image financial-agent/backend:dev-latest \
  --file backend/Dockerfile backend/
```

**If you only changed frontend code:**
```bash
az acr build --registry financialAgent \
  --image financial-agent/frontend:dev-latest \
  --target production \
  --file frontend/Dockerfile frontend/
```

**Build time**: ~2-3 minutes per image

### Step 3: Deploy to Kubernetes

#### Option A: Restart Pods (Fastest - Recommended)

If your Kubernetes manifests haven't changed, just restart the pods to pull new images:

```bash
# Restart backend (if backend image was rebuilt)
kubectl delete pod -l app=backend -n financial-agent-dev

# Restart frontend (if frontend image was rebuilt)
kubectl delete pod -l app=frontend -n financial-agent-dev

# Or use rollout restart
kubectl rollout restart deployment/backend -n financial-agent-dev
kubectl rollout restart deployment/frontend -n financial-agent-dev
```

**Note**: This works because `imagePullPolicy: Always` is set on both deployments.

#### Option B: Apply Full Kustomization (If manifests changed)

If you modified Kubernetes manifests in `.pipeline/k8s/`:

```bash
kubectl apply -k .pipeline/k8s/overlays/dev/
```

### Step 4: Verify Deployment

#### Check Pod Status

```bash
# Watch pods until they're all Running
kubectl get pods -n financial-agent-dev

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
kubectl logs -f deployment/backend -n financial-agent-dev

# Look for:
# - "Starting Financial Agent Backend"
# - "Database connections established"
# - No errors

# Frontend logs (nginx access logs)
kubectl logs deployment/frontend -n financial-agent-dev --tail=20
```

#### Test Application Endpoints

```bash
# 1. Test backend health
curl https://financial-agent-dev.koreacentral.cloudapp.azure.com/api/health

# Expected: JSON with status "ok"

# 2. Test frontend
curl -I https://financial-agent-dev.koreacentral.cloudapp.azure.com/

# Expected: HTTP/2 200

# 3. Test in browser
# Open: https://financial-agent-dev.koreacentral.cloudapp.azure.com/
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

# 2. Build new backend image
az acr build --registry financialAgent \
  --image financial-agent/backend:dev-latest \
  --file backend/Dockerfile backend/

# Wait for build to complete (~2-3 minutes)

# 3. Restart backend pods
kubectl delete pod -l app=backend -n financial-agent-dev

# 4. Verify new pod is running
kubectl get pods -n financial-agent-dev -w
# Press Ctrl+C when backend pod shows 1/1 Running

# 5. Check logs for startup
kubectl logs deployment/backend -n financial-agent-dev --tail=30

# 6. Test the fix
curl https://financial-agent-dev.koreacentral.cloudapp.azure.com/api/market/search?q=test

# 7. Verify in browser
```

## Troubleshooting Deployment Issues

### Issue: Pod stuck in `ImagePullBackOff`

```bash
# Check pod events
kubectl describe pod -l app=backend -n financial-agent-dev

# Common causes:
# 1. Image doesn't exist in ACR
#    Solution: Verify image was pushed
az acr repository show-tags --name financialAgent --repository financial-agent/backend

# 2. ACR not attached to AKS
#    Solution: Re-attach ACR
az aks update --resource-group FinancialAgent --name FinancialAgent-AKS --attach-acr financialAgent
```

### Issue: Pod stuck in `CrashLoopBackOff`

```bash
# Check logs for error
kubectl logs deployment/backend -n financial-agent-dev --previous

# Common causes:
# 1. Database connection failure
kubectl get externalsecret -n financial-agent-dev
kubectl describe externalsecret database-secrets -n financial-agent-dev

# 2. Missing environment variables
kubectl get configmap -n financial-agent-dev
kubectl get secret -n financial-agent-dev
```

### Issue: `502 Bad Gateway` from nginx

```bash
# Backend might not be ready
kubectl get pods -n financial-agent-dev
kubectl logs deployment/backend -n financial-agent-dev

# Test backend directly
kubectl exec -n financial-agent-dev deployment/backend -- curl -s http://localhost:8000/api/health
```

### Issue: Changes not reflected after deployment

```bash
# 1. Verify new image was built
az acr repository show-tags --name financialAgent \
  --repository financial-agent/backend --orderby time_desc --output table

# 2. Verify pod is using new image
kubectl get pod -l app=backend -n financial-agent-dev \
  -o jsonpath='{.items[0].status.containerStatuses[0].imageID}'

# 3. Force complete recreate
kubectl delete pod -l app=backend -n financial-agent-dev
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
kubectl rollout undo deployment/backend -n financial-agent-dev

# Or rollback to specific revision
kubectl rollout history deployment/backend -n financial-agent-dev
kubectl rollout undo deployment/backend -n financial-agent-dev --to-revision=2
```

### Full Rollback (Re-build previous version)

```bash
# 1. Checkout previous git commit
git log --oneline  # Find commit hash
git checkout <previous-commit-hash>

# 2. Rebuild images
az acr build --registry financialAgent \
  --image financial-agent/backend:dev-latest \
  --file backend/Dockerfile backend/

# 3. Restart pods
kubectl delete pod -l app=backend -n financial-agent-dev

# 4. Return to main branch
git checkout main
```

## Best Practices

1. **Always test locally first** before building images
2. **Use descriptive commit messages** for tracking
3. **Deploy during low-traffic periods** when possible (pod restart causes ~5-10s downtime)
4. **Monitor logs after deployment** for 5-10 minutes
5. **Keep images tagged properly** (current: `:dev-latest`, future: semantic versioning)
6. **Document issues** if rollback needed

## Useful Aliases

Add these to your `~/.bashrc` or `~/.zshrc`:

```bash
# Kubernetes shortcuts
alias k='kubectl'
alias kgp='kubectl get pods -n financial-agent-dev'
alias kgpw='kubectl get pods -n financial-agent-dev -w'
alias klb='kubectl logs -f deployment/backend -n financial-agent-dev'
alias krb='kubectl delete pod -l app=backend -n financial-agent-dev'
alias krf='kubectl delete pod -l app=frontend -n financial-agent-dev'

# Deployment shortcuts
alias build-backend='az acr build --registry financialAgent --image financial-agent/backend:dev-latest --file backend/Dockerfile backend/'
alias build-frontend='az acr build --registry financialAgent --image financial-agent/frontend:dev-latest --target production --file frontend/Dockerfile frontend/'
alias deploy-dev='kubectl apply -k .pipeline/k8s/overlays/dev/'

# Health check
alias health='curl -s https://financial-agent-dev.koreacentral.cloudapp.azure.com/api/health | jq .'
```

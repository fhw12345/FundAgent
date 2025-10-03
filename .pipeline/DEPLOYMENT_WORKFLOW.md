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
# {"status":"ok","environment":"development",...}

# 2. Test frontend
curl -I https://financial-agent-dev.koreacentral.cloudapp.azure.com/

# Expected: HTTP/2 200

# 3. Test in browser
# Open: https://financial-agent-dev.koreacentral.cloudapp.azure.com/
# - Page loads without errors
# - Can search for symbols
# - Backend health shows "Connected"
```

#### Verify Image Tags

```bash
# Check which image is running
kubectl describe pod -l app=backend -n financial-agent-dev | grep Image:
kubectl describe pod -l app=frontend -n financial-agent-dev | grep Image:

# Should show:
# Image: financialagent-gxftdbbre4gtegea.azurecr.io/financial-agent/backend:dev-latest
# Image: financialagent-gxftdbbre4gtegea.azurecr.io/financial-agent/frontend:dev-latest
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
# Look for: "Successfully pushed image: ..."

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
# Open app and test the search functionality
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
#    Check: External secrets are synced
kubectl get externalsecret -n financial-agent-dev
kubectl describe externalsecret database-secrets -n financial-agent-dev

# 2. Missing environment variables
#    Check: ConfigMaps and secrets are applied
kubectl get configmap -n financial-agent-dev
kubectl get secret -n financial-agent-dev

# 3. Application code error
#    Check: Build logs and application logs
```

### Issue: `502 Bad Gateway` from nginx

```bash
# Backend might not be ready
kubectl get pods -n financial-agent-dev
kubectl logs deployment/backend -n financial-agent-dev

# Check backend service
kubectl get svc backend-service -n financial-agent-dev

# Test backend directly
kubectl exec -n financial-agent-dev deployment/backend -- curl -s http://localhost:8000/api/health
```

### Issue: `CORS errors` in browser

```bash
# Check backend CORS settings
kubectl exec deployment/backend -n financial-agent-dev -- env | grep CORS

# Should show: CORS_ORIGINS='["*"]'

# Check if frontend is using correct baseURL
kubectl exec deployment/frontend -n financial-agent-dev -- \
  grep -o 'baseURL[^,]*' /usr/share/nginx/html/assets/*.js | head -1

# Should show: baseURL:""  (empty string for relative URLs)

# If showing localhost:8000, frontend needs rebuild
```

### Issue: Changes not reflected after deployment

```bash
# 1. Verify new image was built
az acr repository show-tags --name financialAgent --repository financial-agent/backend --orderby time_desc --output table

# Check timestamp - should be recent

# 2. Verify pod is using new image
kubectl get pod -l app=backend -n financial-agent-dev -o jsonpath='{.items[0].status.containerStatuses[0].imageID}'

# 3. Check if image was pulled recently
kubectl describe pod -l app=backend -n financial-agent-dev | grep -A5 "Events:"

# Look for recent "Pulled" event

# 4. Force complete recreate
kubectl delete pod -l app=backend -n financial-agent-dev
kubectl get pods -n financial-agent-dev -w
```

## Future: GitHub Actions CI/CD Workflow

### Planned Workflow (.pipeline/workflows/dev-deploy.yml)

```yaml
name: Deploy to Dev

on:
  push:
    branches: [ main ]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      # Backend tests
      - name: Run backend tests
        run: |
          cd backend
          python -m pytest tests/

      # Frontend tests
      - name: Run frontend tests
        run: |
          cd frontend
          npm ci
          npm run test

  build-and-deploy:
    needs: test
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Login to Azure
        uses: azure/login@v1
        with:
          creds: ${{ secrets.AZURE_CREDENTIALS }}

      - name: Build and push backend
        run: |
          az acr build --registry financialAgent \
            --image financial-agent/backend:dev-latest \
            --file backend/Dockerfile backend/

      - name: Build and push frontend
        run: |
          az acr build --registry financialAgent \
            --image financial-agent/frontend:dev-latest \
            --target production \
            --file frontend/Dockerfile frontend/

      - name: Get AKS credentials
        run: |
          az aks get-credentials \
            --resource-group FinancialAgent \
            --name FinancialAgent-AKS

      - name: Deploy to Kubernetes
        run: |
          kubectl rollout restart deployment/backend -n financial-agent-dev
          kubectl rollout restart deployment/frontend -n financial-agent-dev
          kubectl rollout status deployment/backend -n financial-agent-dev --timeout=5m
          kubectl rollout status deployment/frontend -n financial-agent-dev --timeout=5m

      - name: Verify deployment
        run: |
          kubectl get pods -n financial-agent-dev
          curl -f https://financial-agent-dev.koreacentral.cloudapp.azure.com/api/health
```

### Required GitHub Secrets for CI/CD

When implementing GitHub Actions, create these secrets in GitHub repo settings:

```bash
# 1. Create Azure Service Principal
az ad sp create-for-rbac \
  --name "financial-agent-github" \
  --role contributor \
  --scopes /subscriptions/<subscription-id>/resourceGroups/FinancialAgent \
  --sdk-auth

# Copy the output JSON

# 2. Add to GitHub Secrets
# Repository Settings → Secrets and variables → Actions → New secret
# Name: AZURE_CREDENTIALS
# Value: <paste JSON from step 1>
```

## Deployment Checklist

Use this checklist for each deployment:

### Pre-Deployment
- [ ] Code changes committed and pushed to git
- [ ] Local tests passing (`make test` for backend, `npm test` for frontend)
- [ ] No sensitive data in code (API keys, passwords, etc.)

### Build Phase
- [ ] Backend image built successfully (if backend changed)
- [ ] Frontend image built successfully (if frontend changed)
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
- [ ] Database and Redis connections working (check backend health JSON)

### Post-Deployment
- [ ] Monitor logs for 5-10 minutes for any errors
- [ ] Test critical user flows
- [ ] Document any issues in git commit or issue tracker

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

## Performance Optimization

### Build Time Optimization

Docker layers are cached by ACR. To maximize cache hits:

1. **Don't change dependency files** unless necessary
   - Backend: `pyproject.toml`
   - Frontend: `package.json`

2. **Build during low-traffic times** if possible
   - Builds take 2-3 minutes and don't affect running services

### Deployment Time Optimization

1. **Use `kubectl delete pod`** instead of `kubectl apply -k`
   - Faster when only image changed
   - ~30 seconds vs ~60 seconds

2. **Only rebuild changed service**
   - Backend-only changes: Skip frontend rebuild
   - Frontend-only changes: Skip backend rebuild

3. **Monitor pod status actively**
   ```bash
   kubectl get pods -n financial-agent-dev -w
   ```
   - Ctrl+C as soon as pods are Running
   - No need to wait for full stabilization

## Monitoring Deployment Health

### Real-time Monitoring During Deployment

```bash
# Terminal 1: Watch pods
kubectl get pods -n financial-agent-dev -w

# Terminal 2: Follow backend logs
kubectl logs -f deployment/backend -n financial-agent-dev

# Terminal 3: Test endpoint repeatedly
watch -n 2 'curl -s https://financial-agent-dev.koreacentral.cloudapp.azure.com/api/health | jq .status'
```

### Post-Deployment Monitoring

```bash
# Check resource usage
kubectl top pods -n financial-agent-dev

# Check for pod restarts (should be 0)
kubectl get pods -n financial-agent-dev

# View recent events
kubectl get events -n financial-agent-dev --sort-by='.lastTimestamp' | tail -20
```

## Best Practices

1. **Always test locally first** before building images
   - Backend: `cd backend && uvicorn src.main:app --reload`
   - Frontend: `cd frontend && npm run dev`

2. **Use descriptive commit messages**
   - Helps track which deployment caused issues
   - Examples: `fix: Handle null values in search`, `feat: Add new chart indicator`

3. **Deploy during low-traffic periods** when possible
   - Pod restart causes ~5-10 seconds of downtime
   - Frontend/backend restart independently

4. **Monitor logs after deployment**
   - Watch for 5-10 minutes
   - Look for error patterns

5. **Keep images tagged properly**
   - Current: using `:dev-latest` tag
   - Future: Consider semantic versioning (`:v1.2.3`)

6. **Document issues**
   - If rollback needed, document why
   - Create GitHub issues for tracking

## Common Deployment Patterns

### Pattern 1: Hotfix

```bash
# Quick fix for production issue
git checkout -b hotfix/search-error
# Make minimal changes
git commit -m "hotfix: Fix search null pointer"
git push origin hotfix/search-error
# Create PR, get approval
git checkout main
git merge hotfix/search-error

# Deploy immediately
az acr build --registry financialAgent --image financial-agent/backend:dev-latest --file backend/Dockerfile backend/
kubectl delete pod -l app=backend -n financial-agent-dev
# Monitor closely
```

### Pattern 2: Feature Deployment

```bash
# Complete feature branch
git checkout -b feature/new-indicator
# Develop and test
git commit -m "feat: Add RSI indicator"
git push origin feature/new-indicator
# Create PR, run tests, get approval
git checkout main
git merge feature/new-indicator

# Deploy during low-traffic time
az acr build --registry financialAgent --image financial-agent/backend:dev-latest --file backend/Dockerfile backend/
kubectl delete pod -l app=backend -n financial-agent-dev
# Verify thoroughly
```

### Pattern 3: Database Migration

```bash
# If changes include database schema changes
# 1. Deploy backend with migration code (backward compatible)
az acr build --registry financialAgent --image financial-agent/backend:dev-latest --file backend/Dockerfile backend/
kubectl delete pod -l app=backend -n financial-agent-dev

# 2. Run migration (if needed)
kubectl exec -it deployment/backend -n financial-agent-dev -- python -m alembic upgrade head

# 3. Verify migration succeeded
kubectl logs deployment/backend -n financial-agent-dev | grep migration

# 4. Deploy any frontend changes
az acr build --registry financialAgent --image financial-agent/frontend:dev-latest --target production --file frontend/Dockerfile frontend/
kubectl delete pod -l app=frontend -n financial-agent-dev
```

## Emergency Procedures

### Complete Service Restart

```bash
# Restart everything (Redis + Backend + Frontend)
kubectl delete pod --all -n financial-agent-dev

# Watch recovery
kubectl get pods -n financial-agent-dev -w
```

### Ingress Issues

```bash
# Restart nginx ingress
kubectl rollout restart deployment/nginx-ingress-ingress-nginx-controller -n ingress-nginx

# Check ingress status
kubectl get ingress -n financial-agent-dev
kubectl describe ingress financial-agent-ingress -n financial-agent-dev
```

### Certificate Issues

```bash
# Check certificate
kubectl get certificate -n financial-agent-dev
kubectl describe certificate financial-agent-tls -n financial-agent-dev

# Force renewal
kubectl delete certificate financial-agent-tls -n financial-agent-dev
kubectl delete secret financial-agent-tls -n financial-agent-dev
kubectl apply -k .pipeline/k8s/overlays/dev/
```

## Useful Aliases

Add these to your `~/.bashrc` or `~/.zshrc`:

```bash
# Kubernetes shortcuts
alias k='kubectl'
alias kgp='kubectl get pods -n financial-agent-dev'
alias kgpw='kubectl get pods -n financial-agent-dev -w'
alias klb='kubectl logs -f deployment/backend -n financial-agent-dev'
alias klf='kubectl logs -f deployment/frontend -n financial-agent-dev'
alias krb='kubectl delete pod -l app=backend -n financial-agent-dev'
alias krf='kubectl delete pod -l app=frontend -n financial-agent-dev'

# Deployment shortcuts
alias build-backend='az acr build --registry financialAgent --image financial-agent/backend:dev-latest --file backend/Dockerfile backend/'
alias build-frontend='az acr build --registry financialAgent --image financial-agent/frontend:dev-latest --target production --file frontend/Dockerfile frontend/'
alias deploy-dev='kubectl apply -k .pipeline/k8s/overlays/dev/'

# Health check
alias health='curl -s https://financial-agent-dev.koreacentral.cloudapp.azure.com/api/health | jq .'
```

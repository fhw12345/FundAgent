# Deployment Issues

## Issue: Pod Stuck in ImagePullBackOff

### Symptoms
```bash
kubectl get pods -n klinematrix-test
# NAME                      READY   STATUS             RESTARTS   AGE
# backend-xxx-yyy           0/1     ImagePullBackOff   0          2m
```

### Root Cause
- Image doesn't exist in ACR
- ACR not attached to AKS
- Image tag incorrect
- Network issues pulling from ACR

### Diagnosis
```bash
# Check pod events
kubectl describe pod -l app=backend -n klinematrix-test | grep -A 10 Events

# Verify image exists in ACR
az acr repository show-tags \
  --name financialAgent \
  --repository financial-agent/backend \
  --output table

# Check if ACR is attached to AKS
az aks show --resource-group FinancialAgent --name FinancialAgent-AKS \
  --query "servicePrincipalProfile" -o table
```

### Solution

**If image doesn't exist:**
```bash
# Build and push image
az acr build --registry financialAgent \
  --image financial-agent/backend:dev-latest \
  --file backend/Dockerfile backend/
```

**If ACR not attached:**
```bash
# Attach ACR to AKS
az aks update \
  --resource-group FinancialAgent \
  --name FinancialAgent-AKS \
  --attach-acr financialAgent

# Restart pod after attaching
kubectl delete pod -l app=backend -n klinematrix-test
```

**If image tag wrong:**
```bash
# Check deployment image reference
kubectl get deployment backend -n klinematrix-test -o jsonpath='{.spec.template.spec.containers[0].image}'

# Should match: financialagent-gxftdbbre4gtegea.azurecr.io/financial-agent/backend:dev-latest
```

### Prevention
- Always verify image exists before deploying
- Keep ACR attached to AKS
- Use consistent image tags
- Set `imagePullPolicy: Always` for latest tags

---

## Issue: Pod Stuck in CrashLoopBackOff

### Symptoms
```bash
kubectl get pods -n klinematrix-test
# NAME                      READY   STATUS             RESTARTS   AGE
# backend-xxx-yyy           0/1     CrashLoopBackOff   5          5m
```

### Root Cause
Application crashes on startup due to:
- Database connection failure
- Missing environment variables
- Python/dependency errors
- Invalid configuration

### Diagnosis
```bash
# Check current logs
kubectl logs deployment/backend -n klinematrix-test --tail=50

# Check previous container logs (after crash)
kubectl logs deployment/backend -n klinematrix-test --previous

# Check environment variables
kubectl exec deployment/backend -n klinematrix-test -- env | grep -E "MONGO|REDIS|ENVIRONMENT"
```

### Solution

**Database connection issues:**
```bash
# Check External Secrets are synced
kubectl get externalsecret -n klinematrix-test
kubectl describe externalsecret database-secrets -n klinematrix-test

# If not synced, check SecretStore
kubectl describe secretstore azure-keyvault-store -n klinematrix-test

# Force refresh External Secret
kubectl delete externalsecret database-secrets -n klinematrix-test
kubectl apply -k .pipeline/k8s/overlays/dev/
```

**Missing environment variables:**
```bash
# Check deployment env vars
kubectl get deployment backend -n klinematrix-test -o yaml | grep -A 20 "env:"

# Add missing vars to overlay
vim .pipeline/k8s/overlays/dev/backend-dev-patch.yaml

# Apply changes
kubectl apply -k .pipeline/k8s/overlays/dev/
```

**Application errors:**
```bash
# Get detailed error
kubectl logs deployment/backend -n klinematrix-test --previous | tail -30

# Common Python errors:
# - ImportError: Module not found -> rebuild with dependencies
# - ValidationError: Config issue -> check env vars
# - ConnectionError: External service down -> check secrets/network
```

### Prevention
- Test configuration locally first
- Validate all environment variables before deployment
- Add health checks with proper initialDelaySeconds
- Monitor logs immediately after deployment

---

## Issue: Frontend Running Development Mode Instead of Production

### Symptoms
- Logs show `vite` dev server instead of nginx
- Port 3000 instead of port 80

### Solution
Rebuild with explicit production target:
```bash
az acr build --registry financialAgent \
  --image financial-agent/frontend:dev-latest \
  --target production \
  --file frontend/Dockerfile frontend/

kubectl delete pod -l app=frontend -n klinematrix-test
```

**Prevention**: Always use `--target production` in ACR build commands.

---

## Issue: Pod OOMKilled (Out of Memory)

### Symptoms
```bash
kubectl get pods -n klinematrix-test
# STATUS: OOMKilled or CrashLoopBackOff

kubectl describe pod frontend-xxx -n klinematrix-test
# Reason: OOMKilled
```

### Root Cause
Container uses more memory than the defined limit.

### Diagnosis
```bash
# Check memory limits
kubectl get pod -l app=frontend -n klinematrix-test -o jsonpath='{.items[0].spec.containers[0].resources}'

# Check actual memory usage
kubectl top pod -l app=frontend -n klinematrix-test

# Check logs before OOMKill
kubectl logs deployment/frontend -n klinematrix-test --previous
```

### Solution

**Increase memory limits:**
```yaml
# .pipeline/k8s/base/frontend/deployment.yaml
resources:
  requests:
    memory: "128Mi"
    cpu: "50m"
  limits:
    memory: "256Mi"  # Increase this
    cpu: "200m"
```

**Or optimize application:**
```bash
# If frontend is running dev mode (vite), switch to production (nginx)
# Production nginx uses much less memory than dev server

az acr build --registry financialAgent \
  --image financial-agent/frontend:dev-latest \
  --target production \
  --file frontend/Dockerfile frontend/
```

**Apply and restart:**
```bash
kubectl apply -k .pipeline/k8s/overlays/dev/
kubectl delete pod -l app=frontend -n klinematrix-test
```

### Prevention
- Use production builds (nginx) not dev servers (vite)
- Set appropriate memory limits based on actual usage
- Monitor memory usage with `kubectl top`
- Optimize bundle sizes for frontend

---

## Issue: Health Check Failing (Readiness/Liveness Probe)

### Symptoms
```bash
kubectl describe pod backend-xxx -n klinematrix-test
# Warning  Unhealthy  10s (x3 over 20s)  kubelet  Readiness probe failed: HTTP probe failed
```

### Root Cause
- Health endpoint returns non-200 status
- Health endpoint not ready on time
- Wrong health check path/port

### Diagnosis
```bash
# Test health endpoint directly
kubectl exec deployment/backend -n klinematrix-test -- \
  curl -v http://localhost:8000/api/health

# Check probe configuration
kubectl get deployment backend -n klinematrix-test -o yaml | grep -A 10 "livenessProbe"

# Check backend logs during probe
kubectl logs -f deployment/backend -n klinematrix-test
```

### Solution

**If health endpoint returns 400/500:**
```bash
# Check backend logs for error
kubectl logs deployment/backend -n klinematrix-test | grep "api/health"

# Temporarily disable probes for debugging
kubectl edit deployment backend -n klinematrix-test
# Comment out livenessProbe and readinessProbe sections

# Fix health endpoint code
# Redeploy with working health check
```

**If probe timing is wrong:**
```yaml
# Increase initialDelaySeconds
livenessProbe:
  httpGet:
    path: /api/health
    port: 8000
  initialDelaySeconds: 30  # Give app more time to start
  periodSeconds: 10
  failureThreshold: 3

readinessProbe:
  httpGet:
    path: /api/health
    port: 8000
  initialDelaySeconds: 10
  periodSeconds: 5
  failureThreshold: 3
```

**If path/port is wrong:**
```yaml
# Correct the probe configuration
livenessProbe:
  httpGet:
    path: /api/health  # Must match your endpoint
    port: 8000         # Must match container port
```

### Prevention
- Test health endpoints locally first
- Use appropriate initialDelaySeconds based on startup time
- Implement separate /health/live and /health/ready endpoints
- Log health check requests for debugging

---

## Issue: Old Image Cached (Changes Not Reflected)

**Quick fix**: Run `kubectl rollout restart deployment/backend -n klinematrix-test`

**Prevention**: Set `imagePullPolicy: Always` in deployment.yaml or use unique image tags.

---

## Issue: Ingress Not Working (404 on Domain)

### Symptoms
```bash
curl https://klinematrix-test.koreacentral.cloudapp.azure.com
# 404 Not Found or Connection refused
```

### Root Cause
- Ingress not created
- TLS certificate not ready
- Ingress controller not installed
- DNS not configured

### Diagnosis
```bash
# Check ingress exists
kubectl get ingress -n klinematrix-test

# Check ingress details
kubectl describe ingress financial-agent-ingress -n klinematrix-test

# Check certificate status
kubectl get certificate -n klinematrix-test

# Check nginx ingress controller
kubectl get pods -n ingress-nginx
```

### Solution

**If ingress controller missing:**
```bash
# Install nginx ingress
helm install nginx-ingress ingress-nginx/ingress-nginx \
  --namespace ingress-nginx --create-namespace
```

**If certificate not ready:**
```bash
# Check cert-manager
kubectl get pods -n cert-manager

# Check certificate order
kubectl describe certificate financial-agent-tls -n klinematrix-test

# If failed, delete and recreate
kubectl delete certificate financial-agent-tls -n klinematrix-test
kubectl delete secret financial-agent-tls -n klinematrix-test
kubectl apply -k .pipeline/k8s/overlays/dev/
```

**If DNS not configured:**
```bash
# Get LoadBalancer IP
kubectl get svc -n ingress-nginx

# Update DNS
az network public-ip update \
  --resource-group MC_FinancialAgent_FinancialAgent-AKS_koreacentral \
  --name <public-ip-name> \
  --dns-name klinematrix-test
```

### Prevention
- Install ingress controller before creating ingress
- Verify DNS resolves before requesting certificate
- Use staging Let's Encrypt for testing
- Check ingress events after creation

---

## Issue: ExternalSecret Not Syncing (Workload Identity)

### Symptoms
```bash
kubectl get externalsecret -n klinematrix-test
# STATUS: SecretSyncedError, READY: False

kubectl describe secretstore azure-keyvault-store -n klinematrix-test
# Error: Tenant '${azure_tenant_id}' not found
```

### Root Cause
- Workload identity service account has placeholder variables instead of actual values
- Federated credential not created linking managed identity to service account
- Managed identity not granted Key Vault access

### Diagnosis
```bash
# Check service account annotations
kubectl get serviceaccount klinematrix-sa -n klinematrix-test -o yaml
# Should have actual client-id and tenant-id, not ${AZURE_CLIENT_ID}

# Check ExternalSecret status
kubectl describe externalsecret app-secrets -n klinematrix-test

# Check SecretStore status
kubectl describe secretstore azure-keyvault-store -n klinematrix-test
```

### Solution

**Temporary workaround - Manual secret update:**
```bash
# Update secret directly (doesn't require ExternalSecrets)
kubectl create secret generic app-secrets -n klinematrix-test \
  --from-literal=key=value \
  --dry-run=client -o yaml | kubectl apply -f -
```

**Proper fix - Configure workload identity:**
```bash
# 1. Create managed identity
az identity create --name klinematrix-external-secrets \
  --resource-group FinancialAgent --location koreacentral

# 2. Grant Key Vault access (RBAC-enabled vault)
PRINCIPAL_ID=$(az identity show --name klinematrix-external-secrets \
  --resource-group FinancialAgent --query principalId -o tsv)

az role assignment create \
  --role "Key Vault Secrets User" \
  --assignee $PRINCIPAL_ID \
  --scope /subscriptions/.../vaults/klinematrix-test-kv

# 3. Create federated credential
CLIENT_ID=$(az identity show --name klinematrix-external-secrets \
  --resource-group FinancialAgent --query clientId -o tsv)

OIDC_ISSUER=$(az aks show --name FinancialAgent-AKS \
  --resource-group FinancialAgent --query oidcIssuerProfile.issuerUrl -o tsv)

az identity federated-credential create \
  --name klinematrix-test-federated-credential \
  --identity-name klinematrix-external-secrets \
  --resource-group FinancialAgent \
  --issuer "$OIDC_ISSUER" \
  --subject "system:serviceaccount:klinematrix-test:klinematrix-sa" \
  --audience api://AzureADTokenExchange

# 4. Update service account
TENANT_ID=$(az account show --query tenantId -o tsv)

kubectl patch serviceaccount klinematrix-sa -n klinematrix-test \
  --type merge \
  -p "{\"metadata\":{\"annotations\":{\"azure.workload.identity/client-id\":\"$CLIENT_ID\",\"azure.workload.identity/tenant-id\":\"$TENANT_ID\"}}}"
```

### Prevention
- Don't commit placeholder variables in base manifests
- Use kustomize configMapGenerator for environment-specific values
- Test ExternalSecrets sync after setup
- Document workload identity configuration in deployment guide

---

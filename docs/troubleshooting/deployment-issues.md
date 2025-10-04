# Deployment Issues

## Issue: Pod Stuck in ImagePullBackOff

### Symptoms
```bash
kubectl get pods -n financial-agent-dev
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
kubectl describe pod -l app=backend -n financial-agent-dev | grep -A 10 Events

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
kubectl delete pod -l app=backend -n financial-agent-dev
```

**If image tag wrong:**
```bash
# Check deployment image reference
kubectl get deployment backend -n financial-agent-dev -o jsonpath='{.spec.template.spec.containers[0].image}'

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
kubectl get pods -n financial-agent-dev
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
kubectl logs deployment/backend -n financial-agent-dev --tail=50

# Check previous container logs (after crash)
kubectl logs deployment/backend -n financial-agent-dev --previous

# Check environment variables
kubectl exec deployment/backend -n financial-agent-dev -- env | grep -E "MONGO|REDIS|ENVIRONMENT"
```

### Solution

**Database connection issues:**
```bash
# Check External Secrets are synced
kubectl get externalsecret -n financial-agent-dev
kubectl describe externalsecret database-secrets -n financial-agent-dev

# If not synced, check SecretStore
kubectl describe secretstore azure-keyvault-store -n financial-agent-dev

# Force refresh External Secret
kubectl delete externalsecret database-secrets -n financial-agent-dev
kubectl apply -k .pipeline/k8s/overlays/dev/
```

**Missing environment variables:**
```bash
# Check deployment env vars
kubectl get deployment backend -n financial-agent-dev -o yaml | grep -A 20 "env:"

# Add missing vars to overlay
vim .pipeline/k8s/overlays/dev/backend-dev-patch.yaml

# Apply changes
kubectl apply -k .pipeline/k8s/overlays/dev/
```

**Application errors:**
```bash
# Get detailed error
kubectl logs deployment/backend -n financial-agent-dev --previous | tail -30

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
- Pod keeps restarting or OOMKilled
- Logs show `vite` dev server instead of nginx
- Port 3000 instead of port 80

### Root Cause
Docker build not targeting production stage or using wrong base image.

### Diagnosis
```bash
# Check pod logs
kubectl logs deployment/frontend -n financial-agent-dev | head -10

# If shows "vite" -> using dev mode
# Should show nginx logs: "GET / HTTP/1.1" 200

# Check which image stage is running
kubectl describe pod -l app=frontend -n financial-agent-dev | grep -A 3 "Image:"
```

### Solution

**Rebuild with explicit production target:**
```bash
az acr build --registry financialAgent \
  --image financial-agent/frontend:dev-latest \
  --target production \
  --file frontend/Dockerfile frontend/

kubectl delete pod -l app=frontend -n financial-agent-dev
```

**Verify Dockerfile has production stage:**
```dockerfile
# Production stage with nginx
FROM nginx:alpine as production

COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
```

### Prevention
- Always use `--target production` in ACR build
- Add build verification step
- Use multi-stage Dockerfiles with clear stage names
- Default to production stage in Dockerfile (make it last)

---

## Issue: Pod OOMKilled (Out of Memory)

### Symptoms
```bash
kubectl get pods -n financial-agent-dev
# STATUS: OOMKilled or CrashLoopBackOff

kubectl describe pod frontend-xxx -n financial-agent-dev
# Reason: OOMKilled
```

### Root Cause
Container uses more memory than the defined limit.

### Diagnosis
```bash
# Check memory limits
kubectl get pod -l app=frontend -n financial-agent-dev -o jsonpath='{.items[0].spec.containers[0].resources}'

# Check actual memory usage
kubectl top pod -l app=frontend -n financial-agent-dev

# Check logs before OOMKill
kubectl logs deployment/frontend -n financial-agent-dev --previous
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
kubectl delete pod -l app=frontend -n financial-agent-dev
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
kubectl describe pod backend-xxx -n financial-agent-dev
# Warning  Unhealthy  10s (x3 over 20s)  kubelet  Readiness probe failed: HTTP probe failed
```

### Root Cause
- Health endpoint returns non-200 status
- Health endpoint not ready on time
- Wrong health check path/port

### Diagnosis
```bash
# Test health endpoint directly
kubectl exec deployment/backend -n financial-agent-dev -- \
  curl -v http://localhost:8000/api/health

# Check probe configuration
kubectl get deployment backend -n financial-agent-dev -o yaml | grep -A 10 "livenessProbe"

# Check backend logs during probe
kubectl logs -f deployment/backend -n financial-agent-dev
```

### Solution

**If health endpoint returns 400/500:**
```bash
# Check backend logs for error
kubectl logs deployment/backend -n financial-agent-dev | grep "api/health"

# Temporarily disable probes for debugging
kubectl edit deployment backend -n financial-agent-dev
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

### Symptoms
- Deployed new image but old code still running
- Pod shows "Running" but behavior unchanged

### Root Cause
Kubernetes cached the image because tag hasn't changed and `imagePullPolicy` not set to `Always`.

### Diagnosis
```bash
# Check when image was pulled
kubectl describe pod -l app=backend -n financial-agent-dev | grep -E "Image:|Pulled:"

# Check imagePullPolicy
kubectl get deployment backend -n financial-agent-dev -o jsonpath='{.spec.template.spec.containers[0].imagePullPolicy}'
```

### Solution

**Set imagePullPolicy to Always:**
```yaml
# .pipeline/k8s/base/backend/deployment.yaml
containers:
- name: backend
  image: financial-agent/backend:dev
  imagePullPolicy: Always  # Add this
```

**Force pull new image:**
```bash
# Delete pod to force fresh pull
kubectl delete pod -l app=backend -n financial-agent-dev

# Or use rollout restart
kubectl rollout restart deployment/backend -n financial-agent-dev
```

**Alternative: Use unique tags:**
```bash
# Build with commit SHA tag
COMMIT_SHA=$(git rev-parse --short HEAD)
az acr build --registry financialAgent \
  --image financial-agent/backend:${COMMIT_SHA} \
  --file backend/Dockerfile backend/

# Update deployment to use new tag
kubectl set image deployment/backend \
  backend=financialagent-gxftdbbre4gtegea.azurecr.io/financial-agent/backend:${COMMIT_SHA} \
  -n financial-agent-dev
```

### Prevention
- Always set `imagePullPolicy: Always` for development
- Use unique tags (commit SHA) for production
- Verify image digest after deployment
- Check pod creation time to confirm new pod

---

## Issue: Ingress Not Working (404 on Domain)

### Symptoms
```bash
curl https://financial-agent-dev.koreacentral.cloudapp.azure.com
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
kubectl get ingress -n financial-agent-dev

# Check ingress details
kubectl describe ingress financial-agent-ingress -n financial-agent-dev

# Check certificate status
kubectl get certificate -n financial-agent-dev

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
kubectl describe certificate financial-agent-tls -n financial-agent-dev

# If failed, delete and recreate
kubectl delete certificate financial-agent-tls -n financial-agent-dev
kubectl delete secret financial-agent-tls -n financial-agent-dev
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
  --dns-name financial-agent-dev
```

### Prevention
- Install ingress controller before creating ingress
- Verify DNS resolves before requesting certificate
- Use staging Let's Encrypt for testing
- Check ingress events after creation

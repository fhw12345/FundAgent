# CORS & API Connectivity Issues

## Issue: Frontend Cannot Connect to Backend (localhost:8000)

### Symptoms
```
Access to XMLHttpRequest at 'http://localhost:8000/api/health' from origin
'https://financial-agent-dev.koreacentral.cloudapp.azure.com' has been blocked
by CORS policy: No 'Access-Control-Allow-Origin' header is present on the
requested resource.
```

### Root Cause
Frontend built with hardcoded `baseURL: 'http://localhost:8000'` instead of using relative URLs for nginx proxy.

### Diagnosis
```bash
# Check frontend JavaScript for localhost references
kubectl exec -n financial-agent-dev deployment/frontend -- \
  grep -o 'baseURL[^,]*localhost[^,]*' /usr/share/nginx/html/assets/*.js
```

### Solution

**Option 1: Use relative URLs (Recommended)**
```typescript
// frontend/src/services/api.ts
const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL !== undefined
    ? import.meta.env.VITE_API_URL
    : (import.meta.env.MODE === 'production' ? '' : 'http://localhost:8000'),
  timeout: 30000,
  headers: { 'Content-Type': 'application/json' },
})
```

**Option 2: Set VITE_API_URL at build time**
```dockerfile
# frontend/Dockerfile
ARG VITE_API_URL=""
ENV VITE_API_URL=${VITE_API_URL}
RUN npx vite build
```

**Rebuild and deploy:**
```bash
az acr build --registry financialAgent \
  --image financial-agent/frontend:dev-latest \
  --target production \
  --file frontend/Dockerfile frontend/

kubectl delete pod -l app=frontend -n financial-agent-dev
```

### Prevention
- Always use environment variables for API URLs
- In production mode, default to relative URLs (`''`)
- Verify built assets don't contain `localhost` references

---

## Issue: Backend Returns "Invalid host header"

### Symptoms
```bash
curl https://financial-agent-dev.koreacentral.cloudapp.azure.com/api/health
# Returns: Invalid host header
```

### Root Cause
FastAPI's `TrustedHostMiddleware` rejects requests from the domain because it's not in `allowed_hosts` list.

### Diagnosis
```bash
# Check backend logs
kubectl logs deployment/backend -n financial-agent-dev | grep -i "host"

# Check TrustedHostMiddleware configuration
kubectl exec deployment/backend -n financial-agent-dev -- \
  python -c "from src.core.config import get_settings; print(get_settings().allowed_hosts)"
```

### Solution

**For Development: Disable TrustedHostMiddleware**
```python
# backend/src/main.py
def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(...)

    # Security middleware - only in production
    if settings.environment == "production":
        app.add_middleware(
            TrustedHostMiddleware,
            allowed_hosts=settings.allowed_hosts,
        )
```

**For Production: Add domain to allowed_hosts**
```python
# backend/src/core/config.py
allowed_hosts: list[str] = [
    "localhost",
    "127.0.0.1",
    "financial-agent-dev.koreacentral.cloudapp.azure.com",
    "*.cloudapp.azure.com",  # Wildcard for Azure domains
]
```

**Deploy fix:**
```bash
az acr build --registry financialAgent \
  --image financial-agent/backend:dev-latest \
  --file backend/Dockerfile backend/

kubectl delete pod -l app=backend -n financial-agent-dev
```

### Prevention
- Disable TrustedHostMiddleware in dev environment
- Use wildcard domains for cloud deployments
- Add domain to allowed_hosts before deploying to new environments

---

## Issue: 502 Bad Gateway from Nginx

### Symptoms
```
HTTP/1.1 502 Bad Gateway
```

### Root Cause
Backend pod is not ready or backend service is not routing correctly.

### Diagnosis
```bash
# Check backend pod status
kubectl get pods -n financial-agent-dev

# Check backend service
kubectl get svc backend-service -n financial-agent-dev

# Test backend directly from within cluster
kubectl exec -n financial-agent-dev deployment/frontend -- \
  curl -v http://backend-service:8000/api/health
```

### Solution

**If backend pod is not ready:**
```bash
# Check logs
kubectl logs deployment/backend -n financial-agent-dev --tail=50

# Common issues:
# 1. Database connection failed - check External Secrets
kubectl describe externalsecret database-secrets -n financial-agent-dev

# 2. Application crash - check logs for stack trace
kubectl logs deployment/backend -n financial-agent-dev --previous
```

**If backend service misconfigured:**
```bash
# Verify service endpoints
kubectl get endpoints backend-service -n financial-agent-dev

# Should show backend pod IP:8000
# If empty, check service selector matches pod labels
kubectl get pod -n financial-agent-dev --show-labels
kubectl describe svc backend-service -n financial-agent-dev
```

### Prevention
- Always check backend health before frontend deployment
- Enable health checks (liveness/readiness probes)
- Monitor backend logs during deployment

---

## Issue: CORS Preflight OPTIONS Request Fails

### Symptoms
```
Failed to load resource: the server responded with a status of 403 (Forbidden)
Request Method: OPTIONS
```

### Root Cause
Backend CORS middleware not configured to allow the origin.

### Diagnosis
```bash
# Check CORS configuration
kubectl exec deployment/backend -n financial-agent-dev -- \
  python -c "from src.core.config import get_settings; print(get_settings().cors_origins)"
```

### Solution

**Update CORS origins:**
```python
# backend/src/core/config.py
cors_origins: list[str] = [
    "http://localhost:3000",
    "https://financial-agent-dev.koreacentral.cloudapp.azure.com",
    "*",  # Allow all in dev (NOT for production)
]
```

**Via environment variable (preferred for dev):**
```yaml
# .pipeline/k8s/overlays/dev/backend-dev-patch.yaml
env:
- name: CORS_ORIGINS
  value: '["*"]'  # JSON array format
```

**Deploy:**
```bash
kubectl apply -k .pipeline/k8s/overlays/dev/
kubectl rollout restart deployment/backend -n financial-agent-dev
```

### Prevention
- Use `["*"]` for dev environment
- Restrict to specific domains in production
- Always use JSON array format for CORS_ORIGINS env var

---

## Issue: Nginx Proxy Not Working

### Symptoms
Frontend loads but API calls to `/api/*` fail with 404.

### Root Cause
Nginx configuration missing or incorrect proxy rules.

### Diagnosis
```bash
# Check nginx config
kubectl exec deployment/frontend -n financial-agent-dev -- \
  cat /etc/nginx/conf.d/default.conf | grep -A 10 "location /api"
```

### Solution

**Verify nginx.conf has proxy:**
```nginx
# frontend/nginx.conf
location /api/ {
    proxy_pass http://backend-service:8000/api/;
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
}
```

**Rebuild frontend with updated config:**
```bash
az acr build --registry financialAgent \
  --image financial-agent/frontend:dev-latest \
  --target production \
  --file frontend/Dockerfile frontend/

kubectl delete pod -l app=frontend -n financial-agent-dev
```

### Prevention
- Always include nginx.conf in frontend Docker image
- Test nginx config locally before deploying
- Verify proxy_pass URL matches backend service name and port

# Fixed Bugs

## Tencent Cloud SES Authentication Failure - Fixed 2025-10-07

**Problem**: Email verification failing in test environment with `AuthFailure.SignatureFailure` but working locally

**Root Cause**: Different Tencent Cloud credentials between environments:
- Local: `AKID*****` (configured with domain/sender/template)
- Test: `AKID*****` (unconfigured account)

**Solution**: Updated Kubernetes secret directly with working credentials
```bash
# Check current credentials
kubectl get secret app-secrets -n klinematrix-test -o jsonpath='{.data.tencent-secret-id}' | base64 -d

# Update with working credentials from local environment
kubectl delete secret app-secrets -n klinematrix-test
kubectl create secret generic app-secrets -n klinematrix-test \
  --from-literal=tencent-secret-id='<working-secret-id>' \
  --from-literal=tencent-secret-key='<working-secret-key>' \
  # ... other secrets

# Restart backend
kubectl rollout restart deployment/backend -n klinematrix-test
```

**Lesson**: When cloud environment diverges from local, compare credentials/config first. Don't overengineer - direct secret update was sufficient. ExternalSecrets was already broken; use manual update until workload identity is properly configured.

**Verification**:
```bash
curl -X POST https://klinematrix.com/api/auth/send-code \
  -H "Content-Type: application/json" \
  -d '{"auth_type": "email", "identifier": "test@example.com"}'
# Expected: {"message":"Verification code sent to test@example.com","code":null}
```

---

## MongoDB Database Name Parsing with Query Parameters - Fixed 2025-10-07

**Problem**: Registration failing with "Database name contains invalid character" error in Cosmos DB

**Root Cause**: Database name extraction didn't strip MongoDB URL query parameters:
- Local: `mongodb://host/financial_agent` → Works ✅ (no query params)
- Cosmos DB: `mongodb://host/klinematrix_test?ssl=true&...` → Fails ❌ (has query params)

**Bug existed in TWO places**:
1. `backend/src/core/config.py` line 89: `return self.mongodb_url.split("/")[-1]`
2. `backend/src/database/mongodb.py` line 25: `database_name = mongodb_url.split("/")[-1]`

**Solution**: Strip query parameters in both files
```python
# Before
database_name = mongodb_url.split("/")[-1]
# Returns: "klinematrix_test?ssl=true&replicaSet=globaldb&..."

# After
db_with_params = mongodb_url.split("/")[-1]
database_name = db_with_params.split("?")[0] if "?" in db_with_params else db_with_params
# Returns: "klinematrix_test"
```

**Files Changed**:
- `backend/src/core/config.py` (config property)
- `backend/src/database/mongodb.py` (connection logic)

**Why it worked locally**: Local MongoDB URLs don't have query parameters, hiding the bug. Cosmos DB requires `?ssl=true&replicaSet=globaldb` which exposed the issue.

**Verification**:
```bash
# Check logs show correct database name
kubectl logs deployment/backend -n klinematrix-test | grep database
# Should show: "database": "klinematrix_test" (not "klinematrix_test?ssl=...")

# Test registration
curl -X POST https://klinematrix.com/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","code":"123456","username":"testuser","password":"password123"}'
# Should work without "Database name contains invalid character" error
```

---

## Frontend API URL Fallback to Localhost - Fixed 2025-10-07

**Problem**: Frontend showing CORS error trying to reach `http://localhost:8000` instead of using relative URLs

**Root Cause**: JavaScript falsy check treated empty string as falsy:
```typescript
const API_BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";
// VITE_API_URL="" is falsy, so fallback to localhost:8000
```

**Why it happened**:
- Docker build sets `VITE_API_URL=""` for relative URLs
- Empty string is falsy in JavaScript
- Code falls back to localhost:8000
- Browser tries to connect to user's local machine instead of backend API

**Solution**: Change fallback to empty string
```typescript
// Before
const API_BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

// After
const API_BASE_URL = import.meta.env.VITE_API_URL || "";
```

**File Changed**: `frontend/src/services/authService.ts`

**Architecture reminder**:
```
User Browser → https://klinematrix.com (Ingress)
    ├─ /api/* → backend-service:8000 → backend pod
    └─ /* → frontend-service:80 → frontend pod (static files only)
```

Frontend and backend run in **separate pods**. Frontend JavaScript runs in **user's browser**, not in the pod.

**Verification**:
```bash
# Rebuild frontend
az acr build --registry financialAgent \
  --image klinematrix/frontend:test-v0.4.0 \
  --build-arg VITE_API_URL="" \
  --target production \
  --file frontend/Dockerfile frontend/

# Restart frontend
kubectl delete pod -l app=frontend -n klinematrix-test

# Test - should use relative URL (no CORS error)
# Check browser DevTools: Network tab should show requests to /api/auth/send-code (relative)
```

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
- Pod keeps restarting or OOMKilled
- Logs show `vite` dev server instead of nginx
- Port 3000 instead of port 80

### Root Cause
Docker build not targeting production stage or using wrong base image.

### Diagnosis
```bash
# Check pod logs
kubectl logs deployment/frontend -n klinematrix-test | head -10

# If shows "vite" -> using dev mode
# Should show nginx logs: "GET / HTTP/1.1" 200

# Check which image stage is running
kubectl describe pod -l app=frontend -n klinematrix-test | grep -A 3 "Image:"
```

### Solution

**Rebuild with explicit production target:**
```bash
az acr build --registry financialAgent \
  --image financial-agent/frontend:dev-latest \
  --target production \
  --file frontend/Dockerfile frontend/

kubectl delete pod -l app=frontend -n klinematrix-test
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

### Symptoms
- Deployed new image but old code still running
- Pod shows "Running" but behavior unchanged

### Root Cause
Kubernetes cached the image because tag hasn't changed and `imagePullPolicy` not set to `Always`.

### Diagnosis
```bash
# Check when image was pulled
kubectl describe pod -l app=backend -n klinematrix-test | grep -E "Image:|Pulled:"

# Check imagePullPolicy
kubectl get deployment backend -n klinematrix-test -o jsonpath='{.spec.template.spec.containers[0].imagePullPolicy}'
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
kubectl delete pod -l app=backend -n klinematrix-test

# Or use rollout restart
kubectl rollout restart deployment/backend -n klinematrix-test
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
  -n klinematrix-test
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

## Issue: Service Has No Endpoints (Label Selector Mismatch)

### Symptoms
```bash
# Pods are running and healthy
kubectl get pods -n klinematrix-test
# NAME                     READY   STATUS    RESTARTS   AGE
# backend-xxx-yyy          1/1     Running   0          5m

# But service has no endpoints
kubectl describe svc backend-service -n klinematrix-test
# Selector: app=backend,app.kubernetes.io/version=0.4.1
# Endpoints: <none>  # ❌ No endpoints!

# Application returns 503 or Connection refused
curl https://klinematrix.com/api/health
# 503 Service Temporarily Unavailable
```

### Root Cause
Kustomize's `commonLabels` adds labels to **service selectors**, making them require exact matches. When pods have different version labels than the service selector requires, the service finds zero matching pods.

**Example of mismatch:**
```bash
# Service requires version 0.4.1
kubectl describe svc backend-service -n klinematrix-test
# Selector: app.kubernetes.io/name=klinematrix,app.kubernetes.io/version=0.4.1,app=backend

# But pod has version 0.3.0
kubectl get pod backend-xxx-yyy -n klinematrix-test --show-labels
# Labels: app.kubernetes.io/version=0.3.0,app=backend
```

The service selector is **immutable** after creation, so `kubectl apply` cannot fix it:
```bash
kubectl apply -k .pipeline/k8s/base
# Error: spec.selector: Invalid value: ... field is immutable
```

### Diagnosis
```bash
# 1. Check service selector
kubectl describe svc backend-service -n klinematrix-test | grep "Selector"
# Note: look for version labels in selector

# 2. Check service endpoints (should be empty if mismatch)
kubectl get endpoints backend-service -n klinematrix-test
# Endpoints: <none>

# 3. Check pod labels
kubectl get pods -l app=backend -n klinematrix-test --show-labels
# Compare version label with service selector

# 4. Test if selector is the issue
kubectl get pods -n klinematrix-test -l "app=backend,app.kubernetes.io/version=0.4.1"
# If this returns no pods, but plain "app=backend" returns pods, it's a selector mismatch
```

### Solution

**Delete and recreate services** using base YAML (without `commonLabels`):

```bash
# Example: Fix Redis service
kubectl delete svc redis-service -n klinematrix-test
kubectl apply -f .pipeline/k8s/base/redis/service.yaml -n klinematrix-test

# Example: Fix backend service
kubectl delete svc backend-service -n klinematrix-test
kubectl apply -f .pipeline/k8s/base/backend/service.yaml -n klinematrix-test

# Example: Fix frontend service
kubectl delete svc frontend-service -n klinematrix-test
kubectl apply -f .pipeline/k8s/base/frontend/service.yaml -n klinematrix-test

# Verify endpoints exist
kubectl describe svc backend-service -n klinematrix-test | grep "Endpoints"
# Should show: Endpoints: 10.244.0.252:8000 (pod IP)
```

**Base service.yaml should have minimal stable selector:**
```yaml
# .pipeline/k8s/base/backend/service.yaml
apiVersion: v1
kind: Service
metadata:
  name: backend-service
spec:
  selector:
    app: backend  # ✅ Stable - matches any version
    # NOT: app.kubernetes.io/version: "0.4.2"  # ❌ Too strict
  ports:
  - port: 8000
    targetPort: 8000
```

### Why This Happens

**Kustomize's `commonLabels` is deprecated** for this reason:
```yaml
# .pipeline/k8s/base/kustomization.yaml
commonLabels:  # ⚠️ DEPRECATED - adds labels to selectors
  app.kubernetes.io/version: "0.4.2"

# Better: use 'labels' instead
labels:  # ✅ Adds labels to resources, NOT selectors
  - pairs:
      app.kubernetes.io/version: "0.4.2"
```

When you run `kubectl apply -k`, `commonLabels` adds the version label to:
- ✅ Deployments (pod templates) - OK
- ❌ **Services** (selectors) - BREAKS routing

### Prevention
1. **Avoid `commonLabels`** - it's deprecated, use `labels` instead
2. **Keep service selectors minimal** - only `app: backend`, not version labels
3. **Version labels are informational only** - put on pods, not in selectors
4. **Test after kustomization changes**:
   ```bash
   kubectl describe svc <service-name> | grep -E "Selector|Endpoints"
   # Endpoints should not be empty
   ```

### Understanding Labels vs Selectors

**Labels** identify resources:
```yaml
# Pod has labels
metadata:
  labels:
    app: backend
    version: "0.4.2"  # Informational tag
```

**Selectors** find resources:
```yaml
# Service uses selector to find pods
spec:
  selector:
    app: backend  # Find pods matching this label
```

**Best Practice:**
- ✅ **Service selectors**: Stable labels only (`app: backend`)
- ✅ **Pod labels**: Can include version (`version: "0.4.2"`)
- ❌ **Avoid**: Version labels in service selectors

This allows pods to update to new versions while services continue routing traffic seamlessly.

---

## Issue: Unexpected Node Autoscaling Due to Duplicate Deployments

### Symptoms
```bash
# More nodes than expected
kubectl get nodes
# Shows 3-4 nodes instead of expected 2

# Multiple namespaces with same applications
kubectl get deployments --all-namespaces | grep -E 'backend|frontend|redis'
# Shows duplicate deployments in multiple namespaces

# High memory utilization triggering autoscale
kubectl top nodes
# Memory: 85-88% across all nodes
```

### Root Cause
Multiple namespaces running duplicate/old workloads that weren't cleaned up during migration, consuming ~30-40% extra resources and triggering cluster autoscaler to add nodes beyond budget expectations.

### Real-World Example (Oct 2025)
- **Before**: 2 nodes expected (1 agentpool + 1 userpool)
- **After autoscale**: 4 nodes running (both pools scaled 1→2)
- **Cause**: Old v0.4.2 deployments in `default` namespace + newer versions in `klinematrix-test` (then v0.4.5/v0.6.1, now v0.5.4/v0.8.4)
- **Memory waste**: ~640Mi consumed by duplicate pods
- **Cost impact**: $53/month → $106/month (100% increase)

### Diagnosis
```bash
# 1. Check all namespaces for deployments
kubectl get deployments --all-namespaces -o wide

# 2. Identify duplicate applications
kubectl get pods --all-namespaces | grep -E 'backend|frontend|redis'

# 3. Check resource usage across nodes
kubectl top nodes

# 4. Check pod status in old namespaces
kubectl get pods -n default
# Look for CrashLoopBackOff or old versions

# 5. Check autoscaler events
kubectl get events --all-namespaces --sort-by='.lastTimestamp' | grep -i "scale"

# 6. Verify autoscaler settings
az aks nodepool show --resource-group FinancialAgent \
  --cluster-name FinancialAgent-AKS --name agentpool \
  --query '{min:minCount, max:maxCount, current:count}'
```

### Solution

**Step 1: Identify old/duplicate deployments**
```bash
# List all deployments across namespaces
kubectl get deployments --all-namespaces

# Check for old versions or crashing pods
kubectl get pods --all-namespaces | grep -E "CrashLoopBackOff|Error|ImagePullBackOff"
```

**Step 2: Delete duplicate deployments**
```bash
# Example: Delete old deployments in default namespace
kubectl delete deployment backend frontend redis -n default

# Verify cleanup
kubectl get pods -n default
# Should show: No resources found
```

**Step 3: Check resource usage improvement**
```bash
# Memory should drop significantly
kubectl top nodes

# Example improvement:
# Before: userpool at 85% (2708Mi)
# After:  userpool at 60% (1910Mi)
# Freed:  ~640Mi (19% reduction)
```

**Step 4: Cap autoscaler to prevent future unexpected scaling**
```bash
# Set max-count to prevent scaling beyond budget
az aks nodepool update --resource-group FinancialAgent \
  --cluster-name FinancialAgent-AKS \
  --name agentpool \
  --update-cluster-autoscaler --max-count 1

az aks nodepool update --resource-group FinancialAgent \
  --cluster-name FinancialAgent-AKS \
  --name userpool \
  --update-cluster-autoscaler --max-count 1

# Autoscaler will scale down extra nodes within 10-15 minutes
```

**Step 5: Monitor scale-down**
```bash
# Watch node count decrease
kubectl get nodes -w

# Check autoscaler status
kubectl get configmap cluster-autoscaler-status -n kube-system -o yaml | grep "Scale-down"
```

### Prevention

**1. Always clean up old deployments when migrating:**
```bash
# Before migrating to new namespace
kubectl get deployments -n old-namespace
kubectl delete deployment <old-deployments> -n old-namespace
```

**2. Set appropriate autoscaler limits:**
```bash
# Production: Set max-count to match budget/capacity planning
az aks nodepool update --max-count <expected-max-nodes>

# Development: Use tighter limits to prevent cost surprises
az aks nodepool update --max-count 1
```

**3. Regular cleanup checks:**
```bash
# Weekly: Check for orphaned deployments
kubectl get deployments --all-namespaces

# Weekly: Check node count vs expected
kubectl get nodes | wc -l
```

**4. Monitor resource usage:**
```bash
# Add to monitoring dashboard
kubectl top nodes
kubectl top pods --all-namespaces --sort-by=memory
```

**5. Budget alerts:**
```bash
# Set Azure cost alerts at expected monthly budget
# Example: Alert if cost exceeds $100/month (vs expected $95)
```

### Cost Analysis

**Node costs per month** (Standard_D2ls_v5 in Korea Central):
- 1 node: ~$26.50/month
- 2 nodes: ~$53/month (expected for HA)
- 3 nodes: ~$80/month (one pool autoscaled)
- 4 nodes: ~$106/month (both pools autoscaled)

**Example savings from cleanup:**
- Before: 4 nodes = $106/month
- After cleanup + autoscaler cap: 2 nodes = $53/month
- **Savings: $53/month (50% reduction)**

### Understanding Autoscaler Behavior

**When autoscaler adds nodes:**
1. Pod pending due to insufficient resources
2. Autoscaler checks if adding node would help
3. Checks `max-count` limit not reached
4. Provisions new node (takes ~3-5 minutes)
5. Pod schedules on new node

**When autoscaler removes nodes:**
1. Node utilization <50% for >10 minutes
2. All pods can be evicted safely (PDB respected)
3. Pods can fit on other nodes
4. Node drained and deleted (~10-15 minute delay)

**Memory reservation vs usage:**
- Kubernetes reserves resources based on pod `requests`, not actual usage
- Even crashing pods hold reservations
- This can trigger autoscaling even when actual usage is low

### Related Issues
- See [Pods Pending Due to Resource Constraints](#issue-pods-pending-due-to-resource-constraints) for handling resource-based scheduling failures
- See [Cost Optimization Guide](../deployment/cost-optimization.md) for comprehensive cost management

---

## Issue: Pods Pending Due to Resource Constraints

### Symptoms
```bash
kubectl get pods -n klinematrix-test
# NAME                     READY   STATUS             RESTARTS   AGE
# backend-new-abc123       0/1     Pending            0          2m
# backend-old-xyz789       0/1     CrashLoopBackOff   5          10m

kubectl describe pod backend-new-abc123 -n klinematrix-test
# Events:
#   Warning  FailedScheduling  0/2 nodes available: 1 Insufficient cpu, 2 Insufficient memory
#   Normal   TriggeredScaleUp  pod triggered scale-up: [{aks-agentpool-xxx 1->2 (max: 2)}]
```

### Root Cause
During rolling updates, old crashing pods still consume resource reservations (even though they're failing), preventing new pods from scheduling. Cluster autoscaler is triggered but takes time to add nodes, blocking deployment progress.

### Diagnosis
```bash
# 1. Check all pods and their resource usage
kubectl get pods -n klinematrix-test
kubectl top pods -n klinematrix-test

# 2. Check pod events for "Insufficient" messages
kubectl describe pod <pending-pod> -n klinematrix-test | grep -A 5 Events

# 3. Check node capacity
kubectl describe nodes | grep -A 5 "Allocated resources"

# 4. Identify old crashing pods consuming resources
kubectl get pods -n klinematrix-test --field-selector=status.phase!=Running
```

### Solution

**Delete old crashing/failed pods immediately** to free resources:

```bash
# Delete specific old pod
kubectl delete pod backend-old-xyz789 -n klinematrix-test

# Or delete all pods with specific old ReplicaSet
kubectl delete pod -l pod-template-hash=<old-hash> -n klinematrix-test

# New pod should schedule within seconds
kubectl get pods -n klinematrix-test -w  # Watch for Running status
```

**If multiple pods are stuck:**
```bash
# Scale down old deployment/replicaset
kubectl scale replicaset <old-replicaset-name> --replicas=0 -n klinematrix-test

# Wait for new pods to start
kubectl wait --for=condition=Ready pod -l app=backend -n klinematrix-test --timeout=120s
```

### Why Deleting Old Pods Helps

Kubernetes **reserves resources** based on pod `requests`, even for crashing pods:
```yaml
# Each pod reserves these resources
resources:
  requests:
    memory: "512Mi"
    cpu: "250m"
```

When a pod is `CrashLoopBackOff`:
- ✅ Kubernetes keeps the pod object (for debugging)
- ✅ Resource reservation remains (blocking new pods)
- ❌ Pod isn't actually using resources (it's crashed)

Deleting the old pod:
- Releases the resource reservation immediately
- Allows new pod to schedule without waiting for autoscaler
- Old pod's ReplicaSet won't recreate it (new ReplicaSet has taken over)

### Prevention

**1. Set appropriate resource requests/limits:**
```yaml
# .pipeline/k8s/base/backend/deployment.yaml
resources:
  requests:
    memory: "256Mi"  # Lower request = more pods fit
    cpu: "100m"
  limits:
    memory: "512Mi"  # Upper bound
    cpu: "500m"
```

**2. Configure pod disruption budgets** for graceful replacements:
```yaml
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: backend-pdb
spec:
  minAvailable: 1  # Keep at least 1 pod during updates
  selector:
    matchLabels:
      app: backend
```

**3. Use smaller image builds** to reduce memory footprint:
- Frontend: Use production nginx build, not dev vite server
- Backend: Use slim Python base images

**4. Monitor cluster autoscaler:**
```bash
# Check autoscaler logs
kubectl logs -n kube-system deployment/cluster-autoscaler

# Check node provisioning time
kubectl get events --sort-by='.lastTimestamp' | grep ScaleUp
```

### Quick Fix Script
```bash
#!/bin/bash
# clean-failed-pods.sh - Delete failed pods to free resources

NAMESPACE="klinematrix-test"

echo "Deleting failed/crashing pods in $NAMESPACE..."

kubectl delete pod \
  --field-selector=status.phase!=Running \
  -n $NAMESPACE

echo "Remaining pods:"
kubectl get pods -n $NAMESPACE
```

---

## Issue: Pods Stuck in Pending During Rolling Update (Over-Allocated CPU Requests)

**Pattern ID**: K8S-001

### Symptoms
```bash
kubectl get pods -n klinematrix-test
# NAME                            READY   STATUS    RESTARTS   AGE
# backend-new-7b8d9f5c4d-abc123   0/1     Pending   0          5m
# backend-old-6c7a8b3d2e-xyz789   1/1     Running   0          30m

kubectl describe pod backend-new-7b8d9f5c4d-abc123 -n klinematrix-test
# Events:
#   Warning  FailedScheduling  0/3 nodes available: Insufficient cpu
```

### Root Cause
CPU requests were set too high across multiple pods, causing node bin-packing to fail during rolling updates. When a new pod tries to schedule, the combined CPU requests of all pods (old + new) exceed available node capacity, even though actual CPU usage is low.

**Real-World Example** (Oct 2025):
- 3 nodes with ~2000m CPU each = 6000m total
- 11 pods × 100m CPU request = 1100m (fits comfortably)
- Reduced to 11 pods × 50m = 550m (50% reduction)
- Result: Rolling updates can now create temporary duplicate pods without capacity issues

### Diagnosis
```bash
# 1. Check pod CPU requests vs node capacity
kubectl describe nodes | grep -A 5 "Allocated resources"

# Look for cpu requests near or exceeding node capacity (2000m on Standard_D2ls_v5)

# 2. Check pending pod events
kubectl describe pod <pending-pod> -n klinematrix-test | grep "Insufficient cpu"

# 3. Calculate total CPU requests
kubectl get pods -n klinematrix-test -o jsonpath='{range .items[*]}{.metadata.name}{"\t"}{.spec.containers[*].resources.requests.cpu}{"\n"}{end}'

# 4. Compare actual usage vs requests
kubectl top pods -n klinematrix-test
```

### Solution

**Reduce CPU requests to match actual usage:**

```yaml
# Before (too high):
resources:
  requests:
    cpu: "100m"  # Reserved but not fully used
  limits:
    cpu: "500m"

# After (optimized):
resources:
  requests:
    cpu: "50m"   # Matches actual usage
  limits:
    cpu: "500m"  # Keep burst capacity
```

**Apply to all deployments:**

```bash
# Example for backend
# Edit .pipeline/k8s/base/backend/deployment.yaml
# Change cpu request from 100m to 50m

# Apply changes
kubectl apply -k .pipeline/k8s/overlays/test/

# Force rolling restart to create new pods
kubectl rollout restart deployment/backend -n klinematrix-test
```

**Affected components** (based on Oct 2025 optimization):
- Backend: 100m→50m
- ClickHouse: 100m→50m
- Langfuse Server: 100m→50m
- Langfuse Worker: 50m→25m

### Prevention

**1. Right-size CPU requests based on actual usage:**
```bash
# Monitor actual CPU usage over time
kubectl top pods -n klinematrix-test --containers

# Set requests to ~10% above average usage
# Set limits to handle burst traffic
```

**2. Test rolling updates after CPU request changes:**
```bash
# Force rolling update
kubectl rollout restart deployment/<service> -n klinematrix-test

# Watch for Pending pods
kubectl get pods -n klinematrix-test -w
```

**3. Use pod disruption budgets:**
```yaml
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: backend-pdb
spec:
  maxUnavailable: 1  # Allows rolling update to proceed
  selector:
    matchLabels:
      app: backend
```

**4. Monitor node capacity utilization:**
```bash
# Should stay below 80% to allow for rolling updates
kubectl describe nodes | grep -E "cpu.*requests"
```

### Impact
- **Before**: Rolling updates would create Pending pods requiring manual intervention
- **After**: Rolling updates complete automatically with 2x pod capacity during rollout
- **Cost**: No change (requests don't affect pricing, only limits do)
- **Performance**: No degradation (actual usage was already <50m)

### Related Issues
- See [Pods Pending Due to Resource Constraints](#issue-pods-pending-due-to-resource-constraints) for general resource troubleshooting
- See [Cost Optimization Guide](../deployment/cost-optimization.md) for resource sizing methodology

---

## Issue: Rolling Update Creates Two ReplicaSets Simultaneously

**Pattern ID**: K8S-002

### Symptoms
```bash
kubectl get replicasets -n klinematrix-test
# NAME                      DESIRED   CURRENT   READY   AGE
# backend-7b8d9f5c4d (new)  1         1         0       5m    # New version stuck at 0/1 Ready
# backend-6c7a8b3d2e (old)  1         1         1       30m   # Old version still running

# Deployment shows progressing but never completes
kubectl get deployment backend -n klinematrix-test
# NAME      READY   UP-TO-DATE   AVAILABLE   AGE
# backend   1/1     1            1           30m
# Conditions: Progressing (ReplicaSetUpdated)
```

### Root Cause
During rolling updates, Kubernetes creates a new ReplicaSet while keeping the old one. If the new pod fails to become Ready (due to CPU constraints, health check failures, or dependency issues), both ReplicaSets remain active, consuming double the resources.

**Common Triggers:**
1. New pod Pending due to insufficient CPU/memory (see K8S-001)
2. New pod fails readiness probe (database connection issues)
3. New pod CrashLoopBackOff (code errors)

### Diagnosis
```bash
# 1. Check ReplicaSet status
kubectl get replicasets -n klinematrix-test -l app=backend

# Look for two ReplicaSets with DESIRED=1

# 2. Check why new pod isn't Ready
kubectl get pods -n klinematrix-test -l app=backend
kubectl describe pod <new-pod-name> -n klinematrix-test

# 3. Check deployment rollout status
kubectl rollout status deployment/backend -n klinematrix-test

# 4. Check rollout history
kubectl rollout history deployment/backend -n klinematrix-test
```

### Solution

**Option 1: Fix the underlying issue** (preferred):

```bash
# Example: If pod is Pending due to CPU (K8S-001)
# Delete old pod to free resources
kubectl delete pod <old-pod-name> -n klinematrix-test

# New pod should schedule and become Ready
kubectl wait --for=condition=Ready pod -l app=backend,pod-template-hash=<new-hash> -n klinematrix-test --timeout=120s
```

**Option 2: Rollback to previous version:**

```bash
# Undo the rollout
kubectl rollout undo deployment/backend -n klinematrix-test

# Verify rollback completed
kubectl rollout status deployment/backend -n klinematrix-test
```

**Option 3: Force cleanup old ReplicaSet:**

```bash
# Scale down old ReplicaSet manually
kubectl scale replicaset backend-6c7a8b3d2e --replicas=0 -n klinematrix-test

# Verify only new ReplicaSet remains
kubectl get replicasets -n klinematrix-test -l app=backend
```

### Prevention

**1. Ensure sufficient resources for rolling updates:**
```yaml
# Keep CPU requests low enough to allow 2x pods during rollout
resources:
  requests:
    cpu: "50m"      # Allows room for old + new pod
    memory: "384Mi"
```

**2. Configure deployment strategy:**
```yaml
spec:
  replicas: 1
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxUnavailable: 0   # Keep old pod until new pod is Ready
      maxSurge: 1         # Allow 1 extra pod during rollout
```

**3. Set appropriate readiness probe timing:**
```yaml
readinessProbe:
  httpGet:
    path: /api/health/ready
    port: 8000
  initialDelaySeconds: 10  # Give app time to start
  periodSeconds: 5
  failureThreshold: 3      # Allow 3 failures before marking unready
```

**4. Monitor rollout progress:**
```bash
# Watch rollout in real-time
kubectl rollout status deployment/backend -n klinematrix-test -w

# If stuck for >5 minutes, investigate immediately
```

**5. Use deployment deadline:**
```yaml
spec:
  progressDeadlineSeconds: 300  # Fail rollout if not progressing after 5 min
```

### Understanding Rolling Update Flow

**Normal flow:**
1. New ReplicaSet created with 1 replica
2. New pod scheduled and starts
3. New pod passes readiness probe → Ready
4. Old ReplicaSet scaled down to 0
5. Old pod terminated
6. Rollout complete

**Stuck flow (this issue):**
1. New ReplicaSet created with 1 replica
2. New pod scheduled but **Pending/CrashLoopBackOff**
3. New pod never becomes Ready ❌
4. Old ReplicaSet stays at 1 (maxUnavailable: 0)
5. **Both ReplicaSets active indefinitely**

### Impact
- **Resource consumption**: 2x resource reservations (old + new pod)
- **Deployment time**: Stuck until manual intervention
- **Risk**: Production traffic still served by old version with potential bugs
- **Cost**: Autoscaler may add nodes to fit both pods (see COST-001)

### Related Issues
- See [K8S-001 (Over-Allocated CPU Requests)](#issue-pods-stuck-in-pending-during-rolling-update-over-allocated-cpu-requests) for CPU constraint fixes
- See [K8S-003 (CrashLoopBackOff)](#issue-pod-stuck-in-crashloopbackoff) for dependency failure fixes
- See [Cost Optimization Guide](../deployment/cost-optimization.md) for autoscaler impact

---

## Issue: Mixed Content Error - HTTP Resources on HTTPS Page

**Pattern ID**: WEB-001

### Symptoms
```javascript
// Browser console error:
Mixed Content: The page at 'https://klinematrix.com/' was loaded over HTTPS,
but requested an insecure XMLHttpRequest endpoint
'http://financial-agent-feedback.oss-cn-hangzhou.aliyuncs.com/feedback/...'
This request has been blocked; the content must be served over HTTPS.
```

**User-facing symptoms:**
- Image uploads appear to work (shows progress bar)
- Upload completes but image doesn't display
- Network tab shows request blocked/canceled
- No error shown to user (silent failure)

### Root Cause
OSS presigned URLs were generated using `http://` instead of `https://`, causing browsers to block requests due to mixed content security policy. Modern browsers prevent HTTPS pages from loading HTTP resources to protect against man-in-the-middle attacks.

**Code issue:**
```python
# backend/src/services/oss_service.py (BEFORE FIX)
auth = oss2.Auth(access_key_id, access_key_secret)
self.bucket = oss2.Bucket(auth, endpoint, bucket_name)
# endpoint = "oss-cn-hangzhou.aliyuncs.com" (no protocol)
# Result: presigned URLs use HTTP by default
```

### Diagnosis
```bash
# 1. Check browser console for mixed content errors
# F12 → Console → Look for "Mixed Content" warnings

# 2. Test backend presigned URL generation
kubectl exec -n klinematrix-test deployment/backend -- python -c "
from src.services.oss_service import OSSService
import os
svc = OSSService(
    os.getenv('OSS_ACCESS_KEY'),
    os.getenv('OSS_SECRET_KEY'),
    os.getenv('OSS_ENDPOINT'),
    os.getenv('OSS_BUCKET')
)
url = svc.generate_presigned_upload_url('test/file.png', 'image/png', 300)
print('URL:', url['url'][:60])
print('Uses HTTPS:', url['url'].startswith('https://'))
"

# 3. Check backend logs for upload requests
kubectl logs -l app=backend -n klinematrix-test --tail=50 | grep "upload"

# 4. Inspect Network tab in browser DevTools
# F12 → Network → Filter: XHR → Look for blocked requests
```

### Solution

**Fix OSS service to use HTTPS endpoint:**

```python
# backend/src/services/oss_service.py
def __init__(
    self,
    access_key_id: str,
    access_key_secret: str,
    endpoint: str,
    bucket_name: str,
):
    self.endpoint = endpoint
    self.bucket_name = bucket_name

    # Initialize OSS auth and bucket (use HTTPS endpoint)
    auth = oss2.Auth(access_key_id, access_key_secret)
    # Ensure endpoint uses HTTPS for presigned URLs
    https_endpoint = f"https://{endpoint}" if not endpoint.startswith("http") else endpoint
    self.bucket = oss2.Bucket(auth, https_endpoint, bucket_name)
```

**Deploy fix:**
```bash
# 1. Rebuild backend image with fix
az acr build --registry financialAgent \
  --image klinematrix/backend:test-v0.5.12 \
  --file backend/Dockerfile backend/

# 2. Update deployment
kubectl apply -k .pipeline/k8s/overlays/test

# 3. Restart backend pods
kubectl rollout restart deployment/backend -n klinematrix-test

# 4. Verify HTTPS URLs are generated
kubectl exec -n klinematrix-test deployment/backend -- python -c "
from src.services.oss_service import OSSService
import os
svc = OSSService(
    os.getenv('OSS_ACCESS_KEY'),
    os.getenv('OSS_SECRET_KEY'),
    os.getenv('OSS_ENDPOINT'),
    os.getenv('OSS_BUCKET')
)
url = svc.generate_presigned_upload_url('test/file.png', 'image/png', 300)
assert url['url'].startswith('https://'), 'URL should use HTTPS'
print('✅ Fix verified: URLs use HTTPS')
"
```

### Prevention

**1. Always use HTTPS for external resources:**
```python
# When initializing any S3-compatible client
endpoint = f"https://{raw_endpoint}" if not raw_endpoint.startswith("http") else raw_endpoint
```

**2. Test with browser security policies:**
```javascript
// Frontend integration test
const uploadUrl = await generateUploadUrl({filename: 'test.png', content_type: 'image/png'});
if (!uploadUrl.startsWith('https://')) {
  throw new Error('Upload URL must use HTTPS');
}
```

**3. Add CSP headers to enforce HTTPS:**
```nginx
# nginx.conf
add_header Content-Security-Policy "upgrade-insecure-requests" always;
```

**4. Monitor browser console in production:**
```javascript
// Log mixed content errors
window.addEventListener('securitypolicyviolation', (e) => {
  console.error('CSP Violation:', {
    blockedURI: e.blockedURI,
    violatedDirective: e.violatedDirective
  });
});
```

### Impact
- **Severity**: High (feature completely broken for users)
- **Detection**: Silent failure (no error shown to user)
- **Browser scope**: All modern browsers (Chrome, Firefox, Safari, Edge)
- **Workaround**: None (browsers enforce policy strictly)

### Related Issues
- See [OSS Configuration](../deployment/cloud-setup.md#alibaba-cloud-oss) for OSS setup guide
- See [Feedback Image Attachments](../features/feedback-image-attachments.md) for feature documentation
- See [Security Hardening](../deployment/security-hardening.md) for HTTPS best practices

### Real-World Occurrence
**Date**: October 31, 2025
**Versions Affected**: Backend v0.5.11 and earlier
**Fixed In**: Backend v0.5.12
**Discovery**: User reported "Network Error" during image upload testing
**Resolution Time**: ~2 hours (diagnosis + fix + deployment)

---

## Issue: Backend Image Build Missing Upload Endpoint Code

**Pattern ID**: DEPLOY-001

### Symptoms
```bash
# API endpoint returns 404
curl https://klinematrix.com/api/feedback/upload-image
# HTTP/1.1 404 Not Found

# Backend logs show endpoint not registered
kubectl exec -n klinematrix-test deployment/backend -- \
  python -c "from src.api.feedback import router; print([r.path for r in router.routes])"
# Output: ['/api/feedback/items', '/api/feedback/items/{item_id}']
# Missing: '/api/feedback/upload-image'
```

**User-facing symptoms:**
- "Request failed with status code 404" error on image upload
- Upload widget appears but upload fails immediately
- No server-side error logged (request never reaches backend)

### Root Cause
Docker image was built from ACR build context **before** the upload endpoint code was committed to git. ACR builds upload the local directory content, so if code hasn't been pushed/committed when build runs, the image will be missing those changes.

**Timeline that causes this:**
1. Developer writes upload endpoint code locally
2. Developer runs `az acr build` (uploads local `backend/` directory)
3. **BUG**: Local code includes uncommitted changes
4. Developer commits code **after** build completes
5. Image is deployed but missing the new endpoint

### Diagnosis
```bash
# 1. Verify endpoint exists in local code
grep -n "upload-image" backend/src/api/feedback.py

# 2. Check if endpoint is registered in deployed pod
kubectl exec -n klinematrix-test deployment/backend -- \
  grep -n "@router.post.*upload" /app/src/api/feedback.py

# 3. Compare file sizes (local vs deployed)
wc -c backend/src/api/feedback.py
kubectl exec -n klinematrix-test deployment/backend -- \
  wc -c /app/src/api/feedback.py

# 4. Check file modification date in image
kubectl exec -n klinematrix-test deployment/backend -- \
  ls -la /app/src/api/feedback.py
# If date is older than expected, image was built from old code

# 5. Verify image tag matches expected version
kubectl get deployment backend -n klinematrix-test \
  -o jsonpath='{.spec.template.spec.containers[0].image}'
```

### Solution

**Option 1: Rebuild with correct source (recommended):**
```bash
# 1. Ensure all code is committed
git status
git add backend/src/api/feedback.py
git commit -m "feat: add upload endpoint"
git push origin main

# 2. Build image from committed code
az acr build --registry financialAgent \
  --image klinematrix/backend:test-v0.5.11 \
  --file backend/Dockerfile backend/

# 3. Force pull new image (use unique tag)
# Option A: Use timestamp tag to force unique build
TIMESTAMP=$(date +%s)
az acr build --registry financialAgent \
  --image klinematrix/backend:test-v0.5.11-${TIMESTAMP} \
  --file backend/Dockerfile backend/

# Update deployment to use timestamped image
kubectl set image deployment/backend \
  backend=financialagent-gxftdbbre4gtegea.azurecr.io/klinematrix/backend:test-v0.5.11-${TIMESTAMP} \
  -n klinematrix-test

# 4. Restart pods
kubectl rollout restart deployment/backend -n klinematrix-test

# 5. Verify endpoint is now available
kubectl exec -n klinematrix-test deployment/backend -- \
  python -c "from src.api.feedback import router; \
  routes = [r.path for r in router.routes]; \
  print('Upload endpoint exists:', '/api/feedback/upload-image' in routes)"
```

**Option 2: Patch file directly (NOT RECOMMENDED - testing only):**
```bash
# Copy file into running pod (temporary fix for testing)
kubectl cp backend/src/api/feedback.py \
  klinematrix-test/backend-xxx:/app/src/api/feedback.py

# Restart pod to reload code
kubectl delete pod backend-xxx -n klinematrix-test

# Note: This change will be lost on next deployment!
```

### Prevention

**1. Always commit before building images:**
```bash
# Add to deployment workflow
git status | grep "nothing to commit" || {
  echo "❌ Uncommitted changes found. Commit first!"; exit 1;
}

az acr build ...
```

**2. Use git commit SHA as image tag:**
```bash
# Ensures image matches exact code state
COMMIT_SHA=$(git rev-parse --short HEAD)
az acr build --registry financialAgent \
  --image klinematrix/backend:${COMMIT_SHA} \
  --file backend/Dockerfile backend/
```

**3. Add verification step after build:**
```bash
# Verify image contains expected files/code
docker run --rm klinematrix/backend:test-v0.5.11 \
  grep -q "upload-image" /app/src/api/feedback.py && \
  echo "✅ Upload endpoint code present" || \
  echo "❌ Upload endpoint code missing!"
```

**4. Use CI/CD pipeline with git integration:**
```yaml
# GitHub Actions example
- name: Build Docker image
  run: |
    # CI builds from checked-out commit (never local changes)
    az acr build --registry financialAgent \
      --image klinematrix/backend:${{ github.sha }} \
      --file backend/Dockerfile backend/
```

**5. Document build-commit workflow:**
```markdown
# Deployment Workflow
1. ✅ Write code
2. ✅ Test locally
3. ✅ Commit changes
4. ✅ Push to git
5. ✅ Build Docker image (from committed code)
6. ✅ Deploy image
```

### Impact
- **Severity**: Critical (feature completely broken)
- **Detection**: API 404 errors, missing routes
- **Scope**: Affects any endpoint added but not in deployed image
- **Resolution**: Rebuild image with correct source

### Related Issues
- See [Old Image Cached](#issue-old-image-cached-changes-not-reflected) for caching issues
- See [ImagePullBackOff](#issue-pod-stuck-in-imagepullbackoff) for image availability issues
- See [Deployment Workflow](../deployment/workflow.md) for CI/CD best practices

### Real-World Occurrence
**Date**: October 31, 2025
**Versions Affected**: Backend v0.5.11 (initial build)
**Fixed In**: Backend v0.5.11-1761890785 (rebuild with code)
**Discovery**: Image upload returned 404, endpoint not in routes list
**Root Cause**: ACR build ran before commit with upload endpoint code
**Resolution**: Rebuilt image with timestamped tag from committed code

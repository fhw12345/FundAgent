# Kubernetes Issues & Troubleshooting

Common Kubernetes issues encountered in ACK (Alibaba Cloud) and AKS (Azure) environments with detailed resolution steps.

---

## ENV001: Test Environment (klinematrix.com) Not Accessible

### Symptoms
- Documentation references https://klinematrix.com
- Site returns connection timeout or DNS error
- Confusion about which environment to use for testing

### Root Cause
Azure AKS test environment was planned but deployment prioritized Alibaba Cloud ACK for production first. Test environment has not yet been deployed.

### Current Environment Status

| Environment | Platform | URL | Status |
|------------|----------|-----|--------|
| **Dev/Local** | Docker Compose | http://localhost:3000 | ✅ Active |
| **Test** | Azure AKS | https://klinematrix.com | ⚠️ Planned (not deployed) |
| **Production** | Alibaba ACK | https://klinecubic.cn | ✅ Active |

### Resolution

**For local development:**
```bash
make dev  # Uses docker-compose
```

**For cloud testing:**
Use the production environment: https://klinecubic.cn

**Verify production health:**
```bash
curl https://klinecubic.cn/api/health
```

### Prevention
- Always check `docs/deployment/infrastructure.md` for latest environment status
- Refer to `CLAUDE.md` environment table before deploying

---

## ARCH001: ACR Image Pull Authentication

### Symptoms
- Pods stuck in `ImagePullBackOff` status
- Error: `Failed to pull image ... unauthorized: authentication required`
- Container images not pulling from Azure Container Registry

### Root Cause
Missing or incorrect `imagePullSecrets` configuration for Azure Container Registry (ACR) authentication.

### How ACR Authentication Works

```
Pod Scheduled
  ↓
Kubelet checks spec.imagePullSecrets
  ↓
Reads acr-secret (Docker registry credentials)
  ↓
HTTPS + Basic Auth to ACR
  ↓
ACR validates credentials
  ↓
Returns image layers → Container starts
```

### Resolution Steps

#### 1. Verify Secret Exists

```bash
kubectl get secret acr-secret -n klinematrix-prod
```

If missing, create it:

```bash
kubectl create secret docker-registry acr-secret \
  --docker-server=financialagent-gxftdbbre4gtegea.azurecr.io \
  --docker-username=<ACR_USERNAME> \
  --docker-password=<ACR_PASSWORD> \
  -n klinematrix-prod
```

#### 2. Verify Deployment References Secret

```bash
kubectl get deploy backend -n klinematrix-prod -o yaml | grep imagePullSecrets
```

Should show:
```yaml
imagePullSecrets:
- name: acr-secret
```

#### 3. Test ACR Credentials Locally

```bash
docker login financialagent-gxftdbbre4gtegea.azurecr.io
# Enter credentials - should succeed
```

#### 4. Check Pod Events

```bash
kubectl describe pod <pod-name> -n klinematrix-prod | grep -A 10 Events
```

Look for image pull errors.

#### 5. Restart Deployment

```bash
kubectl rollout restart deployment/backend -n klinematrix-prod
```

### See Also
- [ACK Architecture](../deployment/ack-architecture.md#3️⃣-azure-container-registry-acr-authentication) for complete authentication flows

---

## DEPLOY001: Image Update Not Reflected After `kubectl apply`

### Symptoms
- Updated `kustomization.yaml` with new image tag
- Ran `kubectl apply -k overlays/prod/`
- Pods still running old image version
- No errors, but changes not applied

### Root Cause
In ACK (Alibaba Cloud Kubernetes), updating image tags in `kustomization.yaml` does NOT automatically trigger pod rollouts. Kubernetes only recreates pods when the **pod template** changes, not when external references change.

### Resolution

**Always run `kubectl rollout restart` after `kubectl apply`:**

```bash
# 1. Apply configuration
kubectl apply -k .pipeline/k8s/overlays/prod/

# 2. Force rollout restart (REQUIRED for ACK)
kubectl rollout restart deployment/backend deployment/frontend -n klinematrix-prod

# 3. Verify new image is running
kubectl get deploy backend -n klinematrix-prod -o jsonpath='{.spec.template.spec.containers[0].image}'
```

### Why This Happens

```yaml
# Kustomize transforms this:
images:
- name: klinematrix/backend
  newTag: "prod-v0.6.0"

# Into this in the deployment:
spec:
  template:
    spec:
      containers:
      - image: financialagent-.../backend:prod-v0.6.0

# BUT: If the image REFERENCE changes without the template hash changing,
# Kubernetes won't detect it as a pod template update.
```

### Prevention
- **Always** use `kubectl rollout restart` after `kubectl apply -k`
- Add to deployment checklist
- Consider using `imagePullPolicy: Always` for non-production environments

---

## CERT001: SSL Certificate Not Renewing

### Symptoms
- Certificate expiration warnings
- HTTPS site showing "Certificate expired" error
- Cert-Manager logs show renewal failures

### Resolution Steps

#### 1. Check Certificate Status

```bash
kubectl get certificate -n klinematrix-prod
kubectl describe certificate klinecubic-tls -n klinematrix-prod
```

#### 2. Check Cert-Manager Logs

```bash
kubectl logs -f deployment/cert-manager -n cert-manager
```

Look for ACME challenge failures.

#### 3. Verify ClusterIssuer

```bash
kubectl get clusterissuer letsencrypt-prod -o yaml
```

#### 4. Force Certificate Renewal

```bash
# Delete the secret (cert-manager will recreate)
kubectl delete secret klinecubic-tls -n klinematrix-prod

# Delete the certificate resource to trigger fresh request
kubectl delete certificate klinecubic-tls -n klinematrix-prod

# Cert-Manager will automatically recreate based on Ingress annotation
```

#### 5. Verify HTTP-01 Challenge Access

```bash
# Ensure /.well-known/acme-challenge is reachable
curl -I http://klinecubic.cn/.well-known/acme-challenge/test
```

Should return 404 (handled by cert-manager solver), not 403/500.

---

## SECRET001: Backend Secrets Not Found

### Symptoms
- Backend pods crashing with "KeyError" or "Environment variable not set"
- Logs show missing environment variables
- Deployment succeeds but pods fail to start

### Resolution Steps

#### 1. Verify Secret Exists

```bash
kubectl get secret backend-secrets -n klinematrix-prod
```

#### 2. Check Secret Keys

```bash
kubectl get secret backend-secrets -n klinematrix-prod -o jsonpath='{.data}' | jq 'keys'
```

Should include:
- `mongodb-url`
- `dashscope-api-key`
- `jwt-secret`
- `alpaca-api-key`
- `alpha-vantage-api-key`

#### 3. Verify Environment Variable Mapping

```bash
kubectl get deploy backend -n klinematrix-prod -o yaml | grep -A 5 "secretKeyRef"
```

#### 4. Recreate Secret if Missing

```bash
kubectl create secret generic backend-secrets \
  --from-literal=mongodb-url="mongodb://..." \
  --from-literal=dashscope-api-key="sk-..." \
  --from-literal=jwt-secret="..." \
  --from-literal=alpaca-api-key="..." \
  --from-literal=alpaca-secret-key="..." \
  --from-literal=alpha-vantage-api-key="..." \
  -n klinematrix-prod
```

#### 5. Restart Deployment

```bash
kubectl rollout restart deployment/backend -n klinematrix-prod
```

---

## INGRESS001: NGINX Ingress Not Routing Traffic

### Symptoms
- Cannot access application via domain (klinecubic.cn)
- Direct service access works (port-forward)
- NGINX Ingress controller pod running

### Resolution Steps

#### 1. Check Ingress Status

```bash
kubectl get ingress -n klinematrix-prod
kubectl describe ingress klinematrix-ingress -n klinematrix-prod
```

Verify:
- `ingressClassName: nginx` is set
- Hosts match DNS records
- Backend services exist

#### 2. Check NGINX Controller Service

```bash
kubectl get svc -n ingress-nginx
```

Should show `LoadBalancer` type with EXTERNAL-IP.

#### 3. Verify SLB External IP

```bash
kubectl get svc nginx-ingress-ingress-nginx-controller -n ingress-nginx -o jsonpath='{.status.loadBalancer.ingress[0].ip}'
```

Should return: `139.224.28.199` (or current SLB IP)

#### 4. Check DNS Records

```bash
nslookup klinecubic.cn
dig klinecubic.cn
```

Should point to SLB external IP.

#### 5. Test NGINX Controller Logs

```bash
kubectl logs -f deployment/nginx-ingress-ingress-nginx-controller -n ingress-nginx | grep klinecubic
```

Look for routing errors or 404s.

#### 6. Verify Backend Service

```bash
# Port-forward to test backend directly
kubectl port-forward svc/backend-service 8000:8000 -n klinematrix-prod
curl http://localhost:8000/api/health
```

If this works but Ingress doesn't, issue is in NGINX routing.

---

## POD001: Pods in CrashLoopBackOff

### Symptoms
- Pods repeatedly restarting
- Status shows `CrashLoopBackOff`
- Application not accessible

### Resolution Steps

#### 1. Check Pod Logs

```bash
kubectl logs <pod-name> -n klinematrix-prod --previous
```

The `--previous` flag shows logs from the crashed container.

#### 2. Describe Pod for Events

```bash
kubectl describe pod <pod-name> -n klinematrix-prod
```

Look for:
- Image pull errors
- Resource limits exceeded (OOMKilled)
- Liveness/readiness probe failures

#### 3. Common Causes & Fixes

**OOMKilled (Out of Memory):**
```yaml
# Increase memory limits
resources:
  limits:
    memory: "1Gi"  # Increase from 512Mi
```

**Missing Environment Variables:**
```bash
# Check SECRET001 above
kubectl get secret backend-secrets -n klinematrix-prod
```

**Database Connection Failures:**
```bash
# Verify MongoDB is running
kubectl get pods -n klinematrix-prod | grep mongodb

# Check MongoDB logs
kubectl logs mongodb-0 -n klinematrix-prod
```

#### 4. Disable Health Checks Temporarily

```bash
# Edit deployment to comment out liveness/readinessProbe
kubectl edit deploy backend -n klinematrix-prod
```

This allows pod to start for debugging, then re-enable after fixing root cause.

---

## NODE001: Node Resource Exhaustion

### Symptoms
- Pods stuck in `Pending` status
- Events show "Insufficient cpu" or "Insufficient memory"
- Some pods running, others can't be scheduled

### Resolution Steps

#### 1. Check Node Resources

```bash
kubectl top nodes
kubectl describe nodes
```

Look for memory/CPU usage near 100%.

#### 2. Check Pod Resource Requests

```bash
kubectl top pods -n klinematrix-prod --containers
```

#### 3. Scale Down Non-Critical Workloads

```bash
# Temporarily reduce replicas
kubectl scale deployment frontend --replicas=0 -n klinematrix-prod
```

#### 4. Increase Node Pool Size (ACK)

```bash
# Via Alibaba Cloud Console
# Container Service → Clusters → Node Pools → Scale
```

Or use auto-scaling if configured.

#### 5. Evict Low-Priority Pods

```bash
# Check for non-essential pods
kubectl get pods --all-namespaces

# Delete if safe
kubectl delete pod <pod-name> -n <namespace>
```

---

## K8S-001: ImagePullBackOff - Docker Hub Access in ACK China

**Issue ID:** K8S-001
**Severity:** High
**Occurrences:** 2 (nginx-ingress webhook, Redis deployment)
**Related Commits:** af8b0c7, 0d5e3e5

### Symptoms
- Pods stuck in `ImagePullBackOff` or `ErrImagePull` status
- Error messages show network timeouts:
  ```
  Failed to pull image "redis:7.2-alpine":
  dial tcp <docker-hub-ip>:443: i/o timeout
  ```
- Multiple retry attempts to different Docker Hub IPs all timeout
- Failing to pull images from `registry-1.docker.io` or `docker.io`

### Root Cause
ACK clusters deployed in China regions (cn-shanghai, cn-hangzhou, etc.) cannot reliably access Docker Hub (`registry-1.docker.io`) due to network restrictions (GFW blocking). This affects:
- Public images from Docker Hub
- Images using full `docker.io/library/` prefix
- Any image without explicit registry specified

### Diagnosis

Check which image is failing:
```bash
kubectl describe pod <failing-pod> -n <namespace> | grep -A 3 "Image:"
kubectl get events -n <namespace> --sort-by='.lastTimestamp' | grep ImagePull
```

### Solution Options

#### Option 1: Use Alibaba Cloud Registry Mirror (Public Images)

**Best for:** Official public images (redis, nginx, postgres, etc.)

```yaml
# Before (Docker Hub - FAILS in China)
image: redis:7.2-alpine

# After (Alibaba Mirror - WORKS)
image: registry.cn-hangzhou.aliyuncs.com/library/redis:7.2-alpine
```

**Limitations:**
- Not all images/tags are mirrored
- SHA digest pinning may not work (digests not always mirrored)
- Some specialized images unavailable

**Example:** nginx-ingress controller (commit af8b0c7)
```yaml
controller:
  image:
    registry: registry.cn-hangzhou.aliyuncs.com
    image: google_containers/nginx-ingress-controller
    tag: v1.9.4
    digest: ""  # Must be empty - digests not mirrored
```

#### Option 2: Use Azure Container Registry (Custom/Cached Images)

**Best for:** Application images, cached third-party images

```yaml
# Application images
image: financialagent-gxftdbbre4gtegea.azurecr.io/klinecubic/backend:prod-v0.6.0

# Cached third-party images
image: financialagent-gxftdbbre4gtegea.azurecr.io/redis:7.2-alpine-final
```

**How to cache public images in ACR:**
```bash
# 1. Pull from Docker Hub locally (or from mirror)
docker pull redis:7.2-alpine

# 2. Tag for ACR
docker tag redis:7.2-alpine financialagent-gxftdbbre4gtegea.azurecr.io/redis:7.2-alpine-final

# 3. Login to ACR
az acr login --name financialAgent

# 4. Push to ACR
docker push financialagent-gxftdbbre4gtegea.azurecr.io/redis:7.2-alpine-final

# 5. Update deployment YAML
# image: financialagent-gxftdbbre4gtegea.azurecr.io/redis:7.2-alpine-final
```

### Prevention
1. **Always use ACR or Alibaba mirrors** for ACK deployments
2. Test image pull accessibility before production deployment:
   ```bash
   # From ACK cluster node
   kubectl debug node/<node-name> -it --image=busybox
   wget -O- <registry-url>
   ```
3. Document image sources in deployment READMEs
4. Pre-cache critical images in ACR during CI/CD pipeline

### See Also
- [Image Registry Strategy](#image-registry-strategy) in deployment docs
- [ACK Architecture](../deployment/ack-architecture.md)
- nginx-ingress Helm README: `.pipeline/helm/nginx-ingress/README.md`

---

## K8S-002: Git Config Out of Sync with Cluster Reality

**Issue ID:** K8S-002
**Severity:** Critical
**Occurrences:** 1 (Redis image tag mismatch)
**Related Commits:** 0d5e3e5

### Symptoms
- Deployment updates trigger new pod creation that immediately fails
- Running pods use different image than what's in Git deployment YAML
- `kubectl describe pod` shows different image than `cat deployment.yaml`
- Rolling updates cause ImagePullBackOff even though old pod runs fine

### Root Cause
Manual cluster modifications or image updates were made directly via kubectl without updating the Git source of truth. This breaks GitOps principles and causes:
- Git-defined configuration doesn't match cluster reality
- Any deployment update tries to "fix" the cluster to match stale Git config
- Results in failed rollouts and broken deployments

### Real-World Example

**Git config (.pipeline/k8s/base/redis/deployment.yaml):**
```yaml
image: redis:7.2-alpine  # Docker Hub (inaccessible)
```

**Actual running pod:**
```bash
$ kubectl describe pod redis-57f57df567-qzjmq -n klinematrix-prod | grep Image:
Image: financialagent-gxftdbbre4gtegea.azurecr.io/redis:7.2-alpine-final
```

**Result:** Any `kubectl apply` triggered rolling update creating new pod with `redis:7.2-alpine` → ImagePullBackOff

### Diagnosis

```bash
# 1. Check running pod image
kubectl describe pod <pod-name> -n <namespace> | grep "Image:"

# 2. Check Git deployment config
cat .pipeline/k8s/base/<resource>/deployment.yaml | grep "image:"

# 3. Check current deployment spec
kubectl get deployment <name> -n <namespace> -o jsonpath='{.spec.template.spec.containers[0].image}'

# 4. Compare all three - they MUST match
```

### Resolution Steps

#### 1. Identify Correct Image

The **running pod** usually has the correct, working image:
```bash
kubectl get pods -n <namespace> -l app=<label>
# Find the Running pod
kubectl describe pod <running-pod-name> -n <namespace> | grep "Image:"
```

#### 2. Update Git Config

```bash
# Edit deployment YAML to match cluster reality
vim .pipeline/k8s/base/<resource>/deployment.yaml

# Change from:
# image: redis:7.2-alpine

# To:
# image: financialagent-gxftdbbre4gtegea.azurecr.io/redis:7.2-alpine-final
```

#### 3. Commit Changes

```bash
git add .pipeline/k8s/base/<resource>/deployment.yaml
git commit -m "fix(infra): sync <resource> deployment with ACR image

Issue:
- Git config referenced Docker Hub image
- Cluster actually used ACR image
- Any deployment update caused ImagePullBackOff

Solution:
- Updated Git to match cluster reality
- Future updates will use correct ACR image
"
```

#### 4. Apply and Verify

```bash
# Apply Git config (now matches cluster)
kubectl apply -f .pipeline/k8s/base/<resource>/deployment.yaml -n <namespace>

# No new pod should be created (config already matches)
kubectl get pods -n <namespace> -l app=<label>
```

### Prevention

1. **Enforce GitOps Workflow:**
   - ALL changes must go through Git first
   - Never use `kubectl edit` or `kubectl patch` in production
   - Use `kubectl apply -f` with Git-tracked YAMLs only

2. **Regular Config Audits:**
   ```bash
   # Compare Git vs Cluster script
   for deploy in backend frontend redis; do
     echo "=== $deploy ==="
     echo "Git:"
     grep "image:" .pipeline/k8s/base/$deploy/deployment.yaml
     echo "Cluster:"
     kubectl get deploy $deploy -n klinematrix-prod -o jsonpath='{.spec.template.spec.containers[0].image}'
     echo ""
   done
   ```

3. **Use Deployment Tools:**
   - ArgoCD, Flux CD, or other GitOps tools that enforce Git as source of truth
   - Prevent manual cluster modifications

4. **Document Changes:**
   - Always document WHY image was changed
   - Link to commits, issue tracking, version docs

### See Also
- [Deployment Workflow](../deployment/workflow.md#git-config-sync)
- [GitOps Best Practices](../development/pipeline-workflow.md)

---

## K8S-003: ACK LoadBalancer Annotation Mismatch

**Issue ID:** K8S-003
**Severity:** Medium
**Occurrences:** 1 (nginx-ingress service)
**Related Commits:** af8b0c7

### Symptoms
- ACK console shows warning: **"付费模式与实际实例不一致"** (Payment mode inconsistent with actual instance)
- Service has annotation specifying CLB spec that doesn't match reality
- Warning doesn't break functionality but indicates configuration drift
- May cause issues during future CLB modifications

### Root Cause
Kubernetes Service has hardcoded `service.beta.kubernetes.io/alibaba-cloud-loadbalancer-spec` annotation (e.g., `slb.s1.small`) but the actual Cloud Load Balancer instance has different configuration (e.g., PayByCLCU model or different spec).

### Real-World Example

**Service annotation:**
```yaml
apiVersion: v1
kind: Service
metadata:
  annotations:
    service.beta.kubernetes.io/alibaba-cloud-loadbalancer-spec: slb.s1.small
spec:
  type: LoadBalancer
```

**Actual CLB:** PayByCLCU instance (not slb.s1.small)

**Result:** ACK Cloud Controller Manager detects mismatch and shows console warning

### Diagnosis

```bash
# Check service annotations
kubectl get svc <service-name> -n <namespace> -o jsonpath='{.metadata.annotations}' | jq .

# Look for:
# - service.beta.kubernetes.io/alibaba-cloud-loadbalancer-spec
# - service.beta.kubernetes.io/alibaba-cloud-loadbalancer-instance-charge-type

# Check external IP (will work despite warning)
kubectl get svc <service-name> -n <namespace> -o jsonpath='{.status.loadBalancer.ingress[0].ip}'
```

### Resolution

**Remove the annotation and let ACK CCM auto-detect:**

```yaml
# Before
service:
  type: LoadBalancer
  annotations:
    service.beta.kubernetes.io/alibaba-cloud-loadbalancer-spec: slb.s1.small

# After
service:
  type: LoadBalancer
  annotations: {}  # Let ACK auto-detect
```

**Apply via Helm (for nginx-ingress):**
```bash
helm upgrade nginx-ingress ingress-nginx/ingress-nginx \
  --namespace ingress-nginx \
  --values .pipeline/helm/nginx-ingress/values.yaml \
  --values .pipeline/helm/nginx-ingress/values-prod.yaml
```

**Or via kubectl:**
```bash
# Remove annotation
kubectl annotate svc <service-name> -n <namespace> \
  service.beta.kubernetes.io/alibaba-cloud-loadbalancer-spec-

# Verify removed
kubectl get svc <service-name> -n <namespace> -o jsonpath='{.metadata.annotations}' | jq .
```

### Impact

✅ **Zero downtime** - ACK CCM preserves existing CLB and external IP
✅ **External IP unchanged** - Traffic continues flowing
✅ **Console warning cleared** - Configuration drift resolved
✅ **Future-proof** - Allows ACK to manage CLB configuration

### Prevention

1. **Don't hardcode CLB specs** unless creating brand new LoadBalancer
2. **Let ACK CCM auto-detect** for existing CLBs
3. **Only specify annotations** when you need to:
   - Create new CLB with specific requirements
   - Override defaults (e.g., internal vs public)
   - Configure special features (e.g., health checks)

### When TO Use Annotations

```yaml
# Creating NEW LoadBalancer with requirements
service:
  type: LoadBalancer
  annotations:
    service.beta.kubernetes.io/alibaba-cloud-loadbalancer-spec: slb.s2.small
    service.beta.kubernetes.io/alibaba-cloud-loadbalancer-address-type: internet
    service.beta.kubernetes.io/alibaba-cloud-loadbalancer-charge-type: PayByTraffic
```

### When NOT TO Use Annotations

```yaml
# Using EXISTING LoadBalancer - let ACK auto-detect
service:
  type: LoadBalancer
  annotations: {}
```

### See Also
- [nginx-ingress Helm README](.pipeline/helm/nginx-ingress/README.md#key-configuration-decisions)
- [ACK LoadBalancer Annotations](https://www.alibabacloud.com/help/en/ack/ack-managed-and-ack-dedicated/user-guide/use-annotations-to-configure-load-balancing)

---

## 🔗 Related Documentation

- [ACK Architecture](../deployment/ack-architecture.md) - Complete infrastructure overview
- [Deployment Workflow](../deployment/workflow.md) - Step-by-step deployment procedures
- [Deployment Issues](deployment-issues.md) - Cloud deployment troubleshooting

---

**Last Updated:** 2025-11-13

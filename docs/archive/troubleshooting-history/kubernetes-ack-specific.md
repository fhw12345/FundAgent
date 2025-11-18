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

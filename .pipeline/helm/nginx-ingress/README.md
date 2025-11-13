# nginx-ingress Helm Deployment

## Overview

nginx-ingress controller for **klinecubic-financialagent** ACK cluster in Alibaba Cloud (cn-shanghai).

**Chart**: `ingress-nginx/ingress-nginx` v4.14.0
**App Version**: 1.14.0
**External IP**: 139.224.28.199

## Deployment

### Prerequisites

```bash
# Add Helm repo
helm repo add ingress-nginx https://kubernetes.github.io/ingress-nginx
helm repo update

# Configure kubectl for ACK cluster
export KUBECONFIG=/Users/allenpan/.kube/config-ack-prod
```

### Initial Installation

```bash
cd /Users/allenpan/Desktop/repos/projects/financial_agent

helm install nginx-ingress ingress-nginx/ingress-nginx \
  --namespace ingress-nginx \
  --create-namespace \
  --values .pipeline/helm/nginx-ingress/values.yaml \
  --values .pipeline/helm/nginx-ingress/values-prod.yaml
```

### Upgrade Existing Installation

```bash
export KUBECONFIG=/Users/allenpan/.kube/config-ack-prod

helm upgrade nginx-ingress ingress-nginx/ingress-nginx \
  --namespace ingress-nginx \
  --values .pipeline/helm/nginx-ingress/values.yaml \
  --values .pipeline/helm/nginx-ingress/values-prod.yaml
```

### Verify Deployment

```bash
# Check service status
kubectl get svc nginx-ingress-ingress-nginx-controller -n ingress-nginx

# Check pods
kubectl get pods -n ingress-nginx

# Test external access
curl -I http://139.224.28.199
```

## Configuration

### Files Structure

```
.pipeline/helm/nginx-ingress/
├── values.yaml          # Base configuration (all environments)
├── values-prod.yaml     # Production overrides
└── README.md           # This file
```

### Key Configuration Decisions

#### 1. No LoadBalancer Spec Annotation

**Before:**
```yaml
service:
  annotations:
    service.beta.kubernetes.io/alibaba-cloud-loadbalancer-spec: slb.s1.small
```

**After:**
```yaml
service:
  annotations: {}  # Removed
```

**Reason**: Annotation didn't match actual CLB configuration, causing ACK console error:
> "付费模式与实际实例不一致" (Payment mode inconsistent with actual instance)

**Impact**:
- ✅ ACK Cloud Controller Manager auto-detects existing CLB
- ✅ External IP preserved (139.224.28.199)
- ✅ Zero downtime
- ✅ No more ACK console warnings

#### 2. Admission Webhooks Disabled

**Configuration:**
```yaml
controller:
  admissionWebhooks:
    enabled: false
```

**Reason**: Image pull failures due to SHA digest not available in Alibaba Cloud registry:
```
registry.cn-hangzhou.aliyuncs.com/google_containers/kube-webhook-certgen:v1.6.4@sha256:bcfc926e...
```

**Impact**:
- ✅ No ImagePullBackOff errors
- ✅ Clean pod status
- ℹ️ Admission webhook is optional - ingress controller works fine without it

#### 3. Alibaba Cloud Registry

**Configuration:**
```yaml
controller:
  image:
    registry: registry.cn-hangzhou.aliyuncs.com
    image: google_containers/nginx-ingress-controller
    tag: v1.9.4
    digest: ""  # No SHA digest
```

**Benefits**:
- Faster image pulls from China region
- Avoid Docker Hub rate limits
- Use mirrored images

## Troubleshooting

### Cleanup Old Webhook Job

If old admission webhook job exists from previous deployment:

```bash
kubectl delete job nginx-ingress-ingress-nginx-admission-create -n ingress-nginx
```

### Check Helm Values

```bash
helm get values nginx-ingress -n ingress-nginx
```

### View Service Annotations

```bash
kubectl get svc nginx-ingress-ingress-nginx-controller -n ingress-nginx \
  -o jsonpath='{.metadata.annotations}' | jq .
```

### Rollback

```bash
# List revisions
helm history nginx-ingress -n ingress-nginx

# Rollback to previous revision
helm rollback nginx-ingress <revision> -n ingress-nginx
```

## Changelog

### 2025-11-13: Fix LoadBalancer Annotation Mismatch + Webhook Issues

**Issues Fixed:**
1. ❌ LoadBalancer annotation `slb.s1.small` didn't match actual CLB configuration
2. ❌ nginx-ingress-admission-create pod stuck in ImagePullBackOff

**Changes:**
- Removed `service.beta.kubernetes.io/alibaba-cloud-loadbalancer-spec` annotation
- Disabled admission webhooks (`controller.admissionWebhooks.enabled: false`)
- Added production HA configuration (2 replicas, pod anti-affinity)
- Created git-tracked Helm values for reproducible deployments

**Result:**
- ✅ ACK console warnings cleared
- ✅ All pods healthy
- ✅ External IP unchanged (139.224.28.199)
- ✅ Zero downtime deployment

## Maintenance

### Upgrade nginx-ingress Chart Version

```bash
# Check available versions
helm search repo ingress-nginx/ingress-nginx --versions

# Upgrade to specific version
helm upgrade nginx-ingress ingress-nginx/ingress-nginx \
  --namespace ingress-nginx \
  --version <chart-version> \
  --values .pipeline/helm/nginx-ingress/values.yaml \
  --values .pipeline/helm/nginx-ingress/values-prod.yaml
```

### Monitor Controller Logs

```bash
kubectl logs -f -n ingress-nginx \
  -l app.kubernetes.io/component=controller
```

## References

- [nginx-ingress Helm Chart](https://github.com/kubernetes/ingress-nginx/tree/main/charts/ingress-nginx)
- [ACK LoadBalancer Annotations](https://www.alibabacloud.com/help/en/ack/ack-managed-and-ack-dedicated/user-guide/use-annotations-to-configure-load-balancing)
- [Alibaba Cloud Registry Mirror](https://help.aliyun.com/document_detail/60750.html)

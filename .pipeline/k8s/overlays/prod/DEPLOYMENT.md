# Production Deployment to Alibaba Cloud ACK

## Overview

Production environment deployed on Alibaba Cloud Container Service for Kubernetes (ACK) in Shanghai region with hybrid cloud architecture:
- **Compute**: ACK cluster (4 nodes)
- **Container Registry**: Azure ACR
- **Domain**: klinecubic.cn
- **TLS**: Let's Encrypt via cert-manager

## Cluster Information

- **Cluster Name**: klinecubic-financialagent
- **Region**: Shanghai (华东2)
- **Namespace**: klinematrix-prod
- **Nodes**:
  - 1× ecs.r8a.large (2c16GB, 100GB SSD)
  - 3× ecs.u1-c1m2.large (2c4GB, 40GB SSD)
- **LoadBalancer IP**: 139.224.28.199

## Pre-deployment Setup

### 1. Install Infrastructure Components

```bash
# Set kubeconfig
export KUBECONFIG=~/.kube/config-ack-prod

# Install cert-manager (v1.16.2)
kubectl apply -f https://github.com/cert-manager/cert-manager/releases/download/v1.16.2/cert-manager.yaml

# Install nginx-ingress with Alibaba Cloud mirrors (China network optimization)
helm repo add ingress-nginx https://kubernetes.github.io/ingress-nginx
helm repo update

helm install nginx-ingress ingress-nginx/ingress-nginx \
  --namespace ingress-nginx --create-namespace \
  --set controller.service.type=LoadBalancer \
  --set controller.service.annotations."service\.beta\.kubernetes\.io/alibaba-cloud-loadbalancer-spec"="slb.s1.small" \
  --set controller.image.registry=registry.cn-hangzhou.aliyuncs.com \
  --set controller.image.image=google_containers/nginx-ingress-controller \
  --set controller.image.tag=v1.9.4 \
  --set controller.image.digest="" \
  --set controller.admissionWebhooks.enabled=false

# Get LoadBalancer IP
kubectl get svc -n ingress-nginx nginx-ingress-ingress-nginx-controller
```

### 2. Configure DNS

Point your domain to the LoadBalancer IP:

```
Type: A
Name: klinecubic.cn
Value: 139.224.28.199

Type: A
Name: www.klinecubic.cn
Value: 139.224.28.199
```

### 3. Fix cert-manager DNS Resolution (ACK-specific)

ACK's CoreDNS cannot resolve external domains. Apply DNS patch:

```bash
kubectl patch deployment cert-manager -n cert-manager \
  --patch-file cert-manager-dns-patch.yaml
```

## Deployment Process

### 1. Create Namespace and RBAC

```bash
kubectl apply -f namespace.yaml
kubectl apply -f rbac.yaml
```

### 2. Create ACR Pull Secret

```bash
kubectl create secret docker-registry acr-secret \
  --docker-server=financialagent-gxftdbbre4gtegea.azurecr.io \
  --docker-username=financialAgent \
  --docker-password=<ACR_PASSWORD> \
  --namespace klinematrix-prod
```

### 3. Initialize Secrets

```bash
chmod +x init-secrets.sh
./init-secrets.sh
```

**Important**: Update placeholder values after deployment:
```bash
kubectl edit secret backend-secrets -n klinematrix-prod
# Update: dashscope-api-key, tencent-secret-id, tencent-secret-key
```

### 4. Deploy Application

```bash
# Apply all resources using Kustomize
kubectl apply -k .

# Verify deployment
kubectl get pods -n klinematrix-prod
kubectl get certificate -n klinematrix-prod
kubectl get ingress -n klinematrix-prod
```

## Key Fixes Applied

### 1. Backend Image Version
- **Issue**: v0.5.13 doesn't exist in ACR
- **Fix**: Updated kustomization.yaml to use v0.5.12
- **File**: `kustomization.yaml` line 49

### 2. Ingress Class
- **Issue**: Ingress not associated with nginx-ingress controller
- **Fix**: Added `ingressClassName: nginx` to ingress spec
- **File**: `ingress-prod-patch.yaml` line 10

### 3. MongoDB URL Encoding
- **Issue**: MongoDB password contains `/` which breaks URL parsing
- **Fix**: URL-encode password in connection string (`/` → `%2F`, `=` → `%3D`)
- **File**: `init-secrets.sh` line 24-26

### 4. cert-manager DNS Resolution
- **Issue**: ACK CoreDNS cannot resolve external domains
- **Fix**: Configure cert-manager to use Google DNS (8.8.8.8)
- **File**: `cert-manager-dns-patch.yaml`

## Verification

### Check All Services

```bash
# Pods
kubectl get pods -n klinematrix-prod
# Expected: backend, frontend, mongodb, redis all Running

# Certificate
kubectl get certificate -n klinematrix-prod
# Expected: klinecubic-tls READY=True

# Ingress
kubectl get ingress -n klinematrix-prod
# Expected: ADDRESS=139.224.28.199, PORTS=80,443
```

### Test Endpoints

```bash
# Frontend
curl -I https://klinecubic.cn

# Backend API
curl https://klinecubic.cn/api/health

# Certificate details
kubectl get secret klinecubic-tls -n klinematrix-prod -o jsonpath='{.data.tls\.crt}' | base64 -d | openssl x509 -noout -text
```

## Storage Configuration

- **MongoDB**: 10Gi emptyDir (ephemeral, cost-free)
- **Redis**: In-memory only
- **Tradeoff**: Data lost on pod restart (acceptable for Phase 1 testing)

## Cost Optimization

- Using existing node SSDs via emptyDir: **$0 additional cost**
- Cross-cloud image pulls: Within ACR free tier (<100GB/month)
- SLB spec: slb.s1.small (basic LoadBalancer)

## Troubleshooting

### Certificate Not Issuing

```bash
# Check certificate status
kubectl describe certificate klinecubic-tls -n klinematrix-prod

# Check challenges
kubectl get challenges -n klinematrix-prod

# Check cert-manager logs
kubectl logs -n cert-manager deployment/cert-manager
```

### 404 Not Found

Verify ingress class is set:
```bash
kubectl get ingress klinematrix-ingress -n klinematrix-prod -o jsonpath='{.spec.ingressClassName}'
# Should return: nginx
```

### Backend Crashes

Check MongoDB connection:
```bash
kubectl logs -n klinematrix-prod deployment/backend --tail=50
# Look for "MongoDB connection established"
```

## Rollback

```bash
# Rollback deployment
kubectl rollout undo deployment/backend -n klinematrix-prod
kubectl rollout undo deployment/frontend -n klinematrix-prod

# Or delete and redeploy
kubectl delete -k .
kubectl apply -k .
```

## Future Improvements

1. **Persistent Storage**: Migrate from emptyDir to Alibaba Cloud Disk
2. **Azure Key Vault**: Enable External Secrets Operator integration
3. **Monitoring**: Add Prometheus/Grafana
4. **Backup**: Implement MongoDB backup strategy
5. **Autoscaling**: Configure HPA based on CPU/memory

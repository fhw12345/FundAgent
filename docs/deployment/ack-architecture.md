# ACK Production Architecture

Comprehensive guide to the Alibaba Cloud Container Service for Kubernetes (ACK) production environment architecture, authentication mechanisms, and operational procedures.

## 🏗️ Architecture Overview

```
Internet (HTTPS)
     ↓
Alibaba Cloud SLB (139.224.28.199)
     ↓
NGINX Ingress Controller (ingress-nginx namespace)
     ↓
├─→ klinecubic.cn/api → Backend Service (port 8000)
└─→ klinecubic.cn/    → Frontend Service (port 80)
     ↓
Backend Pod ←→ MongoDB (StatefulSet)
     ↓         Redis (Deployment)
     ↓
External APIs (DashScope, Alpaca, Alpha Vantage)
```

### Key Components

| Component | Purpose | Namespace | Access |
|-----------|---------|-----------|--------|
| **NGINX Ingress** | Load balancing, TLS termination | `ingress-nginx` | External SLB |
| **Cert-Manager** | SSL certificate management | `cert-manager` | Internal |
| **Backend** | FastAPI application | `klinematrix-prod` | Via Ingress |
| **Frontend** | React application | `klinematrix-prod` | Via Ingress |
| **MongoDB** | Database (StatefulSet) | `klinematrix-prod` | Internal |
| **Redis** | Cache (Deployment) | `klinematrix-prod` | Internal |

---

## 1️⃣ NGINX Ingress Controller

### Deployment

Installed via Helm chart in the `ingress-nginx` namespace:

```bash
helm install nginx-ingress ingress-nginx/ingress-nginx \
  --namespace ingress-nginx --create-namespace \
  --set controller.service.type=LoadBalancer \
  --set controller.service.annotations."service\.beta\.kubernetes\.io/alibaba-cloud-loadbalancer-spec"="slb.s1.small"
```

### How It Works

1. **Service Load Balancer (SLB) Creation:**
   - Alibaba Cloud Controller Manager detects `type: LoadBalancer`
   - Automatically provisions SLB instance (`slb.s1.small` spec)
   - Assigns external IP: `139.224.28.199`

2. **Traffic Routing:**
   ```
   Internet → SLB:443 (HTTPS)
            → NodePort:30548/32608 (TCP)
            → NGINX Ingress Pod
            → Backend/Frontend Services (HTTP internal)
   ```

3. **Routing Rules:**
   - `/api/*` → backend-service:8000
   - `/*` → frontend-service:80

### Ingress Configuration

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: klinematrix-ingress
  annotations:
    cert-manager.io/cluster-issuer: "letsencrypt-prod"
    nginx.ingress.kubernetes.io/ssl-redirect: "true"
spec:
  ingressClassName: nginx
  tls:
  - hosts:
    - klinecubic.cn
    secretName: klinecubic-tls
  rules:
  - host: klinecubic.cn
    http:
      paths:
      - path: /api
        backend:
          service:
            name: backend-service
            port:
              number: 8000
```

**Key Points:**
- TLS termination happens at Ingress level
- Internal cluster communication uses HTTP (secure network)
- Force SSL redirect ensures all traffic is HTTPS

---

## 2️⃣ Cert-Manager (SSL Certificate Management)

### Deployment

Installed via Helm in the `cert-manager` namespace:

```bash
helm repo add jetstack https://charts.jetstack.io
helm install cert-manager jetstack/cert-manager \
  --namespace cert-manager --create-namespace \
  --set installCRDs=true
```

### Automatic Certificate Workflow

1. **Certificate Request:**
   - Ingress annotation `cert-manager.io/cluster-issuer: "letsencrypt-prod"` triggers request
   - Cert-Manager creates Certificate resource

2. **ACME Challenge (HTTP-01):**
   ```
   Let's Encrypt → HTTP request to klinecubic.cn/.well-known/acme-challenge/TOKEN
                 → NGINX Ingress routes to cert-manager solver pod
                 → Validation succeeds
   ```

3. **Certificate Issuance:**
   - Let's Encrypt issues certificate
   - Cert-Manager stores in Secret: `klinecubic-tls`
   - NGINX Ingress automatically uses the certificate

4. **Auto-Renewal:**
   - Cert-Manager monitors certificate expiration
   - Renews automatically 30 days before expiry
   - Zero downtime renewal

### Verification

```bash
# Check certificate status
kubectl get certificate -n klinematrix-prod

# Check certificate details
kubectl describe certificate klinecubic-tls -n klinematrix-prod

# Verify cert-manager pods
kubectl get pods -n cert-manager
```

---

## 3️⃣ Azure Container Registry (ACR) Authentication

### Registry Details

- **Registry**: `financialagent-gxftdbbre4gtegea.azurecr.io`
- **Image Naming Convention**:
  - Test: `klinematrix/backend:test-v*`, `klinematrix/frontend:test-v*`
  - Prod: `klinecubic/backend:prod-v*`, `klinecubic/frontend:prod-v*`

### Authentication Mechanism

ACK pulls images from Azure ACR using Docker registry secrets:

#### 1. Create Docker Registry Secret (One-time setup)

```bash
kubectl create secret docker-registry acr-secret \
  --docker-server=financialagent-gxftdbbre4gtegea.azurecr.io \
  --docker-username=<ACR_USERNAME> \
  --docker-password=<ACR_PASSWORD> \
  -n klinematrix-prod
```

#### 2. Reference in Deployment

```yaml
apiVersion: apps/v1
kind: Deployment
spec:
  template:
    spec:
      imagePullSecrets:
      - name: acr-secret  # ← References the secret
      containers:
      - name: backend
        image: financialagent-gxftdbbre4gtegea.azurecr.io/klinecubic/backend:prod-v0.7.0
```

#### 3. Image Pull Workflow

```
Pod scheduled
  ↓
Kubelet checks imagePullSecrets
  ↓
Reads acr-secret credentials
  ↓
HTTPS + Basic Auth to ACR
  ↓
ACR validates credentials
  ↓
Returns image layers
  ↓
Container starts
```

### Troubleshooting Image Pull

```bash
# Verify secret exists
kubectl get secret acr-secret -n klinematrix-prod

# Check deployment references secret
kubectl get deploy backend -n klinematrix-prod -o yaml | grep imagePullSecrets

# Test ACR credentials locally
docker login financialagent-gxftdbbre4gtegea.azurecr.io

# Check pod events for image pull errors
kubectl describe pod <pod-name> -n klinematrix-prod
```

---

## 4️⃣ Secrets Management

### Current Approach: Manual Kubernetes Secrets

Application secrets are manually created as Kubernetes secrets:

```bash
kubectl create secret generic backend-secrets \
  --from-literal=mongodb-url="mongodb://..." \
  --from-literal=dashscope-api-key="sk-..." \
  --from-literal=jwt-secret="..." \
  --from-literal=alpaca-api-key="..." \
  --from-literal=alpha-vantage-api-key="..." \
  -n klinematrix-prod
```

### Secret Injection

Secrets are injected as environment variables:

```yaml
containers:
- name: backend
  env:
  - name: MONGODB_URL
    valueFrom:
      secretKeyRef:
        name: backend-secrets
        key: mongodb-url
  - name: DASHSCOPE_API_KEY
    valueFrom:
      secretKeyRef:
        name: backend-secrets
        key: dashscope-api-key
```

### Planned: External Secrets Operator + Azure Key Vault

**Future integration** (not currently active):

```yaml
# Planned: Azure Key Vault → External Secrets Operator → K8s Secrets
apiVersion: external-secrets.io/v1beta1
kind: SecretStore
metadata:
  name: azure-keyvault
spec:
  provider:
    azurekv:
      vaultUrl: "https://klinematrix-test-kv.vault.azure.net/"
      authType: ServicePrincipal
```

**Why not active yet:**
- Requires External Secrets Operator installation
- Cross-cloud (Azure ↔ Alibaba) integration complexity
- Manual secrets management sufficient for current scale

---

## 5️⃣ Kubernetes RBAC

### Service Account

Pods run with limited permissions via `klinematrix-sa`:

```yaml
apiVersion: v1
kind: ServiceAccount
metadata:
  name: klinematrix-sa
  namespace: klinematrix-prod
```

### Permissions (Role)

```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
rules:
- apiGroups: [""]
  resources: ["secrets", "configmaps"]
  verbs: ["get", "list"]  # Read-only
- apiGroups: [""]
  resources: ["pods"]
  verbs: ["get", "list"]  # Pod inspection
```

**Key Points:**
- **Least privilege**: Pods can read secrets/configmaps but not modify
- **No cluster-wide access**: Limited to `klinematrix-prod` namespace
- **Pod introspection**: Allows health checks to query pod metadata

---

## 🔐 Authentication & Communication Summary

| Component | Auth Method | Credentials Storage | Protocol |
|-----------|-------------|---------------------|----------|
| **External → SLB** | None (public) | N/A | HTTPS |
| **SLB → NGINX** | None (trusted network) | N/A | TCP (NodePort) |
| **NGINX → Services** | None (cluster internal) | N/A | HTTP |
| **TLS Certificates** | ACME (Let's Encrypt) | K8s Secret (`klinecubic-tls`) | HTTPS |
| **ACR Image Pull** | Docker Registry Secret | K8s Secret (`acr-secret`) | HTTPS + Basic Auth |
| **Backend Secrets** | K8s Secrets | K8s Secret (`backend-secrets`) | In-cluster (envFrom) |
| **MongoDB** | Password Auth | Embedded in `mongodb-url` | MongoDB Wire Protocol |
| **Redis** | No Auth | N/A (internal service) | Redis Protocol |

---

## 🚀 Deployment Strategy

### Backend: Recreate Strategy

The backend uses `strategy: Recreate` instead of `RollingUpdate` due to memory constraints:

```yaml
spec:
  strategy:
    type: Recreate  # Terminates old pod before starting new one
```

**Cluster Resource Context:**
- **3 nodes** with ~2.3GB memory each (78-86% utilized)
- **1 node** with 16GB memory (for Langfuse/MongoDB)
- Backend requests 512Mi memory

**Why Recreate:**
| Strategy | Behavior | Downtime | Resource Need |
|----------|----------|----------|---------------|
| RollingUpdate | New pod starts → Old pod stops | Zero | 2x pod memory |
| Recreate | Old pod stops → New pod starts | ~10-30s | 1x pod memory |

RollingUpdate would fail with "Insufficient memory" when both pods need to run simultaneously.

---

## 🚀 Deployment Workflow

### 1. Build Images in ACR

```bash
# Get current version
BACKEND_VERSION=$(grep '^version = ' backend/pyproject.toml | sed 's/version = "\(.*\)"/\1/')

# Build in Azure Container Registry
az acr build --registry financialAgent \
  --image klinecubic/backend:prod-v${BACKEND_VERSION} \
  --file backend/Dockerfile backend/
```

### 2. Update Kustomization

Edit `.pipeline/k8s/overlays/prod/kustomization.yaml`:

```yaml
images:
- name: klinematrix/backend
  newName: financialagent-gxftdbbre4gtegea.azurecr.io/klinecubic/backend
  newTag: "prod-v0.7.0"  # ← Update version
```

### 3. Apply Configuration

```bash
export KUBECONFIG=/Users/allenpan/.kube/config-ack-prod
kubectl apply -k .pipeline/k8s/overlays/prod/
```

### 4. Force Rollout Restart

⚠️ **CRITICAL:** ACK requires explicit restart to pull new images even if tag changed:

```bash
kubectl rollout restart deployment/backend deployment/frontend -n klinematrix-prod
```

**Why this is necessary:**
- Image tag changes in `kustomization.yaml` don't auto-trigger rollouts
- Must use `kubectl rollout restart` to force pod recreation
- Pods then pull latest image with updated tag

### 5. Verify Deployment

```bash
# Check pod status
kubectl get pods -n klinematrix-prod

# Verify image version
kubectl get deploy backend -n klinematrix-prod -o jsonpath='{.spec.template.spec.containers[0].image}'

# Test health endpoint
curl https://klinecubic.cn/api/health
```

---

## 🔍 Operational Commands

### Cluster Access

```bash
# Set kubeconfig for ACK
export KUBECONFIG=/Users/allenpan/.kube/config-ack-prod

# Verify connection
kubectl cluster-info
kubectl get nodes
```

### Monitoring

```bash
# Check all pods
kubectl get pods -n klinematrix-prod

# View logs
kubectl logs -f deployment/backend -n klinematrix-prod
kubectl logs -f deployment/frontend -n klinematrix-prod

# Pod resource usage
kubectl top pods -n klinematrix-prod

# Node resource usage
kubectl top nodes
```

### Debugging

```bash
# Describe pod (events, status)
kubectl describe pod <pod-name> -n klinematrix-prod

# Shell into pod
kubectl exec -it <pod-name> -n klinematrix-prod -- /bin/sh

# Port forward for local testing
kubectl port-forward svc/backend-service 8000:8000 -n klinematrix-prod
```

### Ingress & Networking

```bash
# Check ingress status
kubectl get ingress -n klinematrix-prod
kubectl describe ingress klinematrix-ingress -n klinematrix-prod

# Check NGINX Ingress controller
kubectl get svc -n ingress-nginx
kubectl logs -f deployment/nginx-ingress-ingress-nginx-controller -n ingress-nginx

# Verify SLB external IP
kubectl get svc nginx-ingress-ingress-nginx-controller -n ingress-nginx
```

### Certificates

```bash
# Check certificate status
kubectl get certificate -n klinematrix-prod
kubectl describe certificate klinecubic-tls -n klinematrix-prod

# Force certificate renewal
kubectl delete secret klinecubic-tls -n klinematrix-prod
# Cert-manager will automatically recreate
```

---

## 📊 Architecture Comparison: ACK vs AKS

| Aspect | ACK (Production - Active) | AKS (Test - Planned) |
|--------|---------------------------|----------------------|
| **Cloud Provider** | Alibaba Cloud | Azure |
| **Region** | Shanghai (cn-shanghai) | Korea Central (planned) |
| **Domain** | klinecubic.cn | klinematrix.com (planned) |
| **Namespace** | klinematrix-prod | klinematrix-test |
| **Image Prefix** | klinecubic/* | klinematrix/* |
| **Load Balancer** | Alibaba SLB | Azure Load Balancer |
| **Secrets Mgmt** | Manual K8s Secrets | External Secrets + AKV (planned) |
| **Node Pools** | Standard nodes | Workload identity (planned) |
| **Status** | ✅ Active | ⚠️ Not deployed |

---

## 🔗 Related Documentation

- [Deployment Workflow](workflow.md) - Step-by-step deployment procedures
- [Infrastructure Setup](infrastructure.md) - Cloud resource provisioning
- [SLS Logging Setup](sls-logging.md) - Application log collection to Alibaba Cloud SLS
- [Kubernetes Operations](../troubleshooting/kubernetes-issues.md) - Common K8s issues and solutions
- [Environment Configuration](../CLAUDE.md) - Environment variables and settings

---

## 📝 Notes

- **Hybrid Cloud Strategy**: Azure ACR for container registry + Alibaba ACK for compute
- **Security**: TLS everywhere external, HTTP internal (trusted network)
- **High Availability**: Single-node for cost optimization, multi-node planned for HA
- **Monitoring**: Integrated with Alibaba Cloud monitoring + Langfuse for LLM observability

**Last Updated:** 2025-12-13
**Production Version:** Backend v0.8.7, Frontend v0.11.4

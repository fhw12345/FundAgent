# Financial Agent - Infrastructure Overview

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                         Azure Cloud                              │
│                                                                  │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │  DNS: financial-agent-dev.koreacentral.cloudapp.azure.com  │ │
│  │  Public IP: Managed by Azure                                │ │
│  └─────────────────────────┬──────────────────────────────────┘ │
│                            │                                     │
│  ┌─────────────────────────▼──────────────────────────────────┐ │
│  │         Nginx Ingress Controller (HTTPS/TLS)               │ │
│  │         - Let's Encrypt Certificate (auto-renewal)          │ │
│  │         - Routes: / → frontend, /api/* → backend            │ │
│  └─────────────────┬────────────────┬────────────────────────┘ │
│                    │                │                           │
│  ┌─────────────────▼──────┐  ┌──────▼────────────────┐        │
│  │   Frontend Service     │  │   Backend Service      │        │
│  │   (ClusterIP:80)       │  │   (ClusterIP:8000)     │        │
│  └─────────────────┬──────┘  └──────┬────────────────┘        │
│                    │                │                           │
│  ┌─────────────────▼──────┐  ┌──────▼────────────────┐        │
│  │  Frontend Deployment   │  │  Backend Deployment    │        │
│  │  - nginx:alpine        │  │  - Python 3.12 FastAPI │        │
│  │  - Serves React build  │  │  - Connects to MongoDB │        │
│  │  - Proxies /api/       │  │  - Connects to Redis   │        │
│  └────────────────────────┘  └──────┬────────────────┘        │
│                                      │                           │
│                    ┌─────────────────┴───────────────┐          │
│                    │                                 │          │
│         ┌──────────▼──────────┐         ┌───────────▼────────┐│
│         │  Redis Deployment   │         │  Azure Cosmos DB   ││
│         │  - redis:7.2-alpine │         │  (MongoDB API)     ││
│         │  - In-cluster cache │         │  - Managed service ││
│         └─────────────────────┘         └────────────────────┘│
│                                                                  │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │  External Secrets Operator                                 │ │
│  │  - Syncs from Azure Key Vault → Kubernetes Secrets         │ │
│  └───────────────────────────────────────────────────────────┘ │
│                                                                  │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │  Azure Container Registry (ACR)                            │ │
│  │  Images: backend:dev-latest, frontend:dev-latest           │ │
│  └───────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘

External Dependencies:
┌──────────────────────────────────┐
│  Alibaba Cloud                   │
│  - DashScope API (LLM services)  │
│  - OSS (Object Storage)          │
└──────────────────────────────────┘
```

## Resources Created

### 1. Azure Kubernetes Service (AKS)
- **Cluster Name**: `FinancialAgent-AKS`
- **Resource Group**: `FinancialAgent`
- **Region**: Korea Central
- **Node Count**: 1-3 nodes (auto-scaling)
- **Kubernetes Version**: 1.32+
- **Features Enabled**:
  - Workload Identity (for secretless auth)
  - OIDC Issuer
  - Azure CNI networking

### 2. Azure Container Registry (ACR)
- **Registry Name**: `financialAgent`
- **SKU**: Basic
- **Images Stored**:
  - `financial-agent/backend:dev-latest` (Python FastAPI)
  - `financial-agent/frontend:dev-latest` (React + nginx)

### 3. Azure Cosmos DB
- **Account Name**: `financialagent-mongodb`
- **API**: MongoDB API (compatible)
- **Connection**: Via external secret from Key Vault

### 4. Azure Key Vault
- **Name**: `financial-agent-dev-kv`
- **Purpose**: Centralized secret management
- **Secrets**:
  - `mongodb-url`: Cosmos DB connection string
  - `dashscope-api-key`: Alibaba Cloud DashScope API key
- **Access**: Via External Secrets Operator with Workload Identity

### 5. Kubernetes Resources (Namespace: financial-agent-dev)

#### Deployments
1. **backend**
   - Image: ACR/financial-agent/backend:dev-latest
   - Replicas: 1
   - Resources: 256Mi memory, 100m CPU
   - Environment: development

2. **frontend**
   - Image: ACR/financial-agent/frontend:dev-latest
   - Replicas: 1
   - Resources: 128Mi memory, 50m CPU
   - nginx serving React build

3. **redis**
   - Image: redis:7.2-alpine
   - Replicas: 1
   - Resources: 256Mi memory, 50m CPU
   - Configuration: LRU eviction, 256MB max memory

#### Services
1. **backend-service** (ClusterIP:8000)
2. **frontend-service** (ClusterIP:80)
3. **redis-service** (ClusterIP:6379)

#### Ingress
- **Class**: nginx
- **TLS**: Let's Encrypt certificate (auto-renewed)
- **Routes**:
  - `/` → frontend-service:80
  - `/api/` → backend-service:8000

#### Secrets (via External Secrets)
1. **database-secrets**
   - Source: Azure Key Vault secret `mongodb-url`
   - Used by: backend deployment

2. **alibaba-secrets**
   - Source: Azure Key Vault secret `dashscope-api-key`
   - Used by: backend deployment

### 6. Installed Kubernetes Add-ons

#### External Secrets Operator
- **Purpose**: Sync secrets from Azure Key Vault to Kubernetes
- **Version**: v0.12.0+
- **Installation**:
```bash
helm install external-secrets external-secrets/external-secrets \
  --namespace external-secrets-system --create-namespace
```

#### cert-manager
- **Purpose**: Automatic SSL/TLS certificate management
- **Version**: v1.16.0+
- **Installation**:
```bash
helm install cert-manager jetstack/cert-manager \
  --namespace cert-manager --create-namespace \
  --set crds.enabled=true
```

#### Nginx Ingress Controller
- **Purpose**: Ingress traffic management and LoadBalancer
- **Version**: v4.11.0+
- **Installation**:
```bash
helm install nginx-ingress ingress-nginx/ingress-nginx \
  --namespace ingress-nginx --create-namespace
```

## Network Flow

### User Request Flow
```
1. User Browser
   ↓ HTTPS (443)
2. Azure Load Balancer (Public IP)
   ↓
3. Nginx Ingress Controller (TLS termination)
   ↓ (routes based on path)
   ├─→ / (frontend)
   │   ↓ HTTP (80)
   │   Frontend Service → Frontend Pod (nginx)
   └─→ /api/* (backend)
       ↓ HTTP (8000)
       Backend Service → Backend Pod (FastAPI)
       ├─→ Redis Service (port 6379)
       └─→ Cosmos DB (external, port 10255)
```

## Configuration Details

### Frontend Configuration
- **Base URL**: Empty string (uses relative URLs)
- **Production Mode**: Vite builds with `MODE=production`
- **nginx.conf**: Proxies `/api/*` to `http://backend-service:8000/api/`

### Backend Configuration
- **Environment**: development
- **CORS Origins**: `["*"]` (all origins allowed in dev)
- **Database**: MongoDB URL from external secret
- **Cache**: Redis at `redis://redis-service:6379/0`
- **LLM API**: Alibaba DashScope (credentials from external secret)

### Security Configuration
- **HTTPS**: Enforced via Let's Encrypt TLS certificate
- **Secrets**: Stored in Azure Key Vault, synced to Kubernetes
- **Workload Identity**: No service principal credentials in cluster
- **Image Pull**: ACR attached to AKS (automatic authentication)

## Key File Locations

### Kubernetes Manifests
```
.pipeline/k8s/
├── base/                           # Base configuration
│   ├── namespace.yaml
│   ├── backend/
│   │   ├── deployment.yaml
│   │   └── service.yaml
│   ├── frontend/
│   │   ├── deployment.yaml
│   │   └── service.yaml
│   ├── redis/
│   │   ├── deployment.yaml
│   │   ├── service.yaml
│   │   └── configmap.yaml
│   ├── ingress/
│   │   ├── clusterissuer.yaml
│   │   └── ingress.yaml
│   └── kustomization.yaml
└── overlays/
    └── dev/                        # Development environment
        ├── alibaba-config.yaml
        ├── backend-dev-patch.yaml
        ├── secrets.yaml
        └── kustomization.yaml
```

## Deployment Commands Reference

### Manual Deployment
```bash
# Apply all configurations
kubectl apply -k .pipeline/k8s/overlays/dev/

# Restart a specific deployment
kubectl rollout restart deployment/backend -n financial-agent-dev

# Force pod restart (pulls new image if imagePullPolicy: Always)
kubectl delete pod -l app=backend -n financial-agent-dev
```

### Build and Push Images
```bash
# Build and push backend
az acr build --registry financialAgent \
  --image financial-agent/backend:dev-latest \
  --file backend/Dockerfile backend/

# Build and push frontend
az acr build --registry financialAgent \
  --image financial-agent/frontend:dev-latest \
  --target production \
  --file frontend/Dockerfile frontend/
```

### Secret Management
```bash
# Add/update secret in Azure Key Vault
az keyvault secret set \
  --vault-name financial-agent-dev-kv \
  --name mongodb-url \
  --value "mongodb://username:password@host:port/database"

# Force External Secret sync
kubectl delete externalsecret database-secrets -n financial-agent-dev
kubectl apply -k .pipeline/k8s/overlays/dev/
```

### Troubleshooting Commands
```bash
# Check pod logs
kubectl logs -f deployment/backend -n financial-agent-dev

# Describe pod for events
kubectl describe pod -l app=backend -n financial-agent-dev

# Check External Secrets status
kubectl get externalsecret -n financial-agent-dev

# Test backend directly (from inside cluster)
kubectl exec -n financial-agent-dev deployment/backend -- \
  curl -s http://localhost:8000/api/health
```

## Health Check URLs

- **Application**: https://financial-agent-dev.koreacentral.cloudapp.azure.com/
- **Backend Health**: https://financial-agent-dev.koreacentral.cloudapp.azure.com/api/health
- **Backend Docs** (dev): https://financial-agent-dev.koreacentral.cloudapp.azure.com/docs

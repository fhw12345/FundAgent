# Financial Agent - Infrastructure Overview

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                         Azure Cloud                              │
│                                                                  │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │  DNS: financial-agent-dev.koreacentral.cloudapp.azure.com  │ │
│  │  Public IP: 20.249.187.xxx (managed by Azure)              │ │
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
│         │  - No auth (dev)    │         │  - External to AKS ││
│         └─────────────────────┘         └────────────────────┘│
│                                                                  │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │  External Secrets Operator                                 │ │
│  │  - Syncs from Azure Key Vault → Kubernetes Secrets         │ │
│  │  - Secrets: database-secrets, alibaba-secrets              │ │
│  └───────────────────────────────────────────────────────────┘ │
│                                                                  │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │  Azure Container Registry (ACR)                            │ │
│  │  Registry: financialagent-gxftdbbre4gtegea.azurecr.io      │ │
│  │  Images:                                                    │ │
│  │    - financial-agent/backend:dev-latest                    │ │
│  │    - financial-agent/frontend:dev-latest                   │ │
│  └───────────────────────────────────────────────────────────┘ │
│                                                                  │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │  Azure Key Vault: financial-agent-dev-kv                   │ │
│  │  Secrets:                                                   │ │
│  │    - mongodb-url (Cosmos DB connection string)             │ │
│  │    - dashscope-api-key (Alibaba Cloud AI)                  │ │
│  └───────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘

External Dependencies:
┌──────────────────────────────────┐
│  Alibaba Cloud                   │
│  - DashScope API (LLM services)  │
│  - Region: cn-hangzhou           │
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
- **Full URL**: `financialagent-gxftdbbre4gtegea.azurecr.io`
- **SKU**: Basic
- **Images Stored**:
  - `financial-agent/backend:dev-latest` (Python FastAPI)
  - `financial-agent/frontend:dev-latest` (React + nginx)

### 3. Azure Cosmos DB
- **Account Name**: `financialagent-mongodb`
- **API**: MongoDB API (compatible)
- **Database**: Auto-created by application
- **Connection**: Via external secret from Key Vault
- **Endpoint**: `financialagent-mongodb.mongo.cosmos.azure.com:10255`

### 4. Azure Key Vault
- **Name**: `financial-agent-dev-kv`
- **Purpose**: Centralized secret management
- **Secrets**:
  - `mongodb-url`: Cosmos DB connection string with credentials
  - `dashscope-api-key`: Alibaba Cloud DashScope API key
- **Access**: Via External Secrets Operator with Workload Identity

### 5. Azure Public IP & DNS
- **Public IP**: Auto-assigned by Nginx Ingress LoadBalancer
- **DNS Name**: `financial-agent-dev.koreacentral.cloudapp.azure.com`
- **Configuration**: Set via `az network public-ip update`

### 6. Kubernetes Resources (Namespace: financial-agent-dev)

#### Deployments
1. **backend**
   - Image: `financialagent-gxftdbbre4gtegea.azurecr.io/financial-agent/backend:dev-latest`
   - Replicas: 1
   - Resources: 256Mi memory, 100m CPU
   - Environment: development
   - Health Checks: Disabled (temporary)

2. **frontend**
   - Image: `financialagent-gxftdbbre4gtegea.azurecr.io/financial-agent/frontend:dev-latest`
   - Replicas: 1
   - Resources: 128Mi memory, 50m CPU
   - nginx serving React build
   - Proxies `/api/*` to backend

3. **redis**
   - Image: `redis:7.2-alpine`
   - Replicas: 1
   - Resources: 256Mi memory, 50m CPU
   - Configuration: LRU eviction, 256MB max memory

#### Services
1. **backend-service** (ClusterIP:8000)
2. **frontend-service** (ClusterIP:80)
3. **redis-service** (ClusterIP:6379)

#### Ingress
- **Class**: nginx
- **TLS**: Let's Encrypt certificate (auto-renewed by cert-manager)
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

#### ConfigMaps
1. **alibaba-config**
   - Region: cn-hangzhou
   - Endpoint: https://dashscope.cn-hangzhou.aliyuncs.com
   - Model: qwen-vl-plus

2. **redis-config**
   - Redis server configuration

### 7. Installed Kubernetes Add-ons

#### External Secrets Operator (v0.12.0+)
- **Purpose**: Sync secrets from Azure Key Vault to Kubernetes
- **Installation**: Helm chart
```bash
helm install external-secrets external-secrets/external-secrets \
  --namespace external-secrets-system --create-namespace
```
- **Resources**:
  - SecretStore: `azure-keyvault-store` (uses Workload Identity)
  - ExternalSecrets: `database-secrets`, `alibaba-secrets`

#### cert-manager (v1.16.0+)
- **Purpose**: Automatic SSL/TLS certificate management
- **Installation**: Helm chart
```bash
helm install cert-manager jetstack/cert-manager \
  --namespace cert-manager --create-namespace \
  --set crds.enabled=true
```
- **Resources**:
  - ClusterIssuer: `letsencrypt-prod`
  - Certificate: Auto-generated for ingress

#### Nginx Ingress Controller (v4.11.0+)
- **Purpose**: Ingress traffic management and LoadBalancer
- **Installation**: Helm chart
```bash
helm install nginx-ingress ingress-nginx/ingress-nginx \
  --namespace ingress-nginx --create-namespace \
  --set controller.service.annotations."service\.beta\.kubernetes\.io/azure-dns-label-name"=financial-agent-dev
```
- **Features**:
  - Automatic LoadBalancer provisioning
  - SSL termination
  - Reverse proxy for backend

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
   │   ↓ (user opens page, JavaScript loads)
   │   User makes API call to /api/health
   │   ↓ (browser sends to same domain)
   └─→ /api/* (backend via nginx proxy in frontend pod)
       ↓ HTTP (8000)
       Backend Service → Backend Pod (FastAPI)
       ↓ (backend queries)
       ├─→ Redis Service (port 6379)
       └─→ Cosmos DB (external, port 10255)
```

## Configuration Details

### Frontend Configuration
- **Base URL**: Empty string (uses relative URLs)
- **Production Mode**: Vite builds with `MODE=production`
- **API Calls**: All go to relative `/api/*` paths
- **nginx.conf**: Proxies `/api/*` to `http://backend-service:8000/api/`

### Backend Configuration
- **Environment**: development
- **Allowed Hosts**: All hosts allowed (TrustedHostMiddleware disabled in dev)
- **CORS Origins**: `["*"]` (all origins allowed in dev)
- **Database**: MongoDB URL from external secret
- **Cache**: Redis at `redis://redis-service:6379/0`
- **LLM API**: Alibaba DashScope (credentials from external secret)

### Security Configuration
- **HTTPS**: Enforced via Let's Encrypt TLS certificate
- **Secrets**: Stored in Azure Key Vault, synced to Kubernetes
- **Workload Identity**: No service principal credentials stored in cluster
- **Image Pull**: ACR attached to AKS (automatic authentication)

## Key File Locations

### Kubernetes Manifests
```
.pipeline/k8s/
├── base/                           # Base configuration
│   ├── namespace.yaml              # financial-agent-dev namespace
│   ├── backend/
│   │   ├── deployment.yaml         # Backend FastAPI deployment
│   │   └── service.yaml            # Backend ClusterIP service
│   ├── frontend/
│   │   ├── deployment.yaml         # Frontend nginx deployment
│   │   └── service.yaml            # Frontend ClusterIP service
│   ├── redis/
│   │   ├── deployment.yaml         # Redis deployment
│   │   ├── service.yaml            # Redis ClusterIP service
│   │   ├── configmap.yaml          # Redis configuration
│   │   └── secret.yaml             # Redis auth (empty in dev)
│   ├── ingress/
│   │   ├── clusterissuer.yaml      # Let's Encrypt issuer
│   │   └── ingress.yaml            # HTTPS ingress with TLS
│   └── kustomization.yaml          # Base kustomization
│
└── overlays/
    └── dev/                        # Development environment
        ├── alibaba-config.yaml     # Alibaba Cloud configuration
        ├── backend-dev-patch.yaml  # Dev-specific backend env vars
        ├── secrets.yaml            # External Secrets configuration
        └── kustomization.yaml      # Dev overlay kustomization
```

### Docker Images
```
backend/Dockerfile                  # Multi-stage Python build
frontend/Dockerfile                 # Multi-stage React + nginx build
frontend/nginx.conf                 # nginx reverse proxy config
```

### Scripts
```
.pipeline/scripts/
├── setup-azure-dev.sh              # One-time Azure infrastructure setup
└── deploy-dev.sh                   # Manual deployment script
```

## Deployment Commands Reference

### Manual Deployment
```bash
# Apply all configurations
kubectl apply -k .pipeline/k8s/overlays/dev/

# Restart a specific deployment
kubectl rollout restart deployment/backend -n financial-agent-dev
kubectl rollout restart deployment/frontend -n financial-agent-dev

# Force pod restart (pulls new image if imagePullPolicy: Always)
kubectl delete pod -l app=backend -n financial-agent-dev
kubectl delete pod -l app=frontend -n financial-agent-dev

# Check deployment status
kubectl get pods -n financial-agent-dev
kubectl get ingress -n financial-agent-dev
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
  --value "mongodb://username:password@host:port/database?options"

# View secret (External Secrets will auto-sync within 1 hour)
az keyvault secret show \
  --vault-name financial-agent-dev-kv \
  --name mongodb-url

# Force External Secret sync (delete and recreate)
kubectl delete externalsecret database-secrets -n financial-agent-dev
kubectl apply -k .pipeline/k8s/overlays/dev/
```

### Troubleshooting Commands
```bash
# Check pod logs
kubectl logs -f deployment/backend -n financial-agent-dev
kubectl logs -f deployment/frontend -n financial-agent-dev

# Describe pod for events
kubectl describe pod -l app=backend -n financial-agent-dev

# Check External Secrets status
kubectl get externalsecret -n financial-agent-dev
kubectl describe externalsecret database-secrets -n financial-agent-dev

# Check certificate status
kubectl get certificate -n financial-agent-dev
kubectl describe certificate financial-agent-tls -n financial-agent-dev

# Check ingress status
kubectl describe ingress financial-agent-ingress -n financial-agent-dev

# Get public IP
kubectl get svc -n ingress-nginx

# Test backend directly (from inside cluster)
kubectl exec -n financial-agent-dev deployment/backend -- \
  curl -s http://localhost:8000/api/health

# Test Redis connection
kubectl exec -n financial-agent-dev deployment/redis -- redis-cli ping
```

## Current Known Configurations

### Image Pull Policy
Both frontend and backend deployments have `imagePullPolicy: Always` to ensure latest images are pulled on pod restart.

### Health Checks
- **Backend**: Disabled temporarily (health endpoint returns 400)
- **Frontend**: Active (checks nginx on port 80 path `/`)

### Resource Limits
- **Backend**: 256Mi memory / 100m CPU
- **Frontend**: 128Mi memory / 50m CPU
- **Redis**: 256Mi memory / 50m CPU

### Environment-Specific Settings (Dev)
- **Backend**:
  - `LOG_LEVEL=DEBUG`
  - `ENABLE_DEBUG=true`
  - `CORS_ORIGINS='["*"]'`
  - TrustedHostMiddleware disabled

- **Frontend**:
  - Vite build mode: production
  - Base URL: empty string (relative URLs)

## External Dependencies

### Alibaba Cloud
- **Service**: DashScope (AI/LLM API)
- **Region**: cn-hangzhou
- **API Key**: Stored in Azure Key Vault (`dashscope-api-key`)

### Azure Cosmos DB
- **API Type**: MongoDB
- **Account**: financialagent-mongodb
- **Connection String**: Stored in Azure Key Vault (`mongodb-url`)

## Admin Rotation Checklist

When rotating credentials or updating infrastructure:

### 1. Rotating Database Credentials
```bash
# 1. Update Cosmos DB password in Azure Portal
# 2. Update Key Vault secret
az keyvault secret set \
  --vault-name financial-agent-dev-kv \
  --name mongodb-url \
  --value "new-connection-string"
# 3. Force secret sync (or wait up to 1 hour)
kubectl delete externalsecret database-secrets -n financial-agent-dev
kubectl apply -k .pipeline/k8s/overlays/dev/
# 4. Restart backend pods
kubectl rollout restart deployment/backend -n financial-agent-dev
```

### 2. Rotating API Keys (Alibaba DashScope)
```bash
# 1. Generate new API key in Alibaba Cloud Console
# 2. Update Key Vault
az keyvault secret set \
  --vault-name financial-agent-dev-kv \
  --name dashscope-api-key \
  --value "new-api-key"
# 3. Force sync and restart
kubectl delete externalsecret alibaba-secrets -n financial-agent-dev
kubectl apply -k .pipeline/k8s/overlays/dev/
kubectl rollout restart deployment/backend -n financial-agent-dev
```

### 3. Renewing TLS Certificate
TLS certificates are automatically renewed by cert-manager. If manual renewal is needed:
```bash
# Check certificate expiration
kubectl describe certificate financial-agent-tls -n financial-agent-dev

# Force renewal (delete and recreate)
kubectl delete certificate financial-agent-tls -n financial-agent-dev
kubectl delete secret financial-agent-tls -n financial-agent-dev
kubectl apply -k .pipeline/k8s/overlays/dev/
```

### 4. Updating AKS Credentials
```bash
# Refresh AKS credentials
az aks get-credentials \
  --resource-group FinancialAgent \
  --name FinancialAgent-AKS \
  --overwrite-existing
```

### 5. Updating ACR Access
ACR is attached to AKS via `az aks update --attach-acr`. If re-attachment is needed:
```bash
az aks update \
  --resource-group FinancialAgent \
  --name FinancialAgent-AKS \
  --attach-acr financialAgent
```

## Health Check URLs

- **Application**: https://financial-agent-dev.koreacentral.cloudapp.azure.com/
- **Backend Health**: https://financial-agent-dev.koreacentral.cloudapp.azure.com/api/health
- **Backend Docs** (dev only): https://financial-agent-dev.koreacentral.cloudapp.azure.com/docs

# Financial Agent - Infrastructure Overview

**Environment**: Test (klinematrix-test)
**Domain**: https://klinematrix.com
**Users**: 10 beta testers

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                         Cloudflare DNS                           │
│  Domain: klinematrix.com                                         │
│  A Record: @ → 4.217.130.195                                     │
│  A Record: www → 4.217.130.195                                   │
│  Email Auth: SPF, DKIM, DMARC (Tencent Cloud)                    │
└─────────────────────────┬────────────────────────────────────────┘
                          │
┌─────────────────────────▼────────────────────────────────────────┐
│                         Azure Cloud (Korea Central)              │
│                                                                  │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │  Public IP: 4.217.130.195                                   │ │
│  │  DNS: klinematrix.com (via Cloudflare)                      │ │
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
│         └─────────────────────┘         │  - DB: klinematrix_test ││
│                                          └────────────────────┘│
│  ┌───────────────────────────────────────────────────────────┐ │
│  │  Azure Key Vault: klinematrix-test-kv                     │ │
│  │  - JWT secret, MongoDB URL, LLM API key, SMTP credentials │ │
│  └───────────────────────────────────────────────────────────┘ │
│                                                                  │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │  Azure Container Registry (ACR): financialAgent            │ │
│  │  Images: klinematrix/backend:test-v0.3.0                   │ │
│  │          klinematrix/frontend:test-v0.3.0                  │ │
│  └───────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘

External Dependencies:
┌─────────────────────────────────────────────────────────────┐
│  Alibaba Cloud (cn-hangzhou)                                │
│  - DashScope API (Qwen LLM services)                        │
│  - Model: qwen-vl-plus                                      │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│  Tencent Cloud 邮件推送 (SES)                                 │
│  - Region: ap-guangzhou                                     │
│  - API: Simple Email Service (SES)                          │
│  - Sender: noreply@klinematrix.com                          │
│  - Email verification codes for user registration           │
└─────────────────────────────────────────────────────────────┘
```

## Resources Created

### 1. Azure Kubernetes Service (AKS)
- **Cluster Name**: `FinancialAgent-AKS`
- **Resource Group**: `FinancialAgent`
- **Region**: Korea Central
- **Node Count**: 3 nodes (fixed) across 3 pools
- **Kubernetes Version**: 1.28+
- **Features Enabled**:
  - Workload Identity (for secretless auth)
  - OIDC Issuer
  - Azure CNI networking

**Node Pool Configuration** (as of October 2025 migration):

| Pool Name     | VM SKU             | vCPU | Memory | Mode   | Count | Autoscaler   | Purpose                              |
|---------------|--------------------|------|--------|--------|-------|--------------|--------------------------------------|
| agentpool     | Standard_D2ls_v5   | 2    | 4GB    | System | 1     | max-count=1  | System pods (CoreDNS, metrics-server)|
| userpool      | Standard_D2ls_v5   | 2    | 4GB    | User   | 1     | max-count=1  | General workloads                    |
| userpoolv2    | Standard_E2_v3     | 2    | 16GB   | User   | 1     | max-count=1  | Memory-intensive workloads (ClickHouse, Langfuse) |

**Cost**: $237/month (3 nodes total, autoscaler capped at max-count=1 per pool to prevent cost overruns)

**Note**: Autoscaler configured with max-count=1 to prevent automatic scaling beyond 3 nodes total. See [Cost Optimization Guide](cost-optimization.md) for details.

**Access**:
```bash
az aks get-credentials --resource-group FinancialAgent --name FinancialAgent-AKS
```

### 2. Azure Container Registry (ACR)
- **Registry Name**: `financialAgent` *(legacy name, kept for budget)*
- **Registry URL**: `financialagent-gxftdbbre4gtegea.azurecr.io`
- **SKU**: Basic
- **Images Stored** (new naming):
  - `klinematrix/backend:test-v0.3.0` (Python FastAPI)
  - `klinematrix/frontend:test-v0.3.0` (React + nginx)

**Note**: ACR name cannot be renamed (globally unique), but we use new `klinematrix/*` naming for images inside.

### 3. Azure Cosmos DB
- **Account Name**: `financialagent-mongodb` *(legacy name, kept for budget)*
- **API**: MongoDB API (compatible)
- **Database**: `klinematrix_test` (test environment)
- **Connection**: Via secret from Key Vault

**Note**: Cosmos DB account cannot be renamed (globally unique), but we use different database names per environment.

### 4. Azure Key Vault
- **Name**: `klinematrix-test-kv`
- **Resource Group**: `FinancialAgent`
- **Purpose**: Test environment secrets
- **Secrets**:
  - `jwt-secret-key-test`: Application JWT signing key
  - `mongodb-connection-string-test`: Cosmos DB connection string
  - `alibaba-dashscope-api-key-test`: Alibaba Cloud DashScope API key
  - `tencent-secret-id-test`: Tencent Cloud API SecretId
  - `tencent-secret-key-test`: Tencent Cloud API SecretKey

**Access**:
```bash
az keyvault secret list --vault-name klinematrix-test-kv
az keyvault secret show --vault-name klinematrix-test-kv --name <secret-name>
```

### 5. Kubernetes Resources (Namespace: klinematrix-test)

#### Deployments
1. **backend**
   - Image: `klinematrix/backend:test-v0.3.0`
   - Replicas: 1
   - Resources: 256Mi memory (request), 512Mi (limit), 100m-500m CPU
   - Environment: test

2. **frontend**
   - Image: `klinematrix/frontend:test-v0.3.0`
   - Replicas: 1
   - Resources: 128Mi memory (request), 256Mi (limit), 50m-200m CPU
   - nginx serving React build

3. **redis**
   - Image: redis:7.2-alpine
   - Replicas: 1
   - Resources: 64Mi memory (request), 256Mi (limit), 50m-200m CPU
   - Configuration: LRU eviction, 256MB max memory

#### Services
1. **backend-service** (ClusterIP:8000)
2. **frontend-service** (ClusterIP:80)
3. **redis-service** (ClusterIP:6379)

#### Ingress
- **Name**: `klinematrix-ingress`
- **Class**: nginx
- **Hosts**: klinematrix.com, www.klinematrix.com
- **TLS**: Let's Encrypt certificate (auto-renewed)
- **Routes**:
  - `/` → frontend-service:80
  - `/api/*` → backend-service:8000

#### ConfigMaps
1. **alibaba-config**
   - DashScope region: cn-hangzhou
   - Endpoint: https://dashscope.cn-hangzhou.aliyuncs.com
   - Model: qwen-vl-plus

2. **redis-config**
   - Redis server configuration

#### Secrets
1. **app-secrets** (Opaque)
   - jwt-secret-key
   - mongodb-url
   - dashscope-api-key
   - tencent-secret-id
   - tencent-secret-key

2. **redis-auth** (Opaque)
   - password

3. **klinematrix-tls** (kubernetes.io/tls)
   - tls.crt, tls.key (Let's Encrypt)

### 6. Installed Kubernetes Add-ons

#### External Secrets Operator
- **Purpose**: Sync secrets from Azure Key Vault to Kubernetes
- **Version**: v0.12.0+
- **Status**: ⚠️ Not fully working, using manual secret creation
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
2. Cloudflare DNS → Azure Load Balancer (4.217.130.195)
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
       └─→ Cosmos DB (external, port 10255, SSL)
```

## Configuration Details

### Frontend Configuration
- **API URL**: https://klinematrix.com/api
- **Production Mode**: Vite builds with `MODE=production`
- **nginx.conf**: Proxies `/api/*` to `http://backend-service:8000/api/`

### Backend Configuration
- **Environment**: test
- **CORS Origins**: `["https://klinematrix.com"]`
- **Database**: `klinematrix_test` (Cosmos DB)
- **Cache**: Redis at `redis://redis-service:6379/0`
- **LLM API**: Alibaba DashScope (credentials from Key Vault)
- **Email**: Tencent Cloud SES API (noreply@klinematrix.com)
- **Email Bypass**: Disabled (real email verification enabled)

### Security Configuration
- **HTTPS**: Enforced via Let's Encrypt TLS certificate
- **Secrets**: Stored in Azure Key Vault
- **Workload Identity**: No service principal credentials in cluster
- **Image Pull**: ACR attached to AKS (automatic authentication)
- **Email Auth**: SPF, DKIM, DMARC configured via Cloudflare DNS

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
│   │   ├── configmap.yaml
│   │   └── secret.yaml
│   ├── ingress/
│   │   ├── clusterissuer.yaml
│   │   └── ingress.yaml
│   ├── workload-identity/
│   │   └── serviceaccount.yaml
│   └── kustomization.yaml
└── overlays/
    └── test/                       # Test environment
        ├── alibaba-config.yaml
        ├── backend-test-patch.yaml
        ├── frontend-test-patch.yaml
        ├── secrets.yaml
        └── kustomization.yaml
```

## Deployment Commands Reference

### Apply Configuration
```bash
# Apply all configurations
kubectl apply -k .pipeline/k8s/overlays/test/

# Restart a specific deployment
kubectl rollout restart deployment/backend -n klinematrix-test

# Force pod restart (pulls new image if imagePullPolicy: Always)
kubectl delete pod -l app=backend -n klinematrix-test
```

### Build and Push Images
```bash
# Get versions
BACKEND_VERSION=$(grep '^version = ' backend/pyproject.toml | sed 's/version = "\(.*\)"/\1/')
FRONTEND_VERSION=$(grep '"version":' frontend/package.json | sed 's/.*"version": "\(.*\)".*/\1/')

# Build and push backend
az acr build --registry financialAgent \
  --image klinematrix/backend:test-v${BACKEND_VERSION} \
  --file backend/Dockerfile backend/

# Build and push frontend
az acr build --registry financialAgent \
  --image klinematrix/frontend:test-v${FRONTEND_VERSION} \
  --target production \
  --file frontend/Dockerfile frontend/
```

### Secret Management
```bash
# Add/update secret in Azure Key Vault
az keyvault secret set \
  --vault-name klinematrix-test-kv \
  --name mongodb-connection-string-test \
  --value "mongodb://..."

# Recreate Kubernetes secret manually (External Secrets not working)
kubectl delete secret app-secrets -n klinematrix-test
kubectl create secret generic app-secrets -n klinematrix-test \
  --from-literal=jwt-secret-key="$(az keyvault secret show --vault-name klinematrix-test-kv --name jwt-secret-key-test --query value -o tsv)" \
  --from-literal=mongodb-url="$(az keyvault secret show --vault-name klinematrix-test-kv --name mongodb-connection-string-test --query value -o tsv)" \
  --from-literal=dashscope-api-key="$(az keyvault secret show --vault-name klinematrix-test-kv --name alibaba-dashscope-api-key-test --query value -o tsv)" \
  --from-literal=tencent-secret-id="$(az keyvault secret show --vault-name klinematrix-test-kv --name tencent-secret-id-test --query value -o tsv)" \
  --from-literal=tencent-secret-key="$(az keyvault secret show --vault-name klinematrix-test-kv --name tencent-secret-key-test --query value -o tsv)"
```

### Troubleshooting Commands
```bash
# Check pod logs
kubectl logs -f deployment/backend -n klinematrix-test

# Describe pod for events
kubectl describe pod -l app=backend -n klinematrix-test

# Check secrets
kubectl get secret app-secrets -n klinematrix-test

# Test backend directly (from inside cluster)
kubectl exec -n klinematrix-test deployment/backend -- \
  curl -s http://localhost:8000/api/health
```

## DNS Configuration

### Custom Domain (Cloudflare)
- **Domain**: `klinematrix.com`
- **Registrar**: Cloudflare Registrar
- **Nameservers**: Cloudflare (managed)

### DNS Records
| Type | Host | Value | Purpose |
|------|------|-------|---------|
| A | @ | 4.217.130.195 | Root domain → Azure Ingress |
| A | www | 4.217.130.195 | www subdomain → Azure Ingress |
| TXT | @ | v=spf1 include:spf.qcloudmail.com ~all | SPF: Authorize Tencent Cloud |
| TXT | _dmarc | v=DMARC1; p=none; rua=mailto:dmarc@klinematrix.com | DMARC policy |
| CNAME | _domainkey | <tencent-dkim-record> | DKIM signature key |

### Email Authentication
- **Method**: Tencent Cloud SES API (not SMTP)
- **Region**: ap-guangzhou
- **Sender Address**: noreply@klinematrix.com
- **Template ID**: 37066 (email verification)
- **Authentication**: API credentials (SecretId/SecretKey) stored in Key Vault

## Health Check URLs

- **Application**: https://klinematrix.com/
- **www alias**: https://www.klinematrix.com/
- **Backend Health**: https://klinematrix.com/api/health
- **Backend Docs**: https://klinematrix.com/docs

### Expected Health Response
```json
{
  "status": "ok",
  "environment": "test",
  "version": "0.3.0",
  "dependencies": {
    "mongodb": {
      "connected": true,
      "database": "klinematrix_test"
    },
    "redis": {
      "connected": true,
      "version": "7.2.11"
    }
  }
}
```

## Environment Separation

### Local Development (Not in K8s)
- **Location**: Developer machine
- **Method**: Docker Compose for infrastructure (MongoDB, Redis), native Python/Node.js for code
- **Secrets**: `.env.development` file
- **Email**: Bypass mode (no real emails)
- **Database**: Local MongoDB container (port 27017)
- **Cache**: Local Redis container (port 6379)
- **Access**: http://localhost:5173 (frontend), http://localhost:8000 (backend)

### Test (Cloud - AKS)
- **Namespace**: `klinematrix-test`
- **Images**: `klinematrix/backend:test-v0.3.0`
- **Key Vault**: `klinematrix-test-kv`
- **Domain**: https://klinematrix.com
- **Users**: 10 beta testers
- **Email**: Real email verification (Tencent Cloud SES API)
- **Database**: Cosmos DB (`klinematrix_test`)

### Production (Future)
- **Namespace**: `klinematrix-prod`
- **Images**: `klinematrix/backend:v0.3.0` (no "test-" prefix)
- **Key Vault**: `klinematrix-prod-kv`
- **Database**: Cosmos DB (`klinematrix_prod`)

## Related Documentation

- [Resource Inventory](RESOURCE_INVENTORY.md) - Complete resource list
- [Migration Guide](MIGRATION_DEV_TO_TEST.md) - How we migrated to test
- [Deployment Workflow](workflow.md) - How to deploy updates
- [Cloud Setup](cloud-setup.md) - Initial Azure setup

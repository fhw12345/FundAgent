# Resource Inventory - Test Environment

**Last Updated**: 2025-10-06
**Environment**: Test (klinematrix-test)

## Overview

This document provides a complete inventory of all Azure and Kubernetes resources for the test environment.

---

## Azure Resources

### 1. Azure Kubernetes Service (AKS)

| Property | Value |
|----------|-------|
| **Name** | FinancialAgent-AKS |
| **Resource Group** | FinancialAgent |
| **Location** | Korea Central |
| **Kubernetes Version** | 1.32.7 |
| **Node Pools** | agentpool (system), userpool (user) |
| **VM Size** | Standard_D2ls_v5 (2 vCPU, 4 GB RAM) |
| **Node Count** | 2 total (1 per pool, autoscaling capped at max=1) |
| **Purpose** | Hosts test workloads for 10 beta users |

**Node Pool Configuration**:
```bash
# agentpool (system pool)
- Min: 1, Max: 1, Current: 1
- Mode: System
- Autoscaling: Enabled (capped to prevent cost overruns)

# userpool (user pool)
- Min: 1, Max: 1, Current: 1
- Mode: User
- Autoscaling: Enabled (capped to prevent cost overruns)
```

**Access**:
```bash
az aks get-credentials --resource-group FinancialAgent --name FinancialAgent-AKS
```

**Cost Optimization** (Oct 2025):
- Capped autoscaler at max-count=1 per pool to prevent unexpected scaling
- Cleaned up duplicate deployments that were causing memory pressure
- See [Cost Optimization Guide](cost-optimization.md) for details

---

### 2. Azure Container Registry (ACR)

| Property | Value |
|----------|-------|
| **Name** | financialAgent |
| **Registry URL** | financialagent-gxftdbbre4gtegea.azurecr.io |
| **Resource Group** | FinancialAgent |
| **SKU** | Basic |
| **Purpose** | Stores Docker images |

**Images**:
```
├── financial-agent/backend:*      # Legacy naming (deprecated)
├── financial-agent/frontend:*     # Legacy naming (deprecated)
├── klinematrix/backend:test-v0.3.0
└── klinematrix/frontend:test-v0.3.0
```

**Note**: ACR name cannot be changed (globally unique), but we use new naming for images inside.

---

### 3. Azure Cosmos DB (MongoDB API)

| Property | Value |
|----------|-------|
| **Account Name** | financialagent-mongodb |
| **Resource Group** | FinancialAgent |
| **API** | MongoDB |
| **Location** | Global (multi-region) |
| **Purpose** | Application database |

**Databases**:
- `klinematrix_test` - Test environment database

**Connection**:
```bash
# Stored in Key Vault: mongodb-connection-string-test
mongodb://financialagent-mongodb:<password>@financialagent-mongodb.mongo.cosmos.azure.com:10255/?ssl=true&replicaSet=globaldb&retrywrites=false&maxIdleTimeMS=120000&appName=@financialagent-mongodb@
```

**Note**: Cosmos DB account cannot be renamed (globally unique), but we use different database names per environment.

---

### 4. Azure Key Vault

| Property | Value |
|----------|-------|
| **Name** | klinematrix-test-kv |
| **Resource Group** | FinancialAgent |
| **Location** | Korea Central |
| **Purpose** | Stores test environment secrets |

**Secrets**:
```
├── jwt-secret-key-test                    # Application JWT signing key
├── mongodb-connection-string-test         # Cosmos DB connection string
├── alibaba-dashscope-api-key-test         # Alibaba Cloud LLM API key
├── tencent-secret-id-test                 # Tencent Cloud API SecretId
└── tencent-secret-key-test                # Tencent Cloud API SecretKey
```

**Access**:
```bash
az keyvault secret list --vault-name klinematrix-test-kv
az keyvault secret show --vault-name klinematrix-test-kv --name <secret-name>
```

---

### 5. Public IP Address

| Property | Value |
|----------|-------|
| **IP Address** | 4.217.130.195 |
| **DNS Name** | klinematrix.com |
| **Purpose** | Ingress controller external IP |

**DNS Records** (Cloudflare):
```
A     klinematrix.com     → 4.217.130.195
A     www.klinematrix.com → 4.217.130.195
```

---

## Kubernetes Resources (klinematrix-test namespace)

### Deployments

| Name | Replicas | Image | Status |
|------|----------|-------|--------|
| **backend** | 1/1 | klinematrix/backend:test-v0.3.0 | ✅ Running |
| **frontend** | 1/1 | klinematrix/frontend:test-v0.3.0 | ✅ Running |
| **redis** | 1/1 | redis:7.2-alpine | ✅ Running |

### Services

| Name | Type | Port | Target |
|------|------|------|--------|
| **backend-service** | ClusterIP | 8000 | backend:8000 |
| **frontend-service** | ClusterIP | 80 | frontend:80 |
| **redis-service** | ClusterIP | 6379 | redis:6379 |

### Ingress

| Name | Host | Path | Backend |
|------|------|------|---------|
| **klinematrix-ingress** | klinematrix.com | /api | backend-service:8000 |
|  | klinematrix.com | / | frontend-service:80 |
|  | www.klinematrix.com | /api | backend-service:8000 |
|  | www.klinematrix.com | / | frontend-service:80 |

**TLS Certificate**:
- Issuer: Let's Encrypt (cert-manager)
- Secret: klinematrix-tls
- Auto-renewal: Enabled

### ConfigMaps

| Name | Purpose |
|------|---------|
| **alibaba-config** | Alibaba DashScope (LLM) configuration |
| **redis-config** | Redis server configuration |

### Secrets

| Name | Type | Keys |
|------|------|------|
| **app-secrets** | Opaque | jwt-secret-key, mongodb-url, dashscope-api-key, tencent-secret-id, tencent-secret-key |
| **redis-auth** | Opaque | password |
| **klinematrix-tls** | kubernetes.io/tls | tls.crt, tls.key |

### External Secrets

| Name | Status | Vault |
|------|--------|-------|
| **app-secrets** | ⚠️ SecretSyncedError | klinematrix-test-kv |

**Note**: External Secrets Operator currently not working. Using manual secret creation as workaround.

---

## Resource Organization

### Naming Convention

```
Infrastructure (cannot rename):
├── ACR: financialAgent
├── Cosmos DB: financialagent-mongodb
└── AKS: FinancialAgent-AKS

Application Resources (new naming):
├── Namespace: klinematrix-test
├── Images: klinematrix/backend, klinematrix/frontend
├── Database: klinematrix_test
└── Key Vault: klinematrix-test-kv
```

### Why Mixed Naming?

- **Infrastructure**: Azure resource names are globally unique and immutable (cannot rename)
- **Budget**: Keeping existing infrastructure saves costs (~$50-100/month)
- **Solution**: Use new naming inside old infrastructure (images in ACR, databases in Cosmos DB)

---

## Environment Configuration

### Backend Environment Variables

```yaml
ENVIRONMENT: test
LOG_LEVEL: INFO
ENABLE_DEBUG: false
EMAIL_BYPASS_MODE: false
CORS_ORIGINS: '["https://klinematrix.com"]'
MONGODB_DATABASE: klinematrix_test
REDIS_URL: redis://redis-service:6379/0
TENCENT_SES_REGION: ap-guangzhou
TENCENT_SES_FROM_EMAIL: noreply@klinematrix.com
TENCENT_SES_FROM_NAME: Klinematrix
TENCENT_SES_TEMPLATE_ID: 37066
```

### Frontend Environment Variables

```yaml
REACT_APP_DEBUG: false
REACT_APP_API_URL: https://klinematrix.com/api
```

---

## Resource Limits

### Backend (10 beta users)

| Resource | Request | Limit |
|----------|---------|-------|
| Memory | 256Mi | 512Mi |
| CPU | 100m | 500m |

### Frontend

| Resource | Request | Limit |
|----------|---------|-------|
| Memory | 128Mi | 256Mi |
| CPU | 50m | 200m |

### Redis

| Resource | Request | Limit |
|----------|---------|-------|
| Memory | 64Mi | 256Mi |
| CPU | 50m | 200m |

---

## Access & Health Checks

### Application URLs

- **Frontend**: https://klinematrix.com
- **Backend API**: https://klinematrix.com/api
- **Health Check**: https://klinematrix.com/api/health

### Health Check Response

```json
{
  "status": "ok",
  "environment": "test",
  "version": "0.3.0",
  "timestamp": "2025-01-20T00:00:00Z",
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

### Kubernetes Access

```bash
# Get resources
kubectl get all -n klinematrix-test

# View logs
kubectl logs -f deployment/backend -n klinematrix-test
kubectl logs -f deployment/frontend -n klinematrix-test

# Execute commands
kubectl exec -it deployment/backend -n klinematrix-test -- bash

# Restart deployments
kubectl rollout restart deployment/backend -n klinematrix-test
kubectl rollout restart deployment/frontend -n klinematrix-test
```

---

## External Services

### 1. Alibaba Cloud DashScope

| Property | Value |
|----------|-------|
| **Service** | DashScope (Qwen LLM) |
| **Region** | cn-hangzhou |
| **Model** | qwen-vl-plus |
| **API Key** | Stored in Key Vault |

### 2. Tencent Cloud 邮件推送 (SES)

| Property | Value |
|----------|-------|
| **Service** | Simple Email Service (SES) |
| **Region** | ap-guangzhou |
| **From Address** | noreply@klinematrix.com |
| **From Name** | Klinematrix |
| **Template ID** | 37066 |
| **Status** | ✅ Configured |

**DNS Authentication** (Cloudflare):
```
TXT   _spf.klinematrix.com     → v=spf1 include:spf.qcloudmail.com ~all
CNAME _domainkey.klinematrix.com → <tencent-dkim-record>
TXT   _dmarc.klinematrix.com   → v=DMARC1; p=none; rua=mailto:dmarc@klinematrix.com
```

---

## Cost Breakdown (Monthly)

| Service | SKU/Tier | Estimated Cost |
|---------|----------|----------------|
| **AKS Nodes** | 2× Standard_D2ls_v5 | **$53** |
| Cosmos DB MongoDB | 400 RU/s shared throughput | $24 |
| Container Registry | Basic tier | $5 |
| Load Balancer + IPs | 2 public IPs | $8 |
| Log Analytics | Data ingestion | $5-10 |
| Key Vault | Standard | $0.03 |
| **Total** |  | **~$95-100/month** |

### Recent Cost Optimization (Oct 2025)

**Before optimization**: $148-153/month (4 nodes autoscaled)
**After optimization**: $95-100/month (2 nodes capped)
**Savings**: $53-58/month (35-38% reduction)

**Actions taken**:
1. Deleted duplicate deployments in default namespace (~640Mi freed)
2. Capped autoscaler: `az aks nodepool update --max-count 1` on both pools
3. Result: Stable 2-node configuration with proper resource headroom

See [Cost Optimization Guide](cost-optimization.md) for detailed analysis and monitoring procedures.

---

## Security

### Workload Identity

- **Service Account**: klinematrix-sa
- **Azure AD Integration**: Enabled
- **Key Vault Access**: Managed via Azure RBAC

### TLS/SSL

- **Certificate Provider**: Let's Encrypt
- **Management**: cert-manager (auto-renewal)
- **Force HTTPS**: Enabled

### Secrets Management

- **Key Vault**: All sensitive data stored in Azure Key Vault
- **No Secrets in Code**: ✅ Verified
- **No Secrets in Git**: ✅ Verified

---

## Troubleshooting

### Common Commands

```bash
# Check pod status
kubectl get pods -n klinematrix-test

# View pod logs
kubectl logs -f <pod-name> -n klinematrix-test

# Describe pod (events)
kubectl describe pod <pod-name> -n klinematrix-test

# Check secrets
kubectl get secret app-secrets -n klinematrix-test -o yaml

# Test backend locally
kubectl port-forward -n klinematrix-test deployment/backend 8000:8000
curl http://localhost:8000/api/health

# Check ingress
kubectl describe ingress klinematrix-ingress -n klinematrix-test
```

### Known Issues

1. **External Secrets Operator**: Not syncing from Key Vault
   - **Workaround**: Manual secret creation in Kubernetes
   - **Status**: Non-blocking, low priority

2. **Tencent SMTP Password**: Currently PLACEHOLDER
   - **Impact**: Email verification not working
   - **Action Required**: Add real password from Tencent dashboard

---

## Related Documentation

- [Migration Guide](MIGRATION_DEV_TO_TEST.md) - How we got here
- [Deployment Workflow](workflow.md) - How to deploy updates
- [Infrastructure Guide](infrastructure.md) - K8s architecture
- [Troubleshooting](../troubleshooting/) - Common issues

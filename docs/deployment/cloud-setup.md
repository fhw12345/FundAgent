# Cloud Infrastructure Setup

## Strategic Hybrid Cloud Architecture

### Azure Services (Core Platform)
- **AKS (Kubernetes)**: Container orchestration and application hosting
- **Cosmos DB (NoSQL)**: Primary database with MongoDB API compatibility
- **Azure AD B2C**: Authentication and user management service
- **Azure Monitor**: Observability and monitoring
- **Container Registry**: Docker image storage
- **Key Vault**: Secrets management

### Alibaba Cloud Services (AI & Storage)
- **Qwen-VL Model**: LLM inference for financial analysis
- **OSS (Object Storage)**: Chart storage and file management
- **DashScope API**: AI model access

### Third-Party Services
- **Cloudflare**: DNS management and domain registration (`klinematrix.com`)
- **Tencent Cloud SES**: Transactional email delivery service (replaces SendGrid)

### Rationale for Hybrid Approach
1. **Best-of-Breed Services**: Leverage Azure's enterprise Kubernetes platform with Alibaba's cutting-edge AI models
2. **Cost Optimization**: Use Alibaba Cloud's competitive pricing for storage and AI inference
3. **Geographic Distribution**: Azure for global reach, Alibaba for APAC/China market access
4. **Risk Mitigation**: Multi-cloud strategy reduces vendor lock-in
5. **Compliance**: Flexible data residency options

## Azure Environment

### Configuration Status
- **CLI Version**: 2.77.0+
- **Subscription**: Visual Studio Enterprise Subscription
- **Tenant**: Default Directory
- **Resource Group**: `FinancialAgent`

### Existing Resources

#### AKS Cluster: FinancialAgent-AKS
- **Location**: Korea Central
- **Kubernetes Version**: 1.32.6+
- **Status**: Running
- **Node Count**: 3 nodes (fixed) across 3 pools
- **Node Pools**:
  - agentpool: 1 × Standard_D2ls_v5 (2 vCPU, 4GB, System mode)
  - userpool: 1 × Standard_D2ls_v5 (2 vCPU, 4GB, User mode)
  - userpoolv2: 1 × Standard_E2_v3 (2 vCPU, 16GB, User mode, memory-optimized)
- **Features Enabled**:
  - Workload Identity (for secretless auth)
  - OIDC Issuer
  - Azure CNI networking
  - Autoscaler (capped at max-count=1 per pool)

#### Azure Monitor Stack
- **Workspace**: Azure Monitor Workspace
- **Prometheus Integration**: Enabled
- **Data Collection Rules**: Multiple DCRs configured
- **Alerting**: CPU/Memory thresholds configured
- **Rule Groups**: Node, Kubernetes, and UX recording rules

### Resources to Create

#### Cosmos DB
- **Account Name**: `financialagent-mongodb`
- **API**: MongoDB API (compatible)
- **Purpose**: Primary database for application data
- **Configuration**: Multi-region, auto-scaling

#### Azure Key Vault
- **Name**: `klinematrix-test-kv`
- **Purpose**: Centralized secret management
- **Secrets to Store**:
  - `mongodb-url`: Cosmos DB connection string
  - `dashscope-api-key`: Alibaba Cloud DashScope API key
  - `tencent-ses-secret-id`: Tencent Cloud SES credentials
  - `tencent-ses-secret-key`: Tencent Cloud SES credentials

#### Azure Container Registry (ACR)
- **Registry Name**: `financialAgent`
- **SKU**: Basic
- **Purpose**: Store Docker images for deployment

## Alibaba Cloud Environment

### Configuration Status
- **CLI Version**: 3.0.302+
- **Profile**: `dev` (active)
- **Region**: `cn-shanghai` (Primary), `cn-hangzhou` (AI Services)
- **User**: RAM user with programmatic access

### Existing Resources

#### MongoDB Instance (Optional - for migration)
- **Instance ID**: `dds-uf6aaefb2431c224`
- **Version**: MongoDB 8.0
- **Type**: Replica Set (3 nodes)
- **Status**: Running
- **Network**: VPC mode
- **Purpose**: Can be used as data migration source or backup

#### VPC Configuration
- **VPC ID**: `vpc-uf61bb584xp7lmixq645v`
- **CIDR Block**: `172.16.0.0/12`
- **Status**: Available
- **Purpose**: Network isolation for Alibaba Cloud resources

### Resources to Create

#### OSS (Object Storage Service)
- **Purpose**: Chart and file storage
- **Features**:
  - Multi-region replication
  - CDN integration for global delivery
  - Pre-signed URLs for secure access
  - Lifecycle policies for cost optimization

#### DashScope API Access
- **Model**: Qwen-VL-Plus (or latest)
- **Region**: cn-hangzhou
- **Purpose**: AI-powered chart interpretation and analysis
- **Configuration**:
  - API authentication
  - Rate limiting
  - Model inference caching

## Cross-Cloud Integration

### Network Connectivity
- **Option 1**: VPN Gateway between Azure VNet and Alibaba VPC
- **Option 2**: Public API endpoints with TLS encryption
- **Recommendation**: Start with Option 2 for simplicity, upgrade to VPN if needed

### Data Flow Architecture
```
User Request → Azure AKS → Backend Service
                    ↓
              ┌─────┴──────┐
              ↓            ↓
    Azure Cosmos DB    Alibaba OSS
              ↓            ↓
         (Data Store)  (File Storage)

Backend Service → Alibaba DashScope API
                     ↓
                (AI Analysis)
```

## Setup Instructions

### Azure Setup

#### 1. Create Cosmos DB
```bash
# Create Cosmos DB account with MongoDB API
az cosmosdb create \
  --name financialagent-mongodb \
  --resource-group FinancialAgent \
  --kind MongoDB \
  --locations regionName=KoreaCentral failoverPriority=0 \
  --default-consistency-level Session
```

#### 2. Create Azure Key Vault
```bash
# Create Key Vault
az keyvault create \
  --name klinematrix-test-kv \
  --resource-group FinancialAgent \
  --location koreacentral

# Enable Azure AD authentication
az keyvault update \
  --name klinematrix-test-kv \
  --resource-group FinancialAgent \
  --enable-rbac-authorization true
```

#### 3. Configure AKS
```bash
# Get AKS credentials
az aks get-credentials \
  --resource-group FinancialAgent \
  --name FinancialAgent-AKS

# Enable workload identity
az aks update \
  --resource-group FinancialAgent \
  --name FinancialAgent-AKS \
  --enable-workload-identity \
  --enable-oidc-issuer

# Attach ACR
az aks update \
  --resource-group FinancialAgent \
  --name FinancialAgent-AKS \
  --attach-acr financialAgent
```

#### 4. Install Kubernetes Add-ons

**External Secrets Operator:**
```bash
helm repo add external-secrets https://charts.external-secrets.io
helm install external-secrets external-secrets/external-secrets \
  --namespace external-secrets-system --create-namespace
```

**cert-manager:**
```bash
helm repo add jetstack https://charts.jetstack.io
helm install cert-manager jetstack/cert-manager \
  --namespace cert-manager --create-namespace \
  --set crds.enabled=true
```

**Nginx Ingress:**
```bash
helm repo add ingress-nginx https://kubernetes.github.io/ingress-nginx
helm install nginx-ingress ingress-nginx/ingress-nginx \
  --namespace ingress-nginx --create-namespace
```

#### 5. Store Secrets in Key Vault
```bash
# Store MongoDB connection string
MONGODB_URL=$(az cosmosdb keys list \
  --name financialagent-mongodb \
  --resource-group FinancialAgent \
  --type connection-strings \
  --query "connectionStrings[0].connectionString" -o tsv)

az keyvault secret set \
  --vault-name klinematrix-test-kv \
  --name mongodb-url \
  --value "$MONGODB_URL"

# Store Alibaba DashScope API key (get from Alibaba Cloud Console)
az keyvault secret set \
  --vault-name klinematrix-test-kv \
  --name dashscope-api-key \
  --value "your-dashscope-api-key"
```

### Alibaba Cloud Setup

#### 1. Create OSS Bucket
```bash
# Using Alibaba Cloud CLI
aliyun oss mb oss://financial-agent-charts \
  --region cn-shanghai \
  --acl private

# Configure CORS for browser access
aliyun oss cors-put \
  --bucket financial-agent-charts \
  --cors-configuration file://oss-cors-config.json
```

**oss-cors-config.json:**
```json
{
  "CORSRule": [
    {
      "AllowedOrigin": ["*"],
      "AllowedMethod": ["GET", "HEAD"],
      "AllowedHeader": ["*"],
      "MaxAgeSeconds": 3600
    }
  ]
}
```

#### 2. Configure DashScope API Access
```bash
# Get API key from Alibaba Cloud Console
# Model Studio → API Keys → Create New Key

# Test API access
curl -X POST https://dashscope.cn-hangzhou.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation \
  -H "Authorization: Bearer your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "qwen-vl-plus",
    "input": {
      "messages": [
        {
          "role": "user",
          "content": [
            {"text": "Hello"}
          ]
        }
      ]
    }
  }'
```

## Cost Estimates

**Current Production Costs** (as of October 2025):
- **AKS**: $237/month (3 nodes: agentpool + userpool + userpoolv2, autoscaler capped)
- **Cosmos DB**: ~$200-500/month (depends on usage)
- **Alibaba Cloud OSS/DashScope**: ~$60-250/month (pay-per-use)
- **Total**: ~$500-1000/month

**Historical Context**:
- Before October 2025 migration: $280/month (4 × Standard_B2s nodes, uncapped autoscaler)
- After migration: $237/month (15% savings, cost-controlled autoscaling)

See [Cost Optimization Guide](cost-optimization.md) for detailed breakdown and monitoring procedures.

## Security Configuration

### Azure Security
- **Access Method**: Azure AD user authentication
- **Permissions**: RBAC with minimal permissions
- **Network**: AKS with Azure CNI, Network Policies
- **Encryption**: TLS in transit, encryption at rest for Cosmos DB
- **Secrets**: Stored in Key Vault, accessed via Workload Identity

### Alibaba Cloud Security
- **Access Method**: RAM user with programmatic access
- **Permissions**: Minimal required permissions
- **Network**: VPC isolation
- **Encryption**: OSS encryption at rest, HTTPS for API calls
- **Secrets**: API keys stored in Azure Key Vault

## Monitoring & Observability

### Azure Monitor
- **Metrics**: AKS cluster metrics, container insights
- **Logs**: Application logs, Kubernetes events
- **Alerts**: CPU/memory thresholds, pod failures
- **Dashboards**: Pre-built and custom dashboards

### Application Monitoring
- **LangSmith**: Agent execution traces
- **Structured Logging**: JSON logs with correlation IDs
- **Health Checks**: Kubernetes liveness/readiness probes
- **Custom Metrics**: Prometheus metrics endpoint

## Disaster Recovery

### Backup Strategy
- **Cosmos DB**: Automatic continuous backups
- **OSS**: Cross-region replication
- **Kubernetes**: GitOps approach (all manifests in git)
- **Secrets**: Backed up in Key Vault with soft-delete enabled

### Recovery Procedures
1. **Database Failure**: Restore from Cosmos DB point-in-time backup
2. **Storage Failure**: Failover to replicated OSS bucket
3. **AKS Cluster Failure**: Redeploy from manifests to new cluster
4. **Complete Region Failure**: Deploy to secondary region

## DNS and Email Configuration

### Cloudflare DNS Setup

#### Domain Registration
1. **Register domain** at https://www.cloudflare.com/products/registrar/
   - Domain: `klinematrix.com`
   - Cost: ~$9/year (at-cost pricing)
   - Includes: Free WHOIS privacy, automatic DNS management

#### DNS Records Configuration
Add the following records in Cloudflare DNS dashboard:

**Application Access:**
```
Type: A
Name: @
Content: 4.217.130.195
Proxy: DNS only (gray cloud)

Type: A
Name: www
Content: 4.217.130.195
Proxy: DNS only (gray cloud)
```

**Email Authentication (Tencent Cloud SES):**
```
Type: TXT
Name: @
Content: v=spf1 include:spf.qcloud.com ~all
TTL: Auto

Type: TXT
Name: _dmarc
Content: v=DMARC1; p=none; rua=mailto:dmarc@klinematrix.com
TTL: Auto

# Domain verification (obtain from Tencent Cloud Console)
Type: CNAME
Name: tencent-verify-<verification-code>
Target: verify.qcloud.com
Proxy: DNS only
```

### Tencent Cloud SES (Simple Email Service) Setup

**Status**: ✅ Currently in use for production email sending

#### Overview
Tencent Cloud SES is used for transactional emails (password reset, verification codes) instead of SendGrid.

**Key Features**:
- API-based email sending
- Authentication via SecretId/SecretKey
- Integrated with Alibaba Cloud infrastructure
- See [Fixed Bugs - Tencent SES Authentication](../troubleshooting/fixed-bugs.md) for implementation details

#### Configuration in Kubernetes

**Stored in Azure Key Vault** (synced via External Secrets Operator):
```bash
# Secret name: tencent-ses-credentials
# Fields:
# - TENCENT_SECRET_ID
# - TENCENT_SECRET_KEY
```

**Environment variables** (set in backend deployment):
```yaml
env:
- name: TENCENT_SECRET_ID
  valueFrom:
    secretKeyRef:
      name: tencent-ses-credentials
      key: TENCENT_SECRET_ID
- name: TENCENT_SECRET_KEY
  valueFrom:
    secretKeyRef:
      name: tencent-ses-credentials
      key: TENCENT_SECRET_KEY
```

#### Test Environment Bypass

Test environment uses `EMAIL_BYPASS_MODE=true` to skip actual email sending during development:
```yaml
env:
- name: EMAIL_BYPASS_MODE
  value: "true"
```

This allows testing password reset flows without sending real emails.

#### Production Setup Checklist

**If setting up fresh Tencent SES credentials:**

1. **Obtain Tencent Cloud credentials**
   - Log in to Tencent Cloud Console
   - Navigate to CAM (Cloud Access Management)
   - Create API key for SES service
   - Note down `SecretId` and `SecretKey`

2. **Store in Azure Key Vault**
   ```bash
   az keyvault secret set \
     --vault-name klinematrix-test-kv \
     --name tencent-ses-credentials \
     --value '{"TENCENT_SECRET_ID":"xxx","TENCENT_SECRET_KEY":"yyy"}'
   ```

3. **Configure External Secrets to sync**
   ```yaml
   # Already configured in .pipeline/k8s/base/external-secrets.yaml
   apiVersion: external-secrets.io/v1beta1
   kind: ExternalSecret
   metadata:
     name: tencent-ses-credentials
   spec:
     target:
       name: tencent-ses-credentials
   ```

4. **Verify secret sync**
   ```bash
   kubectl get secret tencent-ses-credentials -n klinematrix-test
   kubectl describe externalsecret tencent-ses-credentials -n klinematrix-test
   ```

#### Email Authentication (Future Enhancement)

**Note**: Currently using basic API authentication. For production-grade email delivery, consider:
- **SPF**: Authorize Tencent's mail servers for your domain
- **DKIM**: Add cryptographic signatures to emails
- **DMARC**: Set policy for authentication failures
- **Purpose**: Improves deliverability, prevents spam classification

**Alternative**: If Tencent SES has deliverability issues, alternative email providers (AWS SES, Mailgun) can be configured with similar API integration patterns.

#### Troubleshooting

**Common Issues**:
- **Invalid credentials**: Check Azure Key Vault secret format
- **External Secrets not syncing**: Verify workload identity configuration
- **Emails not sending in test**: Verify `EMAIL_BYPASS_MODE=true` is set

See [Troubleshooting - Fixed Bugs](../troubleshooting/fixed-bugs.md) for detailed password reset flow debugging.

## Quick Start Commands

### Initial Setup (One-time)
```bash
# Run Azure setup script
./.pipeline/scripts/setup-azure-dev.sh

# Deploy to Kubernetes
kubectl apply -k .pipeline/k8s/overlays/dev/

# Verify deployment
kubectl get pods -n klinematrix-test
```

### Day-to-Day Operations
```bash
# Check status
kubectl get pods -n klinematrix-test

# View logs
kubectl logs -f deployment/backend -n klinematrix-test

# Update deployment
kubectl apply -k .pipeline/k8s/overlays/dev/

# Health check
curl https://klinematrix.com/api/health
```

# Langfuse Production Deployment - Alibaba Cloud Strategy

> **Target**: 10 users | **Budget**: <$15/month | **Platform**: K8s + Aliyun Managed Services
> **Last Updated**: 2025-10-24 | **Status**: ⚠️ **ACTION REQUIRED - PolarDB Database Creation**

---

## 🚨 CRITICAL: Manual Action Required

**Langfuse is currently DOWN (503) due to missing PolarDB database.**

### What You Need to Do

Create the `langfuse` database manually via Alibaba Cloud Console:

1. **Login**: https://polardb.console.aliyun.com/
2. **Region**: Switch to **华东1 (杭州) / Hangzhou**
3. **Cluster**: Find `pc-bp141ar06fos11131`
4. **Create Database**:
   - Name: `langfuse`
   - Character Set: `UTF8`
   - Owner: `km_admin`
5. **Restart Langfuse**:
   ```bash
   kubectl delete pod -l app=langfuse-server -n klinematrix-test
   kubectl delete pod -l app=langfuse-worker -n klinematrix-test
   ```

**See [Manual Database Creation](#manual-database-creation) section below for detailed steps.**

---

## Current Deployment Status (2025-10-24)

| Component | Status | Details |
|-----------|--------|---------|
| **Infrastructure** |||
| PolarDB | ✅ Running | `aliyun-polardb-klinematrix.rwlb.rds.aliyuncs.com:5432` |
| OSS Bucket | ✅ Working | `langfuse-events-prod` (HTTP endpoint) |
| Azure Workload Identity | ✅ Complete | Managed identity + federated credential configured |
| Azure Key Vault | ✅ Synced | All secrets stored, RBAC granted |
| **Kubernetes** |||
| Namespace | ✅ Ready | klinematrix-test |
| ClickHouse | ✅ Ready | Database created (empty, awaiting schema) |
| Redis | ✅ Running | Shared Redis, DB 1 allocated for Langfuse |
| Secrets | ✅ Manual | `langfuse-secrets` created (OSS credentials fixed) |
| External Secrets | ⚠️ Caching | SecretStore: Valid, ExternalSecrets: old errors |
| **Langfuse** |||
| Server | ❌ **CrashLoopBackOff** | Can't connect to PolarDB (database doesn't exist) |
| Worker | ❌ Not Running | Depends on server startup |
| **Blockers** |||
| PolarDB Database | ❌ **CRITICAL** | **`langfuse` database needs manual creation** |

### What's Been Completed

✅ **OSS Storage** - HTTP endpoint workaround implemented (see `docs/deployment/langfuse-oss-http-workaround.md`)
- Issue: boto3 aws-chunked encoding incompatible with OSS HTTPS
- Solution: Using `http://oss-cn-hangzhou.aliyuncs.com`
- Security: Documented tradeoffs (ClickHouse primary, OSS backup only)

✅ **Azure Workload Identity** - Complete OIDC federation setup
- Managed identity: `klinematrix-identity` (03e41e5f-f062-45b2-9094-367e406c30a6)
- Federated credential: AKS ↔ Azure AD
- Key Vault RBAC: Granted "Key Vault Secrets User" role
- ServiceAccount: Updated with actual tenant/client IDs

✅ **ClickHouse** - Database ready for schema initialization
- Dropped old database
- Recreated empty `langfuse` database
- Will auto-initialize tables when Langfuse connects to PolarDB

❌ **PolarDB Database** - Password authentication failures blocking automated creation
- Multiple CLI attempts failed
- Password has special character `=` causing escaping issues
- **Requires manual creation via Alibaba Cloud Console**

---

## Manual Database Creation

### Why Manual Creation Is Required

All automated attempts to create the `langfuse` database via `kubectl`/`psql` have failed with:
```
Password authentication failed for user
```

**Root Causes**:
1. Password contains special character `=` at the end
2. URL encoding and shell escaping attempts all failed
3. Alibaba Cloud PolarDB CLI limitations

**Solution**: Create database manually via web console (takes 2 minutes).

### Step-by-Step Instructions

#### 1. Login to Alibaba Cloud Console

- URL: https://polardb.console.aliyun.com/
- **Use your main Alibaba Cloud account** (not RAM sub-user)

#### 2. Select Correct Region

- **Region selector** in top navigation bar
- **Switch to: 华东1 (杭州) / Hangzhou**
- ⚠️ Common mistake: Wrong region = cluster not visible

#### 3. Find Your PolarDB Cluster

- Look for **Cluster ID**: `pc-bp141ar06fos11131`
- Or search for endpoint: `aliyun-polardb-klinematrix.rwlb.rds.aliyuncs.com`
- Click on the cluster name to open details page

#### 4. Navigate to Databases

- Left sidebar menu
- Click: **数据库管理** (Database Management)
- You should see a list of existing databases (if any)

#### 5. Create Database

- Click **创建数据库** (Create Database) button
- **Database Name**: `langfuse`
- **Character Set**: `UTF8`
- **Owner**: `km_admin` (verify this user exists first)
- Click **确定** (Confirm) to create

#### 6. Verify Database Created

You should see `langfuse` in the database list.

#### 7. Restart Langfuse Pods

Once the database exists:

```bash
# Delete pods to trigger restart with new database
kubectl delete pod -l app=langfuse-server -n klinematrix-test
kubectl delete pod -l app=langfuse-worker -n klinematrix-test

# Monitor server startup (should see migrations running)
kubectl logs -f deployment/langfuse-server -n klinematrix-test
```

**Success Indicators**:
```
Prisma schema loaded from packages/shared/prisma/schema.prisma
346 migrations found in prisma/migrations
Applying migration `001_initial_migration`...
...
No pending migrations to apply
✓ Ready in 12.3s
Server listening on port 3000
```

#### 8. Verify ClickHouse Tables Created

```bash
kubectl exec statefulset/langfuse-clickhouse -n klinematrix-test -- \
  clickhouse-client --query "SHOW TABLES FROM langfuse"
```

Expected output:
```
event_log
observations
scores
traces
```

#### 9. Test Langfuse UI

```bash
# Should return 200 OK (not 503)
curl -I https://monitor.klinematrix.com

# Or visit in browser
open https://monitor.klinematrix.com
```

### Troubleshooting After Database Creation

**If server still crashes**:

1. **Check database owner**:
   - Database might exist but `km_admin` doesn't have permissions
   - Grant ownership: `GRANT ALL ON DATABASE langfuse TO km_admin;`

2. **Verify password in secret**:
   ```bash
   kubectl get secret langfuse-secrets -n klinematrix-test -o jsonpath='{.data.polardb-password}' | base64 -d
   ```
   Should match Key Vault: `rhFxS588onhn5yQkohnwsTixvpCulsh359xVQV011eI=`

3. **Check firewall/whitelist**:
   - PolarDB console → Data Security → Whitelist Settings
   - Ensure AKS node IPs are whitelisted

---

## Executive Summary

**Recommended Approach**: Self-hosted on K8s + Aliyun PolarDB + OSS

**Estimated Monthly Cost**: ~$8-12/month (CNY ¥55-80)
- Aliyun PolarDB PostgreSQL Serverless: ~$6-8/month (¥40-55, pay-per-use)
- Aliyun OSS (Object Storage): ~$0.50-1/month (¥3-7, minimal usage)
- Redis in K8s: $0 (use existing Redis, separate database)
- ClickHouse in K8s: $0 (uses existing cluster capacity)
- Langfuse Server/Worker: $0 (uses existing cluster capacity)

**Access Point**: `https://klinematrix.com/monitor` (path-based routing on existing domain)

**Why This Approach**:
- ✅ **Lowest cost option**: PolarDB Serverless charges only for actual usage
- ✅ Leverage ALL existing K8s infrastructure (Redis, ingress, cluster)
- ✅ Aliyun native services (better performance in China, if applicable)
- ✅ S3-compatible OSS (no code changes needed)
- ✅ No separate subdomain needed (path-based routing)
- ✅ Can scale to 50-100 users without architecture changes
- ✅ **~85% cost savings vs Langfuse Cloud** ($10/mo vs $59/mo)

---

## Option Comparison

| Option | Monthly Cost (USD) | Monthly Cost (CNY) | Pros | Cons | Recommendation |
|--------|-------------------|-------------------|------|------|----------------|
| **Langfuse Cloud (SaaS)** | $0-59 | ¥0-420 | Zero ops, instant setup | Data external, limited free tier | ❌ Not for production |
| **Azure (Postgres+Blob)** | $13-15 | ¥90-105 | Azure-native | Higher cost than Aliyun | ⚠️ More expensive |
| **Aliyun (PolarDB+OSS)** | $8-12 | ¥55-80 | Lowest cost, serverless | Shared Redis risk | ✅ **RECOMMENDED** |

---

## Architecture Design

### Deployment Topology

```
┌──────────────────────────────────────────────────────────────────┐
│  Kubernetes Cluster (AKS/ACK/Self-hosted)                        │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │  Namespace: klinematrix-test                               │  │
│  │                                                             │  │
│  │  ┌─────────────────┐  ┌─────────────────┐                │  │
│  │  │  Backend Pod    │  │  Langfuse Server│                │  │
│  │  │  (FastAPI)      │──▶│  (Next.js)      │                │  │
│  │  │  + Langfuse SDK │  │  /monitor path  │                │  │
│  │  └─────────────────┘  └─────────────────┘                │  │
│  │           │                     │                          │  │
│  │           │            ┌─────────────────┐                │  │
│  │           │            │  Langfuse Worker│                │  │
│  │           │            │  (BullMQ jobs)  │                │  │
│  │           │            └─────────────────┘                │  │
│  │           │                     │                          │  │
│  │  ┌─────────────────┐  ┌────────┴─────────┐               │  │
│  │  │  ClickHouse     │  │  Redis (Shared)  │               │  │
│  │  │  (StatefulSet)  │◀─│  DB 0: Business  │               │  │
│  │  │  2GB PVC        │  │  DB 1: Langfuse  │               │  │
│  │  └─────────────────┘  └──────────────────┘               │  │
│  │                               │                            │  │
│  │  ┌──────────────────────────────────────────────────────┐ │  │
│  │  │  Ingress (klinematrix.com)                           │ │  │
│  │  │  ├─ /          → Frontend                            │ │  │
│  │  │  ├─ /api       → Backend                             │ │  │
│  │  │  └─ /monitor   → Langfuse Server (path rewrite)     │ │  │
│  │  └──────────────────────────────────────────────────────┘ │  │
│  └────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────┘
                  │                            │
         ┌────────┴────────┐          ┌───────┴──────────┐
         │  Aliyun PolarDB │          │  Aliyun OSS      │
         │  PostgreSQL     │          │  (S3-compatible) │
         │  Serverless     │          │  langfuse-events │
         │  (Pay-per-use)  │          │  bucket          │
         └─────────────────┘          └──────────────────┘
           ~$6-8/mo (~¥40-55)          ~$0.50-1/mo (~¥3-7)
```

**Key Design Decisions**:
1. ✅ **Shared Redis**: Use existing Redis with DB 1 for Langfuse (DB 0 for business)
2. ✅ **Path-based routing**: `/monitor` instead of separate subdomain
3. ✅ **Aliyun managed services**: PolarDB Serverless + OSS (lowest cost)
4. ✅ **S3-compatible OSS**: No code changes, uses standard S3 SDK

### Resource Specifications (10 Users)

| Component | CPU Request | Memory Request | CPU Limit | Memory Limit | Storage |
|-----------|-------------|----------------|-----------|--------------|---------|
| Langfuse Server | 100m | 256Mi | 500m | 512Mi | - |
| Langfuse Worker | 50m | 128Mi | 250m | 256Mi | - |
| ClickHouse | 200m | 512Mi | 1000m | 2Gi | 2GB PVC |
| **Total In-Cluster** | **350m** | **896Mi** | **1750m** | **~3Gi** | **2GB** |

**Existing Node Capacity**: 2 nodes × Standard_B2s (2 vCPU, 4GB RAM each) = 4 vCPU, 8GB RAM total
**Current Usage**: Backend + Frontend + MongoDB + Redis ≈ 2-3 vCPU, 4-5GB RAM
**After Langfuse**: ≈ 2.5-3.5 vCPU, 5-6GB RAM (still fits in 2 nodes) ✅

---

## Implementation Plan

### Phase 1: Aliyun Managed Services Setup (Week 1)

#### 1.1 Aliyun PolarDB PostgreSQL Serverless

**Why**: Fully managed, serverless (pay-per-use), automatic scaling, minimal cost for 10 users.

**Sizing for 10 users**:
- Edition: Serverless (按量付费 - pay-as-you-go)
- Compute Units (CU): 0.5-2 CU (auto-scales based on load)
- Storage: 20GB (grows automatically, pay for usage)
- Backup retention: 7 days
- Cost: ~¥40-55/month (~$6-8, only charged when database is active)

**Key Benefits**:
- 💰 **Ultra-low cost**: Serverless = no idle charges, perfect for 10 users
- 🚀 **Auto-scaling**: Scales from 0.5 to 2 CU automatically
- 🔒 **Fully managed**: Automatic backups, patches, monitoring
- ⚡ **Fast**: POLARDB native storage, faster than standard RDS

**Provisioning via Aliyun Console**:
1. Login to Aliyun Console → PolarDB → Create Instance
2. **Edition**: Serverless (Serverless 弹性版)
3. **Region**: Same as your K8s cluster (e.g., cn-hangzhou, ap-southeast-1)
4. **Database Engine**: PostgreSQL 15 (compatible with Langfuse)
5. **Compute Units**: 0.5-2 CU (recommended for 10 users)
6. **Storage**: Start with 20GB
7. **Network**: VPC (same VPC as K8s cluster if possible, or public access)
8. **Whitelist**: Add your K8s cluster's public IP or VPC CIDR

**Provisioning via Aliyun CLI** (optional):
```bash
# Set variables
REGION="cn-hangzhou"  # or your preferred region
DB_CLUSTER_ID="pc-langfuse-prod"
DB_NAME="langfuse"
DB_ADMIN_USER="langfuseadmin"
DB_ADMIN_PASSWORD="<generate-secure-password>"  # 8-32 chars

# Create PolarDB Serverless cluster
aliyun polardb CreateDBCluster \
  --RegionId $REGION \
  --DBType PostgreSQL \
  --DBVersion 15 \
  --DBNodeClass polar.pg.x2.medium.sc \
  --PayType Serverless \
  --ServerlessType AgileServerless \
  --ScaleMin 0.5 \
  --ScaleMax 2 \
  --ClusterNetworkType VPC \
  --DBClusterDescription "Langfuse Observability"

# Get cluster endpoint after creation
aliyun polardb DescribeDBClusterEndpoints \
  --DBClusterId $DB_CLUSTER_ID

# Create database
aliyun polardb CreateDatabase \
  --DBClusterId $DB_CLUSTER_ID \
  --DBName $DB_NAME \
  --CharacterSetName UTF8

# Add whitelist (K8s cluster IP range)
aliyun polardb ModifyDBClusterAccessWhitelist \
  --DBClusterId $DB_CLUSTER_ID \
  --SecurityIps "1.2.3.4/32"  # Replace with your K8s cluster public IP
```

**Connection String** (store in secret):
```
postgresql://langfuseadmin:<password>@pc-langfuse-prod.pg.rds.aliyuncs.com:5432/langfuse?sslmode=require

# Format: postgresql://USER:PASSWORD@ENDPOINT:PORT/DATABASE?sslmode=require
# Endpoint example: pc-xxxxx.pg.rds.aliyuncs.com (get from console)
```

**Cost Estimate** (10 users, low activity):
- **Compute**: ~0.5 CU average × ¥0.17/CU/hour × 720 hours = ¥61/month (~$9)
- **Storage**: 20GB × ¥0.0006/GB/hour × 720 hours = ¥8.6/month (~$1.2)
- **Backup**: 20GB × ¥0.0003/GB/hour × 720 hours = ¥4.3/month (~$0.6)
- **Total**: ~¥40-55/month (~$6-8) with actual usage patterns

---

#### 1.2 Configure Shared Redis (In-Cluster)

**Why**: Reuse existing Redis deployment, no external cost, separate database for isolation.

**Redis Database Allocation**:
- **Database 0**: Business logic (current usage - cache, sessions, etc.)
- **Database 1**: Langfuse queue management (BullMQ worker jobs)

**Verification**:
```bash
# Check existing Redis deployment
kubectl get deployment redis -n klinematrix-test

# Verify Redis is accessible
kubectl exec -it deployment/redis -n klinematrix-test -- redis-cli ping
# Should return: PONG

# Test database switching
kubectl exec -it deployment/redis -n klinematrix-test -- redis-cli
> SELECT 1
> PING
> EXIT
```

**Connection String** (for Langfuse):
```
redis://redis:6379/1
# Format: redis://<service-name>:<port>/<database-number>
# Database 1 ensures isolation from business logic (DB 0)
```

**Pros**:
- ✅ Zero cost (no Azure Redis)
- ✅ Faster (no network egress)
- ✅ Simple management

**Cons**:
- ⚠️ Shared failure domain (if Redis crashes, both business + observability affected)
- ⚠️ Resource contention (unlikely with 10 users, Langfuse queue is lightweight)

**Mitigation**:
- Set memory limits on Langfuse worker to prevent Redis memory exhaustion
- Observability is non-critical (can afford downtime without business impact)
- Consider dedicated Redis instance if load increases >50 users

---

#### 1.3 Aliyun OSS (Object Storage Service)

**Why**: Langfuse v3 requires S3-compatible storage for event persistence (mandatory). OSS is fully S3-compatible.

**Sizing for 10 users**:
- Storage: ~1-5GB/month (depends on trace volume)
- Transactions: Minimal (mostly PUT operations)
- Cost: ~¥3-7/month (~$0.50-1) including storage + requests

**Provisioning via Aliyun Console**:
1. Login to Aliyun Console → OSS → Buckets → Create Bucket
2. **Bucket Name**: `langfuse-events-prod` (globally unique)
3. **Region**: Same as PolarDB and K8s cluster
4. **Storage Class**: Standard (标准存储)
5. **Access Control**: Private (私有)
6. **Versioning**: Enable (recommended for production)
7. **Server-Side Encryption**: Enable (AES256 or KMS)

**Provisioning via Aliyun CLI** (optional):
```bash
# Set variables
REGION="oss-cn-hangzhou"  # OSS region endpoint
BUCKET_NAME="langfuse-events-prod"

# Create bucket
aliyun oss mb oss://$BUCKET_NAME \
  --region $REGION \
  --storage-class Standard \
  --acl private

# Enable versioning
aliyun oss bucket-versioning --method put oss://$BUCKET_NAME enabled

# Enable server-side encryption
aliyun oss bucket-encryption --method put oss://$BUCKET_NAME \
  --sse-algorithm AES256
```

**Get Access Credentials**:
1. Aliyun Console → RAM → Users → Create User (or use existing)
2. **User Name**: `langfuse-oss-user`
3. **Access Method**: Programmatic Access (获取 AccessKey)
4. **Permissions**: Grant OSS access to bucket `langfuse-events-prod`
   - Policy: `AliyunOSSFullAccess` (or custom policy for specific bucket)
5. **Save AccessKey ID and AccessKey Secret** (cannot retrieve later)

**Custom RAM Policy** (recommended, least privilege):
```json
{
  "Version": "1",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "oss:PutObject",
        "oss:GetObject",
        "oss:DeleteObject",
        "oss:ListObjects"
      ],
      "Resource": [
        "acs:oss:*:*:langfuse-events-prod/*"
      ]
    }
  ]
}
```

**S3-compatible Configuration** (for Langfuse):
- **Endpoint**: `https://oss-cn-hangzhou.aliyuncs.com` (replace region as needed)
- **Bucket**: `langfuse-events-prod`
- **Access Key ID**: Your RAM user AccessKey ID
- **Access Key Secret**: Your RAM user AccessKey Secret
- **Region**: `cn-hangzhou` (or your chosen region)
- **Force Path Style**: `true` (required for OSS S3 compatibility)

**Cost Estimate** (10 users, 2GB storage, 10k requests/month):
- **Storage**: 2GB × ¥0.12/GB/month = ¥0.24/month (~$0.03)
- **Requests (PUT)**: 10,000 × ¥0.01/10k requests = ¥0.01/month (~$0.001)
- **Requests (GET)**: 50,000 × ¥0.01/10k requests = ¥0.05/month (~$0.007)
- **Traffic (Public)**: 1GB × ¥0.50/GB = ¥0.50/month (~$0.07)
- **Total**: ~¥3-7/month (~$0.50-1) depending on access patterns

---

#### 1.4 Store Secrets Securely

**Options** (choose based on your setup):

##### Option A: Kubernetes Secrets (Simple, built-in)

```bash
# Create namespace-specific secret
kubectl create secret generic langfuse-secrets \
  --namespace klinematrix-test \
  --from-literal=postgres-connection-string='postgresql://langfuseadmin:<password>@pc-xxxxx.pg.rds.aliyuncs.com:5432/langfuse?sslmode=require' \
  --from-literal=s3-access-key='<aliyun-ram-access-key-id>' \
  --from-literal=s3-secret-key='<aliyun-ram-access-key-secret>' \
  --from-literal=nextauth-secret="$(openssl rand -base64 32)" \
  --from-literal=salt="$(openssl rand -base64 32)"
```

##### Option B: Azure Key Vault + External Secrets Operator (if using AKS)

```bash
KEY_VAULT_NAME="financial-agent-kv"  # Your existing Key Vault

# PolarDB connection string
az keyvault secret set \
  --vault-name $KEY_VAULT_NAME \
  --name langfuse-postgres-connection-string \
  --value "postgresql://langfuseadmin:<password>@pc-xxxxx.pg.rds.aliyuncs.com:5432/langfuse?sslmode=require"

# Aliyun OSS credentials
az keyvault secret set \
  --vault-name $KEY_VAULT_NAME \
  --name langfuse-s3-access-key \
  --value "<aliyun-ram-access-key-id>"

az keyvault secret set \
  --vault-name $KEY_VAULT_NAME \
  --name langfuse-s3-secret-key \
  --value "<aliyun-ram-access-key-secret>"

# Langfuse application secrets
az keyvault secret set \
  --vault-name $KEY_VAULT_NAME \
  --name langfuse-nextauth-secret \
  --value "$(openssl rand -base64 32)"

az keyvault secret set \
  --vault-name $KEY_VAULT_NAME \
  --name langfuse-salt \
  --value "$(openssl rand -base64 32)"
```

##### Option C: ACK Secrets Manager (if using Alibaba ACK)

If using Alibaba Cloud Container Service for Kubernetes (ACK), use KMS integration:

```bash
# Install ACK Secrets Manager
# https://www.alibabacloud.com/help/en/ack/ack-managed-and-ack-dedicated/user-guide/use-ack-secrets-manager

# Create secrets in Aliyun KMS, then reference them in K8s
```

**Redis Connection** (no secret needed):
- Connection string: `redis://redis:6379/1` (configured directly in deployment YAML)

---

### Phase 2: Kubernetes Deployment (Week 2)

#### 2.1 Ingress Configuration for Path-Based Routing

**Access Point**: `https://klinematrix.com/monitor`

**Ingress Rules** (add to existing ingress):
```yaml
# .pipeline/kubernetes/base/ingress.yaml (append to existing rules)
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: main-ingress
  namespace: klinematrix-test
  annotations:
    cert-manager.io/cluster-issuer: letsencrypt-prod
    nginx.ingress.kubernetes.io/ssl-redirect: "true"
    # Path rewrite for Langfuse (removes /monitor prefix)
    nginx.ingress.kubernetes.io/rewrite-target: /$2
    # Increase timeouts for long-running queries
    nginx.ingress.kubernetes.io/proxy-read-timeout: "300"
    nginx.ingress.kubernetes.io/proxy-send-timeout: "300"
spec:
  ingressClassName: nginx
  tls:
    - hosts:
        - klinematrix.com
      secretName: klinematrix-tls
  rules:
    - host: klinematrix.com
      http:
        paths:
          # Existing paths
          - path: /
            pathType: Prefix
            backend:
              service:
                name: frontend
                port:
                  number: 80
          - path: /api
            pathType: Prefix
            backend:
              service:
                name: backend
                port:
                  number: 8000

          # NEW: Langfuse observability UI
          - path: /monitor(/|$)(.*)
            pathType: ImplementationSpecific
            backend:
              service:
                name: langfuse-server
                port:
                  number: 3000
```

**How it works**:
1. User visits `https://klinematrix.com/monitor`
2. Ingress matches path `/monitor(/|$)(.*)`
3. Rewrite rule removes `/monitor` prefix → forwards to Langfuse at `/`
4. Langfuse server receives clean paths (e.g., `/monitor/traces` → `/traces`)

**Langfuse Server Configuration**:
```yaml
# Langfuse needs to know its base path for asset URLs
env:
  - name: NEXTAUTH_URL
    value: "https://klinematrix.com/monitor"
  - name: NEXT_PUBLIC_BASE_PATH
    value: "/monitor"  # For client-side routing
```

---

#### 2.2 Create Kubernetes Manifests

**Directory structure**:
```
.pipeline/kubernetes/langfuse/
├── base/
│   ├── kustomization.yaml
│   ├── clickhouse-statefulset.yaml
│   ├── clickhouse-service.yaml
│   ├── langfuse-server-deployment.yaml
│   ├── langfuse-worker-deployment.yaml
│   ├── langfuse-service.yaml
│   └── external-secrets.yaml
└── overlays/
    └── production/
        ├── kustomization.yaml
        └── patches/
            └── langfuse-env.yaml  # Environment-specific config
```

**Key Configuration Points**:

1. **Redis Connection** (Database 1):
```yaml
# langfuse-server-deployment.yaml & langfuse-worker-deployment.yaml
env:
  - name: REDIS_HOST
    value: "redis"
  - name: REDIS_PORT
    value: "6379"
  - name: REDIS_DB
    value: "1"  # Use database 1 (business uses 0)
```

2. **PostgreSQL Connection** (from External Secret):
```yaml
env:
  - name: DATABASE_URL
    valueFrom:
      secretKeyRef:
        name: langfuse-secrets
        key: postgres-connection-string
```

3. **Aliyun OSS** (S3-compatible):
```yaml
env:
  - name: LANGFUSE_S3_EVENT_UPLOAD_BUCKET
    value: "langfuse-events-prod"
  - name: LANGFUSE_S3_EVENT_UPLOAD_REGION
    value: "cn-hangzhou"  # Match your OSS region
  - name: LANGFUSE_S3_EVENT_UPLOAD_ENDPOINT
    value: "https://oss-cn-hangzhou.aliyuncs.com"  # OSS endpoint
  - name: LANGFUSE_S3_EVENT_UPLOAD_FORCE_PATH_STYLE
    value: "true"  # Required for OSS S3 compatibility
  - name: LANGFUSE_S3_EVENT_UPLOAD_ACCESS_KEY_ID
    valueFrom:
      secretKeyRef:
        name: langfuse-secrets
        key: s3-access-key
  - name: LANGFUSE_S3_EVENT_UPLOAD_SECRET_ACCESS_KEY
    valueFrom:
      secretKeyRef:
        name: langfuse-secrets
        key: s3-secret-key
```

I'll create the full manifests next. Would you like me to proceed?

---

### Phase 3: Deployment & Verification (Week 2-3)

**Deployment Steps** (after manifests are ready):

1. **Deploy ClickHouse** (StatefulSet with PVC)
2. **Deploy External Secrets Operator** (sync from Key Vault)
3. **Deploy Langfuse Server** (with health checks)
4. **Deploy Langfuse Worker** (queue processing)
5. **Configure Ingress** (HTTPS via existing cert)
6. **Initialize Langfuse** (first admin user, project setup)
7. **Update Backend** (enable Langfuse SDK with production credentials)

**Verification Checklist**:
- [ ] ClickHouse pods running (1/1 Ready)
- [ ] Langfuse server pod running (1/1 Ready)
- [ ] Langfuse worker pod running (1/1 Ready)
- [ ] External secrets synced from Key Vault
- [ ] Langfuse UI accessible at https://langfuse.klinematrix.com
- [ ] PostgreSQL connection successful
- [ ] Redis queue working (check worker logs)
- [ ] ClickHouse migrations applied
- [ ] Azure Blob Storage receiving events
- [ ] Backend SDK sending traces to Langfuse

---

## Cost Optimization Strategies

### 1. Reuse Existing Infrastructure
- ✅ **Redis in-cluster**: Use DB 1 for Langfuse (saves $16/mo vs Azure Redis)
- ✅ **Shared ingress**: Path-based routing on existing domain (no new LB cost)
- ✅ **Existing cluster**: No new nodes needed for 10 users

### 2. Use Burstable Tiers
- ✅ PostgreSQL B1ms: Bursts to 100% when needed, idles at low cost

### 3. Minimize Data Transfer
- ✅ All resources in same region (no egress charges)
- ✅ Redis in-cluster (no network egress to external service)
- ✅ Use private endpoints if cost increases (currently public OK for 10 users)

### 4. Storage Optimization
- ✅ Azure Blob LRS (Locally Redundant): No geo-replication overhead
- ✅ ClickHouse data retention: 30 days (configurable)
- ✅ PostgreSQL auto-storage growth: Pay only for what you use

### 5. Right-size Resource Limits
```yaml
# Langfuse Server (conservative for 10 users)
resources:
  requests:
    cpu: 100m      # Minimal baseline
    memory: 256Mi
  limits:
    cpu: 500m      # Burst capacity
    memory: 512Mi  # Prevents OOM, low enough to avoid node pressure
```

### 6. Scale-to-Zero (Optional Future Optimization)
For very low usage periods, consider KEDA autoscaling:
- Scale Langfuse server to 0 replicas if no requests for 1 hour
- Scale up on HTTP traffic
- **Savings**: ~20-30% if usage is bursty

---

## Monitoring & Maintenance

### Weekly Checks (5 minutes)
```bash
# Check pod health
kubectl get pods -n klinematrix-test | grep langfuse

# Check storage usage
kubectl exec -it langfuse-clickhouse-0 -n klinematrix-test -- \
  clickhouse-client --query "SELECT formatReadableSize(sum(bytes)) FROM system.parts"

# Check Azure costs (month-to-date)
az consumption usage list --start-date 2025-01-01 --end-date 2025-01-31 \
  --query "[?contains(instanceName, 'langfuse')].{name:instanceName, cost:pretaxCost}" -o table
```

### Monthly Tasks (15 minutes)
- Review Azure Cost Analysis for Langfuse resources
- Check PostgreSQL storage growth (should be <5GB for 10 users)
- Review ClickHouse data retention (delete old traces if needed)
- Verify backups (PostgreSQL auto-backups, should have 7 days)

---

## Scaling Plan (Future Growth)

| User Count | Changes Needed | Estimated Cost (USD) | Estimated Cost (CNY) |
|------------|----------------|---------------------|---------------------|
| **10 users** | Current setup (PolarDB Serverless, shared Redis) | **$8-12/mo** | **¥55-80/mo** |
| 50 users | PolarDB → 1-4 CU range, Redis → dedicated | $20-30/mo | ¥140-210/mo |
| 100 users | PolarDB → 2-8 CU range, Redis → Aliyun Redis 256MB | $40-60/mo | ¥280-420/mo |
| 500+ users | Consider Langfuse Cloud or scale to dedicated PolarDB cluster | $100-200/mo | ¥700-1400/mo |

**When to upgrade**:
- **Dedicated Redis**: If shared Redis memory >70% or queue backlog >1000 jobs
  - Aliyun Redis Community 256MB: ~¥50/mo (~$7)
- **PolarDB CU Scale**: If CPU consistently >70%, increase ScaleMax to 4 CU
  - Cost scales linearly: 2 CU = 2× cost of 1 CU
- **ClickHouse**: If PVC >80% full, expand storage (automated in K8s)
  - Storage cost minimal (cluster node disk)
- **Add cluster nodes**: If overall CPU pressure or pods evicted

---

## Alternative: Langfuse Cloud (SaaS)

If you prefer zero maintenance:

| Tier | Price | Traces/mo | Users | Recommendation |
|------|-------|-----------|-------|----------------|
| Developer | **$0** | 50,000 | Unlimited | ⚠️ Too limited for prod |
| Team | **$59/mo** | 1M traces | Unlimited | ✅ Good for 10-50 users |
| Pro | **Custom** | Unlimited | Unlimited | For 100+ users |

**Pros**:
- Zero infrastructure cost
- No maintenance
- Automatic updates
- Professional support

**Cons**:
- Recurring $59/mo (vs $40/mo self-hosted)
- Data sent to external service (privacy consideration)
- Less control over data retention

**When to consider**: If team has no DevOps capacity or values zero-ops over cost savings.

---

## Recommendation Summary

For **10 users** with **existing K8s cluster**:

✅ **Go with Aliyun ultra cost-effective approach** ($8-12/mo | ¥55-80/mo):
1. ✅ Aliyun PolarDB PostgreSQL Serverless - **$6-8/mo (¥40-55)**
2. ✅ Aliyun OSS (S3-compatible) - **$0.50-1/mo (¥3-7)**
3. ✅ Redis in K8s (shared, DB 1 for Langfuse) - **$0**
4. ✅ ClickHouse in K8s (StatefulSet, 2GB PVC) - **$0**
5. ✅ Langfuse Server + Worker in K8s - **$0**
6. ✅ Access via `https://klinematrix.com/monitor` (path-based routing) - **$0**

**Total Setup Time**: 2-3 weeks (1 week Aliyun services, 1-2 weeks K8s deployment & testing)

**Cost Comparison**:
| Option | Monthly Cost (USD) | Monthly Cost (CNY) | Savings vs Cloud |
|--------|-------------------|-------------------|-----------------|
| **Aliyun (Recommended)** | **$8-12** | **¥55-80** | **~85% cheaper** |
| Azure | $13-15 | ¥90-105 | ~75% cheaper |
| Langfuse Cloud | $59 | ¥420 | Baseline |

**Break-even point**: Immediate (cheaper from day 1)

**Key Benefits**:
- 💰 **Ultra-low cost**: PolarDB Serverless = pay only for actual usage
- 🔒 Full data control (stays in your cloud tenant)
- 🚀 Scales to 50+ users without major changes
- 🔧 Leverage existing infrastructure (no new cluster/ingress)
- 📊 Access at familiar domain (klinematrix.com/monitor)
- 🌏 Better performance in China (if applicable)

**Trade-offs Accepted**:
- ⚠️ Shared Redis (observability not mission-critical, acceptable)
- ⚠️ Manual maintenance (PolarDB managed, but ClickHouse needs monitoring)
- ⚠️ Aliyun account required (if not already using Aliyun)

**Why Aliyun over Azure**:
- **Serverless billing**: PolarDB charges per CU-hour (idle = minimal cost)
- **OSS cheaper**: ~¥0.12/GB vs Azure ~$0.018/GB (comparable, but combined package cheaper)
- **Better for China**: Lower latency if users/infra in China
- **Flexible**: Works with any K8s cluster (AKS, ACK, self-hosted)

**Next Steps**:
1. ✅ Provision Aliyun PolarDB Serverless (PostgreSQL 15)
2. ✅ Create Aliyun OSS bucket with S3-compatible access
3. ✅ Verify existing Redis can handle additional database
4. ✅ Create Kubernetes manifests (ClickHouse, Langfuse deployments, ingress)
5. ✅ Deploy to production K8s cluster
6. ✅ Configure backend to use production Langfuse (switch from local to production endpoints)
7. ✅ Monitor costs weekly for first month (should be ~¥55-80/month)

---

## APPENDIX: Manual PolarDB Whitelist Configuration

**Status**: Required manual action via Alibaba Cloud Console

### Background

The Aliyun CLI cannot modify PolarDB whitelist due to resource group level IAM restrictions. You must configure the whitelist through the Alibaba Cloud web console.

### IPs to Whitelist (AKS Public IPs)

```
20.249.104.210
4.217.130.195
```

### Step-by-Step Instructions

1. **Login to Alibaba Cloud Console**
   - URL: https://homenew.console.aliyun.com
   - **Use your main Alibaba Cloud account** (not RAM sub-user)

2. **Navigate to PolarDB**
   - Click: **产品与服务** (Products & Services) in top-left
   - Search: **PolarDB**
   - Or direct link: https://polardb.console.aliyun.com

3. **⚠️ CRITICAL: Select Correct Region**
   - **Region selector** in top navigation bar
   - **Switch to: 华东1 (杭州) / Hangzhou**
   - Common mistake: Wrong region = cluster not visible

4. **Find Your PolarDB Cluster**
   - Look for **Cluster ID**: `pc-bp141ar06fos11131`
   - Click on the cluster name to open details page

5. **Open Whitelist Settings**
   - Left sidebar menu
   - Click: **数据安全性** (Data Security)
   - Click: **白名单设置** (Whitelist Settings)
   - You should see a "default" whitelist group

6. **Add AKS IP Addresses**
   - Click **修改** (Modify) button next to the default group
   - In the whitelist input field, add (comma-separated, no spaces):
     ```
     20.249.104.210,4.217.130.195
     ```
   - Click **确定** (Confirm) to save

7. **Verify Configuration**
   - Whitelist should now show both IPs
   - Changes take effect **immediately** (no restart needed)

### What Happens Next

Once the whitelist is configured:

1. **Automatic Connection**: The `langfuse-server` pod will automatically connect on its next restart (~2-3 minutes)
2. **Health Check Recovery**: Failed health checks will start passing
3. **Database Migrations**: Langfuse will auto-run Prisma migrations on first successful connection
4. **Pod Status**: Server pod will transition from `CrashLoopBackOff` → `Running (1/1)`

### Verification Commands

```bash
# Watch pod status (should see server become 1/1 Running within 5 minutes)
kubectl get pods -n klinematrix-test -w | grep langfuse

# Check server logs (should see "Listening on port 3000" instead of connection errors)
kubectl logs -f langfuse-server-<pod-id> -n klinematrix-test

# Test Langfuse UI (should load login page)
curl -I https://klinematrix.com/monitor
```

### Troubleshooting

**If server still crashes after whitelist configuration**:

1. **Verify whitelist saved correctly**:
   - Go back to PolarDB console → Whitelist Settings
   - Confirm both IPs are visible

2. **Check for different error**:
   ```bash
   # Get latest logs
   kubectl logs langfuse-server-<pod-id> -n klinematrix-test --tail=100
   ```

3. **Check ClickHouse connectivity**:
   ```bash
   # Verify ClickHouse is running
   kubectl get pods -n klinematrix-test | grep clickhouse
   # Should show: langfuse-clickhouse-0  1/1  Running
   ```

4. **Check Redis connectivity**:
   ```bash
   # Test Redis from within cluster
   kubectl exec -it deployment/redis -n klinematrix-test -- redis-cli ping
   # Should return: PONG
   ```

5. **Check OSS credentials**:
   ```bash
   # Verify secret exists
   kubectl get secret langfuse-secrets -n klinematrix-test

   # Check secret keys
   kubectl get secret langfuse-secrets -n klinematrix-test -o jsonpath='{.data}' | jq keys
   ```

### Current Deployment Status (as of 2025-10-23)

| Component | Status | Details |
|-----------|--------|---------|
| **Infrastructure** |||
| VPC | ✅ Created | vpc-bp145xhba8pe5cnxh16sx (langfuse-prod-vpc) |
| vSwitch Zone K | ✅ Created | vsw-bp1q3m7dcgbldkbixr6ti (10.0.2.0/24) |
| PolarDB | ✅ Created | pc-bp141ar06fos11131 (needs whitelist) |
| OSS Bucket | ✅ Created | langfuse-events-prod |
| RAM User | ✅ Created | langfuse-oss-user (with access keys) |
| Azure Key Vault | ✅ Updated | All secrets stored |
| **Kubernetes** |||
| Namespace | ✅ Ready | klinematrix-test |
| Secrets | ✅ Created | langfuse-secrets (manual kubectl create) |
| ClickHouse | ✅ Running | 1/1 Ready (256Mi/512Mi) |
| Worker | ✅ Running | 1/1 Ready (32Mi/64Mi) |
| Server | ⏸️ Waiting | CrashLoopBackOff (PolarDB connection blocked) |
| Ingress | ✅ Configured | /monitor path routing |
| **Action Required** |||
| PolarDB Whitelist | ❌ **BLOCKER** | **Add AKS IPs via console (see above)** |

### Next Steps After Whitelist Configuration

1. ✅ User configures PolarDB whitelist (this step)
2. ⏳ Verify all pods running (automatic after whitelist)
3. ⏳ Access Langfuse UI at https://klinematrix.com/monitor
4. ⏳ Create admin account and project
5. ⏳ Get API keys for backend integration
6. ⏳ Update backend with Langfuse credentials
7. ⏳ Test LLM observability in production

---

Would you like me to proceed with creating the Kubernetes manifests?

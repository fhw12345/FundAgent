# Migration: Dev → Test Environment

**Date**: 2025-10-06
**Status**: ✅ Complete

## Summary

Successfully migrated from dev-focused naming (`financial-agent-dev`) to proper test environment (`klinematrix-test`) with clean separation between local development and cloud test.

## Architecture Changes

### Before (Incorrect)
```
Local Dev + Cloud "Dev" (mixed):
- Namespace: financial-agent-dev (actually test environment)
- Images: financial-agent/backend:dev-latest
- Key Vault: financial-agent-dev-kv
- Domain: klinematrix.com
```

### After (Correct)
```
Local Dev (Docker Compose):
- Location: Developer machine
- Secrets: .env.development
- Email: Bypass mode
- Database: Local MongoDB container
- Access: http://localhost:3000

Test (Cloud - AKS):
- Namespace: klinematrix-test
- Images: klinematrix/backend:test-v0.3.0
- Key Vault: klinematrix-test-kv
- Domain: https://klinematrix.com
- Users: 10 beta testers
```

## Resources Migrated

### Created New
| Resource | Name | Purpose |
|----------|------|---------|
| Key Vault | `klinematrix-test-kv` | Test environment secrets |
| Namespace | `klinematrix-test` | Test workloads |
| Images | `klinematrix/backend:test-v0.3.0` | Versioned test images |
| Images | `klinematrix/frontend:test-v0.3.0` | Versioned test images |

### Kept (Infrastructure - Budget Savings)
| Resource | Name | Reason |
|----------|------|--------|
| ACR | `financialAgent` | Cannot rename, just infrastructure |
| Cosmos DB | `financialagent-mongodb` | Cannot rename, using different database name |

### Deleted
| Resource | Name | Reason |
|----------|------|--------|
| Namespace | `financial-agent-dev` | Was actually test, renamed properly |
| Key Vault | `financial-agent-dev-kv` | Obsolete, secrets moved to new vault |

## Secrets Configuration

### klinematrix-test-kv Secrets
```bash
# Generated
jwt-secret-key-test                    # NEW: Cryptographically secure

# Email (Tencent Cloud SES)
tencent-secret-id-test                 # Tencent Cloud API SecretId
tencent-secret-key-test                # Tencent Cloud API SecretKey

# External Services
alibaba-dashscope-api-key-test         # Copied from dev
mongodb-connection-string-test         # Cosmos DB connection
```

## Database Strategy

**Cosmos DB Account**: `financialagent-mongodb` (cannot rename)

**Databases per Environment**:
- Dev (local): `klinematrix_dev` (Docker container)
- Test (cloud): `klinematrix_test` (Cosmos DB)
- Prod (cloud): `klinematrix_prod` (Cosmos DB) - future

## Image Naming Convention

### Registry
- **ACR**: `financialagent-gxftdbbre4gtegea.azurecr.io` (old name, kept)
- **Images inside**: `klinematrix/*` (new naming)

### Tags
```
Test: klinematrix/backend:test-v0.3.0
Prod: klinematrix/backend:v0.3.0 (future)
```

## Environment Variables

### Test Environment (backend-test-patch.yaml)
```yaml
ENVIRONMENT: test
EMAIL_BYPASS_MODE: false
CORS_ORIGINS: '["https://klinematrix.com"]'
MONGODB_DATABASE: klinematrix_test
TENCENT_SES_REGION: ap-guangzhou
TENCENT_SES_FROM_EMAIL: noreply@klinematrix.com
TENCENT_SES_FROM_NAME: Klinematrix
TENCENT_SES_TEMPLATE_ID: 37066
```

### Local Dev (.env.development) - Not in K8s
```bash
ENVIRONMENT=development
EMAIL_BYPASS_MODE=true
MONGODB_URL=mongodb://localhost:27017/klinematrix_dev
REDIS_URL=redis://localhost:6379/0
```

## Deployment Workflow

### Old (Mixed)
```bash
# Dev on cloud (wrong)
docker-compose up  # Local
kubectl apply -k overlays/dev/  # Cloud "dev" (actually test)
```

### New (Clean Separation)
```bash
# Local dev
docker-compose up

# Test deployment
kubectl apply -k overlays/test/
```

## Health Check

```bash
# Test endpoint
curl https://klinematrix.com/api/health

# Expected response
{
  "status": "ok",
  "environment": "test",
  "dependencies": {
    "mongodb": {"connected": true},
    "redis": {"connected": true}
  }
}
```

## Post-Migration Checklist

- [x] New Key Vault created
- [x] Test secrets generated
- [x] Namespace created
- [x] Images built with new naming
- [x] Manifests updated (all namespace references fixed)
- [x] Old namespace deleted
- [x] Deployed to cluster
- [x] Health checks passing
- [x] Documentation updated (resource inventory created)
- [x] Tencent Cloud email configured (SES API with SecretId/SecretKey)

## Rollback Procedure

If needed, revert by:

1. Keep `klinematrix-test` namespace (it's working)
2. Old `financial-agent-dev` is deleted, cannot restore
3. Secrets in old vault can be retrieved if needed
4. Images are immutable (safe)

## Cost Impact

**Savings**: $0 (reused existing ACR and Cosmos DB)

**New Costs**:
- Key Vault: ~$0.03/month (minimal)
- No new infrastructure created

## Next Steps

1. ✅ Complete migration to test
2. ✅ Fix all namespace references
3. ✅ Create resource inventory documentation
4. ✅ Configure Tencent Cloud email (SES API)
5. 🚧 Test email verification flow
6. 🚧 Invite 10 beta users
7. 🚧 Create prod environment when ready

## Related Documentation

- [Resource Inventory](RESOURCE_INVENTORY.md) - Complete list of all Azure and K8s resources

# External Secrets Sync Issues

> **Last Updated**: 2025-10-24
> **Affected Versions**: All versions using External Secrets Operator

## Problem: Secrets Not Updating After Key Vault Changes

### Symptoms
- Updated secrets in Azure Key Vault but pods still have old values
- External Secrets Operator shows `SecretSyncedError` or stale `lastSync` timestamp
- Application fails to connect using updated credentials
- Backend crashes with "authentication failed" or similar errors after Key Vault update

### Root Cause
External Secrets Operator caches secrets and only refreshes based on `refreshInterval` (default: 1h). Manual sync required for immediate updates.

## Solution

### Step 1: Force Sync External Secret

```bash
# Add annotation with current timestamp to trigger sync
kubectl annotate externalsecret <name> -n <namespace> \
  force-sync="$(date +%s)" --overwrite

# Example:
kubectl annotate externalsecret app-secrets -n klinematrix-test \
  force-sync="$(date +%s)" --overwrite
```

### Step 2: Verify Sync Status

```bash
kubectl get externalsecret <name> -n <namespace> \
  -o jsonpath='{.status.conditions[?(@.type=="Ready")].status}'

# Should return: True
```

### Step 3: Restart Pods to Pick Up New Secrets

```bash
kubectl delete pod -l app=<app> -n <namespace>

# Example:
kubectl delete pod -l app=backend -n klinematrix-test
```

### Step 4: Verify Secret Content

```bash
# Decode and verify secret value
kubectl get secret <name> -n <namespace> \
  -o jsonpath='{.data.<key>}' | base64 -d

# Example:
kubectl get secret app-secrets -n klinematrix-test \
  -o jsonpath='{.data.mongodb-url}' | base64 -d
```

## Prevention

### Option 1: Shorter Refresh Interval

```yaml
apiVersion: external-secrets.io/v1
kind: ExternalSecret
metadata:
  name: app-secrets
spec:
  refreshInterval: 5m  # Default is 1h
  # ... rest of spec
```

**Trade-offs**:
- ✅ Faster automatic sync
- ❌ More API calls to Azure Key Vault (may incur costs)
- ❌ Higher risk of rate limiting

### Option 2: Document Force-Sync Procedure

- Add force-sync commands to deployment runbook
- Train team on manual sync process
- Use for infrequent updates (recommended)

## Common Scenarios

### Scenario 1: Rotating API Keys

```bash
# 1. Update secret in Azure Key Vault
az keyvault secret set --vault-name <vault> --name <secret> --value <new-value>

# 2. Force sync
kubectl annotate externalsecret app-secrets -n klinematrix-test \
  force-sync="$(date +%s)" --overwrite

# 3. Wait 10-30 seconds for sync
sleep 30

# 4. Verify sync completed
kubectl get externalsecret app-secrets -n klinematrix-test

# 5. Restart application
kubectl delete pod -l app=backend -n klinematrix-test
```

### Scenario 2: MongoDB Connection String Update

Example from **Backend v0.5.5**: Adding database name to connection string

```bash
# Update connection string in Key Vault
az keyvault secret set --vault-name klinematrix-test-kv \
  --name mongodb-connection-string-test \
  --value "mongodb://...@host:10255/klinematrix_test?ssl=true..."

# Force sync
kubectl annotate externalsecret app-secrets -n klinematrix-test \
  force-sync="$(date +%s)" --overwrite

# Wait and restart
sleep 30
kubectl delete pod -l app=backend -n klinematrix-test

# Verify backend starts successfully
kubectl logs deployment/backend -n klinematrix-test --tail=50 | grep "MongoDB"
```

### Scenario 3: Adding New Secrets (Langfuse API Keys)

Example from recent deployment: Adding Langfuse observability keys

```bash
# 1. Create secrets in Azure Key Vault
az keyvault secret set --vault-name klinematrix-test-kv \
  --name langfuse-public-key \
  --value "pk-lf-..."

az keyvault secret set --vault-name klinematrix-test-kv \
  --name langfuse-secret-key \
  --value "sk-lf-..."

# 2. Update ExternalSecret manifest to reference new keys
kubectl edit externalsecret app-secrets -n klinematrix-test

# Add to spec.data:
#   - secretKey: langfuse-public-key
#     remoteRef:
#       key: langfuse-public-key
#   - secretKey: langfuse-secret-key
#     remoteRef:
#       key: langfuse-secret-key

# 3. Force sync
kubectl annotate externalsecret app-secrets -n klinematrix-test \
  force-sync="$(date +%s)" --overwrite

# 4. Verify new keys are in secret
kubectl get secret app-secrets -n klinematrix-test -o json | jq '.data | keys'

# 5. Restart pods that need new keys
kubectl delete pod -l app=backend -n klinematrix-test
```

## Troubleshooting

### Issue: Force Sync Not Working

**Check External Secrets Operator Logs**:
```bash
kubectl logs -n external-secrets-system deployment/external-secrets-operator --tail=100
```

**Common Errors**:
- `"access denied"` → Check workload identity permissions
- `"secret not found"` → Verify secret name in Key Vault
- `"throttled"` → Wait and retry (rate limiting)

### Issue: Pods Not Picking Up New Secrets

**Problem**: Restarting pods doesn't update secret values

**Cause**: Secrets are mounted as volumes, not environment variables

**Solution**: Delete the pod completely (not just restart):
```bash
# This works:
kubectl delete pod -l app=backend -n klinematrix-test

# This does NOT work:
kubectl rollout restart deployment/backend -n klinematrix-test  # Still uses old secrets
```

### Issue: Secret Sync Shows "Ready: True" but Value is Wrong

**Cause**: Kubernetes secret exists but contains stale data

**Solution**: Delete the Kubernetes secret and force re-sync:
```bash
# 1. Delete Kubernetes secret (will be recreated)
kubectl delete secret app-secrets -n klinematrix-test

# 2. Force sync to recreate from Key Vault
kubectl annotate externalsecret app-secrets -n klinematrix-test \
  force-sync="$(date +%s)" --overwrite

# 3. Wait for recreation
sleep 30

# 4. Verify new content
kubectl get secret app-secrets -n klinematrix-test \
  -o jsonpath='{.data.mongodb-url}' | base64 -d

# 5. Restart pods
kubectl delete pod -l app=backend -n klinematrix-test
```

## Verification Checklist

After updating secrets, verify:

- [ ] Azure Key Vault secret updated: `az keyvault secret show --vault-name <vault> --name <secret>`
- [ ] External Secret synced: `kubectl get externalsecret <name> -n <namespace>` (check lastSync timestamp)
- [ ] Kubernetes secret contains new value: `kubectl get secret <name> -n <namespace> -o jsonpath='{.data.<key>}' | base64 -d`
- [ ] Pods restarted: `kubectl get pods -n <namespace>` (check AGE column)
- [ ] Application logs show successful connection: `kubectl logs deployment/<app> -n <namespace> --tail=50`

## Automation Options

### Option 1: Kubernetes CronJob for Periodic Sync

```yaml
apiVersion: batch/v1
kind: CronJob
metadata:
  name: force-sync-secrets
  namespace: klinematrix-test
spec:
  schedule: "*/30 * * * *"  # Every 30 minutes
  jobTemplate:
    spec:
      template:
        spec:
          serviceAccountName: klinematrix-sa  # Must have permissions
          containers:
          - name: sync
            image: bitnami/kubectl:latest
            command:
            - /bin/sh
            - -c
            - |
              kubectl annotate externalsecret app-secrets -n klinematrix-test \
                force-sync="$(date +%s)" --overwrite
          restartPolicy: OnFailure
```

### Option 2: GitHub Actions Workflow

```yaml
name: Sync External Secrets

on:
  workflow_dispatch:  # Manual trigger
  schedule:
    - cron: '0 */6 * * *'  # Every 6 hours

jobs:
  sync:
    runs-on: ubuntu-latest
    steps:
      - uses: azure/k8s-set-context@v3
        with:
          kubeconfig: ${{ secrets.KUBECONFIG }}

      - name: Force Sync
        run: |
          kubectl annotate externalsecret app-secrets -n klinematrix-test \
            force-sync="$(date +%s)" --overwrite
```

## Related Issues

- **Backend v0.5.5**: MongoDB connection string missing database name - required force-sync after Key Vault update
- **Langfuse Deployment**: Adding API keys required force-sync and pod restart
- **Cosmos DB Migration**: Connection string format change required force-sync

## References

- [External Secrets Operator Documentation](https://external-secrets.io/latest/)
- [Azure Key Vault Provider](https://external-secrets.io/latest/provider/azure-key-vault/)
- [Workload Identity Authentication](https://external-secrets.io/latest/provider/azure-key-vault/#workload-identity)
- Deployment Workflow: [docs/deployment/workflow.md](../deployment/workflow.md)
- Troubleshooting Guide: [docs/troubleshooting/README.md](./README.md)

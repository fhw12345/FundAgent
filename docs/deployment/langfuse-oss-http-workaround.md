# Langfuse OSS S3-Compatible API HTTP Workaround

## Problem

Langfuse v3 uses AWS SDK (boto3) to upload trace events to S3-compatible storage. When configured with Alibaba Cloud OSS using HTTPS, boto3's chunked transfer encoding causes the following error:

```
InvalidArgument: aws-chunked encoding is not supported with the specified x-amz-content-sha256 value.
```

## Root Cause

- **boto3/botocore** uses `aws-chunked` encoding for HTTPS requests
- **Alibaba Cloud OSS** does not support this encoding mode
- Path-style addressing also fails (OSS requires virtual-hosted style)

## Solution

Use **HTTP instead of HTTPS** for the OSS endpoint.

### Configuration

```yaml
env:
- name: LANGFUSE_S3_EVENT_UPLOAD_ENDPOINT
  value: "http://oss-cn-hangzhou.aliyuncs.com"  # HTTP, not HTTPS
- name: LANGFUSE_S3_EVENT_UPLOAD_FORCE_PATH_STYLE
  value: "false"  # Virtual-hosted style required
```

### Credentials (Azure Key Vault)

Stored in `klinematrix-test-kv`:
- `langfuse-oss-access-key-id`: `<REDACTED>` (stored in Key Vault)
- `langfuse-oss-access-key-secret`: `<REDACTED>` (stored in Key Vault)

Referenced via External Secrets in:
- `.pipeline/k8s/base/langfuse/server-deployment.yaml`
- `.pipeline/k8s/base/langfuse/worker-deployment.yaml`

## Security Considerations

### Risk

- **HTTP transmits data in plaintext**, including trace events
- Traffic is unencrypted between AKS (Azure) and OSS (Alibaba Cloud)

### Mitigation

1. **Primary storage is ClickHouse** (PostgreSQL-compatible) with encryption at rest
2. **OSS is backup/event storage** only, not the primary trace database
3. **Internal endpoint not available** - AKS in Azure cannot access OSS internal network
4. **Cost vs. Security tradeoff** - Using HTTPS would require:
   - Custom boto3 client configuration
   - OR different S3-compatible storage (MinIO, AWS S3, etc.)
   - OR separate VPN/interconnect between clouds

### Alternatives Considered

1. **Use OSS internal endpoint** (`oss-cn-hangzhou-internal.aliyuncs.com`)
   - ❌ Not possible - AKS is in Azure, OSS is in Alibaba Cloud
   - Would be secure + free egress if both were in Alibaba Cloud

2. **Disable payload signing** (`payload_signing_enabled: false`)
   - ❌ Still triggers chunked encoding issue

3. **Use path-style addressing** (`FORCE_PATH_STYLE: true`)
   - ❌ OSS explicitly rejects: "Please use virtual hosted style to access"

4. **Upgrade/downgrade boto3 version**
   - ❌ Langfuse uses pinned SDK versions in Docker image
   - Would require custom Docker image maintenance

## Verification

### Test Script

See `scripts/verify-oss-s3-auth.py` for OSS S3-compatible API testing.

### Successful Test Output

```bash
python3 scripts/verify-oss-s3-auth.py

OSS_ENDPOINT="http://oss-cn-hangzhou.aliyuncs.com" \
OSS_BUCKET="langfuse-events-prod" \
OSS_REGION="cn-hangzhou" \
OSS_ACCESS_KEY_ID="LTAI..." \
OSS_SECRET_ACCESS_KEY="..." \
python3 scripts/verify-oss-s3-auth.py

Testing with HTTP endpoint + virtual-hosted style...
Uploading test file...
✅ Upload successful!
Downloading test file...
✅ Download successful - content matches!
Deleting test file...
✅ Delete successful!
```

### Verify in Kubernetes

```bash
# Check Langfuse server logs for S3 upload errors
kubectl logs deployment/langfuse-server -n klinematrix-test | grep -i "s3\|oss"

# Should see successful uploads, no "InvalidArgument" errors

# Check environment variables
kubectl exec deployment/langfuse-server -n klinematrix-test -- env | grep LANGFUSE_S3

# Expected output:
# LANGFUSE_S3_EVENT_UPLOAD_ENDPOINT=http://oss-cn-hangzhou.aliyuncs.com
# LANGFUSE_S3_EVENT_UPLOAD_FORCE_PATH_STYLE=false
# LANGFUSE_S3_EVENT_UPLOAD_BUCKET=langfuse-events-prod
# LANGFUSE_S3_EVENT_UPLOAD_REGION=cn-hangzhou
```

## Implementation Timeline

- **Date**: 2025-10-23
- **Affected Services**: Langfuse v3 (server + worker)
- **Deployment**: Test environment (`klinematrix-test`)

## References

- [Alibaba Cloud OSS S3-Compatible API](https://www.alibabacloud.com/help/en/oss/developer-reference/use-amazon-s3-sdks-to-access-oss)
- [Langfuse v3 S3 Storage Docs](https://langfuse.com/docs/deployment/v3/components/blobstorage)
- Boto3 Issue: aws-chunked encoding incompatibility with non-AWS S3 implementations

## Recommendations

### For Production

1. **Monitor OSS bucket access logs** for unauthorized access
2. **Implement VPC peering or VPN** between Azure and Alibaba Cloud if sensitive data in traces
3. **Consider alternative storage**:
   - MinIO (self-hosted, supports HTTPS properly)
   - Azure Blob Storage (native Azure, encrypted)
   - AWS S3 (native AWS SDK support)

### For Development

Current HTTP configuration is acceptable for test environment with 10 beta users and non-sensitive trace data.

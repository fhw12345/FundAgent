# Slow Azure ACR to Alibaba ACK Image Pull

## Problem Description

Image pulls from Azure Container Registry (ACR) to Alibaba Cloud Kubernetes (ACK) take 15-20+ minutes for a ~240MB image.

**Symptoms:**
- `kubectl rollout status` times out (even with 5-10 min timeout)
- Pod stuck in `ContainerCreating` state
- Events show `Pulling image...` for extended periods
- Service downtime during deployments (with `Recreate` strategy)

## Root Cause Analysis

### Measured Performance
- **Image size**: 240 MB
- **Pull time**: ~15 minutes (900 seconds)
- **Effective speed**: 0.26 MB/s = **2.13 Mbps**

### Why So Slow?

1. **Cross-Cloud Network**: Azure → Alibaba networks have no direct peering
2. **Cross-Border Traffic**: Hong Kong (Azure) → Shanghai (ACK) crosses China border
3. **GFW Overhead**: Great Firewall packet inspection adds latency
4. **Bandwidth Throttling**: Cross-border links are heavily throttled

### Network Path
```
Azure ACR (Hong Kong/East Asia)
    ↓
Internet (cross-border link)
    ↓
GFW (packet inspection)
    ↓
Alibaba Cloud (Shanghai)
    ↓
ACK Node
```

## Solutions

### Solution 1: DaemonSet Pre-Pull (Implemented)

**How it works:**
- CI/CD creates a DaemonSet before deployment
- DaemonSet pulls image to ALL nodes in parallel
- After caching complete, DaemonSet is deleted
- Deployment uses cached image (fast startup)

**Trade-offs:**
- ✅ No infrastructure changes needed
- ✅ Works with existing Azure ACR
- ❌ Still takes 15-20 min per new version
- ❌ All nodes pull in parallel (more bandwidth)

**Implementation:**
See `.github/workflows/deploy.yml` - "Pre-pull images" step

### Solution 2: Alibaba ACR Mirror (Recommended for Speed)

**How it works:**
- Create Alibaba Container Registry in cn-shanghai
- CI/CD pushes images to BOTH Azure ACR AND Alibaba ACR
- ACK pulls from same-region Alibaba ACR

**Trade-offs:**
- ✅ Expected speed: 100+ MB/s (same cloud, same region)
- ✅ Deploy in seconds, not minutes
- ❌ Requires additional infrastructure (~$15-50/month)
- ❌ Need to maintain two registries

**Implementation:**
1. Create Alibaba ACR instance in cn-shanghai
2. Update CI/CD to push to both registries
3. Create new `imagePullSecret` for Alibaba ACR
4. Update kustomization.yaml to use Alibaba ACR

### Solution 3: Azure ACR Geo-Replication

**How it works:**
- Enable Azure ACR Premium geo-replication
- Add China North as replication target

**Trade-offs:**
- ✅ Azure-native solution
- ❌ Requires Azure China subscription (21Vianet operated)
- ❌ Complex: China Azure is separate from global Azure
- ❌ Regulatory compliance requirements

### Solution 4: Image Proxy (Harbor)

**How it works:**
- Deploy Harbor registry in ACK
- Configure as pull-through cache for Azure ACR
- Caches images after first pull

**Trade-offs:**
- ✅ Self-hosted, no external dependencies
- ❌ Still slow for first pull of new images
- ❌ Additional infrastructure to maintain
- ❌ Uses cluster resources

## Current Implementation

We use **Solution 1 (DaemonSet Pre-Pull)** because:
1. No additional infrastructure cost
2. Works with existing Azure ACR setup
3. Deployment is fast once images are cached
4. Acceptable for current deployment frequency

## Monitoring

Check image pull progress:
```bash
# Watch pod status
kubectl get pods -n klinematrix-prod -l app=backend -w

# Check events for pull progress
kubectl describe pod -n klinematrix-prod -l app=backend | grep -A 10 "Events:"

# Monitor DaemonSet pre-pull (during CI/CD)
kubectl get daemonset pre-pull-backend -n klinematrix-prod
```

## Future Improvements

If deployment frequency increases or downtime becomes unacceptable:
1. **Short-term**: Consider Alibaba ACR mirror (~$15/month)
2. **Long-term**: Evaluate full migration to Alibaba ACR as primary registry

## Related Documentation

- [Deployment Workflow](../deployment/workflow.md)
- [CI/CD Pipeline](.github/workflows/deploy.yml)

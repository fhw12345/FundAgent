# Cost Optimization Guide

## Overview

This guide documents cost optimization strategies for the Financial Agent AKS deployment based on real-world cost analysis and optimization efforts.

## Current Cost Breakdown (Oct 2025)

| Resource | Monthly Cost | Notes |
|----------|--------------|-------|
| **AKS Nodes** | **$53** | 2× Standard_D2ls_v5 (2 vCPU, 4GB RAM) |
| Cosmos DB MongoDB | $24 | 400 RU/s shared throughput |
| Container Registry | $5 | Basic tier (financialAgent) |
| Load Balancer + IPs | $8 | 2 public IPs |
| Log Analytics | $5-10 | Data ingestion |
| **Total** | **~$95-100/month** | After optimization |

## Optimization History

### Oct 2025: Node Pool Autoscaling Optimization

**Problem**: Unexpected autoscaling increased costs from $95 to $150/month.

**Root Cause**:
- Duplicate deployments running in `default` namespace (old v0.4.2)
- klinematrix-test namespace running current versions (v0.4.5/v0.6.1)
- Combined workload consumed ~7GB RAM, triggering autoscaler
- agentpool scaled 1→2 nodes, userpool briefly scaled 1→2
- Total nodes: 4 (should be 2)

**Solution**:
1. Deleted duplicate deployments: `kubectl delete deployment backend frontend redis -n default`
2. Freed ~640Mi RAM (userpool: 85%→60% utilization)
3. Capped autoscaler: `az aks nodepool update --max-count 1` on both pools
4. Cost reduced: $150→$95/month (**$55/month savings**, 37% reduction)

**Lesson**: Always clean up old deployments when migrating namespaces.

## Node Sizing Analysis

### Current Setup: 2× Standard_D2ls_v5

**Specs per node**:
- 2 vCPUs
- 4GB RAM (2.8GB usable after system pods)
- Cost: ~$26.50/month each

**Total capacity**: ~5.6GB usable RAM
**Current usage**: ~6.4GB RAM (after cleanup)
**Utilization**: 88-60% across nodes
**HA**: ✅ 2 nodes provide redundancy

### Alternative: 2× Standard_D4ls_v5

**Specs per node**:
- 4 vCPUs
- 8GB RAM (~6.5GB usable)
- Cost: ~$40/month each

**Total cost**: $80/month (+$27/month vs current)
**Pros**: More headroom for growth, better performance
**Cons**: 50% more expensive
**When to upgrade**: If hitting OOM errors or adding CPU-intensive features

### Alternative: 1× Standard_D4ls_v5

**Total cost**: $40/month (-$13/month vs current)
**Pros**: Cheapest option
**Cons**: ❌ No HA, no rolling updates, single point of failure
**Use case**: Dev/staging only, NOT production

## Autoscaler Configuration

### Current Settings (Optimized)

```bash
# agentpool (system pool)
az aks nodepool show --resource-group FinancialAgent \
  --cluster-name FinancialAgent-AKS --name agentpool \
  --query '{min:minCount, max:maxCount, current:count}'
# Output: {"min": 1, "max": 1, "current": 1}

# userpool (user pool)
az aks nodepool show --resource-group FinancialAgent \
  --cluster-name FinancialAgent-AKS --name userpool \
  --query '{min:minCount, max:maxCount, current:count}'
# Output: {"min": 1, "max": 1, "current": 1}
```

**Why max-count=1**: Prevents unexpected scaling beyond 2 total nodes, caps cost at ~$53/month.

### Monitoring Autoscaling

```bash
# Check if autoscaling triggered recently
kubectl get events --all-namespaces --sort-by='.lastTimestamp' | grep -i scale

# Check current node count
kubectl get nodes

# Check memory pressure
kubectl top nodes
```

**Autoscaler will scale up if**:
- Memory utilization >80% on all nodes
- Pods pending due to insufficient resources
- `max-count` not reached

**Scale-down delay**: 10-15 minutes after capacity becomes available

## Cost Optimization Checklist

### Before Deployment
- [ ] Verify old deployments cleaned up from all namespaces
- [ ] Check autoscaler limits: `max-count` should prevent unexpected scaling
- [ ] Review resource requests/limits in deployment manifests

### Monthly Review
- [ ] Check Azure Cost Management for unexpected spikes
- [ ] Verify node count matches expected: `kubectl get nodes`
- [ ] Review memory utilization: `kubectl top nodes` (should be <80%)
- [ ] Check for zombie resources: old deployments, unused namespaces

### If Costs Increase Unexpectedly
1. Check node count: `kubectl get nodes | wc -l`
2. Check autoscaler events: `kubectl get events | grep -i scale`
3. Check all namespaces for deployments: `kubectl get deployments --all-namespaces`
4. Check memory usage: `kubectl top nodes`
5. Review Azure activity log for scaling events

## Resource Right-Sizing

### Application Resource Requests (Current)

```yaml
# Backend
resources:
  requests:
    cpu: 100m
    memory: 256Mi

# Frontend
resources:
  requests:
    cpu: 50m
    memory: 128Mi

# Redis
resources:
  requests:
    cpu: 50m
    memory: 64Mi
```

**Total per environment**: 200m CPU, 448Mi RAM
**Total cluster** (with infrastructure): ~1.5 vCPU, ~6.4GB RAM

### Cosmos DB Throughput Optimization

**Current**: 400 RU/s shared across all collections ($24/month)

**Strategy**: Shared database-level throughput instead of collection-level
- Saves ~$20/month per additional collection
- Adequate for current load (light usage)
- Can scale up if needed

**Monitor**: Check Cosmos DB metrics for throttling (429 errors)

## Future Optimization Opportunities

1. **Azure Reserved Instances**: 1-year commit could save 30-40% on VM costs
2. **Spot VMs**: Use for non-critical workloads (not recommended for production)
3. **Horizontal Pod Autoscaler**: Scale pods down during low traffic
4. **Log Analytics**: Reduce data retention from 30 days to 7 days
5. **Container Registry**: Cleanup old/unused images

## Debugging High Costs

### Quick Diagnostic Script

```bash
#!/bin/bash
# cost-check.sh - Quick cost diagnostic

echo "=== Node Count ==="
kubectl get nodes | wc -l

echo -e "\n=== Node Pool Config ==="
az aks nodepool list --resource-group FinancialAgent \
  --cluster-name FinancialAgent-AKS \
  --query "[].{Name:name, Count:count, Min:minCount, Max:maxCount}" -o table

echo -e "\n=== Memory Usage ==="
kubectl top nodes

echo -e "\n=== All Deployments ==="
kubectl get deployments --all-namespaces

echo -e "\n=== Recent Scale Events ==="
kubectl get events --all-namespaces --sort-by='.lastTimestamp' | grep -i scale | tail -10
```

### Common Cost Surprises

| Issue | Symptom | Fix |
|-------|---------|-----|
| **Duplicate deployments** | 2+ namespaces with same apps | `kubectl delete deployment -n old-namespace` |
| **Autoscaler uncapped** | 3-4 nodes instead of 2 | `az aks nodepool update --max-count 1` |
| **Crashing pods** | High restart count, resource waste | Fix crash, delete old pods |
| **Dev mode in prod** | Vite server instead of nginx | Rebuild with `--target production` |
| **Oversized requests** | Low utilization but high costs | Lower resource requests |

## Related Documentation

- [Deployment Issues > Autoscaling](../troubleshooting/deployment-issues.md#issue-unexpected-node-autoscaling-due-to-duplicate-deployments)
- [Resource Inventory](./RESOURCE_INVENTORY.md)
- [Cloud Setup](./cloud-setup.md)

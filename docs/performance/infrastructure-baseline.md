# Infrastructure Performance Baseline

**Collected**: 2025-12-23
**Platform**: Alibaba Cloud ACK (Shanghai)
**Namespace**: klinematrix-prod

---

## Cluster Overview

### Node Pool Configuration

| Node | Type | CPU | Memory | Role |
|------|------|-----|--------|------|
| cn-shanghai.172.22.192.247 | Standard | 2 vCPU | 2.3 GB | User workloads |
| cn-shanghai.172.22.192.249 | Standard | 2 vCPU | 2.3 GB | User workloads |
| cn-shanghai.172.22.192.250 | Standard | 2 vCPU | 2.3 GB | User workloads |
| cn-shanghai.172.22.192.251 | Memory-optimized | 2 vCPU | 14 GB | Heavy workloads |

---

## Node Utilization

### Current Metrics

| Node | CPU Usage | CPU % | Memory | Memory % | Status |
|------|-----------|-------|--------|----------|--------|
| 172.22.192.247 | 83m | 4% | 1595Mi | **68%** | 🟢 OK |
| 172.22.192.249 | 66m | 3% | 2112Mi | **90%** | 🔴 Critical |
| 172.22.192.250 | 65m | 3% | 2013Mi | **86%** | 🟡 Warning |
| 172.22.192.251 | 332m | 17% | 4884Mi | 34% | 🟢 OK |

**⚠️ FINDING**: Two nodes (249, 250) have memory utilization >80%, which can cause:
- Pod scheduling failures
- OOM kills
- Performance degradation

---

## Pod Resource Usage

### Current Pod Metrics

| Pod | CPU | Memory | Status |
|-----|-----|--------|--------|
| backend-* | TBD (just restarted) | TBD | Running |
| frontend-* | 1m | 4Mi | 🟢 Efficient |
| mongodb-0 | 161m | 295Mi | 🟢 Normal |
| redis-* | 3m | 8Mi | 🟢 Minimal |
| langfuse-server-* | 2m | 455Mi | 🟢 Normal |
| langfuse-worker-* | 6m | 230Mi | 🟢 Normal |
| langfuse-clickhouse-* | 45m | 632Mi | 🟡 Heavy |
| langfuse-postgres-* | 5m | 48Mi | 🟢 Minimal |

---

## Resource Requests/Limits

### Backend (`backend-prod-patch.yaml`)

```yaml
resources:
  requests:
    memory: "512Mi"
    cpu: "200m"
  limits:
    memory: "1Gi"
    cpu: "1000m"
```

### Frontend (`frontend-prod-patch.yaml`)

```yaml
resources:
  requests:
    memory: "128Mi"
    cpu: "100m"
  limits:
    memory: "256Mi"
    cpu: "500m"
```

---

## HPA Configuration

**Status**: No HPA found in namespace

This means pods are running at fixed replicas without auto-scaling.

---

## Bottlenecks Identified

### Priority 1: High Memory Nodes

- **Nodes**: 172.22.192.249 (90%), 172.22.192.250 (86%)
- **Risk**: OOM, scheduling failures
- **Action**:
  - Reduce pod memory requests where possible
  - Consider adding nodes
  - Review Langfuse resource usage

### Priority 2: No Auto-Scaling

- **Issue**: Fixed replicas, no HPA
- **Risk**: Can't handle traffic spikes
- **Action**: Configure HPA for backend/frontend

### Priority 3: Langfuse Resource Usage

- **ClickHouse**: 632Mi (largest pod)
- **Server**: 455Mi
- **Total**: ~1.3GB for observability
- **Action**: Evaluate if needed in production

---

## Recommendations

### High Priority

1. **Right-size Pods**
   - Frontend: 4Mi actual vs 128Mi requested → reduce to 64Mi
   - Monitor backend after restart for actual usage

2. **Enable HPA**
   ```yaml
   apiVersion: autoscaling/v2
   kind: HorizontalPodAutoscaler
   metadata:
     name: backend-hpa
   spec:
     minReplicas: 1
     maxReplicas: 3
     metrics:
     - type: Resource
       resource:
         name: cpu
         target:
           averageUtilization: 70
   ```

### Medium Priority

3. **Node Pool Optimization**
   - Move heavy workloads to memory-optimized node
   - Add node affinity/anti-affinity rules

4. **Langfuse Resource Review**
   - Consider scaling down if not heavily used
   - ClickHouse can run with less memory

---

## Data Collection Commands

```bash
# Set kubeconfig
export KUBECONFIG=~/.kube/config-ack-prod

# Pod metrics
kubectl top pods -n klinematrix-prod

# Node metrics
kubectl top nodes

# HPA status
kubectl get hpa -n klinematrix-prod

# Pod list
kubectl get pods -n klinematrix-prod
```

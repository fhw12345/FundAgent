# Feature: Admin Health Dashboard with Resource Metrics

> **Status**: Draft
> **Created**: 2025-10-08
> **Last Updated**: 2025-10-08
> **Owner**: Allen Pan

## Context

Before production launch, we need proper monitoring and administrative controls to ensure system health and security.

**User Story**:
As a system administrator, I want a comprehensive health dashboard to monitor resource usage and database statistics, so that I can proactively identify issues before they affect users.

**Background**:
- Current health endpoint is publicly accessible (security risk)
- No resource metrics (CPU, memory) visibility
- No database growth monitoring
- No favicon in browser tab (unprofessional)
- Production requires admin-only monitoring capabilities

**Business Impact**:
- Early detection of resource exhaustion
- Capacity planning for user growth
- Security: Prevent information disclosure
- Professional appearance (favicon)

## Problem Statement

**Current Pain Points**:
1. **No Access Control**: Anyone can view `/health` endpoint revealing system internals
2. **No Resource Visibility**: Cannot monitor CPU/memory usage without kubectl
3. **No Database Metrics**: Unknown database growth rate, collection sizes
4. **Missing Favicon**: Browser tab shows default icon (unprofessional)

**Success Metrics**:
- Admin can view comprehensive system metrics in <2 seconds
- Non-admin users cannot access health dashboard
- CPU/memory usage visible at pod and node level
- Database collection sizes tracked and sortable

## Proposed Solution

### High-Level Approach

1. **Access Control**: Implement admin role checking (username-based for MVP)
2. **Kubernetes Metrics**: Query metrics-server API for CPU/memory
3. **Database Statistics**: Aggregate MongoDB collection counts and sizes
4. **Enhanced UI**: Display metrics in organized dashboard
5. **Favicon**: Add professional icon to frontend

### Architecture Changes

**Backend Changes**:

```python
# New admin middleware
from functools import wraps
from fastapi import HTTPException, status

def require_admin(username: str) -> bool:
    """Check if user is admin (MVP: hardcoded username)"""
    return username == "allenpan"

def admin_required(func):
    @wraps(func)
    async def wrapper(*args, current_user: User = Depends(get_current_user), **kwargs):
        if not require_admin(current_user.username):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin access required"
            )
        return await func(*args, current_user=current_user, **kwargs)
    return wrapper
```

**New Data Models**:

```python
# backend/src/api/schemas/admin_models.py

class PodMetrics(BaseModel):
    """Pod resource usage metrics"""
    name: str
    cpu_usage: str  # e.g., "150m" (millicores)
    memory_usage: str  # e.g., "256Mi"
    cpu_percentage: float  # % of requested
    memory_percentage: float  # % of requested

class NodeMetrics(BaseModel):
    """Node resource usage metrics"""
    name: str
    cpu_usage: str
    memory_usage: str
    cpu_capacity: str
    memory_capacity: str
    cpu_percentage: float
    memory_percentage: float

class DatabaseStats(BaseModel):
    """Database collection statistics"""
    collection: str
    document_count: int
    size_bytes: int
    size_mb: float
    avg_document_size_bytes: int

class SystemMetrics(BaseModel):
    """Complete system metrics"""
    timestamp: datetime
    pods: list[PodMetrics]
    nodes: list[NodeMetrics]
    database: list[DatabaseStats]
    health_status: str  # "healthy" | "warning" | "critical"
```

**API Endpoints**:

```
GET  /api/admin/health          Get comprehensive system metrics (admin-only)
GET  /api/admin/metrics/pods    Get pod resource usage (admin-only)
GET  /api/admin/metrics/nodes   Get node resource usage (admin-only)
GET  /api/admin/metrics/database Get database statistics (admin-only)
```

### Technical Implementation Details

#### 1. Admin Access Control

**User Model Enhancement**:
```python
# backend/src/database/models/user.py
class User(BaseModel):
    username: str
    email: str
    hashed_password: str
    is_admin: bool = False  # Future: database-driven admin flag
    created_at: datetime

    @property
    def admin(self) -> bool:
        """Check admin status (MVP: hardcoded, Future: DB-driven)"""
        return self.username == "allenpan" or self.is_admin
```

**Frontend Route Protection**:
```typescript
// frontend/src/components/Layout.tsx
const Layout = () => {
  const { user } = useAuth();
  const isAdmin = user?.username === 'allenpan';

  return (
    <nav>
      {isAdmin && (
        <NavLink to="/health">Health</NavLink>
      )}
      {/* other nav items */}
    </nav>
  );
};
```

#### 2. Kubernetes Metrics Integration

**Challenge**: Access Kubernetes metrics from inside pod without exposing cluster credentials

**Solution**: Use in-cluster config with RBAC permissions

```yaml
# .pipeline/k8s/base/backend/serviceaccount.yaml
apiVersion: v1
kind: ServiceAccount
metadata:
  name: backend-sa
---
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: metrics-reader
rules:
- apiGroups: ["metrics.k8s.io"]
  resources: ["pods", "nodes"]
  verbs: ["get", "list"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: backend-metrics-reader
subjects:
- kind: ServiceAccount
  name: backend-sa
roleRef:
  kind: Role
  name: metrics-reader
  apiGroup: rbac.authorization.k8s.io
```

**Backend Implementation**:
```python
# backend/src/services/kubernetes_metrics.py
from kubernetes import client, config
from kubernetes.client.rest import ApiException

class KubernetesMetricsService:
    def __init__(self):
        try:
            # Load in-cluster config when running in K8s
            config.load_incluster_config()
        except config.ConfigException:
            # Fallback to kubeconfig for local development
            config.load_kube_config()

        self.core_api = client.CoreV1Api()
        self.custom_api = client.CustomObjectsApi()

    async def get_pod_metrics(self, namespace: str = "klinematrix-test") -> list[PodMetrics]:
        """Get CPU and memory usage for all pods"""
        try:
            # Query metrics-server API
            metrics = self.custom_api.list_namespaced_custom_object(
                group="metrics.k8s.io",
                version="v1beta1",
                namespace=namespace,
                plural="pods"
            )

            pod_metrics = []
            for item in metrics.get("items", []):
                containers = item.get("containers", [])
                total_cpu = sum(self._parse_cpu(c["usage"]["cpu"]) for c in containers)
                total_memory = sum(self._parse_memory(c["usage"]["memory"]) for c in containers)

                pod_metrics.append(PodMetrics(
                    name=item["metadata"]["name"],
                    cpu_usage=f"{total_cpu}m",
                    memory_usage=f"{total_memory}Mi",
                    cpu_percentage=self._calculate_percentage(total_cpu, "cpu"),
                    memory_percentage=self._calculate_percentage(total_memory, "memory")
                ))

            return pod_metrics
        except ApiException as e:
            logger.error(f"Failed to get pod metrics: {e}")
            return []

    def _parse_cpu(self, cpu_str: str) -> int:
        """Parse CPU string to millicores (e.g., '150m' -> 150, '1.5' -> 1500)"""
        if cpu_str.endswith('n'):
            return int(cpu_str[:-1]) // 1_000_000
        elif cpu_str.endswith('m'):
            return int(cpu_str[:-1])
        else:
            return int(float(cpu_str) * 1000)

    def _parse_memory(self, mem_str: str) -> int:
        """Parse memory string to MiB (e.g., '256Mi' -> 256, '1Gi' -> 1024)"""
        units = {'Ki': 1/1024, 'Mi': 1, 'Gi': 1024, 'Ti': 1024*1024}
        for suffix, multiplier in units.items():
            if mem_str.endswith(suffix):
                return int(int(mem_str[:-2]) * multiplier)
        # Assume bytes if no suffix
        return int(mem_str) // (1024 * 1024)
```

#### 3. Database Statistics

**MongoDB Aggregation**:
```python
# backend/src/services/database_stats.py
from motor.motor_asyncio import AsyncIOMotorDatabase

class DatabaseStatsService:
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db

    async def get_collection_stats(self) -> list[DatabaseStats]:
        """Get statistics for all collections"""
        collection_names = await self.db.list_collection_names()
        stats = []

        for name in collection_names:
            collection = self.db[name]

            # Get document count
            count = await collection.count_documents({})

            # Get collection stats (size, avg doc size)
            coll_stats = await self.db.command("collStats", name)

            stats.append(DatabaseStats(
                collection=name,
                document_count=count,
                size_bytes=coll_stats.get("size", 0),
                size_mb=coll_stats.get("size", 0) / (1024 * 1024),
                avg_document_size_bytes=coll_stats.get("avgObjSize", 0)
            ))

        # Sort by size (largest first)
        stats.sort(key=lambda x: x.size_bytes, reverse=True)
        return stats
```

#### 4. Frontend Health Dashboard

**Enhanced Health Page**:
```typescript
// frontend/src/pages/HealthPage.tsx
interface SystemMetrics {
  timestamp: string;
  pods: PodMetric[];
  nodes: NodeMetric[];
  database: DatabaseStat[];
  health_status: 'healthy' | 'warning' | 'critical';
}

const HealthPage = () => {
  const { data: metrics, isLoading } = useQuery<SystemMetrics>(
    'system-metrics',
    () => api.get('/admin/health').then(r => r.data),
    { refetchInterval: 10000 } // Refresh every 10s
  );

  if (isLoading) return <LoadingSpinner />;

  return (
    <div className="p-6">
      <h1 className="text-2xl font-bold mb-6">System Health Dashboard</h1>

      {/* Overall Status */}
      <StatusBadge status={metrics.health_status} />

      {/* Resource Metrics */}
      <section className="mb-8">
        <h2 className="text-xl font-semibold mb-4">Resource Usage</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {metrics.pods.map(pod => (
            <PodMetricCard key={pod.name} pod={pod} />
          ))}
        </div>
      </section>

      {/* Database Statistics */}
      <section>
        <h2 className="text-xl font-semibold mb-4">Database Collections</h2>
        <table className="w-full border">
          <thead>
            <tr className="bg-gray-100">
              <th className="p-2">Collection</th>
              <th className="p-2">Documents</th>
              <th className="p-2">Size (MB)</th>
              <th className="p-2">Avg Doc Size</th>
            </tr>
          </thead>
          <tbody>
            {metrics.database.map(stat => (
              <tr key={stat.collection} className="border-t">
                <td className="p-2 font-mono">{stat.collection}</td>
                <td className="p-2 text-right">{stat.document_count.toLocaleString()}</td>
                <td className="p-2 text-right">{stat.size_mb.toFixed(2)}</td>
                <td className="p-2 text-right">{formatBytes(stat.avg_document_size_bytes)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </div>
  );
};
```

#### 5. Favicon Implementation

**Assets**:
```bash
# Generate favicon set (use online tool or design software)
frontend/public/
  ├── favicon.ico           # 32x32, 16x16 multi-size
  ├── favicon-16x16.png
  ├── favicon-32x32.png
  ├── apple-touch-icon.png  # 180x180 for iOS
  └── site.webmanifest      # PWA manifest
```

**HTML Update**:
```html
<!-- frontend/index.html -->
<head>
  <link rel="icon" type="image/x-icon" href="/favicon.ico">
  <link rel="icon" type="image/png" sizes="32x32" href="/favicon-32x32.png">
  <link rel="icon" type="image/png" sizes="16x16" href="/favicon-16x16.png">
  <link rel="apple-touch-icon" sizes="180x180" href="/apple-touch-icon.png">
  <link rel="manifest" href="/site.webmanifest">
</head>
```

## Implementation Plan

### Phase 1: Access Control & Favicon (2-3 hours)
- [ ] Add favicon assets to frontend/public/
- [ ] Update index.html with favicon links
- [ ] Create admin middleware in backend
- [ ] Protect health endpoints with @admin_required
- [ ] Add frontend route guard for /health
- [ ] Hide health nav item for non-admin users
- [ ] Test admin access control

### Phase 2: Kubernetes Metrics (4-6 hours)
- [ ] Add kubernetes Python client dependency
- [ ] Create RBAC ServiceAccount and Role
- [ ] Implement KubernetesMetricsService
- [ ] Add /api/admin/metrics/pods endpoint
- [ ] Add /api/admin/metrics/nodes endpoint
- [ ] Test metrics collection in dev cluster
- [ ] Handle metrics-server unavailable gracefully

### Phase 3: Database Statistics (2-3 hours)
- [ ] Implement DatabaseStatsService
- [ ] Add /api/admin/metrics/database endpoint
- [ ] Test with production-like data volumes
- [ ] Add caching for expensive stats queries
- [ ] Sort collections by size descending

### Phase 4: Frontend Dashboard (4-6 hours)
- [ ] Create SystemMetrics TypeScript interfaces
- [ ] Implement HealthPage with resource cards
- [ ] Add pod metrics visualization
- [ ] Add database statistics table
- [ ] Add auto-refresh (10s interval)
- [ ] Add loading and error states
- [ ] Style with TailwindCSS

### Phase 5: Testing & Polish (2-3 hours)
- [ ] Test admin vs non-admin access
- [ ] Test with high CPU/memory usage
- [ ] Test with large database collections
- [ ] Verify RBAC permissions in cluster
- [ ] Add error handling for metrics failures
- [ ] Update documentation

**Total Estimated Effort**: 14-21 hours (~2-3 days)

## Acceptance Criteria

- [ ] **Favicon**:
  - [ ] Favicon appears in browser tab
  - [ ] Icon works on Chrome, Firefox, Safari
  - [ ] Apple touch icon works on iOS

- [ ] **Access Control**:
  - [ ] Health page only accessible to admin (username: allenpan)
  - [ ] Non-admin receives 403 Forbidden on health endpoints
  - [ ] Health nav item hidden for non-admin users
  - [ ] Logged-out users cannot access health page

- [ ] **Resource Metrics**:
  - [ ] Display CPU usage for all pods (millicores and %)
  - [ ] Display memory usage for all pods (MiB and %)
  - [ ] Display node-level CPU and memory
  - [ ] Metrics auto-refresh every 10 seconds
  - [ ] Graceful degradation if metrics-server unavailable

- [ ] **Database Statistics**:
  - [ ] Show document count for each collection
  - [ ] Show size in MB for each collection
  - [ ] Collections sorted by size (largest first)
  - [ ] Average document size displayed
  - [ ] Stats update on page refresh

- [ ] **Technical Requirements**:
  - [ ] All tests passing
  - [ ] RBAC configured for metrics access
  - [ ] Error handling for K8s API failures
  - [ ] No performance degradation (<200ms response time)

## Testing Strategy

**Unit Tests**:
- Admin middleware: Test username validation
- KubernetesMetricsService: Test CPU/memory parsing
- DatabaseStatsService: Test aggregation logic
- Frontend: Test conditional rendering

**Integration Tests**:
- End-to-end admin login → health page access
- Metrics collection from real cluster
- Database stats with test data

**Manual Testing**:
1. Login as admin → verify health page visible
2. Login as regular user → verify health page hidden
3. Check pod metrics match `kubectl top pods`
4. Verify database stats accuracy
5. Test auto-refresh behavior
6. Test favicon on multiple browsers/devices

## Security Considerations

**Access Control**:
- Admin check must be server-side (not just frontend hiding)
- JWT token must contain user identity for admin verification
- Consider rate limiting on admin endpoints

**Information Disclosure**:
- Health metrics reveal infrastructure details (pod names, sizes)
- Only expose to trusted admins
- Sanitize error messages (no stack traces to non-admin)

**RBAC Permissions**:
- Minimal permissions: only `get/list` on metrics
- No write access to cluster resources
- Namespace-scoped (not cluster-wide)

**Future Enhancement**:
- Database-driven admin roles (not hardcoded username)
- Audit logging for admin actions
- IP allowlist for admin endpoints

## Performance Considerations

**Kubernetes API Calls**:
- Metrics queries are relatively fast (<100ms)
- Cache metrics for 5-10 seconds to reduce API load
- Use async/await for parallel queries

**Database Stats**:
- `collStats` command can be slow on large collections
- Cache results for 30-60 seconds
- Consider background job for expensive aggregations

**Frontend**:
- Lazy load health page (code splitting)
- Debounce auto-refresh if user navigates away
- Use React Query caching

**Expected Load**:
- Single admin user checking dashboard
- ~1 request per 10 seconds
- Negligible impact on system performance

## Rollout Strategy

**Development**:
1. Implement on local development cluster
2. Test with kubectl port-forward
3. Verify metrics accuracy

**Test Environment**:
1. Deploy RBAC changes first
2. Deploy backend with admin endpoints
3. Deploy frontend with updated health page
4. Test with real metrics-server data

**Production**:
1. Feature flag: `ADMIN_HEALTH_ENABLED=true`
2. Deploy during low-traffic window
3. Monitor for errors in logs
4. Verify admin can access, regular users cannot

**Rollback Plan**:
- If admin endpoints fail → disable feature flag
- If metrics errors → return cached/mock data
- If RBAC issues → revert to previous ServiceAccount

## Open Questions

1. **Icon Design**: Use stock icon or custom design?
   - **Decision**: Use simple stock finance icon (chart/graph), custom design later

2. **Metrics Retention**: Should we store historical metrics?
   - **Decision**: No for MVP, just real-time data. Add Prometheus later for history.

3. **Alert Thresholds**: When to show "warning" vs "critical" status?
   - **Decision**: Warning: >70% CPU/memory, Critical: >90%

4. **Multiple Admins**: How to add more admin users?
   - **Decision**: Hardcoded list for MVP, database field in Phase 2

## Dependencies

- **kubernetes**: Python client library (~10MB)
- **motor**: Already installed (MongoDB async driver)
- **React Query**: Already installed (frontend state management)

**Infrastructure**:
- metrics-server must be running in cluster (already enabled in AKS)
- RBAC must be enabled (already enabled)

## Risks and Mitigations

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| metrics-server unavailable | High | Low | Return cached data + error message |
| Kubernetes RBAC misconfiguration | High | Medium | Test thoroughly in dev, have rollback ready |
| Database stats query slow | Medium | Medium | Add caching, timeout queries at 5s |
| Hardcoded admin username inflexible | Low | High | Document plan to migrate to DB field |
| Favicon not loading | Low | Low | Test across browsers, use fallback |

## References

- [Kubernetes Metrics API](https://kubernetes.io/docs/tasks/debug/debug-cluster/resource-metrics-pipeline/)
- [MongoDB collStats](https://www.mongodb.com/docs/manual/reference/command/collStats/)
- [Favicon Best Practices](https://evilmartians.com/chronicles/how-to-favicon-in-2021-six-files-that-fit-most-needs)
- Backend auth: `backend/src/api/dependencies/auth_deps.py`
- Frontend auth: `frontend/src/hooks/useAuth.ts`

---

## Change Log

- **2025-10-08**: Initial draft - comprehensive admin health dashboard spec

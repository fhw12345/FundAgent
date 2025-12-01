# Langfuse Observability

> **Last Updated**: 2025-11-29 | **Status**: Production Deployed

## Overview

Langfuse provides LLM observability for the financial agent, tracking agent executions, tool calls, and LLM interactions. This guide covers setup, deployment, and debugging workflows.

## Deployment Status

| Environment | URL | Status |
|-------------|-----|--------|
| **Production (ACK)** | https://monitor.klinecubic.cn | ✅ DEPLOYED |
| **Local Dev** | http://localhost:3001 | ✅ AVAILABLE |

## Version Compatibility

**Current Production Setup**: Langfuse Python SDK v3.10.1 + Langfuse Server v3.135.0 ✅ **VERIFIED WORKING**

| Component | Version | Environment | Status |
|-----------|---------|-------------|--------|
| **Langfuse Python SDK** | v3.10.1 | All | ✅ VERIFIED (2025-11-29) |
| **Langfuse Server** | v3.135.0 | Production | ✅ VERIFIED (2025-11-29) |
| **ClickHouse** | v24.1-alpine | All | ✅ REQUIRED (analytics/OLAP) |
| **PostgreSQL** | v15-alpine | All | ✅ REQUIRED (metadata storage) |
| **Alibaba OSS** | - | Production | ✅ REQUIRED (event backup) |
| **MinIO** | latest | Local Dev | ✅ REQUIRED (S3-compatible) |
| **Redis** | v7.2-alpine | All | ✅ REQUIRED (queue management) |

### Architecture (v3.x)

**SDK v3.x uses OpenTelemetry/OTLP with native ingestion fallback**:

```
SDK v3.x Architecture:
├─ Primary: OpenTelemetry SDK → OTLP HTTP Exporter
├─ Fallback: Native ingestion API (/api/public/ingestion)
└─ @observe decorators → OTLP → Langfuse Server → Storage

Langfuse Server v3.x Architecture:
├─ OTLP ingestion: /v1/traces (OpenTelemetry endpoint)
├─ Native ingestion API: /api/public/ingestion (fallback)
├─ Redis: Queue management (REQUIRED for worker processing)
├─ Worker: Background job processing (ingestion, analytics)
├─ PostgreSQL: Metadata storage (users, projects, API keys, trace metadata)
├─ ClickHouse: Analytics storage (OLAP queries, observations, scores)
└─ MinIO: S3-compatible blob storage (REQUIRED for event persistence)
```

**Infrastructure Requirements for v3.x**:
- **Redis**: Queue management for async worker processing
- **PostgreSQL**: Trace metadata, user/project data
- **ClickHouse**: High-performance analytics queries
- **MinIO**: Event blob storage (mandatory, cannot be disabled)

## Access Points

### Production (ACK - Alibaba Cloud)

**Langfuse UI** - https://monitor.klinecubic.cn
- View LLM traces and observations
- Analyze agent execution flow
- Query trace data
- Monitor token usage and costs
- First user to sign up becomes admin

**Backend Integration**: Traces are automatically sent from https://klinecubic.cn

**Infrastructure**:
- PostgreSQL: In-cluster (`langfuse-postgres:5432`)
- ClickHouse: In-cluster (`langfuse-clickhouse:8123`)
- Redis: Shared with backend (`redis-service:6379`)
- OSS: `klinecubic-financialagent-oss` bucket, prefix `langfuse-events/`

**Secrets Required** (see [secrets-architecture.md](../deployment/secrets-architecture.md)):
- `langfuse-secrets`: postgres-password, clickhouse-password, nextauth-secret, salt, oss-access-key-id, oss-access-key-secret
- `backend-secrets`: langfuse-public-key, langfuse-secret-key

### Local Development

**Langfuse UI** - http://localhost:3001
- View LLM traces and observations
- Analyze agent execution flow
- Query trace data
- Monitor token usage and costs

**MinIO Console** - http://localhost:9003
- Manage S3-compatible blob storage
- View event files in `langfuse-events` bucket
- Monitor storage usage
- Default credentials: `minioadmin` / `minioadmin`

**ClickHouse** - localhost:8123 (HTTP), localhost:9000 (Native)
- Analytics/OLAP queries
- Access via `clickhouse-client` in container
- View traces and observations tables

**PostgreSQL** - localhost:5432
- Metadata storage (users, projects, API keys)
- Access via `psql` in container
- Database: `langfuse`

## Setup Instructions

### 1. SDK Version (v3.x)

Update `backend/pyproject.toml`:

```toml
dependencies = [
    "langfuse>=3.0.0,<4.0.0",  # v3.x with OTLP support (requires ClickHouse)
]
```

### 2. Install Correct Version

```bash
# Inside backend container
pip install 'langfuse>=3.0.0,<4.0.0'

# Verify version
pip show langfuse | grep Version
# Should output: Version: 3.x.x
```

### 3. Configure Environment Variables

`backend/.env.development`:

```bash
# Langfuse Observability (local dev)
LANGFUSE_PUBLIC_KEY=pk-lf-8b770ac7-31c5-4bee-bbb1-bec2172a76eb
LANGFUSE_SECRET_KEY=sk-lf-c2cb097e-8182-46d1-a77b-572aeb770bdd
LANGFUSE_HOST=http://langfuse-server:3000
```

**Note**: Ensure ClickHouse is running (required for v3.x analytics backend).

### 4. Code Integration Pattern (v3.x)

```python
from langfuse import Langfuse, observe

# Initialize global client (once per module)
Langfuse(
    public_key=settings.langfuse_public_key,
    secret_key=settings.langfuse_secret_key,
    host=settings.langfuse_host,
)

# Use @observe decorators (auto-traces to global client)
@observe(name="my_function")
async def my_function():
    return "traced"

# Flush handled automatically (or call flush() if needed)
```

**SDK v3.x Pattern**: Global initialization, no manual client management needed.

## Common Issues

### Issue 1: Traces Not Appearing in Database

**Symptoms**:
- `flush()` succeeds without errors
- Database query shows 0 traces: `SELECT COUNT(*) FROM traces; → 0`
- No API requests to Langfuse server in logs

**Debugging Steps**:

1. **Check SDK version**:
```bash
docker compose exec backend pip show langfuse | grep Version
```
Should show v3.x.x for current setup.

2. **Check ClickHouse is running**:
```bash
docker compose ps langfuse-clickhouse
# Should show "Up" status
```
If ClickHouse is down, traces won't persist.

3. **Test API directly**:
```bash
docker compose exec backend curl -X POST http://langfuse-server:3000/api/public/ingestion \
  -u "pk-lf-...:sk-lf-..." \
  -H "Content-Type: application/json" \
  -d '{
    "batch": [{
      "id": "test-123",
      "type": "trace-create",
      "timestamp": "2025-10-20T14:00:00.000Z",
      "body": {"id": "test-123", "name": "test"}
    }]
  }'
```
Should return: `{"successes":[{"id":"test-123","status":201}],"errors":[]}`

4. **Verify database**:
```bash
docker compose exec langfuse-postgres psql -U langfuse -d langfuse \
  -c "SELECT id, name, created_at FROM traces ORDER BY created_at DESC LIMIT 5;"
```

**Fix**: Ensure ClickHouse is running and SDK v3.x is installed correctly.

### Issue 2: ClickHouse Connection Errors

**Error**:
```
ClickHouse connection refused / timeout
```

**Cause**: ClickHouse service not running or network issue

**Fix**:
```bash
# Check ClickHouse status
docker compose logs langfuse-clickhouse --tail=50

# Restart if needed
docker compose restart langfuse-clickhouse

# Verify health
docker compose exec langfuse-clickhouse wget -q -O- http://localhost:8123/ping
# Should return: Ok.
```

### Issue 3: Authentication Error (401)

**Error**:
```json
{"errors":[{"status":401,"message":"Authentication error","error":"Access Scope Denied"}]}
```

**Cause**: Using public key in Authorization header instead of basic auth

**Fix**: Use basic auth with both keys:
```bash
curl -u "PUBLIC_KEY:SECRET_KEY" ...
```

### Issue 4: Empty Traces with Valid API Calls

**Symptom**: API returns 201 success but traces have no observations

**Cause**: @observe decorators not creating observations in SDK v2.x context

**Fix**: Verify decorator placement and ensure client is initialized before decorated functions are called.

## Verification Workflow

After setup, verify the integration works:

1. **Send test trace**:
```python
from langfuse import Langfuse
import os

client = Langfuse(
    public_key=os.getenv('LANGFUSE_PUBLIC_KEY'),
    secret_key=os.getenv('LANGFUSE_SECRET_KEY'),
    host=os.getenv('LANGFUSE_HOST'),
)

# Create trace
span = client.start_span(name='test_verification')
span.update(input='test', output='success')
span.end()
client.flush()
```

2. **Check database**:
```sql
SELECT COUNT(*) FROM traces WHERE name = 'test_verification';
```
Should return: `1`

3. **Check Langfuse portal**:
- Navigate to http://localhost:3001 (dev) or https://monitor.klinecubic.cn (prod)
- Select your project
- Should see trace in dashboard

## Architecture Notes

### Production Architecture (v3.x)

```
┌─────────────────────────────────────────────┐
│  Backend (FastAPI) - klinecubic.cn          │
│  ┌──────────────────────────────────────┐  │
│  │  LangGraph Agent                     │  │
│  │  ├─ @observe(reasoning_node)         │  │
│  │  ├─ @observe(tool_execution)         │  │
│  │  └─ @observe(synthesis_node)         │  │
│  └──────────────────────────────────────┘  │
│              │                              │
│              │ Langfuse SDK v3.10.1        │
│              │ (OTLP + Native API)         │
│              ▼                              │
└─────────────────────────────────────────────┘
              │
              │ HTTP POST (in-cluster)
              │ http://langfuse-server:3000
              ▼
┌─────────────────────────────────────────────┐
│  Langfuse Server v3.135.0                   │
│  monitor.klinecubic.cn                      │
│  ┌──────────────────────────────────────┐  │
│  │  Ingestion API                       │  │
│  │  ├─ /v1/traces (OTLP)               │  │
│  │  └─ /api/public/ingestion (native)  │  │
│  └──────────────────────────────────────┘  │
│              │                              │
│              ▼                              │
│  ┌────────────┐  ┌───────────────────────┐ │
│  │ PostgreSQL │  │ ClickHouse            │ │
│  │ (metadata) │  │ (analytics/traces)    │ │
│  └────────────┘  └───────────────────────┘ │
│              │                              │
│              ▼                              │
│  ┌──────────────────────────────────────┐  │
│  │  Alibaba OSS (event backup)          │  │
│  │  klinecubic-financialagent-oss       │  │
│  │  /langfuse-events/                   │  │
│  └──────────────────────────────────────┘  │
└─────────────────────────────────────────────┘
```

### K8s Resources (Production)

| Resource | Type | Purpose |
|----------|------|---------|
| `langfuse-server` | Deployment | Web UI + API |
| `langfuse-worker` | Deployment | Background processing |
| `langfuse-postgres` | Deployment | Metadata storage |
| `langfuse-clickhouse` | Deployment | Analytics OLAP |
| `langfuse-ingress` | Ingress | TLS termination |

**Note**: Uses emptyDir for storage (data loss on pod restart). Consider PVC when budget allows.

## Related Documentation

- **Feature Spec**: [docs/features/langgraph-agent-dual-observability.md](../features/langgraph-agent-dual-observability.md)
- **System Design**: [docs/architecture/system-design.md](../architecture/system-design.md)
- **Deployment Issues**: [docs/troubleshooting/deployment-issues.md](./deployment-issues.md)
- **Fixed Bugs**: [docs/troubleshooting/fixed-bugs.md](./fixed-bugs.md)

## Support

If traces still don't appear after following this guide:

1. Check Langfuse server logs: `docker compose logs langfuse-server --tail 100`
2. Check PostgreSQL: `docker compose exec langfuse-postgres psql -U langfuse -d langfuse`
3. Verify network connectivity: `docker compose exec backend curl http://langfuse-server:3000/api/health`
4. Review backend logs for flush errors: `docker compose logs backend | grep Langfuse`

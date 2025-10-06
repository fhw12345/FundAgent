# Financial Agent - Development Guide

> **RULE**: Only concise, actionable rules here. No details, no repetition. See [docs/](docs/) for comprehensive documentation.

## 📚 Documentation Index

### Quick Links
- **[Getting Started](docs/development/getting-started.md)** - Local setup, first deployment
- **[Deployment Workflow](docs/deployment/workflow.md)** - Deploy changes to production
- **[Coding Standards](docs/development/coding-standards.md)** - Python/TypeScript patterns
- **[System Design](docs/architecture/system-design.md)** - Architecture overview

### Complete Documentation Structure

```
docs/
├── architecture/           # System design and patterns
│   ├── agent-12-factors.md      # 12-Factor agent principles
│   ├── agent-architecture.md    # LangChain/LangGraph implementation
│   └── system-design.md         # Tech stack & architecture
│
├── deployment/            # Production deployment
│   ├── cloud-setup.md          # Azure + Alibaba hybrid cloud
│   ├── infrastructure.md       # Kubernetes resources & topology
│   └── workflow.md             # Deploy, verify, rollback procedures
│
├── development/           # Local development
│   ├── getting-started.md      # Quick start guide
│   ├── coding-standards.md     # Code patterns & debugging
│   ├── pipeline-workflow.md    # CI/CD & testing
│   └── verification.md         # Health checks & validation
│
├── project/              # Project management
│   ├── specifications.md       # Requirements & roadmap
│   └── versions/              # 📦 Version management
│       ├── README.md              # Versioning guidelines
│       ├── VERSION_MATRIX.md      # Compatibility matrix
│       ├── backend/CHANGELOG.md   # Backend version history
│       └── frontend/CHANGELOG.md  # Frontend version history
│
└── troubleshooting/      # 🐛 Bug fixes & common issues
    ├── README.md                   # Troubleshooting index
    ├── cors-api-connectivity.md    # CORS & API issues
    ├── data-validation-issues.md   # Validation errors
    ├── deployment-issues.md        # Kubernetes issues
    └── known-bugs.md              # Current bugs & status
```

## Tech Stack

| Layer | Technology |
|-------|-----------|
| **Backend** | Python 3.12 + FastAPI + MongoDB + Redis |
| **Frontend** | React 18 + TypeScript 5 + Vite + TailwindCSS |
| **Deployment** | Kubernetes (AKS) + Azure + Alibaba Cloud |
| **AI/LLM** | LangChain + LangGraph + Alibaba DashScope |
| **Tooling** | Black, Ruff, MyPy (Python) \| ESLint, Prettier (TS) |

## Development Workflow

### 1. Make Changes Locally
```bash
# Backend changes
cd backend && make test && make lint

# Frontend changes
cd frontend && npm test && npm run lint
```

### 2. Bump Version (Required)
```bash
# Every commit must increment at least one version
./scripts/bump-version.sh backend patch   # 0.1.0 → 0.1.1
./scripts/bump-version.sh frontend minor  # 0.1.0 → 0.2.0

# Pre-commit hook validates version increment
```

### 3. Deploy to Dev
```bash
# Build versioned images in Azure Container Registry
BACKEND_VERSION=$(grep '^version = ' backend/pyproject.toml | sed 's/version = "\(.*\)"/\1/')

az acr build --registry financialAgent \
  --image financial-agent/backend:${BACKEND_VERSION}-dev \
  --file backend/Dockerfile backend/

# Restart pods (with imagePullPolicy: Always)
kubectl delete pod -l app=backend -n financial-agent-dev
```

### 4. Verify
```bash
# Check deployment
kubectl get pods -n financial-agent-dev

# Test endpoints
curl https://klinematrix.com/api/health
```

**See [docs/deployment/workflow.md](docs/deployment/workflow.md) for complete procedures**
**See [docs/project/versions/README.md](docs/project/versions/README.md) for versioning system**

## Code Standards

### Python
- Modern syntax: `|` unions, `match/case`, f-strings, `@dataclass`
- Type hints: All functions typed
- Docstrings: Required for all modules, classes, functions
- Max file size: 500 lines (split into modules)

### TypeScript
- ES modules, optional chaining, `satisfies` operator
- Strict mode enabled
- Components: Functional with hooks
- State: React Query for server state, useState for UI state

### Quality Gates
```bash
make fmt && make test && make lint  # Must pass before commit
```

**See [docs/development/coding-standards.md](docs/development/coding-standards.md) for patterns & debugging**

## Common Patterns & Debugging

### API Validation Pattern
```python
# ✅ Validate symbols before suggesting
ticker = yf.Ticker(symbol)
history = ticker.history(period="5d")
if history.empty:
    raise ValueError(f"No data available for {symbol}")
```

### React Closure Trap Fix
```typescript
// ❌ Closure captures stale state
const mutation = useMutation({
  mutationFn: () => api.analyze(symbol)  // symbol is stale!
});

// ✅ Pass state explicitly
const mutation = useMutation({
  mutationFn: ({ symbol, timeframe }) =>
    api.analyze({ symbol, timeframe })
});
```

### Data Contract Synchronization
```python
# Backend Pydantic
class Analysis(BaseModel):
    interval: Literal["1d", "1h", "5m"]  # Add new value here

# Frontend TypeScript
type Interval = "1d" | "1h" | "5m"      // Must match exactly

# User parsing - handle new format
if "1 hour" in message: interval = "1h"
```

**422 errors** → Backend rejects frontend data (check contracts)
**Silent fallbacks** → Frontend parsing fails (check user input handlers)

### Docker Hot Reload

**Restart Required ❌**
- New dependencies (`pip install`, `npm install`)
- Module-level changes (DB connections, decorators)
- Docker config (docker-compose.yml, Dockerfile)

**Hot Reload Works ✅**
- Function logic, new routes, UI changes
- ~90% of development changes

**Test**: `print(f"🔄 Code updated: {datetime.now()}")` - No print = restart needed

## Project Methodology

### Walking Skeleton Approach
1. **Milestone 1**: End-to-end connectivity (Frontend → API → DB → Cache) ✅
2. **Milestone 2**: Authentication + core business logic ✅
3. **Milestone 3+**: Layer features incrementally 🚧

**See [docs/development/verification.md](docs/development/verification.md) for validation procedures**

## Key Resources

### Architecture & Design
- [12-Factor Agent Principles](docs/architecture/agent-12-factors.md)
- [LangChain Implementation](docs/architecture/agent-architecture.md)
- [System Design Overview](docs/architecture/system-design.md)

### Deployment & Operations
- [Cloud Setup Guide](docs/deployment/cloud-setup.md) - Azure + Alibaba hybrid
- [Kubernetes Infrastructure](docs/deployment/infrastructure.md) - Resources, networking
- [Deployment Workflow](docs/deployment/workflow.md) - Build, deploy, verify, rollback

### Development
- [Getting Started](docs/development/getting-started.md) - Local setup
- [Coding Standards](docs/development/coding-standards.md) - Patterns & debugging
- [CI/CD Pipeline](docs/development/pipeline-workflow.md) - Automated testing
- [Verification Guide](docs/development/verification.md) - Health checks

### Project Management
- [Technical Specifications](docs/project/specifications.md) - Features & roadmap
- [Versioning System](docs/project/versions/README.md) - Version management & workflow
- [Version Matrix](docs/project/versions/VERSION_MATRIX.md) - Component compatibility

### Troubleshooting
- [Troubleshooting Index](docs/troubleshooting/README.md) - Bug fixes & common issues
- [CORS & API Issues](docs/troubleshooting/cors-api-connectivity.md) - Connection problems
- [Data Validation](docs/troubleshooting/data-validation-issues.md) - Pydantic errors
- [Deployment Issues](docs/troubleshooting/deployment-issues.md) - Kubernetes problems
- [Known Bugs](docs/troubleshooting/known-bugs.md) - Current open issues

## Quick Reference Commands

```bash
# Local Development
make test           # Run all tests
make fmt            # Format code
make lint           # Check code quality
docker-compose up   # Start local services (deprecated - use kubectl)

# Kubernetes Deployment
kubectl get pods -n financial-agent-dev                    # Check status
kubectl logs -f deployment/backend -n financial-agent-dev  # View logs
kubectl delete pod -l app=backend -n financial-agent-dev   # Restart with new image

# Build Images
az acr build --registry financialAgent --image financial-agent/backend:dev-latest --file backend/Dockerfile backend/
az acr build --registry financialAgent --image financial-agent/frontend:dev-latest --target production --file frontend/Dockerfile frontend/

# Health Checks
curl https://klinematrix.com/api/health
```

## Important Reminders

### ⚠️ Before Committing
- [ ] Run `make fmt && make test && make lint`
- [ ] **Bump version** (required): `./scripts/bump-version.sh [component] [patch|minor|major]`
- [ ] Check data contracts (Pydantic ↔ TypeScript)
- [ ] Verify no secrets in code
- [ ] Test locally first

### 🚀 Before Deploying
- [ ] Build images in ACR
- [ ] Restart pods (auto-pulls new images)
- [ ] Check pod status (1/1 Running)
- [ ] Test health endpoints
- [ ] Monitor logs for 5-10 minutes

### 🔍 When Debugging
1. Check pod logs first
2. Verify data contracts alignment
3. Test backend directly (kubectl exec)
4. Check Redis cache if caching issues
5. Review External Secrets sync

---

**For detailed information, see the [complete documentation](docs/).**

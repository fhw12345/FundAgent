# Financial Agent - Development Guide

> **RULE**: Only concise, actionable rules here. No details, no repetition. See [docs/](docs/) for comprehensive documentation.

## Tech Stack

| Layer | Technology |
|-------|-----------|
| **Backend** | Python 3.12 + FastAPI + MongoDB + Redis |
| **Frontend** | React 18 + TypeScript 5 + Vite + TailwindCSS |
| **Deployment** | Kubernetes (AKS) + Azure + Alibaba Cloud |
| **AI/LLM** | LangChain + LangGraph + Alibaba DashScope |

> 📖 **See [System Design](docs/architecture/system-design.md) for architecture details**

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

### 3. Deploy to Test
```bash
# Build versioned images in Azure Container Registry
BACKEND_VERSION=$(grep '^version = ' backend/pyproject.toml | sed 's/version = "\(.*\)"/\1/')

az acr build --registry financialAgent \
  --image klinematrix/backend:test-v${BACKEND_VERSION} \
  --file backend/Dockerfile backend/

# Restart pods to pull new image (imagePullPolicy: Always)
kubectl delete pod -l app=backend -n klinematrix-test
```

### 4. Verify
```bash
# Check deployment status
kubectl get pods -n klinematrix-test

# Test health endpoint
curl https://klinematrix.com/api/health
```

> 📖 **See [Deployment Workflow](docs/deployment/workflow.md) for complete procedures (build, deploy, verify, rollback)**
> 📖 **See [Version Management](docs/project/versions/README.md) for versioning system and workflow**

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

**See [docs/development/verification.md](docs/development/verification.md) for validation procedures**

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

### 💡 Development Principles
- **Find the root cause** - Don't fix symptoms, fix the underlying problem
- **Less code is more** - Simplest solution that works is usually correct
- **Avoid duplication** - Same logic in multiple places = bug waiting to happen
- **Don't overcomplicate** - Complex solutions are harder to debug and maintain
- **Compare environments** - When cloud differs from local, check config/credentials first

**Example**: Database name parsing bug existed in TWO places (config.py + mongodb.py). Fix once, extract to shared utility if needed.

---

**Before any actions, always get context by reading the [docs main page](docs/README.md).**

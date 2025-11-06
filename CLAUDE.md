# Financial Agent - Development Guide

> **RULE**: Only concise, actionable rules here. No details, no repetition. See [docs/](docs/) for comprehensive documentation.

## 🔐 Security Rules

**🚨 NEVER COMMIT SECRETS 🚨** - API keys, passwords, tokens, credentials, connection strings, certificates
- ✅ Use placeholders: `<REDACTED>`, `YOUR_SECRET_HERE`, `AKID*****`
- ✅ Store in Azure Key Vault, reference by name only
- ✅ Before commit: Run `git diff --staged`, scan for secrets/passwords/keys
- ❌ **GitHub Push Protection blocks secret commits → painful git history rewrite!**

## Tech Stack

| Layer | Technology |
|-------|-----------|
| **Backend** | Python 3.12 + FastAPI + MongoDB + Redis |
| **Frontend** | React 18 + TypeScript 5 + Vite + TailwindCSS |
| **Deployment** | Kubernetes (AKS) + Azure + Alibaba Cloud |
| **AI/LLM** | LangChain + LangGraph + Alibaba DashScope |

> 📖 **See [System Design](docs/architecture/system-design.md) for architecture details**

## 🌍 Environment Rules

**We have 3 environments with different deployment methods:**

| Environment | Deployment Method | Access | Purpose |
|-------------|------------------|--------|---------|
| **Dev/Local** | Docker Compose | `localhost:3000` | Local development on your machine |
| **Test** | Kubernetes (AKS) | `https://klinematrix.com` | Cloud testing environment |
| **Prod** | *(Not yet deployed)* | *(Planned)* | Production environment |

### Dev/Local Environment
- **How to run**: `make dev` (starts docker-compose)
- **Services**: Backend, Frontend, MongoDB, Redis, Langfuse Stack (all in containers)
- **Access Points**:
  - Frontend: http://localhost:3000
  - Backend API: http://localhost:8000
  - Langfuse UI: http://localhost:3001 (LLM trace visualization)
  - MinIO Console: http://localhost:9003 (S3 storage)
- **Frontend commands**: `docker compose exec frontend npm ...`
- **Backend commands**: `cd backend && make test && make lint`
- **Hot reload**: ✅ Works for 90% of changes
- **When to use**: Daily development, testing features locally

### Test Environment (Kubernetes)
- **How to deploy**: Build images → Push to ACR → Restart pods
- **Access**: https://klinematrix.com
- **Commands**: `kubectl get pods -n klinematrix-test`
- **When to use**: Testing before merging, verifying cloud integration
- **Note**: This is the ONLY cloud environment right now

### Prod Environment
- **Status**: Not yet deployed
- **Planned**: Will be separate K8s namespace with production data

**Golden Rule**: Develop locally with docker-compose, deploy to Test (K8s) for verification.

## 🧪 Testing & Iteration Rules

**When using webapp-testing skill for E2E testing:**

1. **Test First** - Run comprehensive E2E test to identify all issues
2. **Document Findings** - Write findings to `/tmp/webtesting/{scenario}/FINDINGS.md`
3. **Auto-Fix Loop** - Once testing complete, AUTOMATICALLY start fixing issues WITHOUT waiting for user prompt:
   ```
   WHILE issues exist:
     - Fix the issue in code
     - Restart affected services (docker compose restart)
     - Use Playwright/Chromium to trigger actions in UI
     - Re-run verification checks (logs + database + frontend)
     - IF new issues found: Add to list and continue
     - IF all checks pass: DONE
   ```
4. **No Manual Intervention** - Keep iterating until ALL checks pass (backend logs + database + frontend + APIs)
5. **Use Browser Automation** - Install playwright and use Chromium to:
   - Login with credentials (allenpan/admin123)
   - Navigate to features
   - Click buttons, trigger actions
   - Verify UI updates
6. **Verification Required** - After each fix, verify:
   - ✅ Backend logs show expected behavior
   - ✅ Database contains correct data
   - ✅ Frontend displays correctly
   - ✅ 3rd party APIs reflect changes

**Example:**
```
Test finds: Agent not being invoked
→ Fix: Inject agent into WatchlistAnalyzer
→ Restart: docker compose restart backend
→ Use Playwright: Login, click "Analyze Now"
→ Check logs for "Agent invoked"
→ IF fails: Fix and repeat
→ IF passes: Move to next issue
```

**Browser Automation Setup:**
```bash
pip install playwright
python -m playwright install chromium
```

**CRITICAL:** Don't stop at first fix - keep going until EVERYTHING works!

## Development Workflow

### 1. Feature Specification (Required for New Features)

**Before implementing any new feature**, create a specification document:

```bash
# Create feature spec in /docs/features/
touch docs/features/<feature-name>.md
```

**Required sections**:
- **Context**: Why this feature is needed, user problem it solves
- **Problem Statement**: Clear description of the problem
- **Proposed Solution**: Detailed technical approach
- **Implementation Plan**: Step-by-step breakdown
- **Acceptance Criteria**: How to verify success

**Process**:
1. Create feature spec document
2. **Discuss and get approval** before coding
3. Reference spec during implementation
4. Update spec if design changes during development

> 📖 **See [docs/features/](docs/features/) for examples**

### 2. Make Changes Locally
```bash
# Backend changes
cd backend && make test && make lint

# Frontend changes - MUST run inside Docker
docker compose exec frontend npm run lint
docker compose exec frontend npm run type-check
docker compose exec frontend npm test

# Install new frontend dependencies
docker compose exec frontend npm install --save-dev <package-name>
```

**⚠️ Frontend Commands**: Always run `npm` commands through `docker compose exec frontend` to ensure correct dependencies and environment. The `/app/node_modules` volume mount keeps node_modules isolated inside the container.

**⚠️ Package Management**: ALWAYS check if packages are already installed before installing:
- Check Docker containers: `docker compose exec <service> pip list` or `docker compose exec <service> npm list`
- Check existing venv: Look for `/tmp/webtesting/*/venv` or project venvs
- Check conda environments: `conda env list`
- **REUSE existing environments** - don't install duplicate packages globally

**Example:**
```bash
# ❌ DON'T: Install globally without checking
pip install playwright

# ✅ DO: Check and reuse existing venv
ls /tmp/webtesting/*/venv  # Check for existing venvs
source /tmp/webtesting/portfolio-analysis/venv/bin/activate  # Reuse it
```

### 3. Bump Version (Required)
```bash
# Every commit must increment at least one version
./scripts/bump-version.sh backend patch   # 0.1.0 → 0.1.1
./scripts/bump-version.sh frontend minor  # 0.1.0 → 0.2.0

# Pre-commit hook validates version increment
```

### 4. Deploy to Test Environment (Kubernetes)
```bash
# Build versioned images in Azure Container Registry
BACKEND_VERSION=$(grep '^version = ' backend/pyproject.toml | sed 's/version = "\(.*\)"/\1/')
FRONTEND_VERSION=$(grep '"version":' frontend/package.json | head -1 | sed 's/.*"\(.*\)".*/\1/')

az acr build --registry financialAgent \
  --image klinematrix/backend:test-v${BACKEND_VERSION} \
  --file backend/Dockerfile backend/

az acr build --registry financialAgent \
  --image klinematrix/frontend:test-v${FRONTEND_VERSION} \
  --target production --file frontend/Dockerfile frontend/

# Update kustomization.yaml, then apply and force restart
# Edit .pipeline/k8s/overlays/test/kustomization.yaml with new versions
kubectl apply -k .pipeline/k8s/overlays/test
kubectl rollout restart deployment/backend deployment/frontend -n klinematrix-test
```

**⚠️ CRITICAL**: Always use `kubectl rollout restart` after `apply -k` - image tag changes alone don't trigger rollouts

### 5. Verify Test Deployment
```bash
# Check deployment status
kubectl get pods -n klinematrix-test

# Test health endpoint
curl https://klinematrix.com/api/health
```

> 📖 **See [Deployment Workflow](docs/deployment/workflow.md) for complete procedures (build, deploy, verify, rollback)**
> 📖 **See [Version Management](docs/project/versions/README.md) for versioning system and workflow**

## Code Standards

### Pre-commit Hooks
- **Version validation**: Every commit must bump version
- **File length**: Max 500 lines per file (Python, TypeScript, JavaScript)
- **Security**: eslint-plugin-security for vulnerability detection
- **Performance**: eslint-plugin-perf-standard for optimization
- **Code quality**: Black, Ruff, mypy, ESLint, Prettier

**See [docs/development/coding-standards.md](docs/development/coding-standards.md) for patterns & debugging**

## Project Methodology

**See [docs/development/verification.md](docs/development/verification.md) for validation procedures**

## Quick Reference Commands

```bash
# Dev/Local Environment (Docker Compose)
make dev            # Start all services (docker-compose up -d)
make test           # Run all tests
make fmt            # Format code
make lint           # Check code quality
docker compose exec frontend npm run lint       # Frontend linting
docker compose logs -f backend                  # View backend logs

# Test Environment (Kubernetes)
kubectl get pods -n klinematrix-test                    # Check status
kubectl logs -f deployment/backend -n klinematrix-test  # View logs
kubectl delete pod -l app=backend -n klinematrix-test   # Restart with new image

# Build Images (use current versions from pyproject.toml/package.json)
BACKEND_VERSION=$(grep '^version = ' backend/pyproject.toml | sed 's/version = "\(.*\)"/\1/')
FRONTEND_VERSION=$(grep '"version":' frontend/package.json | head -1 | sed 's/.*"\(.*\)".*/\1/')

az acr build --registry financialAgent --image klinematrix/backend:test-v${BACKEND_VERSION} --file backend/Dockerfile backend/
az acr build --registry financialAgent --image klinematrix/frontend:test-v${FRONTEND_VERSION} --target production --file frontend/Dockerfile frontend/

# Health Checks
curl http://localhost:8000/api/health         # Dev/Local Backend
curl https://klinematrix.com/api/health       # Test (K8s)

# Langfuse Observability (Dev/Local)
open http://localhost:3001                    # Langfuse UI (trace visualization)
open http://localhost:9003                    # MinIO Console (S3 storage)
docker compose logs langfuse-server --tail=50 # Check Langfuse server logs
docker compose ps | grep langfuse             # Check Langfuse services status

# Cost Monitoring (prevent unexpected autoscaling)
kubectl get nodes                          # Should show 2 nodes (not 3-4)
kubectl top nodes                          # Memory should be <80%
kubectl get deployments --all-namespaces  # Check for duplicate/old deployments
```

## Important Reminders

### ⚠️ Before Committing

**🚨 CRITICAL: TEST FIRST, THEN COMMIT**
- **ALWAYS test changes before committing**
- Restart pods if needed: `kubectl rollout restart deployment/<service> -n klinematrix-test`
- Check browser console for errors
- Test the actual user flow (click buttons, check UI updates)
- **DO NOT commit without testing**

**Checklist:**
- [ ] **Test locally first** - Verify changes work in browser/terminal
- [ ] **Docker running** (required for frontend tests): `open -a Docker` if needed
- [ ] **Feature spec created** (for new features): Document in `docs/features/`
- [ ] Run `make fmt && make test && make lint`
- [ ] **Bump version** (required): `./scripts/bump-version.sh [component] [patch|minor|major]`
- [ ] **Document version file** (required): Fill out `docs/project/versions/[component]/v*.md` with overview, features, technical details before committing
- [ ] Check data contracts (Pydantic ↔ TypeScript)
- [ ] Verify no secrets in code

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

### 💰 Cost Management
- **Monitor weekly**: `kubectl get nodes | wc -l` should always return 2
- See [Cost Optimization Guide](docs/deployment/cost-optimization.md) for troubleshooting

### 💡 Development Principles
- **Find the root cause** - Don't fix symptoms, fix the underlying problem
- **Less code is more** - Simplest solution that works is usually correct
- **Avoid duplication** - Same logic in multiple places = bug waiting to happen
- **Don't overcomplicate** - Complex solutions are harder to debug and maintain
- **Compare environments** - When cloud differs from local, check config/credentials first

**Example**: Database name parsing bug existed in TWO places (config.py + mongodb.py). Fix once, extract to shared utility if needed.

## 🎯 Kubernetes Operations Best Practices

### Declarative Configuration
- **Always use explicit values** - Don't rely on implicit transformations
- **Include image references** - Strategic merge patches need explicit `image:` field
- **Verify before apply**: `kubectl kustomize <path>` to check rendered manifests
- **Never force with kubectl** - All changes must be in YAML files

### Resource Management
- **Use resource requests for scheduling** - High memory requests → high-memory nodes
- **Right-size based on metrics**: `kubectl top pods --containers`
- **Memory ≠ Pod slots** - Node can have free memory but hit pod limit
- **Node pool limits are immutable**:
  - `max-pods` cannot be changed after creation
  - Must delete/recreate node pool to modify

### Node Pool Strategy
```yaml
# High-memory workloads (2Gi request) → userpoolv2 (Standard_E2_v3, 16GB)
langfuse-worker, langfuse-clickhouse, backend

# Lightweight workloads (< 256Mi) → userpool (Standard_D2ls_v5, 4GB)
redis, frontend
```

### Troubleshooting Checklist
1. **Deployment version reverts** → Check explicit image in patch files
2. **Pod pending with free memory** → Check `kubectl describe node` for pod limit
3. **CPU throttling** → Review `kubectl top pods` and adjust limits
4. **Pods on wrong node** → Verify resource requests match node capacity

---

**Before any actions, always get context by reading the [docs main page](docs/README.md).**

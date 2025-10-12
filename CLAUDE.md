# Financial Agent - Development Guide

> **RULE**: Only concise, actionable rules here. No details, no repetition. See [docs/](docs/) for comprehensive documentation.

## 🔐 Security Rules

**CRITICAL**: Never write secrets in code, docs, or comments:
- ❌ API keys, access tokens, secret IDs, passwords
- ❌ Connection strings with credentials
- ❌ Private keys, certificates
- ✅ Use placeholders: `YOUR_SECRET_HERE`, `AKID*****`, `<REDACTED>`
- ✅ Store secrets in Azure Key Vault + External Secrets Operator
- ✅ Reference secrets by name in documentation

**GitHub Push Protection will block commits containing secrets.**

## Tech Stack

| Layer | Technology |
|-------|-----------|
| **Backend** | Python 3.12 + FastAPI + MongoDB + Redis |
| **Frontend** | React 18 + TypeScript 5 + Vite + TailwindCSS |
| **Deployment** | Kubernetes (AKS) + Azure + Alibaba Cloud |
| **AI/LLM** | LangChain + LangGraph + Alibaba DashScope |

> 📖 **See [System Design](docs/architecture/system-design.md) for architecture details**

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

# Frontend changes - Run natively
cd frontend
npm run lint
npm run type-check
npm test

# Install new frontend dependencies
npm install --save-dev <package-name>
```

**Note**: For local testing against deployed backend, use `kubectl port-forward` if needed:
```bash
kubectl port-forward -n klinematrix-test svc/backend 8000:8000
```

### 3. Bump Version (Required)
```bash
# Every commit must increment at least one version
./scripts/bump-version.sh backend patch   # 0.1.0 → 0.1.1
./scripts/bump-version.sh frontend minor  # 0.1.0 → 0.2.0

# Pre-commit hook validates version increment
```

### 4. Deploy to Test
```bash
# Build versioned images in Azure Container Registry
BACKEND_VERSION=$(grep '^version = ' backend/pyproject.toml | sed 's/version = "\(.*\)"/\1/')

az acr build --registry financialAgent \
  --image klinematrix/backend:test-v${BACKEND_VERSION} \
  --file backend/Dockerfile backend/

# Restart pods to pull new image (imagePullPolicy: Always)
kubectl delete pod -l app=backend -n klinematrix-test
```

### 5. Verify
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
# Local Development
make test           # Run all tests
make fmt            # Format code
make lint           # Check code quality

# Kubernetes Deployment
kubectl get pods -n klinematrix-test                    # Check status
kubectl logs -f deployment/backend -n klinematrix-test  # View logs
kubectl delete pod -l app=backend -n klinematrix-test   # Restart with new image

# Build Images (use current versions from pyproject.toml/package.json)
BACKEND_VERSION=$(grep '^version = ' backend/pyproject.toml | sed 's/version = "\(.*\)"/\1/')
FRONTEND_VERSION=$(grep '"version":' frontend/package.json | head -1 | sed 's/.*"\(.*\)".*/\1/')

az acr build --registry financialAgent --image klinematrix/backend:test-v${BACKEND_VERSION} --file backend/Dockerfile backend/
az acr build --registry financialAgent --image klinematrix/frontend:test-v${FRONTEND_VERSION} --target production --file frontend/Dockerfile frontend/

# Health Checks
curl https://klinematrix.com/api/health

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

---

**Before any actions, always get context by reading the [docs main page](docs/README.md).**

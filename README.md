# Financial Agent Platform

AI-Enhanced Financial Analysis Platform with Fibonacci retracements, market structure analysis, and conversational AI interfaces.

## 🏗️ Architecture

This project transforms a sophisticated CLI financial analysis tool into a production-ready web platform following the **"Infra-First Walking Skeleton"** methodology and **12-Factor Agent** principles.

### Tech Stack

**Tech Stack:**
- **Backend**: FastAPI + Python 3.12, MongoDB, Redis, LangChain + LangGraph
- **Frontend**: React 18 + TypeScript 5, Vite, TailwindCSS
- **Deployment**: Kubernetes (AKS), Azure + Alibaba Cloud hybrid
- **AI/LLM**: DashScope Qwen with streaming, LangSmith observability

> 📖 **See [System Design](docs/architecture/system-design.md) for complete tech stack details**

## 🚀 Quick Start

> 📖 **See [Getting Started Guide](docs/development/getting-started.md) for detailed setup instructions**

**Access deployed application:**
- Test: https://klinematrix.com
- Production: Not yet deployed
- API Docs: https://klinematrix.com/api/docs
- Health Check: https://klinematrix.com/api/health

**Local development:**
```bash
make dev
```

This starts:
- **Frontend**: http://localhost:3000
- **Backend API**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs
- **MongoDB**: localhost:27017
- **Redis**: localhost:6379

### 3. Verify Walking Skeleton
Visit http://localhost:3000 and check the "Health Status" tab. You should see:
- ✅ MongoDB connected
- ✅ Redis connected
- ✅ End-to-end connectivity confirmed

## 🛠️ Development Commands

```bash
# Development
make dev          # Start development environment
make up           # Start all services
make down         # Stop all services
make logs         # View service logs

# Code Quality (REQUIRED before commits)
make fmt          # Format all code
make lint         # Lint all code
make test         # Run all tests

# Building
make build        # Build Docker images
make clean        # Clean up Docker resources
```

## 📊 Financial Analysis Features

### Technical Analysis (Production)
- **Fibonacci Retracement**: Multi-trend detection with confidence scoring and customizable levels
- **Stochastic Oscillator**: K%/D% signals with overbought/oversold detection
- **Market Structure**: Swing point detection and trend analysis
- **Interactive Charts**: Lightweight Charts with date range selection and Fibonacci overlays
- **Data Caching**: Redis-based ticker data with consistent timeframe formatting

### AI-Powered Analysis (Production)
- **Conversational Interface**: Natural language financial queries via chat
- **Real-Time Streaming**: Token-by-token LLM responses with SSE
- **Wall Street Analyst Persona**: Expert insights with "Compact Logic Book" structure
- **Session Management**: Context-aware chat conversations
- **Symbol Search**: Smart search with yfinance validation

### Platform Features
- **Modern UI**: Glassmorphism design with gradient accents
- **Responsive Layout**: Full-width trading interface with 60/40 chat/chart split
- **Health Monitoring**: Real-time status of MongoDB, Redis, and backend services
- **Development Workflow**: Hot reload, pre-commit hooks, automated testing

## 🤖 Agent Architecture (12-Factor Design)

### Factor Implementation
1. **Own Configuration**: Environment-based settings via Pydantic
2. **Own Prompts**: LangSmith Hub for centralized prompt management
3. **External Dependencies**: Clean service interfaces for market data
4. **Environment Parity**: Docker Compose across dev/staging/prod
5. **Unified State**: Single state object through LangGraph
6. **Pause/Resume**: Human-in-the-loop approval workflows
7. **Stateless Service**: RESTful API with external state storage
8. **Error Handling**: Comprehensive observability with LangSmith
9. **Small Agents**: Composable tools using LCEL
10. **Triggerable**: HTTP endpoints for all agent operations

### Agent Tools
```python
# Available financial analysis tools
- FibonacciTool: Retracement analysis
- MarketStructureTool: Swing point detection
- MacroAnalysisTool: Market sentiment
- ChartGenerationTool: Visual chart creation
- FundamentalsTool: Stock data retrieval
```

## 🏥 Health Monitoring

### Endpoints
- `GET /api/health` - Comprehensive system status
- `GET /api/health/ready` - Kubernetes readiness probe
- `GET /api/health/live` - Kubernetes liveness probe

### Observability
- **Structured Logging**: JSON logs with trace_id correlation
- **OpenTelemetry**: Distributed tracing with trace_id propagation
- **Tencent CLS**: Centralized log aggregation and analysis
- **Metrics**: Application performance monitoring
- **Error Tracking**: Automatic error capture and alerting

## 🔐 Security

- 🔐 JWT authentication with email verification (Tencent Cloud SES)
- 🔄 Refresh token rotation with 30-day TTL automatic cleanup
- 🛡️ Non-root containers with read-only filesystems
- 🔑 Azure Key Vault + External Secrets Operator for secret management
- 🚦 Rate limiting and request validation
- 🔒 OAuth2/OIDC social authentication (planned)

## 📁 Project Structure

```
financial_agent/
├── backend/                 # FastAPI backend
│   ├── src/
│   │   ├── api/            # REST API endpoints
│   │   ├── core/           # Configuration and utilities
│   │   ├── database/       # MongoDB and Redis connections
│   │   └── main.py         # Application entry point
│   ├── pyproject.toml      # Python dependencies and tools
│   └── Dockerfile          # Backend container
├── frontend/               # React frontend
│   ├── src/
│   │   ├── components/     # React components
│   │   ├── services/       # API client services
│   │   ├── types/          # TypeScript type definitions
│   │   └── App.tsx         # Main application
│   ├── package.json        # Node.js dependencies
│   └── Dockerfile          # Frontend container
├── docker-compose.yml      # Development orchestration
├── Makefile               # Development commands
└── README.md              # This file
```

## 🚢 Deployment

### Test Environment (Azure AKS)

**Current Process**: Manual deployment via Kustomize

```bash
# 1. Bump version
./scripts/bump-version.sh backend patch  # or minor/major

# 2. Build and push images to Azure Container Registry
BACKEND_VERSION=$(grep '^version = ' backend/pyproject.toml | sed 's/version = "\(.*\)"/\1/')
az acr build --registry financialAgent \
  --image klinematrix/backend:test-v${BACKEND_VERSION} \
  --file backend/Dockerfile backend/

# 3. Update image tag in kustomization
# Edit .pipeline/k8s/overlays/test/kustomization.yaml

# 4. Apply with Kustomize
kubectl apply -k .pipeline/k8s/overlays/test/

# 5. Verify deployment
kubectl get pods -n klinematrix-test
curl https://klinematrix.com/api/health
```

**Documentation**: See [Deployment Workflow](docs/deployment/workflow.md) for complete procedures.

### CI/CD Pipeline

**Status**: ⚠️ Manual deployment (CI/CD automation planned for future)

**Current Tools**:
- **Pre-commit hooks** for code quality (Black, Ruff, mypy, ESLint, Prettier)
- **Azure Container Registry** for image storage
- **Azure Kubernetes Service (AKS)** for container orchestration
- **External Secrets Operator** for secret management

**Future**: See [Pipeline Workflow](docs/development/pipeline-workflow.md) for planned automation

## 🎯 Current Status: Production-Ready Platform ✅

**Current Versions** (as of 2025-10-24):
- ✅ **Backend v0.5.5**: Cosmos DB MongoDB API compatibility fix, Langfuse observability integration
- ✅ **Frontend v0.8.4**: CJK-aware token estimation, credit rollback, UI enhancements
- ✅ **Test Environment**: https://klinematrix.com (Azure Kubernetes + Alibaba Cloud AI)
- ✅ **Observability**: https://monitor.klinematrix.com (Langfuse v3 LLM trace visualization)

**Recent Milestones**:
- ✅ **v0.5.5**: Cosmos DB sorting compatibility + Langfuse v3 production deployment (2025-10-24)
- ✅ **v0.5.4**: LLM model selection with per-model pricing + code quality improvements (2025-10-15)
- ✅ **v0.5.3**: Token credit system with transaction tracking and reconciliation (2025-10-14)
- ✅ **v0.4.5/v0.6.1**: Security hardening (non-root containers, read-only filesystems) (2025-10-08)

**Core Features Delivered**:
- [x] **Financial Analysis**: Fibonacci retracements, stochastic oscillator, market structure
- [x] **AI Chat**: DashScope Qwen streaming with Wall Street analyst persona
- [x] **Interactive Charts**: TradingView Lightweight Charts with date range selection
- [x] **Credit Economy**: Token-based billing with optimistic updates and rollback
- [x] **Authentication**: JWT with refresh token rotation and 30-day TTL cleanup
- [x] **Cloud Infrastructure**: Azure AKS + Alibaba Cloud hybrid deployment
- [x] **Test Coverage**: 187 backend + 11 frontend tests with pre-commit enforcement

**Next Milestones:**
- [ ] OAuth2/OIDC social authentication (Google, GitHub)
- [ ] Transaction history UI and credit purchase flow
- [ ] Chart generation with AI interpretation
- [ ] Multi-user session isolation

## 🤝 Contributing

1. **Fork** the repository
2. **Create** a feature branch
3. **Run** `make fmt && make lint && make test`
4. **Commit** your changes
5. **Push** and create a Pull Request

### Code Standards
- **Python**: Black formatting, Ruff linting, MyPy type checking
- **TypeScript**: Prettier formatting, ESLint linting
- **Commits**: Conventional commit messages
- **Testing**: Maintain >95% test coverage

## 📚 Documentation

- [Complete Documentation](docs/README.md) - Full documentation index
- [12-Factor Agent Guide](docs/architecture/agent-12-factors.md) - Agent development principles
- [Agent Architecture](docs/architecture/agent-architecture.md) - Implementation details
- [API Documentation](https://klinematrix.com/api/docs) - Auto-generated OpenAPI docs
- [Coding Standards](CLAUDE.md) - Development practices and patterns

## 🔮 Roadmap

**Phase 1: Foundation** (Current)
- Infrastructure setup and walking skeleton
- Basic health monitoring and logging

**Phase 2: Agent Core**
- LangChain agent implementation
- Financial analysis tool integration
- Conversational interface

**Phase 3: Production**
- Authentication and authorization
- AI chart interpretation
- Cloud deployment and monitoring

**Phase 4: Scale**
- Advanced analytics and insights
- Multi-user support
- Performance optimization

---

**Transform your financial analysis from CLI to AI-powered web platform** 🚀

# Financial Agent Platform

AI-Enhanced Financial Analysis Platform with Fibonacci retracements, market structure analysis, and conversational AI interfaces.

## 🏗️ Architecture

This project transforms a sophisticated CLI financial analysis tool into a production-ready web platform following the **"Infra-First Walking Skeleton"** methodology and **12-Factor Agent** principles.

### Tech Stack

**Backend:**
- FastAPI (Python 3.12) with async/await
- MongoDB for document storage
- Redis for caching
- LangChain + LangGraph for AI agent orchestration
- LangSmith for observability

**Frontend:**
- React 18 with TypeScript 5.x
- Vite for build tooling
- TailwindCSS for styling
- React Query for state management
- Modern chat interface

**Infrastructure:**
- Docker Compose for local development
- Kubernetes for production deployment
- GitHub Actions for CI/CD
- Alibaba Cloud for hosting

## 🚀 Quick Start

### Prerequisites
- Docker and Docker Compose
- Node.js 18+ (for local frontend development)
- Python 3.12+ (for local backend development)

### 1. Clone and Setup
```bash
git clone <repository>
cd financial_agent
cp .env.example .env
# Edit .env with your configuration
```

### 2. Start Development Environment
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

### Current CLI Capabilities (Being Transformed)
- **Fibonacci Analysis**: Retracement levels with confidence scoring
- **Market Structure**: Swing point detection and trend analysis
- **Macro Analysis**: VIX sentiment, sector rotation, Buffett Indicator
- **Chart Generation**: Professional matplotlib visualizations
- **Fundamentals**: Stock metrics and valuation data

### Web Platform Enhancements
- **Conversational Interface**: Natural language financial queries
- **AI Chart Interpretation**: Qwen-VL model for visual analysis
- **Real-time Updates**: Live data streaming and caching
- **User Management**: Authentication and session persistence
- **Cloud Storage**: Chart images stored in Alibaba OSS

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
- **Structured Logging**: JSON logs with correlation IDs
- **LangSmith Tracing**: Complete agent execution traces
- **Metrics**: Prometheus-compatible application metrics
- **Error Tracking**: Automatic error capture and alerting

## 🔐 Security

- OAuth2/OIDC authentication (planned)
- JWT token validation
- Rate limiting and request validation
- Secure Docker image builds
- Environment-based secrets management

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

### Staging/Production
```bash
# Build production images
make build-prod

# Deploy to Kubernetes (requires kubectl config)
kubectl apply -f infra/k8s/

# Or using Helm
helm install financial-agent infra/helm/financials/
```

### CI/CD Pipeline
- **GitHub Actions** for automated testing and building
- **Docker image scanning** with Trivy
- **Automated deployment** to Alibaba Cloud ACK
- **Progressive rollouts** with health checks

## 🎯 Current Status: Walking Skeleton ✅

**Milestone 1 Complete:**
- [x] Docker Compose infrastructure
- [x] FastAPI backend with health endpoints
- [x] React frontend with health monitoring
- [x] MongoDB and Redis connectivity
- [x] End-to-end request flow verified

**Next Milestones:**
- [ ] LangChain agent integration
- [ ] Financial analysis API endpoints
- [ ] Authentication and user management
- [ ] Chart generation and OSS storage
- [ ] AI model integration
- [ ] Production deployment pipeline

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

- [Architecture Decisions](docs/adr/) - ADR records for major decisions
- [API Documentation](http://localhost:8000/docs) - Auto-generated OpenAPI docs
- [12-Factor Agent Guide](agent_12_factors.md) - Agent development principles
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
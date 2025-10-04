# Financial Agent Platform

AI-Enhanced Financial Analysis Platform with Fibonacci retracements, market structure analysis, and conversational AI interfaces.

## 🏗️ Architecture

This project transforms a sophisticated CLI financial analysis tool into a production-ready web platform following the **"Infra-First Walking Skeleton"** methodology and **12-Factor Agent** principles.

### Tech Stack

**Backend:**
- FastAPI (Python 3.12) with async/await
- MongoDB for document storage
- Redis for caching and ticker data
- DashScope Qwen LLM with streaming support
- yfinance for market data
- pandas/numpy for analysis

**Frontend:**
- React 18 with TypeScript 5.x
- Vite for build tooling
- TailwindCSS with glassmorphism design
- React Query for state management
- Lightweight Charts for interactive charting
- Server-Sent Events (SSE) for streaming

**Infrastructure:**
- Docker Compose for local development
- Kubernetes (Azure AKS) for production deployment
- GitHub Actions for CI/CD
- Azure Container Registry for image hosting
- Azure DNS for domain management

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

## 🎯 Current Status: Production-Ready Platform ✅

**Milestone 1 Complete: Walking Skeleton**
- [x] Docker Compose infrastructure
- [x] FastAPI backend with health endpoints
- [x] React frontend with health monitoring
- [x] MongoDB and Redis connectivity
- [x] End-to-end request flow verified

**Milestone 2 Complete: Financial Analysis Engine**
- [x] Fibonacci retracement analysis with multi-trend detection
- [x] Stochastic oscillator with 100% test coverage
- [x] Interactive TradingView charts with date range selection
- [x] Unified ticker data caching system
- [x] Symbol search with yfinance validation

**Milestone 3 Complete: AI Integration (v0.3.0)**
- [x] DashScope Qwen LLM integration with streaming
- [x] Real-time token-by-token response streaming (SSE)
- [x] Wall Street analyst persona with "Compact Logic Book" structure
- [x] Session-based chat management
- [x] Modern glassmorphism UI design

**Milestone 4 Complete: Cloud Deployment**
- [x] Azure AKS Kubernetes infrastructure
- [x] CI/CD pipeline with GitHub Actions
- [x] Azure Container Registry integration
- [x] Automated deployment workflows
- [x] Production-grade monitoring and health checks

**Next Milestones:**
- [ ] Authentication and user management (OAuth2/OIDC)
- [ ] Chart generation and OSS storage
- [ ] Multi-user session isolation
- [ ] Advanced analytics and insights

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

# Financial Agent Platform

AI-Enhanced Financial Analysis Platform with market insights, technical analysis, portfolio management, and conversational AI interfaces.

## Architecture

Production-ready web platform built on **12-Factor Agent** principles with hybrid cloud deployment.

### Tech Stack

| Layer | Technology |
|-------|-----------|
| **Backend** | Python 3.12 + FastAPI, MongoDB, Redis, LangChain + LangGraph |
| **Frontend** | React 18 + TypeScript 5, Vite, TailwindCSS |
| **Deployment** | Kubernetes (ACK), GitHub Actions CI/CD, Azure ACR |
| **AI/LLM** | Alibaba DashScope Qwen with streaming |
| **Observability** | Langfuse (https://monitor.klinecubic.cn) |

> See [System Design](docs/architecture/system-design.md) for complete architecture details

## Quick Start

### Environments

| Environment | Platform | URL | Status |
|------------|----------|-----|--------|
| **Dev/Local** | Docker Compose | http://localhost:3000 | Active |
| **Production** | Alibaba Cloud ACK | https://klinecubic.cn | Active |

### Local Development

```bash
make dev
```

This starts:
- **Frontend**: http://localhost:3000
- **Backend API**: http://localhost:8000
- **Langfuse**: http://localhost:3001 (LLM tracing)
- **MongoDB**: localhost:27017
- **Redis**: localhost:6379

### Production URLs
- Application: https://klinecubic.cn
- API Docs: https://klinecubic.cn/api/docs
- LLM Monitoring: https://monitor.klinecubic.cn

## Features

### Market Insights Dashboard
- **7 Market Metrics**: AI Price Anomaly, News Sentiment, Smart Money Flow, Put/Call Ratio, IPO Heat, Market Liquidity, Fed Expectations
- **Trend Visualization**: Sparklines and expanded 30-day trend charts
- **Composite Score**: Aggregated market sentiment tracking
- **Daily Snapshots**: Automated CronJob captures at 14:30 UTC

### Technical Analysis
- **Fibonacci Retracement**: Multi-trend detection with confidence scoring and golden zone highlighting
- **Stochastic Oscillator**: K%/D% signals with overbought/oversold detection
- **Market Structure**: Swing point detection and trend analysis
- **Interactive Charts**: Lightweight Charts with date range selection

### AI-Powered Analysis
- **Conversational Interface**: Natural language financial queries
- **Real-Time Streaming**: Token-by-token LLM responses via SSE
- **Wall Street Analyst Persona**: Expert insights with structured analysis
- **Agent Tools**: PCR lookup, sector risk, historical prices, fundamentals

### Portfolio Management
- **Watchlist Analysis**: Symbol-specific AI chat sessions
- **Automated Analysis**: CronJob-triggered portfolio reviews
- **Trading Integration**: Alpaca API for order management

### Platform
- **Authentication**: JWT with refresh token rotation (30-min access, 7-day refresh)
- **Credit System**: Token-based billing with transaction tracking
- **Health Monitoring**: Real-time status of all services

## Development

### Commands

```bash
# Development
make dev          # Start all services
make up           # Start services
make down         # Stop services
make logs         # View logs

# Code Quality
make fmt          # Format code (Black, Prettier)
make lint         # Lint code (Ruff, ESLint)
make test         # Run tests (1693 tests, 57% coverage)

# Building
make build        # Build Docker images
```

### Code Standards
- **Python**: Black formatting, Ruff linting, mypy type checking
- **TypeScript**: Prettier formatting, ESLint with security plugins
- **Pre-commit**: Automated hooks for formatting, linting, version validation
- **File limits**: Max 500 lines per file

## Deployment

### CI/CD Pipeline (GitHub Actions)

```
PR to main → Unit Tests → Review → Merge → Auto-deploy to Production
```

**Workflows**:
- **PR Workflow**: Runs unit tests on every pull request
- **Deploy Workflow**: Builds images and deploys to ACK on merge to main
- **Manual Trigger**: Available via GitHub Actions UI

See [Deployment Workflow](docs/deployment/workflow.md) for details.

### Manual Deployment

```bash
# 1. Bump version
./scripts/bump-version.sh backend patch

# 2. Build image
BACKEND_VERSION=$(grep '^version = ' backend/pyproject.toml | sed 's/version = "\(.*\)"/\1/')
az acr build --registry financialAgent \
  --image klinecubic/backend:prod-v${BACKEND_VERSION} \
  --file backend/Dockerfile backend/

# 3. Deploy
export KUBECONFIG=~/.kube/config-ack-prod
kubectl apply -k .pipeline/k8s/overlays/prod/
kubectl rollout restart deployment/backend -n klinematrix-prod
```

## Project Structure

```
financial_agent/
├── backend/                 # FastAPI backend
│   ├── src/
│   │   ├── api/            # REST endpoints
│   │   ├── agent/          # LangGraph AI agent
│   │   ├── services/       # Business logic
│   │   ├── database/       # MongoDB/Redis
│   │   └── workers/        # Background tasks
│   └── tests/              # 1693 unit tests
├── frontend/               # React frontend
│   ├── src/
│   │   ├── components/     # React components
│   │   ├── services/       # API clients
│   │   └── types/          # TypeScript types
├── docs/                   # Documentation
│   ├── architecture/       # System design
│   ├── features/           # Feature specs
│   ├── deployment/         # Deploy guides
│   └── stories/            # User stories
├── .pipeline/              # CI/CD & K8s configs
└── docker-compose.yml      # Local development
```

## Current Status

**Versions** (January 2026):
- Backend: v0.10.1
- Frontend: v0.11.5
- Test Coverage: 57% (1693 tests)

**Recent Releases**:
- **v0.10.x**: Comprehensive unit test coverage (57%), auth token consolidation
- **v0.9.0**: Market Insights Platform - PCR, FRED Liquidity, trend visualization
- **v0.8.x**: Performance monitoring, LangGraph latency tracking
- **v0.7.x**: Langfuse observability deployment

**Production Features**:
- [x] Market Insights Dashboard with 7 metrics
- [x] AI Chat with DashScope Qwen streaming
- [x] Technical Analysis (Fibonacci, Stochastic, Market Structure)
- [x] Portfolio Analysis with automated CronJob
- [x] Credit-based billing system
- [x] JWT auth with refresh token rotation
- [x] Langfuse LLM observability
- [x] GitHub Actions CI/CD

## Documentation

- [Complete Documentation](docs/README.md)
- [System Design](docs/architecture/system-design.md)
- [Deployment Workflow](docs/deployment/workflow.md)
- [Feature Specs](docs/features/)
- [Development Guide](CONTRIBUTING.md)
- [API Documentation](https://klinecubic.cn/api/docs)

## Contributing

1. Create feature branch from `main`
2. Run `make fmt && make lint && make test`
3. Bump version: `./scripts/bump-version.sh [component] patch`
4. Create Pull Request
5. CI runs tests → Review → Merge → Auto-deploy

---

**AI-powered financial analysis platform** | [Production](https://klinecubic.cn) | [Monitoring](https://monitor.klinecubic.cn)

# Getting Started - Financial Agent Development

## Quick Start

### Prerequisites
- Docker and Docker Compose
- Node.js 18+ (for local frontend development)
- Python 3.12+ (for local backend development)
- Git

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

## Development Commands

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

## Project Structure

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
├── docs/                   # Documentation
├── .pipeline/              # Kubernetes and CI/CD
├── docker-compose.yml      # Development orchestration
├── Makefile               # Development commands
└── README.md              # Project overview
```

## Tech Stack Overview

### Backend
- **Python 3.12** with modern syntax
- **FastAPI** for async API framework
- **MongoDB** for document storage
- **Redis** for caching
- **LangChain + LangGraph** for AI agent orchestration
- **LangSmith** for observability

### Frontend
- **React 18** with TypeScript 5.x
- **Vite** for fast build tooling
- **TailwindCSS** for styling
- **React Query** for state management
- Modern chat interface

### Infrastructure
- **Docker Compose** for local development
- **Kubernetes** for production deployment
- **GitHub Actions** for CI/CD
- **Azure** for cloud hosting

## Local Development Workflow

### Backend Development

```bash
# Start backend with hot reload
cd backend
python -m uvicorn src.main:app --reload --host 0.0.0.0 --port 8000

# Or use Docker Compose (recommended)
docker-compose up backend
```

**Backend Hot Reload:**
- Function/method changes: Auto-reload ✅
- New routes/endpoints: Auto-reload ✅
- New dependencies: Restart required ❌
- Global/module-level changes: Restart required ❌

### Frontend Development

```bash
# Start frontend with hot reload
cd frontend
npm install
npm run dev

# Or use Docker Compose (recommended)
docker-compose up frontend
```

**Frontend Hot Reload:**
- Component changes: Auto-reload ✅
- CSS/styling changes: Auto-reload ✅
- New dependencies: Restart required ❌

### Database Development

```bash
# Access MongoDB shell
docker-compose exec mongodb mongosh

# Access Redis CLI
docker-compose exec redis redis-cli
```

## Code Standards

### Python
- Use modern syntax: `|` unions, `match/case`, f-strings, `@dataclass`
- Type hints required
- Black for formatting
- Ruff for linting
- MyPy for type checking
- Maximum 500 lines per file

### TypeScript
- ES modules
- Optional chaining
- `satisfies` operator
- ESLint for linting
- Prettier for formatting
- Maximum 500 lines per file

### Documentation
- Descriptive docstrings at top of every file
- Rich comments for key business logic (explain "why", not "what")
- No code duplication (DRY principle)

## Quality Gates

Before committing, always run:

```bash
make fmt && make test && make lint
```

This ensures:
- ✅ Code is properly formatted
- ✅ All tests pass
- ✅ No linting violations

## Common Development Tasks

### Adding a New API Endpoint

1. Create endpoint in `backend/src/api/`
2. Add tests in `backend/tests/api/`
3. Update API client in `frontend/src/services/`
4. Run quality gates: `make fmt && make test && make lint`

### Adding a New React Component

1. Create component in `frontend/src/components/`
2. Add TypeScript types in `frontend/src/types/`
3. Write tests
4. Run quality gates

### Adding a New Database Model

1. Create Pydantic model in `backend/src/models/`
2. Add database operations in `backend/src/database/`
3. Write tests
4. Ensure TypeScript types match in frontend

## Environment Variables

### Backend (.env)
```env
ENVIRONMENT=development
MONGODB_URL=mongodb://mongodb:27017/financial_agent
REDIS_URL=redis://redis:6379/0
CORS_ORIGINS='["*"]'
LOG_LEVEL=DEBUG
```

### Frontend (.env)
```env
VITE_API_BASE_URL=http://localhost:8000
```

## Troubleshooting

### Services Won't Start

```bash
# Clean up and restart
make clean
make dev

# Check for port conflicts
lsof -i :3000  # Frontend
lsof -i :8000  # Backend
lsof -i :27017 # MongoDB
lsof -i :6379  # Redis
```

### Backend Shows "unhealthy"

```bash
# Check backend logs
docker-compose logs backend

# Restart backend
docker-compose restart backend

# Check database connectivity
docker-compose logs mongodb
docker-compose logs redis
```

### Frontend Not Loading

```bash
# Check frontend logs
docker-compose logs frontend

# Verify frontend container is running
docker-compose ps frontend

# Restart frontend
docker-compose restart frontend
```

### Database Connection Errors

```bash
# Restart databases
docker-compose restart mongodb redis backend

# Check database logs
docker-compose logs mongodb
docker-compose logs redis
```

### Hot Reload Not Working

**If code changes aren't reflected:**
1. Check if it's a type of change that requires restart (see Hot Reload sections above)
2. If yes, restart the service:
   ```bash
   docker-compose restart backend  # or frontend
   ```
3. If no, check logs for errors:
   ```bash
   docker-compose logs backend  # or frontend
   ```

## Next Steps

Once your development environment is running:

1. **Explore the Interface** - Try the chat interface and health monitoring
2. **Review the Code** - Check out backend and frontend source code
3. **Read the Architecture** - See [docs/architecture/system-design.md](/Users/allenpan/Desktop/repos/projects/financial_agent/docs/architecture/system-design.md)
4. **Review Coding Standards** - See [docs/development/coding-standards.md](/Users/allenpan/Desktop/repos/projects/financial_agent/docs/development/coding-standards.md)
5. **Start Building** - Pick a task and start developing!

## Resources

- **API Documentation**: http://localhost:8000/docs
- **Project Specifications**: [docs/project/specifications.md](/Users/allenpan/Desktop/repos/projects/financial_agent/docs/project/specifications.md)
- **12-Factor Agent Guide**: [docs/architecture/agent-12-factors.md](/Users/allenpan/Desktop/repos/projects/financial_agent/docs/architecture/agent-12-factors.md)
- **Deployment Guide**: [docs/deployment/workflow.md](/Users/allenpan/Desktop/repos/projects/financial_agent/docs/deployment/workflow.md)

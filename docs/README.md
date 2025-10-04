# Financial Agent Documentation

Comprehensive documentation for the AI-Enhanced Financial Analysis Platform.

## Quick Links

- **Getting Started**: [Development Setup Guide](development/getting-started.md)
- **Architecture Overview**: [System Design](architecture/system-design.md)
- **Deployment Guide**: [Cloud Setup](deployment/cloud-setup.md)
- **Project Specs**: [Full Specifications](project/specifications.md)

## Documentation Structure

### Architecture
Design and architectural decisions for the Financial Agent platform.

- **[12-Factor Agent Playbook](architecture/agent-12-factors.md)**: Guide to implementing production-ready AI agents with LangChain, LangGraph, and LangSmith
- **[Agent Architecture](architecture/agent-architecture.md)**: Detailed implementation of the 12-factor agent principles for financial analysis
- **[System Design](architecture/system-design.md)**: Complete system architecture overview, technology stack, and design patterns

### Deployment
Infrastructure setup and deployment procedures.

- **[Cloud Setup](deployment/cloud-setup.md)**: Hybrid cloud architecture with Azure and Alibaba Cloud, including setup instructions and cost estimates
- **[Infrastructure Overview](deployment/infrastructure.md)**: Kubernetes resources, network topology, and operational commands
- **[Deployment Workflow](deployment/workflow.md)**: Manual deployment procedures, troubleshooting, and rollback strategies

### Development
Developer guides and best practices.

- **[Getting Started](development/getting-started.md)**: Quick start guide for local development environment
- **[Coding Standards](development/coding-standards.md)**: Python/TypeScript standards, patterns, and best practices
- **[Pipeline Workflow](development/pipeline-workflow.md)**: AI automation, CI/CD pipeline, and testing strategy
- **[Verification Guide](development/verification.md)**: Walking skeleton verification and health check procedures

### Project
High-level project information and specifications.

- **[Project Specifications](project/specifications.md)**: Complete technical specifications, features, roadmap, and success metrics

### Troubleshooting
Bug fixes, common issues, and debugging guides.

- **[Troubleshooting Index](troubleshooting/README.md)**: Quick index of all troubleshooting resources
- **[CORS & API Connectivity](troubleshooting/cors-api-connectivity.md)**: Frontend-backend connection issues, CORS errors, nginx proxy problems
- **[Data Validation Issues](troubleshooting/data-validation-issues.md)**: Pydantic validation errors, type mismatches, data format issues
- **[Deployment Issues](troubleshooting/deployment-issues.md)**: Kubernetes problems, pod crashes, image pulls, health checks
- **[Known Bugs](troubleshooting/known-bugs.md)**: Current open issues, workarounds, and status

## Key Features

### Financial Analysis
- Fibonacci retracement analysis with confidence scoring
- Market structure and swing point detection
- Macro sentiment analysis (VIX, sector rotation)
- Professional chart generation
- Fundamental analysis and stock metrics

### AI-Powered Insights
- Natural language conversational interface
- AI chart interpretation via Qwen-VL multimodal model
- Automated report generation
- Context-aware responses

### Technology Stack
- **Backend**: Python 3.12, FastAPI, MongoDB, Redis
- **Frontend**: React 18, TypeScript 5, Vite, TailwindCSS
- **AI/ML**: LangChain, LangGraph, LangSmith, Qwen-VL
- **Infrastructure**: Kubernetes (AKS), Docker, GitHub Actions
- **Cloud**: Hybrid Azure + Alibaba Cloud

## Development Quick Start

```bash
# Clone and setup
git clone <repository>
cd financial_agent
cp .env.example .env

# Start development environment
make dev

# Access services
# Frontend:  http://localhost:3000
# Backend:   http://localhost:8000
# API Docs:  http://localhost:8000/docs

# Code quality checks
make fmt && make test && make lint
```

## Architecture Highlights

### Walking Skeleton Methodology
1. **Milestone 1**: End-to-end connectivity (Frontend → API → DB → Cache) ✅
2. **Milestone 2**: Authentication + core business logic (In Progress)
3. **Milestone 3+**: Layer features incrementally

### 12-Factor Agent Principles
1. Own Configuration
2. Own Prompts
3. External Dependencies as Services
4. Environment Parity
5. Unified State Management
6. Pause/Resume Capability
7. Human-in-the-Loop
8. Explicit Control Flow
9. Error Handling & Observability
10. Small Composable Agents
11. Triggerable via API
12. Stateless Service Design

### Hybrid Cloud Strategy
- **Azure**: Core platform (AKS, Cosmos DB, monitoring, authentication)
- **Alibaba Cloud**: Specialized services (Qwen-VL AI model, OSS storage)
- **Benefits**: Best-of-breed services, cost optimization, geographic distribution

## Deployment Environments

### Development
- **Platform**: Docker Compose (local) or AKS dev namespace
- **Database**: In-cluster MongoDB
- **Cache**: In-cluster Redis (non-persistent)
- **URL**: http://localhost:3000 (local)

### Staging
- **Platform**: AKS dedicated namespace
- **Database**: Azure Cosmos DB (dev instance)
- **URL**: https://financial-agent-dev.koreacentral.cloudapp.azure.com

### Production (Planned)
- **Platform**: AKS multi-region
- **Database**: Azure Cosmos DB (production, multi-region)
- **Cache**: ApsaraDB for Redis (managed)
- **CDN**: Global content delivery

## Documentation Maintenance

### When to Update

**Architecture Documents**: When making architectural decisions or design changes
- Update affected architecture docs
- Add ADR (Architecture Decision Record) if significant

**Deployment Documents**: When changing infrastructure or deployment procedures
- Update deployment workflow
- Update infrastructure diagrams
- Document new configuration steps

**Development Documents**: When changing development practices or tooling
- Update coding standards
- Update getting started guide
- Update verification procedures

**Project Specifications**: When adding features or changing roadmap
- Update feature list
- Update success metrics
- Update roadmap phases

### Documentation Standards
- Use clear, concise language
- Include code examples where helpful
- Keep diagrams up-to-date
- Add links between related documents
- Version control all documentation

## Additional Resources

- **Main README**: [Project Overview](../README.md)
- **CLAUDE.md**: [Development Guidelines](../CLAUDE.md) (Project-specific instructions)
- **API Documentation**: http://localhost:8000/docs (when running locally)

## Support & Contribution

For questions, issues, or contributions:
1. Check this documentation first
2. Review the [Getting Started Guide](development/getting-started.md)
3. Consult the [Coding Standards](development/coding-standards.md)
4. Follow the quality gates: `make fmt && make test && make lint`

## Version History

- **v0.1.0** (Current): Walking skeleton complete
  - End-to-end connectivity
  - Health monitoring
  - Basic infrastructure
  - Documentation organization

- **v0.2.0** (Planned): Agent core
  - LangChain integration
  - Financial analysis tools
  - Conversational interface

- **v1.0.0** (Future): Production release
  - Authentication
  - AI interpretation
  - Full deployment
  - Performance optimization

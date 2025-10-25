# Financial Agent Documentation

Comprehensive documentation for the AI-Enhanced Financial Analysis Platform.

---

## Current Versions

**Last Updated:** 2025-10-24

| Component | Version | Environment | Status |
|-----------|---------|-------------|--------|
| Backend   | v0.5.5  | Test (K8s)  | ✅ Stable |
| Frontend  | v0.8.4  | Test (K8s)  | ✅ Stable |
| Langfuse  | v3.x    | Test (K8s)  | ✅ Production |
| Production | -      | Not deployed | ⏳ Planned |

**Test Environment:** https://klinematrix.com
**Observability:** https://monitor.klinematrix.com (Langfuse v3)
**Production:** Not yet deployed

For detailed version history and release notes, see [Version Management](project/versions/README.md).

---

## Quick Links

- **Getting Started**: [Development Setup Guide](development/getting-started.md)
- **Architecture Overview**: [System Design](architecture/system-design.md)
- **Deployment Guide**: [Cloud Setup](deployment/cloud-setup.md)
- **Project Specs**: [Full Specifications](project/specifications.md)

## Documentation Structure

### Architecture
Design and architectural decisions for the Financial Agent platform.

- **[12-Factor Agent Playbook](architecture/agent-12-factors.md)**: Guide to implementing production-ready AI agents with LangChain, LangGraph, and Langfuse
- **[Agent Architecture](architecture/agent-architecture.md)**: Detailed implementation of the 12-factor agent principles for financial analysis
- **[System Design](architecture/system-design.md)**: Complete system architecture overview, technology stack, and design patterns

### Deployment
Infrastructure setup and deployment procedures.

- **[Cloud Setup](deployment/cloud-setup.md)**: Hybrid cloud architecture with Azure and Alibaba Cloud, including setup instructions and cost estimates
- **[Infrastructure Overview](deployment/infrastructure.md)**: Kubernetes resources, network topology, and operational commands
- **[Deployment Workflow](deployment/workflow.md)**: Manual deployment procedures, troubleshooting, and rollback strategies
- **[Resource Inventory](deployment/RESOURCE_INVENTORY.md)**: Complete list of all Azure and Kubernetes resources
- **[Dev→Test Migration](deployment/MIGRATION_DEV_TO_TEST.md)**: Migration guide from dev to test environment

### Features
Feature specifications and requirements documentation.

- **[Feature Specs](features/README.md)**: Template and guidelines for creating feature specifications before implementation
- **Active Features**: Browse `features/` directory for approved and in-progress feature specs

**Agent Implementation:**
- **[SDK ReAct Agent](features/langgraph-sdk-react-agent.md)**: LangGraph SDK-based agent with autonomous tool chaining and flexible auto-planning

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

**Agent Architecture**:
- **SDK ReAct Agent** (`/api/chat/stream-react`)
  - Autonomous tool chaining (LLM decides next tool)
  - Flexible, context-driven routing
  - Compressed tool results for efficiency
  - Built-in message history and state management

### Technology Stack
See [Architecture → System Design](architecture/system-design.md) for complete tech stack and architecture overview.

## Development Quick Start

See [Development → Getting Started](development/getting-started.md) for complete setup instructions.

**Quick access:**
```bash
# Production deployment
curl https://klinematrix.com/api/health

# View logs
kubectl logs -f deployment/backend -n klinematrix-test

# Local development (optional)
cd backend && uvicorn src.main:app --reload
cd frontend && npm run dev

# Code quality checks (REQUIRED before commits)
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

### Local Development
- **Platform**: Kubernetes (kubectl port-forward to access services)
- **Database**: MongoDB (accessed via port-forward or cloud)
- **Cache**: Redis (accessed via port-forward or cloud)
- **Email**: Bypass mode (no real emails)
- **Secrets**: `.env.development` or Azure Key Vault
- **URL**: http://localhost:3000
- **Note**: Never deployed to K8s

### Test (Cloud - Current)
- **Platform**: AKS (`klinematrix-test` namespace)
- **Database**: Azure Cosmos DB (`klinematrix_test` database)
- **Cache**: In-cluster Redis
- **Email**: Tencent Cloud SES API (real email verification)
- **Secrets**: Azure Key Vault (`klinematrix-test-kv`)
- **URL**: https://klinematrix.com
- **Users**: 10 beta testers
- **Current Versions**: Backend v0.5.4, Frontend v0.8.4 (as of 2025-10-15)

### Production (Planned)
- **Platform**: AKS multi-region (`klinematrix-prod` namespace)
- **Database**: Azure Cosmos DB (`klinematrix_prod` database, multi-region)
- **Cache**: In-cluster Redis (persistent)
- **Email**: Tencent Cloud SES API (production)
- **Secrets**: Azure Key Vault (`klinematrix-prod-kv`)
- **URL**: https://klinematrix.com (same domain, different namespace)
- **CDN**: Global content delivery
- **Images**: `klinematrix/backend:v1.0.0`, `klinematrix/frontend:v1.0.0` (no "test-" prefix)

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

**Recent Releases:**

- **v0.5.4 / v0.8.4** (2025-10-15) - **Current**
  - **Backend v0.5.4**: LLM model selection with per-model pricing, code quality improvements, datetime deprecation fixes
    - Multi-model support (qwen-plus, qwen3-max, deepseek-v3, deepseek-v3.2-exp)
    - Per-model pricing (1 credit = ¥0.001 CNY baseline)
    - Thinking mode support (qwen-plus 4x cost, deepseek-v3.2-exp same cost)
    - Input validation for negative tokens
    - Modern Python 3.12+ type annotations (X | Y syntax)
    - Transaction reconciliation worker tested (processed 8 stuck PENDING transactions)
  - **Frontend v0.8.4**: Credit balance privacy toggle, UI layout improvements
    - Credit blur/show toggle for screen sharing
    - Flexbox layout improvements
    - Centered sidebar collapse button
    - Memoization for expensive computations
    - Eliminated `any` types (proper React Query types)
  - See [Feature Spec: LLM Model Selection](features/llm-model-selection.md) for complete details

- **v0.5.3** (2025-10-14)
  - Token credit system with transaction tracking and reconciliation
  - See [v0.5.3 Release Notes](project/versions/backend/v0.5.3.md)

- **v0.5.2 / v0.8.3** (2025-10-12)
  - **Backend v0.5.2**: Feedback platform with rate limiting, N+1 query optimization
  - **Frontend v0.8.3**: Feedback platform UI with gamification (trophy badges)
  - Type safety overhaul (107 mypy errors → 0)
  - See [Version Management](project/versions/README.md) for complete release notes

- **v0.4.5 / v0.6.1** (2025-10-08)
  - Security hardening (non-root users, read-only filesystems)
  - Cost optimization (2-node AKS cluster)

- **v0.3.0-v0.4.0** (2025-10-07)
  - Authentication with email verification
  - LLM chat integration with streaming responses
  - Chat restoration with UI state persistence

- **v0.1.0**: Walking skeleton complete
  - End-to-end connectivity
  - Health monitoring
  - Basic infrastructure

**Future Releases:**

- **v1.0.0** (Planned): Production release
  - Frontend model selection UI
  - AI chart interpretation
  - Production deployment
  - Multi-user support

> **Note**: For detailed release notes and compatibility information, see [Version Management](project/versions/README.md).

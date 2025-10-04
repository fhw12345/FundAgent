# Financial Agent System Design

## Executive Summary

AI-Enhanced Financial Analysis Platform that provides on-demand Fibonacci and market structure analysis for financial symbols. The platform generates chart images and supplements them with AI-powered interpretations using a decoupled, cloud-native architecture.

## Overall Direction

The project transforms a sophisticated CLI financial analysis tool into a modern, cloud-native, AI-enhanced web application. The architecture is designed to be scalable, secure, and observable from the ground up, prioritizing managed services to reduce operational overhead while maintaining focus on core financial analysis features.

## Technology Stack

### Cloud Platform
**Hybrid Cloud Strategy**
- **Primary Platform**: Microsoft Azure
  - Container orchestration (AKS)
  - Database (Cosmos DB with MongoDB API)
  - Authentication (Azure AD B2C)
  - Monitoring (Azure Monitor)

- **Specialized Services**: Alibaba Cloud
  - AI/LLM (Qwen-VL Model via DashScope)
  - Object Storage (OSS for charts)
  - Geographic distribution for APAC markets

### Backend
- **Framework**: Python 3.12 with FastAPI
- **Rationale**: High performance, asynchronous capabilities, automatic API documentation
- **Features**:
  - RESTful API endpoints
  - OAuth2/OIDC Bearer JWTs for authentication
  - Scope-based authorization
  - Automatic OpenAPI documentation

### Frontend
- **Framework**: React 18 with TypeScript 5.x
- **Build Tool**: Vite
- **Styling**: TailwindCSS
- **State Management**: React Query for server state
- **Features**:
  - Secure login flow using OIDC Authorization Code + PKCE
  - Conversational chat interface with quick actions
  - Chart visualization and AI-generated summaries
  - Historical request dashboard

### Compute & Orchestration
- **Platform**: Azure Kubernetes Service (AKS)
- **Container Runtime**: Docker
- **Scaling**: Horizontal Pod Autoscaler (HPA) based on CPU load
- **Features**:
  - Automated scaling
  - Self-healing deployments
  - Zero-downtime updates

### Data Layer

#### Primary Database
- **Service**: Azure Cosmos DB (MongoDB API)
- **Rationale**: Flexible document-based structure ideal for complex analysis results
- **Usage**: Analysis results, user requests, metadata

#### Chat Storage
- **Service**: Alibaba Cloud Tablestore (planned)
- **Rationale**: Optimized for time-series data like chat messages
- **Features**: Automatic scaling, fast conversation thread retrieval

#### Caching
- **Service**: Redis (in-cluster for dev, ApsaraDB for Redis in production)
- **Purpose**: Distributed cache for external data sources (yfinance)
- **Benefits**: Reduced latency and API calls across horizontally scaled replicas

#### Object Storage
- **Service**: Alibaba Cloud OSS
- **Purpose**: Chart image storage
- **Access**: Temporary pre-signed URLs for secure client access

### AI & Analytics
- **Service**: Alibaba Cloud Model Studio (Bailian)
- **Model**: Qwen-VL-Max (multimodal vision-language model)
- **Use Cases**:
  1. Chart interpretation and analysis
  2. Natural language query processing
  3. Automated report generation

### Infrastructure & DevOps

#### API Management
- **Service**: Nginx Ingress Controller
- **Features**:
  - Traffic management
  - Rate limiting
  - SSL termination
  - Reverse proxy

#### CI/CD
- **Platform**: GitHub Actions
- **Pipeline Stages**:
  1. Lint, test, and build application code
  2. Build and scan Docker images (Trivy)
  3. Push to Azure Container Registry (ACR)
  4. Deploy to staging
  5. Manual approval for production
  6. Progressive rollout with health checks

#### Observability
- **Logging**: Structured JSON logs with correlation IDs
- **Metrics**: Prometheus-compatible application metrics
- **Tracing**: LangSmith for agent execution traces
- **Monitoring**: Azure Monitor with custom dashboards
- **Alerting**: Automated alerts for critical conditions

## Architecture Patterns

### Walking Skeleton Methodology
1. **Milestone 1**: End-to-end connectivity (Frontend → API → DB → Cache)
2. **Milestone 2**: Authentication + core business logic
3. **Milestone 3+**: Layer features incrementally

### 12-Factor Agent Principles
1. **Own Configuration**: Environment-based settings via Pydantic
2. **Own Prompts**: LangSmith Hub for centralized prompt management
3. **External Dependencies**: Clean service interfaces
4. **Environment Parity**: Consistent environments via Kubernetes
5. **Unified State**: Single state object through LangGraph
6. **Pause/Resume**: Human-in-the-loop approval workflows
7. **Stateless Service**: RESTful API with external state storage
8. **Own Control Flow**: Explicit state machine with LangGraph
9. **Error Handling**: Comprehensive observability
10. **Small Agents**: Composable tools using LCEL
11. **Triggerable**: HTTP endpoints for all operations
12. **Stateless**: No server-side session state

## Financial Analysis Features

### Current CLI Capabilities
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
- **Cloud Storage**: Chart images with global CDN delivery

## Security & Compliance

### Authentication & Authorization
- OAuth2/OIDC via Azure AD B2C
- JWT token validation
- Scope-based access control
- Session management

### Network Security
- HTTPS/TLS encryption (Let's Encrypt)
- Azure CNI networking
- Network policies
- VPN for cross-cloud communication

### Data Security
- Encryption at rest (Cosmos DB, OSS)
- Encryption in transit (TLS 1.3)
- Secrets management via Azure Key Vault
- External Secrets Operator for K8s integration

### Compliance
- No hardcoded secrets in manifests
- Audit logging
- RBAC with minimal permissions
- Signed container images

## Scalability & Performance

### Horizontal Scaling
- Stateless application design
- Kubernetes HPA for automatic scaling
- Load balancing via Nginx Ingress
- Distributed caching with Redis

### Performance Optimization
- CDN for static assets
- Redis caching for market data
- Async/await throughout backend
- Connection pooling for databases
- Image optimization for charts

### Cost Optimization
- Auto-scaling based on demand
- Managed services reduce operational overhead
- Development environment with minimal resources
- CDN reduces bandwidth costs

## Deployment Topology

### Development Environment
- Local: Docker Compose
- Cloud: AKS dev namespace
- Minimal resources
- In-cluster Redis (non-persistent)
- Mock authentication

### Production Environment
- Multi-region AKS deployment
- Azure Cosmos DB (multi-region)
- ApsaraDB for Redis (managed)
- Azure AD B2C authentication
- Progressive rollouts
- Blue-green deployments

## Integration Points

### Cross-Cloud Integration
1. **Authentication Flow**: Azure AD B2C → AKS → Services
2. **Data Flow**: Azure Cosmos DB ↔ Application ↔ Alibaba OSS
3. **AI Processing**: Application → Qwen-VL Model → Response
4. **Monitoring**: Azure Monitor + custom metrics from Alibaba services

### External APIs
- yfinance for market data
- Alibaba DashScope for AI inference
- Azure Cosmos DB for persistence
- Redis for caching

## Roadmap

### Phase 1: Foundation (Current)
- Infrastructure setup and walking skeleton
- Basic health monitoring and logging
- End-to-end connectivity verification

### Phase 2: Agent Core
- LangChain agent implementation
- Financial analysis tool integration
- Conversational interface
- State management and persistence

### Phase 3: Production
- Authentication and authorization
- AI chart interpretation
- Cloud deployment automation
- Monitoring and alerting

### Phase 4: Scale
- Advanced analytics and insights
- Multi-user support
- Performance optimization
- Geographic distribution

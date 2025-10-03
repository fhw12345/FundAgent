# Financial Agent - DevOps Pipeline

## Dev Environment Setup

This pipeline deploys the Financial Agent to Azure AKS with Alibaba Cloud LLM integration.

### Architecture
- **Platform**: Azure AKS (FinancialAgent-AKS)
- **Authentication**: Azure Workload Identity (OAuth2/OIDC)
- **LLM APIs**: Alibaba Cloud DashScope
- **Deployment**: Kustomize + GitHub Actions

### Quick Start
```bash
# 1. Set up Azure resources
./scripts/setup-azure-dev.sh

# 2. Deploy to dev
kubectl apply -k k8s/overlays/dev

# 3. Verify deployment
kubectl get pods -n financial-agent-dev
```

### Structure
```
.pipeline/
├── k8s/base/          # Base manifests
├── k8s/overlays/dev/  # Dev-specific config
├── workflows/         # GitHub Actions
└── scripts/           # Setup scripts
```
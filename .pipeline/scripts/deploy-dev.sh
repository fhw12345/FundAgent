#!/bin/bash
set -euo pipefail

# Financial Agent - Manual Dev Deployment Script
echo "🚀 Deploying Financial Agent to Dev Environment"

# Configuration
NAMESPACE="financial-agent-dev"
AKS_CLUSTER="FinancialAgent-AKS"
RESOURCE_GROUP="FinancialAgent"

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

log() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

# Check if kubectl is configured
log "Checking kubectl configuration..."
if ! kubectl cluster-info &>/dev/null; then
    warning "Getting AKS credentials..."
    az aks get-credentials \
        --resource-group "$RESOURCE_GROUP" \
        --name "$AKS_CLUSTER" \
        --overwrite-existing
fi

# Build and tag images locally (for testing)
log "Building Docker images..."
cd "$(dirname "$0")/../.."

# Build backend
docker build -t financial-agent/backend:dev-latest ./backend

# Build frontend
docker build -t financial-agent/frontend:dev-latest ./frontend

# Load images to kind/minikube if running locally
if kubectl config current-context | grep -E "(kind|minikube)" &>/dev/null; then
    log "Loading images to local cluster..."
    kind load docker-image financial-agent/backend:dev-latest || true
    kind load docker-image financial-agent/frontend:dev-latest || true
fi

# Deploy to Kubernetes
log "Deploying to Kubernetes..."
cd .pipeline

# Apply the dev overlay
kubectl apply -k k8s/overlays/dev

# Wait for deployments
log "Waiting for deployments to be ready..."
kubectl rollout status deployment/backend -n "$NAMESPACE" --timeout=300s
kubectl rollout status deployment/frontend -n "$NAMESPACE" --timeout=300s

# Show status
echo ""
success "🎉 Deployment complete!"
echo ""
log "📊 Pod Status:"
kubectl get pods -n "$NAMESPACE"
echo ""
log "📡 Services:"
kubectl get services -n "$NAMESPACE"
echo ""
log "🔍 Get frontend URL:"
echo "kubectl get service frontend-service -n $NAMESPACE -o jsonpath='{.status.loadBalancer.ingress[0].ip}'"
echo ""
log "🐞 Debug commands:"
echo "kubectl logs -f deployment/backend -n $NAMESPACE"
echo "kubectl logs -f deployment/frontend -n $NAMESPACE"
echo "kubectl describe pod -l app=backend -n $NAMESPACE"

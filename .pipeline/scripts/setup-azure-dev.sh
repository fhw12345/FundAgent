#!/bin/bash
set -euo pipefail

# Financial Agent - Azure Dev Environment Setup
echo "🚀 Setting up Azure Dev Environment for Financial Agent"

# Configuration
RESOURCE_GROUP="FinancialAgent"
AKS_CLUSTER="FinancialAgent-AKS"
KEY_VAULT_NAME="financial-agent-dev-kv"
LOCATION="koreacentral"
IDENTITY_NAME="financial-agent-dev-identity"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1"
    exit 1
}

# Check if logged into Azure
log "Checking Azure login status..."
if ! az account show &>/dev/null; then
    error "Please login to Azure: az login"
fi

# Get current subscription
SUBSCRIPTION_ID=$(az account show --query id -o tsv)
log "Using subscription: $SUBSCRIPTION_ID"

# 1. Enable Workload Identity on AKS
log "Enabling Workload Identity on AKS cluster..."
az aks update \
    --resource-group "$RESOURCE_GROUP" \
    --name "$AKS_CLUSTER" \
    --enable-workload-identity \
    --enable-oidc-issuer \
    || warning "Workload Identity may already be enabled"

# Get OIDC issuer URL
OIDC_ISSUER=$(az aks show --resource-group "$RESOURCE_GROUP" --name "$AKS_CLUSTER" --query "oidcIssuerProfile.issuerUrl" -o tsv)
log "OIDC Issuer URL: $OIDC_ISSUER"

# 2. Create Key Vault for secrets
log "Creating Azure Key Vault..."
az keyvault create \
    --name "$KEY_VAULT_NAME" \
    --resource-group "$RESOURCE_GROUP" \
    --location "$LOCATION" \
    --enable-rbac-authorization \
    || warning "Key Vault may already exist"

# 3. Create Managed Identity
log "Creating Managed Identity..."
IDENTITY_RESOURCE_ID=$(az identity create \
    --resource-group "$RESOURCE_GROUP" \
    --name "$IDENTITY_NAME" \
    --query id -o tsv)

IDENTITY_CLIENT_ID=$(az identity show \
    --resource-group "$RESOURCE_GROUP" \
    --name "$IDENTITY_NAME" \
    --query clientId -o tsv)

success "Created identity with Client ID: $IDENTITY_CLIENT_ID"

# 4. Grant permissions to Key Vault
log "Granting Key Vault permissions to managed identity..."
az role assignment create \
    --assignee "$IDENTITY_CLIENT_ID" \
    --role "Key Vault Secrets User" \
    --scope "/subscriptions/$SUBSCRIPTION_ID/resourceGroups/$RESOURCE_GROUP/providers/Microsoft.KeyVault/vaults/$KEY_VAULT_NAME"

# 5. Install External Secrets Operator
log "Installing External Secrets Operator..."
kubectl get namespace external-secrets-system &>/dev/null || {
    helm repo add external-secrets https://charts.external-secrets.io
    helm repo update
    helm install external-secrets external-secrets/external-secrets \
        --namespace external-secrets-system \
        --create-namespace
}

# 6. Create GitHub OIDC federation (requires GitHub repo)
log "Setting up GitHub OIDC federation..."
read -p "Enter your GitHub repository (org/repo): " GITHUB_REPO

# Create Azure AD Application
APP_ID=$(az ad app create \
    --display-name "financial-agent-github-actions" \
    --query appId -o tsv)

# Create federated credential for main branch
az ad app federated-credential create \
    --id "$APP_ID" \
    --parameters "{
        \"name\": \"github-actions-main\",
        \"issuer\": \"https://token.actions.githubusercontent.com\",
        \"subject\": \"repo:$GITHUB_REPO:ref:refs/heads/main\",
        \"audiences\": [\"api://AzureADTokenExchange\"]
    }"

# Create service principal
SP_ID=$(az ad sp create --id "$APP_ID" --query id -o tsv)

# Grant AKS permissions
az role assignment create \
    --assignee "$APP_ID" \
    --role "Azure Kubernetes Service Cluster User Role" \
    --scope "/subscriptions/$SUBSCRIPTION_ID/resourceGroups/$RESOURCE_GROUP/providers/Microsoft.ContainerService/managedClusters/$AKS_CLUSTER"

# 7. Add sample secrets to Key Vault
log "Adding sample secrets to Key Vault..."
az keyvault secret set \
    --vault-name "$KEY_VAULT_NAME" \
    --name "alibaba-dashscope-api-key-dev" \
    --value "your-dashscope-api-key-here"

az keyvault secret set \
    --vault-name "$KEY_VAULT_NAME" \
    --name "database-url-dev" \
    --value "mongodb://your-database-url:27017/financial-agent-dev"

# Redis runs as internal Kubernetes service - no external secrets needed

# 8. Output GitHub Secrets
echo ""
success "✅ Azure Dev Environment Setup Complete!"
echo ""
echo "🔑 Add these secrets to your GitHub repository:"
echo "AZURE_CLIENT_ID: $APP_ID"
echo "AZURE_TENANT_ID: $(az account show --query tenantId -o tsv)"
echo "AZURE_SUBSCRIPTION_ID: $SUBSCRIPTION_ID"
echo ""
echo "🎯 Next steps:"
echo "1. Update secrets in Key Vault: $KEY_VAULT_NAME"
echo "2. Deploy to AKS: kubectl apply -k .pipeline/k8s/overlays/dev"
echo "3. Check deployment: kubectl get pods -n financial-agent-dev"
echo ""
echo "📝 Key Vault URL: https://$KEY_VAULT_NAME.vault.azure.net"
echo "🎮 AKS Cluster: $AKS_CLUSTER"

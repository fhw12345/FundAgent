#!/bin/bash
# Production Secret Initialization Script
# This script creates temporary secrets for production deployment
# These will be replaced by Azure Key Vault integration in the future

set -e

NAMESPACE="klinematrix-prod"

echo "Creating production secrets in namespace: $NAMESPACE"

# Get MongoDB password from existing secret (or generate if needed)
if kubectl get secret mongodb-secret -n $NAMESPACE &>/dev/null; then
    MONGO_PASSWORD=$(kubectl get secret mongodb-secret -n $NAMESPACE -o jsonpath='{.data.mongodb-root-password}' | base64 -d)
    echo "✓ Using existing MongoDB password"
else
    MONGO_PASSWORD=$(openssl rand -base64 32)
    echo "✓ Generated new MongoDB password"
    kubectl create secret generic mongodb-secret \
        --from-literal=mongodb-root-password="$MONGO_PASSWORD" \
        -n $NAMESPACE
fi

# URL-encode the MongoDB password for connection string
# This handles special characters like / which break URL parsing
MONGO_PASSWORD_ENCODED=$(python3 -c "import urllib.parse; import sys; print(urllib.parse.quote(sys.argv[1], safe=''))" "$MONGO_PASSWORD")

# Create MongoDB URL with encoded password
MONGODB_URL="mongodb://admin:${MONGO_PASSWORD_ENCODED}@mongodb-service:27017/klinematrix_prod?authSource=admin"

# Create backend secrets
kubectl create secret generic backend-secrets \
    --from-literal=mongodb-url="$MONGODB_URL" \
    --from-literal=dashscope-api-key="<PLACEHOLDER_DASHSCOPE_KEY>" \
    --from-literal=tencent-secret-id="<PLACEHOLDER_TENCENT_ID>" \
    --from-literal=tencent-secret-key="<PLACEHOLDER_TENCENT_KEY>" \
    --from-literal=jwt-secret="prod-jwt-$(openssl rand -hex 32)" \
    -n $NAMESPACE \
    --dry-run=client -o yaml | kubectl apply -f -

echo "✓ Backend secrets created/updated"
echo ""
echo "⚠️  IMPORTANT: Update the following placeholders for full functionality:"
echo "   - DashScope API key (for AI features)"
echo "   - Tencent Cloud credentials (for email)"
echo ""
echo "Update with:"
echo "  kubectl edit secret backend-secrets -n $NAMESPACE"

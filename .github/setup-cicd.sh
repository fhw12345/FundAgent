#!/bin/bash
# CI/CD Setup Script for Financial Agent
# Run this script to configure GitHub secrets and branch protection
#
# Prerequisites:
# - GitHub CLI (gh) installed and authenticated
# - Access to the repository as admin
# - Environment variables or interactive input for secrets
#
# Usage: ./setup-cicd.sh

set -e

REPO="HuskyDanny/FinancialAgent"

echo "═══════════════════════════════════════════════════════"
echo "       Financial Agent CI/CD Setup                      "
echo "═══════════════════════════════════════════════════════"
echo ""

# Check gh CLI
if ! command -v gh &> /dev/null; then
    echo "❌ GitHub CLI (gh) is not installed."
    echo "   Install: brew install gh"
    exit 1
fi

# Check authentication
if ! gh auth status &> /dev/null; then
    echo "❌ Not authenticated with GitHub CLI."
    echo "   Run: gh auth login"
    exit 1
fi

echo "✅ GitHub CLI authenticated"
echo ""

# ═══════════════════════════════════════════════════════════
# STEP 1: Configure Secrets (Interactive)
# ═══════════════════════════════════════════════════════════
echo "📦 Step 1: Configuring GitHub Secrets..."
echo ""
echo "⚠️  Secrets must be provided via environment variables or entered interactively."
echo "   Required secrets:"
echo "   - GEMINI_API_KEY: Google Gemini API key for AI PR summaries"
echo "   - AZURE_ACR_USERNAME: Azure Container Registry username"
echo "   - AZURE_ACR_PASSWORD: Azure Container Registry password"
echo "   - ACK_KUBECONFIG: Base64-encoded kubeconfig for Alibaba ACK"
echo ""

# Function to set secret from env var or prompt
set_secret() {
    local secret_name=$1
    local env_var_name=$2
    local description=$3

    # Check if already set in GitHub
    if gh secret list --repo "$REPO" | grep -q "^${secret_name}"; then
        echo "✓ $secret_name already configured"
        return 0
    fi

    # Check environment variable
    local value="${!env_var_name}"

    if [ -n "$value" ]; then
        echo "Setting $secret_name from environment variable..."
        gh secret set "$secret_name" --repo "$REPO" --body "$value"
        echo "✓ $secret_name configured"
    else
        echo "⚠️  $secret_name not set. Set it manually with:"
        echo "   gh secret set $secret_name --repo $REPO"
        echo "   Description: $description"
    fi
}

# Set secrets (from env vars or skip if not provided)
set_secret "GEMINI_API_KEY" "GEMINI_API_KEY" "Google Gemini API key"
set_secret "AZURE_ACR_USERNAME" "AZURE_ACR_USERNAME" "Azure ACR username"
set_secret "AZURE_ACR_PASSWORD" "AZURE_ACR_PASSWORD" "Azure ACR password"

# Handle kubeconfig specially (needs base64 encoding)
if gh secret list --repo "$REPO" | grep -q "^ACK_KUBECONFIG"; then
    echo "✓ ACK_KUBECONFIG already configured"
elif [ -f ~/.kube/config-ack-prod ]; then
    echo "Setting ACK_KUBECONFIG from ~/.kube/config-ack-prod..."
    ACK_CONFIG=$(base64 -i ~/.kube/config-ack-prod)
    gh secret set ACK_KUBECONFIG --repo "$REPO" --body "$ACK_CONFIG"
    echo "✓ ACK_KUBECONFIG configured"
else
    echo "⚠️  ACK_KUBECONFIG not set. Provide ~/.kube/config-ack-prod or set manually:"
    echo "   base64 -i /path/to/kubeconfig | gh secret set ACK_KUBECONFIG --repo $REPO"
fi

echo ""
echo "✅ Secrets check complete!"
echo ""

# ═══════════════════════════════════════════════════════════
# STEP 2: Configure Branch Protection
# ═══════════════════════════════════════════════════════════
echo "🔒 Step 2: Configuring Branch Protection..."
echo ""

# Apply branch protection rules
gh api -X PUT "repos/$REPO/branches/main/protection" \
  -H "Accept: application/vnd.github+json" \
  --input - <<EOF
{
  "required_status_checks": {
    "strict": true,
    "contexts": ["Unit Tests"]
  },
  "enforce_admins": false,
  "required_pull_request_reviews": {
    "dismiss_stale_reviews": true,
    "require_code_owner_reviews": false,
    "required_approving_review_count": 1
  },
  "restrictions": null,
  "allow_force_pushes": false,
  "allow_deletions": false
}
EOF

echo ""
echo "✅ Branch protection configured!"
echo ""

# ═══════════════════════════════════════════════════════════
# Summary
# ═══════════════════════════════════════════════════════════
echo "═══════════════════════════════════════════════════════"
echo "                   SETUP COMPLETE                       "
echo "═══════════════════════════════════════════════════════"
echo ""
echo "Branch protection on 'main':"
echo "  ✓ Require PR for all changes"
echo "  ✓ Require 1 approving review"
echo "  ✓ Require 'Unit Tests' status check"
echo "  ✓ Dismiss stale reviews on new commits"
echo "  ✓ Admin bypass enabled (allenpan can push directly)"
echo ""
echo "Verify secrets are configured:"
echo "  gh secret list --repo $REPO"
echo ""
echo "Next steps:"
echo "  1. Commit and push the workflow files"
echo "  2. Create a test branch: git checkout -b users/allen/test-cicd"
echo "  3. Make a small change and open a PR"
echo "  4. Verify the workflows run correctly"
echo ""

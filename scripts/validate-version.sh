#!/bin/bash
set -e

# Financial Agent Version Validation Script
# Ensures at least one component version has been incremented

echo "🔍 Validating version increment..."

# Get current versions from files
BACKEND_VERSION=$(grep '^version = ' backend/pyproject.toml | sed 's/version = "\(.*\)"/\1/')
FRONTEND_VERSION=$(node -p "require('./frontend/package.json').version" 2>/dev/null || echo "0.0.0")

echo "Current versions:"
echo "  Backend:  $BACKEND_VERSION"
echo "  Frontend: $FRONTEND_VERSION"

# Get previous commit versions
git fetch --tags 2>/dev/null || true

PREV_BACKEND_VERSION=$(git show HEAD~1:backend/pyproject.toml 2>/dev/null | grep '^version = ' | sed 's/version = "\(.*\)"/\1/' || echo "0.0.0")
PREV_FRONTEND_VERSION=$(git show HEAD~1:frontend/package.json 2>/dev/null | node -p "JSON.parse(require('fs').readFileSync('/dev/stdin', 'utf-8')).version" || echo "0.0.0")

echo ""
echo "Previous versions:"
echo "  Backend:  $PREV_BACKEND_VERSION"
echo "  Frontend: $PREV_FRONTEND_VERSION"

# Function to compare semantic versions
version_gt() {
    test "$(printf '%s\n' "$@" | sort -V | head -n 1)" != "$1"
}

# Check if at least one version has incremented
BACKEND_INCREMENTED=false
FRONTEND_INCREMENTED=false

if version_gt "$BACKEND_VERSION" "$PREV_BACKEND_VERSION"; then
    BACKEND_INCREMENTED=true
fi

if version_gt "$FRONTEND_VERSION" "$PREV_FRONTEND_VERSION"; then
    FRONTEND_INCREMENTED=true
fi

echo ""
if [[ "$BACKEND_INCREMENTED" == true ]]; then
    echo "✅ Backend version incremented: $PREV_BACKEND_VERSION → $BACKEND_VERSION"
fi

if [[ "$FRONTEND_INCREMENTED" == true ]]; then
    echo "✅ Frontend version incremented: $PREV_FRONTEND_VERSION → $FRONTEND_VERSION"
fi

# Validation result
if [[ "$BACKEND_INCREMENTED" == false ]] && [[ "$FRONTEND_INCREMENTED" == false ]]; then
    echo ""
    echo "❌ ERROR: No version increment detected!"
    echo ""
    echo "At least one component version must be incremented."
    echo ""
    echo "To bump version:"
    echo "  ./scripts/bump-version.sh backend patch   # For backend changes"
    echo "  ./scripts/bump-version.sh frontend patch  # For frontend changes"
    echo ""
    exit 1
fi

# Check for version decrements (shouldn't happen)
if version_gt "$PREV_BACKEND_VERSION" "$BACKEND_VERSION"; then
    echo ""
    echo "❌ ERROR: Backend version decreased!"
    echo "  Previous: $PREV_BACKEND_VERSION"
    echo "  Current:  $BACKEND_VERSION"
    exit 1
fi

if version_gt "$PREV_FRONTEND_VERSION" "$FRONTEND_VERSION"; then
    echo ""
    echo "❌ ERROR: Frontend version decreased!"
    echo "  Previous: $PREV_FRONTEND_VERSION"
    echo "  Current:  $FRONTEND_VERSION"
    exit 1
fi

# Check for duplicate tags
if [[ "$BACKEND_INCREMENTED" == true ]]; then
    if git rev-parse "backend-v$BACKEND_VERSION" >/dev/null 2>&1; then
        echo ""
        echo "❌ ERROR: Git tag backend-v$BACKEND_VERSION already exists!"
        echo "  This version has already been released."
        echo "  Please increment to a new version."
        exit 1
    fi
fi

if [[ "$FRONTEND_INCREMENTED" == true ]]; then
    if git rev-parse "frontend-v$FRONTEND_VERSION" >/dev/null 2>&1; then
        echo ""
        echo "❌ ERROR: Git tag frontend-v$FRONTEND_VERSION already exists!"
        echo "  This version has already been released."
        echo "  Please increment to a new version."
        exit 1
    fi
fi

echo ""
echo "✅ Version validation passed!"
echo ""

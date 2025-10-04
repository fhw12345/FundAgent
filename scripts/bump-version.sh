#!/bin/bash
set -e

# Financial Agent Version Bumping Script
# Usage: ./scripts/bump-version.sh [backend|frontend] [major|minor|patch]

COMPONENT=$1
BUMP_TYPE=$2

if [[ -z "$COMPONENT" ]] || [[ -z "$BUMP_TYPE" ]]; then
    echo "Usage: $0 [backend|frontend] [major|minor|patch]"
    echo ""
    echo "Examples:"
    echo "  $0 backend patch   # 0.1.0 → 0.1.1"
    echo "  $0 backend minor   # 0.1.1 → 0.2.0"
    echo "  $0 backend major   # 0.2.0 → 1.0.0"
    echo "  $0 frontend patch  # 0.1.0 → 0.1.1"
    exit 1
fi

if [[ "$COMPONENT" != "backend" ]] && [[ "$COMPONENT" != "frontend" ]]; then
    echo "Error: Component must be 'backend' or 'frontend'"
    exit 1
fi

if [[ "$BUMP_TYPE" != "major" ]] && [[ "$BUMP_TYPE" != "minor" ]] && [[ "$BUMP_TYPE" != "patch" ]]; then
    echo "Error: Bump type must be 'major', 'minor', or 'patch'"
    exit 1
fi

# Get current version from git HEAD (last committed version)
# This prevents version increment on failed commits
if [[ "$COMPONENT" == "backend" ]]; then
    VERSION_FILE="backend/pyproject.toml"
    # Try to get version from git HEAD, fall back to current file if not in git
    CURRENT_VERSION=$(git show HEAD:"$VERSION_FILE" 2>/dev/null | grep '^version = ' | sed 's/version = "\(.*\)"/\1/' || grep '^version = ' "$VERSION_FILE" | sed 's/version = "\(.*\)"/\1/')
else
    VERSION_FILE="frontend/package.json"
    # Try to get version from git HEAD, fall back to current file if not in git
    CURRENT_VERSION=$(git show HEAD:"$VERSION_FILE" 2>/dev/null | node -p "JSON.parse(require('fs').readFileSync('/dev/stdin', 'utf8')).version" || node -p "require('./frontend/package.json').version")
fi

echo "Last committed $COMPONENT version: $CURRENT_VERSION"

# Parse version
IFS='.' read -r MAJOR MINOR PATCH <<< "$CURRENT_VERSION"

# Bump version
case $BUMP_TYPE in
    major)
        MAJOR=$((MAJOR + 1))
        MINOR=0
        PATCH=0
        ;;
    minor)
        MINOR=$((MINOR + 1))
        PATCH=0
        ;;
    patch)
        PATCH=$((PATCH + 1))
        ;;
esac

NEW_VERSION="$MAJOR.$MINOR.$PATCH"
echo "New $COMPONENT version: $NEW_VERSION"

# Update version file
if [[ "$COMPONENT" == "backend" ]]; then
    sed -i.bak "s/^version = \".*\"/version = \"$NEW_VERSION\"/" "$VERSION_FILE"
    rm "${VERSION_FILE}.bak"
else
    # Use npm version to update package.json
    cd frontend
    npm version "$NEW_VERSION" --no-git-tag-version
    cd ..
fi

echo "✅ Updated $VERSION_FILE to version $NEW_VERSION"

# Prompt for changelog entry
echo ""
echo "Enter changelog entry (or press Enter to skip):"
read -r CHANGELOG_ENTRY

if [[ -n "$CHANGELOG_ENTRY" ]]; then
    CHANGELOG_FILE="docs/project/versions/$COMPONENT/CHANGELOG.md"
    TODAY=$(date +%Y-%m-%d)

    # Create temporary changelog with new entry
    {
        sed -n '1,/## \[Unreleased\]/p' "$CHANGELOG_FILE"
        echo ""
        echo "## [$NEW_VERSION] - $TODAY"
        echo ""
        echo "### Added"
        echo "- $CHANGELOG_ENTRY"
        echo ""
        sed -n '/## \[Unreleased\]/,$ { /## \[Unreleased\]/d; p; }' "$CHANGELOG_FILE"
    } > "${CHANGELOG_FILE}.tmp"

    mv "${CHANGELOG_FILE}.tmp" "$CHANGELOG_FILE"
    echo "✅ Updated $CHANGELOG_FILE"
fi

# Create version documentation file
VERSION_DOC="docs/project/versions/$COMPONENT/v$NEW_VERSION.md"
if [[ ! -f "$VERSION_DOC" ]]; then
    cat > "$VERSION_DOC" <<EOF
# $(echo $COMPONENT | sed 's/\b\(.\)/\u\1/g') v$NEW_VERSION

**Release Date**: $(date +%Y-%m-%d)
**Docker Image**: \`financial-agent/$COMPONENT:$NEW_VERSION\`

## Overview

[Brief description of this release]

## Features Added

- [Feature 1]
- [Feature 2]

## Bug Fixes

- [Bug fix 1]

## Breaking Changes

None

## Compatibility

| Component | Required Version |
|-----------|-----------------|
| [Dependency] | [Version] |

## Known Issues

None

## Migration Guide

[Migration instructions if needed]
EOF
    echo "✅ Created $VERSION_DOC"
    echo "   Please edit this file to add release details"
fi

# Summary
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ Version bump complete!"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Component: $COMPONENT"
echo "Old version: $CURRENT_VERSION"
echo "New version: $NEW_VERSION"
echo ""
echo "Next steps:"
echo "1. Review and edit: $VERSION_DOC"
echo "2. Commit changes: git add . && git commit -m \"chore: bump $COMPONENT to v$NEW_VERSION\""
echo "3. Tag release: git tag $COMPONENT-v$NEW_VERSION"
echo "4. Build image: az acr build --image financial-agent/$COMPONENT:$NEW_VERSION ..."
echo ""

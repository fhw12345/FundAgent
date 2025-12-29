# Troubleshooting Guide

This directory contains documentation for bugs, fixes, and common issues encountered during development and deployment.

## Quick Index

### Common Issues

**🚨 Critical (Stop & Fix Immediately)**
- [Docker Env Reload Issue](docker-env-reload-issue.md) - Containers don't reload env vars on restart
- [Deployment Issues](deployment-issues.md) - Pod crashes, image pulls, Kubernetes problems

**⚠️ High Priority**
- [CORS & API Connectivity](cors-api-connectivity.md) - CORS errors, localhost issues, nginx proxy problems
- [External Secrets Sync](external-secrets-sync.md) - Secrets not updating from Azure Key Vault
- [Streaming Issues](streaming-issues.md) - SSE streaming, agent response issues
- [SLS Logging Issues](sls-logging-issues.md) - Logs not appearing in Alibaba Cloud SLS

**📋 Standard Priority**
- [Data Validation](data-validation-issues.md) - Pydantic validation errors, data format mismatches
- [MongoDB Cosmos DB](mongodb-cosmos-db.md) - Throughput modes, indexes, unique constraints
- [Git History Rewrite](git-history-rewrite.md) - Team awareness for git history rewrites
- [Technical Analysis Limitations](technical-analysis-limitations.md) - Intraday analysis not available
- [Transaction Reconciliation Fix](transaction-reconciliation-datetime-fix.md) - Datetime deprecation fix
- [Frontend Issues](frontend-issues.md) - React, TypeScript, build problems
- [Kubernetes Issues](kubernetes-issues.md) - K8s-specific debugging
- [Symbol Injection Race Condition](symbol-injection-race-condition.md) - Chat symbol context issues
- [Slow ACR to ACK Image Pull](slow-acr-to-ack-image-pull.md) - Cross-region image pulls

### Bug Reports
- [Known Bugs](known-bugs.md) - Current open issues and workarounds
- [Fixed Bugs](fixed-bugs.md) - Resolved issues and solutions

## How to Use This Section

### For Developers
When you encounter an issue:
1. **Search here first** - Check if the issue is already documented
2. **Follow the fix** - Apply the documented solution
3. **Document new issues** - Add to the appropriate file if not found

### For New Team Members
- Start with [Common Issues](#common-issues) to understand typical problems
- Review [Fixed Bugs](fixed-bugs.md) to learn from past solutions
- Check [Known Bugs](known-bugs.md) for current limitations

## Adding New Issues

### For New Bugs
Add to `known-bugs.md` with this template:
```markdown
## [Bug Title]

**Symptom**: What the user sees
**Cause**: Root cause of the issue
**Workaround**: Temporary solution (if any)
**Status**: Open/In Progress/Fixed
**Related**: Links to related issues
```

### For Fixed Bugs
Move from `known-bugs.md` to `fixed-bugs.md` with:
```markdown
## [Bug Title] - Fixed YYYY-MM-DD

**Problem**: Original issue description
**Root Cause**: What caused the bug
**Solution**: How it was fixed
**Code Changes**: Files modified
**Verification**: How to test the fix
```

### For Common Issues
Add to the appropriate category file:
```markdown
### Issue: [Description]

**Symptoms**:
- What you see/error messages

**Diagnosis**:
```bash
# Commands to diagnose
```

**Solution**:
```bash
# Commands to fix
```

**Prevention**: How to avoid in future
```

## Issue Categories

### 🚨 Docker Environment Variables (CRITICAL)
Containers freezing environment variables at creation time, `restart` vs `recreate`, env var debugging

### CORS & API Connectivity
Frontend cannot connect to backend, CORS errors, proxy issues

### Data Validation
Pydantic validation failures, type mismatches, data format issues

### Deployment Issues
Kubernetes problems, image pulls, pod crashes, health check failures

### External Secrets Sync
Azure Key Vault secret updates not syncing, force-sync procedures, secret rotation workflows

### MongoDB Cosmos DB
Azure Cosmos DB limitations, throughput modes, index configuration, unique constraints with NULL values

### SLS Logging
Alibaba Cloud SLS log collection issues, AliyunLogConfig CRD troubleshooting, loongcollector container matching

## Historical Reference

For resolved issues with detailed root cause analysis (ACK-specific, CORS deep dives, etc.), see [docs/archive/troubleshooting-history/](../archive/troubleshooting-history/).

## Emergency Contacts

If you encounter a critical production issue:
1. Check [deployment/workflow.md](../deployment/workflow.md) for rollback procedures
2. Review logs: `kubectl logs -f deployment/backend -n klinematrix-prod`
3. Check health: `curl https://klinecubic.cn/api/health`

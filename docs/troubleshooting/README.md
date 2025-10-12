# Troubleshooting Guide

This directory contains documentation for bugs, fixes, and common issues encountered during development and deployment.

## Quick Index

### Common Issues
- [CORS & API Connectivity](cors-api-connectivity.md) - CORS errors, localhost issues, nginx proxy problems
- [Data Validation](data-validation-issues.md) - Pydantic validation errors, data format mismatches
- [Deployment Issues](deployment-issues.md) - Pod crashes, image pulls, Kubernetes problems, service selectors
- [MongoDB Indexes](mongodb-unique-indexes-with-nulls.md) - Unique index handling with NULL values

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

### CORS & API Connectivity
Frontend cannot connect to backend, CORS errors, proxy issues

### Data Validation
Pydantic validation failures, type mismatches, data format issues

### Deployment Issues
Kubernetes problems, image pulls, pod crashes, health check failures

### MongoDB Indexes
Unique index configuration, handling NULL values in multi-auth systems

## Emergency Contacts

If you encounter a critical production issue:
1. Check [deployment/workflow.md](../deployment/workflow.md) for rollback procedures
2. Review logs: `kubectl logs -f deployment/backend -n klinematrix-test`
3. Check health: `curl https://klinematrix.com/api/health`

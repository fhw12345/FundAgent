# TestSprite Testing Setup & Troubleshooting

## Overview

TestSprite is an MCP (Model Context Protocol) tool for automated E2E testing. This document covers setup, common issues, and workarounds.

## Test Plans Created

We have comprehensive test plans ready:
- **Backend**: `testsprite_tests/testsprite_backend_test_plan.json` (15 API test cases)
- **Frontend**: `testsprite_tests/testsprite_frontend_test_plan.json` (15 UI test cases)
- **PRD**: `testsprite_tests/standard_prd.json` (Product requirements)
- **Code Summary**: `testsprite_tests/tmp/code_summary.json` (18 features)

## Proxy Configuration Issue

**Problem**: macOS system proxy (`127.0.0.1:7890`) blocks TestSprite tunnel connection.

**Solution**: Use `NO_PROXY` environment variable to bypass proxy for TestSprite domains.

### Quick Start

```bash
# Method 1: Use the helper script
./scripts/run-testsprite.sh

# Method 2: Run manually with NO_PROXY
NO_PROXY="tun.testsprite.com,testsprite-nlb-a31ae558ab59c16f.elb.us-east-1.amazonaws.com,35.170.174.200,3.223.9.40" \
no_proxy="tun.testsprite.com,testsprite-nlb-a31ae558ab59c16f.elb.us-east-1.amazonaws.com,35.170.174.200,3.223.9.40" \
node ~/.npm/_npx/8ddf6bea01b2519d/node_modules/@testsprite/testsprite-mcp/dist/index.js generateCodeAndExecute
```

## Troubleshooting Steps

### 1. Proxy Timeout Issues

**Symptoms**:
```
Error: Timeout connecting to tun.testsprite.com:7300
```

**Diagnosis**:
```bash
# Check system proxy settings
scutil --proxy | grep -E "(HTTPProxy|HTTPSProxy)"

# Check environment variables
env | grep -i proxy

# Test direct connection
nc -zv -w 5 tun.testsprite.com 7300
```

**Fix**: Use `NO_PROXY` as shown above.

### 2. Authentication Issues

**Symptoms**:
```
Error: Expected authentication challenge, but no secret was required.
Received: {"Error":"client not exist."}
```

**Fix**: Ensure TestSprite API key is configured in Claude Code MCP settings.

### 3. Backend Service Issues

**Symptoms**:
```
Error: No response from backend
```

**Possible Causes**:
1. TestSprite cloud service is down or slow
2. API rate limiting
3. Network instability

**What We've Verified**:
- ✅ Local services (frontend/backend) are running and healthy
- ✅ Tunnel authentication succeeds
- ✅ Proxy bypass works correctly

**Next Steps**:
- Wait a few minutes and retry
- Check TestSprite service status
- Contact TestSprite support if persistent

## Test Execution

### Prerequisites

1. **Local services running**:
   ```bash
   docker compose ps
   # Verify backend (port 8000) and frontend (port 3000) are UP
   ```

2. **Services healthy**:
   ```bash
   curl http://localhost:8000/api/health
   curl -I http://localhost:3000
   ```

3. **TestSprite API key configured** in Claude Code MCP settings

### Expected Execution Flow

1. **Tunnel Setup** (10-30 seconds)
   ```
   🚀 Starting test execution...
   Proxy port: 57046
   Tunnel started successfully! Proxy URL: http://...@tun.testsprite.com:8080
   ```

2. **Test Execution** (5-15 minutes)
   ```
   ⚡ Running tests...
   This process may take anywhere from several minutes up to 15 minutes to complete.
   ```

3. **Report Generation**
   - Raw report: `testsprite_tests/tmp/raw_report.md`
   - Final report: `testsprite_tests/testsprite-mcp-test-report.md`

## Network Configuration

### Verified Working Configuration

```bash
# Add to ~/.zshrc or ~/.bashrc for permanent fix
export NO_PROXY="tun.testsprite.com,testsprite-nlb-a31ae558ab59c16f.elb.us-east-1.amazonaws.com,35.170.174.200,3.223.9.40"
export no_proxy="$NO_PROXY"
```

### TestSprite Infrastructure

- **Tunnel Domain**: `tun.testsprite.com`
- **Tunnel Port**: `7300` (TCP)
- **Proxy Port**: `8080` (HTTP)
- **AWS ELB**: `testsprite-nlb-a31ae558ab59c16f.elb.us-east-1.amazonaws.com`
- **IP Addresses**: `35.170.174.200`, `3.223.9.40`

## Known Limitations

1. **Proxy Interference**: System-wide proxy settings affect Node.js applications
2. **Service Availability**: TestSprite backend may experience occasional outages
3. **Execution Time**: Tests can take 5-15 minutes to complete
4. **Network Stability**: Requires stable internet connection throughout execution

## Alternative Testing

If TestSprite continues to fail, consider:

1. **Native Playwright Tests**: Convert test plans to Playwright scripts
2. **Manual Testing**: Use test plans as manual testing checklist
3. **Cypress**: Alternative E2E testing framework
4. **Jest + Testing Library**: For component-level testing

## References

- Test Plans: `testsprite_tests/`
- TestSprite Logs: `~/.testsprite/mcp.log`
- Helper Script: `scripts/run-testsprite.sh`
- MCP Configuration: Claude Code settings

## Support

If issues persist:
1. Check `~/.testsprite/mcp.log` for detailed errors
2. Verify local services are healthy
3. Test proxy bypass with `curl` commands above
4. Contact TestSprite support with log excerpts

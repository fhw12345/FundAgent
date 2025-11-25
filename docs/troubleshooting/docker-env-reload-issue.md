# Docker Environment Variable Reload Issue

**Date**: 2025-11-23
**Severity**: Critical
**Category**: Configuration Management

## Problem Summary

Docker Compose containers **do not automatically reload** environment variables from `.env` files when the files are modified. Running containers keep their original environment variables until **recreated**.

## Incident Details

### What Happened

The `portfolio-cron` service was running with incorrect configuration:
- **Expected**: `CRON_ENABLED=false`, `CRON_INTERVAL_MINUTES=1440` (24 hours)
- **Actual**: `CRON_ENABLED=true`, `CRON_INTERVAL_MINUTES=5` (5 minutes)

This caused:
- 99 portfolio analysis runs in ~25 hours
- 33 duplicate chat threads created
- Unnecessary database bloat and API quota consumption

### Root Cause

1. Container was created with initial values (likely `CRON_ENABLED=true`, `CRON_INTERVAL_MINUTES=5`)
2. `.env.development` was later updated to `CRON_ENABLED=false`, `CRON_INTERVAL_MINUTES=1440`
3. **Container kept the old values** because Docker doesn't hot-reload env vars
4. `docker compose restart` was used, which **does NOT reload environment variables**

## Technical Deep Dive

### How Docker Compose Loads Environment Variables

**Order of precedence** (highest to lowest):
1. Shell environment variables (from current terminal session)
2. `environment:` section in `docker-compose.yml`
3. `env_file:` files (e.g., `.env.development`)
4. Default values in bash scripts (e.g., `${VAR:-default}`)

**Critical insight**: These values are read **once at container creation** and then frozen.

### The Bash Script Pattern

```yaml
portfolio-cron:
  command: >
    bash -c "
      INTERVAL=$${CRON_INTERVAL_MINUTES:-1440};
      ENABLED=$${CRON_ENABLED:-true};

      if [ \"$$ENABLED\" = \"false\" ]; then
        echo 'Cron disabled. Sleeping indefinitely...';
        sleep infinity;
      fi;

      while true; do
        python scripts/run_portfolio_analysis.py;
        sleep $$((INTERVAL * 60));
      done
    "
  env_file:
    - ./backend/.env.development
```

**How it works**:
- `${CRON_INTERVAL_MINUTES:-1440}` - Use env var, default to 1440
- `${CRON_ENABLED:-true}` - Use env var, default to true
- Script reads these **from container's environment** (set at creation time)

## Solution

### Immediate Fix

```bash
# ❌ WRONG - Does NOT reload env vars
docker compose restart portfolio-cron

# ✅ CORRECT - Recreates container with fresh env
docker compose stop portfolio-cron
docker compose rm -f portfolio-cron
docker compose up -d portfolio-cron

# ✅ ALTERNATIVE - Force recreate
docker compose up -d --force-recreate portfolio-cron
```

### Verification

```bash
# Check actual env vars in running container
docker compose exec portfolio-cron printenv | grep CRON

# Check logs for configuration
docker compose logs portfolio-cron --tail=20

# Should show:
# Portfolio Cron Configuration:
#   Enabled: false
#   Interval: 1440 minutes
# Cron disabled. Sleeping indefinitely...
```

## Prevention Rules

### ⚠️ CRITICAL RULES - Never Violate

1. **After changing `.env` files, ALWAYS recreate containers**
   ```bash
   docker compose up -d --force-recreate <service-name>
   ```

2. **NEVER trust `docker compose restart` to reload env vars**
   - It only restarts the process, not the container
   - Environment variables remain unchanged

3. **ALWAYS verify env vars after container creation**
   ```bash
   docker compose exec <service> printenv | grep <VAR_PREFIX>
   ```

4. **Document expected env vars in comments**
   ```yaml
   # Expected: CRON_ENABLED=false, CRON_INTERVAL_MINUTES=1440
   portfolio-cron:
     env_file:
       - ./backend/.env.development
   ```

### Best Practices

**1. Check before assuming**
```bash
# Before changing .env files
docker compose exec service printenv | grep VAR_NAME

# After changing .env files
docker compose up -d --force-recreate service
docker compose exec service printenv | grep VAR_NAME  # Verify!
```

**2. Use explicit recreation commands**
```bash
# For single service
docker compose up -d --force-recreate service-name

# For all services
docker compose down
docker compose up -d
```

**3. Add health checks to detect misconfigurations**
```python
# In application startup
expected_interval = 1440
actual_interval = int(os.getenv("CRON_INTERVAL_MINUTES", "1440"))
if actual_interval != expected_interval:
    logger.warning(f"Unexpected interval: {actual_interval}, expected {expected_interval}")
```

## Commands Reference

### Inspect Container Environment

```bash
# View all env vars
docker inspect <container-id> --format='{{range .Config.Env}}{{println .}}{{end}}'

# View specific var
docker compose exec service printenv VAR_NAME

# View docker-compose resolved config
docker compose config
```

### Reload Environment Variables

```bash
# Method 1: Force recreate (recommended)
docker compose up -d --force-recreate service-name

# Method 2: Stop, remove, start (more explicit)
docker compose stop service-name
docker compose rm -f service-name
docker compose up -d service-name

# Method 3: Full stack recreation
docker compose down
docker compose up -d
```

### Debug Environment Issues

```bash
# Compare expected vs actual
cat backend/.env.development | grep CRON
docker compose exec portfolio-cron printenv | grep CRON

# Check when container was created
docker inspect portfolio-cron-1 --format='{{.Created}}'

# Check .env file modification time
stat -f "Modified: %Sm" backend/.env.development
```

## Related Issues

- **Issue**: Container ignoring updated environment variables
- **Symptom**: Logs show old/unexpected configuration values
- **Fix**: Recreate container with `--force-recreate`

## Key Takeaways

1. **Docker containers do NOT hot-reload environment variables**
2. **`restart` ≠ `recreate`** - Use `--force-recreate` to reload env vars
3. **Always verify** env vars after modifying `.env` files
4. **When in doubt, recreate** - It's safer than assuming restart worked

## References

- [Docker Compose Environment Variables](https://docs.docker.com/compose/environment-variables/)
- [Docker Compose CLI Reference](https://docs.docker.com/compose/reference/)
- Local issue: Portfolio cron running every 5 minutes despite `CRON_ENABLED=false` (2025-11-23)

# Redis Cache Performance Baseline

**Collected**: 2025-12-23
**Environment**: Local Development (docker-compose)
**Last Updated**: 2025-12-23 (Story 1.3 enhancements)

---

## Cache Statistics

### Hit/Miss Metrics (Pre-Optimization Baseline)

| Metric | Value | Analysis |
|--------|-------|----------|
| **Keyspace Hits** | 7,069,218 | Cache hits |
| **Keyspace Misses** | 15,189,792 | Cache misses |
| **Hit Ratio** | **31.76%** | 🔴 Critical - Target is >80% |
| **Total Commands** | 52,289,705 | High activity |
| **Ops/Second** | 41 | Current throughput |

### Cache Hit Ratio Calculation

```
Hit Ratio = Hits / (Hits + Misses)
         = 7,069,218 / (7,069,218 + 15,189,792)
         = 7,069,218 / 22,259,010
         = 31.76%
```

**⚠️ CRITICAL FINDING**: Hit ratio of 31.76% is significantly below the 80%+ target. This means 68% of cache lookups result in misses, causing unnecessary API calls to external services.

---

## Memory Usage

| Metric | Value |
|--------|-------|
| **Used Memory** | 2.78 MB |
| **Peak Memory** | 5.28 MB |
| **Memory Dataset** | 1.37 MB (68.18%) |
| **System Memory** | 7.65 GB available |
| **Evicted Keys** | 0 |
| **Expired Keys** | 950,696 |

**Analysis**: Memory usage is minimal. No eviction pressure indicates TTL-based expiration is working correctly.

---

## Story 1.3 Enhancements (Implemented)

### 1. Centralized TTL Configuration

TTL values are now configurable via `backend/src/core/config.py`:

```python
# Cache settings - TTL values in seconds by data category
cache_ttl_realtime: int = 60       # Real-time quotes (1 min)
cache_ttl_price_data: int = 300    # Price data (5 min)
cache_ttl_analysis: int = 1800     # Analysis results (30 min)
cache_ttl_news: int = 3600         # News/sentiment (1 hour)
cache_ttl_historical: int = 7200   # Historical data (2 hours)
cache_ttl_fundamentals: int = 86400  # Company fundamentals (24 hours)
cache_ttl_insights: int = 1800     # AI insights (30 min)
```

### 2. Cache Warming Service

Startup warming pre-populates cache with common symbols:

```python
# Default symbols warmed on startup
DEFAULT_SYMBOLS = ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA", "SPY", "QQQ", "BRK.B"]
```

Admin endpoints for manual warming:
- `POST /api/admin/cache/warm` - Warm default symbols
- `POST /api/admin/cache/warm-market-movers` - Warm current market movers
- `GET /api/admin/cache/warming-status` - Check warming status

### 3. Request Deduplication (Thundering Herd Prevention)

`RedisCache.get_with_dedup()` method prevents multiple concurrent requests from fetching the same data:

```python
# Pattern: Lock-based deduplication
async def get_with_dedup(cache_key, fetch_func, ttl_seconds):
    # 1. Check cache
    # 2. If miss, acquire lock
    # 3. Winner fetches data, losers wait for cache
    # 4. Timeout fallback for safety
```

### 4. Cache Hit/Miss Logging

Debug-level logging for monitoring cache efficiency:
```
logger.debug("Cache HIT", cache_key=key)
logger.debug("Cache MISS", cache_key=key)
```

### 5. Redis Statistics Endpoint

`GET /api/admin/cache/stats` returns comprehensive metrics:
- Memory usage (used, peak, fragmentation)
- Key counts (total, with expiry, expired, evicted)
- Cache efficiency (hits, misses, hit ratio %)
- Connection info and performance metrics

---

## Caching Patterns

### Cache-Aside Pattern (Implemented)

```python
# backend/src/database/redis.py
async def get(key: str) -> Any | None:
    value = await self.client.get(key)
    if value:
        logger.debug("Cache HIT", cache_key=key)
        return json.loads(value)
    logger.debug("Cache MISS", cache_key=key)
    return None

async def set(key: str, value: Any, ttl_seconds: int | None = None):
    json_value = json.dumps(value, default=str)
    await self.client.set(key, json_value, ex=ttl_seconds)
```

### Cache Invalidation Patterns

**Time-Based (TTL)**:
- All cache entries have TTL configured by data category
- No manual invalidation needed for most cases
- TTL values tuned by data freshness requirements

**Date-Based Keys**:
- Many cache keys include date: `{type}:{symbol}:{YYYY-MM-DD}`
- Natural daily refresh without explicit invalidation
- Example: `fundamentals:AAPL:2025-12-23`

**Manual Invalidation**:
- Use `redis_cache.delete(key)` when data is explicitly updated
- Currently minimal need due to read-heavy workload

---

## Known Cache Keys

| Key Pattern | Purpose | TTL | Source |
|-------------|---------|-----|--------|
| `quote:{symbol}:{date}` | Real-time quotes | 60s | `cache_ttl_realtime` |
| `market_data:{symbol}` | Market quotes | 300s | `cache_ttl_price_data` |
| `fundamentals:{symbol}:{date}` | Company fundamentals | 86400s | `cache_ttl_fundamentals` |
| `company_overview:{symbol}:{date}` | Company overview | 86400s | `cache_ttl_fundamentals` |
| `news_sentiment:{symbol}:{date}` | News sentiment | 3600s | `cache_ttl_news` |
| `market_movers:{date}` | Top gainers/losers | 3600s | `cache_ttl_news` |
| `analysis:{type}:{symbol}:{date}` | Analysis results | 1800s | `cache_ttl_analysis` |
| `insights:{category}:{date}` | AI insights | 1800s | `cache_ttl_insights` |
| `lock:{cache_key}` | Deduplication locks | 30s | Fixed |

---

## Monitoring Commands

### Via Admin API (Recommended)

```bash
# Get comprehensive cache stats (requires admin auth)
curl -s -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/api/admin/cache/stats | jq

# Trigger manual cache warming
curl -X POST -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/api/admin/cache/warm

# Check warming status
curl -s -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/api/admin/cache/warming-status
```

### Via Redis CLI (Development)

```bash
# Get cache stats
docker compose exec redis redis-cli INFO stats | grep keyspace

# Get memory stats
docker compose exec redis redis-cli INFO memory

# List all keys (development only)
docker compose exec redis redis-cli KEYS "*"

# Monitor live operations (impacts performance)
docker compose exec redis redis-cli MONITOR
```

---

## Expected Improvements

After Story 1.3 enhancements, expected metrics:

| Metric | Before | Target | Improvement |
|--------|--------|--------|-------------|
| **Hit Ratio** | 31.76% | >80% | +150% |
| **API Calls Saved** | - | ~50% reduction | Cost savings |
| **Cold Start Misses** | High | Low | Cache warming |
| **Thundering Herd** | Possible | Prevented | Deduplication |

---

## Files Modified (Story 1.3)

- `backend/src/core/config.py` - Added centralized TTL settings
- `backend/src/database/redis.py` - Added deduplication, stats, logging
- `backend/src/services/cache_warming_service.py` - New service
- `backend/src/api/admin.py` - Added cache admin endpoints
- `backend/src/api/analysis/*.py` - Updated to use config TTLs
- `backend/src/services/insights/base.py` - Updated to use config TTLs

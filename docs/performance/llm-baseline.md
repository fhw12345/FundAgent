# LLM/Agent Performance Baseline

**Collected**: 2025-12-24
**Environment**: Production (Langfuse at https://monitor.klinecubic.cn)

---

## Agent Architecture

### LangGraph ReAct Agent

- **Implementation**: `backend/src/agent/langgraph_react_agent.py`
- **Endpoint**: `/api/chat/stream-react`
- **Model**: Qwen via Alibaba DashScope
- **Pattern**: Autonomous tool chaining with compressed results

### Observability

- **Langfuse URL**: https://monitor.klinecubic.cn
- **Integration**: `@observe` decorators for automatic tracing
- **Status**: Enabled in production

---

## Performance Measurement Infrastructure

### Admin Endpoints (Story 1.4)

| Endpoint | Purpose | Response |
|----------|---------|----------|
| `GET /api/admin/llm/tool-performance?days=7` | Tool execution metrics | Avg/P50/P95/P99 duration, success rate, cache hit rate |
| `GET /api/admin/llm/slowest-tools?days=7` | Identify optimization targets | Slowest tools by avg execution time |
| `GET /api/admin/timing-metrics` | API endpoint latency | P50/P95/P99 for all endpoints |
| `GET /api/admin/cache/stats` | Redis cache efficiency | Hit/miss ratio, memory usage |

### Data Sources

1. **Tool Execution Repository** (`tool_executions` collection)
   - Records every tool call with timing, status, cache hit
   - Aggregation queries for performance analysis

2. **Langfuse Traces**
   - Time-to-first-token (TTFT)
   - End-to-end response time
   - Token usage per request

3. **Timing Middleware**
   - Per-endpoint P50/P95/P99 latency
   - Request count tracking

---

## Baseline Performance Metrics

### Current State (2025-12-24)

| Metric | Current | Target | Status |
|--------|---------|--------|--------|
| **Avg Tool Execution Time** | TBD | -25% from baseline | Pending |
| **Time to First Token** | TBD | <1s | Pending |
| **Cache Hit Rate** | 31.76% (Story 1.1) | >80% | In Progress |
| **Tool Success Rate** | TBD | >98% | Pending |

### Measurement Commands

```bash
# Get tool performance metrics (last 7 days)
curl -s -H "Authorization: Bearer $TOKEN" \
  "https://klinecubic.cn/api/admin/llm/tool-performance?days=7"

# Get slowest tools for optimization
curl -s -H "Authorization: Bearer $TOKEN" \
  "https://klinecubic.cn/api/admin/llm/slowest-tools?days=7&limit=10"

# Get API endpoint timing
curl -s -H "Authorization: Bearer $TOKEN" \
  "https://klinecubic.cn/api/admin/timing-metrics"
```

---

## Tools Available

### Alpha Vantage MCP Tools (118 tools)

Loaded via MCP protocol on startup:

| Category | Examples | Expected Latency |
|----------|----------|------------------|
| **Quotes** | `get_quote`, `global_quote` | <500ms (cached) |
| **Fundamentals** | `income_statement`, `balance_sheet` | 1-2s |
| **Technical** | `rsi`, `macd`, `sma` | 1-3s |
| **News** | `news_sentiment` | 2-5s |

### Custom Analysis Tools

| Tool | Purpose | Expected Latency |
|------|---------|------------------|
| `fibonacci_analysis` | Fibonacci retracement | 1-2s |
| `stochastic_analysis` | Stochastic oscillator | 1-2s |
| `macro_analysis` | Market sentiment | 2-3s |

---

## Token Optimization

### Compression Strategy

Tool results are compressed by ~99.5% before returning to the LLM:

```python
# Original response: ~10KB of raw JSON
# Compressed: 2-3 lines of essential data
compressed_result = compress_tool_result(raw_result)
```

### Token Tracking

- **Collection**: `tool_executions` in MongoDB
- **Fields**: `input_tokens`, `output_tokens`, `total_tokens`
- **Repository**: `ToolExecutionRepository`

---

## Bottlenecks Identified

### Priority 1: Time to First Token (TTFT)

- User perceives delay before response starts
- Depends on: Model cold start, tool planning
- **Optimization**: Streaming implementation, agent initialization

### Priority 2: Multi-Tool Chains

- Long chains = cumulative latency
- Example: `get_quote -> fibonacci -> macro` = 3-5s
- **Optimization**: Parallel tool execution where possible

### Priority 3: Tool Execution Time

- External API calls (Alpha Vantage) are the bottleneck
- **Optimization**: Redis caching (Story 1.3), request deduplication

### Priority 4: Retry Overhead

- Retries on API failures add latency
- **Optimization**: Exponential backoff with jitter, circuit breaker pattern

---

## Performance Repository Methods

### `get_tool_performance_metrics()`

Returns aggregated metrics for all tools:

```python
{
    "period": {"start": "...", "end": "..."},
    "summary": {
        "total_executions": 1000,
        "avg_duration_ms": 1250,
        "success_rate": 0.98,
        "cache_hit_rate": 0.75
    },
    "by_tool": [
        {
            "tool_name": "GLOBAL_QUOTE",
            "tool_source": "mcp_alphavantage",
            "total_calls": 500,
            "avg_duration_ms": 1200,
            "p50_duration_ms": 1100,
            "p95_duration_ms": 2500,
            "p99_duration_ms": 3500,
            "success_rate": 0.99,
            "cache_hit_rate": 0.80
        }
    ]
}
```

### `get_slowest_tools()`

Identifies optimization targets:

```python
[
    {
        "tool_name": "NEWS_SENTIMENT",
        "tool_source": "mcp_alphavantage",
        "total_calls": 100,
        "avg_duration_ms": 3500,
        "max_duration_ms": 8000
    }
]
```

---

## Recommendations

### Immediate (Story 1.4)

1. **Tool Execution Optimization**
   - Implement parallel tool execution for independent tools
   - Add tool execution timeout with graceful fallback

2. **Token Usage Optimization**
   - Persist token_usage to database (currently log-only)
   - Add token budget limits per request type

3. **Streaming Latency Optimization**
   - Reduce TTFT by optimizing agent initialization
   - Implement eager streaming (start streaming before full response)

4. **Retry Logic Optimization**
   - Implement exponential backoff with jitter
   - Add circuit breaker pattern for failing tools

### Future

5. **Context Window Management**
   - Prune stale conversation history
   - Implement sliding window for long conversations

6. **Prompt Optimization**
   - Reduce system prompt size
   - Improve tool selection accuracy

---

## Data Collection

### Langfuse Access

```
URL: https://monitor.klinecubic.cn
Integration: Automatic via @observe decorators
```

### Local Development

```bash
# View Langfuse UI
open http://localhost:3001

# Check Langfuse logs
docker compose logs langfuse-server --tail=50

# Get tool performance (local)
curl -s -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/api/admin/llm/tool-performance?days=7"
```

---

## Change Log

| Date | Change | Author |
|------|--------|--------|
| 2025-12-23 | Initial baseline document created | Story 1.1 |
| 2025-12-24 | Added performance metrics endpoints and repository methods | Story 1.4 Task 1 |

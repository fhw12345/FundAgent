# Financial Agent Development Guide

## Tech Stack
* **Backend**: Python 3.12 + FastAPI + MongoDB + Redis
* **Frontend**: React 18 + TypeScript 5 + Vite + TailwindCSS
* **Development**: Docker Compose with hot reload
* **Tooling**: Black, Ruff, MyPy (Python) | ESLint, Prettier (TypeScript)

## Methodology: Walking Skeleton
1. **Milestone 1**: End-to-end connectivity (Frontend → API → DB → Cache)
2. **Milestone 2**: Authentication + core business logic
3. **Milestone 3+**: Layer features incrementally

## Code Standards
* Python: Modern syntax (`|` unions, `match/case`, f-strings, `@dataclass`)
* TypeScript: ES modules, optional chaining, `satisfies` operator
* Quality gates: `make fmt && make test && make lint`

## API Validation Patterns
* **Symbol Validation**: Test `ticker.history(period="5d")` before suggesting symbols
* **Root Cause Fix**: Fix validation at source (search) not downstream (UI)
* **yfinance Pattern**: Some symbols exist but lack price data - always verify availability

## React Closure Debugging

### Problem: React Query Closure Trap
React Query mutations capture state at creation time, not execution time.

**Symptoms**:
- UI shows correct state but API gets wrong parameters
- Identical cache keys for different UI states
- Debug logs show stale closure values

### Solutions

**Message-Based State Transfer**:
```typescript
// ✅ Pass state via message, not closures
const handleAction = () => {
    const message = `Analysis for ${symbol} (${selectedInterval} timeframe)`;
    mutation.mutate(message);
};
```

**Direct Parameter Passing**:
```typescript
// ✅ Bypass closures entirely
const mutation = useMutation({
    mutationFn: async ({ symbol, timeframe, dates }) => {
        return api.analyze({ symbol, timeframe, ...dates });
    }
});
```

### Debugging Strategy
1. Log user messages AND parsed parameters
2. Check Redis cache keys: `docker-compose exec redis redis-cli keys "fibonacci:*"`
3. Add structured logging: `logging.basicConfig(level=logging.INFO)`
4. Use "zero-closure" patterns for complex state dependencies
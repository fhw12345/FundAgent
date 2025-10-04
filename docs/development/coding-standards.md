# Coding Standards and Best Practices

## General Principles

### Code Quality
- **File Size Limit**: Maximum 500 lines per file - split into modules when exceeded
- **Documentation**: Descriptive docstrings at top of every file explaining purpose and context
- **Comments**: Rich comments required for all key business logic - explain "why", not "what"
- **No Duplication**: DRY principle - centralize shared logic in utils modules, avoid duplicate code

### Quality Gates
Before every commit, run:
```bash
make fmt && make test && make lint
```

All checks must pass before code can be committed.

## Python Standards

### Modern Syntax
- Use `|` for type unions: `str | None` instead of `Optional[str]`
- Use `match/case` for pattern matching
- Use f-strings for string formatting
- Use `@dataclass` for data classes

### Type Hints
Type hints are required for all functions and methods:

```python
def analyze_fibonacci(symbol: str, timeframe: str = "6mo") -> dict[str, Any]:
    """Analyze Fibonacci retracement levels."""
    pass
```

### Code Organization
```python
"""
Module description goes here.
Explains the purpose and context of this file.
"""

# Standard library imports
import sys
from typing import Any

# Third-party imports
import pandas as pd
from fastapi import FastAPI

# Local imports
from src.core.config import settings
from src.database.mongodb import get_database

# Constants
DEFAULT_TIMEFRAME = "6mo"

# Functions and classes
def process_data(data: pd.DataFrame) -> dict[str, Any]:
    """
    Process financial data.

    Args:
        data: Raw market data DataFrame

    Returns:
        Processed data dictionary

    Raises:
        ValueError: If data is empty or invalid
    """
    # Implementation with rich comments explaining WHY
    pass
```

### Error Handling
```python
# Use specific exceptions
try:
    result = analyze_data(symbol)
except ValueError as e:
    logger.error(f"Invalid symbol: {symbol}", exc_info=e)
    raise
except ConnectionError as e:
    logger.error(f"Database connection failed", exc_info=e)
    # Retry logic here
```

### Logging
```python
import structlog

logger = structlog.get_logger()

# Use structured logging with context
logger.info("Starting analysis", symbol=symbol, timeframe=timeframe)
logger.error("Analysis failed", symbol=symbol, error=str(e))
```

### Async/Await
Prefer async/await for I/O operations:

```python
async def get_market_data(symbol: str) -> dict[str, Any]:
    """Fetch market data asynchronously."""
    async with httpx.AsyncClient() as client:
        response = await client.get(f"/api/data/{symbol}")
        return response.json()
```

## TypeScript Standards

### Modern Syntax
- Use ES modules
- Use optional chaining: `data?.fibonacci?.levels`
- Use nullish coalescing: `value ?? defaultValue`
- Use `satisfies` operator for type checking

### Type Definitions
Types are required for all functions and components:

```typescript
interface FibonacciLevel {
  level: number;
  price: number;
  label: string;
}

interface AnalysisResult {
  symbol: string;
  levels: FibonacciLevel[];
  chartUrl?: string;
}

async function analyzeFibonacci(
  symbol: string,
  timeframe: string = '6mo'
): Promise<AnalysisResult> {
  // Implementation
}
```

### React Components
```typescript
/**
 * FibonacciChart component displays Fibonacci retracement levels.
 *
 * Handles user interactions and updates via React Query.
 */
interface FibonacciChartProps {
  symbol: string;
  timeframe: string;
  onAnalysisComplete?: (result: AnalysisResult) => void;
}

export function FibonacciChart({
  symbol,
  timeframe,
  onAnalysisComplete
}: FibonacciChartProps) {
  // Component implementation
  return (
    <div className="fibonacci-chart">
      {/* JSX */}
    </div>
  );
}
```

### Error Handling
```typescript
try {
  const result = await api.analyzeFibonacci(symbol, timeframe);
  setData(result);
} catch (error) {
  if (error instanceof ApiError) {
    toast.error(`API Error: ${error.message}`);
  } else {
    toast.error('An unexpected error occurred');
  }
  console.error('Analysis failed:', error);
}
```

## API Validation Patterns

### Symbol Validation
Always validate symbols before suggesting them to users:

```python
def validate_symbol(symbol: str) -> bool:
    """
    Validate that a symbol has available price data.

    Some symbols exist but lack price data in yfinance.
    Test with ticker.history(period="5d") before returning.
    """
    try:
        ticker = yf.Ticker(symbol)
        history = ticker.history(period="5d")
        return len(history) > 0
    except Exception:
        return False
```

### Root Cause Fix Principle
Fix validation at the source (search endpoint), not downstream (UI):

```python
# ✅ Good: Validate in search endpoint
@app.get("/api/market/search")
async def search_symbols(q: str) -> list[str]:
    candidates = search_provider.search(q)
    # Filter out invalid symbols immediately
    valid_symbols = [s for s in candidates if validate_symbol(s)]
    return valid_symbols

# ❌ Bad: Let invalid symbols through, handle in UI
@app.get("/api/market/search")
async def search_symbols(q: str) -> list[str]:
    return search_provider.search(q)  # May include invalid symbols
```

## React Closure Debugging

### Problem: React Query Closure Trap
React Query mutations capture state at creation time, not execution time.

**Symptoms:**
- UI shows correct state but API gets wrong parameters
- Identical cache keys for different UI states
- Debug logs show stale closure values

### Solutions

**Message-Based State Transfer:**
```typescript
// ✅ Pass state via message, not closures
const handleAction = () => {
    const message = `Analysis for ${symbol} (${selectedInterval} timeframe)`;
    mutation.mutate(message);
};
```

**Direct Parameter Passing:**
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

## Data Contract Synchronization

### Critical Rule
When modifying **any** frontend or backend logic, always verify data contract alignment across all layers.

### 4-Layer Contract Checklist
1. **Backend Pydantic Models** - `Literal["value1", "NEW_VALUE"]`
2. **Frontend TypeScript** - `'value1' | 'NEW_VALUE'` (must mirror backend)
3. **User Input Parsing** - Handle new patterns in messages/UI
4. **Business Logic** - Process new values appropriately

### Common Failures

**422 Errors (Backend validation failure):**
```python
# Backend Pydantic model
class AnalysisRequest(BaseModel):
    timeframe: Literal["1d", "5d", "1mo", "3mo", "6mo", "1y"]
```

```typescript
// Frontend TypeScript type must match exactly
type Timeframe = '1d' | '5d' | '1mo' | '3mo' | '6mo' | '1y';
```

**Silent Fallbacks:**
```typescript
// ❌ Bad: Frontend parsing fails, uses default
const timeframe = parseTimeframe(message) || '6mo';

// ✅ Good: Frontend parsing must succeed or show error
const timeframe = parseTimeframe(message);
if (!timeframe) {
  throw new Error('Invalid timeframe in message');
}
```

### Debugging Data Contracts
1. Check Pydantic validation errors in backend logs
2. Verify frontend types match backend models
3. Test parsing logic with all valid values
4. Ensure business logic handles all cases

## Docker Hot Reload Rules

### When Restart Required ❌
- **New dependencies**: `pip install` / `npm install`
- **Global/module-level objects**: DB connections, clients, constants, decorators
- **Docker config changes**: docker-compose.yml, Dockerfile
- **When hot reload visibly fails**: Old behavior persists despite code changes

### When Hot Reload Works ✅
- **Function/method logic**: Business rules, calculations, API logic
- **New routes/endpoints**: Adding FastAPI routes, React components
- **Local variables/operations**: Any code inside functions
- **UI changes**: CSS, HTML, component updates

### Development Workflow
1. **Make change**
2. **Test immediately**
3. **If old behavior persists** → `docker-compose restart [service]`

### Quick Test
```python
print(f"🔄 Code updated: {datetime.now()}")
```
No print = restart needed.

### Golden Rule
**Hot reload works for ~90% of changes. When in doubt, restart - 10 seconds vs 10 minutes debugging.**

## Testing Standards

### Backend Tests
```python
"""
tests/test_fibonacci_analysis.py

Tests for Fibonacci analysis functionality.
"""
import pytest
from src.analysis.fibonacci import FibonacciAnalyzer

class TestFibonacciAnalyzer:
    """Test suite for Fibonacci analyzer."""

    def test_analyze_valid_symbol(self):
        """Test analysis with valid symbol returns expected structure."""
        analyzer = FibonacciAnalyzer()
        result = analyzer.analyze("AAPL", "6mo")

        assert "levels" in result
        assert "confidence" in result
        assert result["confidence"] > 0.5

    def test_analyze_invalid_symbol(self):
        """Test analysis with invalid symbol raises ValueError."""
        analyzer = FibonacciAnalyzer()

        with pytest.raises(ValueError):
            analyzer.analyze("INVALID", "6mo")
```

### Frontend Tests
```typescript
/**
 * FibonacciChart.test.tsx
 *
 * Tests for FibonacciChart component.
 */
import { render, screen, waitFor } from '@testing-library/react';
import { FibonacciChart } from './FibonacciChart';

describe('FibonacciChart', () => {
  it('renders loading state initially', () => {
    render(<FibonacciChart symbol="AAPL" timeframe="6mo" />);
    expect(screen.getByText(/loading/i)).toBeInTheDocument();
  });

  it('displays chart after successful analysis', async () => {
    render(<FibonacciChart symbol="AAPL" timeframe="6mo" />);

    await waitFor(() => {
      expect(screen.getByRole('img')).toBeInTheDocument();
    });
  });
});
```

## Commit Standards

### Commit Message Format
```
type(scope): brief description

Longer description if needed.

- Detail point 1
- Detail point 2
```

**Types:**
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `refactor`: Code refactoring
- `test`: Adding tests
- `chore`: Maintenance tasks

**Examples:**
```
feat(analysis): Add stochastic oscillator indicator

Implements stochastic oscillator calculation and visualization.

- Calculate %K and %D lines
- Add oversold/overbought zones
- Include in chart generation
```

```
fix(api): Handle empty search results gracefully

Previously crashed when yfinance returned no results.
Now returns empty array with appropriate message.
```

## Security Standards

### Secrets Management
- ❌ Never commit secrets to git
- ✅ Use environment variables
- ✅ Use `.env.example` for documentation
- ✅ Store production secrets in Azure Key Vault

### Input Validation
```python
from pydantic import BaseModel, validator

class AnalysisRequest(BaseModel):
    symbol: str
    timeframe: str

    @validator('symbol')
    def validate_symbol(cls, v):
        """Ensure symbol is alphanumeric and uppercase."""
        if not v.isalnum() or not v.isupper():
            raise ValueError('Invalid symbol format')
        return v
```

### Authentication
```python
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer

security = HTTPBearer()

async def verify_token(token: str = Depends(security)) -> str:
    """Verify JWT token and return user ID."""
    try:
        payload = jwt.decode(token.credentials, SECRET_KEY)
        return payload['user_id']
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")
```

## Performance Standards

### Database Queries
```python
# ✅ Good: Use indexes and limit results
async def get_recent_analyses(user_id: str, limit: int = 10):
    return await db.analyses.find(
        {"user_id": user_id}
    ).sort("created_at", -1).limit(limit).to_list()

# ❌ Bad: Load everything into memory
async def get_recent_analyses(user_id: str):
    all_analyses = await db.analyses.find({"user_id": user_id}).to_list()
    return sorted(all_analyses, key=lambda x: x['created_at'], reverse=True)[:10]
```

### Caching
```python
# Use Redis for expensive operations
async def get_market_data(symbol: str) -> dict:
    """Get market data with Redis caching."""
    cache_key = f"market_data:{symbol}"

    # Try cache first
    cached = await redis.get(cache_key)
    if cached:
        return json.loads(cached)

    # Fetch and cache
    data = await fetch_from_yfinance(symbol)
    await redis.setex(cache_key, 3600, json.dumps(data))  # 1 hour TTL
    return data
```

## Documentation Standards

### File Documentation
```python
"""
fibonacci_analyzer.py

Fibonacci retracement analysis for financial instruments.

This module calculates Fibonacci retracement levels based on swing highs
and lows in price data. It identifies significant support/resistance levels
using the Fibonacci sequence ratios (0.236, 0.382, 0.500, 0.618, 0.786).

Key Features:
- Automatic swing point detection
- Multiple timeframe support
- Confidence scoring based on price action
- Integration with chart generation

Dependencies:
- pandas: For price data manipulation
- numpy: For numerical calculations
- yfinance: For market data retrieval
"""
```

### Function Documentation
```python
def calculate_fibonacci_levels(
    high: float,
    low: float,
    direction: Literal["up", "down"] = "up"
) -> dict[str, float]:
    """
    Calculate Fibonacci retracement levels between high and low prices.

    Fibonacci levels are calculated using standard ratios:
    23.6%, 38.2%, 50%, 61.8%, and 78.6%.

    Args:
        high: Swing high price
        low: Swing low price
        direction: Direction of the trend ("up" for uptrend, "down" for downtrend)

    Returns:
        Dictionary mapping level names to price values:
        {
            "0.0": float,    # Base level
            "0.236": float,  # 23.6% retracement
            "0.382": float,  # 38.2% retracement
            "0.500": float,  # 50% retracement
            "0.618": float,  # 61.8% retracement (golden ratio)
            "0.786": float,  # 78.6% retracement
            "1.0": float     # 100% retracement
        }

    Raises:
        ValueError: If high <= low or direction is invalid

    Example:
        >>> levels = calculate_fibonacci_levels(150.0, 100.0, "up")
        >>> levels["0.618"]  # Golden ratio level
        130.9
    """
    pass
```

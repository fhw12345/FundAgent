# Data Validation Issues

## Issue: Dividend Yield Validation Error (71% > 25%)

### Symptoms
```
❌ Error: Invalid symbol: 1 validation error for StockFundamentalsResponse
dividend_yield
  Input should be less than or equal to 25
  [type=less_than_equal, input_value=71.0, input_type=float]
```

### Root Cause
yfinance API inconsistency:
- For most stocks: Returns dividend yield as decimal (0.025 = 2.5%)
- For some stocks (e.g., MSFT): Returns as percentage already (0.71 = 0.71%)
- Code multiplied all values by 100 blindly: `0.71 × 100 = 71%` ❌

### Diagnosis
```bash
# Check what yfinance returns for a symbol
kubectl exec deployment/backend -n financial-agent-dev -- python << 'EOF'
import yfinance as yf
ticker = yf.Ticker("MSFT")
print(f"Dividend Yield: {ticker.info.get('dividendYield')}")
EOF
```

### Solution

**Smart detection for dividend yield format:**
```python
# backend/src/core/analysis/stock_analyzer.py
dividend_yield_raw = safe_float(info.get('dividendYield'))

if dividend_yield_raw is not None and dividend_yield_raw > 0:
    # If value > 1, assume it's already a percentage
    if dividend_yield_raw > 1:
        dividend_yield = dividend_yield_raw
    else:
        dividend_yield = dividend_yield_raw * 100

    # Cap at reasonable max to reject bad data
    if dividend_yield > 25:
        dividend_yield = None  # Reject unrealistic data
else:
    dividend_yield = None
```

**Deploy fix:**
```bash
az acr build --registry financialAgent \
  --image financial-agent/backend:dev-latest \
  --file backend/Dockerfile backend/

kubectl delete pod -l app=backend -n financial-agent-dev
```

**Fixed in**: `backend/src/core/analysis/stock_analyzer.py:84-97`

### Prevention
- Always validate external API data formats
- Add unit tests for edge cases
- Cap financial metrics at reasonable maxima
- Log warnings for suspicious values

---

## Issue: 422 Validation Error - Type Mismatch

### Symptoms
```
422 Unprocessable Entity
{
  "detail": [
    {
      "type": "literal_error",
      "msg": "Input should be '1d', '1h' or '5m'",
      "input": "1 day"
    }
  ]
}
```

### Root Cause
Frontend sends parsed user input that doesn't match backend's Literal type.

### Diagnosis
```bash
# Check Pydantic model
grep -A 5 "class.*Request" backend/src/api/models.py

# Check frontend type
grep -A 5 "type.*Interval" frontend/src/types/api.ts

# Check user input parsing
grep -A 10 "parseInterval" frontend/src/
```

### Solution

**Ensure data contract alignment:**

```python
# backend/src/api/models.py
class FibonacciRequest(BaseModel):
    interval: Literal["1d", "1h", "5m"]  # Exact values
```

```typescript
// frontend/src/types/api.ts
export type Interval = "1d" | "1h" | "5m"  // Must match exactly
```

```typescript
// frontend/src/utils/parseMessage.ts
function parseInterval(text: string): Interval {
  if (text.includes("hour")) return "1h"
  if (text.includes("minute") || text.includes("5m")) return "5m"
  return "1d"  // default
}
```

### Prevention
- Keep Pydantic Literal and TypeScript types in sync
- Add validation tests for user input parsing
- Document valid values in API specs
- Use code generation to sync types (future improvement)

---

## Issue: Optional Fields Failing Validation

### Symptoms
```
1 validation error for StockFundamentalsResponse
pe_ratio
  Input should be a valid number [type=float_type]
```

### Root Cause
External API returns `None` or invalid values, but Pydantic field is not Optional.

### Diagnosis
```bash
# Check field definition
grep "pe_ratio" backend/src/api/models.py

# Check if yfinance returns None
kubectl exec deployment/backend -n financial-agent-dev -- python << 'EOF'
import yfinance as yf
ticker = yf.Ticker("BRK.B")  # Berkshire doesn't have P/E
print(f"PE Ratio: {ticker.info.get('trailingPE')}")
EOF
```

### Solution

**Make financial metrics Optional:**
```python
# backend/src/api/models.py
from typing import Optional

class StockFundamentalsResponse(BaseModel):
    pe_ratio: Optional[float] = Field(None, description="Price-to-earnings ratio")
    pb_ratio: Optional[float] = Field(None, description="Price-to-book ratio")
    dividend_yield: Optional[float] = Field(None, ge=0, le=25)
    beta: Optional[float] = Field(None, description="Stock beta")
```

**Handle None in business logic:**
```python
# Generate summary handles None values
if pe_ratio is not None and pe_ratio > 0:
    key_metrics.append(f"P/E Ratio: {pe_ratio:.1f}")
else:
    key_metrics.append("P/E Ratio: N/A")
```

### Prevention
- Make all external data fields Optional by default
- Validate data before creating response models
- Handle None gracefully in business logic
- Add default values or "N/A" for missing data

---

## Issue: Date Format Mismatch

### Symptoms
```
422 Unprocessable Entity
"Input should be a valid datetime or date"
```

### Root Cause
Frontend sends date as string, backend expects datetime object or ISO format.

### Diagnosis
```bash
# Check request payload in browser network tab
# Look for date format: "2024-01-01" vs "2024-01-01T00:00:00Z"

# Check Pydantic model
grep -A 3 "date" backend/src/api/models.py
```

### Solution

**Use ISO 8601 format consistently:**
```python
# backend/src/api/models.py
from datetime import datetime

class AnalysisRequest(BaseModel):
    start_date: datetime  # Accepts ISO 8601: "2024-01-01T00:00:00Z"
    end_date: datetime
```

```typescript
// frontend/src/services/api.ts
const request = {
  start_date: startDate.toISOString(),  // "2024-01-01T00:00:00.000Z"
  end_date: endDate.toISOString(),
}
```

**Alternative: Use date strings with validator:**
```python
from pydantic import field_validator

class AnalysisRequest(BaseModel):
    start_date: str

    @field_validator('start_date')
    @classmethod
    def validate_date(cls, v: str) -> str:
        try:
            datetime.fromisoformat(v)
            return v
        except ValueError:
            raise ValueError('Invalid date format. Use YYYY-MM-DD')
```

### Prevention
- Always use ISO 8601 format for dates
- Use datetime objects in Pydantic models
- Add field validators for custom formats
- Document date format in API specs

---

## Issue: Large Number Precision Loss

### Symptoms
Market cap shows as `1.5e+12` instead of `$1.5T`

### Root Cause
JavaScript number precision limits, or backend returns scientific notation.

### Diagnosis
```python
# Check backend response
import json
data = {"market_cap": 1500000000000.0}
print(json.dumps(data))  # Shows: 1.5e+12
```

### Solution

**Format large numbers server-side:**
```python
def format_market_cap(value: float) -> str:
    """Format market cap with appropriate suffix."""
    if value >= 1e12:
        return f"${value/1e12:.2f}T"
    elif value >= 1e9:
        return f"${value/1e9:.2f}B"
    elif value >= 1e6:
        return f"${value/1e6:.2f}M"
    return f"${value:,.0f}"

class StockFundamentalsResponse(BaseModel):
    market_cap: float
    market_cap_formatted: str  # "1.50T"
```

**Or handle in frontend:**
```typescript
function formatMarketCap(value: number): string {
  if (value >= 1e12) return `$${(value/1e12).toFixed(2)}T`
  if (value >= 1e9) return `$${(value/1e9).toFixed(2)}B`
  if (value >= 1e6) return `$${(value/1e6).toFixed(2)}M`
  return `$${value.toLocaleString()}`
}
```

### Prevention
- Format large numbers on server for consistency
- Use strings for display values
- Test with real-world large numbers
- Add formatted fields in response models

---

## Issue: Enum Value Case Sensitivity

### Symptoms
```
422 Unprocessable Entity
"Input should be 'buy', 'sell' or 'hold'"
```
User sent: `"BUY"`, backend expects: `"buy"`

### Root Cause
Case mismatch between user input and Pydantic Literal values.

### Solution

**Normalize case before validation:**
```python
from pydantic import field_validator

class TradeSignal(BaseModel):
    action: Literal["buy", "sell", "hold"]

    @field_validator('action', mode='before')
    @classmethod
    def lowercase_action(cls, v: str) -> str:
        if isinstance(v, str):
            return v.lower()
        return v
```

**Or in frontend:**
```typescript
const action = userInput.toLowerCase() as "buy" | "sell" | "hold"
```

### Prevention
- Normalize case consistently (prefer lowercase)
- Use validators to accept multiple formats
- Document case requirements in API specs
- Add frontend validation before API calls

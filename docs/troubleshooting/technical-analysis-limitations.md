# Technical Analysis Limitations

Common issues related to technical analysis features (Fibonacci retracement, Stochastic oscillator) and their limitations.

---

## Intraday Technical Analysis Not Available

### Issue: Fibonacci/Stochastic Analysis Not Available for 1m or 60m Intervals

**Symptoms**:
- Error message: "Fibonacci analysis is not available for [interval] interval"
- Error message: "Stochastic analysis is not available for [interval] interval"
- Technical analysis buttons hidden when 1m interval selected
- 422 Unprocessable Entity when trying to force intraday analysis

**Diagnosis**:
```bash
# Check backend logs for validation errors
kubectl logs -f deployment/backend -n klinematrix-prod | grep -i "fibonacci\|stochastic"

# Test API directly
curl -X POST https://klinecubic.cn/api/analysis/fibonacci \
  -H "Content-Type: application/json" \
  -d '{"symbol": "AAPL", "timeframe": "1m", "start_date": "2025-01-01", "end_date": "2025-01-02"}'
```

**Root Cause**:

Intraday intervals (1m, 60m) cannot provide reliable technical analysis due to data limitations:

1. **Insufficient Data Points**: Alpha Vantage compact mode returns only ~100 bars for intraday data
2. **Minimum Requirements**: Fibonacci analysis requires `swing_lookback × 3` bars minimum (typically 20-60 bars)
3. **Statistical Reliability**: Professional analysis needs months/years of data for pattern recognition
4. **Noise vs Signal**: Short timeframes have high noise-to-signal ratio, making swing detection unreliable

**Technical Details**:
```python
# Backend validation in backend/src/api/analysis.py
if request.timeframe in ["1m", "60m", "60min", "1h"]:
    raise ValueError(
        f"Fibonacci analysis is not available for {request.timeframe} interval. "
        f"Please use daily (1d), weekly (1w), or monthly (1mo) intervals for reliable analysis."
    )
```

**Solution**:

Use appropriate intervals for technical analysis:

| Interval | Chart Display | Technical Analysis | Recommended Use |
|----------|--------------|-------------------|-----------------|
| 1m | ✅ Available | ❌ Not Available | Day trading price action |
| 1d | ✅ Available | ✅ Available | Short-term swing trading |
| 1w | ✅ Available | ✅ Available | Medium-term trends |
| 1mo | ✅ Available | ✅ Available | Long-term macro analysis |

**Date Ranges for Analysis** (professional standards):
- **Daily (1d)**: Last 6 months (~126 trading days)
- **Weekly (1w)**: Last 2 years (~104 weeks)
- **Monthly (1mo)**: Last 5 years (~60 months)

**Prevention**:

The UI automatically prevents this issue:
- Technical analysis buttons (Fibonacci, Stochastic) are **hidden** when 1m interval is selected
- Backend validation rejects intraday intervals with clear error messages
- Frontend only allows `1d`, `1w`, `1mo` in analysis date calculations

**Code References**:
- Frontend button hiding: `frontend/src/components/chat/ChartPanel.tsx:128`
- Backend validation: `backend/src/api/analysis.py` (Fibonacci/Stochastic endpoints)
- Date range calculator: `frontend/src/utils/dateRangeCalculator.ts`
- Pydantic models: `backend/src/api/models.py`

---

## Insufficient Data for Analysis

### Issue: "Insufficient data for Fibonacci analysis. Got X bars, need at least Y"

**Symptoms**:
- Error message indicating too few data points
- Analysis fails even when date range is specified
- Happens more frequently with newer stocks or limited trading history

**Diagnosis**:
```bash
# Check how many bars are being returned
curl -s "https://klinecubic.cn/api/market/price/SYMBOL?interval=1d&period=6mo" | jq '.data | length'
```

**Root Cause**:
- Stock has limited trading history (e.g., recent IPO)
- Date range is too narrow for selected interval
- Data source returns fewer points than expected

**Solution**:
1. Expand date range or use longer interval
2. For stocks with limited history, use available data
3. Check if symbol is valid and has trading data

**Prevention**:
- Use longer intervals (weekly/monthly) for better statistical reliability
- Backend validates minimum bar requirements before processing

---

## Related Documentation

- [Data Validation Issues](data-validation-issues.md) - Pydantic validation errors
- [Known Bugs](known-bugs.md) - Current open issues
- [docs/README.md](../README.md) - Feature overview with analysis note

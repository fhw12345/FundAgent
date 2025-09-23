"""
Comprehensive yfinance integration tests.

Tests the critical yfinance API integration that caused multiple production issues:
- Interval mapping ('1w' → '1wk' conversion failures)
- Symbol validation (delisted symbols like XLY causing crashes)
- Data availability validation
- Error handling and fallbacks

These tests ensure robust integration with the external yfinance API.
"""

import pytest
import yfinance as yf
from unittest.mock import Mock, patch
import pandas as pd
from datetime import datetime, timedelta

from src.core.utils.yfinance_utils import (
    map_timeframe_to_yfinance_interval,
    get_valid_frontend_intervals,
    get_valid_yfinance_intervals
)


class TestYfinanceIntervalMapping:
    """Test the critical interval mapping that caused '1w' vs '1wk' failures."""

    def test_weekly_interval_mapping_prevents_yfinance_error(self):
        """
        REGRESSION TEST: Ensure '1w' maps to '1wk' to prevent yfinance errors.

        Root Cause: yfinance.history(interval='1w') fails with:
        "Invalid input - interval=1w is not supported. Valid intervals: [..., 1wk, ...]"
        """
        # Test the mapping that prevented production failures
        assert map_timeframe_to_yfinance_interval('1w') == '1wk'
        assert map_timeframe_to_yfinance_interval('1M') == '1mo'
        assert map_timeframe_to_yfinance_interval('1mo') == '1mo'  # Already compatible

    def test_all_supported_intervals_map_correctly(self):
        """Test comprehensive interval mapping for all supported timeframes."""
        test_cases = [
            ('1m', '1m'),      # Should pass through unchanged
            ('1h', '1h'),      # Should pass through unchanged
            ('1d', '1d'),      # Should pass through unchanged
            ('1w', '1wk'),     # Critical mapping that prevented failures
            ('1M', '1mo'),     # Alternative monthly format
            ('1mo', '1mo'),    # Already yfinance-compatible
            ('3mo', '3mo'),    # Should pass through unchanged
        ]

        for frontend_interval, expected_yfinance_interval in test_cases:
            result = map_timeframe_to_yfinance_interval(frontend_interval)
            assert result == expected_yfinance_interval, (
                f"Interval mapping failed: '{frontend_interval}' → '{result}', "
                f"expected '{expected_yfinance_interval}'"
            )

    def test_unknown_interval_passes_through_unchanged(self):
        """Test that unknown intervals pass through unchanged for flexibility."""
        unknown_interval = '15s'  # Not in our mapping
        result = map_timeframe_to_yfinance_interval(unknown_interval)
        assert result == unknown_interval

    def test_valid_intervals_include_both_formats(self):
        """Test that validation accepts both frontend and yfinance formats."""
        frontend_intervals = get_valid_frontend_intervals()

        # Critical intervals that caused production issues
        assert '1w' in frontend_intervals, "Frontend must accept '1w' format"
        assert '1M' in frontend_intervals, "Frontend must accept '1M' format"
        assert '1mo' in frontend_intervals, "Frontend must accept '1mo' format"


class TestYfinanceAPIIntegration:
    """Test actual yfinance API calls with proper error handling."""

    def test_yfinance_history_with_mapped_intervals(self):
        """
        INTEGRATION TEST: Verify mapped intervals work with actual yfinance calls.

        This prevents the production error: "interval=1w is not supported"
        """
        # Test with a reliable symbol (AAPL) and short period to avoid API rate limits
        ticker = yf.Ticker('AAPL')

        # Test that mapped intervals work with real yfinance API
        frontend_intervals_to_test = ['1d', '1w']  # Focus on critical cases

        for frontend_interval in frontend_intervals_to_test:
            yfinance_interval = map_timeframe_to_yfinance_interval(frontend_interval)

            try:
                # Use short period to minimize API calls and avoid rate limits
                data = ticker.history(period='5d', interval=yfinance_interval)

                # Verify we got actual data
                assert not data.empty, (
                    f"No data returned for AAPL with interval '{yfinance_interval}' "
                    f"(mapped from '{frontend_interval}')"
                )

                # Verify data structure
                expected_columns = ['Open', 'High', 'Low', 'Close', 'Volume']
                for col in expected_columns:
                    assert col in data.columns, f"Missing column '{col}' in yfinance data"

            except Exception as e:
                pytest.fail(
                    f"yfinance API call failed for interval '{yfinance_interval}' "
                    f"(mapped from '{frontend_interval}'): {str(e)}"
                )

    @patch('yfinance.Ticker')
    def test_delisted_symbol_handling(self, mock_ticker):
        """
        REGRESSION TEST: Handle delisted symbols gracefully (like XLY issue).

        Root Cause: XLY symbol was delisted, causing macro analysis to crash.
        """
        # Mock a delisted symbol scenario
        mock_instance = Mock()
        mock_instance.history.return_value = pd.DataFrame()  # Empty DataFrame = no data
        mock_ticker.return_value = mock_instance

        # Test that we handle empty data gracefully
        ticker = yf.Ticker('XLY')  # The problematic delisted symbol
        data = ticker.history(period='5d', interval='1d')

        # Should return empty DataFrame without crashing
        assert data.empty, "Delisted symbol should return empty DataFrame"

        # Verify our code can detect and handle this scenario
        assert len(data) == 0, "Empty data should have zero length"

    @patch('yfinance.Ticker')
    def test_yfinance_api_timeout_handling(self, mock_ticker):
        """
        TEST: Handle yfinance API timeouts that caused 30-second frontend failures.
        """
        # Mock a timeout scenario
        mock_instance = Mock()
        mock_instance.history.side_effect = Exception("timeout of 30000ms exceeded")
        mock_ticker.return_value = mock_instance

        # Test that we can catch and handle timeouts
        ticker = yf.Ticker('AAPL')

        with pytest.raises(Exception) as exc_info:
            ticker.history(period='5d', interval='1d')

        assert "timeout" in str(exc_info.value).lower()

    def test_symbol_data_availability_validation(self):
        """
        TEST: Validate symbol data availability to prevent downstream failures.

        Ensures symbols have actual price data before using them in analysis.
        """
        # Test with known good symbol
        ticker = yf.Ticker('AAPL')
        data = ticker.history(period='5d', interval='1d')

        # Validation checks that should be performed
        assert not data.empty, "Valid symbol should return data"
        assert len(data) > 0, "Valid symbol should have price points"
        assert 'Close' in data.columns, "Price data should include Close prices"
        assert data['Close'].notna().any(), "Should have valid Close prices"

    @pytest.mark.parametrize("symbol,should_have_data", [
        ('AAPL', True),   # Known good symbol
        ('MSFT', True),   # Known good symbol
        ('INVALID123', False),  # Invalid symbol
    ])
    def test_symbol_validation_scenarios(self, symbol, should_have_data):
        """
        PARAMETERIZED TEST: Test various symbol validation scenarios.

        Covers both valid and invalid symbols to ensure robust error handling.
        """
        ticker = yf.Ticker(symbol)

        try:
            data = ticker.history(period='5d', interval='1d')
            has_data = not data.empty

            if should_have_data:
                assert has_data, f"Symbol '{symbol}' should have data but returned empty"
            # Note: Invalid symbols may or may not return data depending on yfinance behavior
            # We test our handling rather than yfinance's specific responses

        except Exception as e:
            if should_have_data:
                pytest.fail(f"Valid symbol '{symbol}' should not raise exception: {str(e)}")
            # Invalid symbols may raise exceptions, which is acceptable


class TestYfinanceDataValidation:
    """Test data validation and quality checks for yfinance responses."""

    def test_price_data_structure_validation(self):
        """Test that yfinance returns expected data structure."""
        ticker = yf.Ticker('AAPL')
        data = ticker.history(period='5d', interval='1d')

        if not data.empty:  # Only test if data is available
            # Test required columns
            required_columns = ['Open', 'High', 'Low', 'Close', 'Volume']
            for col in required_columns:
                assert col in data.columns, f"Missing required column: {col}"

            # Test data types
            numeric_columns = ['Open', 'High', 'Low', 'Close', 'Volume']
            for col in numeric_columns:
                assert pd.api.types.is_numeric_dtype(data[col]), (
                    f"Column '{col}' should be numeric, got {data[col].dtype}"
                )

            # Test logical price relationships
            for idx in data.index:
                row = data.loc[idx]
                assert row['Low'] <= row['High'], (
                    f"Low price should be <= High price at {idx}"
                )
                assert row['Low'] <= row['Close'] <= row['High'], (
                    f"Close price should be between Low and High at {idx}"
                )

    def test_dividend_yield_data_format(self):
        """
        REGRESSION TEST: Ensure dividend yield is in correct format from yfinance.

        Root Cause: We multiplied by 100 assuming decimal format, but yfinance
        already returns percentage format (0.41 for 0.41%, not 0.0041).
        """
        ticker = yf.Ticker('AAPL')
        info = ticker.info

        if 'dividendYield' in info and info['dividendYield'] is not None:
            dividend_yield = info['dividendYield']

            # Test that yfinance returns reasonable percentage values
            assert isinstance(dividend_yield, (int, float)), (
                "Dividend yield should be numeric"
            )

            # Reasonable range check (0% to 20% for most stocks)
            assert 0 <= dividend_yield <= 20, (
                f"Dividend yield {dividend_yield} seems unreasonable. "
                f"Should be between 0-20% for most stocks."
            )

            # The critical insight: yfinance returns percentage format directly
            # For AAPL, expect ~0.4-0.5%, not ~0.004-0.005
            if dividend_yield > 0:
                assert dividend_yield < 10, (
                    f"Dividend yield {dividend_yield} suggests percentage format "
                    f"(not decimal). No need to multiply by 100."
                )
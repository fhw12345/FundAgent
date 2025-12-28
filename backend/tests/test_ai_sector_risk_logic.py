"""Tests for AI Sector Risk logic with mocked data."""

import pytest
from unittest.mock import AsyncMock, MagicMock
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import pytz

from src.core.config import Settings
from src.services.insights.categories.ai_sector_risk import AISectorRiskCategory
from src.services.insights.models import MetricStatus


class TestAISectorRiskLogic:
    """Tests for AI Sector Risk specific calculation logic."""

    @pytest.fixture
    def mock_market_service(self):
        """Create a mock market service."""
        service = MagicMock()
        service.get_intraday_bars = AsyncMock()
        service.get_etf_profile = AsyncMock()
        service.get_daily_bars = AsyncMock()
        service.get_news_sentiment = AsyncMock()
        service.get_ipo_calendar = AsyncMock()
        service.get_treasury_yield = AsyncMock()
        return service

    @pytest.fixture
    def category(self, mock_market_service):
        """Create category instance with mock service."""
        settings = Settings()
        return AISectorRiskCategory(
            settings=settings, market_service=mock_market_service
        )

    def create_intraday_df(self, open_prices, close_prices, dates=None):
        """Helper to create intraday DataFrame."""
        if dates is None:
            # Default to today
            today = datetime.now(pytz.timezone("America/New_York")).date()
            dates = [today] * len(open_prices)

        # Create timestamps for 9:30 (First Hour) and 15:30 (Last Hour)
        timestamps = []
        for i, date in enumerate(dates):
            # Alternating 9:30 and 15:30 for simplicity in this helper
            # assuming list is [open, close, open, close...]
            hour = 9 if i % 2 == 0 else 15
            minute = 30
            ts = datetime.combine(date, datetime.min.time()).replace(
                hour=hour, minute=minute, tzinfo=pytz.timezone("America/New_York")
            )
            timestamps.append(ts)

        data = {
            "Open": open_prices,
            "Close": close_prices,
            "High": [max(o, c) + 1 for o, c in zip(open_prices, close_prices)],
            "Low": [min(o, c) - 1 for o, c in zip(open_prices, close_prices)],
            "Volume": [1000000] * len(open_prices),
        }

        df = pd.DataFrame(data, index=timestamps)
        return df

    @pytest.mark.asyncio
    async def test_smart_money_flow_bullish(self, category, mock_market_service):
        """
        Test Bullish Smart Money Flow (Institutional Accumulation).

        Scenario:
        - First Hour (Dumb Money): Price drops (Open 100 -> Close 99) = -1% return
        - Last Hour (Smart Money): Price rises (Open 99 -> Close 101) = ~+2% return
        - SMI = Last - First = 2% - (-1%) = +3% (Very Bullish)
        - Expected Risk Score: LOW (Inverted)
        """
        # Mock ETF profile to return symbols
        mock_market_service.get_etf_profile.return_value = {
            "holdings": [{"symbol": "NVDA", "weight": "0.1"}]
        }

        # Mock Intraday Data
        # First Hour: 100 -> 99 (-1%)
        # Last Hour: 100 -> 102 (+2%)
        df = self.create_intraday_df(
            open_prices=[100.0, 100.0], close_prices=[99.0, 102.0]
        )
        mock_market_service.get_intraday_bars.return_value = df

        # Calculate
        # Pass a mocked AI basket tuple: ([symbols], "source")
        metric = await category._calculate_smart_money_flow((["NVDA"], "Test ETF"))

        # Verify
        assert metric.id == "smart_money_flow"
        # Positive SMI (+3%) should be normalized to a LOW risk score
        # Our formula: Score = 50 + ((-SMI) / 1.0) * 25
        # SMI = 2 - (-1) = 3
        # Score approx: 50 + (-3 * 25) = -25 -> Clamped to 0
        assert metric.score < 25
        assert metric.status == MetricStatus.LOW
        assert "Smart money is buying" in metric.explanation.detail

    @pytest.mark.asyncio
    async def test_smart_money_flow_bearish(self, category, mock_market_service):
        """
        Test Bearish Smart Money Flow (Institutional Distribution).

        Scenario:
        - First Hour (Dumb Money): Price rises (Open 100 -> Close 101) = +1% return
        - Last Hour (Smart Money): Price drops (Open 101 -> Close 99) = -2% return
        - SMI = Last - First = -2% - 1% = -3% (Very Bearish)
        - Expected Risk Score: HIGH (Inverted)
        """
        # Mock ETF profile
        mock_market_service.get_etf_profile.return_value = {
            "holdings": [{"symbol": "NVDA", "weight": "0.1"}]
        }

        # Mock Intraday Data
        # First Hour: 100 -> 101 (+1%)
        # Last Hour: 100 -> 98 (-2%)
        df = self.create_intraday_df(
            open_prices=[100.0, 100.0], close_prices=[101.0, 98.0]
        )
        mock_market_service.get_intraday_bars.return_value = df

        # Calculate
        metric = await category._calculate_smart_money_flow((["NVDA"], "Test ETF"))

        # Verify
        assert metric.id == "smart_money_flow"
        # Negative SMI (-3%) should be normalized to a HIGH risk score
        # SMI = -2 - 1 = -3
        # Score approx: 50 + (3 * 25) = 125 -> Clamped to 100
        assert metric.score > 75
        assert metric.status == MetricStatus.HIGH
        assert "Smart money is selling" in metric.explanation.detail

    @pytest.mark.asyncio
    async def test_smart_money_flow_insufficient_data(
        self, category, mock_market_service
    ):
        """Test handling of insufficient data."""
        mock_market_service.get_etf_profile.return_value = {
            "holdings": [{"symbol": "NVDA", "weight": "0.1"}]
        }

        # Empty DataFrame
        mock_market_service.get_intraday_bars.return_value = pd.DataFrame()

        metric = await category._calculate_smart_money_flow((["NVDA"], "Test ETF"))

        # Should return neutral default score
        assert metric.score == 50.0
        assert metric.raw_data["avg_smi"] == 0.0

    @pytest.mark.asyncio
    async def test_ipo_heat_no_data(self, category, mock_market_service):
        """
        Test IPO Heat when no IPOs are returned (strict financial use).
        Should return 0 score, not an error or mocked average.
        """
        # Mock empty IPO list
        mock_market_service.get_ipo_calendar.return_value = []

        metric = await category._calculate_ipo_heat()

        assert metric.id == "ipo_heat"
        assert metric.score == 0.0
        assert metric.status == MetricStatus.LOW
        assert metric.raw_data["ipo_count_90d"] == 0
        assert "0 IPOs scheduled" in metric.explanation.summary

    @pytest.mark.asyncio
    async def test_ipo_heat_with_data(self, category, mock_market_service):
        """Test IPO Heat with valid upcoming IPOs."""
        # Mock IPOs in next 90 days
        future_date = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")
        mock_market_service.get_ipo_calendar.return_value = [
            {"symbol": "ABC", "ipoDate": future_date},
            {"symbol": "XYZ", "ipoDate": future_date},
        ]

        metric = await category._calculate_ipo_heat()

        assert metric.id == "ipo_heat"
        # 2 IPOs -> score > 0
        assert metric.score > 0
        assert metric.raw_data["ipo_count_90d"] == 2

    @pytest.mark.asyncio
    async def test_smart_money_flow_multi_symbol_aggregation(
        self, category, mock_market_service
    ):
        """
        Test Smart Money Flow aggregates SMI across multiple symbols.

        The implementation analyzes up to 3 symbols from the AI basket
        and averages their individual SMI values.

        Scenario:
        - NVDA: SMI = +2% (Bullish)
        - MSFT: SMI = +1% (Slightly Bullish)
        - AMD:  SMI = -1% (Slightly Bearish)
        - Average SMI = (+2 + 1 - 1) / 3 = +0.67% (Net Bullish)
        """
        # Create different intraday patterns for each symbol
        today = datetime.now(pytz.timezone("America/New_York")).date()

        def create_single_day_df(first_hour_return_pct, last_hour_return_pct):
            """Create intraday df with specific first/last hour returns."""
            # First hour: Open=100, Close based on return
            first_close = 100 * (1 + first_hour_return_pct / 100)
            # Last hour: Open=100, Close based on return
            last_close = 100 * (1 + last_hour_return_pct / 100)

            ts_first = datetime.combine(today, datetime.min.time()).replace(
                hour=9, minute=30, tzinfo=pytz.timezone("America/New_York")
            )
            ts_last = datetime.combine(today, datetime.min.time()).replace(
                hour=15, minute=30, tzinfo=pytz.timezone("America/New_York")
            )

            return pd.DataFrame(
                {
                    "Open": [100.0, 100.0],
                    "Close": [first_close, last_close],
                    "High": [max(100, first_close) + 1, max(100, last_close) + 1],
                    "Low": [min(100, first_close) - 1, min(100, last_close) - 1],
                    "Volume": [1000000, 1000000],
                },
                index=[ts_first, ts_last],
            )

        # NVDA: First Hour -1%, Last Hour +1% => SMI = +2%
        nvda_df = create_single_day_df(-1.0, 1.0)
        # MSFT: First Hour 0%, Last Hour +1% => SMI = +1%
        msft_df = create_single_day_df(0.0, 1.0)
        # AMD: First Hour +1%, Last Hour 0% => SMI = -1%
        amd_df = create_single_day_df(1.0, 0.0)

        # Mock to return different data for each symbol
        call_count = [0]

        async def mock_intraday(symbol, interval, outputsize):
            idx = call_count[0]
            call_count[0] += 1
            if idx == 0:
                return nvda_df
            elif idx == 1:
                return msft_df
            else:
                return amd_df

        mock_market_service.get_intraday_bars.side_effect = mock_intraday

        # Calculate with 3 symbols
        metric = await category._calculate_smart_money_flow(
            (["NVDA", "MSFT", "AMD"], "Test Basket")
        )

        # Verify aggregation
        assert metric.id == "smart_money_flow"
        # Average SMI = (2 + 1 - 1) / 3 = 0.67%
        avg_smi = metric.raw_data["avg_smi"]
        assert 0.5 < avg_smi < 0.8, f"Expected avg SMI ~0.67%, got {avg_smi}%"
        # Positive SMI should result in lower risk score
        assert metric.score < 50
        assert len(metric.raw_data["symbols_analyzed"]) == 3

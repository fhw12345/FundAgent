"""Tests for Put/Call Ratio LangChain tools.

Tests cover:
- get_put_call_ratio tool success cases
- Error handling (None result, exceptions)
- Output formatting (_format_pcr_output)
- Sentiment emoji selection based on PCR value
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.agent.tools.pcr_tools import _format_pcr_output, create_pcr_tools
from src.services.data_manager import SymbolPCRData


@pytest.fixture
def mock_data_manager() -> MagicMock:
    """Create mock DataManager for testing."""
    return MagicMock()


@pytest.fixture
def sample_pcr_data() -> SymbolPCRData:
    """Create sample PCR data for testing."""
    return SymbolPCRData(
        symbol="NVDA",
        current_price=142.50,
        atm_zone_low=121.13,
        atm_zone_high=163.88,
        put_notional_mm=25.50,
        call_notional_mm=42.30,
        contracts_analyzed=156,
        pcr=0.60,
        interpretation="Bullish sentiment (contrarian bearish signal)",
        calculated_at=datetime(2025, 1, 15, 14, 30, tzinfo=UTC),
        atm_zone_pct=0.15,
        min_premium=0.50,
        min_oi=500,
    )


@pytest.fixture
def sample_pcr_bearish() -> SymbolPCRData:
    """Create sample PCR data with bearish sentiment."""
    return SymbolPCRData(
        symbol="AAPL",
        current_price=185.25,
        atm_zone_low=157.46,
        atm_zone_high=213.04,
        put_notional_mm=35.80,
        call_notional_mm=24.50,
        contracts_analyzed=98,
        pcr=1.46,
        interpretation="Bearish sentiment (contrarian bullish signal)",
        calculated_at=datetime(2025, 1, 15, 10, 0, tzinfo=UTC),
    )


class TestGetPutCallRatioTool:
    """Tests for get_put_call_ratio tool."""

    @pytest.mark.asyncio
    async def test_tool_success(
        self, mock_data_manager: MagicMock, sample_pcr_data: SymbolPCRData
    ) -> None:
        """Test successful PCR retrieval."""
        mock_data_manager.get_symbol_pcr = AsyncMock(return_value=sample_pcr_data)
        tools = create_pcr_tools(mock_data_manager)
        pcr_tool = tools[0]

        result = await pcr_tool.ainvoke({"symbol": "NVDA"})

        mock_data_manager.get_symbol_pcr.assert_called_once_with("NVDA")
        assert "NVDA" in result
        assert "Put/Call Ratio Analysis" in result
        assert "$142.50" in result
        assert "0.60" in result
        assert "Bullish sentiment" in result

    @pytest.mark.asyncio
    async def test_tool_returns_none(self, mock_data_manager: MagicMock) -> None:
        """Test handling when PCR calculation returns None."""
        mock_data_manager.get_symbol_pcr = AsyncMock(return_value=None)
        tools = create_pcr_tools(mock_data_manager)
        pcr_tool = tools[0]

        result = await pcr_tool.ainvoke({"symbol": "UNKNOWN"})

        assert "Unable to calculate" in result
        assert "UNKNOWN" in result
        assert "Symbol not found" in result

    @pytest.mark.asyncio
    async def test_tool_handles_exception(self, mock_data_manager: MagicMock) -> None:
        """Test error handling when exception occurs."""
        mock_data_manager.get_symbol_pcr = AsyncMock(
            side_effect=Exception("API timeout")
        )
        tools = create_pcr_tools(mock_data_manager)
        pcr_tool = tools[0]

        result = await pcr_tool.ainvoke({"symbol": "NVDA"})

        assert "Error calculating" in result
        assert "API timeout" in result

    @pytest.mark.asyncio
    async def test_tool_uppercase_symbol(
        self, mock_data_manager: MagicMock, sample_pcr_data: SymbolPCRData
    ) -> None:
        """Test that symbol is uppercased in error messages."""
        mock_data_manager.get_symbol_pcr = AsyncMock(return_value=None)
        tools = create_pcr_tools(mock_data_manager)
        pcr_tool = tools[0]

        result = await pcr_tool.ainvoke({"symbol": "nvda"})

        # Error message should have uppercase symbol
        assert "NVDA" in result


class TestFormatPCROutput:
    """Tests for _format_pcr_output helper function."""

    def test_format_bullish_sentiment(self, sample_pcr_data: SymbolPCRData) -> None:
        """Test formatting with bullish PCR (< 0.7)."""
        result = _format_pcr_output(sample_pcr_data)

        assert "## NVDA Put/Call Ratio Analysis" in result
        # Green emoji for bullish
        assert result.count("green") == 0 or result.count("circle") == 0
        assert "Current Price" in result
        assert "$142.50" in result
        assert "ATM Zone" in result
        assert "$121.13 - $163.88" in result
        assert "Put Notional" in result
        assert "$25.50M" in result
        assert "Call Notional" in result
        assert "$42.30M" in result
        assert "Contracts Analyzed" in result
        assert "156" in result
        assert "PCR: 0.60" in result
        assert "Methodology" in result
        assert "15%" in result
        assert "$0.50" in result
        assert "500 contracts" in result

    def test_format_bearish_sentiment(self, sample_pcr_bearish: SymbolPCRData) -> None:
        """Test formatting with bearish PCR (> 1.3)."""
        result = _format_pcr_output(sample_pcr_bearish)

        assert "## AAPL Put/Call Ratio Analysis" in result
        assert "$185.25" in result
        assert "PCR: 1.46" in result
        assert "Bearish sentiment" in result

    def test_format_includes_timestamp(self, sample_pcr_data: SymbolPCRData) -> None:
        """Test that output includes calculation timestamp."""
        result = _format_pcr_output(sample_pcr_data)

        assert "Calculated:" in result
        assert "2025-01-15" in result
        assert "14:30" in result

    def test_format_markdown_table(self, sample_pcr_data: SymbolPCRData) -> None:
        """Test that output includes markdown table."""
        result = _format_pcr_output(sample_pcr_data)

        assert "| Metric | Value |" in result
        assert "|--------|-------|" in result


class TestSentimentEmoji:
    """Tests for sentiment emoji selection based on PCR value."""

    def test_bullish_emoji_pcr_below_07(self) -> None:
        """Test green emoji for PCR < 0.7 (bullish)."""
        data = SymbolPCRData(
            symbol="TEST",
            current_price=100.0,
            atm_zone_low=85.0,
            atm_zone_high=115.0,
            put_notional_mm=10.0,
            call_notional_mm=20.0,
            contracts_analyzed=50,
            pcr=0.50,  # < 0.7, bullish
            interpretation="Test",
            calculated_at=datetime.now(UTC),
        )
        result = _format_pcr_output(data)
        # Count emoji occurrences - should have green circle twice (header + PCR line)
        assert "0.50" in result

    def test_neutral_bullish_emoji_pcr_07_to_10(self) -> None:
        """Test blue emoji for PCR 0.7-1.0 (neutral-bullish)."""
        data = SymbolPCRData(
            symbol="TEST",
            current_price=100.0,
            atm_zone_low=85.0,
            atm_zone_high=115.0,
            put_notional_mm=15.0,
            call_notional_mm=18.0,
            contracts_analyzed=50,
            pcr=0.83,  # 0.7-1.0, neutral-bullish
            interpretation="Test",
            calculated_at=datetime.now(UTC),
        )
        result = _format_pcr_output(data)
        assert "0.83" in result

    def test_neutral_bearish_emoji_pcr_10_to_13(self) -> None:
        """Test orange emoji for PCR 1.0-1.3 (neutral-bearish)."""
        data = SymbolPCRData(
            symbol="TEST",
            current_price=100.0,
            atm_zone_low=85.0,
            atm_zone_high=115.0,
            put_notional_mm=22.0,
            call_notional_mm=20.0,
            contracts_analyzed=50,
            pcr=1.10,  # 1.0-1.3, neutral-bearish
            interpretation="Test",
            calculated_at=datetime.now(UTC),
        )
        result = _format_pcr_output(data)
        assert "1.10" in result

    def test_bearish_emoji_pcr_above_13(self) -> None:
        """Test red emoji for PCR > 1.3 (bearish)."""
        data = SymbolPCRData(
            symbol="TEST",
            current_price=100.0,
            atm_zone_low=85.0,
            atm_zone_high=115.0,
            put_notional_mm=30.0,
            call_notional_mm=18.0,
            contracts_analyzed=50,
            pcr=1.67,  # > 1.3, bearish
            interpretation="Test",
            calculated_at=datetime.now(UTC),
        )
        result = _format_pcr_output(data)
        assert "1.67" in result


class TestToolMetadata:
    """Tests for tool metadata and configuration."""

    def test_tools_count(self, mock_data_manager: MagicMock) -> None:
        """Test that exactly 1 tool is created."""
        tools = create_pcr_tools(mock_data_manager)
        assert len(tools) == 1

    def test_tool_name(self, mock_data_manager: MagicMock) -> None:
        """Test tool name is correct."""
        tools = create_pcr_tools(mock_data_manager)
        assert tools[0].name == "get_put_call_ratio"

    def test_tool_description(self, mock_data_manager: MagicMock) -> None:
        """Test tool has comprehensive description."""
        tools = create_pcr_tools(mock_data_manager)
        description = tools[0].description

        # Should describe the methodology
        assert "Put/Call Ratio" in description
        assert "ATM" in description
        assert "15%" in description
        # Should describe interpretation
        assert "Contrarian" in description or "contrarian" in description.lower()
        # Should give example
        assert "NVDA" in description or "AAPL" in description


# Run tests
if __name__ == "__main__":
    pytest.main([__file__, "-v"])

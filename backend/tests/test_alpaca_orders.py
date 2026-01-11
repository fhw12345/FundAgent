"""
Unit tests for Alpaca OrderOperations.

Tests order placement, retrieval, and history with mocked Alpaca client.
"""

from datetime import datetime, timezone
from unittest.mock import Mock, patch

import pytest

from src.services.alpaca.orders import OrderOperations


# ===== Fixtures =====


@pytest.fixture
def mock_alpaca_client():
    """Create mock Alpaca trading client"""
    client = Mock()
    return client


@pytest.fixture
def order_service(mock_alpaca_client):
    """Create OrderOperations with mocked client"""
    with patch("src.services.alpaca.base.TradingClient") as mock_trading_client:
        mock_trading_client.return_value = mock_alpaca_client

        mock_settings = Mock()
        mock_settings.alpaca_api_key = "test_key"
        mock_settings.alpaca_api_secret = "test_secret"
        mock_settings.alpaca_paper = True

        service = OrderOperations(mock_settings)
        service.client = mock_alpaca_client
        return service


@pytest.fixture
def mock_alpaca_order():
    """Create mock Alpaca order response"""
    order = Mock()
    order.id = "alpaca-order-123"
    order.client_order_id = "analysis-20250110"
    order.symbol = "AAPL"
    order.type = "market"
    order.side = "buy"
    order.qty = 10
    order.limit_price = None
    order.stop_price = None
    order.time_in_force = "day"
    order.status = "accepted"
    order.filled_qty = 0
    order.filled_avg_price = None
    order.submitted_at = datetime(2025, 1, 10, 10, 0, 0, tzinfo=timezone.utc)
    order.filled_at = None
    order.extended_hours = False
    return order


# ===== place_order Tests =====


class TestPlaceOrder:
    """Test place_order method"""

    @pytest.mark.asyncio
    async def test_place_market_order(self, order_service, mock_alpaca_order):
        """Test placing a market order"""
        order_service.client.submit_order.return_value = mock_alpaca_order

        result = await order_service.place_order(
            symbol="AAPL",
            quantity=10,
            side="buy",
            order_type="market",
            analysis_id="test-analysis",
            chat_id="chat_123",
            user_id="user_456",
        )

        assert result.symbol == "AAPL"
        assert result.order_type == "market"
        assert result.side == "buy"
        order_service.client.submit_order.assert_called_once()

    @pytest.mark.asyncio
    async def test_place_limit_order(self, order_service, mock_alpaca_order):
        """Test placing a limit order"""
        mock_alpaca_order.type = "limit"
        mock_alpaca_order.limit_price = 150.00
        order_service.client.submit_order.return_value = mock_alpaca_order

        result = await order_service.place_order(
            symbol="AAPL",
            quantity=10,
            side="buy",
            order_type="limit",
            limit_price=150.00,
        )

        assert result.limit_price == 150.00
        order_service.client.submit_order.assert_called_once()

    @pytest.mark.asyncio
    async def test_place_limit_order_without_price(self, order_service):
        """Test limit order requires limit_price"""
        with pytest.raises(ValueError) as exc_info:
            await order_service.place_order(
                symbol="AAPL",
                quantity=10,
                side="buy",
                order_type="limit",
                # Missing limit_price
            )
        assert "limit_price required" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_place_stop_order(self, order_service, mock_alpaca_order):
        """Test placing a stop order"""
        mock_alpaca_order.type = "stop"
        mock_alpaca_order.stop_price = 140.00
        order_service.client.submit_order.return_value = mock_alpaca_order

        result = await order_service.place_order(
            symbol="AAPL",
            quantity=10,
            side="sell",
            order_type="stop",
            stop_price=140.00,
        )

        assert result.stop_price == 140.00
        order_service.client.submit_order.assert_called_once()

    @pytest.mark.asyncio
    async def test_place_stop_order_without_price(self, order_service):
        """Test stop order requires stop_price"""
        with pytest.raises(ValueError) as exc_info:
            await order_service.place_order(
                symbol="AAPL",
                quantity=10,
                side="sell",
                order_type="stop",
                # Missing stop_price
            )
        assert "stop_price required" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_place_stop_limit_order(self, order_service, mock_alpaca_order):
        """Test placing a stop-limit order"""
        mock_alpaca_order.type = "stop_limit"
        mock_alpaca_order.stop_price = 140.00
        mock_alpaca_order.limit_price = 145.00
        order_service.client.submit_order.return_value = mock_alpaca_order

        result = await order_service.place_order(
            symbol="AAPL",
            quantity=10,
            side="sell",
            order_type="stop_limit",
            stop_price=140.00,
            limit_price=145.00,
        )

        assert result.stop_price == 140.00
        assert result.limit_price == 145.00

    @pytest.mark.asyncio
    async def test_place_stop_limit_order_missing_prices(self, order_service):
        """Test stop-limit order requires both prices"""
        with pytest.raises(ValueError) as exc_info:
            await order_service.place_order(
                symbol="AAPL",
                quantity=10,
                side="sell",
                order_type="stop_limit",
                stop_price=140.00,
                # Missing limit_price
            )
        assert "Both stop_price and limit_price required" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_unsupported_order_type(self, order_service):
        """Test unsupported order type raises error"""
        with pytest.raises(ValueError) as exc_info:
            await order_service.place_order(
                symbol="AAPL",
                quantity=10,
                side="buy",
                order_type="trailing_stop",  # Not supported
            )
        assert "Unsupported order_type" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_place_order_invalid_quantity(self, order_service):
        """Test order with invalid quantity raises error"""
        with pytest.raises(ValueError) as exc_info:
            await order_service.place_order(
                symbol="AAPL",
                quantity=0,  # Invalid
                side="buy",
                order_type="market",
            )
        assert "must be positive" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_place_order_exceeds_max_value(self, order_service):
        """Test order exceeding max value raises error"""
        with pytest.raises(ValueError) as exc_info:
            await order_service.place_order(
                symbol="AAPL",
                quantity=10000,
                side="buy",
                order_type="limit",
                limit_price=100.00,  # $1,000,000 > $500,000 max
            )
        assert "exceeds maximum limit" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_place_order_api_error(self, order_service):
        """Test order placement with API error"""
        order_service.client.submit_order.side_effect = Exception("API Error")

        with pytest.raises(Exception) as exc_info:
            await order_service.place_order(
                symbol="AAPL",
                quantity=10,
                side="buy",
                order_type="market",
            )
        assert "API Error" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_place_order_with_gtc_tif(self, order_service, mock_alpaca_order):
        """Test placing order with GTC time in force"""
        mock_alpaca_order.time_in_force = "gtc"
        order_service.client.submit_order.return_value = mock_alpaca_order

        result = await order_service.place_order(
            symbol="AAPL",
            quantity=10,
            side="buy",
            order_type="market",
            time_in_force="gtc",
        )

        assert result is not None
        order_service.client.submit_order.assert_called_once()


# ===== place_market_order Tests =====


class TestPlaceMarketOrder:
    """Test place_market_order method (backward compatibility)"""

    @pytest.mark.asyncio
    async def test_place_market_order_delegates(self, order_service, mock_alpaca_order):
        """Test place_market_order delegates to place_order"""
        order_service.client.submit_order.return_value = mock_alpaca_order

        result = await order_service.place_market_order(
            symbol="AAPL",
            quantity=10,
            side="buy",
            analysis_id="test",
            chat_id="chat_123",
            user_id="user_456",
        )

        assert result.symbol == "AAPL"


# ===== get_order_by_analysis_id Tests =====


class TestGetOrderByAnalysisId:
    """Test get_order_by_analysis_id method"""

    @pytest.mark.asyncio
    async def test_get_order_found(self, order_service, mock_alpaca_order):
        """Test getting order by analysis ID"""
        order_service.client.get_order_by_client_id.return_value = mock_alpaca_order

        result = await order_service.get_order_by_analysis_id("analysis-20250110")

        assert result is not None
        assert result.analysis_id == "analysis-20250110"

    @pytest.mark.asyncio
    async def test_get_order_not_found(self, order_service):
        """Test getting order by analysis ID when not found"""
        order_service.client.get_order_by_client_id.return_value = None

        result = await order_service.get_order_by_analysis_id("nonexistent")

        assert result is None

    @pytest.mark.asyncio
    async def test_get_order_exception(self, order_service):
        """Test getting order by analysis ID with exception"""
        order_service.client.get_order_by_client_id.side_effect = Exception("Not found")

        result = await order_service.get_order_by_analysis_id("invalid")

        assert result is None


# ===== get_order_history Tests =====


class TestGetOrderHistory:
    """Test get_order_history method"""

    @pytest.mark.asyncio
    async def test_get_order_history_success(self, order_service, mock_alpaca_order):
        """Test getting order history"""
        order_service.client.get_orders.return_value = [mock_alpaca_order]

        result = await order_service.get_order_history(user_id="user_123", limit=10)

        assert len(result) == 1
        assert result[0].symbol == "AAPL"

    @pytest.mark.asyncio
    async def test_get_order_history_empty(self, order_service):
        """Test getting empty order history"""
        order_service.client.get_orders.return_value = []

        result = await order_service.get_order_history(user_id="user_123")

        assert result == []

    @pytest.mark.asyncio
    async def test_get_order_history_exception(self, order_service):
        """Test getting order history with exception"""
        order_service.client.get_orders.side_effect = Exception("API Error")

        with pytest.raises(Exception) as exc_info:
            await order_service.get_order_history(user_id="user_123")

        assert "API Error" in str(exc_info.value)

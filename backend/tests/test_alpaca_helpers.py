"""
Unit tests for Alpaca helper utilities.

Tests validation, conversion, and transformation functions.
"""

from datetime import datetime, timezone
from unittest.mock import Mock

import pytest
from alpaca.trading.enums import OrderSide, TimeInForce

from src.services.alpaca.helpers import (
    MAX_ORDER_VALUE,
    alpaca_order_to_portfolio_order,
    alpaca_position_to_portfolio_position,
    convert_side_to_alpaca,
    convert_time_in_force_to_alpaca,
    validate_order_quantity,
    validate_order_value,
)


# ===== validate_order_quantity Tests =====


class TestValidateOrderQuantity:
    """Test validate_order_quantity function"""

    def test_valid_quantity(self):
        """Test valid positive quantity"""
        validate_order_quantity(10)
        validate_order_quantity(0.5)
        validate_order_quantity(1000)

    def test_zero_quantity(self):
        """Test zero quantity raises error"""
        with pytest.raises(ValueError) as exc_info:
            validate_order_quantity(0)
        assert "must be positive" in str(exc_info.value)

    def test_negative_quantity(self):
        """Test negative quantity raises error"""
        with pytest.raises(ValueError) as exc_info:
            validate_order_quantity(-10)
        assert "must be positive" in str(exc_info.value)


# ===== validate_order_value Tests =====


class TestValidateOrderValue:
    """Test validate_order_value function"""

    def test_valid_order_value(self):
        """Test valid order value"""
        validate_order_value(100, limit_price=100.0)  # $10,000
        validate_order_value(1000, stop_price=100.0)  # $100,000

    def test_exceeds_max_value_with_limit(self):
        """Test order value exceeding max with limit price"""
        with pytest.raises(ValueError) as exc_info:
            validate_order_value(10000, limit_price=100.0)  # $1,000,000
        assert "exceeds maximum limit" in str(exc_info.value)

    def test_exceeds_max_value_with_stop(self):
        """Test order value exceeding max with stop price"""
        with pytest.raises(ValueError) as exc_info:
            validate_order_value(10000, stop_price=100.0)  # $1,000,000
        assert "exceeds maximum limit" in str(exc_info.value)

    def test_no_price_validation_skipped(self):
        """Test no validation when no price provided"""
        # Market orders without price estimate should pass
        validate_order_value(100000)  # Large quantity but no price

    def test_exactly_at_max_value(self):
        """Test order value at exact max"""
        # $500,000 is the max
        validate_order_value(5000, limit_price=100.0)  # $500,000 exactly
        # This should pass (equal is allowed based on > comparison)

    def test_max_order_value_constant(self):
        """Test MAX_ORDER_VALUE constant"""
        assert MAX_ORDER_VALUE == 500000


# ===== convert_side_to_alpaca Tests =====


class TestConvertSideToAlpaca:
    """Test convert_side_to_alpaca function"""

    def test_buy_side(self):
        """Test buy side conversion"""
        assert convert_side_to_alpaca("buy") == OrderSide.BUY
        assert convert_side_to_alpaca("BUY") == OrderSide.BUY
        assert convert_side_to_alpaca("Buy") == OrderSide.BUY

    def test_sell_side(self):
        """Test sell side conversion"""
        assert convert_side_to_alpaca("sell") == OrderSide.SELL
        assert convert_side_to_alpaca("SELL") == OrderSide.SELL
        assert convert_side_to_alpaca("Sell") == OrderSide.SELL

    def test_unknown_defaults_to_sell(self):
        """Test unknown side defaults to sell"""
        assert convert_side_to_alpaca("unknown") == OrderSide.SELL


# ===== convert_time_in_force_to_alpaca Tests =====


class TestConvertTimeInForceToAlpaca:
    """Test convert_time_in_force_to_alpaca function"""

    def test_day_tif(self):
        """Test DAY time in force"""
        assert convert_time_in_force_to_alpaca("day") == TimeInForce.DAY
        assert convert_time_in_force_to_alpaca("DAY") == TimeInForce.DAY

    def test_gtc_tif(self):
        """Test GTC time in force"""
        assert convert_time_in_force_to_alpaca("gtc") == TimeInForce.GTC
        assert convert_time_in_force_to_alpaca("GTC") == TimeInForce.GTC

    def test_ioc_tif(self):
        """Test IOC time in force"""
        assert convert_time_in_force_to_alpaca("ioc") == TimeInForce.IOC

    def test_fok_tif(self):
        """Test FOK time in force"""
        assert convert_time_in_force_to_alpaca("fok") == TimeInForce.FOK

    def test_unknown_defaults_to_day(self):
        """Test unknown TIF defaults to DAY"""
        assert convert_time_in_force_to_alpaca("unknown") == TimeInForce.DAY
        assert convert_time_in_force_to_alpaca("") == TimeInForce.DAY


# ===== alpaca_order_to_portfolio_order Tests =====


class TestAlpacaOrderToPortfolioOrder:
    """Test alpaca_order_to_portfolio_order function"""

    @pytest.fixture
    def mock_alpaca_order(self):
        """Create mock Alpaca order"""
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
        order.status = "filled"
        order.filled_qty = 10
        order.filled_avg_price = 150.50
        order.submitted_at = datetime(2025, 1, 10, 10, 0, 0, tzinfo=timezone.utc)
        order.filled_at = datetime(2025, 1, 10, 10, 0, 1, tzinfo=timezone.utc)
        order.extended_hours = False
        return order

    def test_basic_conversion(self, mock_alpaca_order):
        """Test basic order conversion"""
        result = alpaca_order_to_portfolio_order(mock_alpaca_order)

        assert result.alpaca_order_id == "alpaca-order-123"
        assert result.analysis_id == "analysis-20250110"
        assert result.symbol == "AAPL"
        assert result.order_type == "market"
        assert result.side == "buy"
        assert result.quantity == 10.0
        assert result.status == "filled"

    def test_conversion_with_context(self, mock_alpaca_order):
        """Test order conversion with chat context"""
        result = alpaca_order_to_portfolio_order(
            mock_alpaca_order,
            chat_id="chat_123",
            user_id="user_456",
            message_id="msg_789",
        )

        assert result.chat_id == "chat_123"
        assert result.user_id == "user_456"
        assert result.message_id == "msg_789"

    def test_conversion_with_limit_price(self, mock_alpaca_order):
        """Test order conversion with limit price"""
        mock_alpaca_order.limit_price = 150.00
        result = alpaca_order_to_portfolio_order(mock_alpaca_order)

        assert result.limit_price == 150.00

    def test_conversion_with_stop_price(self, mock_alpaca_order):
        """Test order conversion with stop price"""
        mock_alpaca_order.stop_price = 145.00
        result = alpaca_order_to_portfolio_order(mock_alpaca_order)

        assert result.stop_price == 145.00

    def test_conversion_with_no_client_order_id(self, mock_alpaca_order):
        """Test order conversion with no client_order_id"""
        mock_alpaca_order.client_order_id = None
        result = alpaca_order_to_portfolio_order(mock_alpaca_order)

        assert result.analysis_id == ""

    def test_conversion_with_no_filled_avg_price(self, mock_alpaca_order):
        """Test order conversion with no filled_avg_price (pending order)"""
        mock_alpaca_order.filled_avg_price = None
        mock_alpaca_order.filled_qty = 0
        mock_alpaca_order.status = "pending"
        result = alpaca_order_to_portfolio_order(mock_alpaca_order)

        assert result.filled_avg_price is None
        assert result.filled_qty == 0

    def test_conversion_includes_metadata(self, mock_alpaca_order):
        """Test order conversion includes extended_hours metadata"""
        mock_alpaca_order.extended_hours = True
        result = alpaca_order_to_portfolio_order(mock_alpaca_order)

        assert result.metadata == {"extended_hours": True}


# ===== alpaca_position_to_portfolio_position Tests =====


class TestAlpacaPositionToPortfolioPosition:
    """Test alpaca_position_to_portfolio_position function"""

    @pytest.fixture
    def mock_alpaca_position(self):
        """Create mock Alpaca position"""
        position = Mock()
        position.symbol = "AAPL"
        position.qty = 100
        position.avg_entry_price = 150.00
        position.current_price = 160.00
        position.market_value = 16000.00
        position.cost_basis = 15000.00
        position.unrealized_pl = 1000.00
        position.unrealized_plpc = 0.0667  # 6.67%
        return position

    def test_basic_conversion(self, mock_alpaca_position):
        """Test basic position conversion"""
        result = alpaca_position_to_portfolio_position(
            mock_alpaca_position, user_id="user_123"
        )

        assert result.user_id == "user_123"
        assert result.symbol == "AAPL"
        assert result.quantity == 100.0
        assert result.avg_entry_price == 150.00
        assert result.current_price == 160.00
        assert result.market_value == 16000.00
        assert result.cost_basis == 15000.00
        assert result.unrealized_pl == 1000.00

    def test_pl_percentage_conversion(self, mock_alpaca_position):
        """Test P/L percentage is converted from decimal to percentage"""
        result = alpaca_position_to_portfolio_position(
            mock_alpaca_position, user_id="user_123"
        )

        # 0.0667 * 100 = 6.67%
        assert result.unrealized_pl_pct == pytest.approx(6.67, rel=0.01)

    def test_negative_pl(self, mock_alpaca_position):
        """Test negative P/L position"""
        mock_alpaca_position.unrealized_pl = -500.00
        mock_alpaca_position.unrealized_plpc = -0.0333  # -3.33%

        result = alpaca_position_to_portfolio_position(
            mock_alpaca_position, user_id="user_123"
        )

        assert result.unrealized_pl == -500.00
        assert result.unrealized_pl_pct == pytest.approx(-3.33, rel=0.01)

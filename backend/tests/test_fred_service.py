"""
Unit tests for FRED API Service.

Tests FRED (Federal Reserve Economic Data) API integration including:
- SOFR (Secured Overnight Financing Rate)
- EFFR (Effective Federal Funds Rate)
- RRP Balance (Fed Reverse Repo Operations)
- Error handling and edge cases
"""

from unittest.mock import AsyncMock, Mock, patch

import pandas as pd
import pytest

from src.services.market_data.fred import FREDService

# ===== Fixtures =====


@pytest.fixture
def api_key():
    """Test API key"""
    return "TEST_FRED_API_KEY"


@pytest.fixture
def service(api_key):
    """Create FREDService instance"""
    return FREDService(api_key=api_key)


@pytest.fixture
def mock_sofr_response():
    """Mock SOFR API response"""
    return {
        "observations": [
            {"date": "2025-12-28", "value": "3.66"},
            {"date": "2025-12-29", "value": "3.77"},
            {"date": "2025-12-25", "value": "."},  # Holiday - missing value
        ]
    }


@pytest.fixture
def mock_effr_response():
    """Mock EFFR API response"""
    return {
        "observations": [
            {"date": "2025-12-28", "value": "3.64"},
            {"date": "2025-12-29", "value": "3.64"},
        ]
    }


@pytest.fixture
def mock_rrp_response():
    """Mock RRP Balance API response"""
    return {
        "observations": [
            {"date": "2025-12-27", "value": "15.234"},
            {"date": "2025-12-29", "value": "12.500"},
        ]
    }


# ===== Basic Tests =====


class TestFREDServiceInit:
    """Test FREDService initialization"""

    def test_init_with_api_key(self, api_key):
        """Test service initializes with API key"""
        service = FREDService(api_key=api_key)
        assert service.api_key == api_key
        assert service._client is None
        assert service._owns_client is True

    def test_init_with_external_client(self, api_key):
        """Test service initializes with external client"""
        mock_client = Mock()
        service = FREDService(api_key=api_key, client=mock_client)
        assert service._client == mock_client
        assert service._owns_client is False


class TestGetSeries:
    """Test get_series method"""

    @pytest.mark.asyncio
    async def test_get_series_success(self, service, mock_sofr_response):
        """Test successful series fetch"""
        with patch.object(service, "_get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_response = Mock()
            mock_response.json.return_value = mock_sofr_response
            mock_response.raise_for_status = Mock()
            mock_client.get.return_value = mock_response
            mock_get_client.return_value = mock_client

            df = await service.get_series("SOFR", days=30)

            assert isinstance(df, pd.DataFrame)
            assert "value" in df.columns
            # Should filter out "." values
            assert len(df) == 2
            assert df["value"].iloc[-1] == 3.77

    @pytest.mark.asyncio
    async def test_get_series_empty_response(self, service):
        """Test handling of empty response"""
        with patch.object(service, "_get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_response = Mock()
            mock_response.json.return_value = {"observations": []}
            mock_response.raise_for_status = Mock()
            mock_client.get.return_value = mock_response
            mock_get_client.return_value = mock_client

            df = await service.get_series("SOFR", days=30)

            assert isinstance(df, pd.DataFrame)
            assert df.empty

    @pytest.mark.asyncio
    async def test_get_series_filters_invalid_values(self, service):
        """Test that invalid values are filtered out"""
        mock_response_data = {
            "observations": [
                {"date": "2025-12-28", "value": "."},  # Missing
                {"date": "2025-12-29", "value": "invalid"},  # Invalid
                {"date": "2025-12-30", "value": "3.50"},  # Valid
            ]
        }

        with patch.object(service, "_get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_response = Mock()
            mock_response.json.return_value = mock_response_data
            mock_response.raise_for_status = Mock()
            mock_client.get.return_value = mock_response
            mock_get_client.return_value = mock_client

            df = await service.get_series("SOFR", days=30)

            # Only the valid value should be included
            assert len(df) == 1
            assert df["value"].iloc[0] == 3.50


class TestSOFR:
    """Test SOFR-specific method"""

    @pytest.mark.asyncio
    async def test_get_sofr(self, service, mock_sofr_response):
        """Test SOFR retrieval"""
        with patch.object(service, "get_series") as mock_get_series:
            mock_df = pd.DataFrame(
                {"value": [3.66, 3.77]},
                index=pd.to_datetime(["2025-12-28", "2025-12-29"]),
            )
            mock_get_series.return_value = mock_df

            df = await service.get_sofr(days=60)

            mock_get_series.assert_called_once_with("SOFR", 60)
            assert isinstance(df, pd.DataFrame)
            assert len(df) == 2


class TestEFFR:
    """Test EFFR-specific method"""

    @pytest.mark.asyncio
    async def test_get_effr(self, service, mock_effr_response):
        """Test EFFR retrieval"""
        with patch.object(service, "get_series") as mock_get_series:
            mock_df = pd.DataFrame(
                {"value": [3.64, 3.64]},
                index=pd.to_datetime(["2025-12-28", "2025-12-29"]),
            )
            mock_get_series.return_value = mock_df

            df = await service.get_effr(days=60)

            mock_get_series.assert_called_once_with("EFFR", 60)
            assert isinstance(df, pd.DataFrame)


class TestRRPBalance:
    """Test RRP Balance method"""

    @pytest.mark.asyncio
    async def test_get_rrp_balance(self, service, mock_rrp_response):
        """Test RRP balance retrieval"""
        with patch.object(service, "get_series") as mock_get_series:
            mock_df = pd.DataFrame(
                {"value": [15.234, 12.500]},
                index=pd.to_datetime(["2025-12-27", "2025-12-29"]),
            )
            mock_get_series.return_value = mock_df

            df = await service.get_rrp_balance(days=60)

            mock_get_series.assert_called_once_with("RRPONTSYD", 60)
            assert isinstance(df, pd.DataFrame)
            assert len(df) == 2
            # Latest RRP should be ~12.5B
            assert df["value"].iloc[-1] == 12.500


class TestErrorHandling:
    """Test error handling scenarios"""

    @pytest.mark.asyncio
    async def test_http_error(self, service):
        """Test handling of HTTP errors"""
        import httpx

        with patch.object(service, "_get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_response = Mock()
            mock_response.status_code = 500
            error = httpx.HTTPStatusError(
                "Server Error", request=Mock(), response=mock_response
            )
            mock_response.raise_for_status.side_effect = error
            mock_client.get.return_value = mock_response
            mock_get_client.return_value = mock_client

            with pytest.raises(ValueError, match="FRED API error: 500"):
                await service.get_series("SOFR")

    @pytest.mark.asyncio
    async def test_request_error(self, service):
        """Test handling of request errors"""
        import httpx

        with patch.object(service, "_get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.get.side_effect = httpx.RequestError("Connection failed")
            mock_get_client.return_value = mock_client

            with pytest.raises(ValueError, match="FRED API request failed"):
                await service.get_series("SOFR")

    @pytest.mark.asyncio
    async def test_no_observations_key(self, service):
        """Test handling of response without observations key"""
        with patch.object(service, "_get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_response = Mock()
            mock_response.json.return_value = {"error": "API limit reached"}
            mock_response.raise_for_status = Mock()
            mock_client.get.return_value = mock_response
            mock_get_client.return_value = mock_client

            df = await service.get_series("SOFR")

            assert isinstance(df, pd.DataFrame)
            assert df.empty


class TestClientManagement:
    """Test HTTP client lifecycle management"""

    @pytest.mark.asyncio
    async def test_close_owned_client(self, api_key):
        """Test closing owned client"""
        service = FREDService(api_key=api_key)

        # Create client
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value = mock_client

            client = await service._get_client()
            assert client is not None

            await service.close()
            mock_client.aclose.assert_called_once()

    @pytest.mark.asyncio
    async def test_close_external_client_not_closed(self, api_key):
        """Test that external client is not closed by service"""
        external_client = AsyncMock()
        service = FREDService(api_key=api_key, client=external_client)

        await service.close()

        # External client should not be closed
        external_client.aclose.assert_not_called()


class TestLiquidityMetricCalculation:
    """Test liquidity metric calculation scenarios"""

    @pytest.mark.asyncio
    async def test_sofr_effr_spread_calculation(self, service):
        """Test SOFR-EFFR spread calculation for bubble risk"""
        with patch.object(service, "get_series") as mock_get_series:
            # SOFR at 3.77%, EFFR at 3.64% = 13 bps spread
            async def mock_series(series_id, days=60):
                if series_id == "SOFR":
                    return pd.DataFrame(
                        {"value": [3.77]},
                        index=pd.to_datetime(["2025-12-29"]),
                    )
                elif series_id == "EFFR":
                    return pd.DataFrame(
                        {"value": [3.64]},
                        index=pd.to_datetime(["2025-12-29"]),
                    )
                return pd.DataFrame(columns=["value"])

            mock_get_series.side_effect = mock_series

            sofr_df = await service.get_sofr()
            effr_df = await service.get_effr()

            sofr = float(sofr_df["value"].iloc[-1])
            effr = float(effr_df["value"].iloc[-1])
            spread_bps = (sofr - effr) * 100

            # 13 bps spread
            assert abs(spread_bps - 13) < 1

    @pytest.mark.asyncio
    async def test_rrp_trend_analysis(self, service):
        """Test RRP trend analysis for liquidity direction"""
        with patch.object(service, "get_series") as mock_get_series:
            # RRP declining from 50B to 12.5B over 20 days
            dates = pd.date_range(end="2025-12-29", periods=25, freq="D")
            values = [50.0] + [50 - i * 1.5 for i in range(1, 25)]
            mock_df = pd.DataFrame({"value": values}, index=dates)
            mock_get_series.return_value = mock_df

            df = await service.get_rrp_balance(days=30)

            current = float(df["value"].iloc[-1])
            previous_20d = float(df["value"].iloc[-20])
            change = current - previous_20d
            change_pct = (change / previous_20d) * 100

            # RRP is declining - tight liquidity
            assert change < 0
            assert change_pct < 0

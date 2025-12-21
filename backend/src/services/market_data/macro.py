"""
Macroeconomic indicators and commodity prices for Alpha Vantage service.
"""

import pandas as pd
import structlog

from .base import AlphaVantageBase

logger = structlog.get_logger()


class MacroMixin(AlphaVantageBase):
    """Methods for macroeconomic indicators and commodity prices."""

    async def get_real_gdp(self, interval: str = "annual") -> pd.DataFrame:
        """
        Get Real GDP economic indicator using REAL_GDP endpoint.

        Args:
            interval: annual (default) or quarterly

        Returns:
            DataFrame with date index and value column
        """
        try:
            response = await self.client.get(
                self.base_url,
                params={
                    "function": "REAL_GDP",
                    "interval": interval,
                    "apikey": self.api_key,
                },
            )

            if response.status_code != 200:
                sanitized_text = self._sanitize_text(response.text)
                raise ValueError(
                    f"Alpha Vantage API error: {response.status_code} - {sanitized_text}"
                )

            data = response.json()

            if "data" not in data:
                sanitized = self._sanitize_response(data)
                raise ValueError(f"No REAL_GDP data available: {sanitized}")

            # Convert to DataFrame
            df_data = []
            for item in data["data"]:
                df_data.append(
                    {
                        "date": pd.to_datetime(item["date"]),
                        "value": float(item["value"]),
                    }
                )

            df = pd.DataFrame(df_data)
            df.set_index("date", inplace=True)
            df.sort_index(inplace=True)

            logger.info("REAL_GDP data fetched", interval=interval, data_points=len(df))

            return df

        except Exception as e:
            logger.error("REAL_GDP fetch failed", interval=interval, error=str(e))
            raise

    async def get_cpi(self, interval: str = "monthly") -> pd.DataFrame:
        """
        Get Consumer Price Index (CPI) using CPI endpoint.

        Args:
            interval: monthly (default) or semiannual

        Returns:
            DataFrame with date index and value column
        """
        try:
            response = await self.client.get(
                self.base_url,
                params={
                    "function": "CPI",
                    "interval": interval,
                    "apikey": self.api_key,
                },
            )

            if response.status_code != 200:
                sanitized_text = self._sanitize_text(response.text)
                raise ValueError(
                    f"Alpha Vantage API error: {response.status_code} - {sanitized_text}"
                )

            data = response.json()

            if "data" not in data:
                sanitized = self._sanitize_response(data)
                raise ValueError(f"No CPI data available: {sanitized}")

            # Convert to DataFrame
            df_data = []
            for item in data["data"]:
                df_data.append(
                    {
                        "date": pd.to_datetime(item["date"]),
                        "value": float(item["value"]),
                    }
                )

            df = pd.DataFrame(df_data)
            df.set_index("date", inplace=True)
            df.sort_index(inplace=True)

            logger.info("CPI data fetched", interval=interval, data_points=len(df))

            return df

        except Exception as e:
            logger.error("CPI fetch failed", interval=interval, error=str(e))
            raise

    async def get_inflation(self) -> pd.DataFrame:
        """
        Get Inflation rate using INFLATION endpoint.

        Returns:
            DataFrame with date index and value column
        """
        try:
            response = await self.client.get(
                self.base_url,
                params={
                    "function": "INFLATION",
                    "apikey": self.api_key,
                },
            )

            if response.status_code != 200:
                sanitized_text = self._sanitize_text(response.text)
                raise ValueError(
                    f"Alpha Vantage API error: {response.status_code} - {sanitized_text}"
                )

            data = response.json()

            if "data" not in data:
                sanitized = self._sanitize_response(data)
                raise ValueError(f"No INFLATION data available: {sanitized}")

            # Convert to DataFrame
            df_data = []
            for item in data["data"]:
                df_data.append(
                    {
                        "date": pd.to_datetime(item["date"]),
                        "value": float(item["value"]),
                    }
                )

            df = pd.DataFrame(df_data)
            df.set_index("date", inplace=True)
            df.sort_index(inplace=True)

            logger.info("INFLATION data fetched", data_points=len(df))

            return df

        except Exception as e:
            logger.error("INFLATION fetch failed", error=str(e))
            raise

    async def get_unemployment(self) -> pd.DataFrame:
        """
        Get Unemployment rate using UNEMPLOYMENT endpoint.

        Returns:
            DataFrame with date index and value column
        """
        try:
            response = await self.client.get(
                self.base_url,
                params={
                    "function": "UNEMPLOYMENT",
                    "apikey": self.api_key,
                },
            )

            if response.status_code != 200:
                sanitized_text = self._sanitize_text(response.text)
                raise ValueError(
                    f"Alpha Vantage API error: {response.status_code} - {sanitized_text}"
                )

            data = response.json()

            if "data" not in data:
                sanitized = self._sanitize_response(data)
                raise ValueError(f"No UNEMPLOYMENT data available: {sanitized}")

            # Convert to DataFrame
            df_data = []
            for item in data["data"]:
                df_data.append(
                    {
                        "date": pd.to_datetime(item["date"]),
                        "value": float(item["value"]),
                    }
                )

            df = pd.DataFrame(df_data)
            df.set_index("date", inplace=True)
            df.sort_index(inplace=True)

            logger.info("UNEMPLOYMENT data fetched", data_points=len(df))

            return df

        except Exception as e:
            logger.error("UNEMPLOYMENT fetch failed", error=str(e))
            raise

    async def get_commodity_prices(self, interval: str = "monthly") -> pd.DataFrame:
        """
        Get Global Price Index of All Commodities using WTI endpoint as proxy.

        Note: Alpha Vantage provides WTI (West Texas Intermediate) crude oil prices,
        which serves as a commodity market indicator.

        Args:
            interval: daily, weekly, or monthly (default)

        Returns:
            DataFrame with date index and value column
        """
        try:
            response = await self.client.get(
                self.base_url,
                params={
                    "function": "WTI",
                    "interval": interval,
                    "apikey": self.api_key,
                },
            )

            if response.status_code != 200:
                sanitized_text = self._sanitize_text(response.text)
                raise ValueError(
                    f"Alpha Vantage API error: {response.status_code} - {sanitized_text}"
                )

            data = response.json()

            if "data" not in data:
                sanitized = self._sanitize_response(data)
                raise ValueError(f"No commodity price data available: {sanitized}")

            # Convert to DataFrame
            df_data = []
            for item in data["data"]:
                df_data.append(
                    {
                        "date": pd.to_datetime(item["date"]),
                        "value": float(item["value"]),
                    }
                )

            df = pd.DataFrame(df_data)
            df.set_index("date", inplace=True)
            df.sort_index(inplace=True)

            logger.info(
                "Commodity prices (WTI) fetched",
                interval=interval,
                data_points=len(df),
            )

            return df

        except Exception as e:
            logger.error(
                "Commodity prices fetch failed", interval=interval, error=str(e)
            )
            raise

    async def get_commodity_price(
        self, commodity: str = "COPPER", interval: str = "monthly"
    ) -> pd.DataFrame:
        """
        Get global commodity prices (COPPER, ALUMINUM, WHEAT, etc.).

        Uses commodity-specific endpoints (COPPER, ALUMINUM, etc.).
        Returns time series of commodity prices.

        Args:
            commodity: Commodity code (COPPER, ALUMINUM, WHEAT, CORN, etc.)
            interval: daily, weekly, or monthly (default: monthly)

        Returns:
            DataFrame with date index and value column
        """
        try:
            # Validate commodity code
            valid_commodities = [
                "COPPER",
                "ALUMINUM",
                "WHEAT",
                "CORN",
                "COTTON",
                "SUGAR",
                "COFFEE",
                "ALL_COMMODITIES",
            ]
            commodity_upper = commodity.upper()

            if commodity_upper not in valid_commodities:
                raise ValueError(
                    f"Invalid commodity: {commodity}. Use one of: {', '.join(valid_commodities)}"
                )

            response = await self.client.get(
                self.base_url,
                params={
                    "function": commodity_upper,
                    "interval": interval,
                    "apikey": self.api_key,
                },
            )

            if response.status_code != 200:
                sanitized_text = self._sanitize_text(response.text)
                raise ValueError(
                    f"Alpha Vantage API error: {response.status_code} - {sanitized_text}"
                )

            data = response.json()

            if "data" not in data:
                sanitized = self._sanitize_response(data)
                raise ValueError(f"No {commodity} price data available: {sanitized}")

            # Convert to DataFrame
            df_data = []
            for item in data["data"]:
                df_data.append(
                    {
                        "date": pd.to_datetime(item["date"]),
                        "value": float(item["value"]),
                    }
                )

            df = pd.DataFrame(df_data)
            df.set_index("date", inplace=True)
            df.sort_index(inplace=True)

            logger.info(
                "Commodity price fetched",
                commodity=commodity,
                interval=interval,
                data_points=len(df),
            )

            return df

        except Exception as e:
            logger.error(
                "Commodity price fetch failed",
                commodity=commodity,
                interval=interval,
                error=str(e),
            )
            raise

    async def get_treasury_yield(
        self, maturity: str = "10year", interval: str = "monthly"
    ) -> pd.DataFrame:
        """
        Get Treasury yield data using TREASURY_YIELD endpoint.

        Args:
            maturity: Treasury maturity (3month, 2year, 5year, 7year, 10year, 30year)
            interval: daily, weekly, or monthly (default)

        Returns:
            DataFrame with date index and value (yield percentage) column
        """
        try:
            valid_maturities = ["3month", "2year", "5year", "7year", "10year", "30year"]
            if maturity not in valid_maturities:
                raise ValueError(
                    f"Invalid maturity: {maturity}. Use one of: {', '.join(valid_maturities)}"
                )

            response = await self.client.get(
                self.base_url,
                params={
                    "function": "TREASURY_YIELD",
                    "interval": interval,
                    "maturity": maturity,
                    "apikey": self.api_key,
                },
            )

            if response.status_code != 200:
                sanitized_text = self._sanitize_text(response.text)
                raise ValueError(
                    f"Alpha Vantage API error: {response.status_code} - {sanitized_text}"
                )

            data = response.json()

            if "data" not in data:
                sanitized = self._sanitize_response(data)
                raise ValueError(f"No TREASURY_YIELD data available: {sanitized}")

            # Convert to DataFrame
            df_data = []
            for item in data["data"]:
                # Skip entries with "." as value (no data)
                if item.get("value") == ".":
                    continue
                df_data.append(
                    {
                        "date": pd.to_datetime(item["date"]),
                        "value": float(item["value"]),
                    }
                )

            df = pd.DataFrame(df_data)
            if not df.empty:
                df.set_index("date", inplace=True)
                df.sort_index(inplace=True)

            logger.info(
                "TREASURY_YIELD data fetched",
                maturity=maturity,
                interval=interval,
                data_points=len(df),
            )

            return df

        except Exception as e:
            logger.error(
                "TREASURY_YIELD fetch failed",
                maturity=maturity,
                interval=interval,
                error=str(e),
            )
            raise

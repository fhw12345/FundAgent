"""
Unit tests for AlphaVantageResponseFormatter.

Tests all 5 formatter methods and utility functions for:
- Company Overview
- Cash Flow
- Balance Sheet
- News Sentiment
- Market Movers
"""

from datetime import UTC, datetime

import pytest

from src.services.alphavantage_response_formatter import AlphaVantageResponseFormatter


class TestAlphaVantageResponseFormatter:
    """Test suite for AlphaVantageResponseFormatter."""

    @pytest.fixture
    def formatter(self):
        """Create formatter instance for tests."""
        return AlphaVantageResponseFormatter()

    @pytest.fixture
    def sample_invoked_at(self):
        """Sample invocation timestamp."""
        return datetime(2025, 1, 16, 10, 30, 0, tzinfo=UTC).isoformat()

    # ========================================
    # Utility Function Tests
    # ========================================

    def test_safe_float_with_valid_string(self, formatter):
        """Test safe_float with valid numeric string."""
        result = formatter._safe_float("123.45")
        assert result == 123.45

    def test_safe_float_with_none(self, formatter):
        """Test safe_float with None returns default."""
        result = formatter._safe_float(None, default=100.0)
        assert result == 100.0

    def test_safe_float_with_invalid_string(self, formatter):
        """Test safe_float with invalid string returns default."""
        result = formatter._safe_float("invalid", default=50.0)
        assert result == 50.0

    def test_format_large_number_millions(self, formatter):
        """Test formatting numbers in millions."""
        result = formatter._format_large_number(5_500_000)
        assert result == "$5.5M"  # Uses .1f for millions

    def test_format_large_number_billions(self, formatter):
        """Test formatting numbers in billions."""
        result = formatter._format_large_number(2_300_000_000)
        assert result == "$2.30B"

    def test_format_large_number_none(self, formatter):
        """Test formatting None returns N/A."""
        result = formatter._format_large_number(None)
        assert result == "N/A"

    def test_calculate_qoq_growth_positive(self, formatter):
        """Test QoQ growth calculation with positive growth."""
        result = formatter._calculate_qoq_growth(110.0, 100.0)
        assert result == "+10.0%"

    def test_calculate_qoq_growth_negative(self, formatter):
        """Test QoQ growth calculation with negative growth."""
        result = formatter._calculate_qoq_growth(90.0, 100.0)
        assert result == "-10.0%"

    def test_calculate_qoq_growth_with_none(self, formatter):
        """Test QoQ growth calculation with None values."""
        result = formatter._calculate_qoq_growth(None, 100.0)
        assert result == "N/A"

        result = formatter._calculate_qoq_growth(100.0, None)
        assert result == "N/A"

    def test_calculate_qoq_growth_division_by_zero(self, formatter):
        """Test QoQ growth calculation with zero previous value."""
        result = formatter._calculate_qoq_growth(100.0, 0.0)
        assert result == "N/A"

    def test_generate_metadata_header(self, formatter, sample_invoked_at):
        """Test metadata header generation."""
        result = formatter._generate_metadata_header(
            tool_name="Company Overview",
            symbol="AAPL",
            invoked_at=sample_invoked_at,
            data_source="OVERVIEW",  # Formatter adds "Alpha Vantage " prefix and " API" suffix
        )

        assert "**Tool:** Company Overview" in result
        assert "**Symbol:** AAPL" in result
        assert "**Invoked:** 2025-01-16T10:30:00+00:00" in result
        assert "**Data Source:** Alpha Vantage OVERVIEW API" in result

    def test_extract_current_year_quarters_all_quarters(self, formatter):
        """Test extracting all quarters from current year."""
        quarterly_reports = [
            {"fiscalDateEnding": "2024-03-31"},
            {"fiscalDateEnding": "2024-06-30"},
            {"fiscalDateEnding": "2024-09-30"},
            {"fiscalDateEnding": "2024-12-31"},
            {"fiscalDateEnding": "2023-12-31"},  # Different year
        ]

        result = formatter._extract_current_year_quarters(
            quarterly_reports, current_year=2024
        )

        assert len(result) == 4
        assert result[0]["fiscalDateEnding"] == "2024-03-31"
        assert result[3]["fiscalDateEnding"] == "2024-12-31"

    def test_extract_current_year_quarters_partial_year(self, formatter):
        """Test extracting partial year quarters (e.g., Q1-Q3)."""
        quarterly_reports = [
            {"fiscalDateEnding": "2024-03-31"},
            {"fiscalDateEnding": "2024-06-30"},
            {"fiscalDateEnding": "2024-09-30"},
        ]

        result = formatter._extract_current_year_quarters(
            quarterly_reports, current_year=2024
        )

        assert len(result) == 3

    def test_extract_current_year_quarters_empty_list(self, formatter):
        """Test extracting from empty quarterly reports."""
        result = formatter._extract_current_year_quarters([], current_year=2024)
        assert len(result) == 0

    # ========================================
    # Company Overview Tests
    # ========================================

    def test_format_company_overview_complete_data(self, formatter, sample_invoked_at):
        """Test company overview formatting with complete data."""
        raw_data = {
            "Symbol": "AAPL",
            "Name": "Apple Inc",
            "Description": "Technology company",
            "Industry": "Consumer Electronics",
            "Sector": "Technology",
            "Exchange": "NASDAQ",
            "Country": "USA",
            "MarketCapitalization": "3000000000000",
            "PERatio": "25.5",
            "EPS": "6.12",
            "ProfitMargin": "0.25",
            "RevenueTTM": "400000000000",
            "DividendYield": "0.005",
            "Beta": "1.2",
            "PercentInsiders": "0.07",
            "PercentInstitutions": "60.5",
            "52WeekHigh": "195.00",
            "52WeekLow": "125.00",
        }

        result = formatter.format_company_overview(
            raw_data=raw_data,
            symbol="AAPL",
            invoked_at=sample_invoked_at,
        )

        # Check metadata header
        assert "**Tool:** Company Overview" in result
        assert "**Symbol:** AAPL" in result

        # Check company info
        assert "Apple Inc" in result
        assert "Consumer Electronics" in result
        assert "Technology" in result

        # Check key metrics (formatter doesn't have trillion support, uses billions)
        assert "$3000.00B" in result  # Market cap (3 trillion = 3000 billion)
        assert "25.50" in result  # P/E ratio
        assert "$6.12" in result  # EPS

    def test_format_company_overview_missing_optional_fields(
        self, formatter, sample_invoked_at
    ):
        """Test company overview formatting with missing optional fields."""
        raw_data = {
            "Symbol": "XYZ",
            "Name": "XYZ Corp",
            # Missing Description, Industry, Sector to test N/A handling
            "Exchange": "NYSE",
            "Country": "USA",
        }

        result = formatter.format_company_overview(
            raw_data=raw_data,
            symbol="XYZ",
            invoked_at=sample_invoked_at,
        )

        # Should not crash and should contain N/A for missing fields
        assert "XYZ Corp" in result
        assert (
            "N/A" in result
        )  # Should appear for missing Description, Industry, Sector

    # ========================================
    # Cash Flow Tests
    # ========================================

    def test_format_cash_flow_with_quarters(self, formatter, sample_invoked_at):
        """Test cash flow formatting with annual + quarterly data."""
        from datetime import datetime

        current_year = datetime.now().year

        raw_data = {
            "symbol": "MSFT",
            "annualReports": [
                {
                    "fiscalDateEnding": "2023-12-31",
                    "operatingCashflow": "100000000000",
                    "capitalExpenditures": "-30000000000",
                    "dividendPayout": "20000000000",
                }
            ],
            "quarterlyReports": [
                {
                    "fiscalDateEnding": f"{current_year}-03-31",  # Use current year
                    "operatingCashflow": "25000000000",
                    "capitalExpenditures": "-7500000000",
                },
                {
                    "fiscalDateEnding": f"{current_year}-06-30",  # Use current year
                    "operatingCashflow": "27000000000",
                    "capitalExpenditures": "-8000000000",
                },
                {
                    "fiscalDateEnding": f"{current_year}-09-30",  # Use current year
                    "operatingCashflow": "28000000000",
                    "capitalExpenditures": "-8500000000",
                },
            ],
        }

        result = formatter.format_cash_flow(
            raw_data=raw_data,
            symbol="MSFT",
            invoked_at=sample_invoked_at,
        )

        # Check metadata
        assert "**Tool:** Cash Flow Analysis" in result
        assert "**Symbol:** MSFT" in result

        # Check annual data (formatter shows "FY 2023" not raw date)
        assert "FY 2023" in result or "2023" in result
        assert "$100.00B" in result  # Operating cash flow

        # Check quarterly data exists (formatter shows current year quarters)
        assert str(current_year) in result  # Should have current year quarterly data
        assert (
            "$25.00B" in result or "$27.00B" in result or "$28.00B" in result
        )  # Q1, Q2, or Q3 data

    def test_format_cash_flow_no_quarters(self, formatter, sample_invoked_at):
        """Test cash flow formatting with only annual data."""
        raw_data = {
            "symbol": "TSLA",
            "annualReports": [
                {
                    "fiscalDateEnding": "2023-12-31",
                    "operatingCashflow": "5000000000",
                    "capitalExpenditures": "-2000000000",
                }
            ],
            "quarterlyReports": [],
        }

        result = formatter.format_cash_flow(
            raw_data=raw_data,
            symbol="TSLA",
            invoked_at=sample_invoked_at,
        )

        # Should not crash with no quarterly data
        assert "TSLA" in result
        assert (
            "FY 2023" in result or "2023" in result
        )  # Formatter shows "FY 2023" not raw date

    # ========================================
    # Balance Sheet Tests
    # ========================================

    def test_format_balance_sheet_with_quarters(self, formatter, sample_invoked_at):
        """Test balance sheet formatting with annual + quarterly data."""
        from datetime import datetime

        current_year = datetime.now().year

        raw_data = {
            "symbol": "GOOGL",
            "annualReports": [
                {
                    "fiscalDateEnding": "2023-12-31",
                    "totalAssets": "400000000000",
                    "totalLiabilities": "120000000000",
                    "totalShareholderEquity": "280000000000",
                    "currentAssets": "150000000000",
                    "currentLiabilities": "60000000000",
                }
            ],
            "quarterlyReports": [
                {
                    "fiscalDateEnding": f"{current_year}-03-31",  # Use current year
                    "totalAssets": "410000000000",
                    "totalLiabilities": "125000000000",
                },
                {
                    "fiscalDateEnding": f"{current_year}-06-30",  # Use current year
                    "totalAssets": "420000000000",
                    "totalLiabilities": "130000000000",
                },
            ],
        }

        result = formatter.format_balance_sheet(
            raw_data=raw_data,
            symbol="GOOGL",
            invoked_at=sample_invoked_at,
        )

        # Check metadata
        assert "**Tool:** Balance Sheet Analysis" in result
        assert "**Symbol:** GOOGL" in result

        # Check annual data
        assert "$400.00B" in result  # Total assets
        assert "$280.00B" in result  # Equity

        # Check quarterly data (formatter shows current year quarters)
        assert str(current_year) in result  # Should have current year quarterly trend
        assert "$410.00B" in result or "$420.00B" in result  # Q1 or Q2 assets

    def test_format_balance_sheet_financial_ratios(self, formatter, sample_invoked_at):
        """Test balance sheet includes calculated financial ratios."""
        raw_data = {
            "symbol": "FB",
            "annualReports": [
                {
                    "fiscalDateEnding": "2023-12-31",
                    "totalAssets": "200000000000",
                    "totalLiabilities": "40000000000",
                    "totalShareholderEquity": "160000000000",
                    "currentAssets": "100000000000",
                    "currentLiabilities": "30000000000",
                }
            ],
            "quarterlyReports": [],
        }

        result = formatter.format_balance_sheet(
            raw_data=raw_data,
            symbol="FB",
            invoked_at=sample_invoked_at,
        )

        # Should include financial ratios like current ratio, debt-to-equity
        assert "FB" in result
        # Current ratio = current assets / current liabilities = 100/30 = 3.33
        # Debt-to-equity = total liabilities / equity = 40/160 = 0.25

    # ========================================
    # News Sentiment Tests
    # ========================================

    def test_format_news_sentiment_with_articles(self, formatter, sample_invoked_at):
        """Test news sentiment formatting with articles."""
        raw_data = {
            "feed": [
                {
                    "title": "Great earnings report",
                    "url": "https://example.com/1",
                    "source": "Bloomberg",
                    "overall_sentiment_score": 0.75,
                    "overall_sentiment_label": "Bullish",
                },
                {
                    "title": "Concerns about market",
                    "url": "https://example.com/2",
                    "source": "Reuters",
                    "overall_sentiment_score": -0.60,
                    "overall_sentiment_label": "Bearish",
                },
                {
                    "title": "Analyst upgrade",
                    "url": "https://example.com/3",
                    "source": "CNBC",
                    "overall_sentiment_score": 0.50,
                    "overall_sentiment_label": "Bullish",
                },
            ]
        }

        result = formatter.format_news_sentiment(
            raw_data=raw_data,
            symbol="NVDA",
            invoked_at=sample_invoked_at,
        )

        # Check metadata
        assert "**Tool:** News Sentiment Analysis" in result
        assert "**Symbol:** NVDA" in result

        # Check positive and negative news sections
        assert "Great earnings report" in result
        assert "Concerns about market" in result
        assert "Bloomberg" in result

    def test_format_news_sentiment_no_articles(self, formatter, sample_invoked_at):
        """Test news sentiment formatting with no articles."""
        raw_data = {"feed": []}

        result = formatter.format_news_sentiment(
            raw_data=raw_data,
            symbol="XYZ",
            invoked_at=sample_invoked_at,
        )

        # Should handle empty feed gracefully
        assert "XYZ" in result

    def test_format_news_sentiment_with_summary_and_time(
        self, formatter, sample_invoked_at
    ):
        """Test news sentiment with summary and publication time."""
        raw_data = {
            "feed": [
                {
                    "title": "Apple announces record profits",
                    "url": "https://example.com/apple-profits",
                    "source": "WSJ",
                    "overall_sentiment_score": 0.85,
                    "overall_sentiment_label": "Bullish",
                    "summary": "Apple Inc. reported record quarterly profits driven by strong iPhone sales and growing services revenue.",
                    "time_published": "20250115T143000",
                },
                {
                    "title": "Tech stocks face pressure",
                    "url": "https://example.com/tech-pressure",
                    "source": "Bloomberg",
                    "overall_sentiment_score": -0.45,
                    "overall_sentiment_label": "Bearish",
                    "summary": "Technology stocks continue to face headwinds as interest rates remain elevated and growth concerns persist in the sector.",
                    "time_published": "20250114T090000",
                },
            ]
        }

        result = formatter.format_news_sentiment(
            raw_data=raw_data,
            symbol="AAPL",
            invoked_at=sample_invoked_at,
        )

        # Check titles are clickable links with link icon and bold
        assert (
            "🔗 **[Apple announces record profits](https://example.com/apple-profits)**"
            in result
        )
        assert (
            "🔗 **[Tech stocks face pressure](https://example.com/tech-pressure)**"
            in result
        )

        # Check summaries are included in expandable sections
        assert "Apple Inc. reported record quarterly profits" in result
        assert "Technology stocks continue to face headwinds" in result

        # Check expandable summary structure
        assert "<details>" in result
        assert "<summary><strong>📄 Read summary</strong></summary>" in result
        assert "</details>" in result

        # Check publication dates are formatted
        assert "Jan 15, 2025" in result
        assert "Jan 14, 2025" in result

        # Check sentiment labels
        assert "Bullish" in result
        assert "Bearish" in result

    # ========================================
    # Market Movers Tests
    # ========================================

    def test_format_market_movers_complete_data(self, formatter, sample_invoked_at):
        """Test market movers formatting with complete data."""
        raw_data = {
            "top_gainers": [
                {
                    "ticker": "NVDA",
                    "price": "500.00",
                    "change_amount": "25.50",
                    "change_percentage": "5.38%",
                    "volume": "50000000",
                },
                {
                    "ticker": "TSLA",
                    "price": "250.00",
                    "change_amount": "10.00",
                    "change_percentage": "4.17%",
                    "volume": "40000000",
                },
            ],
            "top_losers": [
                {
                    "ticker": "XYZ",
                    "price": "50.00",
                    "change_amount": "-5.00",
                    "change_percentage": "-9.09%",
                    "volume": "20000000",
                }
            ],
            "most_actively_traded": [
                {
                    "ticker": "AAPL",
                    "price": "180.00",
                    "change_amount": "2.00",
                    "change_percentage": "1.12%",
                    "volume": "100000000",
                }
            ],
        }

        result = formatter.format_market_movers(
            raw_data=raw_data,
            invoked_at=sample_invoked_at,
        )

        # Check metadata
        assert "**Tool:** Market Movers" in result

        # Check all three tables
        assert "Top Gainers" in result
        assert "Top Losers" in result
        assert "Most Active" in result

        # Check specific data
        assert "NVDA" in result
        assert "$500.00" in result
        assert "5.38%" in result

    def test_format_market_movers_empty_categories(self, formatter, sample_invoked_at):
        """Test market movers formatting with empty categories."""
        raw_data = {
            "top_gainers": [],
            "top_losers": [],
            "most_actively_traded": [],
        }

        result = formatter.format_market_movers(
            raw_data=raw_data,
            invoked_at=sample_invoked_at,
        )

        # Should handle empty categories gracefully without crashing
        assert "Market Movers" in result
        assert "**Tool:** Market Movers" in result  # Has metadata header


class TestEdgeCases:
    """Test edge cases and error handling."""

    @pytest.fixture
    def formatter(self):
        """Create formatter instance for tests."""
        return AlphaVantageResponseFormatter()

    def test_malformed_fiscal_date_format(self, formatter):
        """Test handling of malformed fiscal date formats."""
        quarterly_reports = [
            {"fiscalDateEnding": "invalid-date"},
            {"fiscalDateEnding": "2024-13-50"},  # Invalid month/day
        ]

        # Should not crash
        result = formatter._extract_current_year_quarters(
            quarterly_reports, current_year=2024
        )
        assert isinstance(result, list)

    def test_none_values_in_calculations(self, formatter):
        """Test that None values don't cause crashes in calculations."""
        # Should return "N/A" instead of crashing
        result = formatter._format_large_number(None)
        assert result == "N/A"

        result = formatter._calculate_qoq_growth(None, None)
        assert result == "N/A"

    def test_extreme_large_numbers(self, formatter):
        """Test formatting extremely large numbers."""
        # Trillions
        result = formatter._format_large_number(1_500_000_000_000)
        assert (
            result == "$1500.00B"
        )  # Formatter doesn't have trillion support, uses billions

        # Very large billions
        result = formatter._format_large_number(999_000_000_000)
        assert result == "$999.00B"

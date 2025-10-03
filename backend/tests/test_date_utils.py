"""
Unit tests for date utility functions.
Tests period-to-date conversion and date validation logic.
"""

import pytest
from datetime import datetime, timedelta
from src.core.utils.date_utils import DateUtils


class TestDateUtils:
    """Test suite for DateUtils class."""

    def test_period_to_date_range_basic_periods(self):
        """Test conversion of basic period strings to date ranges."""
        # Use fixed reference date for predictable testing
        reference_date = datetime(2024, 10, 3, 15, 30, 0)

        test_cases = [
            ('1d', '2024-10-02', '2024-10-03'),
            ('5d', '2024-09-28', '2024-10-03'),
            ('1mo', '2024-09-03', '2024-10-03'),
            ('3mo', '2024-07-05', '2024-10-03'),
            ('6mo', '2024-04-06', '2024-10-03'),
            ('1y', '2023-10-04', '2024-10-03'),
            ('2y', '2022-10-04', '2024-10-03'),
            ('5y', '2019-10-05', '2024-10-03'),
        ]

        for period, expected_start, expected_end in test_cases:
            start_date, end_date = DateUtils.period_to_date_range(period, reference_date)
            assert start_date == expected_start, f"Failed for period {period}: expected start {expected_start}, got {start_date}"
            assert end_date == expected_end, f"Failed for period {period}: expected end {expected_end}, got {end_date}"

    def test_period_to_date_range_ytd(self):
        """Test year-to-date period calculation."""
        # Test YTD at different times of year
        test_cases = [
            (datetime(2024, 1, 15), '2024-01-01', '2024-01-15'),  # Early year
            (datetime(2024, 6, 15), '2024-01-01', '2024-06-15'),  # Mid year
            (datetime(2024, 12, 31), '2024-01-01', '2024-12-31'), # End of year
        ]

        for reference_date, expected_start, expected_end in test_cases:
            start_date, end_date = DateUtils.period_to_date_range('ytd', reference_date)
            assert start_date == expected_start
            assert end_date == expected_end

    def test_period_to_date_range_max_period(self):
        """Test maximum period (should be ~20 years)."""
        reference_date = datetime(2024, 10, 3)
        start_date, end_date = DateUtils.period_to_date_range('max', reference_date)

        # Should be approximately 20 years back
        start_year = int(start_date.split('-')[0])
        assert start_year <= 2004, f"Max period should go back ~20 years, got {start_year}"
        assert end_date == '2024-10-03'

    def test_period_to_date_range_default_reference_date(self):
        """Test that default reference date uses current date."""
        # Call without reference_date - should use current date
        start_date, end_date = DateUtils.period_to_date_range('1d')

        # End date should be today
        today = datetime.now().date().strftime('%Y-%m-%d')
        assert end_date == today

    def test_period_to_date_range_invalid_period(self):
        """Test error handling for invalid period strings."""
        invalid_periods = ['invalid', '2x', '', '1hour', '30d']

        for invalid_period in invalid_periods:
            with pytest.raises(ValueError, match=f"Unsupported period: {invalid_period}"):
                DateUtils.period_to_date_range(invalid_period)

    def test_validate_date_range_valid_dates(self):
        """Test date range validation with valid dates."""
        valid_ranges = [
            ('2024-01-01', '2024-01-02'),
            ('2023-12-31', '2024-01-01'),
            ('2024-06-15', '2024-10-03'),
        ]

        for start_date, end_date in valid_ranges:
            # Should not raise any exception
            DateUtils.validate_date_range(start_date, end_date)

    def test_validate_date_range_invalid_format(self):
        """Test date range validation with invalid date formats."""
        invalid_formats = [
            ('2024/01/01', '2024-01-02'),  # Wrong separator
            ('24-01-01', '2024-01-02'),    # Wrong year format
            ('2024-1-1', '2024-01-02'),    # Missing zero padding
            ('2024-13-01', '2024-01-02'),  # Invalid month
            ('2024-01-32', '2024-01-02'),  # Invalid day
            ('invalid', '2024-01-02'),     # Completely invalid
        ]

        for start_date, end_date in invalid_formats:
            with pytest.raises(ValueError, match="Invalid date format"):
                DateUtils.validate_date_range(start_date, end_date)

    def test_validate_date_range_logical_errors(self):
        """Test date range validation with logical errors."""
        logical_errors = [
            ('2024-01-02', '2024-01-01'),  # Start after end
            ('2024-01-01', '2024-01-01'),  # Start equals end
            ('2024-06-15', '2024-01-01'),  # Start way after end
        ]

        for start_date, end_date in logical_errors:
            with pytest.raises(ValueError, match="Start date .* must be before end date"):
                DateUtils.validate_date_range(start_date, end_date)

    def test_ytd_delta_calculation(self):
        """Test internal YTD delta calculation."""
        test_cases = [
            (datetime(2024, 1, 1), timedelta(days=0)),    # New Year's Day
            (datetime(2024, 1, 2), timedelta(days=1)),    # Second day
            (datetime(2024, 2, 1), timedelta(days=31)),   # February 1st
            (datetime(2024, 12, 31), timedelta(days=365)), # End of leap year
        ]

        for reference_date, expected_delta in test_cases:
            actual_delta = DateUtils._get_ytd_delta(reference_date)
            assert actual_delta == expected_delta

    def test_leap_year_handling(self):
        """Test that leap years are handled correctly."""
        # Test leap year (2024) vs non-leap year (2023)
        leap_year_ref = datetime(2024, 3, 1)  # March 1st in leap year
        normal_year_ref = datetime(2023, 3, 1)  # March 1st in normal year

        leap_ytd = DateUtils._get_ytd_delta(leap_year_ref)
        normal_ytd = DateUtils._get_ytd_delta(normal_year_ref)

        # Should be one day difference (leap day)
        assert leap_ytd.days == normal_ytd.days + 1

    def test_period_consistency(self):
        """Test that same period always produces same range for same reference date."""
        reference_date = datetime(2024, 10, 3)

        # Call multiple times - should get identical results
        for _ in range(3):
            start1, end1 = DateUtils.period_to_date_range('6mo', reference_date)
            start2, end2 = DateUtils.period_to_date_range('6mo', reference_date)

            assert start1 == start2
            assert end1 == end2
"""
Unit tests for symbol search utilities.

Tests symbol search matching and ranking including:
- Match confidence calculation (exact, prefix, fuzzy)
- Duplicate company filtering based on exchange priority
- Exchange priority ranking (US exchanges prioritized)
"""

from unittest.mock import Mock

import pytest

from src.services.market.symbol_search import (
    EXCHANGE_PRIORITY,
    calculate_match_confidence,
    should_replace_duplicate,
)

# ===== Match Confidence Calculation Tests =====


class TestCalculateMatchConfidence:
    """Test match confidence calculation for symbol search"""

    def test_exact_symbol_match(self):
        """Test exact symbol match returns highest confidence"""
        # Arrange
        query = "aapl"
        symbol = "AAPL"
        name = "Apple Inc."

        # Act
        result = calculate_match_confidence(query, symbol, name)

        # Assert
        assert result is not None
        match_type, confidence = result
        assert match_type == "exact_symbol"
        assert confidence == 1.0

    def test_exact_symbol_match_case_insensitive(self):
        """Test exact match is case-insensitive"""
        # Arrange
        test_cases = [
            ("AAPL", "aapl", "Apple Inc."),
            ("aapl", "AAPL", "Apple Inc."),
            ("AaPl", "aApL", "Apple Inc."),
        ]

        # Act & Assert
        for query, symbol, name in test_cases:
            result = calculate_match_confidence(query, symbol, name)
            assert result is not None
            match_type, confidence = result
            assert match_type == "exact_symbol"
            assert confidence == 1.0

    def test_symbol_prefix_match_short_symbol(self):
        """Test symbol prefix match with short symbol"""
        # Arrange - use query that doesn't match name
        query = "aap"
        symbol = "AAPL"
        name = "Technology Company"

        # Act
        result = calculate_match_confidence(query, symbol, name)

        # Assert
        assert result is not None
        match_type, confidence = result
        assert match_type == "symbol_prefix"
        # Confidence = 0.9 - (4 - 3) * 0.01 = 0.89
        assert confidence == pytest.approx(0.89, abs=0.01)

    def test_symbol_prefix_match_longer_symbol(self):
        """Test symbol prefix match with longer symbol gets lower confidence"""
        # Arrange
        query = "a"
        symbol = "AAPL"  # 4 chars
        name = "Apple Inc."

        # Act
        result = calculate_match_confidence(query, symbol, name)

        # Assert
        assert result is not None
        match_type, confidence = result
        assert match_type == "symbol_prefix"
        # Confidence = 0.9 - (4 - 1) * 0.01 = 0.87
        assert confidence == pytest.approx(0.87, abs=0.01)

    def test_symbol_prefix_penalty_scales_with_length(self):
        """Test that longer symbols get progressively lower confidence"""
        # Arrange
        query = "t"
        short_symbol = "TSM"  # 3 chars → penalty = (3-1)*0.01 = 0.02 → conf = 0.88
        long_symbol = "TSLA"  # 4 chars → penalty = (4-1)*0.01 = 0.03 → conf = 0.87

        # Act
        short_result = calculate_match_confidence(query, short_symbol, "Taiwan Semi")
        long_result = calculate_match_confidence(query, long_symbol, "Tesla Inc")

        # Assert
        assert short_result is not None and long_result is not None
        _, short_conf = short_result
        _, long_conf = long_result
        assert short_conf > long_conf  # Shorter symbol has higher confidence

    def test_name_prefix_match(self):
        """Test name prefix match returns fixed 0.75 confidence"""
        # Arrange
        query = "apple"
        symbol = "AAPL"
        name = "Apple Inc."

        # Act
        result = calculate_match_confidence(query, symbol, name)

        # Assert
        assert result is not None
        match_type, confidence = result
        assert match_type == "name_prefix"
        assert confidence == 0.75

    def test_name_prefix_match_case_insensitive(self):
        """Test name prefix match is case-insensitive"""
        # Arrange
        test_cases = [
            ("apple", "AAPL", "Apple Inc."),
            ("APPLE", "AAPL", "apple inc."),
            ("ApPle", "AAPL", "aPpLe InC."),
        ]

        # Act & Assert
        for query, symbol, name in test_cases:
            result = calculate_match_confidence(query, symbol, name)
            assert result is not None
            match_type, confidence = result
            assert match_type == "name_prefix"
            assert confidence == 0.75

    def test_name_prefix_longer_query(self):
        """Test name prefix match with longer query"""
        # Arrange
        query = "microsoft"
        symbol = "MSFT"
        name = "Microsoft Corporation"

        # Act
        result = calculate_match_confidence(query, symbol, name)

        # Assert
        assert result is not None
        match_type, confidence = result
        assert match_type == "name_prefix"
        assert confidence == 0.75

    def test_fuzzy_match_in_symbol(self):
        """Test fuzzy match when query is substring of symbol"""
        # Arrange
        query = "pl"  # In "AAPL" but not a prefix
        symbol = "AAPL"
        name = "Apple Inc."

        # Act
        result = calculate_match_confidence(query, symbol, name)

        # Assert
        assert result is not None
        match_type, confidence = result
        assert match_type == "fuzzy"
        assert confidence == 0.5

    def test_fuzzy_match_in_name(self):
        """Test fuzzy match when query is substring of name"""
        # Arrange
        query = "inc"  # In "Apple Inc." but not a prefix
        symbol = "AAPL"
        name = "Apple Inc."

        # Act
        result = calculate_match_confidence(query, symbol, name)

        # Assert
        assert result is not None
        match_type, confidence = result
        assert match_type == "fuzzy"
        assert confidence == 0.5

    def test_no_match_returns_none(self):
        """Test that no match returns None"""
        # Arrange
        query = "xyz"
        symbol = "AAPL"
        name = "Apple Inc."

        # Act
        result = calculate_match_confidence(query, symbol, name)

        # Assert
        assert result is None

    def test_empty_query_matches_as_prefix(self):
        """Test that empty query matches as symbol prefix"""
        # Arrange - empty string is technically a prefix of any string
        query = ""
        symbol = "AAPL"
        name = "Technology Company"

        # Act
        result = calculate_match_confidence(query, symbol, name)

        # Assert - empty string matches as prefix
        assert result is not None
        match_type, _ = result
        assert match_type == "symbol_prefix"

    def test_match_priority_exact_beats_prefix(self):
        """Test that exact symbol match has higher confidence than prefix"""
        # Arrange
        query = "tsm"
        exact_symbol = "TSM"
        prefix_symbol = "TSMC"

        # Act
        exact_result = calculate_match_confidence(query, exact_symbol, "Taiwan Semi")
        prefix_result = calculate_match_confidence(
            query, prefix_symbol, "Taiwan Semi Manuf"
        )

        # Assert
        assert exact_result is not None and prefix_result is not None
        exact_type, exact_conf = exact_result
        prefix_type, prefix_conf = prefix_result

        assert exact_type == "exact_symbol"
        assert prefix_type == "symbol_prefix"
        assert exact_conf > prefix_conf

    def test_match_priority_symbol_prefix_beats_name_prefix(self):
        """Test that symbol prefix has higher confidence than name prefix"""
        # Arrange - use query that only matches one as prefix
        query = "aap"

        # Act
        symbol_prefix = calculate_match_confidence(query, "AAPL", "Technology Co")
        name_prefix = calculate_match_confidence(query, "XYZ", "Aapex Corporation")

        # Assert
        assert symbol_prefix is not None and name_prefix is not None
        _, symbol_conf = symbol_prefix
        _, name_conf = name_prefix
        assert symbol_conf > name_conf  # 0.89 > 0.75

    def test_match_priority_name_prefix_beats_fuzzy(self):
        """Test that name prefix has higher confidence than fuzzy"""
        # Arrange
        query = "apple"

        # Act
        name_prefix = calculate_match_confidence(query, "AAPL", "Apple Inc.")
        fuzzy = calculate_match_confidence(query, "AAPL", "Technology apple company")

        # Assert
        assert name_prefix is not None and fuzzy is not None
        _, name_conf = name_prefix
        _, fuzzy_conf = fuzzy
        assert name_conf > fuzzy_conf  # 0.75 > 0.5


# ===== Duplicate Replacement Tests =====


class TestShouldReplaceDuplicate:
    """Test duplicate result replacement logic"""

    def test_higher_confidence_replaces_regardless_of_exchange(self):
        """Test that higher confidence always wins, even with worse exchange"""
        # Arrange
        existing = Mock()
        existing.confidence = 0.75
        existing.exchange = "NMS"  # Priority 1 (best US exchange)

        # Act
        should_replace = should_replace_duplicate(existing, 0.9, "FRA")  # Foreign

        # Assert
        assert should_replace is True

    def test_lower_confidence_does_not_replace(self):
        """Test that lower confidence never replaces"""
        # Arrange
        existing = Mock()
        existing.confidence = 0.9
        existing.exchange = "FRA"  # Foreign exchange

        # Act
        should_replace = should_replace_duplicate(existing, 0.75, "NMS")  # Better ex

        # Assert
        assert should_replace is False

    def test_same_confidence_better_exchange_replaces(self):
        """Test that same confidence with better exchange replaces"""
        # Arrange
        existing = Mock()
        existing.confidence = 0.75
        existing.exchange = "NYQ"  # Priority 3

        # Act
        should_replace = should_replace_duplicate(existing, 0.75, "NMS")  # Priority 1

        # Assert
        assert should_replace is True

    def test_same_confidence_worse_exchange_does_not_replace(self):
        """Test that same confidence with worse exchange doesn't replace"""
        # Arrange
        existing = Mock()
        existing.confidence = 0.75
        existing.exchange = "NMS"  # Priority 1

        # Act
        should_replace = should_replace_duplicate(existing, 0.75, "NYQ")  # Priority 3

        # Assert
        assert should_replace is False

    def test_same_confidence_same_exchange_does_not_replace(self):
        """Test that identical confidence and exchange doesn't replace"""
        # Arrange
        existing = Mock()
        existing.confidence = 0.75
        existing.exchange = "NMS"

        # Act
        should_replace = should_replace_duplicate(existing, 0.75, "NMS")

        # Assert
        assert should_replace is False

    def test_unknown_exchange_has_lowest_priority(self):
        """Test that unknown exchange (empty string) has lowest priority"""
        # Arrange
        existing_unknown = Mock()
        existing_unknown.confidence = 0.75
        existing_unknown.exchange = ""  # Unknown

        existing_known = Mock()
        existing_known.confidence = 0.75
        existing_known.exchange = "NYQ"

        # Act
        unknown_replaced_by_known = should_replace_duplicate(
            existing_unknown, 0.75, "NYQ"
        )
        known_replaced_by_unknown = should_replace_duplicate(existing_known, 0.75, "")

        # Assert
        assert unknown_replaced_by_known is True  # Known exchange beats unknown
        assert known_replaced_by_unknown is False  # Unknown doesn't beat known

    def test_foreign_exchange_not_in_priority_map(self):
        """Test that unlisted foreign exchanges get default priority 999"""
        # Arrange
        existing = Mock()
        existing.confidence = 0.75
        existing.exchange = "NMS"  # Priority 1

        # Act - Foreign exchanges like "FRA", "LON" not in map → priority 999
        should_replace = should_replace_duplicate(existing, 0.75, "FRA")

        # Assert
        assert should_replace is False  # US exchange (1) beats foreign (999)

    def test_exchange_priority_order(self):
        """Test that exchange priorities follow expected order"""
        # Assert expected priority order
        assert EXCHANGE_PRIORITY["NMS"] < EXCHANGE_PRIORITY["NAS"]  # NASDAQ variants
        assert EXCHANGE_PRIORITY["NAS"] < EXCHANGE_PRIORITY["NYQ"]  # NASDAQ < NYSE
        assert EXCHANGE_PRIORITY["NYQ"] < EXCHANGE_PRIORITY["NYE"]  # NYSE < NYSE Arca
        assert EXCHANGE_PRIORITY["NYE"] < EXCHANGE_PRIORITY[""]  # Known < Unknown

    def test_confidence_difference_matters_more_than_exchange(self):
        """Test that even small confidence difference beats exchange priority"""
        # Arrange
        existing = Mock()
        existing.confidence = 0.75
        existing.exchange = "NMS"  # Best exchange

        # Act - Slightly higher confidence with worst exchange
        should_replace = should_replace_duplicate(existing, 0.76, "")  # Unknown ex

        # Assert
        assert should_replace is True  # 0.76 > 0.75 wins despite exchange


# ===== Integration Tests =====


class TestSymbolSearchIntegration:
    """Test integration of match confidence and duplicate filtering"""

    def test_search_workflow_exact_match(self):
        """Test typical search workflow with exact match"""
        # Arrange
        query = "aapl"
        results = [
            ("AAPL", "NMS", "Apple Inc."),
            ("AAPL", "FRA", "Apple Inc."),  # Frankfurt duplicate
        ]

        # Act - Calculate confidence for each
        matches = []
        for symbol, exchange, name in results:
            result = calculate_match_confidence(query, symbol, name)
            if result:
                match_type, confidence = result
                matches.append((symbol, exchange, confidence))

        # Assert - Both have exact match confidence
        assert len(matches) == 2
        assert all(conf == 1.0 for _, _, conf in matches)

        # Act - Filter duplicates (prefer NMS over FRA)
        existing = Mock()
        existing.confidence = matches[0][2]
        existing.exchange = matches[0][1]

        should_replace = should_replace_duplicate(
            existing, matches[1][2], matches[1][1]
        )

        # Assert - NMS (priority 1) should not be replaced by FRA (priority 999)
        assert should_replace is False

    def test_search_workflow_prefix_matches_ranked(self):
        """Test that prefix matches are ranked by symbol length"""
        # Arrange
        query = "a"
        candidates = [
            ("A", "Agilent Technologies Inc."),
            ("AA", "Alcoa Corporation"),
            ("AAA", "AAA Corp"),
            ("AAPL", "Apple Inc."),
        ]

        # Act
        results = []
        for symbol, name in candidates:
            result = calculate_match_confidence(query, symbol, name)
            if result:
                match_type, confidence = result
                results.append((symbol, confidence))

        # Assert - Shorter symbols have higher confidence
        assert results[0][1] > results[1][1]  # "A" > "AA"
        assert results[1][1] > results[2][1]  # "AA" > "AAA"
        assert results[2][1] > results[3][1]  # "AAA" > "AAPL"

    def test_search_workflow_mixed_match_types(self):
        """Test ranking with mixed match types"""
        # Arrange
        query = "aap"
        candidates = [
            ("AAPL", "Technology Co"),  # Symbol prefix: 0.89
            ("AAP", "Advance Auto Parts"),  # Exact symbol: 1.0
            ("GOOG", "Alphabet Inc."),  # No match
            ("XYZ", "Aapex Corporation"),  # Name prefix: 0.75
        ]

        # Act
        results = []
        for symbol, name in candidates:
            result = calculate_match_confidence(query, symbol, name)
            if result:
                match_type, confidence = result
                results.append((symbol, match_type, confidence))

        # Assert - Should be ordered: exact > symbol_prefix > name_prefix
        exact = [r for r in results if r[1] == "exact_symbol"]
        symbol_prefix = [r for r in results if r[1] == "symbol_prefix"]
        name_prefix = [r for r in results if r[1] == "name_prefix"]

        assert len(exact) == 1 and exact[0][2] == 1.0
        assert len(symbol_prefix) == 1 and symbol_prefix[0][2] > 0.75
        assert len(name_prefix) == 1 and name_prefix[0][2] == 0.75

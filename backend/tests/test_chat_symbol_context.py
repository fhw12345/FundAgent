"""Tests for chat symbol context injection feature."""


from src.api.chat import _build_symbol_context_instruction


class TestBuildSymbolContextInstruction:
    """Test suite for _build_symbol_context_instruction helper function."""

    def test_build_symbol_context_with_valid_symbol(self):
        """Test instruction string creation with valid symbol."""
        result = _build_symbol_context_instruction("AAPL")

        assert result is not None
        assert isinstance(result, str)
        assert "AAPL" in result
        assert "[Context:" in result
        assert "User has selected symbol" in result

    def test_build_symbol_context_with_different_symbols(self):
        """Test with various stock symbols."""
        symbols = ["GOOG", "TSLA", "MSFT", "AMZN"]

        for symbol in symbols:
            result = _build_symbol_context_instruction(symbol)
            assert result is not None
            assert symbol in result
            assert f"selected symbol '{symbol}'" in result

    def test_build_symbol_context_returns_empty_with_none_symbol(self):
        """Test returns empty string when no symbol provided."""
        result = _build_symbol_context_instruction(None)
        assert result == ""

    def test_build_symbol_context_returns_empty_with_empty_string(self):
        """Test returns empty string when empty string provided."""
        result = _build_symbol_context_instruction("")
        assert result == ""

    def test_symbol_context_contains_all_instructions(self):
        """Test instruction includes all required parts."""
        result = _build_symbol_context_instruction("GOOG")

        # Check for all required instruction parts
        assert "selected symbol 'GOOG'" in result
        assert "doesn't explicitly mention" in result
        assert "prioritize their explicit choice" in result

    def test_symbol_context_instruction_starts_with_newlines(self):
        """Test the instruction starts with newlines for proper formatting."""
        result = _build_symbol_context_instruction("AAPL")

        # Should start with newlines to separate from user message
        assert result.startswith("\n\n")

    def test_symbol_context_with_lowercase_symbol(self):
        """Test that lowercase symbols are preserved as-is."""
        result = _build_symbol_context_instruction("aapl")

        assert result is not None
        assert "aapl" in result
        assert "selected symbol 'aapl'" in result

    def test_symbol_context_with_special_characters(self):
        """Test symbols with special characters (e.g., BRK.B)."""
        result = _build_symbol_context_instruction("BRK.B")

        assert result is not None
        assert "BRK.B" in result
        assert "selected symbol 'BRK.B'" in result


class TestSymbolContextIntegration:
    """Integration tests for symbol context in message flow."""

    def test_symbol_context_can_be_appended_to_user_message(self):
        """Test that symbol context instruction can be appended to user message."""
        user_message = "What's the trend?"
        symbol_instruction = _build_symbol_context_instruction("AAPL")

        enriched_message = user_message + symbol_instruction

        # Verify appending
        assert "What's the trend?" in enriched_message
        assert "AAPL" in enriched_message
        assert "[Context:" in enriched_message

    def test_multiple_symbols_sequential_usage(self):
        """Test changing symbols doesn't cause issues."""
        user_message = "Analyze this stock"
        symbols = ["AAPL", "GOOG", "TSLA"]

        for symbol in symbols:
            instruction = _build_symbol_context_instruction(symbol)
            enriched = user_message + instruction

            assert user_message in enriched
            assert symbol in enriched
            assert f"selected symbol '{symbol}'" in enriched

    def test_no_symbol_context_with_none(self):
        """Test that empty string is returned when symbol is None."""
        user_message = "Hello"
        symbol_instruction = _build_symbol_context_instruction(None)

        enriched_message = user_message + symbol_instruction

        # Verify no modification
        assert enriched_message == user_message

    def test_symbol_context_preserves_original_message(self):
        """Test that appending context doesn't modify original message."""
        original_message = "Analyze performance"
        symbol_instruction = _build_symbol_context_instruction("MSFT")

        enriched = original_message + symbol_instruction

        # Original message should be intact at the start
        assert enriched.startswith(original_message)
        assert "MSFT" in enriched
        assert len(enriched) > len(original_message)

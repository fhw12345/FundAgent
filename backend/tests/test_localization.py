"""
Unit tests for localization utilities.

Tests language code normalization, instruction templates, and tool name translations including:
- normalize_language_code with various input formats
- get_language_instruction for Chinese and English
- get_brief_language_instruction for short prompts
- get_language_name for display names
- get_tool_display_name with language fallback
- DEFAULT_LANGUAGE and LANGUAGE_NAMES constants
"""


from src.core.localization import (
    DEFAULT_LANGUAGE,
    LANGUAGE_NAMES,
    TOOL_DISPLAY_NAMES,
    get_brief_language_instruction,
    get_language_instruction,
    get_language_name,
    get_tool_display_name,
    normalize_language_code,
)

# ===== Constants Tests =====


class TestConstants:
    """Test module constants."""

    def test_default_language_is_chinese(self):
        """Test that default language is Chinese."""
        # Assert
        assert DEFAULT_LANGUAGE == "zh-CN"

    def test_language_names_contains_both_languages(self):
        """Test that LANGUAGE_NAMES contains Chinese and English."""
        # Assert
        assert "zh-CN" in LANGUAGE_NAMES
        assert "en" in LANGUAGE_NAMES
        assert LANGUAGE_NAMES["zh-CN"] == "简体中文"
        assert LANGUAGE_NAMES["en"] == "English"

    def test_tool_display_names_not_empty(self):
        """Test that TOOL_DISPLAY_NAMES is not empty."""
        # Assert
        assert len(TOOL_DISPLAY_NAMES) > 0

    def test_tool_display_names_have_both_languages(self):
        """Test that all tools have both language translations."""
        # Act & Assert
        for tool_name, translations in TOOL_DISPLAY_NAMES.items():
            assert "zh-CN" in translations, f"{tool_name} missing Chinese translation"
            assert "en" in translations, f"{tool_name} missing English translation"


# ===== normalize_language_code Tests =====


class TestNormalizeLanguageCode:
    """Test language code normalization."""

    def test_none_returns_default(self):
        """Test that None returns default language."""
        # Act
        result = normalize_language_code(None)

        # Assert
        assert result == "zh-CN"

    def test_empty_string_returns_default(self):
        """Test that empty string returns default language."""
        # Act
        result = normalize_language_code("")

        # Assert
        assert result == "zh-CN"

    def test_exact_chinese_code(self):
        """Test exact zh-CN code."""
        # Act
        result = normalize_language_code("zh-CN")

        # Assert
        assert result == "zh-CN"

    def test_exact_english_code(self):
        """Test exact en code."""
        # Act
        result = normalize_language_code("en")

        # Assert
        assert result == "en"

    def test_chinese_short_code(self):
        """Test short zh code normalizes to zh-CN."""
        # Act
        result = normalize_language_code("zh")

        # Assert
        assert result == "zh-CN"

    def test_chinese_simplified_code(self):
        """Test zh-Hans (simplified) normalizes to zh-CN."""
        # Act
        result = normalize_language_code("zh-hans")

        # Assert
        assert result == "zh-CN"

    def test_chinese_singapore_code(self):
        """Test zh-SG normalizes to zh-CN."""
        # Act
        result = normalize_language_code("zh-sg")

        # Assert
        assert result == "zh-CN"

    def test_chinese_word(self):
        """Test 'chinese' word normalizes to zh-CN."""
        # Act
        result = normalize_language_code("chinese")

        # Assert
        assert result == "zh-CN"

    def test_english_us_code(self):
        """Test en-US normalizes to en."""
        # Act
        result = normalize_language_code("en-US")

        # Assert
        assert result == "en"

    def test_english_gb_code(self):
        """Test en-GB normalizes to en."""
        # Act
        result = normalize_language_code("en-gb")

        # Assert
        assert result == "en"

    def test_english_word(self):
        """Test 'english' word normalizes to en."""
        # Act
        result = normalize_language_code("english")

        # Assert
        assert result == "en"

    def test_case_insensitive_chinese(self):
        """Test case insensitive matching for Chinese."""
        # Act & Assert
        assert normalize_language_code("ZH-CN") == "zh-CN"
        assert normalize_language_code("ZH") == "zh-CN"
        assert normalize_language_code("CHINESE") == "zh-CN"

    def test_case_insensitive_english(self):
        """Test case insensitive matching for English."""
        # Act & Assert
        assert normalize_language_code("EN") == "en"
        assert normalize_language_code("EN-US") == "en"
        assert normalize_language_code("ENGLISH") == "en"

    def test_whitespace_trimmed(self):
        """Test that whitespace is trimmed before matching."""
        # Act
        result1 = normalize_language_code("  en  ")
        result2 = normalize_language_code("\tzh-CN\n")

        # Assert
        assert result1 == "en"
        assert result2 == "zh-CN"

    def test_unknown_code_returns_default(self):
        """Test that unknown language code returns default."""
        # Act
        result = normalize_language_code("fr")

        # Assert - French not supported, defaults to Chinese
        assert result == "zh-CN"

    def test_invalid_code_returns_default(self):
        """Test that invalid code returns default."""
        # Act
        result = normalize_language_code("invalid-lang")

        # Assert
        assert result == "zh-CN"


# ===== get_language_instruction Tests =====


class TestGetLanguageInstruction:
    """Test language instruction generation."""

    def test_chinese_instruction_format(self):
        """Test Chinese instruction contains expected text."""
        # Act
        instruction = get_language_instruction("zh-CN")

        # Assert
        assert "LANGUAGE REQUIREMENT" in instruction
        assert "Simplified Chinese" in instruction
        assert "简体中文" in instruction
        assert "MUST respond" in instruction

    def test_english_instruction_format(self):
        """Test English instruction contains expected text."""
        # Act
        instruction = get_language_instruction("en")

        # Assert
        assert "LANGUAGE REQUIREMENT" in instruction
        assert "MUST respond in English" in instruction
        assert "professional financial terminology" in instruction

    def test_chinese_instruction_has_examples(self):
        """Test Chinese instruction includes examples."""
        # Act
        instruction = get_language_instruction("zh-CN")

        # Assert
        assert "P/E Ratio" in instruction or "市盈率" in instruction

    def test_english_instruction_has_clarity_note(self):
        """Test English instruction emphasizes clarity."""
        # Act
        instruction = get_language_instruction("en")

        # Assert
        assert "clear" in instruction.lower() or "professional" in instruction.lower()

    def test_chinese_instruction_multiline(self):
        """Test Chinese instruction is multiline."""
        # Act
        instruction = get_language_instruction("zh-CN")

        # Assert
        assert "\n" in instruction
        assert len(instruction.split("\n")) > 3


# ===== get_brief_language_instruction Tests =====


class TestGetBriefLanguageInstruction:
    """Test brief language instruction generation."""

    def test_chinese_brief_instruction(self):
        """Test Chinese brief instruction."""
        # Act
        instruction = get_brief_language_instruction("zh-CN")

        # Assert
        assert "IMPORTANT" in instruction
        assert "Simplified Chinese" in instruction or "简体中文" in instruction
        assert len(instruction) < 100  # Brief

    def test_english_brief_instruction(self):
        """Test English brief instruction."""
        # Act
        instruction = get_brief_language_instruction("en")

        # Assert
        assert "IMPORTANT" in instruction
        assert "English" in instruction
        assert len(instruction) < 100  # Brief

    def test_brief_shorter_than_full(self):
        """Test brief instruction is shorter than full."""
        # Act
        brief_zh = get_brief_language_instruction("zh-CN")
        full_zh = get_language_instruction("zh-CN")

        brief_en = get_brief_language_instruction("en")
        full_en = get_language_instruction("en")

        # Assert
        assert len(brief_zh) < len(full_zh)
        assert len(brief_en) < len(full_en)


# ===== get_language_name Tests =====


class TestGetLanguageName:
    """Test language display name retrieval."""

    def test_chinese_display_name(self):
        """Test Chinese display name."""
        # Act
        name = get_language_name("zh-CN")

        # Assert
        assert name == "简体中文"

    def test_english_display_name(self):
        """Test English display name."""
        # Act
        name = get_language_name("en")

        # Assert
        assert name == "English"


# ===== get_tool_display_name Tests =====


class TestGetToolDisplayName:
    """Test tool name localization."""

    def test_search_ticker_chinese(self):
        """Test search_ticker Chinese translation."""
        # Act
        name = get_tool_display_name("search_ticker", "zh-CN")

        # Assert
        assert name == "搜索股票代码"

    def test_search_ticker_english(self):
        """Test search_ticker English translation."""
        # Act
        name = get_tool_display_name("search_ticker", "en")

        # Assert
        assert name == "Search Ticker"

    def test_company_overview_chinese(self):
        """Test get_company_overview Chinese translation."""
        # Act
        name = get_tool_display_name("get_company_overview", "zh-CN")

        # Assert
        assert name == "公司概览"

    def test_company_overview_english(self):
        """Test get_company_overview English translation."""
        # Act
        name = get_tool_display_name("get_company_overview", "en")

        # Assert
        assert name == "Company Overview"

    def test_fibonacci_analysis_chinese(self):
        """Test fibonacci_analysis_tool Chinese translation."""
        # Act
        name = get_tool_display_name("fibonacci_analysis_tool", "zh-CN")

        # Assert
        assert name == "斐波那契分析"

    def test_fibonacci_analysis_english(self):
        """Test fibonacci_analysis_tool English translation."""
        # Act
        name = get_tool_display_name("fibonacci_analysis_tool", "en")

        # Assert
        assert name == "Fibonacci Analysis"

    def test_tool_default_language(self):
        """Test tool name with default language parameter."""
        # Act - No language specified, should use DEFAULT_LANGUAGE
        name = get_tool_display_name("search_ticker")

        # Assert - Should be Chinese (default)
        assert name == "搜索股票代码"

    def test_unknown_tool_english_fallback(self):
        """Test unknown tool falls back to formatted name."""
        # Act
        name = get_tool_display_name("unknown_tool_name", "en")

        # Assert - Should convert snake_case to Title Case
        assert name == "Unknown Tool Name"

    def test_unknown_tool_chinese_fallback(self):
        """Test unknown tool falls back for Chinese too."""
        # Act
        name = get_tool_display_name("unknown_tool_name", "zh-CN")

        # Assert - Should also convert snake_case to Title Case
        assert name == "Unknown Tool Name"

    def test_all_known_tools_have_translations(self):
        """Test all TOOL_DISPLAY_NAMES entries are accessible."""
        # Act & Assert
        for tool_name in TOOL_DISPLAY_NAMES.keys():
            zh_name = get_tool_display_name(tool_name, "zh-CN")
            en_name = get_tool_display_name(tool_name, "en")

            assert zh_name  # Not empty
            assert en_name  # Not empty
            assert zh_name != en_name  # Different translations

    def test_market_movers_localization(self):
        """Test get_market_movers localization."""
        # Act
        zh_name = get_tool_display_name("get_market_movers", "zh-CN")
        en_name = get_tool_display_name("get_market_movers", "en")

        # Assert
        assert zh_name == "市场动向"
        assert en_name == "Market Movers"

    def test_financial_statements_localization(self):
        """Test get_financial_statements localization."""
        # Act
        zh_name = get_tool_display_name("get_financial_statements", "zh-CN")
        en_name = get_tool_display_name("get_financial_statements", "en")

        # Assert
        assert zh_name == "财务报表"
        assert en_name == "Financial Statements"


# ===== Integration Tests =====


class TestLocalizationIntegration:
    """Test realistic localization scenarios."""

    def test_full_workflow_chinese(self):
        """Test complete workflow for Chinese language."""
        # Arrange
        raw_lang = "zh"

        # Act
        normalized = normalize_language_code(raw_lang)
        instruction = get_language_instruction(normalized)
        brief = get_brief_language_instruction(normalized)
        display_name = get_language_name(normalized)
        tool_name = get_tool_display_name("search_ticker", normalized)

        # Assert
        assert normalized == "zh-CN"
        assert "简体中文" in instruction
        assert "IMPORTANT" in brief
        assert display_name == "简体中文"
        assert tool_name == "搜索股票代码"

    def test_full_workflow_english(self):
        """Test complete workflow for English language."""
        # Arrange
        raw_lang = "en-US"

        # Act
        normalized = normalize_language_code(raw_lang)
        instruction = get_language_instruction(normalized)
        brief = get_brief_language_instruction(normalized)
        display_name = get_language_name(normalized)
        tool_name = get_tool_display_name("search_ticker", normalized)

        # Assert
        assert normalized == "en"
        assert "English" in instruction
        assert "IMPORTANT" in brief
        assert display_name == "English"
        assert tool_name == "Search Ticker"

    def test_fallback_chain_for_unknown_language(self):
        """Test fallback behavior for unsupported language."""
        # Arrange
        raw_lang = "fr-FR"  # French not supported

        # Act
        normalized = normalize_language_code(raw_lang)
        instruction = get_language_instruction(normalized)
        tool_name = get_tool_display_name("search_ticker", normalized)

        # Assert - Should fall back to Chinese (default)
        assert normalized == "zh-CN"
        assert "简体中文" in instruction
        assert tool_name == "搜索股票代码"

    def test_case_insensitive_workflow(self):
        """Test that workflow handles mixed case input."""
        # Act
        normalized1 = normalize_language_code("EN-us")
        normalized2 = normalize_language_code("ZH-cn")

        # Assert
        assert normalized1 == "en"
        assert normalized2 == "zh-CN"

    def test_whitespace_handling_workflow(self):
        """Test that workflow handles whitespace gracefully."""
        # Act
        normalized = normalize_language_code("  en  ")
        tool_name = get_tool_display_name("search_ticker", normalized)

        # Assert
        assert normalized == "en"
        assert tool_name == "Search Ticker"

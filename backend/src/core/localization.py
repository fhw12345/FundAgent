"""Minimal localization stub for FundAgent (Chinese-first)."""

from typing import Literal

SupportedLanguage = Literal["zh-CN", "en"]
DEFAULT_LANGUAGE: SupportedLanguage = "zh-CN"


def get_language_instruction(language: SupportedLanguage = DEFAULT_LANGUAGE) -> str:
    if language == "en":
        return "Please respond in English."
    return "请用中文回复。"


def get_brief_language_instruction(language: SupportedLanguage = DEFAULT_LANGUAGE) -> str:
    if language == "en":
        return "[Respond in English]"
    return "[请用中文回复]"

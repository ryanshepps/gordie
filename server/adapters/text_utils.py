"""Shared text utilities for channel output formatting."""

import re


def strip_markdown(text: str) -> str:
    result = re.sub(r"```[\s\S]*?```", "", text)
    result = re.sub(r"`([^`]+)`", r"\1", result)
    result = re.sub(r"^#{1,6}\s+", "", result, flags=re.MULTILINE)
    result = re.sub(r"\*\*(.+?)\*\*", r"\1", result)
    result = re.sub(r"\*(.+?)\*", r"\1", result)
    result = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", result)
    result = re.sub(r"!\[([^\]]*)\]\([^)]+\)", r"\1", result)
    result = re.sub(r"^[-*_]{3,}\s*$", "", result, flags=re.MULTILINE)
    result = re.sub(r"^[\s]*[-*+]\s+", "- ", result, flags=re.MULTILINE)
    result = re.sub(r"\n{3,}", "\n\n", result)
    return result.strip()

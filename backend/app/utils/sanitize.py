"""
Input sanitization utilities.
Strips dangerous characters without altering classification-relevant content.
"""
from __future__ import annotations
import re
import unicodedata


_NULL_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_PATH_TRAVERSAL = re.compile(r"[/\\:*?\"<>|]")


def sanitize_text(text: str, max_length: int = 50_000) -> str:
    """
    Strip null bytes and non-printing control characters.
    Preserve newlines (\n), tabs (\t), and carriage returns (\r) as they
    are relevant to line-level classification.
    Normalize to NFC Unicode form.
    """
    text = _NULL_CONTROL.sub("", text)
    text = unicodedata.normalize("NFC", text)
    return text[:max_length]


def sanitize_filename(name: str, max_length: int = 255) -> str:
    """
    Strip path-traversal characters and limit length.
    Returns a safe filename string.
    """
    if not name:
        return "unnamed"
    name = _PATH_TRAVERSAL.sub("_", name)
    name = name.strip(". ")
    return name[:max_length] or "unnamed"

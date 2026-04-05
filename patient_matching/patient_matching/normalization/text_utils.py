"""Shared text normalization utilities.

Implements requirements A.1-A.4:
  - Case insensitive (lowercase)
  - Whitespace removal
  - Punctuation removal
  - Diacritic folding
"""

from __future__ import annotations

import re

from text_unidecode import unidecode  # type: ignore[import-untyped]

_PUNCTUATION_RE = re.compile(r"[^\w\s]", re.UNICODE)
_WHITESPACE_RE = re.compile(r"\s+")


def fold_diacritics(text: str) -> str:
    """Fold diacritics/accented characters to ASCII equivalents.

    Uses text-unidecode for broad Unicode-to-ASCII transliteration,
    which handles accents, ligatures, and non-Latin scripts.
    """
    result: str = unidecode(text)
    return result


def normalize_text(text: str, *, preserve_spaces: bool = False) -> str:
    """Apply full text normalization: lowercase, diacritic fold,
    punctuation removal, and whitespace handling.

    Args:
        text: The input string.
        preserve_spaces: If True, collapse multiple spaces to one space
            instead of removing all whitespace. Used for address fields
            where space is meaningful.

    Returns:
        The normalized string.
    """
    result = text.lower()
    result = fold_diacritics(result)
    result = _PUNCTUATION_RE.sub("", result)

    if preserve_spaces:
        result = _WHITESPACE_RE.sub(" ", result).strip()
    else:
        result = _WHITESPACE_RE.sub("", result)

    return result

"""Drop empty strings from a FHIR-shaped dict, for the helix comparison scripts.

FHIR's `string` type needs at least one non-whitespace character, but a few ONC-derived
records have an empty city, state or given value. Shared by `z_scripts/compare_engines.py`
and `evaluation/legacy_comparison.py`; use it only as a fallback when strict parsing fails.
"""

from __future__ import annotations

from typing import Any


def is_empty_str(value: Any) -> bool:
    """True for a string that is empty or only whitespace."""
    return isinstance(value, str) and value.strip() == ""


def strip_empty_strings(obj: Any) -> Any:
    """Return a copy of `obj` with empty/whitespace-only strings dropped at every depth.

    Dict entries and list items that are blank strings are removed; everything else is kept.
    """
    if isinstance(obj, dict):
        return {
            k: strip_empty_strings(v) for k, v in obj.items() if not is_empty_str(v)
        }
    if isinstance(obj, list):
        cleaned = [strip_empty_strings(v) for v in obj]
        return [v for v in cleaned if not is_empty_str(v)]
    return obj

"""No-op `MatchingBackend` shared by tests that only need `evaluate_pair()`
(a pure pairwise decision) and never touch backend search.

Not itself a test module - `test_*.py` files import from here.
"""

from __future__ import annotations

from typing import Any, Dict, List

from patient_matching.matching.backend import FieldCriterion, MatchingBackend


class NullBackend(MatchingBackend):
    """No-op backend - `MatchingEngine.evaluate_pair()` never calls it, but the
    engine's constructor requires a backend instance."""

    def search(self, criteria: List[FieldCriterion]) -> List[Dict[str, Any]]:
        return []

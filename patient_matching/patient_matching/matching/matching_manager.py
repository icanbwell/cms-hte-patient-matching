"""High-level manager for CMS Patient Matching.

Provides a single entry point that accepts a normalized FHIR Patient
resource and a backend, evaluates all 26 Table 2 rules, and returns
the matching result.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from .backend import MatchingBackend
from .field_comparator import FieldComparator
from .field_extractor import FieldExtractor
from .match_result import MatchResult
from .matching_engine import MatchingEngine
from .table2_rules import APPROVED_RULES, MatchingRule

logger = logging.getLogger(__name__)


class MatchingManager:
    """Manages CMS Patient Matching using Table 2 approved combinations.

    Wraps the MatchingEngine and its dependencies, exposing a simple
    ``match()`` method.

    Args:
        backend: The data-access backend for candidate retrieval.
        rules: Subset of Table 2 rules to evaluate. Defaults to all 26.

    Example::

        manager = MatchingManager(backend=my_backend)
        result = manager.match(normalized_patient)
        if result.outcome == MatchOutcome.MATCH:
            print(result.matched_patients)
    """

    def __init__(
        self,
        *,
        backend: MatchingBackend,
        rules: Optional[tuple[MatchingRule, ...]] = None,
    ) -> None:
        self._backend = backend
        self._extractor = FieldExtractor()
        self._comparator = FieldComparator()
        self._rules = rules or APPROVED_RULES

        self._engine = MatchingEngine(
            backend=self._backend,
            extractor=self._extractor,
            comparator=self._comparator,
            rules=self._rules,
        )

    def match(self, query_patient: Dict[str, Any]) -> MatchResult:
        """Match a normalized FHIR Patient against the backend.

        Args:
            query_patient: A normalized FHIR R4 Patient resource dict.

        Returns:
            A MatchResult with outcome, matched patients, and audit data.
        """
        return self._engine.match(query_patient)

    def match_batch(self, query_patients: List[Dict[str, Any]]) -> List[MatchResult]:
        """Match a list of normalized FHIR Patients against the backend.

        Args:
            query_patients: A list of normalized FHIR R4 Patient dicts.

        Returns:
            A list of MatchResults in the same order.
        """
        return [self._engine.match(p) for p in query_patients]

    @property
    def rule_count(self) -> int:
        """Number of Table 2 rules being evaluated."""
        return len(self._rules)

    @property
    def rules(self) -> tuple[MatchingRule, ...]:
        """The Table 2 rules being evaluated."""
        return self._rules

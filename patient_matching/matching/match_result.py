"""Result types for patient matching operations.

Captures audit-required fields per Section VII of the CMS proposal:
rule ID, match type (exact/fuzzy), uniqueness result, per-field
comparison outcomes, evaluation timestamp, and software version.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class MatchOutcome(Enum):
    """Outcome of a matching operation."""

    MATCH = "match"
    NO_MATCH = "no_match"
    AMBIGUOUS = "ambiguous"
    INSUFFICIENT_FIELDS = "insufficient_fields"


@dataclass
class RuleEvaluation:
    """Result of evaluating a single Table 2 rule against a candidate.

    Attributes:
        rule_id: The Table 2 rule identifier (e.g. "01").
        matched: Whether the rule was satisfied.
        match_type: "exact" or "fuzzy".
        fuzzy_fields: Which fields (if any) were matched via fuzzy.
        negated_by_suffix: Whether a suffix conflict negated the match.
        field_outcomes: Per-field comparison results for audit.
        timestamp: ISO 8601 UTC timestamp of when this evaluation ran.
        version: The patient_matching package version that produced this
            evaluation, from VERSION.
    """

    rule_id: str = ""
    matched: bool = False
    match_type: str = "exact"
    fuzzy_fields: List[str] = field(default_factory=list)
    negated_by_suffix: bool = False
    field_outcomes: Dict[str, str] = field(default_factory=dict)
    timestamp: str = ""
    version: str = ""


@dataclass
class MatchResult:
    """Result of a full matching operation against a query patient.

    Attributes:
        outcome: Overall outcome of the match attempt.
        matched_patients: FHIR Patient dicts that matched (0 or 1 for
            MATCH, 0 for NO_MATCH, 2+ for AMBIGUOUS).
        matched_rule_id: The Table 2 rule that produced the match.
        match_type: "exact" or "fuzzy".
        is_unique: Whether the match produced exactly one candidate.
        rule_evaluations: Detailed per-rule evaluation results for audit.
        candidate_count: Total number of candidates evaluated.
    """

    outcome: MatchOutcome = MatchOutcome.NO_MATCH
    matched_patients: List[Dict[str, Any]] = field(default_factory=list)
    matched_rule_id: Optional[str] = None
    match_type: str = "exact"
    is_unique: bool = False
    rule_evaluations: List[RuleEvaluation] = field(default_factory=list)
    candidate_count: int = 0

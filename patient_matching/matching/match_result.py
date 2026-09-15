"""Result types for patient matching operations.

Captures audit-required fields per Section VII of the CMS proposal:
rule ID, match type (exact/fuzzy), uniqueness result, per-field
comparison outcomes, evaluation timestamp, and software version.

**`rule_id` is not a stable identifier across package versions.** CMS spec
revisions can and do renumber Table 2 (e.g. session 16's v3.4.0 migration
reassigned most Category 1 rule_ids to a different combination than they
meant before). Any audit tooling comparing or aggregating records across a
version boundary must key on `(rule_id, version)` together, never `rule_id`
alone - the same `rule_id` string can mean a different field combination
before and after a spec-driven renumbering.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class MatchOutcome(Enum):
    """Outcome of a matching operation.

    Tiered per CMS v3.3 step 6's uniqueness response: exactly 1 candidate
    is a MATCH, exactly 2 candidates ESCALATE (may go to MFA/disambiguation),
    and 3+ candidates are AMBIGUOUS (must clear a stricter 1e-6 collision
    threshold or the responder declines).
    """

    MATCH = "match"
    NO_MATCH = "no_match"
    ESCALATE = "escalate"  # exactly 2 candidates; may escalate to MFA/disambiguation
    AMBIGUOUS = "ambiguous"  # 3+ candidates; stricter 1e-6 threshold applies
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
            MATCH, 0 for NO_MATCH, 2 for ESCALATE, 3+ for AMBIGUOUS).
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

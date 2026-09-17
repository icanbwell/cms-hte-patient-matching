"""Result types for patient matching operations.

Captures the SS VII per-query audit record (session 18, CMS v3.4.0): query
initiator, Table 2 combination evaluated, match type (exact/fuzzy),
identifiers of records matched, uniqueness-check result, final match
determination, and timestamp. This satisfies **Path A** (rules-engine
integrity - did the engine apply Table 2 correctly), which is what a
per-query record can show. **Path B** (outcomes/performance: match/
no-candidate/ambiguous rate, correction rate, appeal rate, trend over time)
is population-level statistics computed *over* many per-query records, not
a per-query field - this repo has no reporting/analytics layer to compute
or store them (out of scope, see docs/sessions/in_review/session_18.md).

Field mapping: "Table 2 combination evaluated" -> MatchResult.matched_rule_id
/ RuleEvaluation.rule_id; "match type" -> match_type; "identifiers of
records matched" -> RuleEvaluation.field_outcomes (keyed by canonical field
name - SSN/ITIN/Legal ID/MBI/Namespace ID/Member ID/Subscriber ID are all
literally identifiers in the HL7 sense, and field_outcomes already records
which ones were compared and how); "uniqueness-check result" ->
MatchResult.is_unique/outcome; "final match determination" ->
MatchResult.outcome; "timestamp" -> MatchResult.timestamp (query-level,
always populated - RuleEvaluation.timestamp is separately preserved for the
existing per-rule audit trail, but a query can produce zero rule
evaluations, e.g. an empty query patient, so a query-level timestamp is
needed for the record to be complete even then).

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
        field_outcomes: Per-field comparison results for audit - satisfies
            SS VII's "identifiers of records matched" (session 18): keys are
            canonical field names, several of which are literally
            identifiers in the HL7 sense (ssn_last4, itin_last4, legal_id,
            mbi, namespace_id, insurance_member_id, insurance_subscriber_id).
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
        query_initiator: SS VII audit field (session 18) - an opaque,
            caller-supplied identifier for whoever/whatever issued this
            query (e.g. a calling service's name or client ID). This
            library does not validate, derive, or require it - a caller
            that doesn't supply one leaves it None. Deliberately not
            derived from an IAL2 token's issuer/CSP claim: that identifies
            who verified the patient's identity, not who is asking for a
            match, and conflating the two would misattribute the audit
            record (decided with the project lead, 2026-09-15).
        timestamp: SS VII audit field (session 18) - ISO 8601 UTC
            timestamp for this query, always populated even when
            `rule_evaluations` is empty (e.g. an empty query patient
            matches no rules at all, so no per-rule timestamp exists).
    """

    outcome: MatchOutcome = MatchOutcome.NO_MATCH
    matched_patients: List[Dict[str, Any]] = field(default_factory=list)
    matched_rule_id: Optional[str] = None
    match_type: str = "exact"
    is_unique: bool = False
    rule_evaluations: List[RuleEvaluation] = field(default_factory=list)
    candidate_count: int = 0
    query_initiator: Optional[str] = None
    timestamp: str = ""

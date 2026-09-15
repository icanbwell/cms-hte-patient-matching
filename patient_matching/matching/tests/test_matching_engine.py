"""Tests for MatchingEngine."""

from datetime import datetime
from typing import Any, Dict, List, Optional

import pytest

from patient_matching.matching.backend import (
    FieldCriterion,
    MatchingBackend,
)
from patient_matching.matching.match_result import MatchOutcome
from patient_matching.matching.matching_engine import MatchingEngine
from patient_matching.matching.household_rules import (
    CATEGORY_2_RULES,
    HouseholdIndividualRule,
)
from patient_matching.matching.table2_rules import (
    APPROVED_RULES,
    MatchingRule,
)


# ── helpers ──────────────────────────────────────────────────────────


def _rule_by_id(rule_id: str) -> MatchingRule:
    """Look up a rule by ID rather than a fragile positional index - rule
    order/count shifted when session 6 amended rules 13-16 into Category 2
    and inserted new rules 27-33/36."""
    return next(r for r in APPROVED_RULES if r.rule_id == rule_id)


def _category2_rule_by_id(rule_id: str) -> HouseholdIndividualRule:
    return next(r for r in CATEGORY_2_RULES if r.rule_id == rule_id)


def _make_patient(
    *,
    first: str = "john",
    last: str = "smith",
    dob: str = "1990-01-15",
    phone: Optional[str] = "+12125551234",
    email: Optional[str] = "john@gmail.com",
    ssn_last4: Optional[str] = "6789",
    itin_last4: Optional[str] = None,
    street: Optional[str] = "123 main st",
    zip_code: Optional[str] = None,
    suffix: Optional[str] = None,
    mbi: Optional[str] = None,
    legal_id: Optional[str] = None,
    namespace_id: Optional[str] = None,
    insurance_subscriber_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Build a minimal normalized FHIR Patient dict."""
    address: Dict[str, Any] = {}
    if street:
        address["line"] = [street]
    if zip_code:
        address["postalCode"] = zip_code
    patient: Dict[str, Any] = {
        "resourceType": "Patient",
        "name": [
            {
                "family": last,
                "given": [first],
            }
        ],
        "birthDate": dob,
        "telecom": [],
        "address": [address] if address else [],
        "identifier": [],
    }
    if itin_last4:
        patient["identifier"].append(
            {
                "system": "urn:oid:2.16.840.1.113883.4.4",
                "value": f"xxx-xx-{itin_last4}",
            }
        )
    if insurance_subscriber_id:
        patient["identifier"].append(
            {
                "system": "https://payer.example/subscriber-id",
                "type": {"coding": [{"code": "SN"}]},
                "value": insurance_subscriber_id,
            }
        )
    if suffix:
        patient["name"][0]["suffix"] = [suffix]
    if phone:
        patient["telecom"].append({"system": "phone", "value": phone})
    if email:
        patient["telecom"].append({"system": "email", "value": email})
    if ssn_last4:
        patient["identifier"].append(
            {
                "system": "http://hl7.org/fhir/sid/us-ssn",
                "value": f"xxx-xx-{ssn_last4}",
            }
        )
    if mbi:
        patient["identifier"].append(
            {"system": "http://hl7.org/fhir/sid/us-mbi", "value": mbi}
        )
    if legal_id:
        patient["identifier"].append(
            {
                "type": {"coding": [{"code": "DL"}]},
                "value": legal_id,
                "assigner": {"display": "CA-DMV"},
            }
        )
    if namespace_id:
        patient["identifier"].append(
            {
                "system": "urn:hospital:abc",
                "type": {"coding": [{"code": "MR"}]},
                "value": namespace_id,
            }
        )
    return patient


class InMemoryBackend(MatchingBackend):
    """Simple in-memory backend that returns all stored patients."""

    def __init__(self, patients: List[Dict[str, Any]]):
        self._patients = patients

    async def search(self, criteria: List[FieldCriterion]) -> List[Dict[str, Any]]:
        return list(self._patients)


class EmptyBackend(MatchingBackend):
    """Backend that always returns no candidates."""

    async def search(self, criteria: List[FieldCriterion]) -> List[Dict[str, Any]]:
        return []


# ── tests ────────────────────────────────────────────────────────────


class TestMatchingEngineExactMatch:
    async def test_exact_match_single_candidate(self) -> None:
        candidate = _make_patient()
        query = _make_patient()
        engine = MatchingEngine(backend=InMemoryBackend([candidate]))
        result = await engine.match(query)
        assert result.outcome == MatchOutcome.MATCH
        assert result.is_unique is True
        assert len(result.matched_patients) == 1

    async def test_no_match_different_names(self) -> None:
        candidate = _make_patient(first="alice", last="jones")
        query = _make_patient(first="john", last="smith")
        engine = MatchingEngine(backend=InMemoryBackend([candidate]))
        result = await engine.match(query)
        assert result.outcome == MatchOutcome.NO_MATCH

    async def test_no_candidates_from_backend(self) -> None:
        query = _make_patient()
        engine = MatchingEngine(backend=EmptyBackend())
        result = await engine.match(query)
        assert result.outcome == MatchOutcome.NO_MATCH


class TestMatchingEngineAmbiguous:
    async def test_escalate_two_candidates(self) -> None:
        c1 = _make_patient()
        c2 = _make_patient(phone="+12125559999")
        query = _make_patient()
        engine = MatchingEngine(backend=InMemoryBackend([c1, c2]))
        result = await engine.match(query)
        assert result.outcome == MatchOutcome.ESCALATE
        assert result.is_unique is False
        assert result.candidate_count == 2


class TestTieredUniquenessResponse:
    """Boundary behavior across 1 / 2 / 3+ matched candidates (CMS v3.3 step 6)."""

    @pytest.mark.parametrize(
        "n_candidates,expected_outcome,expected_unique",
        [
            (1, MatchOutcome.MATCH, True),
            (2, MatchOutcome.ESCALATE, False),
            (3, MatchOutcome.AMBIGUOUS, False),
            (5, MatchOutcome.AMBIGUOUS, False),
        ],
    )
    async def test_outcome_by_candidate_count(
        self, n_candidates: int, expected_outcome: MatchOutcome, expected_unique: bool
    ) -> None:
        # Rule 08 (First Name + DOB + MBI, all exact) with a distinct MBI per
        # candidate is enough to make each candidate unique while still
        # matching the query on first name + DOB.
        candidates = [
            _make_patient(first="john", dob="1990-01-15", mbi=f"1mbi{i:03d}mbi1")
            for i in range(n_candidates)
        ]
        for i, c in enumerate(candidates):
            c["id"] = f"patient-{i}"
        backend = InMemoryBackend(candidates)
        engine = MatchingEngine(backend=backend)
        query = _make_patient(
            first="john", dob="1990-01-15", mbi=candidates[0]["identifier"][-1]["value"]
        )

        result = await engine.match(query)

        assert result.outcome == expected_outcome
        assert result.is_unique == expected_unique
        assert result.candidate_count == n_candidates


class TestMatchingEngineFuzzyMatch:
    async def test_fuzzy_match_last_name(self) -> None:
        """Last name 'smtih' (transposition) should fuzzy-match 'smith'."""
        candidate = _make_patient(last="smtih")
        query = _make_patient(last="smith")
        engine = MatchingEngine(backend=InMemoryBackend([candidate]))
        result = await engine.match(query)
        assert result.outcome == MatchOutcome.MATCH
        assert result.match_type == "fuzzy"

    async def test_fuzzy_match_short_string_rejected(self) -> None:
        """Short first name 'jon' vs 'john' — should NOT fuzzy match."""
        candidate = _make_patient(first="jon", last="jones", dob="2000-01-01")
        query = _make_patient(first="john", last="jones", dob="2000-01-01")
        # Rule 02: First Name + Last Name* + DOB + Phone
        # first_name is EXACT in rule 02, so 'jon' vs 'john' fails.
        # Rule 04: First Name* + Last Name + DOB + SSN Last 4
        # first_name* is fuzzy eligible but 'jon'/'john' are < 5 chars.
        engine = MatchingEngine(backend=InMemoryBackend([candidate]))
        result = await engine.match(query)
        # Should still match on rules that don't require first_name match
        # (e.g. rule 13: Last Name + Phone + SSN Last 4)
        # but first_name fuzzy should not work for short strings
        has_fuzzy_first = any(
            "first_name" in ev.fuzzy_fields
            for ev in result.rule_evaluations
            if ev.matched
        )
        assert has_fuzzy_first is False


class TestMatchingEngineSuffixConflict:
    async def test_suffix_conflict_negates_match(self) -> None:
        """B.5: Different suffixes should negate the match."""
        candidate = _make_patient(suffix="jr")
        query = _make_patient(suffix="sr")
        engine = MatchingEngine(backend=InMemoryBackend([candidate]))
        result = await engine.match(query)
        assert result.outcome == MatchOutcome.NO_MATCH
        negated = [ev for ev in result.rule_evaluations if ev.negated_by_suffix]
        assert len(negated) > 0

    async def test_same_suffix_no_conflict(self) -> None:
        candidate = _make_patient(suffix="jr")
        query = _make_patient(suffix="jr")
        engine = MatchingEngine(backend=InMemoryBackend([candidate]))
        result = await engine.match(query)
        assert result.outcome == MatchOutcome.MATCH

    async def test_no_suffix_no_conflict(self) -> None:
        candidate = _make_patient()
        query = _make_patient(suffix="jr")
        engine = MatchingEngine(backend=InMemoryBackend([candidate]))
        result = await engine.match(query)
        assert result.outcome == MatchOutcome.MATCH


class TestMatchingEngineRuleSubset:
    async def test_custom_rule_subset(self) -> None:
        """Engine should respect a custom subset of rules."""
        single_rule = (_rule_by_id("22"),)  # Rule 22: namespace_id
        candidate = _make_patient(namespace_id="MRN001")
        query = _make_patient(namespace_id="MRN001")
        engine = MatchingEngine(
            backend=InMemoryBackend([candidate]),
            rules=single_rule,
            household_individual_rules=(),
        )
        result = await engine.match(query)
        assert result.outcome == MatchOutcome.MATCH
        assert result.matched_rule_id == "22"

    async def test_rule_skipped_when_query_missing_fields(self) -> None:
        """Rule should be skipped if query lacks required fields."""
        single_rule = (_rule_by_id("08"),)  # Rule 08: First Name + DOB + MBI
        query = _make_patient(mbi=None)  # No MBI
        candidate = _make_patient(mbi="1EG4TE5MK73")
        engine = MatchingEngine(
            backend=InMemoryBackend([candidate]),
            rules=single_rule,
            household_individual_rules=(),
        )
        result = await engine.match(query)
        assert result.outcome == MatchOutcome.NO_MATCH


class TestMatchingEngineRuleEvaluations:
    async def test_evaluations_are_recorded(self) -> None:
        candidate = _make_patient()
        query = _make_patient()
        engine = MatchingEngine(backend=InMemoryBackend([candidate]))
        result = await engine.match(query)
        assert len(result.rule_evaluations) > 0

    async def test_evaluation_field_outcomes(self) -> None:
        """Rule 22 eval should have namespace_id as exact."""
        single_rule = (_rule_by_id("22"),)
        candidate = _make_patient(namespace_id="MRN001")
        query = _make_patient(namespace_id="MRN001")
        engine = MatchingEngine(
            backend=InMemoryBackend([candidate]),
            rules=single_rule,
            household_individual_rules=(),
        )
        result = await engine.match(query)
        evals = [e for e in result.rule_evaluations if e.rule_id == "22"]
        assert len(evals) == 1
        assert evals[0].field_outcomes.get("namespace_id") == "exact"


class TestAuditFields:
    """RuleEvaluation.timestamp/.version are populated per CMS Section VII."""

    async def test_timestamp_is_iso8601_utc(self) -> None:
        candidate = _make_patient()
        engine = MatchingEngine(backend=InMemoryBackend([candidate]))
        result = await engine.match(_make_patient())
        assert result.rule_evaluations, "expected at least one rule evaluation"
        for ev in result.rule_evaluations:
            parsed = datetime.fromisoformat(ev.timestamp)
            assert parsed.tzinfo is not None

    async def test_version_is_nonempty_string(self) -> None:
        candidate = _make_patient()
        engine = MatchingEngine(backend=InMemoryBackend([candidate]))
        result = await engine.match(_make_patient())
        assert result.rule_evaluations
        for ev in result.rule_evaluations:
            assert isinstance(ev.version, str) and ev.version != ""

    def test_version_matches_repo_version_file(self) -> None:
        from patient_matching.matching.matching_engine import _PACKAGE_VERSION

        repo_version = open("VERSION").read().strip()
        assert _PACKAGE_VERSION == repo_version


class TestHouseholdIndividualRules:
    """CMS v3.3.1 two-step (Category 2) rules 13/34/38, engine-level.

    Each test isolates household_individual_rules to exactly the rule under
    test - _make_patient's shared defaults (same phone/street/email across
    patients unless overridden) mean leaving all 8 rules active would let
    an unrelated rule (e.g. 37's Phone+Street) independently resolve a
    match, masking what the rule under test actually did.
    """

    async def test_household_member_with_different_individual_fields_does_not_match(
        self,
    ) -> None:
        """Rule 13: SSN Last 4 + Phone (household) + First Name/DOB
        (individual). A household member sharing SSN-last-4 and phone but
        with different First Name/DOB must not resolve."""
        rule_13 = _category2_rule_by_id("C2-13")
        household_member = _make_patient(
            first="jane", last="smith", dob="1988-05-01", ssn_last4="6789"
        )
        query = _make_patient(
            first="john", last="smith", dob="1990-01-15", ssn_last4="6789"
        )
        engine = MatchingEngine(
            backend=InMemoryBackend([household_member]),
            rules=(),
            household_individual_rules=(rule_13,),
        )
        result = await engine.match(query)
        assert result.outcome == MatchOutcome.NO_MATCH

    async def test_correct_household_member_resolves_among_several(self) -> None:
        """Household step can legitimately surface multiple candidates
        (household members sharing SSN+phone); individual step must narrow
        to only the one whose First Name/DOB also match."""
        rule_13 = _category2_rule_by_id("C2-13")
        the_person = _make_patient(
            first="john", last="smith", dob="1990-01-15", ssn_last4="6789"
        )
        household_member = _make_patient(
            first="jane", last="smith", dob="1988-05-01", ssn_last4="6789"
        )
        query = _make_patient(
            first="john", last="smith", dob="1990-01-15", ssn_last4="6789"
        )
        engine = MatchingEngine(
            backend=InMemoryBackend([the_person, household_member]),
            rules=(),
            household_individual_rules=(rule_13,),
        )
        result = await engine.match(query)
        assert result.outcome == MatchOutcome.MATCH
        assert result.matched_rule_id == "C2-13"
        assert result.matched_patients == [the_person]

    async def test_no_household_match_declines(self) -> None:
        """Zero household-tier matches (different SSN last 4) -> no match,
        even though First Name/DOB (individual-tier) agree."""
        rule_13 = _category2_rule_by_id("C2-13")
        candidate = _make_patient(ssn_last4="0000")
        query = _make_patient(ssn_last4="6789")
        engine = MatchingEngine(
            backend=InMemoryBackend([candidate]),
            rules=(),
            household_individual_rules=(rule_13,),
        )
        result = await engine.match(query)
        assert result.outcome == MatchOutcome.NO_MATCH

    async def test_last_name_difference_does_not_block_amended_rules(self) -> None:
        """v3.3.1: Last Name is non-blocking corroboration for rules 13-16 -
        a household+individual match must succeed even when Last Name
        differs (the exact blended-family case these rules exist to fix)."""
        rule_13 = _category2_rule_by_id("C2-13")
        candidate = _make_patient(
            first="john", last="jones", dob="1990-01-15", ssn_last4="6789"
        )
        query = _make_patient(
            first="john", last="smith", dob="1990-01-15", ssn_last4="6789"
        )
        engine = MatchingEngine(
            backend=InMemoryBackend([candidate]),
            rules=(),
            household_individual_rules=(rule_13,),
        )
        result = await engine.match(query)
        assert result.outcome == MatchOutcome.MATCH
        assert result.matched_rule_id == "C2-13"

    async def test_rule_38_subscriber_id_household(self) -> None:
        rule_38 = _category2_rule_by_id("C2-38")
        candidate = _make_patient(
            first="john",
            last="smith",
            dob="1990-01-15",
            ssn_last4=None,
            insurance_subscriber_id="W900123456",
        )
        query = _make_patient(
            first="john",
            last="smith",
            dob="1990-01-15",
            ssn_last4=None,
            insurance_subscriber_id="W900123456",
        )
        engine = MatchingEngine(
            backend=InMemoryBackend([candidate]),
            rules=(),
            household_individual_rules=(rule_38,),
        )
        result = await engine.match(query)
        assert result.outcome == MatchOutcome.MATCH
        assert result.matched_rule_id == "C2-38"

    async def test_household_individual_rules_can_be_disabled(self) -> None:
        candidate = _make_patient(ssn_last4="6789")
        query = _make_patient(ssn_last4="6789")
        engine = MatchingEngine(
            backend=InMemoryBackend([candidate]),
            rules=(),  # flat rules also disabled so only rules=() is under test
            household_individual_rules=(),
        )
        result = await engine.match(query)
        assert result.outcome == MatchOutcome.NO_MATCH

    async def test_rules_param_does_not_disable_category_2_default(self) -> None:
        """Passing a restrictive `rules` subset must not silently also
        restrict household_individual_rules - they're independent per
        MatchingEngine's constructor contract."""
        rule_08 = _rule_by_id("08")  # First Name + DOB + MBI - unrelated
        candidate = _make_patient(ssn_last4="6789")
        query = _make_patient(ssn_last4="6789")
        engine = MatchingEngine(
            backend=InMemoryBackend([candidate]),
            rules=(rule_08,),
        )
        result = await engine.match(query)
        # rule_08 can't match (no MBI on either patient), but the default
        # CATEGORY_2_RULES should still resolve rule 13 (SSN+Phone
        # household, First Name/DOB individual - both share defaults).
        assert result.outcome == MatchOutcome.MATCH
        assert result.matched_rule_id == "C2-13"


class TestDobFuzzyDispatch:
    """Rule 28: Last Name* + DOB* (+/-1 day) + Member ID."""

    def _make_member_id_patient(
        self, *, first: str, last: str, dob: str, member_id: str
    ) -> Dict[str, Any]:
        return {
            "resourceType": "Patient",
            "name": [{"family": last, "given": [first]}],
            "birthDate": dob,
            "telecom": [],
            "address": [],
            "identifier": [
                {
                    "system": "https://payer.example/member-id",
                    "type": {"coding": [{"code": "MB"}]},
                    "value": member_id,
                }
            ],
        }

    async def test_dob_within_one_day_and_last_name_fuzzy_both_match_simultaneously(
        self,
    ) -> None:
        """DOB fuzzy-eligibility must not consume max_fuzzy_fields - both
        Last Name (Damerau-Levenshtein) and DOB (+/-1 day) going fuzzy at
        once must not trigger 'fuzzy_exceeded' for either."""
        rule_24 = _rule_by_id("24")
        candidate = self._make_member_id_patient(
            first="john", last="smyth", dob="1990-01-16", member_id="M1"
        )
        query = self._make_member_id_patient(
            first="john", last="smith", dob="1990-01-15", member_id="M1"
        )
        engine = MatchingEngine(
            backend=InMemoryBackend([candidate]),
            rules=(rule_24,),
            household_individual_rules=(),
        )
        result = await engine.match(query)
        assert result.outcome == MatchOutcome.MATCH
        evaluation = next(
            e for e in result.rule_evaluations if e.rule_id == "24" and e.matched
        )
        assert evaluation.field_outcomes["last_name"] == "fuzzy"
        assert evaluation.field_outcomes["dob"] == "fuzzy"

    async def test_dob_two_days_off_does_not_match(self) -> None:
        rule_24 = _rule_by_id("24")
        candidate = self._make_member_id_patient(
            first="john", last="smith", dob="1990-01-17", member_id="M1"
        )
        query = self._make_member_id_patient(
            first="john", last="smith", dob="1990-01-15", member_id="M1"
        )
        engine = MatchingEngine(
            backend=InMemoryBackend([candidate]),
            rules=(rule_24,),
            household_individual_rules=(),
        )
        result = await engine.match(query)
        assert result.outcome == MatchOutcome.NO_MATCH


class TestDobFuzzyExtendedToNewRules:
    """v3.4.0 extends DOB +/-1 day fuzzy from rule 24 alone to rules 01, 02,
    03, and 10 (session 16). End-to-end coverage via MatchingEngine.match()
    that each rule's DOB dispatch actually works - the static
    FieldComparator.dob_fuzzy_match unit tests and the p_collision figure
    check (session_16.md's Execution notes) only prove the comparator and
    the collision-probability math are correct, not that each rule is
    actually wired to use it."""

    _RULE_ANCHOR_FIELDS = [
        ("01", {"street": "123 main st"}),  # First*+Last*+DOB*+Street Line*
        ("02", {"phone": "+12125551234"}),  # First+Last*+DOB*+Phone
        ("03", {"email": "john@gmail.com"}),  # First*+Last*+DOB*+Email
        ("10", {"legal_id": "DL123456"}),  # Last*+DOB*+Legal ID (no First Name field)
    ]

    @pytest.mark.parametrize("rule_id,anchor_kwargs", _RULE_ANCHOR_FIELDS)
    async def test_dob_one_day_off_matches(
        self, rule_id: str, anchor_kwargs: Dict[str, Any]
    ) -> None:
        rule = _rule_by_id(rule_id)
        candidate = _make_patient(
            first="john", last="smith", dob="1990-01-15", **anchor_kwargs
        )
        query = _make_patient(
            first="john", last="smith", dob="1990-01-16", **anchor_kwargs
        )
        engine = MatchingEngine(
            backend=InMemoryBackend([candidate]),
            rules=(rule,),
            household_individual_rules=(),
        )
        result = await engine.match(query)
        assert result.outcome == MatchOutcome.MATCH
        evaluation = next(
            e for e in result.rule_evaluations if e.rule_id == rule_id and e.matched
        )
        assert evaluation.field_outcomes["dob"] == "fuzzy"

    @pytest.mark.parametrize("rule_id,anchor_kwargs", _RULE_ANCHOR_FIELDS)
    async def test_dob_two_days_off_does_not_match(
        self, rule_id: str, anchor_kwargs: Dict[str, Any]
    ) -> None:
        rule = _rule_by_id(rule_id)
        candidate = _make_patient(
            first="john", last="smith", dob="1990-01-17", **anchor_kwargs
        )
        query = _make_patient(
            first="john", last="smith", dob="1990-01-15", **anchor_kwargs
        )
        engine = MatchingEngine(
            backend=InMemoryBackend([candidate]),
            rules=(rule,),
            household_individual_rules=(),
        )
        result = await engine.match(query)
        assert result.outcome == MatchOutcome.NO_MATCH

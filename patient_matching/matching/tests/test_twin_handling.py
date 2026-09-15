"""Tests for CMS v3.4.0 SS C.7 twin/multiple-birth handling (session 19).

Uses Category 2 rule 13 (H-01: SSN Last 4 + Phone; I-01: First Name* + DOB)
as the vehicle throughout - any household/individual rule pairing First
Name* with a shared-household field would exercise the same logic.
"""

from typing import Any, Dict, List

from patient_matching.matching.backend import FieldCriterion, MatchingBackend
from patient_matching.matching.household_rules import CATEGORY_2_RULES
from patient_matching.matching.match_result import MatchOutcome
from patient_matching.matching.matching_engine import MatchingEngine
from patient_matching.matching.table2_rules import APPROVED_RULES

_RULE_13 = next(r for r in CATEGORY_2_RULES if r.rule_id == "13")


class _InMemoryBackend(MatchingBackend):
    def __init__(self, patients: List[Dict[str, Any]]):
        self._patients = patients

    async def search(self, criteria: List[FieldCriterion]) -> List[Dict[str, Any]]:
        return list(self._patients)


def _twin_patient(
    *,
    first: str,
    middle: str = "",
    dob: str,
    ssn_last4: str = "1234",
    phone: str = "+12125551234",
    namespace_id: str = "",
) -> Dict[str, Any]:
    given = [first] + ([middle] if middle else [])
    identifiers: List[Dict[str, Any]] = [
        {"system": "http://hl7.org/fhir/sid/us-ssn", "value": f"xxx-xx-{ssn_last4}"}
    ]
    if namespace_id:
        system, value = namespace_id.split("|", 1)
        identifiers.append(
            {
                "system": system,
                "type": {"coding": [{"code": "MR"}]},
                "value": value,
            }
        )
    return {
        "resourceType": "Patient",
        "name": [{"given": given}],
        "birthDate": dob,
        "telecom": [{"system": "phone", "value": phone}],
        "address": [],
        "identifier": identifiers,
    }


def _rule13_engine(candidates: List[Dict[str, Any]]) -> MatchingEngine:
    return MatchingEngine(
        backend=_InMemoryBackend(candidates),
        rules=(),
        household_individual_rules=(_RULE_13,),
    )


def _default_rules_engine(candidates: List[Dict[str, Any]]) -> MatchingEngine:
    """Engine with the full production default Category 1 rule set active
    alongside rule 13 - used to prove the twin tiebreak actually survives
    contact with the rest of the engine's rules, not just an isolated
    rule=() harness (see adversarial-review finding: the tiebreak was
    empirically inert under the real default configuration because
    `_build_result`'s cross-rule union re-introduced the twin an
    independent flat rule also matched)."""
    return MatchingEngine(
        backend=_InMemoryBackend(candidates),
        rules=APPROVED_RULES,
        household_individual_rules=(_RULE_13,),
    )


class TestExactFirstNameWhenDobShared:
    """SS C.7(1): fuzzy First Name is disabled whenever the household step
    surfaces >1 candidate sharing an identical DOB."""

    async def test_fuzzy_sibling_excluded_when_dob_shared(self) -> None:
        twin_exact = _twin_patient(first="jayden", dob="2015-06-01")
        twin_fuzzy_only = _twin_patient(first="jaden", dob="2015-06-01")
        query = _twin_patient(first="jayden", dob="2015-06-01")
        engine = _rule13_engine([twin_exact, twin_fuzzy_only])

        result = await engine.match(query)

        assert result.outcome == MatchOutcome.MATCH
        assert result.matched_patients == [twin_exact]

    async def test_fuzzy_first_name_still_works_without_a_dob_sharing_sibling(
        self,
    ) -> None:
        """Control case: a single household-tier match (no DOB-sharing
        sibling in the candidate pool) must still resolve via the normal
        fuzzy-eligible First Name path - this session must not regress the
        common, non-twin case."""
        candidate = _twin_patient(first="jaden", dob="2015-06-01")
        query = _twin_patient(first="jayden", dob="2015-06-01")
        engine = _rule13_engine([candidate])

        result = await engine.match(query)

        assert result.outcome == MatchOutcome.MATCH
        assert result.matched_patients == [candidate]


class TestPlaceholderOrIdenticalNamesFailClosed:
    """SS C.7(2): no new mechanism needed - the existing per-candidate
    exact/missing-field checks already produce the required outcome."""

    async def test_identical_first_names_among_twins_escalates(self) -> None:
        twin_a = _twin_patient(first="james", dob="2015-06-01")
        twin_b = _twin_patient(first="james", dob="2015-06-01")
        query = _twin_patient(first="james", dob="2015-06-01")
        engine = _rule13_engine([twin_a, twin_b])

        result = await engine.match(query)

        assert result.outcome == MatchOutcome.ESCALATE
        assert len(result.matched_patients) == 2

    async def test_placeholder_stripped_names_fail_closed_to_no_match(self) -> None:
        """Both twins' First Name already stripped to empty by upstream
        normalization (simulated directly here, not re-testing the
        normalizer) - neither can resolve, so the query fails closed
        rather than guessing."""
        twin_a = _twin_patient(first="", dob="2015-06-01")
        twin_b = _twin_patient(first="", dob="2015-06-01")
        query = _twin_patient(first="john", dob="2015-06-01")
        engine = _rule13_engine([twin_a, twin_b])

        result = await engine.match(query)

        assert result.outcome == MatchOutcome.NO_MATCH
        assert result.matched_patients == []


class TestMiddleNameTiebreaker:
    """SS C.7(3): middle name as a last-resort tiebreaker, only for an
    exact 2-candidate tie on a shared-DOB (twin) case."""

    async def test_discriminating_middle_name_breaks_the_tie(self) -> None:
        twin_a = _twin_patient(first="james", middle="michael", dob="2015-06-01")
        twin_b = _twin_patient(first="james", middle="edward", dob="2015-06-01")
        query = _twin_patient(first="james", middle="michael", dob="2015-06-01")
        engine = _rule13_engine([twin_a, twin_b])

        result = await engine.match(query)

        assert result.outcome == MatchOutcome.MATCH
        assert result.matched_patients == [twin_a]

    async def test_non_discriminating_middle_name_stays_escalated(self) -> None:
        """Both twins share the same middle name too - it doesn't help,
        so the tie must not be force-broken."""
        twin_a = _twin_patient(first="james", middle="lee", dob="2015-06-01")
        twin_b = _twin_patient(first="james", middle="lee", dob="2015-06-01")
        query = _twin_patient(first="james", middle="lee", dob="2015-06-01")
        engine = _rule13_engine([twin_a, twin_b])

        result = await engine.match(query)

        assert result.outcome == MatchOutcome.ESCALATE
        assert len(result.matched_patients) == 2

    async def test_query_without_middle_name_stays_escalated(self) -> None:
        twin_a = _twin_patient(first="james", middle="michael", dob="2015-06-01")
        twin_b = _twin_patient(first="james", middle="edward", dob="2015-06-01")
        query = _twin_patient(first="james", dob="2015-06-01")  # no middle name
        engine = _rule13_engine([twin_a, twin_b])

        result = await engine.match(query)

        assert result.outcome == MatchOutcome.ESCALATE
        assert len(result.matched_patients) == 2


class TestPersistentIdentifierAnchor:
    """SS C.7(4): a query carrying a namespace_id recorded at a prior
    resolution breaks an otherwise-ambiguous twin tie outright, taking
    priority over the middle-name heuristic.

    **Not free via cross-rule aggregation, found empirically while writing
    this test**: `_build_result` unions every contributing rule's matches
    rather than letting a more-specific rule suppress a less-specific one,
    so a separately-matching namespace_id flat rule does NOT by itself
    narrow rule 13's own ambiguous 2-candidate result - the anchor has to
    be applied inside the household/individual tie-resolution itself (see
    `_break_twin_tie_with_namespace_id`)."""

    async def test_namespace_id_resolves_cleanly_despite_twin_ambiguity(self) -> None:
        twin_a = _twin_patient(
            first="james", dob="2015-06-01", namespace_id="urn:hospital:abc|MRN001"
        )
        twin_b = _twin_patient(
            first="james", dob="2015-06-01", namespace_id="urn:hospital:abc|MRN002"
        )
        query = _twin_patient(
            first="james", dob="2015-06-01", namespace_id="urn:hospital:abc|MRN001"
        )
        engine = _rule13_engine([twin_a, twin_b])

        result = await engine.match(query)

        assert result.outcome == MatchOutcome.MATCH
        assert result.matched_patients == [twin_a]

    async def test_namespace_id_takes_priority_over_middle_name(self) -> None:
        """If both an anchor and a discriminating middle name are present
        but disagree, the near-zero-collision namespace_id anchor wins."""
        twin_a = _twin_patient(
            first="james",
            middle="michael",
            dob="2015-06-01",
            namespace_id="urn:hospital:abc|MRN001",
        )
        twin_b = _twin_patient(
            first="james",
            middle="edward",
            dob="2015-06-01",
            namespace_id="urn:hospital:abc|MRN002",
        )
        # Namespace ID points at twin_b; middle name (if it were checked
        # first) would incorrectly point at twin_a.
        query = _twin_patient(
            first="james",
            middle="michael",
            dob="2015-06-01",
            namespace_id="urn:hospital:abc|MRN002",
        )
        engine = _rule13_engine([twin_a, twin_b])

        result = await engine.match(query)

        assert result.outcome == MatchOutcome.MATCH
        assert result.matched_patients == [twin_b]


class TestTiebreakSurvivesDefaultRuleSet:
    """Regression guard for an adversarial-review finding: every test above
    uses `rules=()`, which disables all 30 Category 1 flat rules. Under the
    production default (`rules=APPROVED_RULES`), a flat rule matching on a
    name alias the twins happen to share (e.g. rule 11: First Name + DOB +
    Phone, exact-match via set intersection) independently re-matches BOTH
    twins - and `_build_result`'s cross-rule union is not "most specific
    rule wins," so without an explicit exclusion signal from the tiebreak,
    the union silently recreates the tie rule 13 just resolved."""

    async def test_middle_name_tiebreak_still_resolves_uniquely_with_flat_rules_active(
        self,
    ) -> None:
        # Both twins share "james" as a given name (twin_b's is a second
        # given name, so it lands in first_names per Core Principle 10),
        # which is enough for flat rule 11 (First Name EXACT + DOB EXACT +
        # Phone EXACT, exact-match = set intersection) to match BOTH twins
        # independently of rule 13's household/individual resolution.
        twin_a = _twin_patient(first="james", middle="michael", dob="2015-06-01")
        twin_b = _twin_patient(first="edward", middle="james", dob="2015-06-01")
        query = _twin_patient(first="james", middle="michael", dob="2015-06-01")
        engine = _default_rules_engine([twin_a, twin_b])

        result = await engine.match(query)

        assert result.outcome == MatchOutcome.MATCH
        assert result.matched_patients == [twin_a]
        assert twin_b not in result.matched_patients

    async def test_namespace_anchor_tiebreak_still_resolves_uniquely_with_flat_rules_active(
        self,
    ) -> None:
        twin_a = _twin_patient(
            first="james", dob="2015-06-01", namespace_id="urn:hospital:abc|MRN001"
        )
        twin_b = _twin_patient(
            first="james", dob="2015-06-01", namespace_id="urn:hospital:abc|MRN002"
        )
        query = _twin_patient(
            first="james", dob="2015-06-01", namespace_id="urn:hospital:abc|MRN001"
        )
        engine = _default_rules_engine([twin_a, twin_b])

        result = await engine.match(query)

        assert result.outcome == MatchOutcome.MATCH
        assert result.matched_patients == [twin_a]
        assert twin_b not in result.matched_patients


class TestNonTwinHouseholdMemberUnaffected:
    """Regression guard: the exact-First-Name gate must be scoped to the
    specific candidates whose own DOB is shared with a sibling, not applied
    to the whole household-tier match set. A parent living with twins must
    keep ordinary fuzzy First Name matching."""

    async def test_household_member_without_a_shared_dob_still_gets_fuzzy_first_name(
        self,
    ) -> None:
        twin_a = _twin_patient(first="james", dob="2015-06-01")
        twin_b = _twin_patient(first="john", dob="2015-06-01")
        mom = _twin_patient(first="deborah", dob="1985-01-01")
        # One-edit typo on the parent's first name - must still resolve via
        # ordinary fuzzy matching despite the twins in the same household.
        query = _twin_patient(first="debora", dob="1985-01-01")
        engine = _rule13_engine([twin_a, twin_b, mom])

        result = await engine.match(query)

        assert result.outcome == MatchOutcome.MATCH
        assert result.matched_patients == [mom]


class TestMissingMiddleNameIsNotDiscriminating:
    """Regression guard: absence of a recorded middle name must not be
    treated as evidence against a candidate - only a genuine mismatch
    between two present middle names may break the tie."""

    async def test_twin_with_no_recorded_middle_name_does_not_lose_the_tiebreak(
        self,
    ) -> None:
        twin_a = _twin_patient(first="james", middle="michael", dob="2015-06-01")
        twin_b = _twin_patient(first="james", dob="2015-06-01")  # no middle name
        query = _twin_patient(first="james", middle="michael", dob="2015-06-01")
        engine = _rule13_engine([twin_a, twin_b])

        result = await engine.match(query)

        assert result.outcome == MatchOutcome.ESCALATE
        assert len(result.matched_patients) == 2


class TestAnchorMatchingNeitherCandidateDisqualifies:
    """Regression guard: a namespace_id anchor present on the query but
    matching neither tied candidate is itself a disqualifying signal - it
    must not silently fall through to the middle-name heuristic, which
    could otherwise pick the wrong twin based on a lower-confidence
    signal the anchor already contradicted."""

    async def test_anchor_matching_neither_twin_stays_escalated_despite_middle_name(
        self,
    ) -> None:
        twin_a = _twin_patient(
            first="james",
            middle="michael",
            dob="2015-06-01",
            namespace_id="urn:hospital:abc|MRN001",
        )
        twin_b = _twin_patient(
            first="james",
            middle="edward",
            dob="2015-06-01",
            namespace_id="urn:hospital:abc|MRN002",
        )
        # Query's namespace_id matches neither twin; its middle name would
        # (incorrectly) point at twin_a if the middle-name heuristic ran.
        query = _twin_patient(
            first="james",
            middle="michael",
            dob="2015-06-01",
            namespace_id="urn:hospital:abc|MRN999",
        )
        engine = _rule13_engine([twin_a, twin_b])

        result = await engine.match(query)

        assert result.outcome == MatchOutcome.ESCALATE
        assert len(result.matched_patients) == 2


class TestHigherOrderMultiples:
    """SS C.7 is scoped to "multiple births," not just twins. Documents
    the current, intentionally conservative behavior for triplets+: the
    tiebreak only engages for an exact 2-candidate tie, so 3+ candidates
    sharing a DOB always fall through to the base document's AMBIGUOUS
    escalation, even when a persistent identifier would have uniquely
    resolved one of them. This is a known limitation (safe direction: it
    can only under-return, never mis-match) rather than a defect fixed by
    this session - flagged for follow-up, not solved here."""

    async def test_triplets_with_a_uniquely_resolving_anchor_still_escalate(
        self,
    ) -> None:
        triplet_a = _twin_patient(
            first="james", dob="2015-06-01", namespace_id="urn:hospital:abc|MRN001"
        )
        triplet_b = _twin_patient(
            first="james", dob="2015-06-01", namespace_id="urn:hospital:abc|MRN002"
        )
        triplet_c = _twin_patient(
            first="james", dob="2015-06-01", namespace_id="urn:hospital:abc|MRN003"
        )
        query = _twin_patient(
            first="james", dob="2015-06-01", namespace_id="urn:hospital:abc|MRN001"
        )
        engine = _rule13_engine([triplet_a, triplet_b, triplet_c])

        result = await engine.match(query)

        assert result.outcome == MatchOutcome.AMBIGUOUS
        assert len(result.matched_patients) == 3

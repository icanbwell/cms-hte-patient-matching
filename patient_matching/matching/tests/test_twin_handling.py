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

"""Name and gender-marker changes under Table 2 (BAI-1151).

Characterization tests: they pin what the engine does today when a person's first
name, last name or gender marker changes, so a future change shows up as a deliberate,
reviewed test change. They do not change matching behavior. All records are synthetic.

Scenario IDs follow the ticket:

  (a), (c)  gender-pair cases: Table 2 has no gender field, so a changed gender marker
            never blocks a match (a first-name change is still carried by rule 30)
  (b)       first name and gender marker changed, former name also listed -> link
  (d)       last + middle name changed -> link while phone, email or an identifier is
            shared; no link without any of them
  (e)       first AND last name changed, no shared identifier -> NO link (known
            limitation); every rule that skips First Name needs an identifier or
            Last Name + DOB + Phone

Table 2 is defined by the CMS spec, so closing (e) would need a conformance review, not a
code change alone. Details and the fixture caveat (555-exchange phones): docs/LEARNINGS.md,
"Name and gender-marker changes" and "The §V.D placeholder table had gaps".

Most cases run the real pipeline (normalize -> extract -> evaluate_pair); one class goes
through `match()` against an in-memory backend, because the pairwise decision never blocks.
"""

from typing import Any, Dict, List, Optional, Sequence

import pytest

from patient_matching.matching.field_extractor import FieldExtractor
from patient_matching.matching.in_memory_backend import InMemoryBackend
from patient_matching.matching.match_result import MatchOutcome
from patient_matching.matching.matching_engine import MatchingEngine
from patient_matching.matching.table2_rules import APPROVED_RULES
from patient_matching.normalization.manager import NormalizationManager
from tests._null_backend import NullBackend

_norm = NormalizationManager()
_extract = FieldExtractor().extract
_engine = MatchingEngine(backend=NullBackend())

_MBI = {"system": "http://hl7.org/fhir/sid/us-mbi", "value": "1EG4TE5MK73"}
_PHONE = {"system": "phone", "value": "+14158675309"}
_EMAIL = {"system": "email", "value": "pat.testerson@example.org"}


def _name(given: List[str], family: str, use: str = "official") -> Dict[str, Any]:
    return {"use": use, "family": family, "given": given}


def _record(
    names: Sequence[Dict[str, Any]],
    gender: str = "male",
    telecom: Optional[Sequence[Dict[str, Any]]] = None,
    identifiers: Optional[Sequence[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    return {
        "resourceType": "Patient",
        "name": list(names),
        "gender": gender,
        "birthDate": "1990-04-12",
        "telecom": [_PHONE, _EMAIL] if telecom is None else list(telecom),
        "address": [{"line": ["42 Willow Creek Rd"], "postalCode": "94110"}],
        "identifier": list(identifiers or []),
    }


def _links(a: Dict[str, Any], b: Dict[str, Any]) -> bool:
    return _engine.evaluate_pair(
        _extract(_norm.normalize(a)), _extract(_norm.normalize(b))
    )


_OLD_NAME = _name(["Alex"], "Testerson", use="old")
BEFORE = (_name(["Alex"], "Testerson"),)
NEW_FIRST = (_name(["Jordan"], "Testerson"),)
NEW_FIRST_AND_LAST = (_name(["Jordan"], "Marlowe"),)


class TestGenderMarkerIsNotAMatchingField:
    @pytest.mark.parametrize(
        ("source_gender", "target_gender"),
        [
            pytest.param("male", "male", id="control_gender_unchanged"),
            pytest.param("male", "female", id="a_male_to_female"),
            pytest.param("female", "male", id="a_female_to_male"),
            pytest.param("male", "other", id="c_male_to_other"),
            pytest.param("female", "unknown", id="c_female_to_unknown"),
        ],
    )
    def test_first_name_change_links_whatever_the_gender_marker(
        self, source_gender: str, target_gender: str
    ) -> None:
        assert _links(_record(BEFORE, source_gender), _record(NEW_FIRST, target_gender))


class TestFirstAndLastNameBothChanged:
    def test_e_no_shared_identifier_is_not_linked(self) -> None:
        """KNOWN LIMITATION (BAI-1151 case e): same DOB, phone, email and address."""
        assert not _links(
            _record(BEFORE, "male"), _record(NEW_FIRST_AND_LAST, "female")
        )

    def test_shared_mbi_links(self) -> None:
        assert _links(
            _record(BEFORE, "male", identifiers=[_MBI]),
            _record(NEW_FIRST_AND_LAST, "female", identifiers=[_MBI]),
        )

    def test_e_variant_former_name_on_record_links(self) -> None:
        target_names = [*NEW_FIRST_AND_LAST, _OLD_NAME]

        assert _links(_record(BEFORE, "male"), _record(target_names, "female"))


class TestEndToEndThroughMatch:
    """Same outcomes through `match()` (blocking, retrieval, uniqueness), not just
    the pairwise `evaluate_pair` decision used everywhere else in this file."""

    @pytest.mark.parametrize(
        ("stored", "query", "expected"),
        [
            pytest.param(
                _record(BEFORE, "male"),
                _record(NEW_FIRST, "female"),
                MatchOutcome.MATCH,
                id="a_first_name_and_gender_marker_changed",
            ),
            pytest.param(
                _record(BEFORE, "male"),
                _record([*NEW_FIRST, _OLD_NAME], "female"),
                MatchOutcome.MATCH,
                id="b_first_name_and_gender_changed_former_name_listed",
            ),
            pytest.param(
                _record(BEFORE, "male"),
                _record(NEW_FIRST_AND_LAST, "female"),
                MatchOutcome.NO_MATCH,
                id="e_first_and_last_changed_no_identifier",
            ),
            pytest.param(
                _record(BEFORE, "male", identifiers=[_MBI]),
                _record(NEW_FIRST_AND_LAST, "female", identifiers=[_MBI]),
                MatchOutcome.MATCH,
                id="e_variant_shared_mbi",
            ),
            pytest.param(
                _record(BEFORE, "male"),
                _record([*NEW_FIRST_AND_LAST, _OLD_NAME], "female"),
                MatchOutcome.MATCH,
                id="e_variant_query_lists_former_name",
            ),
            pytest.param(
                _record([*NEW_FIRST_AND_LAST, _OLD_NAME], "female"),
                _record(BEFORE, "male"),
                MatchOutcome.MATCH,
                id="e_variant_stored_record_lists_former_name",
            ),
        ],
    )
    async def test_outcome(
        self, stored: Dict[str, Any], query: Dict[str, Any], expected: MatchOutcome
    ) -> None:
        stored_patient = {**_norm.normalize(stored), "id": "stored"}
        query_patient = {**_norm.normalize(query), "id": "query"}
        engine = MatchingEngine(backend=InMemoryBackend([stored_patient]))

        result = await engine.match(query_patient)

        assert result.outcome == expected


class TestLegalNameChangeOfLastAndMiddleName:
    SOURCE = (_name(["Alex", "Marie"], "Testerson"),)
    TARGET = (_name(["Alex", "Quinn"], "Marlowe"),)

    @pytest.mark.parametrize(
        ("telecom", "identifiers", "links"),
        [
            pytest.param([_PHONE, _EMAIL], [], True, id="phone_and_email"),
            pytest.param([_PHONE], [], True, id="phone_only"),
            pytest.param([_EMAIL], [], True, id="email_only"),
            pytest.param([], [_MBI], True, id="mbi_only"),
            pytest.param([], [], False, id="nothing_shared"),
        ],
    )
    def test_d_links_while_phone_email_or_identifier_is_shared(
        self,
        telecom: List[Dict[str, Any]],
        identifiers: List[Dict[str, Any]],
        links: bool,
    ) -> None:
        """Boundary of (d): without all three, only first name, DOB and address remain."""
        source = _record(self.SOURCE, "female", telecom, identifiers)
        target = _record(self.TARGET, "female", telecom, identifiers)

        assert _links(source, target) is links


class TestRulesThatSkipFirstName:
    _IDENTIFIER_FIELDS = {"mbi", "legal_id", "namespace_id", "insurance_member_id"}

    def test_exactly_these_rules_do_not_need_first_name(self) -> None:
        rule_ids = {
            rule.rule_id
            for rule in APPROVED_RULES
            if "first_name" not in {f.name for f in rule.fields}
        }

        assert rule_ids == {
            "10", "17", "18", "19", "20", "21", "22", "24", "25", "26", "30",
        }  # fmt: skip

    def test_each_needs_an_identifier_or_last_name_dob_phone(self) -> None:
        for rule in APPROVED_RULES:
            names = {f.name for f in rule.fields}
            if "first_name" in names:
                continue
            assert names & self._IDENTIFIER_FIELDS or names == {
                "last_name",
                "dob",
                "phone",
            }, f"rule {rule.rule_id} skips first name without an identifier"

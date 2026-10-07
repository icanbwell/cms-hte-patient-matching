"""CMS v3.4.0 name handling: only a generational suffix can veto a match.

"If a generational suffix can be identified on both the query and the response and they do not
match then the responder SHALL NOT return the match" (§V, Name Handling). MD, PhD, Esq and the like
are not generational: they say nothing about which generation of a family someone is, so they
never veto, and a shared non-generational suffix must not hide a generational conflict.

Each end-to-end case runs the real pipeline (normalize -> extract -> evaluate_pair).

Not covered here, on purpose: the spec also says First Name is the first given name only, but the
engine lets a middle name satisfy it, and removing that costs 194 ONC true matches. That is a
separate decision; see docs/LEARNINGS.md ("First Name accepts the middle name").
"""

from typing import Any, Dict, List, Optional, Set

import pytest

from patient_matching.matching.field_extractor import FieldExtractor
from patient_matching.matching.matching_engine import MatchingEngine
from patient_matching.normalization.manager import NormalizationManager
from tests._null_backend import NullBackend

_norm = NormalizationManager()
_extract = FieldExtractor().extract
_engine = MatchingEngine(backend=NullBackend())


def _record(suffix: Optional[List[str]] = None) -> Dict[str, Any]:
    name: Dict[str, Any] = {"family": "Alvarez", "given": ["Maria"]}
    if suffix:
        name["suffix"] = suffix
    return {
        "resourceType": "Patient",
        "name": [name],
        "birthDate": "1985-03-14",
        "telecom": [{"system": "phone", "value": "+14158675309"}],
        "address": [{"line": ["42 Willow Creek Rd"], "postalCode": "94110"}],
        "identifier": [],
    }


def _links(a: Dict[str, Any], b: Dict[str, Any]) -> bool:
    return _engine.evaluate_pair(
        _extract(_norm.normalize(a)), _extract(_norm.normalize(b))
    )


class TestExtractor:
    @pytest.mark.parametrize(
        ("suffix", "expected"),
        [
            (["Jr"], {"jr"}),
            (["Sr."], {"sr"}),
            (["III"], {"iii"}),
            (["2nd"], {"ii"}),
            (["MD"], set()),
            (["Jr/Sr"], {"jr", "sr"}),
            (["Jr.III"], {"jr", "iii"}),
            (["2"], {"ii"}),
            (["XI"], {"xi"}),
            (["Ph.D."], set()),
            (["PhD"], set()),
            (["Esq"], set()),
            (["MBA"], set()),
            (["Jr", "MD"], {"jr"}),
        ],
    )
    def test_only_generational_suffixes_are_collected(
        self, suffix: List[str], expected: Set[str]
    ) -> None:
        assert _extract(_norm.normalize(_record(suffix))).suffixes == expected


class TestGenerationalSuffixVeto:
    @pytest.mark.parametrize(
        ("a", "b", "links"),
        [
            # controls: these must hold before and after
            (["Jr"], ["Jr."], True),
            (["II"], ["2nd"], True),
            (["Jr"], ["Sr"], False),
            (["II"], ["III"], False),
            (["MD"], None, True),
            (["Jr", "MD"], ["Jr"], True),
            # the deviation: a non-generational suffix must not veto
            (["MD"], ["PhD"], True),
            (["Jr"], ["MD"], True),
            (["Esq"], ["MD"], True),
            (["MBA"], ["Jr"], True),
            # a shared non-generational suffix must not hide a generational conflict
            (["Jr", "MD"], ["Sr", "MD"], False),
        ],
    )
    def test_only_a_generational_suffix_on_both_sides_vetoes(
        self, a: List[str], b: Optional[List[str]], links: bool
    ) -> None:
        assert _links(_record(a), _record(b)) is links

    @pytest.mark.parametrize(
        ("a", "b", "conflict"),
        [
            ("jr", "sr", True),
            ("jr", "jr", False),
            ("md", "phd", False),
            ("jr", "md", False),
            ("esq", None, False),
            (None, "jr", False),
        ],
    )
    def test_manager_suffixes_conflict_follows_the_same_rule(
        self, a: Optional[str], b: Optional[str], conflict: bool
    ) -> None:
        assert _norm.suffixes_conflict(a, b) is conflict


class TestGenerationalSuffixCoverage:
    """A generational suffix must be recognised however it is spelled: before the veto was
    limited to generational suffixes, any unrecognised suffix still vetoed, so dropping one
    silently turned a blocked pair into a match."""

    @pytest.mark.parametrize(
        ("a", "b"),
        [
            (["VII"], ["VIII"]),
            (["IX"], ["X"]),
            (["VII"], ["II"]),
            (["Jr"], ["VII"]),
            (["6th"], ["7th"]),
            (["sixth"], ["seventh"]),
            (["the second"], ["the third"]),
            (["Jr., MD"], ["Sr."]),
            (["Jr III"], ["Sr"]),
            (["2d"], ["3d"]),
            (["2"], ["3"]),
            (["XI"], ["XII"]),
            (["11th"], ["12th"]),
            (["Jr/Sr"], ["III"]),
            (["Jr-MD"], ["Sr"]),
            (["Jr.III"], ["Sr"]),
        ],
    )
    def test_generational_suffixes_in_any_spelling_still_veto(
        self, a: List[str], b: List[str]
    ) -> None:
        assert _links(_record(a), _record(b)) is False

    @pytest.mark.parametrize(
        ("a", "b"),
        [
            (["VII"], ["7th"]),
            (["the second"], ["II"]),
            (["Jr., MD"], ["Jr"]),
            (["2d"], ["2nd"]),
            (["2"], ["II"]),
            (["XI"], ["11th"]),
            (["Jr/Sr"], ["Jr"]),
            (["Jr/Sr"], ["Sr"]),
            (["Jr-MD"], ["Jr"]),
        ],
    )
    def test_the_same_generation_in_different_spellings_still_links(
        self, a: List[str], b: List[str]
    ) -> None:
        assert _links(_record(a), _record(b)) is True

    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            (["Jr"], {"jr"}),
            (["Jr."], {"jr"}),
            (["MD"], set()),
        ],
    )
    def test_extractor_canonicalizes_a_raw_suffix_instead_of_dropping_it(
        self, raw: List[str], expected: Set[str]
    ) -> None:
        # Un-normalized input is outside the contract, but it must not silently lose its veto.
        assert _extract(_record(raw)).suffixes == expected

    def test_a_bare_string_suffix_is_one_suffix_not_a_set_of_characters(self) -> None:
        patient = _record()
        patient["name"][0]["suffix"] = "Jr"
        assert _extract(_norm.normalize(patient)).suffixes == {"jr"}

    def test_suffixes_split_across_name_entries_still_veto(self) -> None:
        a, b = _record(["Jr"]), _record(["Sr"])
        a["name"].append({"family": "Alvarez", "given": ["Maria"], "suffix": ["MD"]})
        b["name"].append({"family": "Alvarez", "given": ["Maria"], "suffix": ["MD"]})
        assert _links(a, b) is False

    def test_the_audit_record_shows_only_the_generational_values_compared(self) -> None:
        import asyncio

        from patient_matching.matching.in_memory_backend import InMemoryBackend

        stored = _norm.normalize(_record(["Sr", "MD"]))
        engine = MatchingEngine(backend=InMemoryBackend([stored]))
        result = asyncio.run(engine.match(_norm.normalize(_record(["Jr", "MD"]))))
        vetoed = [e for e in result.rule_evaluations if e.negated_by_suffix]
        assert vetoed
        assert vetoed[0].suffix_values == {"query": ["jr"], "candidate": ["sr"]}

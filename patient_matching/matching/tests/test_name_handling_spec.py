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

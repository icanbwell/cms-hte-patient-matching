"""Blocking must search on every value of a multi-valued query field.

A query field can carry several values (every given name, several phones,
...). Verification compares all of them, but a candidate only reaches
verification if blocking retrieved it - so blocking on a single value drops
any candidate that shares a non-chosen value. Picking that value from a
``set`` also made the outcome depend on the process's string-hash seed.

Each case below is parametrized over which of the query's two first names the
stored record carries, so a single-value blocker fails at least one case
under every hash seed.
"""

from __future__ import annotations

from typing import Any, AsyncIterator, Callable, Dict, List

import pytest

from patient_matching.cache.cache_backend import CachedPatient
from patient_matching.cache.duckdb_cache import DuckDBCache
from patient_matching.cache.matching_adapter import CacheMatchingBackend
from patient_matching.matching.backend import (
    FieldCriterion,
    MatchingBackend,
    MatchType,
)
from patient_matching.matching.in_memory_backend import InMemoryBackend
from patient_matching.matching.match_result import MatchOutcome
from patient_matching.matching.matching_engine import MatchingEngine
from patient_matching.matching.table2_rules import APPROVED_RULES, MatchingRule

QUERY_FIRST_NAMES = ["alex", "jordan"]
DOB = "1990-01-15"
PHONE = "+12125551234"


def _rule(rule_id: str) -> MatchingRule:
    return next(r for r in APPROVED_RULES if r.rule_id == rule_id)


def _patient(pid: str, given: List[str]) -> Dict[str, Any]:
    """Minimal normalized FHIR Patient (synthetic values only)."""
    return {
        "resourceType": "Patient",
        "id": pid,
        "name": [{"family": "rivera", "given": given}],
        "birthDate": DOB,
        "telecom": [{"system": "phone", "value": PHONE}],
        "address": [],
        "identifier": [],
    }


def _cached(pid: str, first: str) -> CachedPatient:
    return CachedPatient(
        patient_id=pid,
        first_names={first},
        last_names={"rivera"},
        dob={DOB},
        phones={PHONE},
        fhir_resource=_patient(pid, [first]),
    )


@pytest.fixture
async def duckdb_cache() -> AsyncIterator[DuckDBCache]:
    c = DuckDBCache(database=":memory:")
    yield c
    await c.close()


async def _in_memory(stored_first: str, _: DuckDBCache) -> MatchingBackend:
    return InMemoryBackend([_patient("p1", [stored_first])])


async def _cache_backed(stored_first: str, cache: DuckDBCache) -> MatchingBackend:
    await cache.upsert_patients([_cached("p1", stored_first)])
    return CacheMatchingBackend(cache)


BACKENDS = pytest.mark.parametrize(
    "make_backend", [_in_memory, _cache_backed], ids=["in_memory", "duckdb_cache"]
)
STORED_NAME = pytest.mark.parametrize("stored_first", QUERY_FIRST_NAMES)


class TestEngineBlocksOnEveryValue:
    @BACKENDS
    @STORED_NAME
    async def test_candidate_sharing_any_query_first_name_is_matched(
        self,
        make_backend: Callable[[str, DuckDBCache], Any],
        stored_first: str,
        duckdb_cache: DuckDBCache,
    ) -> None:
        engine = MatchingEngine(
            backend=await make_backend(stored_first, duckdb_cache),
            rules=(_rule("11"),),  # First Name + DOB + Phone, all exact
            household_individual_rules=(),
        )
        result = await engine.match(_patient("q", QUERY_FIRST_NAMES))

        assert result.outcome == MatchOutcome.MATCH
        rule_11 = next(e for e in result.rule_evaluations if e.rule_id == "11")
        assert rule_11.candidates_retrieved == 1

    async def test_blocking_criteria_records_every_value_sorted(self) -> None:
        engine = MatchingEngine(
            backend=InMemoryBackend([]),
            rules=(_rule("11"),),
            household_individual_rules=(),
        )
        result = await engine.match(_patient("q", ["jordan", "alex"]))

        rule_11 = next(e for e in result.rule_evaluations if e.rule_id == "11")
        assert rule_11.blocking_criteria["first_name"] == ["alex", "jordan"]
        assert rule_11.blocking_criteria["dob"] == [DOB]


class TestBackendsUnionWithinAField:
    """Within one criterion, values are OR'd; across criteria, still AND."""

    @pytest.fixture
    def criteria(self) -> List[FieldCriterion]:
        return [
            FieldCriterion(
                field_name="first_name", values=frozenset(QUERY_FIRST_NAMES)
            ),
            FieldCriterion(field_name="dob", value=DOB),
        ]

    async def test_in_memory_backend(self, criteria: List[FieldCriterion]) -> None:
        backend = InMemoryBackend(
            [
                _patient("p1", ["alex"]),
                _patient("p2", ["jordan"]),
                _patient("p3", ["casey"]),
            ]
        )
        ids = sorted(p["id"] for p in await backend.search(criteria))
        assert ids == ["p1", "p2"]

    async def test_cache_adapter(
        self, criteria: List[FieldCriterion], duckdb_cache: DuckDBCache
    ) -> None:
        await duckdb_cache.upsert_patients(
            [_cached("p1", "alex"), _cached("p2", "jordan"), _cached("p3", "casey")]
        )
        adapter = CacheMatchingBackend(duckdb_cache)
        ids = sorted(p["id"] for p in await adapter.search(criteria))
        assert ids == ["p1", "p2"]

    async def test_cache_adapter_dob_tolerance_expands_every_value(
        self, duckdb_cache: DuckDBCache
    ) -> None:
        a, b = _cached("p1", "alex"), _cached("p2", "alex")
        a.dob, b.dob = {"1990-01-16"}, {"1985-06-30"}  # each +/-1 day of a query DOB
        await duckdb_cache.upsert_patients([a, b])
        adapter = CacheMatchingBackend(duckdb_cache)

        results = await adapter.search(
            [
                FieldCriterion(
                    field_name="dob",
                    values=frozenset({"1990-01-15", "1985-07-01"}),
                    match_type=MatchType.DOB_TOLERANCE,
                )
            ]
        )
        assert sorted(p["id"] for p in results) == ["p1", "p2"]


class TestFieldCriterionValues:
    def test_single_value_construction_still_works(self) -> None:
        c = FieldCriterion(field_name="first_name", value="alex")
        assert c.values == frozenset({"alex"})

    def test_value_is_a_deterministic_member_of_values(self) -> None:
        c = FieldCriterion(
            field_name="first_name", values=frozenset({"jordan", "alex"})
        )
        assert c.value == "alex"

    def test_rejects_a_criterion_with_no_value(self) -> None:
        with pytest.raises(ValueError, match="first_name"):
            FieldCriterion(field_name="first_name")

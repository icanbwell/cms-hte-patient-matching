"""In-memory matching backend for demos, tests, and small datasets.

The production backends (DuckDB, MongoDB, Elasticsearch, PostgreSQL, Redis)
require external infrastructure. This backend holds a list of already-normalized
FHIR Patient dicts in memory and answers the :class:`MatchingEngine`'s
candidate-search calls with no database at all — ideal for notebooks, unit
tests, and quick experimentation with the Table 2 rules.

Search semantics mirror what the engine expects (see ``backend.MatchingBackend``):
criteria are combined with AND, each criterion matched exactly or fuzzily per its
``match_type``. Candidate values are compared with :class:`FieldComparator`, the
same comparator the engine uses, so blocking here is consistent with the
engine's own per-rule verification (which still runs afterward and enforces
``max_fuzzy_fields``, suffix conflicts, and uniqueness).

Example::

    from patient_matching.matching import InMemoryBackend, MatchingManager

    backend = InMemoryBackend([normalized_patient_a, normalized_patient_b])
    manager = MatchingManager(backend=backend)
    result = await manager.match(normalized_query_patient)
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional

from .backend import FieldCriterion, MatchingBackend, MatchType
from .field_comparator import FieldComparator
from .field_extractor import FieldExtractor, PatientFields


class InMemoryBackend(MatchingBackend):
    """A zero-infrastructure :class:`MatchingBackend` backed by a Python list.

    Patient dicts are expected to be **already normalized** (lowercased,
    diacritics folded, punctuation removed, phones in E.164, etc.) — the same
    contract :class:`FieldExtractor` assumes. Use ``NormalizationManager`` to
    normalize raw FHIR Patients before adding them.

    Args:
        patients: Optional iterable of normalized FHIR Patient dicts to load.
        extractor: Field extractor (a default is created if omitted).
        comparator: Field comparator (a default is created if omitted).
    """

    def __init__(
        self,
        patients: Optional[Iterable[Dict[str, Any]]] = None,
        *,
        extractor: Optional[FieldExtractor] = None,
        comparator: Optional[FieldComparator] = None,
    ) -> None:
        self._extractor = extractor or FieldExtractor()
        self._comparator = comparator or FieldComparator()
        self._patients: List[Dict[str, Any]] = []
        # Pre-extract each patient's fields once so repeated searches are cheap.
        self._fields: List[PatientFields] = []
        if patients is not None:
            self.add_many(patients)

    def add(self, patient: Dict[str, Any]) -> None:
        """Add one normalized FHIR Patient dict to the in-memory store."""
        self._patients.append(patient)
        self._fields.append(self._extractor.extract(patient))

    def add_many(self, patients: Iterable[Dict[str, Any]]) -> None:
        """Add several normalized FHIR Patient dicts."""
        for patient in patients:
            self.add(patient)

    def __len__(self) -> int:
        return len(self._patients)

    async def search(self, criteria: List[FieldCriterion]) -> List[Dict[str, Any]]:
        """Return every stored patient that satisfies ALL criteria (AND).

        An empty criteria list returns no candidates (the engine only calls
        ``search`` with a rule's fully-populated field set).
        """
        if not criteria:
            return []
        return [
            patient
            for patient, fields in zip(self._patients, self._fields)
            if all(self._satisfies(criterion, fields) for criterion in criteria)
        ]

    def _satisfies(self, criterion: FieldCriterion, fields: PatientFields) -> bool:
        """Check one criterion against one candidate's extracted fields."""
        candidate_values = fields.get_values(criterion.field_name)
        if not candidate_values:
            return False
        query_values = {criterion.value}
        if self._comparator.exact_match(query_values, candidate_values):
            return True
        if criterion.match_type == MatchType.FUZZY:
            return self._comparator.fuzzy_match(query_values, candidate_values)
        if criterion.match_type == MatchType.DOB_TOLERANCE:
            return self._comparator.dob_fuzzy_match(query_values, candidate_values)
        return False

"""matching: CMS Patient Matching per Proposal v3.2.2.

Evaluates a query FHIR Patient resource against candidate records
using the 26 approved Table 2 field combinations, constrained
fuzzy matching, suffix conflict detection, and uniqueness checks.
"""

from .backend import FieldCriterion, MatchingBackend, MatchType
from .field_comparator import FieldComparator
from .field_extractor import FieldExtractor, PatientFields
from .in_memory_backend import InMemoryBackend
from .match_result import MatchOutcome, MatchResult, RuleEvaluation
from .matching_engine import MatchingEngine
from .matching_manager import MatchingManager
from .table2_rules import APPROVED_RULES, FieldRole, MatchingRule

__all__ = [
    "APPROVED_RULES",
    "FieldComparator",
    "FieldCriterion",
    "FieldExtractor",
    "FieldRole",
    "InMemoryBackend",
    "MatchingBackend",
    "MatchingEngine",
    "MatchingManager",
    "MatchingRule",
    "MatchOutcome",
    "MatchResult",
    "MatchType",
    "PatientFields",
    "RuleEvaluation",
]

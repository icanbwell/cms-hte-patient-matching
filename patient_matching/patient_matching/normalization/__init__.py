"""normalization: Normalize FHIR Patient demographics for matching.

Applies case folding, diacritic folding, whitespace/punctuation removal,
nickname expansion, address standardization (Project US@), phone E.164
normalization, date validation, and placeholder suppression per the
CMS Patient Matching proposal.
"""

from .normalizer import PatientNormalizer
from .manager import NormalizationManager
from .name_normalizer import NameNormalizer
from .address_normalizer import AddressNormalizer
from .phone_normalizer import PhoneNormalizer
from .date_normalizer import DateNormalizer
from .placeholder_detector import PlaceholderDetector
from .text_utils import normalize_text, fold_diacritics

__all__ = [
    "AddressNormalizer",
    "DateNormalizer",
    "fold_diacritics",
    "NameNormalizer",
    "NormalizationManager",
    "normalize_text",
    "PatientNormalizer",
    "PhoneNormalizer",
    "PlaceholderDetector",
]

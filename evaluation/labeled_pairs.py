"""Assemble a labeled CMS test-dataset sample - (Outside Record, Internal
Record, IsMatch) - from the ONC dataset.

This is session_9's concrete answer to session_8.md's 2026-08-13 open question
("the test-data simulation methodology itself is still open"): true-match rows
come from mutations.py's single-edit fuzzy variants of a real record; true-
non-match rows come from hard_negatives.py's mined real-record pairs - not
random cross-pairs (session_3/onc_baseline.py's approach) and not mutations
asserted to be non-matches (see hard_negatives.py's module docstring for why
that would only test the algorithm's own tolerance, not reality).

Session_8 is expected to consume this module's `LabeledPair` output directly
for its labeled-set comparison; this module does not score pairs itself - see
SYNTHETIC_DATA_COMPARISON.md for the full division of responsibility.

Run standalone from the repo root:

    PYTHONPATH=. python evaluation/labeled_pairs.py
"""

from __future__ import annotations

import random
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List

from hard_negatives import mine_shared_address_hard_negatives
from mutations import generate_fuzzy_variant
from onc_loader import load_onc_patients
from rule_eval import LabeledPair

from patient_matching.matching.field_extractor import FieldExtractor
from patient_matching.normalization.manager import NormalizationManager


def build_labeled_pairs(
    patients: List[Dict[str, Any]],
    *,
    n_fuzzy_variants_per_patient: int = 1,
    seed: int = 0,
) -> List[LabeledPair]:
    """Build LabeledPairs from ONC patients: fuzzy-variant true-matches plus
    mined-hard-negative true-non-matches.

    Patients are run through NormalizationManager before mutation/extraction,
    matching onc_baseline.py's build_onc_pairs contract (every MatchingEngine
    caller must normalize first; FieldExtractor assumes it).
    """
    normalizer = NormalizationManager()
    extractor = FieldExtractor()
    normalized = [normalizer.normalize(p) for p in patients]
    rng = random.Random(seed)
    pairs: List[LabeledPair] = []

    for p in normalized:
        q_fields = extractor.extract(p)
        for _ in range(n_fuzzy_variants_per_patient):
            variant, mutation_type = generate_fuzzy_variant(p, rng=rng)
            c_fields = extractor.extract(variant)
            pairs.append(
                LabeledPair(
                    features={"query": q_fields, "candidate": c_fields},
                    is_true_match=True,
                    strata={"pair_type": "fuzzy_variant", "mutation": mutation_type},
                    pair_id=f"{p['id']}::{mutation_type}",
                )
            )

    for candidate in mine_shared_address_hard_negatives(normalized):
        q_fields = extractor.extract(candidate.query)
        c_fields = extractor.extract(candidate.candidate)
        pairs.append(
            LabeledPair(
                features={"query": q_fields, "candidate": c_fields},
                is_true_match=False,
                strata={"pair_type": "hard_negative", **candidate.shared_fields},
                pair_id=f"{candidate.query['id']}::{candidate.candidate['id']}",
            )
        )
    return pairs


if __name__ == "__main__":
    onc_dir = Path(__file__).parent / "fixtures" / "onc"
    patients = load_onc_patients(sorted(onc_dir.glob("*.csv")))
    pairs = build_labeled_pairs(patients)
    counts = Counter(
        (p.strata.get("pair_type"), p.strata.get("mutation")) for p in pairs
    )
    print(f"Built {len(pairs)} labeled pairs from {len(patients)} ONC patients:")
    for (pair_type, mutation), count in sorted(counts.items(), key=lambda kv: -kv[1]):
        label = f"{pair_type}/{mutation}" if mutation else pair_type
        print(f"  {label}: {count}")

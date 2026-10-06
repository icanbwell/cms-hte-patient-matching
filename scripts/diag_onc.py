"""TEMPORARY diagnostic (BAI-1062): print env + per-pair ONC outcomes to diff CI vs local."""
import json
import platform
import sys
import unicodedata
from importlib import metadata

sys.path.insert(0, ".")
from patient_matching.matching.field_extractor import FieldExtractor  # noqa: E402
from patient_matching.matching.matching_engine import MatchingEngine  # noqa: E402
from patient_matching.matching.table2_rules import APPROVED_RULES  # noqa: E402
from patient_matching.normalization.manager import NormalizationManager  # noqa: E402
from tests._null_backend import NullBackend  # noqa: E402

print("DIAG python", sys.version.split()[0], platform.platform(), "unidata", unicodedata.unidata_version)
print("DIAG rules", len(APPROVED_RULES), sorted(r.rule_id for r in APPROVED_RULES))
print("DIAG pkgs", sorted(f"{d.metadata['Name']}=={d.version}" for d in metadata.distributions()))
n = NormalizationManager()
x = FieldExtractor()
e = MatchingEngine(backend=NullBackend())
for line in open("tests/fixtures/onc/sample_labeled_pairs.jsonl"):
    c = json.loads(line)
    p = e.evaluate_pair(x.extract(n.normalize(c["source"])), x.extract(n.normalize(c["target"])))
    print("DIAG pair", c["case_id"], int(p), int(c["expected_match"]))

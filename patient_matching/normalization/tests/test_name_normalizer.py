"""Tests for name normalization."""

import pytest

from patient_matching.normalization.name_normalizer import NameNormalizer
from patient_matching.normalization.report import DroppedValue, NormalizationReport


class TestNameNormalizer:
    def setup_method(self) -> None:
        self.normalizer = NameNormalizer()

    def test_basic_name_normalization(self) -> None:
        patient = {
            "name": [
                {
                    "use": "official",
                    "family": "O'Connor",
                    "given": ["Mary-Jane", "Elizabeth"],
                }
            ]
        }
        result = self.normalizer.normalize_patient_names(patient)

        assert len(result) == 1
        assert result[0]["family"] == "oconnor"
        assert result[0]["given"][0] == "maryjane"
        assert result[0]["given"][1] == "elizabeth"
        assert result[0]["use"] == "official"

    def test_diacritic_folding_in_names(self) -> None:
        patient = {"name": [{"family": "García", "given": ["José"]}]}
        result = self.normalizer.normalize_patient_names(patient)

        assert result[0]["family"] == "garcia"
        assert result[0]["given"][0] == "jose"

    def test_suffix_normalization(self) -> None:
        patient = {
            "name": [
                {
                    "family": "Smith",
                    "given": ["John"],
                    "suffix": ["Junior"],
                }
            ]
        }
        result = self.normalizer.normalize_patient_names(patient)
        assert result[0]["suffix"] == ["jr"]

    def test_suffix_expansion_variants(self) -> None:
        assert self.normalizer.normalize_suffix("Junior") == "jr"
        assert self.normalizer.normalize_suffix("Jr.") == "jr"
        assert self.normalizer.normalize_suffix("III") == "iii"
        assert self.normalizer.normalize_suffix("3rd") == "iii"
        assert self.normalizer.normalize_suffix("Senior") == "sr"
        assert self.normalizer.normalize_suffix("Esquire") == "esq"

    def test_suffix_conflict_detection(self) -> None:
        # B.5: Both have suffixes and they differ -> conflict
        assert self.normalizer.suffixes_conflict("Jr", "Sr")
        assert self.normalizer.suffixes_conflict("II", "III")

        # One or both missing -> no conflict
        assert not self.normalizer.suffixes_conflict("Jr", "")
        assert not self.normalizer.suffixes_conflict("", "Sr")
        assert not self.normalizer.suffixes_conflict("", "")

        # Same suffix -> no conflict
        assert not self.normalizer.suffixes_conflict("Jr", "Junior")
        assert not self.normalizer.suffixes_conflict("3rd", "III")

    def test_placeholder_names_filtered(self) -> None:
        patient = {
            "name": [
                {"family": "Doe", "given": ["Baby Boy"]},
                {"family": "Smith", "given": ["James"]},
            ]
        }
        result = self.normalizer.normalize_patient_names(patient)

        # Baby Boy Doe should be filtered out (both parts are placeholders)
        assert len(result) == 1
        assert result[0]["family"] == "smith"

    @pytest.mark.parametrize(
        "given",
        [["Baby Girl", "Mary"], ["BABY BOY"], ["Infant"], ["Newborn Girl"]],
    )
    def test_placeholder_given_keeps_real_family_name(self, given: list[str]) -> None:
        """A newborn/temporary given name must not discard a real family name.

        The placeholder patterns are prefix-anchored, so testing the
        concatenated given+family string used to flag the whole entry (and
        lose e.g. `last_name`) whenever the given name began with "baby".
        """
        patient = {"name": [{"family": "Aaron", "given": given}]}
        result = self.normalizer.normalize_patient_names(patient)

        assert len(result) == 1
        assert result[0]["family"] == "aaron"
        assert "given" not in result[0]
        assert "_nicknames" not in result[0]

    @pytest.mark.parametrize(
        "given,family,reason",
        [
            (["Baby Girl", "Mary"], "Aaron", "newborn_temp_name"),
            (["Test"], "Smith", "test_name"),
            (["", "Baby Boy"], "Aaron", "newborn_temp_name"),
        ],
    )
    def test_dropped_placeholder_given_is_recorded_in_report(
        self, given: list[str], family: str, reason: str
    ) -> None:
        """Dropping only the given names must still be explainable, like a
        whole-entry drop is."""
        report = NormalizationReport()
        patient = {"name": [{"family": family, "given": given}]}
        result = self.normalizer.normalize_patient_names(patient, report=report)

        assert result[0]["family"] == family.lower()
        assert report.dropped == [
            DroppedValue(
                path="name[0].given",
                raw_value=next(g for g in given if g),
                reason=reason,
            )
        ]

    def test_missing_given_name_is_not_reported_as_dropped(self) -> None:
        report = NormalizationReport()
        patient = {"name": [{"family": "Aaron"}]}
        result = self.normalizer.normalize_patient_names(patient, report=report)

        assert result[0]["family"] == "aaron"
        assert report.dropped == []

    def test_placeholder_given_and_family_still_filtered(self) -> None:
        patient = {"name": [{"family": "Test", "given": ["Baby Boy"]}]}
        assert self.normalizer.normalize_patient_names(patient) == []

    def test_test_patient_filtered(self) -> None:
        patient = {"name": [{"family": "Test", "given": ["Test"]}]}
        result = self.normalizer.normalize_patient_names(patient)
        assert len(result) == 0

    def test_historical_names_preserved(self) -> None:
        patient = {
            "name": [
                {
                    "use": "official",
                    "family": "Johnson",
                    "given": ["Sarah"],
                },
                {
                    "use": "old",
                    "family": "Williams",
                    "given": ["Sarah"],
                },
            ]
        }
        result = self.normalizer.normalize_patient_names(patient)

        assert len(result) == 2
        assert result[0]["use"] == "official"
        assert result[0]["family"] == "johnson"
        assert result[1]["use"] == "old"
        assert result[1]["family"] == "williams"

    def test_nickname_lookup(self) -> None:
        nicks = self.normalizer.get_nicknames("William")
        # Should include common nicknames like bill, will, billy, etc.
        assert len(nicks) > 0
        assert any(n in nicks for n in ["bill", "will", "billy", "willy"])

    def test_nickname_empty(self) -> None:
        nicks = self.normalizer.get_nicknames("")
        assert len(nicks) == 0

    def test_nicknames_attached_to_name(self) -> None:
        patient = {"name": [{"family": "Smith", "given": ["Robert"]}]}
        result = self.normalizer.normalize_patient_names(patient)

        # Should have _nicknames extension with bob, rob, etc.
        nicks = result[0].get("_nicknames", [])
        assert len(nicks) > 0
        assert "bob" in nicks or "rob" in nicks

    def test_empty_names_list(self) -> None:
        assert self.normalizer.normalize_patient_names({}) == []
        assert self.normalizer.normalize_patient_names({"name": []}) == []

    def test_null_subfields_do_not_raise(self) -> None:
        """Real FHIR payloads can have a HumanName field present but explicitly
        `null` rather than omitted or `[]` -- `dict.get(key, default)` does not
        catch that case, only a missing key. Caught via a live run against
        `bronze.fhir_lake.patient_4_0_0` (name.suffix was `null`)."""
        patient = {
            "name": [
                {
                    "family": None,
                    "given": None,
                    "suffix": None,
                    "prefix": None,
                    "text": None,
                    "use": None,
                }
            ]
        }
        result = self.normalizer.normalize_patient_names(patient)
        assert result == []

    def test_null_name_list_does_not_raise(self) -> None:
        assert self.normalizer.normalize_patient_names({"name": None}) == []

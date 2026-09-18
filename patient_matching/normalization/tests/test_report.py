"""Tests for NormalizationReport / DroppedValue."""

from patient_matching.normalization.report import DroppedValue, NormalizationReport


class TestNormalizationReport:
    def test_starts_empty(self) -> None:
        report = NormalizationReport()
        assert report.dropped == []

    def test_record_appends_a_dropped_value(self) -> None:
        report = NormalizationReport()
        report.record("telecom[0].value", "+15551234567", "invalid_number")
        assert report.dropped == [
            DroppedValue(
                path="telecom[0].value",
                raw_value="+15551234567",
                reason="invalid_number",
            )
        ]

    def test_record_preserves_order_across_multiple_drops(self) -> None:
        report = NormalizationReport()
        report.record("name[0]", "jane doe", "unidentified_name")
        report.record("birthDate", "not-a-date", "unrecognized_format")
        assert [d.reason for d in report.dropped] == [
            "unidentified_name",
            "unrecognized_format",
        ]

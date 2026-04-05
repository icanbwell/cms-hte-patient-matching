"""Tests for shared text normalization utilities."""

from patient_matching.normalization.text_utils import fold_diacritics, normalize_text


class TestNormalizeText:
    def test_lowercase(self) -> None:
        assert normalize_text("JOHN") == "john"

    def test_remove_whitespace(self) -> None:
        assert normalize_text("  John  Doe  ") == "johndoe"

    def test_remove_punctuation(self) -> None:
        assert normalize_text("O'Brien-Smith") == "obriensmith"

    def test_diacritic_folding(self) -> None:
        assert normalize_text("Jose") == normalize_text("José")
        assert normalize_text("Müller") == "muller"
        assert normalize_text("Søren") == "soren"
        assert normalize_text("Ñoño") == "nono"

    def test_preserve_spaces(self) -> None:
        result = normalize_text("  123  Main  St  ", preserve_spaces=True)
        assert result == "123 main st"

    def test_combined(self) -> None:
        assert normalize_text("María-José O'Connor") == "mariajoseoconnor"

    def test_empty_string(self) -> None:
        assert normalize_text("") == ""


class TestFoldDiacritics:
    def test_accented_characters(self) -> None:
        assert fold_diacritics("café") == "cafe"
        assert fold_diacritics("naïve") == "naive"

    def test_no_diacritics(self) -> None:
        assert fold_diacritics("hello") == "hello"

    def test_ligatures(self) -> None:
        assert fold_diacritics("Æther") == "AEther"
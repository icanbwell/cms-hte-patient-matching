"""safe_fromstring must refuse DTD/entity declarations (entity-expansion attacks)."""

import io
import zipfile
from typing import List

import pytest

from scripts.institutional_registry.states.common import read_xlsx, safe_fromstring

BILLION_LAUGHS = b"""<?xml version="1.0"?>
<!DOCTYPE lolz [
  <!ENTITY lol "lol">
  <!ENTITY lol2 "&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;">
]>
<lolz>&lol2;</lolz>"""


def test_plain_xml_parses() -> None:
    root = safe_fromstring(b'<Root><FAC_SEARCH FACID="1" Address="1 Main St"/></Root>')
    assert root.find("FAC_SEARCH") is not None


@pytest.mark.parametrize(
    "payload",
    [
        BILLION_LAUGHS,
        b'<!DOCTYPE r [<!ENTITY x SYSTEM "file:///etc/passwd">]><r>&x;</r>',
        b"<!doctype r><r/>",  # DOCTYPE is matched case-insensitively
    ],
    ids=["entity-expansion", "external-entity", "lowercase-doctype"],
)
def test_doctype_and_entities_are_rejected(payload: bytes) -> None:
    with pytest.raises(ValueError, match="DOCTYPE or entities"):
        safe_fromstring(payload)


def test_utf16_is_rejected_because_its_markup_is_invisible_to_the_check() -> None:
    with pytest.raises(UnicodeDecodeError):
        safe_fromstring("<r><!DOCTYPE x></r>".encode("utf-16"))


def _xlsx(rows: List[List[str]]) -> bytes:
    """A minimal one-sheet workbook with inline strings."""
    ns = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
    cells = "".join(
        "<row>"
        + "".join(
            f'<c r="{chr(65 + j)}{i + 1}" t="inlineStr"><is><t>{v}</t></is></c>'
            for j, v in enumerate(row)
        )
        + "</row>"
        for i, row in enumerate(rows)
    )
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        zf.writestr(
            "xl/worksheets/sheet1.xml",
            f'<worksheet xmlns="{ns}"><sheetData>{cells}</sheetData></worksheet>',
        )
    return buffer.getvalue()


def test_read_xlsx_decodes_excel_escapes_and_rejects_hostile_parts() -> None:
    assert read_xlsx(_xlsx([["a_x000D_b", "c"]])) == [["a\rb", "c"]]
    hostile = io.BytesIO()
    with zipfile.ZipFile(hostile, "w") as zf:
        zf.writestr("xl/worksheets/sheet1.xml", BILLION_LAUGHS)
    with pytest.raises(ValueError, match="DOCTYPE or entities"):
        read_xlsx(hostile.getvalue())

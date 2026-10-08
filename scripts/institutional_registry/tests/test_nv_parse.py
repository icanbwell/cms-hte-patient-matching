"""Offline tests for Nevada's page parsing and address splitting (no network)."""

import pytest

from scripts.institutional_registry.states import nv

_TYPE = "RESIDENTIAL FACILITY FOR GROUPS"


def _row(*cells: str) -> str:
    return "<tr>" + "".join(f"<td>{c}</td>" for c in cells) + "</tr>"


# The 14 cells the grid renders per facility (verified against the live page).
FACILITY = [
    "A AND J CARE HOME LLC",
    _TYPE,
    "11168-AGC-3",
    "Active",
    "12/31/2026",
    "N",
    "5217 W. GOWAN RD. LAS VEGAS, NV 89130",
    "702-645-2291",
    "09/12/2023",
    "SEAN STERN",
    "Administrator",
    "7",
    "View Detail",
    "",
]


def test_data_rows_keeps_only_full_facility_rows() -> None:
    page = (
        "<table>"
        + _row("Credential Number", "", "Credential Type", "All")  # filter header row
        + _row(*FACILITY)
        + _row(
            *[*FACILITY[:1], "SKILLED NURSING FACILITY", *FACILITY[2:]]
        )  # other license type
        + _row("1", "2", "3")  # pager row
        + "</table>"
    )
    rows = nv._data_rows(page)
    assert len(rows) == 1
    assert rows[0][2] == "11168-AGC-3"


def test_data_rows_strips_tags_and_collapses_whitespace() -> None:
    cells = list(FACILITY)
    cells[0] = "<a href='x'>A  AND\n J  CARE</a>"
    assert nv._data_rows(_row(*cells))[0][0] == "A AND J CARE"


@pytest.mark.parametrize(
    ("full", "street", "city", "zip5"),
    [
        (
            "5217 W. GOWAN RD. LAS VEGAS, NV 89130",
            "5217 W Gowan Rd",
            "Las Vegas",
            "89130",
        ),
        ("123 MAIN ST. RENO, NV 89501", "123 Main St", "Reno", "89501"),
        ("45 ELM AVE HENDERSON, NV 89002-1234", "45 Elm Ave", "Henderson", "89002"),
    ],
)
def test_split_address(full: str, street: str, city: str, zip5: str) -> None:
    assert nv._split_address(full) == {"street": street, "city": city, "zip": zip5}


def test_split_address_rejects_what_it_cannot_parse() -> None:
    with pytest.raises(ValueError, match="could not split address"):
        nv._split_address("no address here")

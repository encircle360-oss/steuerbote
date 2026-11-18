"""The example month of the specification of the XML, and helpers to read what the tests write."""

from datetime import date
from decimal import Decimal
from pathlib import Path

from lxml import etree

from steuerbote.elster.ustva_xml import Filer, Voranmeldung, to_import_file
from steuerbote.ustva import Mapping, Period, calculate

FIXTURES = Path(__file__).parent / "fixtures"
CREATED = date(2026, 11, 18)
OCTOBER = Period.month(2026, 10)

# The test Steuernummer 198/113/10010 of Bayern (ERiC-Entwicklerhandbuch 44.3.6.0, table 6-5) for ELSTER.
TEST_STEUERNUMMER = "9198011310010"

EXAMPLE_MONTH = {
	"81": Decimal("1000"),
	"21": Decimal("2000"),
	"45": Decimal("500"),
	"46": Decimal("300"),
	"47": Decimal("57.00"),
	"66": Decimal("95.00"),
	"67": Decimal("57.00"),
	"83": Decimal("95.00"),
}


# The amounts of Datenarten/ElsterAnmeldung/UStVA/Beispiele/UStVA_2026.xml in the ERiC documentation 44.3.6.0:
# 19 % of 150000 and 7 % of 25000, plus 1600.00 and 200.00, less 15000.00.
OFFICIAL_EXAMPLE = {
	"35": Decimal("10000"),
	"36": Decimal("1600.00"),
	"66": Decimal("15000.00"),
	"69": Decimal("200.00"),
	"81": Decimal("150000"),
	"86": Decimal("25000"),
	"83": Decimal("17050.00"),
}


def filer(**fields: object) -> Filer:
	values: dict = {
		"steuernummer": TEST_STEUERNUMMER,
		"name": "Beispiel GmbH",
		"street": "Hauptstraße 1",
		"postal_code": "80331",
		"city": "München",
		**fields,
	}
	return Filer(**values)


def voranmeldung(
	amounts: dict[str, Decimal] | None = None, period: Period = OCTOBER, **fields
) -> Voranmeldung:
	return Voranmeldung(period, EXAMPLE_MONTH if amounts is None else amounts, **fields)


def parse(document: bytes | str) -> etree._Element:
	return etree.fromstring(document.encode("utf-8") if isinstance(document, str) else document)


def children(element: etree._Element) -> list[tuple[str, str | None]]:
	"""Name and text of each child, in the order of the document."""
	return [(etree.QName(child).localname, child.text) for child in element]


def elements(document: bytes | str) -> list[tuple[str, str | None]]:
	"""Name and text of each child of Umsatzsteuervoranmeldung, in the order of the document."""
	(anmeldung,) = parse(document).iter("{*}Umsatzsteuervoranmeldung")
	return children(anmeldung)


def write(amounts: dict[str, Decimal], **fields) -> dict[str, str]:
	"""The Kennzahlen of the import file of October 2026 with these amounts."""
	document = to_import_file(filer(), voranmeldung(amounts, **fields), CREATED)
	return {name: text for name, text in elements(document) if name.startswith("Kz")}


def balance(amounts: dict[str, Decimal]) -> Decimal:
	"""Kz 83 of the amounts as the core computes it."""
	return calculate((), Mapping(chart="", rules=(), year=2026), extra_values=amounts).kz83

"""An invented Zusammenfassende Meldung for October 2026, filed on 20 November 2026, and helpers to read its XML."""

from datetime import date
from decimal import Decimal

from lxml import etree

from steuerbote.elster.zm_xml import NAMESPACE, Unternehmer, Zm, to_nutzdaten
from steuerbote.zm.lines import Art, Meldezeile
from steuerbote.zm.period import ReportingPeriod

CREATED = date(2026, 11, 20)
OCTOBER = ReportingPeriod.month(2026, 10)

# Invented numbers in the form of their country.
OWN_VAT_ID = "DE123456789"
AUSTRIA = "ATU12345678"
FRANCE = "FR12345678901"
NORTHERN_IRELAND = "XI123456789"

LINES = (
	Meldezeile(AUSTRIA, Art.L, Decimal("12000")),
	Meldezeile(FRANCE, Art.S, Decimal("3500")),
	Meldezeile(NORTHERN_IRELAND, Art.L, Decimal("-250")),
)


def line(vat_id: str, art: Art, amount: str) -> Meldezeile:
	return Meldezeile(vat_id, art, Decimal(amount))


def unternehmer(**fields: object) -> Unternehmer:
	values: dict = {
		"ust_idnr": OWN_VAT_ID,
		"name": "Beispiel GmbH",
		"street": "Hauptstraße 1",
		"postal_code": "80331",
		"city": "München",
		**fields,
	}
	return Unternehmer(**values)


def zm(
	lines: tuple[Meldezeile, ...] | list[Meldezeile] = LINES, period: ReportingPeriod = OCTOBER, **fields
) -> Zm:
	return Zm(period, tuple(lines), **fields)


def nutzdaten(statement: Zm | None = None, created: date = CREATED, **fields: object) -> str:
	return to_nutzdaten(unternehmer(**fields), zm() if statement is None else statement, created)


def parse(document: str) -> etree._Element:
	return etree.fromstring(document.encode("utf-8"))


def child_names(element: etree._Element) -> list[str]:
	return [etree.QName(child).localname for child in element]


def find(document: str, path: str) -> etree._Element:
	"""The element at the path below zm, written with the local names, such as "unternehmer/knri"."""
	element = parse(document).find("/".join(f"{{{NAMESPACE}}}{name}" for name in path.split("/")))
	assert element is not None, path
	return element


def text(document: str, path: str) -> str | None:
	return find(document, path).text


def zeilen(document: str) -> list[tuple[str, str, str]]:
	"""Art, USt-IdNr. and sum of each zeile, in the order of the document."""
	return [
		(
			zeile.get("umsatzart"),
			zeile.findtext(f"{{{NAMESPACE}}}knre"),
			zeile.findtext(f"{{{NAMESPACE}}}betrag"),
		)
		for zeile in find(document, "unternehmer/zm-zeilen").iter(f"{{{NAMESPACE}}}zeile")
	]

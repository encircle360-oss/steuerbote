"""The Körperschaftsteuer- and the Gewerbesteuererklärung as their print formats show them, without Frappe.

Mein ELSTER imports neither Erklärung (ELSTER-Hilfe „Benutzeranleitung zum Hochladen von Formulardaten“), so the print
format is what is typed in there or checked with the Steuerberatung. print_sections() lays out the Vordrucke a return
files, the same that go into its Nutzdaten (bridge.filed_vordrucke), in the order of the forms: each Vordruck in the
order of the catalogue, which is the order of the schema and of the printed form (steuerbote.kst.form,
steuerbote.gewst.form), and in it each field with its Vordruckzeile and its Beschreibung, which the Jahresdokumentation
also prints as its Drucktext, with the years of the return in place of its placeholders (bridge.shown). The fields of a context that repeats, such as an Anteilseigner of KSt 1 lines 21 to 23b
or a sale of Anlage GK lines 161 to 166a, stand together, instance by instance, numbered as the return numbers them.

Values read as the German forms write them: whole euros with points between the thousands, amounts in cents with a
comma, yes and no in words, days as TT.MM.JJJJ, and the key of a Listenfeld as it is filed. The numbers of the
Anteilseigner go to ELSTER and into no print (bridge.IDENTIFIERS): a body other than the Finanzbehörde may process the
Identifikationsnummer only as far as a transmission to it needs it (§ 139b Absatz 2 Satz 2 Nummer 1 AO).

This module is pure Python and never imports Frappe.
"""

from collections.abc import Collection, Iterable, Mapping
from datetime import date
from decimal import Decimal
from types import MappingProxyType
from typing import Any

from steuerbote.elster.erklaerung import Field, FormCatalogue
from steuerbote.kst.form import Entry, Vordruck
from steuerbote.steuerbote.doctype.corporate_income_tax_return.bridge import shown

WHOLE_EUROS = frozenset({"N", "U", "G", "M"})
CENTS = frozenset({"P", "%", "R", "S"})
TITLES = MappingProxyType(
	{
		"KSt1": "KSt 1",
		"GK": "Anlage GK",
		"ZVE": "Anlage ZVE",
		"Z": "Anlage Z",
		"Verluste": "Anlage Verluste",
		"WA": "Anlage WA",
		"KSt1F": "KSt 1 F",
		"GewSt1A": "GewSt 1 A",
		"BEG": "Anlage BEG",
	}
)
"""The names of the Vordrucke as the print shows them."""


def print_sections(
	catalogue: FormCatalogue,
	vordrucke: Iterable[Vordruck],
	repeats: Collection[str],
	hidden: Collection[str] = frozenset(),
) -> list[dict[str, Any]]:
	"""The sections of the print: one per Vordruck in the order of the catalogue, each with its title and its rows of
	line, Beschreibung, instance and value; ``repeats`` are the contexts that repeat (steuerbote.elster.kst_xml.Schema),
	``hidden`` the fields left out of the print."""
	order = {form.name: rank for rank, form in enumerate(catalogue.forms)}
	fields = {item.feldkennung: shown(item, catalogue.datenart.year) for item in catalogue.fields}
	ranks = _ranks(catalogue)
	sections = []
	for vordruck in sorted(vordrucke, key=lambda item: order[item.form]):
		printed = [entry for entry in vordruck.entries if entry.feldkennung not in hidden]
		placed = sorted(printed, key=lambda entry: _key(fields[entry.feldkennung], entry, ranks, repeats))
		rows = [row for entry in placed if (row := _row(fields[entry.feldkennung], entry)) is not None]
		sections.append({"form": vordruck.form, "title": TITLES[vordruck.form], "rows": rows})
	return sections


RECHTSFORM_FIELDS = frozenset({"E8001105", "E4000501"})
"""The Rechtsform of KSt 1 and of GewSt 1 A, which the print writes with its meaning."""
RECHTSFORM_NAMES: MappingProxyType[str, str] = MappingProxyType(
	{
		"350": "Gesellschaft mit beschränkter Haftung",
		"370": "Unternehmergesellschaft (haftungsbeschränkt)",
	}
)
"""The Rechtsformen Steuerbote files by their keys in the Anleitungen to KSt 1 and GewSt 1 A."""


def value_text(item: Field, value: object) -> str | None:
	"""The value of a field as the print writes it, None for a yes field that says no where the form takes only a yes;
	a Rechtsform with its meaning beside its key."""
	if item.feldkennung in RECHTSFORM_FIELDS and str(value) in RECHTSFORM_NAMES:
		return f"{value} ({RECHTSFORM_NAMES[str(value)]})"
	if isinstance(value, bool):
		if not value and item.format != "Y":
			return None
		return "Ja" if value else "Nein"
	if isinstance(value, Decimal):
		return amount_text(value, item.format)
	if isinstance(value, date):
		return value.strftime("%d.%m." if item.format == "T" else "%d.%m.%Y")
	return str(value)


def amount_text(value: Decimal, formatkennzeichen: str) -> str:
	"""An amount in the German way: whole euros as 1.234, cents as 1.234,56, other numbers with the decimals they
	have."""
	if formatkennzeichen in WHOLE_EUROS:
		digits = 0
	elif formatkennzeichen in CENTS:
		digits = 2
	else:
		digits = max(-value.normalize().as_tuple().exponent, 0)
	shown = f"{value:,.{digits}f}"
	return shown.replace(",", " ").replace(".", ",").replace(" ", ".")


def _row(item: Field, entry: Entry) -> dict[str, str] | None:
	text = value_text(item, entry.value)
	if text is None:
		return None
	return {
		"line": "" if item.line is None else str(item.line),
		"label": item.label,
		"instance": ".".join(str(row + 1) for row in entry.rows),
		"value": text,
	}


def _ranks(catalogue: FormCatalogue) -> Mapping[str, int]:
	"""The rank of each field and each context in the order of the catalogue: a context ranks with its first field."""
	ranks: dict[str, int] = {}
	for rank, item in enumerate(catalogue.fields):
		ranks[item.feldkennung] = rank
		for path in _prefixes(item):
			ranks.setdefault(path, rank)
	return ranks


def _key(item: Field, entry: Entry, ranks: Mapping[str, int], repeats: Collection[str]) -> tuple:
	"""Where a field stands in its Vordruck: by the contexts around it, each with its instance where it repeats, then by
	the field itself, as the Nutzdaten order it (steuerbote.elster.kst_xml)."""
	rows = iter(entry.rows)
	contexts = tuple((ranks[prefix], next(rows, 0) if prefix in repeats else 0) for prefix in _prefixes(item))
	return (*contexts, (ranks[item.feldkennung], 0))


def _prefixes(item: Field) -> tuple[str, ...]:
	names = [part for part in item.context.split("/") if part]
	return tuple("/".join((item.form, *names[: length + 1])) for length in range(len(names)))

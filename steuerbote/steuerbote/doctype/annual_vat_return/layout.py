"""The print of the Umsatzsteuererklärung in the order and wording of form USt 2 A, one layout per year.

2026: Vordruckmuster USt 2 A 2026 of the BMF letter of 29 December 2025 (GZ III C 3 - S 7344/00040/008/034), its
sections A to K with their headings and the headings within them, and the lines 127 to 129 of the Mitwirkung. Each
line prints its number, the Beschreibung of its fields in the Jahresdokumentation E50 2026 (which is the text the
form prints, with $VZ$ for the year), the Kennzahl and the amount of each field: a base in whole euros in the left
column, a tax in euros and cents in the right one, and in lines 105 to 108 the Vorsteuer nachträglich abziehbar on the
left and zurückzuzahlen on the right, as the form has them. Lines 46, 52 and 54 print the paragraph of their sales,
„Umsätze nach § … UStG“. A statement of the company prints its value as the form asks for it: 1 = Ja, X, a day, a
span of days, or the key of a list with its text.

print_sections() takes the values the return files (bridge.filed_values) and the Grundstücke of line 95, and gives
each section with the rows of its lines that hold a value; a section without one prints „Keine Eintragungen“. The
print format „Umsatzsteuererklärung“ shows them; it computes nothing. LAYOUTS holds a layout for each year of
steuerbote/ustjahr/years.py.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from types import MappingProxyType
from typing import Any

from steuerbote.ustjahr.form import Field, Format, Source, catalogue_for

YEAR = "$VZ$"
BASE = "Bemessungsgrundlage ohne Umsatzsteuer EUR"
TAX = "Steuer EUR Ct"
AMOUNT = "Betrag EUR"
LEFT, RIGHT = "left", "right"
YES = "1 = Ja"
CROSS = "X"


@dataclass(frozen=True, slots=True)
class Section:
	"""A section of the form: its letter, its heading, its first and last line, the headings of its columns and the
	headings within it, by the line they stand before."""

	letter: str
	title: str
	first: int
	last: int
	columns: tuple[str, str] = ("", "")
	headings: Mapping[int, tuple[int, str]] = field(default_factory=dict)
	"""Each heading by the line it stands before, with the last line it heads."""


@dataclass(frozen=True, slots=True)
class Layout:
	"""The print of one year: its sections in the order of the form, the column of each amount that is not where its
	format puts it, and the text of each value of a list."""

	sections: tuple[Section, ...]
	columns: Mapping[str, str]
	options: Mapping[str, Mapping[str, str]]


_SECTIONS_2026 = (
	Section("A.", "Allgemeine Angaben", 3, 22),
	Section("", "Ergänzende Angaben zur Steuererklärung", 23, 23),
	Section(
		"B.",
		"Steuerpflichtige Lieferungen, sonstige Leistungen und unentgeltliche Wertabgaben",
		24,
		41,
		(BASE, TAX),
		{
			24: (26, "Umsätze zum allgemeinen Steuersatz"),
			27: (29, "Umsätze zum ermäßigten Steuersatz von 7 %"),
			30: (32, "Umsätze zum ermäßigten Steuersatz von 0 %"),
			34: (36, "Umsätze land- und forstwirtschaftlicher Betriebe nach § 24 UStG"),
			37: (37, "Umsätze nach § 25 UStG (Reiseleistungen)"),
			38: (38, "Umsätze nach § 25a UStG (Differenzbesteuerung)"),
			39: (
				39,
				"Wechsel von der Kleinunternehmer-Regelung (§ 19 UStG) zur Regelbesteuerung beziehungsweise "
				"Durchschnittssatzbesteuerung (§ 24 UStG)",
			),
		},
	),
	Section(
		"C.",
		"Steuerfreie Lieferungen, sonstige Leistungen und unentgeltliche Wertabgaben",
		42,
		54,
		(BASE, ""),
		{
			42: (
				44,
				"Steuerfreie Umsätze mit Vorsteuerabzug: a) Innergemeinschaftliche Lieferungen (§ 4 Nummer 1 "
				"Buchstabe b UStG)",
			),
			45: (
				50,
				"Steuerfreie Umsätze mit Vorsteuerabzug: b) Weitere steuerfreie Umsätze mit Vorsteuerabzug (z. B. nach "
				"§ 4 Nummer 1 Buchstabe a, 2 bis 7 UStG)",
			),
			51: (
				52,
				"Steuerfreie Umsätze ohne Vorsteuerabzug: a) nicht zum Gesamtumsatz (§ 19 Absatz 2 UStG) gehörend",
			),
			53: (
				54,
				"Steuerfreie Umsätze ohne Vorsteuerabzug: b) zum Gesamtumsatz (§ 19 Absatz 2 UStG) gehörend",
			),
		},
	),
	Section(
		"D.",
		"Innergemeinschaftliche Erwerbe",
		55,
		62,
		(BASE, TAX),
		{57: (61, "Steuerpflichtige innergemeinschaftliche Erwerbe (§ 1a UStG)")},
	),
	Section("E.", "Steuerschuldner bei Auslagerung (§ 27 Absatz 40a UStG)", 63, 64, (BASE, TAX)),
	Section(
		"F.",
		"Innergemeinschaftliche Dreiecksgeschäfte (§ 25b UStG)",
		65,
		70,
		(BASE, TAX),
		{66: (69, "Lieferungen, für die der letzte Abnehmer die Umsatzsteuer schuldet")},
	),
	Section("G.", "Leistungsempfänger als Steuerschuldner (§ 13b UStG)", 71, 74, (BASE, TAX)),
	Section("H.", "Ergänzende Angaben zu Umsätzen", 75, 84, (AMOUNT, "")),
	Section(
		"I.",
		"Abziehbare Vorsteuerbeträge (ohne die Berichtigung nach § 15a UStG)",
		85,
		94,
		("", TAX),
		{94: (94, "Ergänzende Angabe")},
	),
	Section(
		"J.",
		"Berichtigung des Vorsteuerabzugs (§ 15a UStG)",
		95,
		108,
		("nachträglich abziehbar EUR Ct", "zurückzuzahlen EUR Ct"),
		{
			96: (
				98,
				f"Haben sich im Jahr {YEAR} die für den ursprünglichen Vorsteuerabzug maßgebenden Verhältnisse "
				"geändert bei",
			),
			99: (
				104,
				"Die Verhältnisse, die ursprünglich für die Beurteilung des Vorsteuerabzugs maßgebend waren, haben sich "
				"seitdem geändert durch:",
			),
			105: (108, "Vorsteuerberichtigungsbeträge"),
		},
	),
	Section("K.", "Berechnung der zu entrichtenden Umsatzsteuer", 109, 126, ("", TAX)),
	Section("", "Mitwirkung", 127, 129),
)

LAYOUTS: MappingProxyType[int, Layout] = MappingProxyType(
	{
		2026: Layout(
			sections=_SECTIONS_2026,
			columns=MappingProxyType(
				{
					"E3008701": LEFT,
					"E3008702": RIGHT,
					"E3008801": LEFT,
					"E3008802": RIGHT,
					"E3008803": LEFT,
					"E3008804": RIGHT,
					"E3008901": LEFT,
					"E3008902": RIGHT,
				}
			),
			options=MappingProxyType(
				{
					"E3002203": MappingProxyType(
						{
							"1": "vereinbarten Entgelten (§ 16 Absatz 1 Satz 1 UStG)",
							"2": "vereinnahmten Entgelten (§ 20 UStG)",
							"3": (
								"vereinnahmten Entgelten nur für einzelne Unternehmensteile (§ 20 Satz 1 Nummer 2 in "
								"Verbindung mit Satz 2 oder § 20 Satz 1 Nummer 3 UStG)"
							),
						}
					),
					"E3002201": MappingProxyType(
						{
							"1": "konnten steuererhebliche Sachverhalte nicht erklärt werden.",
							"2": "wird bewusst eine von der Verwaltungsmeinung abweichende Rechtsauffassung vertreten.",
							"3": "sollen Sachverhalte personell vertieft geprüft werden.",
							"4": "liegen mehrere der vorgenannten Gründe vor (Mehrfachauswahl).",
						}
					),
				}
			),
		),
	}
)


def print_sections(
	year: int, values: Mapping[str, object], grundstuecke: Sequence[Mapping[str, object]] = ()
) -> list[dict[str, Any]]:
	"""The sections of the form with the rows of their lines that hold a value, each row a dict for the print
	format: ``line``, ``label``, ``left_kz`` and ``left``, ``right_kz`` and ``right`` for the amounts, ``text`` for a
	statement, ``heading`` for a heading within the section, and ``sum`` for a sum of the form."""
	layout = LAYOUTS[year]
	catalogue = catalogue_for(year)
	by_line: dict[int, list[Field]] = {}
	for entry in catalogue.fields:
		by_line.setdefault(entry.line, []).append(entry)
	sections = []
	for section in layout.sections:
		rows: list[dict[str, Any]] = []
		pending: str | None = None
		until = 0
		for line in range(section.first, section.last + 1):
			if line in section.headings:
				until, text = section.headings[line]
				pending = text.replace(YEAR, str(year))
			elif line > until:
				pending = None
			found = _rows(layout, year, line, by_line.get(line, []), values, grundstuecke)
			if found and pending is not None:
				rows.append({"heading": pending})
				pending = None
			rows.extend(found)
		sections.append(
			{
				"letter": section.letter,
				"title": section.title,
				"left": section.columns[0],
				"right": section.columns[1],
				"rows": rows,
			}
		)
	return sections


def german(amount: Decimal, decimals: int) -> str:
	"""An amount as the form prints it: a dot between the thousands and a comma before the cents, as 1.234,56."""
	shown = format(amount, f",.{decimals}f")
	return shown.replace(",", " ").replace(".", ",").replace(" ", ".")


def _rows(
	layout: Layout,
	year: int,
	line: int,
	fields: list[Field],
	values: Mapping[str, object],
	grundstuecke: Sequence[Mapping[str, object]],
) -> list[dict[str, Any]]:
	paragraphs = {entry.paragraph for entry in fields if entry.paragraph}
	amounts = [
		entry for entry in fields if entry.format.amount and entry.repeat == 1 and entry.element in values
	]
	rows = []
	if amounts:
		row: dict[str, Any] = {"line": line, "label": _label(amounts[0], values, year), "sum": False}
		for entry in amounts:
			side = layout.columns.get(entry.element) or (LEFT if entry.format.whole_euros else RIGHT)
			row[f"{side}_kz"] = entry.kennzahl or ""
			row[side] = _amount(entry, values[entry.element])
			row["sum"] = row["sum"] or entry.source in (Source.SUM, Source.SOLL)
		rows.append(row)
	for entry in fields:
		if (
			entry.format.amount
			or entry.repeat > 1
			or entry.element in paragraphs
			or entry.element not in values
		):
			continue
		rows.append(
			{
				"line": line,
				"label": entry.label.replace(YEAR, str(year)),
				"right_kz": entry.kennzahl or "",
				"text": _statement(layout, entry, values[entry.element]),
			}
		)
	repeated = [entry for entry in fields if entry.repeat > 1]
	if repeated:
		for index, grundstueck in enumerate(grundstuecke, start=1):
			parts = [
				f"{entry.label}: {_statement(layout, entry, grundstueck[entry.element])}"
				for entry in repeated
				if entry.element in grundstueck
			]
			rows.append({"line": line, "label": f"Grundstück {index}", "text": "; ".join(parts)})
	return rows


def _label(entry: Field, values: Mapping[str, object], year: int) -> str:
	label = entry.label.replace(YEAR, str(year))
	if entry.paragraph is not None and entry.paragraph in values:
		return f"{label} {values[entry.paragraph]} UStG"
	return label


def _amount(entry: Field, value: object) -> str:
	return german(Decimal(str(value)), 0 if entry.format.whole_euros else 2)


def _statement(layout: Layout, entry: Field, value: object) -> str:
	if entry.format is Format.YES:
		return YES
	if entry.format is Format.CROSS:
		return CROSS
	if entry.format is Format.DATE and isinstance(value, date):
		return value.strftime("%d.%m.%Y")
	if entry.format is Format.DAYS and isinstance(value, tuple):
		start, end = value
		return f"vom {start:%d.%m.} bis zum {end:%d.%m.}"
	if entry.format is Format.LIST:
		text = layout.options.get(entry.element, {}).get(str(value))
		return f"{value} = {text}" if text else str(value)
	if entry.format.amount:
		return _amount(entry, value)
	return str(value)

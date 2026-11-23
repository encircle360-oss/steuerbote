"""The print of the Umsatzsteuererklärung in the order and wording of form USt 2 A, without a bench."""

from datetime import date
from decimal import Decimal
from unittest import TestCase

from steuerbote.steuerbote.doctype.annual_vat_return import layout
from steuerbote.steuerbote.doctype.annual_vat_return.layout import LAYOUTS, german, print_sections
from steuerbote.ustjahr.calculation import entries
from steuerbote.ustjahr.form import catalogue_for
from steuerbote.ustjahr.years import YEARS

YEAR = 2026


def filed(amounts: dict[str, str], soll: str = "0", **details: object) -> dict[str, object]:
	"""The values a return of 2026 files: the amounts through entries(), and the details as given."""
	values = dict(
		entries(catalogue_for(YEAR), {key: Decimal(value) for key, value in amounts.items()}, Decimal(soll))
	)
	values.update(details)
	return values


def section(sections: list[dict], title: str) -> dict:
	(found,) = (entry for entry in sections if entry["title"] == title)
	return found


class LayoutTableTest(TestCase):
	def test_holds_exactly_the_years_of_the_annual_return(self):
		self.assertEqual(sorted(LAYOUTS), list(YEARS))

	def test_the_sections_follow_the_form_and_hold_every_line_once(self):
		sections = LAYOUTS[YEAR].sections
		self.assertEqual(
			[(entry.letter, entry.first, entry.last) for entry in sections],
			[
				("A.", 3, 22),
				("", 23, 23),
				("B.", 24, 41),
				("C.", 42, 54),
				("D.", 55, 62),
				("E.", 63, 64),
				("F.", 65, 70),
				("G.", 71, 74),
				("H.", 75, 84),
				("I.", 85, 94),
				("J.", 95, 108),
				("K.", 109, 126),
				("", 127, 129),
			],
		)
		lines = {field.line for field in catalogue_for(YEAR).fields}
		covered = [line for entry in sections for line in range(entry.first, entry.last + 1)]
		self.assertEqual(len(covered), len(set(covered)))
		self.assertLessEqual(lines, set(covered))

	def test_the_headings_of_the_sections_are_those_of_the_form(self):
		titles = [entry.title for entry in LAYOUTS[YEAR].sections]
		self.assertEqual(
			titles,
			[
				"Allgemeine Angaben",
				"Ergänzende Angaben zur Steuererklärung",
				"Steuerpflichtige Lieferungen, sonstige Leistungen und unentgeltliche Wertabgaben",
				"Steuerfreie Lieferungen, sonstige Leistungen und unentgeltliche Wertabgaben",
				"Innergemeinschaftliche Erwerbe",
				"Steuerschuldner bei Auslagerung (§ 27 Absatz 40a UStG)",
				"Innergemeinschaftliche Dreiecksgeschäfte (§ 25b UStG)",
				"Leistungsempfänger als Steuerschuldner (§ 13b UStG)",
				"Ergänzende Angaben zu Umsätzen",
				"Abziehbare Vorsteuerbeträge (ohne die Berichtigung nach § 15a UStG)",
				"Berichtigung des Vorsteuerabzugs (§ 15a UStG)",
				"Berechnung der zu entrichtenden Umsatzsteuer",
				"Mitwirkung",
			],
		)

	def test_each_heading_within_a_section_heads_lines_of_it(self):
		for entry in LAYOUTS[YEAR].sections:
			for first, (last, _text) in entry.headings.items():
				with self.subTest(section=entry.title, line=first):
					self.assertLessEqual(entry.first, first)
					self.assertLessEqual(first, last)
					self.assertLessEqual(last, entry.last)


class AmountsTest(TestCase):
	def test_a_base_prints_in_whole_euros_on_the_left_and_its_tax_in_cents_on_the_right(self):
		sections = print_sections(YEAR, filed({"E3003303": "12345", "E3003304": "2345.55"}))
		rows = section(
			sections, "Steuerpflichtige Lieferungen, sonstige Leistungen und unentgeltliche Wertabgaben"
		)["rows"]
		self.assertEqual(
			rows,
			[
				{"heading": "Umsätze zum allgemeinen Steuersatz"},
				{
					"line": 24,
					"label": "Lieferungen und sonstige Leistungen zu 19 %",
					"sum": False,
					"left_kz": "177",
					"left": "12.345",
					"right_kz": "",
					"right": "2.345,55",
				},
				{
					"line": 41,
					"label": "Summe der Steuer (zu übertragen in Zeile 109)",
					"sum": True,
					"right_kz": "",
					"right": "2.345,55",
				},
			],
		)

	def test_names_the_columns_of_each_section_as_the_form_heads_them(self):
		sections = print_sections(YEAR, filed({}))
		self.assertEqual(
			(sections[2]["left"], sections[2]["right"]),
			("Bemessungsgrundlage ohne Umsatzsteuer EUR", "Steuer EUR Ct"),
		)
		self.assertEqual(
			(sections[10]["left"], sections[10]["right"]),
			("nachträglich abziehbar EUR Ct", "zurückzuzahlen EUR Ct"),
		)
		self.assertEqual((sections[0]["left"], sections[0]["right"]), ("", ""))

	def test_a_heading_stands_only_before_a_line_it_heads(self):
		rows = section(
			print_sections(YEAR, filed({"E3005901": "19.00"})),
			"Steuerpflichtige Lieferungen, sonstige Leistungen und unentgeltliche Wertabgaben",
		)["rows"]
		self.assertEqual([row.get("heading") or row["line"] for row in rows], [40, 41])

	def test_lines_46_52_and_54_print_the_paragraph_of_their_sales(self):
		values = filed(
			{"E3103902": "500", "E3104502": "300"}, E3103901="4 Nummer 2", E3104501="8 Buchstabe a"
		)
		rows = section(
			print_sections(YEAR, values),
			"Steuerfreie Lieferungen, sonstige Leistungen und unentgeltliche Wertabgaben",
		)["rows"]
		labels = [row.get("label") for row in rows if row.get("line") in (46, 52)]
		self.assertEqual(labels, ["Umsätze nach § 4 Nummer 2 UStG", "nach § 4 Nummer 8 Buchstabe a UStG"])
		self.assertNotIn("text", [key for row in rows for key in row])

	def test_lines_105_to_108_print_what_is_deductible_on_the_left_and_what_is_repayable_on_the_right(self):
		values = filed({"E3008701": "100.00", "E3008802": "40.00"})
		rows = section(print_sections(YEAR, values), "Berichtigung des Vorsteuerabzugs (§ 15a UStG)")["rows"]
		amounts = {row["line"]: (row.get("left"), row.get("right")) for row in rows if "line" in row}
		self.assertEqual(amounts, {105: ("100,00", None), 106: (None, "40,00"), 108: ("100,00", "40,00")})
		self.assertEqual(rows[0], {"heading": "Vorsteuerberichtigungsbeträge"})

	def test_section_k_always_prints_kz_816_line_125_and_kz_820_and_marks_them_as_sums(self):
		rows = section(
			print_sections(YEAR, filed({"E3006201": "100.00"}, soll="150.00")),
			"Berechnung der zu entrichtenden Umsatzsteuer",
		)["rows"]
		self.assertEqual(
			[(row["line"], row["right_kz"], row["right"], row["sum"]) for row in rows],
			[
				(115, "", "100,00", True),
				(117, "", "-100,00", True),
				(122, "", "-100,00", True),
				(124, "816", "-100,00", True),
				(125, "", "150,00", True),
				(126, "820", "-250,00", True),
			],
		)
		self.assertEqual(rows[4]["label"], "Vorauszahlungssoll 2026 (einschließlich Sondervorauszahlung)")

	def test_a_section_without_a_value_has_no_rows(self):
		sections = print_sections(YEAR, filed({"E3006201": "100.00"}))
		empty = [entry["letter"] for entry in sections if not entry["rows"]]
		self.assertEqual(empty, ["A.", "", "B.", "C.", "D.", "E.", "F.", "G.", "H.", "J.", ""])

	def test_a_year_without_amounts_prints_kz_177_with_zero(self):
		"""entries() files Kz 177 = 0 for a year without amounts (rule 30449)."""
		rows = section(
			print_sections(YEAR, filed({})),
			"Steuerpflichtige Lieferungen, sonstige Leistungen und unentgeltliche Wertabgaben",
		)["rows"]
		self.assertEqual(
			[(row.get("line"), row.get("left"), row.get("right")) for row in rows[1:]],
			[(24, "0", "0,00"), (41, None, "0,00")],
		)


class StatementsTest(TestCase):
	def test_a_statement_prints_its_value_as_the_form_asks_for_it(self):
		values = filed(
			{},
			E3000601=True,
			E3000901="Muster GmbH",
			E3001601=date(2026, 4, 1),
			E3001401=(date(2026, 5, 4), date(2026, 12, 31)),
			E3002203="1",
			E3002201="9",
			E3007801=True,
		)
		sections = print_sections(YEAR, values)
		general = {row["line"]: row for row in section(sections, "Allgemeine Angaben")["rows"]}
		self.assertEqual(
			{line: row["text"] for line, row in general.items()},
			{
				3: "1 = Ja",
				5: "Muster GmbH",
				18: "01.04.2026",
				19: "vom 04.05. bis zum 31.12.",
				21: "1 = vereinbarten Entgelten (§ 16 Absatz 1 Satz 1 UStG)",
			},
		)
		self.assertEqual((general[3]["right_kz"], general[21]["right_kz"]), ("110", "133"))
		(supplementary,) = section(sections, "Ergänzende Angaben zur Steuererklärung")["rows"]
		self.assertEqual(supplementary["text"], "9")
		rows = section(sections, "Berichtigung des Vorsteuerabzugs (§ 15a UStG)")["rows"]
		self.assertEqual(
			rows,
			[
				{
					"heading": (
						"Die Verhältnisse, die ursprünglich für die Beurteilung des Vorsteuerabzugs maßgebend waren, "
						"haben sich seitdem geändert durch:"
					)
				},
				{"line": 99, "label": "Veräußerung", "right_kz": "", "text": "X"},
			],
		)

	def test_a_key_of_a_list_prints_with_its_text(self):
		values = filed({}, E3002201="2", E3002202="Abweichende Rechtsauffassung")
		rows = section(print_sections(YEAR, values), "Ergänzende Angaben zur Steuererklärung")["rows"]
		self.assertEqual(
			[row["text"] for row in rows],
			[
				"2 = wird bewusst eine von der Verwaltungsmeinung abweichende Rechtsauffassung vertreten.",
				"Abweichende Rechtsauffassung",
			],
		)

	def test_the_year_replaces_the_placeholder_of_the_form(self):
		values = filed({}, E3007301=True, E3007601=True)
		rows = section(print_sections(YEAR, values), "Berichtigung des Vorsteuerabzugs (§ 15a UStG)")["rows"]
		self.assertEqual(
			rows[0]["label"],
			"Sind im Kalenderjahr 2026 Grundstücke, Grundstücksteile, Gebäude oder Gebäudeteile, für die Vorsteuer abgezogen worden ist, erstmals tatsächlich verwendet worden?",
		)
		self.assertEqual(
			rows[1],
			{
				"heading": "Haben sich im Jahr 2026 die für den ursprünglichen Vorsteuerabzug maßgebenden Verhältnisse geändert bei"
			},
		)

	def test_line_95_prints_each_grundstueck(self):
		grundstuecke = (
			{
				"E3007401": "Musterweg 12, München",
				"E3007402": date(2026, 3, 1),
				"E3007404": Decimal("60"),
				"E3007405": Decimal("19000"),
			},
			{"E3007403": "Büro"},
		)
		rows = section(
			print_sections(YEAR, filed({}, E3007301=True), grundstuecke),
			"Berichtigung des Vorsteuerabzugs (§ 15a UStG)",
		)["rows"]
		first = "; ".join(
			(
				"Lage des Grundstücks oder Gebäudes: Musterweg 12, München",
				"Zeitpunkt der erstmaligen tatsächlichen Verwendung: 01.03.2026",
				"Umfang der Verwendung im Erstjahr: 60,00",
				"insgesamt angefallene Vorsteuer: 19.000",
			)
		)
		self.assertEqual(
			[(row["label"], row["text"]) for row in rows[1:]],
			[("Grundstück 1", first), ("Grundstück 2", "Art der Verwendung im Erstjahr: Büro")],
		)

	def test_the_mitwirkung_prints_lines_127_and_128(self):
		values = filed({}, E3002602=True, E3002501="Steuerkanzlei Beispiel")
		rows = section(print_sections(YEAR, values), "Mitwirkung")["rows"]
		self.assertEqual(
			[(row["line"], row["text"]) for row in rows], [(127, "1 = Ja"), (128, "Steuerkanzlei Beispiel")]
		)


class GermanTest(TestCase):
	def test_prints_amounts_with_dots_between_the_thousands_and_a_decimal_comma(self):
		self.assertEqual(german(Decimal("1234567.5"), 2), "1.234.567,50")
		self.assertEqual(german(Decimal("-1234"), 0), "-1.234")
		self.assertEqual(german(Decimal("0"), 2), "0,00")

	def test_a_statement_of_an_amount_prints_as_an_amount(self):
		field = catalogue_for(YEAR).field("E3007405")
		self.assertEqual(layout._statement(LAYOUTS[YEAR], field, Decimal("2500")), "2.500")

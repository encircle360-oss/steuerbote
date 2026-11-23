"""The Körperschaftsteuer- and the Gewerbesteuererklärung as their print formats lay them out, without a bench."""

from datetime import date
from decimal import Decimal
from unittest import TestCase

from steuerbote.elster import gewst_xml, kst_xml
from steuerbote.elster.erklaerung import Field
from steuerbote.gewst.form import catalogue_for as gewst_catalogue
from steuerbote.kst.form import Entry, Vordruck, catalogue_for
from steuerbote.steuerbote.doctype.corporate_income_tax_return import bridge, layout
from steuerbote.steuerbote.doctype.corporate_income_tax_return import test_bridge as corporate
from steuerbote.steuerbote.doctype.trade_tax_return import test_bridge as trade

YEAR = 2026
REPEATS = kst_xml.schema_for(YEAR).repeats


def field(format: str, line: object = "1") -> Field:
	options = ("1", "2") if format == "H" else ()
	return Field(
		"KSt1",
		"",
		"E8000101",
		"Bezeichnung",
		format,
		line,
		length=10 if format == "C" else None,
		options=options,
	)


def rows_of(sections, form: str) -> list[tuple[str, str, str]]:
	(section,) = (section for section in sections if section["form"] == form)
	return [(row["line"], row["instance"], row["value"]) for row in section["rows"]]


class SectionsTest(TestCase):
	def setUp(self):
		computation = corporate.compute()
		self.filed = bridge.filed_vordrucke(
			corporate.RETURN, corporate.reported(computation.lines), corporate.SETTINGS
		)
		self.sections = layout.print_sections(catalogue_for(YEAR), self.filed, REPEATS, bridge.IDENTIFIERS)

	def test_one_section_per_vordruck_in_the_order_of_the_forms(self):
		self.assertEqual(
			[(section["form"], section["title"]) for section in self.sections],
			[
				("KSt1", "KSt 1"),
				("GK", "Anlage GK"),
				("ZVE", "Anlage ZVE"),
				("Z", "Anlage Z"),
				("WA", "Anlage WA"),
				("KSt1F", "KSt 1 F"),
			],
		)
		shuffled = layout.print_sections(catalogue_for(YEAR), reversed(self.filed), REPEATS)
		self.assertEqual(
			[section["form"] for section in shuffled], [section["form"] for section in self.sections]
		)

	def test_each_row_has_its_line_beschreibung_instance_and_value(self):
		(section,) = (section for section in self.sections if section["form"] == "ZVE")
		self.assertEqual(
			section["rows"][-1],
			{
				"line": "71",
				"label": "Körperschaftsteuer (15 % des Betrages laut Vorspalte)",
				"instance": "",
				"value": "16.680",
			},
		)

	def test_the_shareholders_stand_together_instance_by_instance(self):
		rows = rows_of(self.sections, "KSt1")
		self.assertEqual(
			[row for row in rows if row[1]],
			[
				("22c", "1", "Erika Muster"),
				("22d", "1", "Musterweg 2"),
				("22e", "1", "12345 Musterstadt"),
				("23", "1.1", "25.000,00"),
				("23a", "1.1", "100"),
				("23b", "1.1", "01.01.2026"),
				("23b", "1.1", "31.12.2026"),
			],
		)
		self.assertEqual(rows[0], ("", "", "Ja"))
		self.assertEqual(rows[-1], ("27", "", "Nein"))

	def test_each_sale_stands_with_its_name_day_and_result(self):
		rows = [row for row in rows_of(self.sections, "GK") if row[0] in ("162", "162a", "166", "166a")]
		self.assertEqual(
			rows,
			[
				("162", "1", "Delta AG"),
				("162a", "1", "04.05.2026"),
				("166", "1", "30.000,00"),
				("162", "2", "Epsilon GmbH"),
				("162a", "2", "30.09.2026"),
				("166a", "2", "12.000,00"),
			],
		)

	def test_the_years_of_the_return_stand_in_place_of_the_placeholders(self):
		(section,) = (section for section in self.sections if section["form"] == "Z")
		labels = [row["label"] for row in section["rows"]]
		self.assertIn("im Wirtschaftsjahr 2025/2026 geleistete Zuwendungen", labels[3])
		self.assertFalse(
			any(
				"$VZ" in label
				for section in self.sections
				for label in (row["label"] for row in section["rows"])
			)
		)

	def test_the_numbers_of_the_shareholders_go_into_no_print(self):
		person = corporate.shareholder(tax_number="9198011310010", idnr="12345678903")
		filed = (Vordruck("KSt1", tuple(bridge.shareholder_entries(corporate.RETURN, (person,)))),)
		printed = layout.print_sections(catalogue_for(YEAR), filed, REPEATS, bridge.IDENTIFIERS)
		values = [row["value"] for row in printed[0]["rows"]]
		self.assertNotIn("12345678903", values)
		self.assertNotIn("9198011310010", values)
		self.assertIn(
			"12345678903",
			[row["value"] for row in layout.print_sections(catalogue_for(YEAR), filed, REPEATS)[0]["rows"]],
		)

	def test_a_yes_field_that_says_no_is_left_out(self):
		filed = (Vordruck("KSt1", (Entry("E8000016", False), Entry("E8001007", False))),)
		(section,) = layout.print_sections(catalogue_for(YEAR), filed, REPEATS)
		self.assertEqual([(row["line"], row["value"]) for row in section["rows"]], [("17", "Nein")])

	def test_lays_out_the_gewerbesteuererklaerung_with_its_anlagen_beg(self):
		computation = trade.compute()
		filed = trade.bridge.filed_vordrucke(
			trade.RETURN,
			trade.reported(computation.lines),
			computation.holdings,
			computation.municipalities,
			corporate.RETURN.donations,
			trade.SETTINGS,
		)
		sections = layout.print_sections(gewst_catalogue(YEAR), filed, gewst_xml.schema_for(YEAR).repeats)
		self.assertEqual(
			[(section["form"], section["title"]) for section in sections],
			[("GewSt1A", "GewSt 1 A"), ("BEG", "Anlage BEG")],
		)
		rows = rows_of(sections, "GewSt1A")
		self.assertIn(("26", "", "Nein"), rows)
		self.assertIn(("92a", "1", "Musterverein e. V."), rows)
		self.assertEqual(rows_of(sections, "BEG")[0], ("2", "", "Beta GmbH"))


class ValuesTest(TestCase):
	"""The values as the German forms write them."""

	def test_yes_and_no(self):
		self.assertEqual(layout.value_text(field("X"), True), "Ja")
		self.assertEqual(layout.value_text(field("Y"), True), "Ja")
		self.assertEqual(layout.value_text(field("Y"), False), "Nein")
		self.assertIsNone(layout.value_text(field("X"), False))
		self.assertIsNone(layout.value_text(field("J"), False))

	def test_amounts(self):
		for format, value, text in (
			("N", Decimal("-1234567"), "-1.234.567"),
			("U", Decimal("0"), "0"),
			("G", Decimal("1000.00"), "1.000"),
			("P", Decimal("1234.5"), "1.234,50"),
			("%", Decimal("12"), "12,00"),
			("R", Decimal("0.07"), "0,07"),
			("F", Decimal("0.5000"), "0,5"),
			("F", Decimal("100"), "100"),
			("V", Decimal("-12.25"), "-12,25"),
		):
			with self.subTest(format=format, value=value):
				self.assertEqual(layout.value_text(field(format), value), text)

	def test_days_and_texts(self):
		self.assertEqual(layout.value_text(field("D"), date(2026, 3, 1)), "01.03.2026")
		self.assertEqual(layout.value_text(field("T"), date(2026, 3, 1)), "01.03.")
		self.assertEqual(layout.value_text(field("C"), "Musterstadt"), "Musterstadt")
		self.assertEqual(layout.value_text(field("H"), "2"), "2")

	def test_a_field_without_a_line_prints_none(self):
		(section,) = layout.print_sections(
			catalogue_for(YEAR), (Vordruck("KSt1", (Entry("E8000016", True),)),), REPEATS
		)
		self.assertEqual(section["rows"][0]["line"], "")

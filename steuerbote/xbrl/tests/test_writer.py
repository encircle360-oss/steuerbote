"""The instance of a report, against the mini taxonomy (steuerbote/xbrl/tests/mini.py)."""

import re
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from unittest import TestCase

from lxml import etree

from steuerbote.xbrl import writer
from steuerbote.xbrl.facts import (
	Entity,
	Item,
	Period,
	Periods,
	Report,
	Tuple,
	amount,
	choice,
	nil,
)
from steuerbote.xbrl.taxonomy import View
from steuerbote.xbrl.tests import mini
from steuerbote.xbrl.versions import BASE_URL
from steuerbote.xbrl.writer import WriterError

FIXTURES = Path(__file__).parent / "fixtures"
# Invented: a Steuernummer of the test Finanzamt 9198 of the ERiC documentation.
ENTITY = Entity.steuernummer("9198011310010")
PERIODS = Periods(date(2026, 1, 1), date(2026, 12, 31))
PRIOR = Periods(
	date(2026, 1, 1),
	date(2026, 12, 31),
	prior_fiscal_year_begin=date(2025, 1, 1),
	prior_fiscal_year_end=date(2025, 12, 31),
)
NS = {
	"xbrli": "http://www.xbrl.org/2003/instance",
	"link": "http://www.xbrl.org/2003/linkbase",
	"xlink": "http://www.w3.org/1999/xlink",
	"xsi": "http://www.w3.org/2001/XMLSchema-instance",
	"xbrldi": "http://xbrl.org/2006/xbrldi",
	"de-gcd": mini.GCD_NS,
	"de-gaap-ci": mini.GAAP_NS,
}
NIL = "{http://www.w3.org/2001/XMLSchema-instance}nil"
TAX_BALANCE = ("de-gaap-ci:dim_taxTrans", "de-gaap-ci:dim_taxBal")
TANGIBLE = ("de-gaap-ci:dim_changes.nt.ass.gross", "de-gaap-ci:bs.ass.fixAss.tan")
INTANGIBLE = ("de-gaap-ci:dim_changes.nt.ass.gross", "de-gaap-ci:bs.ass.fixAss.intan")
WJ = Period.WIRTSCHAFTSJAHR


def report(*facts, periods: Periods = PERIODS, view: View = View.FISCAL, **values) -> Report:
	return Report(ENTITY, periods, writer.entry_points(mini.view(view)), facts, **values)


def written(*facts, periods: Periods = PERIODS, view: View = View.FISCAL, **values) -> etree._Element:
	return writer.instance(report(*facts, periods=periods, view=view, **values), mini.view(view))


def account(position: str, number: str, value: Decimal) -> Tuple:
	return Tuple(
		"de-gaap-ci:detailedInformation.accountBalances",
		(
			Item("de-gaap-ci:detailedInformation.accountbalances.positionName", WJ, position),
			Item("de-gaap-ci:detailedInformation.accountbalances.accountNumber", WJ, number),
			Item("de-gaap-ci:detailedInformation.accountbalances.accountDescription", WJ, "Bank"),
			Item("de-gaap-ci:detailedInformation.accountbalances.amount", WJ, value),
		),
	)


def only(root: etree._Element, path: str) -> etree._Element:
	(found,) = root.xpath(path, namespaces=NS)
	return found


class DocumentTest(TestCase):
	def test_the_instance_of_a_report(self):
		"""Entry points, contexts, units and facts, in this order (XBRL 2.1, Kap. 4.1), as the examples of the ERiC
		documentation 44.3.6.0 write them."""
		facts = (
			choice(
				"de-gcd:genInfo.report.id.reportStatus",
				"de-gcd:genInfo.report.id.reportStatus.reportStatus.E",
			),
			Item("de-gcd:genInfo.doc.id.generationDate", WJ, date(2027, 3, 31)),
			Tuple(
				"de-gcd:genInfo.company.id.idNo",
				(Item("de-gcd:genInfo.company.id.idNo.type.companyId.ST13", WJ, "9198011310010"),),
			),
			Tuple(
				"de-gcd:genInfo.company.id.shareholder",
				(
					Item("de-gcd:genInfo.company.id.shareholder.currentnumber", WJ, 1, decimals=0),
					Item("de-gcd:genInfo.company.id.shareholder.name", WJ, "Erika Mustermann"),
				),
			),
			amount("de-gaap-ci:bs.ass", Period.STICHTAG, Decimal("1500")),
			nil("de-gaap-ci:bs.ass.fixAss.intan", Period.STICHTAG),
			amount("de-gaap-ci:gross", WJ, Decimal("1000.5"), (TAX_BALANCE, TANGIBLE)),
			account("de-gaap-ci:bs.ass.currAss.cashEquiv.bank", "1200", Decimal("1500.00")),
		)
		self.assertEqual(
			writer.write(report(*facts), mini.view()), (FIXTURES / "instance-fiscal.xml").read_bytes()
		)

	def test_the_same_report_gives_the_same_bytes(self):
		facts = (
			amount("de-gaap-ci:gross", WJ, Decimal("1.00"), (TANGIBLE, TAX_BALANCE)),
			amount("de-gaap-ci:gross", WJ, Decimal("2.00"), (INTANGIBLE, TAX_BALANCE)),
			amount("de-gaap-ci:bs.ass", Period.STICHTAG, Decimal("3.00")),
		)
		first = writer.write(report(*facts), mini.view())
		self.assertEqual(writer.write(report(*facts), mini.view()), first)
		contexts = [
			etree.tostring(context)
			for context in etree.fromstring(first).xpath("xbrli:context", namespaces=NS)
		]
		reversed_contexts = [
			etree.tostring(context)
			for context in etree.fromstring(writer.write(report(*reversed(facts)), mini.view())).xpath(
				"xbrli:context", namespaces=NS
			)
		]
		self.assertEqual(reversed_contexts, contexts)

	def test_a_document_in_utf_8(self):
		"""„Die Daten werden mit <?xml version=“1.0“ encoding=“utf-8“?> erwartet.“ (Einheitliche
		Elster-Datenschnittstelle XML, Stand 2026-02-12, Kap. 2.1)"""
		document = writer.write(
			report(Item("de-gcd:genInfo.company.id.name", WJ, "Müller GmbH")), mini.view()
		)
		self.assertTrue(document.startswith(b'<?xml version="1.0" encoding="UTF-8"?>\n<xbrli:xbrl '))
		self.assertTrue(document.endswith(b"</xbrli:xbrl>\n"))
		self.assertIn("Müller GmbH".encode(), document)

	def test_references_the_entry_points_of_its_view(self):
		"""„ist immer genau eines zusammen mit dem Einstiegsschema für die GCD, „de-gcd-2025-04-01-shell.xsd“, zu
		referenzieren“ (Technischer Leitfaden 6.9, B.3), by its absolute URL (A.6)."""
		for view, gaap in (
			(View.FISCAL, mini.VERSION.fiscal_shell),
			(View.COMMERCIAL, mini.VERSION.commercial_shell),
			(View.COMMERCIAL_MICROBILG, mini.VERSION.microbilg_shell),
		):
			with self.subTest(view=view):
				root = written(amount("de-gaap-ci:bs.ass", Period.STICHTAG, Decimal(1)), view=view)
				self.assertEqual(
					root.xpath("link:schemaRef/@xlink:href", namespaces=NS),
					[BASE_URL + mini.VERSION.gcd_shell, BASE_URL + gaap],
				)
				self.assertEqual(
					root.xpath("link:schemaRef/@xlink:type", namespaces=NS), ["simple", "simple"]
				)

	def test_refuses_the_entry_points_of_another_view(self):
		commercial = report(amount("de-gaap-ci:bs.ass", Period.STICHTAG, Decimal(1)), view=View.COMMERCIAL)
		with self.assertRaisesRegex(WriterError, "entry point"):
			writer.instance(commercial, mini.view(View.FISCAL))


class ContextsTest(TestCase):
	"""„Stichtagsbezogene Positionen müssen im Datensatz stichtagsbezogenen Kontexten zugordnet sein“ (Leitfaden B.8),
	one context for each period and scenario the items refer to (ERiC E-Bilanz-Dokumentation 44.3.6.0, Kap. 3.2)."""

	def test_each_context_names_the_company_by_its_steuernummer(self):
		"""„Die entity-Einträge in den Kontexten sind daraufhin zu prüfen, ob sie im gesamten Datensatz mit nur einem
		einheitlichen Wert belegt sind.“ (Leitfaden B.14.7)"""
		root = written(
			amount("de-gaap-ci:bs.ass", Period.STICHTAG, Decimal(1)),
			amount("de-gaap-ci:is.netIncome", WJ, Decimal(1)),
		)
		self.assertEqual(
			root.xpath("xbrli:context/xbrli:entity/xbrli:identifier/@scheme", namespaces=NS),
			["http://www.rzf-nrw.de/Steuernummer"] * 2,
		)
		self.assertEqual(
			root.xpath("xbrli:context/xbrli:entity/xbrli:identifier/text()", namespaces=NS),
			["9198011310010"] * 2,
		)

	def test_a_context_at_the_bilanzstichtag_and_one_over_the_fiscal_year(self):
		root = written(
			amount("de-gaap-ci:is.netIncome", WJ, Decimal(1)),
			amount("de-gaap-ci:bs.ass", Period.STICHTAG, Decimal(1)),
		)
		self.assertEqual(root.xpath("xbrli:context/@id", namespaces=NS), ["I-AKTJAHR", "D-AKTJAHR"])
		self.assertEqual(
			only(root, "xbrli:context[@id='I-AKTJAHR']/xbrli:period/xbrli:instant").text, "2026-12-31"
		)
		self.assertEqual(
			root.xpath("xbrli:context[@id='D-AKTJAHR']/xbrli:period/*/text()", namespaces=NS),
			["2026-01-01", "2026-12-31"],
		)
		self.assertEqual(only(root, "de-gaap-ci:bs.ass").get("contextRef"), "I-AKTJAHR")
		self.assertEqual(only(root, "de-gaap-ci:is.netIncome").get("contextRef"), "D-AKTJAHR")

	def test_only_the_contexts_the_items_refer_to(self):
		"""„Jeder der im eingereichten Datensatz spezifizierten Kontexte muss von mindestens einem Fakt referenziert
		werden.“ (Leitfaden B.14.7)"""
		root = written(amount("de-gaap-ci:bs.ass", Period.STICHTAG, Decimal(1)))
		self.assertEqual(root.xpath("xbrli:context/@id", namespaces=NS), ["I-AKTJAHR"])

	def test_the_previous_year(self):
		"""„Handelsbilanzen dürfen auch Angaben zum Vorjahr und somit einen periodenbezogenen Vorjahreskontext oder
		einen stichtagsbezogenen Vorjahreskontext oder beides enthalten“ (Leitfaden B.8.3)."""
		root = written(
			amount("de-gaap-ci:bs.ass", Period.VORJAHR_STICHTAG, Decimal(1)),
			amount("de-gaap-ci:is.netIncome", Period.VORJAHR, Decimal(1)),
			periods=PRIOR,
		)
		self.assertEqual(root.xpath("xbrli:context/@id", namespaces=NS), ["I-VORJAHR", "D-VORJAHR"])
		self.assertEqual(
			only(root, "xbrli:context[@id='I-VORJAHR']/xbrli:period/xbrli:instant").text, "2025-12-31"
		)
		self.assertEqual(
			root.xpath("xbrli:context[@id='D-VORJAHR']/xbrli:period/*/text()", namespaces=NS),
			["2025-01-01", "2025-12-31"],
		)

	def test_an_eroeffnungsbilanz_at_the_first_day(self):
		"""SteuerbilanzAutoverkaeufer-Eroeffnung_PersG.xml of the ERiC documentation: the instant 2025-01-01."""
		opening = Periods(date(2026, 1, 1), date(2026, 12, 31), balance_sheet_date=date(2026, 1, 1))
		root = written(amount("de-gaap-ci:bs.ass", Period.STICHTAG, Decimal(1)), periods=opening)
		self.assertEqual(only(root, "xbrli:context/xbrli:period/xbrli:instant").text, "2026-01-01")

	def test_the_members_of_a_table_in_the_scenario(self):
		"""„Alle Dimensionen der HGB-Taxonomie sind Szenario-Dimensionen“ (Leitfaden A.14.2.1); the contexts of a
		table follow the one without dimensions of their period, in the order of their members."""
		root = written(
			amount("de-gaap-ci:gross", WJ, Decimal(1), (TANGIBLE, TAX_BALANCE)),
			amount("de-gaap-ci:gross", WJ, Decimal(2), (INTANGIBLE, TAX_BALANCE)),
			Item("de-gcd:genInfo.company.id.name", WJ, "Beispiel GmbH"),
		)
		self.assertEqual(
			root.xpath("xbrli:context/@id", namespaces=NS), ["D-AKTJAHR", "D-AKTJAHR-1", "D-AKTJAHR-2"]
		)
		self.assertEqual(
			[
				(member.get("dimension"), member.text)
				for member in root.xpath(
					"xbrli:context[@id='D-AKTJAHR-1']/xbrli:scenario/xbrldi:explicitMember", namespaces=NS
				)
			],
			[INTANGIBLE, TAX_BALANCE],
		)
		self.assertEqual(
			root.xpath("de-gaap-ci:gross/@contextRef", namespaces=NS), ["D-AKTJAHR-2", "D-AKTJAHR-1"]
		)
		self.assertEqual(root.xpath("xbrli:context[@id='D-AKTJAHR']/xbrli:scenario", namespaces=NS), [])

	def test_the_previous_year_has_no_dimensions(self):
		"""„Vorjahreskontexte dürfen nicht dimensional sein.“ (ERiC E-Bilanz-Dokumentation 44.3.6.0, Kap. 3.2)"""
		with self.assertRaisesRegex(WriterError, "previous year"):
			written(
				amount("de-gaap-ci:gross", Period.VORJAHR, Decimal(1), (TANGIBLE, TAX_BALANCE)), periods=PRIOR
			)


class AmountsTest(TestCase):
	"""„Geprüft wird, dass der Datensatz nur Euro als Währungsangabe enthält. Die monetären Wertangaben müssen auf zwei
	Nachkommastellen genau angegeben sein“ (Leitfaden B.7), with decimals="2" (ERiC E-Bilanz-Dokumentation, Kap.
	3.8)."""

	def test_in_euros_with_two_decimals(self):
		root = written(
			amount("de-gaap-ci:bs.ass", Period.STICHTAG, Decimal("1500")),
			amount("de-gaap-ci:bs.ass.fixAss", Period.STICHTAG, Decimal("1.5")),
			amount("de-gaap-ci:bs.ass.currAss", Period.STICHTAG, Decimal("-3.25")),
			amount("de-gaap-ci:bs.eqLiab", Period.STICHTAG, Decimal("1E+3")),
		)
		self.assertEqual(only(root, "xbrli:unit").get("id"), "EUR")
		self.assertEqual(only(root, "xbrli:unit/xbrli:measure").text, "iso4217:EUR")
		self.assertEqual(
			[
				(element.get("unitRef"), element.get("decimals"), element.text)
				for element in root.xpath("de-gaap-ci:*", namespaces=NS)
			],
			[("EUR", "2", "1500.00"), ("EUR", "2", "1.50"), ("EUR", "2", "-3.25"), ("EUR", "2", "1000.00")],
		)

	def test_zero_has_no_sign(self):
		root = written(amount("de-gaap-ci:bs.ass", Period.STICHTAG, Decimal("-0.00")))
		self.assertEqual(only(root, "de-gaap-ci:bs.ass").text, "0.00")

	def test_nothing_finer_than_cents(self):
		"""Steuerbote rounds where the rules say so, never while it writes (steuerbote/ustva/rounding.py)."""
		for value in (
			Decimal("0.005"),
			Decimal("1.001"),
			Decimal("NaN"),
			Decimal("Infinity"),
			Decimal("1E+30"),
		):
			with self.subTest(value=value), self.assertRaisesRegex(WriterError, "bs.ass"):
				written(amount("de-gaap-ci:bs.ass", Period.STICHTAG, value))

	def test_whole_euros_where_the_report_asks_for_them(self):
		root = written(amount("de-gaap-ci:bs.ass", Period.STICHTAG, Decimal("1500.00")), monetary_decimals=0)
		element = only(root, "de-gaap-ci:bs.ass")
		self.assertEqual((element.get("decimals"), element.text), ("0", "1500"))
		with self.assertRaises(WriterError):
			written(amount("de-gaap-ci:bs.ass", Period.STICHTAG, Decimal("1.50")), monetary_decimals=0)
		with self.assertRaises(WriterError):
			written(amount("de-gaap-ci:bs.ass", Period.STICHTAG, Decimal("1000")), monetary_decimals=-3)

	def test_an_amount_is_a_decimal(self):
		for value in (1500, "1500.00", True):
			with self.subTest(value=value), self.assertRaisesRegex(WriterError, "Decimal"):
				written(Item("de-gaap-ci:bs.ass", Period.STICHTAG, value))

	def test_nil_has_its_unit_and_no_decimals(self):
		"""„If a numeric fact has a nil value ... the precision and decimals attributes MUST NOT appear“ (XBRL 2.1,
		Kap. 4.6.3), as in „<de-bra:bs.ass.currAss.inventory.ownProduce xsi:nil="true" contextRef="I-AKTJAHR"
		unitRef="EUR"/>“ of HandelsbilanzLandwirt_GmbH.xml."""
		element = only(written(nil("de-gaap-ci:bs.ass", Period.STICHTAG)), "de-gaap-ci:bs.ass")
		self.assertEqual(
			(element.get(NIL), element.get("unitRef"), element.get("decimals"), element.text),
			("true", "EUR", None, None),
		)


class ValuesTest(TestCase):
	def test_other_numbers_take_their_decimals_and_the_unit_pure(self):
		"""„<de-gcd:genInfo.company.id.shareholder.currentnumber decimals="0" contextRef="D-AKTJAHR"
		unitRef="PURE">1</...>“ and „<xbrli:unit id="PURE"><xbrli:measure>xbrli:pure</xbrli:measure>“ (examples of
		the ERiC documentation)."""
		root = written(
			Tuple(
				"de-gcd:genInfo.company.id.shareholder",
				(
					Item("de-gcd:genInfo.company.id.shareholder.name", WJ, "Erika Mustermann"),
					Item("de-gcd:genInfo.company.id.shareholder.currentnumber", WJ, 2, decimals=0),
					Tuple(
						"de-gcd:genInfo.company.id.shareholder.ShareDivideKey",
						(
							Item(
								"de-gcd:genInfo.company.id.shareholder.ShareDivideKey.numerator",
								WJ,
								Decimal("1.5"),
								decimals=1,
							),
							Item(
								"de-gcd:genInfo.company.id.shareholder.ShareDivideKey.denominator",
								WJ,
								Decimal("1E+1"),
								decimals=0,
							),
						),
					),
				),
			)
		)
		self.assertEqual(only(root, "xbrli:unit/xbrli:measure").text, "xbrli:pure")
		self.assertEqual(
			[
				(element.get("unitRef"), element.get("decimals"), element.text)
				for element in root.xpath("//de-gcd:*[@unitRef]", namespaces=NS)
			],
			[("PURE", "0", "2"), ("PURE", "1", "1.5"), ("PURE", "0", "10")],
		)

	def test_a_number_names_its_decimals_and_keeps_to_them(self):
		numerator = "de-gcd:genInfo.company.id.shareholder.ShareDivideKey.numerator"
		denominator = Item(
			"de-gcd:genInfo.company.id.shareholder.ShareDivideKey.denominator", WJ, 1, decimals=0
		)
		name = Item("de-gcd:genInfo.company.id.shareholder.name", WJ, "Erika Mustermann")
		for parts in (
			(
				Tuple(
					denominator.concept.rpartition(".")[0], (Item(numerator, WJ, Decimal("1.5")), denominator)
				),
			),
			(
				Tuple(
					denominator.concept.rpartition(".")[0],
					(Item(numerator, WJ, Decimal("1.55"), decimals=1), denominator),
				),
			),
			(
				Tuple(
					denominator.concept.rpartition(".")[0],
					(Item(numerator, WJ, True, decimals=0), denominator),
				),
			),
			(Item("de-gcd:genInfo.company.id.shareholder.currentnumber", WJ, Decimal("2"), decimals=0),),
		):
			with self.subTest(parts=parts), self.assertRaisesRegex(WriterError, "number"):
				written(Tuple("de-gcd:genInfo.company.id.shareholder", (name, *parts)))

	def test_dates_booleans_texts_and_qnames(self):
		root = written(
			Item("de-gcd:genInfo.doc.id.generationDate", WJ, date(2027, 3, 31)),
			Item("de-gcd:genInfo.company.id.optionKStGs1a", WJ, False),
			Item("de-gcd:genInfo.company.id.name", WJ, "Beispiel & Söhne GmbH\nBerlin"),
			account("de-gaap-ci:bs.ass.currAss.cashEquiv.bank", "1200", Decimal(1)),
		)
		self.assertEqual(only(root, "de-gcd:genInfo.doc.id.generationDate").text, "2027-03-31")
		self.assertEqual(only(root, "de-gcd:genInfo.company.id.optionKStGs1a").text, "false")
		self.assertEqual(only(root, "de-gcd:genInfo.company.id.name").text, "Beispiel & Söhne GmbH\nBerlin")
		self.assertEqual(
			only(root, "//de-gaap-ci:detailedInformation.accountbalances.positionName").text,
			"de-gaap-ci:bs.ass.currAss.cashEquiv.bank",
		)
		self.assertEqual(
			only(written(Item("de-gcd:genInfo.company.id.optionKStGs1a", WJ, True)), "*[@contextRef]").text,
			"true",
		)

	def test_a_qname_names_the_module_of_the_position(self):
		for position in ("bs.ass", "de-gaap:bs.ass"):
			with self.subTest(position=position), self.assertRaisesRegex(WriterError, "prefix"):
				written(account(position, "1200", Decimal(1)))

	def test_refuses_a_value_its_type_does_not_take(self):
		for item in (
			Item("de-gcd:genInfo.doc.id.generationDate", WJ, "2027-03-31"),
			Item("de-gcd:genInfo.doc.id.generationDate", WJ, datetime(2027, 3, 31, 12, 0)),
			Item("de-gcd:genInfo.company.id.optionKStGs1a", WJ, 1),
			Item("de-gcd:genInfo.company.id.name", WJ, Decimal(1)),
			Item("de-gcd:genInfo.company.id.name", WJ, True),
			Item("de-gcd:genInfo.company.id.name", WJ, date(2027, 3, 31)),
		):
			with self.subTest(item=item), self.assertRaisesRegex(WriterError, item.concept):
				written(item)

	def test_texts_keep_to_the_characters_elster_takes(self):
		"""„Im Inhaltsbereich von XML-Elementen des Datenteils sind alle Zeichen zugelassen, deren Code-Punkt ... in
		einen der nachfolgend aufgelisteten Wertebereiche fällt“ (ERiC E-Bilanz-Dokumentation 44.3.6.0, Kap. 3.16),
		the character set of the Einheitliche Elster-Datenschnittstelle XML (Kap. 2.2) with line feed and carriage
		return."""
		allowed = "Œuvre € »Zürich« ¯\r\n"
		root = written(Item("de-gcd:genInfo.company.id.name", WJ, allowed))
		self.assertEqual(only(root, "de-gcd:genInfo.company.id.name").text, allowed)
		for text, character in (
			("Łódź", "U+0141"),
			("A \N{EN DASH} B", "U+2013"),
			("A\tB", "U+0009"),
			("©", "U+00A9"),
		):
			with self.subTest(text=text), self.assertRaisesRegex(WriterError, re.escape(character)):
				written(Item("de-gcd:genInfo.company.id.name", WJ, text))


class ItemsTest(TestCase):
	def test_refuses_a_concept_the_view_does_not_have(self):
		"""„Es dürfen bei der Einreichung nur Positionen der zugelassenen, standardisierten Taxonomie-Schemata ...
		verwendet werden.“ (Leitfaden B.10)"""
		with self.assertRaisesRegex(WriterError, "bs.ass.unknown"):
			written(amount("de-gaap-ci:bs.ass.unknown", Period.STICHTAG, Decimal(1)))

	def test_an_item_is_no_abstract_position_and_no_tuple(self):
		for fact in (
			Item("de-gaap-ci:detailedInformation", WJ, ""),
			Item("de-gaap-ci:detailedInformation.accountBalances", WJ, ""),
			Tuple("de-gaap-ci:bs.ass", nil=True),
		):
			with self.subTest(fact=fact), self.assertRaisesRegex(WriterError, fact.concept):
				written(fact)

	def test_an_item_refers_to_the_period_type_of_its_concept(self):
		"""Instant concepts to instant contexts, duration concepts to duration contexts (Leitfaden B.8)."""
		for fact in (
			amount("de-gaap-ci:bs.ass", WJ, Decimal(1)),
			amount("de-gaap-ci:bs.ass", Period.VORJAHR, Decimal(1)),
			amount("de-gaap-ci:is.netIncome", Period.STICHTAG, Decimal(1)),
		):
			with self.subTest(fact=fact), self.assertRaisesRegex(WriterError, "period"):
				written(fact, periods=PRIOR)

	def test_an_item_of_a_table_names_a_member_of_each_dimension(self):
		"""The hypercube of the Anlagenspiegel with its dimensions „steuerliche Überleitung“ and „Positionen des
		Anlagevermögens“ (Leitfaden A.14.1), whose members are the usable ones of each dimension (XBRL Dimensions
		1.0, Kap. 2.5.3)."""
		for dimensions in (
			(TAX_BALANCE,),
			(TAX_BALANCE, ("de-gaap-ci:dim_changes.nt.ass.gross", "de-gaap-ci:bs.ass.currAss")),
			(TAX_BALANCE, ("de-gaap-ci:dim_changes.nt.ass.gross", "de-gaap-ci:dim_comBal")),
			(TAX_BALANCE, TANGIBLE, ("de-gaap-ci:dim_other", "de-gaap-ci:dim_taxBal")),
		):
			with self.subTest(dimensions=dimensions), self.assertRaisesRegex(WriterError, "gross"):
				written(amount("de-gaap-ci:gross", WJ, Decimal(1), dimensions))
		with self.assertRaisesRegex(WriterError, "gross"):
			written(amount("de-gaap-ci:gross", WJ, Decimal(1)))

	def test_only_the_items_of_a_table_have_dimensions(self):
		"""„Zusätzliche Angaben zur Definition von Kontexten („scenario“ und „segment“) sind grundsätzlich unzulässig,
		allenfalls im Bereich der Tabellenbereiche ... zulässig“ (Leitfaden B.14.7)."""
		with self.assertRaisesRegex(WriterError, "bs.ass"):
			written(amount("de-gaap-ci:bs.ass", Period.STICHTAG, Decimal(1), (TAX_BALANCE, TANGIBLE)))


class TuplesTest(TestCase):
	def test_a_tuple_holds_its_parts_in_the_order_of_its_content(self):
		balances = account("de-gaap-ci:bs.ass", "1200", Decimal(1))
		root = written(Tuple(balances.concept, tuple(reversed(balances.children))))
		self.assertEqual(
			[etree.QName(child).localname for child in only(root, "de-gaap-ci:*")],
			[
				"detailedInformation.accountbalances.positionName",
				"detailedInformation.accountbalances.accountNumber",
				"detailedInformation.accountbalances.accountDescription",
				"detailedInformation.accountbalances.amount",
			],
		)

	def test_a_choice_writes_its_values_empty_and_an_unreported_mussfeld_nil(self):
		"""„übermittelte Strings sollen mit einer Länge von 0 übermittelt werden (ggf. Übermittlung mit NIL, wenn
		Position Mussfeld, aber nicht zu berichten)“ (Leitfaden B.14.1)."""
		root = written(
			choice(
				"de-gcd:genInfo.report.id.reportElement",
				"de-gcd:genInfo.report.id.reportElement.reportElements.B",
				"de-gcd:genInfo.report.id.reportElement.reportElements.GuV",
				unreported=("de-gcd:genInfo.report.id.reportElement.reportElements.EB",),
			)
		)
		self.assertEqual(
			[
				(etree.QName(child).localname, child.text, child.get(NIL), child.get("contextRef"))
				for child in only(root, "de-gcd:genInfo.report.id.reportElement")
			],
			[
				("genInfo.report.id.reportElement.reportElements.B", None, None, "D-AKTJAHR"),
				("genInfo.report.id.reportElement.reportElements.GuV", None, None, "D-AKTJAHR"),
				("genInfo.report.id.reportElement.reportElements.EB", None, "true", "D-AKTJAHR"),
			],
		)

	def test_a_nil_tuple_is_empty(self):
		element = only(
			written(Tuple("de-gcd:genInfo.company.id.shareholder", nil=True)),
			"de-gcd:genInfo.company.id.shareholder",
		)
		self.assertEqual((element.get(NIL), len(element), element.get("contextRef")), ("true", 0, None))

	def test_a_tuple_holds_what_its_content_requires_and_allows(self):
		"""The content of the complex type of a tuple (XBRL 2.1, Kap. 4.9; XML Schema, Kap. 3.8)."""
		balances = account("de-gaap-ci:bs.ass", "1200", Decimal(1))
		amount_ = balances.children[-1]
		for fact in (
			Tuple(balances.concept, (*balances.children, amount_)),
			Tuple(balances.concept, balances.children[:-1]),
			Tuple(
				balances.concept,
				(*balances.children, Item("de-gcd:genInfo.company.id.shareholder.name", WJ, "X")),
			),
			Tuple(
				"de-gcd:genInfo.report.id.reportStatus",
				(
					Item("de-gcd:genInfo.report.id.reportStatus.reportStatus.E", WJ, ""),
					Item("de-gcd:genInfo.report.id.reportStatus.reportStatus.V", WJ, ""),
				),
			),
			Tuple("de-gcd:genInfo.report.id.reportElement"),
			Tuple("de-gcd:genInfo.company.id.shareholder", (amount_,)),
		):
			with self.subTest(fact=fact), self.assertRaisesRegex(WriterError, fact.concept):
				written(fact)

	def test_the_parts_of_a_tuple_only_inside_it(self):
		"""„Bei E-Bilanz wird diese Möglichkeit jedoch durch eine zusätzliche Prüfung gezielt unterbunden, da bestimmte
		Plausibilisierungen eine Gruppierung der Fakten nach Tupeln voraussetzen.“ (ERiC E-Bilanz-Dokumentation,
		Kap. 3.10)"""
		with self.assertRaisesRegex(WriterError, "shareholder.name"):
			written(Item("de-gcd:genInfo.company.id.shareholder.name", WJ, "Erika Mustermann"))


class DuplicatesTest(TestCase):
	"""„Im Gegensatz dazu darf der an die Finanzverwaltung einzureichende Datensatz derartige Duplikate sowohl im GCD-
	als auch im GAAP-Bereich nicht enthalten.“ (Leitfaden B.14.13)"""

	def test_refuses_an_item_twice_in_one_context(self):
		with self.assertRaisesRegex(WriterError, "bs.ass"):
			written(
				amount("de-gaap-ci:bs.ass", Period.STICHTAG, Decimal(1)),
				amount("de-gaap-ci:bs.ass", Period.STICHTAG, Decimal(2)),
			)

	def test_the_same_position_in_another_context_is_no_duplicate(self):
		root = written(
			amount("de-gaap-ci:bs.ass", Period.STICHTAG, Decimal(1)),
			amount("de-gaap-ci:bs.ass", Period.VORJAHR_STICHTAG, Decimal(2)),
			amount("de-gaap-ci:gross", WJ, Decimal(1), (TANGIBLE, TAX_BALANCE)),
			amount("de-gaap-ci:gross", WJ, Decimal(1), (INTANGIBLE, TAX_BALANCE)),
			periods=PRIOR,
		)
		self.assertEqual(len(root.xpath("de-gaap-ci:*", namespaces=NS)), 4)

	def test_refuses_a_tuple_twice(self):
		balances = account("de-gaap-ci:bs.ass", "1200", Decimal(1))
		with self.assertRaisesRegex(WriterError, "accountBalances"):
			written(balances, balances)
		root = written(balances, account("de-gaap-ci:bs.ass", "1210", Decimal(1)))
		self.assertEqual(len(root.xpath("de-gaap-ci:*", namespaces=NS)), 2)

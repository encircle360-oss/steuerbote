"""Form USt 1 H as ELSTER XML for ERiC, see ust1h_xml.py. test_schema.py checks it against the schema of its year
and against the examples of the ERiC documentation."""

from datetime import date
from decimal import Decimal
from types import MappingProxyType
from unittest import TestCase, mock

from lxml import etree

from steuerbote.dauerfrist import Context, FormError, layout_for
from steuerbote.dauerfrist import form as dauerfrist_form
from steuerbote.elster import ust1h_xml, ustva_xml
from steuerbote.elster.tests.examples import (
	CREATED,
	FIXTURES,
	TEST_STEUERNUMMER,
	anmeldung,
	antrag,
	children,
	filer,
	parse,
	voranmeldung,
)
from steuerbote.elster.ust1h_xml import to_nutzdaten
from steuerbote.elster.ustva_xml import XmlError
from steuerbote.ustva import Rhythm

DF = Context.DAUERFRISTVERLAENGERUNG
SVZ = Context.UMSATZSTEUERSONDERVORAUSZAHLUNG
HERSTELLER_ID = "12345"
LOW_QUOTE = "\N{DOUBLE LOW-9 QUOTATION MARK}"
LEFT_QUOTE = "\N{LEFT DOUBLE QUOTATION MARK}"
ELLIPSIS = "\N{HORIZONTAL ELLIPSIS}"


def written(filing, **fields) -> str:
	return to_nutzdaten(filer(**fields), filing, CREATED, HERSTELLER_ID)


def contexts(document: str) -> list[etree._Element]:
	(steuerfall,) = parse(document).iter("{*}Steuerfall")
	return list(steuerfall)


def elements(document: str) -> list[tuple[str, str | None]]:
	"""Name and text of each child of the one context of form USt 1 H, in the order of the document."""
	(context,) = contexts(document)
	return children(context)


def kennzahlen(document: str) -> dict[str, str | None]:
	return {name: text for name, text in elements(document) if name.startswith("Kz")}


class NutzdatenTest(TestCase):
	def test_writes_the_anmeldung_of_the_example_of_the_anleitung_byte_for_byte(self):
		self.assertEqual(
			written(anmeldung()),
			(FIXTURES / "ust1h_2026_umsatzsteuersondervorauszahlung.xml").read_text(encoding="utf-8"),
		)

	def test_writes_the_antrag_byte_for_byte(self):
		self.assertEqual(
			written(antrag()),
			(FIXTURES / "ust1h_2026_dauerfristverlaengerung.xml").read_text(encoding="utf-8"),
		)

	def test_is_the_text_of_the_nutzdaten_without_a_declaration(self):
		document = written(anmeldung())
		self.assertTrue(document.startswith("<Anmeldungssteuern "))
		self.assertTrue(document.endswith("</Anmeldungssteuern>\n"))

	def test_shares_root_erstellungsdatum_and_datenlieferant_with_the_voranmeldung(self):
		contact = {"phone": "089 1234567", "email": "erika@example.org"}
		ours = parse(written(anmeldung(), **contact))
		theirs = parse(ustva_xml.to_nutzdaten(filer(**contact), voranmeldung(), CREATED, HERSTELLER_ID))
		self.assertEqual((ours.tag, dict(ours.attrib)), (theirs.tag, dict(theirs.attrib)))
		self.assertEqual(children(ours)[:1], children(theirs)[:1])
		(ours_datenlieferant,) = ours.iter("{*}DatenLieferant")
		(theirs_datenlieferant,) = theirs.iter("{*}DatenLieferant")
		self.assertEqual(children(ours_datenlieferant), children(theirs_datenlieferant))

	def test_carries_the_date_of_creation(self):
		document = to_nutzdaten(filer(), anmeldung(), date(2027, 1, 5), HERSTELLER_ID)
		self.assertEqual(parse(document).findtext("{*}Erstellungsdatum"), "20270105")


class ContextTest(TestCase):
	def test_a_quarterly_filer_files_the_antrag_as_the_context_dauerfristverlaengerung(self):
		self.assertIs(Context.for_rhythm(Rhythm.QUARTERLY), DF)
		(context,) = contexts(written(antrag()))
		self.assertEqual(etree.QName(context).localname, "Dauerfristverlaengerung")
		self.assertEqual(
			elements(written(antrag())),
			[("Jahr", "2026"), ("Steuernummer", TEST_STEUERNUMMER), ("Kz09", HERSTELLER_ID)],
		)

	def test_a_monthly_filer_files_the_anmeldung_as_the_context_umsatzsteuersondervorauszahlung(self):
		self.assertIs(Context.for_rhythm(Rhythm.MONTHLY), SVZ)
		(context,) = contexts(written(anmeldung()))
		self.assertEqual(etree.QName(context).localname, "Umsatzsteuersondervorauszahlung")
		self.assertEqual(
			elements(written(anmeldung())),
			[
				("Jahr", "2026"),
				("Steuernummer", TEST_STEUERNUMMER),
				("Kz09", HERSTELLER_ID),
				("Kz38", "4000"),
			],
		)

	def test_110085099_a_file_holds_exactly_one_context(self):
		for filing in (antrag(), anmeldung()):
			with self.subTest(context=filing.context):
				self.assertEqual(
					[etree.QName(context).localname for context in contexts(written(filing))],
					[filing.context.value],
				)

	def test_110085046_the_steuerfall_names_neither_unternehmer_nor_berater_nor_mandant(self):
		(steuerfall,) = parse(written(anmeldung())).iter("{*}Steuerfall")
		self.assertEqual([etree.QName(child).localname for child in steuerfall], [SVZ.value])

	def test_110085130_and_110085131_jahr_is_the_year_of_the_schema(self):
		for filing in (antrag(), anmeldung()):
			document = written(filing)
			root = parse(document)
			with self.subTest(context=filing.context):
				self.assertEqual(dict(elements(document))["Jahr"], "2026")
				self.assertEqual(root.get("version"), "2026")
				self.assertEqual(etree.QName(root).namespace, ustva_xml.schema_for(2026).namespace)

	def test_writes_every_element_in_the_order_of_the_schema(self):
		full = {
			SVZ: anmeldung(
				corrected=True,
				no_sepa_mandate=True,
				offset_requested=True,
				supplementary_code="4",
				begruendung="Siehe Anlage",
			),
			DF: antrag(supplementary_code="2", begruendung="Siehe Anlage"),
		}
		for context, filing in full.items():
			with self.subTest(context=context):
				document = written(filing, wid_nr="DE123456789")
				self.assertEqual(
					tuple(name for name, _ in elements(document)), layout_for(2026).elements(context)
				)

	def test_needs_the_schema_of_the_year_of_the_form(self):
		with (
			mock.patch.object(ustva_xml, "SCHEMAS", MappingProxyType({})),
			self.assertRaises(XmlError) as raised,
		):
			written(anmeldung())
		self.assertEqual((raised.exception.template, raised.exception.values), (ustva_xml.NO_SCHEMA, (2026,)))

	def test_a_year_without_the_form_has_no_file(self):
		with self.assertRaises(FormError) as raised:
			anmeldung(year=2027)
		self.assertEqual(raised.exception.template, dauerfrist_form.NO_LAYOUT)


class SondervorauszahlungTest(TestCase):
	def test_110085143_kz38_is_written_even_as_zero(self):
		self.assertEqual(
			kennzahlen(written(anmeldung(sondervorauszahlung=Decimal("0")))),
			{
				"Kz09": HERSTELLER_ID,
				"Kz38": "0",
			},
		)

	def test_kz38_is_whole_euros_without_cents_or_sign(self):
		for amount in (Decimal("4000.00"), Decimal("4E+3")):
			with self.subTest(amount=amount):
				self.assertEqual(kennzahlen(written(anmeldung(sondervorauszahlung=amount)))["Kz38"], "4000")
		largest = Decimal("9999999999999")
		self.assertEqual(kennzahlen(written(anmeldung(sondervorauszahlung=largest)))["Kz38"], "9999999999999")

	def test_yes_fields_are_one_or_left_out(self):
		self.assertEqual(
			{name for name in kennzahlen(written(anmeldung())) if name in ("Kz10", "Kz26", "Kz29")}, set()
		)
		flags = kennzahlen(written(anmeldung(corrected=True, no_sepa_mandate=True, offset_requested=True)))
		self.assertEqual(
			{name: flags[name] for name in ("Kz10", "Kz26", "Kz29")},
			{"Kz10": "1", "Kz26": "1", "Kz29": "1"},
		)

	def test_the_antrag_carries_no_kennzahl_of_the_sondervorauszahlung(self):
		self.assertEqual(kennzahlen(written(antrag())), {"Kz09": HERSTELLER_ID})


class RulesTest(TestCase):
	"""The rules of the Jahresdokumentation on Kz 10, 29 and 500, which dauerfrist.form.Ust1H keeps."""

	def test_kz10_alone_files_a_corrected_anmeldung(self):
		self.assertEqual(kennzahlen(written(anmeldung(corrected=True)))["Kz10"], "1")

	def test_11085150_kz29_only_with_kz10(self):
		with self.assertRaises(FormError) as raised:
			anmeldung(offset_requested=True)
		self.assertEqual(raised.exception.rule.code, "11085150")
		written_flags = kennzahlen(written(anmeldung(corrected=True, offset_requested=True)))
		self.assertEqual((written_flags["Kz10"], written_flags["Kz29"]), ("1", "1"))

	def test_11085137_kz500_only_with_its_begruendung(self):
		for fields in ({"supplementary_code": "1"}, {"begruendung": "Sachverhalt"}):
			for filing in (antrag, anmeldung):
				with (
					self.subTest(fields=fields, filing=filing.__name__),
					self.assertRaises(FormError) as raised,
				):
					filing(**fields)
				self.assertEqual(raised.exception.rule.code, "11085137")
		for filing in (antrag, anmeldung):
			with self.subTest(filing=filing.__name__):
				document = written(filing(supplementary_code="3", begruendung="Sachverhalt"))
				self.assertEqual(
					elements(document)[-2:], [("Kz500", "3"), ("Kz500_Begruendung", "Sachverhalt")]
				)

	def test_kz500_goes_with_kz10_and_kz29(self):
		filing = anmeldung(
			corrected=True, offset_requested=True, supplementary_code="1", begruendung="Sachverhalt"
		)
		self.assertEqual(
			[name for name, _ in elements(written(filing))][-5:],
			["Kz10", "Kz29", "Kz38", "Kz500", "Kz500_Begruendung"],
		)

	def test_the_antrag_takes_none_of_kz10_kz26_kz29_and_kz38(self):
		for fields in (
			{"corrected": True},
			{"no_sepa_mandate": True},
			{"corrected": True, "offset_requested": True},
			{"sondervorauszahlung": Decimal("0")},
		):
			with self.subTest(fields=fields), self.assertRaises(FormError) as raised:
				antrag(**fields)
			self.assertEqual(raised.exception.template, dauerfrist_form.NOT_IN_CONTEXT)

	def test_the_begruendung_takes_the_elster_character_set(self):
		filing = anmeldung(
			supplementary_code="2", begruendung=f"{LOW_QUOTE}Abweichende Auffassung{LEFT_QUOTE}"
		)
		self.assertEqual(dict(elements(written(filing)))["Kz500_Begruendung"], '"Abweichende Auffassung"')
		with self.assertRaises(XmlError) as raised:
			written(anmeldung(supplementary_code="2", begruendung="Łódź"))
		self.assertEqual(
			(raised.exception.template, raised.exception.label),
			(ustva_xml.TEXT_CHARACTERS, ustva_xml.BEGRUENDUNG_LABEL),
		)

	def test_the_begruendung_has_at_most_180_characters_as_written(self):
		self.assertEqual(
			dict(elements(written(anmeldung(supplementary_code="1", begruendung=ELLIPSIS * 60))))[
				"Kz500_Begruendung"
			],
			"." * 180,
		)
		with self.assertRaises(XmlError) as raised:
			written(anmeldung(supplementary_code="1", begruendung=ELLIPSIS * 61))
		self.assertEqual(
			(raised.exception.template, raised.exception.values), (ustva_xml.TEXT_TOO_LONG, (183, 180))
		)


class FilerTest(TestCase):
	def test_110085044_the_steuernummer_is_the_one_of_the_filer(self):
		self.assertEqual(dict(elements(written(anmeldung())))["Steuernummer"], TEST_STEUERNUMMER)

	def test_writes_the_wid_nr_after_the_steuernummer(self):
		self.assertEqual(
			elements(written(antrag(), wid_nr=" de 123 456 789 ")),
			[
				("Jahr", "2026"),
				("Steuernummer", TEST_STEUERNUMMER),
				("WIdNr", "DE123456789"),
				("Kz09", HERSTELLER_ID),
			],
		)


class HerstellerIdTest(TestCase):
	def test_110085045_kz09_carries_the_hersteller_id_as_for_the_voranmeldung(self):
		for filing in (antrag(), anmeldung()):
			with self.subTest(context=filing.context):
				self.assertEqual(dict(elements(written(filing)))["Kz09"], HERSTELLER_ID)

	def test_kz09_takes_an_hersteller_id_of_five_digits(self):
		for value in ("1234", "123456", "1234a", "\N{FULLWIDTH DIGIT ONE}2345", ""):
			with self.subTest(value=value), self.assertRaises(XmlError) as raised:
				to_nutzdaten(filer(), anmeldung(), CREATED, value)
			self.assertEqual(raised.exception.template, ustva_xml.NOT_A_HERSTELLER_ID)

	def test_refuses_the_hersteller_id_that_only_illustrates_the_documentation(self):
		with self.assertRaises(XmlError) as raised:
			to_nutzdaten(filer(), antrag(), CREATED, "74931")
		self.assertEqual(raised.exception.template, ustva_xml.ILLUSTRATION_HERSTELLER_ID)


class ModuleTest(TestCase):
	def test_writes_no_file_for_mein_elster(self):
		self.assertFalse(hasattr(ust1h_xml, "to_import_file"))

import re
from datetime import date
from decimal import Decimal
from unittest import TestCase

from lxml import etree

from steuerbote.elster import ustva_xml
from steuerbote.elster.tests.examples import (
	CREATED,
	EXAMPLE_MONTH,
	FIXTURES,
	OFFICIAL_EXAMPLE,
	TEST_STEUERNUMMER,
	balance,
	children,
	elements,
	filer,
	parse,
	voranmeldung,
	write,
)
from steuerbote.elster.ustva_xml import SCHEMAS, XmlError, import_file_name, to_import_file, to_nutzdaten
from steuerbote.ustva import Kind, Period, catalogue_for, to_cents

# The children of Umsatzsteuervoranmeldung in the order of UStVA-2026.xsd, as docs/abgabe-mein-elster.md
# lists them.
SCHEMA_ORDER = (
	*("Jahr", "Zeitraum", "Steuernummer", "WIdNr", "Kz09", "Kz10", "Kz21", "Kz22", "Kz26", "Kz29"),
	*("Kz35", "Kz36", "Kz37", "Kz39", "Kz41", "Kz42", "Kz43", "Kz44", "Kz45", "Kz46", "Kz47", "Kz48"),
	*("Kz49", "Kz50", "Kz59", "Kz60", "Kz61", "Kz62", "Kz63", "Kz64", "Kz65", "Kz66", "Kz67", "Kz69"),
	*("Kz70", "Kz73", "Kz74", "Kz76", "Kz77", "Kz80", "Kz81", "Kz83", "Kz84", "Kz85", "Kz86", "Kz87"),
	*("Kz89", "Kz91", "Kz93", "Kz90", "Kz94", "Kz95", "Kz96", "Kz98", "Kz500", "Kz500_Begruendung"),
)

# The rules of Jahresdokumentation_UStVA_2026.ods by Fehlercode that require a base and its tax together.
PAIR_RULES = {
	"110085065": ("35", "36"),
	"110085066": ("46", "47"),
	"110085068": ("73", "74"),
	"110085069": ("76", "80"),
	"110085070": ("95", "98"),
	"110085071": ("94", "96"),
	"110085072": ("84", "85"),
}

LOW_QUOTE = "\N{DOUBLE LOW-9 QUOTATION MARK}"
LEFT_QUOTE = "\N{LEFT DOUBLE QUOTATION MARK}"


def d(value: str) -> Decimal:
	return Decimal(value)


class ImportFileTest(TestCase):
	def test_writes_the_import_file_of_the_example_month_byte_for_byte(self):
		self.assertEqual(
			to_import_file(filer(), voranmeldung(), CREATED),
			(FIXTURES / "UStVA_2026_10.xml").read_bytes(),
		)

	def test_declares_iso_8859_15_as_the_elster_help_shows_it(self):
		document = to_import_file(filer(), voranmeldung(), CREATED)
		self.assertTrue(
			document.startswith(
				b'<?xml version="1.0" encoding="ISO-8859-15" standalone="no"?>\n<Anmeldungssteuern '
			)
		)

	def test_encodes_the_texts_in_iso_8859_15(self):
		document = to_import_file(filer(name="Beispiel € GmbH"), voranmeldung(), CREATED)
		self.assertIn(b"<Name>Beispiel \xa4 GmbH</Name>", document)
		self.assertIn(b"<Strasse>Hauptstra\xdfe 1</Strasse>", document)

	def test_escapes_what_xml_reserves(self):
		document = to_import_file(filer(name="Müller & <Söhne>"), voranmeldung(), CREATED)
		self.assertIn("<Name>Müller &amp; &lt;Söhne&gt;</Name>".encode("iso-8859-15"), document)

	def test_holds_the_nutzdaten_alone_without_kz09(self):
		root = parse(to_import_file(filer(), voranmeldung(), CREATED))
		self.assertEqual(
			root.tag, "{http://finkonsens.de/elster/elsteranmeldung/ustva/v2026}Anmeldungssteuern"
		)
		self.assertEqual(dict(root.attrib), {"version": "2026"})
		self.assertEqual(
			[name for name, _ in children(root)],
			["Erstellungsdatum", "DatenLieferant", "Steuerfall"],
		)
		self.assertNotIn("Kz09", dict(elements(etree.tostring(root))))

	def test_carries_the_date_of_creation(self):
		root = parse(to_import_file(filer(), voranmeldung(), date(2027, 1, 5)))
		self.assertEqual(root.findtext("{*}Erstellungsdatum"), "20270105")

	def test_names_the_file_by_year_and_period(self):
		self.assertEqual(import_file_name(voranmeldung()), "UStVA_2026_10.xml")
		quarter = voranmeldung({"83": d("0")}, Period.quarter(2026, 1))
		self.assertEqual(import_file_name(quarter), "UStVA_2026_41.xml")
		self.assertEqual(import_file_name(voranmeldung(corrected=True)), "UStVA_2026_10_berichtigt.xml")


class NutzdatenTest(TestCase):
	def test_writes_the_same_tree_with_the_hersteller_id_in_kz09(self):
		self.assertEqual(
			to_nutzdaten(filer(), voranmeldung(), CREATED, "12345"),
			(FIXTURES / "nutzdaten_2026_10.xml").read_text(encoding="utf-8"),
		)

	def test_differs_from_the_import_file_by_kz09_alone(self):
		nutzdaten = elements(to_nutzdaten(filer(), voranmeldung(), CREATED, "12345"))
		self.assertEqual(
			[element for element in nutzdaten if element[0] != "Kz09"],
			elements(to_import_file(filer(), voranmeldung(), CREATED)),
		)
		self.assertIn(("Kz09", "12345"), nutzdaten)

	def test_kz09_takes_an_hersteller_id_of_five_digits(self):
		for value in ("1234", "123456", "1234a", "\N{FULLWIDTH DIGIT ONE}2345", ""):
			with self.subTest(value=value), self.assertRaises(XmlError) as raised:
				to_nutzdaten(filer(), voranmeldung(), CREATED, value)
			self.assertEqual(raised.exception.template, ustva_xml.NOT_A_HERSTELLER_ID)

	def test_refuses_the_hersteller_id_that_only_illustrates_the_documentation(self):
		with self.assertRaises(XmlError) as raised:
			to_nutzdaten(filer(), voranmeldung(), CREATED, "74931")
		self.assertEqual(raised.exception.template, ustva_xml.ILLUSTRATION_HERSTELLER_ID)


class OrderTest(TestCase):
	schema = SCHEMAS[2026]

	def test_lists_every_kennzahl_of_the_form_once(self):
		self.assertEqual(len(self.schema.order), len(set(self.schema.order)))
		self.assertEqual(set(self.schema.order), set(catalogue_for(2026)))

	def test_follows_the_sequence_of_the_schema(self):
		self.assertEqual(self.schema.elements, SCHEMA_ORDER)

	def test_kz90_follows_kz93(self):
		amounts = {"90": d("10"), "93": d("10"), "83": d("0.70")}
		names = list(write(amounts))
		self.assertLess(names.index("Kz93"), names.index("Kz90"))

	def test_writes_every_element_in_the_order_of_the_schema(self):
		catalogue = catalogue_for(2026)
		amounts = {number: d("1") for number, kennzahl in catalogue.items() if kennzahl.holds_amount}
		amounts["83"] = balance({number: amount for number, amount in amounts.items() if number != "83"})
		document = to_nutzdaten(
			filer(wid_nr="DE123456789"),
			voranmeldung(
				amounts,
				corrected=True,
				attachments=True,
				no_sepa_mandate=True,
				offset_requested=True,
				supplementary_code="4",
				begruendung="Siehe Anlage",
				regelbesteuerung_from=date(2026, 10, 1),
			),
			CREATED,
			"12345",
		)
		self.assertEqual(tuple(name for name, _ in elements(document)), SCHEMA_ORDER)

	def test_refuses_a_year_without_schema(self):
		with self.assertRaises(XmlError) as raised:
			to_import_file(filer(), voranmeldung({"83": d("0")}, Period.month(2025, 12)), CREATED)
		self.assertEqual((raised.exception.template, raised.exception.values), (ustva_xml.NO_SCHEMA, (2025,)))


class FormatTest(TestCase):
	def test_bases_are_whole_euros_without_their_cents(self):
		self.assertEqual(write({"81": d("1000.99"), "83": d("190.00")})["Kz81"], "1000")
		self.assertEqual(write({"81": d("-1000.99"), "83": d("-190.00")})["Kz81"], "-1000")

	def test_taxes_have_exactly_two_decimals(self):
		self.assertEqual(write({"66": d("95"), "83": d("-95")}), {"Kz66": "95.00", "Kz83": "-95.00"})
		self.assertEqual(write({"66": d("0.5"), "83": d("-0.50")})["Kz66"], "0.50")

	def test_taxes_are_rounded_to_cents_half_up(self):
		self.assertEqual(write({"66": d("0.005"), "83": d("-0.01")})["Kz66"], "0.01")

	def test_numbers_carry_no_plus_no_leading_zero_and_no_negative_zero(self):
		base = re.compile(r"-?[1-9][0-9]*|0")
		tax = re.compile(r"-?(0|[1-9][0-9]*)\.[0-9]{2}")
		for amount in ("0.07", "-0.07", "-0.004", "12.30", "-1000", "1000000.5", "+42"):
			with self.subTest(amount=amount):
				written = write(
					{"45": d(amount), "66": d(amount), "83": balance({"66": to_cents(d(amount))})}
				)
				for name, text in written.items():
					self.assertRegex(text, tax if name in ("Kz66", "Kz83") else base)
					self.assertNotIn(text, ("-0", "-0.00"))

	def test_writes_no_negative_zero_for_an_amount_that_rounds_to_zero(self):
		self.assertEqual(write({"66": d("-0.004"), "45": d("-0.99"), "83": d("0")}), {"Kz83": "0.00"})

	def test_takes_as_many_digits_as_the_schema(self):
		self.assertEqual(write({"45": d("9999999999999"), "83": d("0")})["Kz45"], "9999999999999")
		self.assertEqual(write({"45": d("-9999999999999"), "83": d("0")})["Kz45"], "-9999999999999")
		taxes = {"66": d("99999999999.99"), "83": d("-99999999999.99")}
		self.assertEqual(write(taxes)["Kz66"], "99999999999.99")

	def test_refuses_more_digits_than_the_schema_takes(self):
		for amounts in (
			{"45": d("10000000000000"), "83": d("0")},
			{"66": d("100000000000.00"), "83": d("-100000000000.00")},
		):
			with self.subTest(amounts=amounts), self.assertRaises(XmlError) as raised:
				write(amounts)
			self.assertEqual(raised.exception.template, ustva_xml.TOO_MANY_DIGITS)

	def test_kz37_kz39_and_kz50_take_no_sign(self):
		cases = {
			"37": {"37": d("-5"), "83": d("0")},
			"39": {"39": d("-5"), "83": d("5.00")},
			"50": {"50": d("-5"), "83": d("0")},
		}
		for number, amounts in cases.items():
			with self.subTest(kennzahl=number), self.assertRaises(XmlError) as raised:
				write(amounts)
			self.assertEqual(raised.exception.template, ustva_xml.NEGATIVE)
			self.assertEqual(raised.exception.values[0], number)
		self.assertEqual(
			write({"37": d("5"), "50": d("7"), "83": d("0")}), {"Kz37": "5.00", "Kz50": "7", "Kz83": "0.00"}
		)

	def test_amounts_are_decimals(self):
		with self.assertRaises(TypeError):
			write({"45": 500.0, "83": d("0")})  # type: ignore[dict-item]

	def test_amounts_are_finite(self):
		for amount in ("NaN", "Infinity", "-Infinity"):
			with self.subTest(amount=amount), self.assertRaises(ValueError):
				write({"45": d(amount), "83": d("0")})


class OmissionTest(TestCase):
	def test_leaves_out_kennzahlen_of_zero(self):
		self.assertEqual(
			write({"81": d("0"), "45": d("0.40"), "66": d("0.004"), "83": d("0")}), {"Kz83": "0.00"}
		)

	def test_writes_kz83_even_as_zero(self):
		self.assertEqual(write({"83": d("0")}), {"Kz83": "0.00"})

	def test_yes_fields_are_one_or_left_out(self):
		self.assertEqual(
			{
				name: text
				for name, text in write(EXAMPLE_MONTH).items()
				if name in ("Kz10", "Kz22", "Kz26", "Kz29")
			},
			{},
		)
		written = write(
			EXAMPLE_MONTH, corrected=True, attachments=True, no_sepa_mandate=True, offset_requested=True
		)
		self.assertEqual(
			{name: written[name] for name in ("Kz10", "Kz22", "Kz26", "Kz29")},
			{"Kz10": "1", "Kz22": "1", "Kz26": "1", "Kz29": "1"},
		)

	def test_the_yes_fields_are_the_flags_of_the_form(self):
		self.assertEqual(
			{number for number, kennzahl in catalogue_for(2026).items() if kennzahl.kind is Kind.FLAG},
			{"10", "22", "26", "29"},
		)


class PairTest(TestCase):
	def test_the_pairs_are_those_of_the_rules(self):
		self.assertEqual(ustva_xml.pairs(catalogue_for(2026)), dict(PAIR_RULES.values()))

	def test_110085065_to_110085072_a_base_and_its_tax_are_written_together(self):
		for code, (base, tax) in PAIR_RULES.items():
			with self.subTest(code):
				self.assertEqual(
					write({base: d("100"), "83": d("0")}),
					{f"Kz{base}": "100", f"Kz{tax}": "0.00", "Kz83": "0.00"},
				)
				self.assertEqual(
					write({tax: d("7"), "83": d("7")}), {f"Kz{base}": "0", f"Kz{tax}": "7.00", "Kz83": "7.00"}
				)

	def test_a_base_rounding_to_zero_is_written_as_zero_with_its_tax(self):
		self.assertEqual(
			write({"46": d("0.40"), "47": d("0.08"), "83": d("0.08")}),
			{"Kz46": "0", "Kz47": "0.08", "Kz83": "0.08"},
		)


class BalanceTest(TestCase):
	def test_matches_the_example_of_the_eric_documentation(self):
		self.assertEqual(write(OFFICIAL_EXAMPLE)["Kz83"], "17050.00")

	def test_refuses_a_kz83_that_the_values_written_do_not_give(self):
		with self.assertRaises(XmlError) as raised:
			write({**OFFICIAL_EXAMPLE, "83": d("17050.01")})
		self.assertEqual(
			(raised.exception.template, raised.exception.values),
			(ustva_xml.BALANCE_MISMATCH, ("17050.01", "17050.00")),
		)

	def test_derives_the_tax_from_the_base_as_written(self):
		with self.assertRaises(XmlError) as raised:
			write({"81": d("1000.99"), "83": d("190.19")})
		self.assertEqual(raised.exception.values, ("190.19", "190.00"))

	def test_counts_the_derived_taxes_of_both_rates(self):
		self.assertEqual(
			write({"86": d("100"), "89": d("100"), "93": d("100"), "83": d("33.00")})["Kz83"], "33.00"
		)

	def test_deducts_the_sondervorauszahlung(self):
		self.assertEqual(write({"39": d("1200"), "83": d("-1200")}), {"Kz39": "1200.00", "Kz83": "-1200.00"})

	def test_kz83_is_required(self):
		with self.assertRaises(XmlError) as raised:
			write({"81": d("1000")})
		self.assertEqual(raised.exception.template, ustva_xml.BALANCE_MISSING)


class RulesTest(TestCase):
	def test_11085149_kz29_needs_a_surplus_or_a_corrected_return(self):
		self.assertEqual(write({"66": d("95"), "83": d("-95")}, offset_requested=True)["Kz29"], "1")
		for amounts in ({"83": d("0")}, EXAMPLE_MONTH):
			with self.subTest(kz83=amounts["83"]), self.assertRaises(XmlError) as raised:
				write(amounts, offset_requested=True)
			self.assertEqual(raised.exception.template, ustva_xml.OFFSET_WITHOUT_REFUND)
		self.assertEqual(write(EXAMPLE_MONTH, offset_requested=True, corrected=True)["Kz29"], "1")

	def test_11085137_kz500_and_its_begruendung_go_together(self):
		document = to_import_file(
			filer(), voranmeldung(supplementary_code="2", begruendung="Siehe Anlage"), CREATED
		)
		self.assertEqual(elements(document)[-2:], [("Kz500", "2"), ("Kz500_Begruendung", "Siehe Anlage")])
		cases = {
			"code without Begründung": ({"supplementary_code": "2"}, ustva_xml.CODE_WITHOUT_BEGRUENDUNG),
			"code with a blank Begründung": (
				{"supplementary_code": "2", "begruendung": " \n "},
				ustva_xml.CODE_WITHOUT_BEGRUENDUNG,
			),
			"Begründung without code": ({"begruendung": "Siehe Anlage"}, ustva_xml.BEGRUENDUNG_WITHOUT_CODE),
		}
		for case, (fields, template) in cases.items():
			with self.subTest(case), self.assertRaises(XmlError) as raised:
				write(EXAMPLE_MONTH, **fields)
			self.assertEqual(raised.exception.template, template)

	def test_kz500_takes_the_codes_of_line_55(self):
		for code in ("1", "2", "3", "4"):
			with self.subTest(code=code):
				self.assertEqual(
					write(EXAMPLE_MONTH, supplementary_code=code, begruendung="x")["Kz500"], code
				)
		for code in ("0", "5", "12", " 1"):
			with self.subTest(code=code), self.assertRaises(XmlError) as raised:
				write(EXAMPLE_MONTH, supplementary_code=code, begruendung="x")
			self.assertEqual(
				(raised.exception.template, raised.exception.values), (ustva_xml.UNKNOWN_CODE, (code,))
			)
		self.assertNotIn("Kz500", write(EXAMPLE_MONTH, supplementary_code=""))

	def test_kz500_and_its_begruendung_can_be_checked_before_the_file_is_made(self):
		self.assertEqual(ustva_xml.supplementary_details(None, None), {})
		self.assertEqual(ustva_xml.supplementary_details("", " \n "), {})
		self.assertEqual(
			ustva_xml.supplementary_details("1", " Siehe  Anlage "),
			{"Kz500": "1", "Kz500_Begruendung": "Siehe Anlage"},
		)
		with self.assertRaises(XmlError):
			ustva_xml.supplementary_details("1", None)

	def test_the_begruendung_is_one_line_of_at_most_180_characters(self):
		text = f"{LOW_QUOTE}Abweichende Rechtsauffassung{LEFT_QUOTE}\n  siehe   Schreiben "
		written = write(EXAMPLE_MONTH, supplementary_code="2", begruendung=text)
		self.assertEqual(written["Kz500_Begruendung"], '"Abweichende Rechtsauffassung" siehe Schreiben')
		self.assertEqual(
			len(write(EXAMPLE_MONTH, supplementary_code="1", begruendung="x" * 180)["Kz500_Begruendung"]), 180
		)
		with self.assertRaises(XmlError) as raised:
			write(EXAMPLE_MONTH, supplementary_code="1", begruendung="x" * 181)
		self.assertEqual(
			(raised.exception.template, raised.exception.values, raised.exception.label),
			(ustva_xml.TEXT_TOO_LONG, (181, 180), ustva_xml.BEGRUENDUNG_LABEL),
		)

	def test_11085153_the_date_of_kz70_lies_in_the_year_of_the_period(self):
		self.assertEqual(write(EXAMPLE_MONTH, regelbesteuerung_from=date(2026, 7, 1))["Kz70"], "01.07.2026")
		with self.assertRaises(XmlError) as raised:
			write(EXAMPLE_MONTH, regelbesteuerung_from=date(2025, 12, 31))
		self.assertEqual(
			(raised.exception.template, raised.exception.values),
			(ustva_xml.SWITCH_IN_ANOTHER_YEAR, (2026, 2025)),
		)

	def test_refuses_kennzahlen_that_are_not_on_the_form(self):
		with self.assertRaises(XmlError) as raised:
			write({"99": d("1"), "83": d("0")})
		self.assertEqual(
			(raised.exception.template, raised.exception.values), (ustva_xml.UNKNOWN_KENNZAHL, ("99", 2026))
		)

	def test_refuses_an_amount_for_a_kennzahl_without_one(self):
		with self.assertRaises(XmlError) as raised:
			write({"10": d("1"), "83": d("0")})
		self.assertEqual((raised.exception.template, raised.exception.values), (ustva_xml.NO_AMOUNT, ("10",)))


class FilerTest(TestCase):
	def test_110085044_the_steuernummer_has_13_digits_with_0_in_the_fifth_place(self):
		self.assertEqual(filer().steuernummer, TEST_STEUERNUMMER)
		for number in (
			"9198111310010",
			"919801131001",
			"91980113100100",
			"198/113/10010",
			"\N{FULLWIDTH DIGIT NINE}198011310010",
			"",
		):
			with self.subTest(number=number), self.assertRaises(XmlError) as raised:
				filer(steuernummer=number)
			self.assertEqual(raised.exception.template, ustva_xml.NOT_A_STEUERNUMMER)

	def test_takes_the_wid_nr_as_de_and_nine_digits(self):
		self.assertEqual(filer(wid_nr=" de 123 456 789 ").wid_nr, "DE123456789")
		self.assertIsNone(filer(wid_nr="  ").wid_nr)
		self.assertIsNone(filer().wid_nr)
		for value in ("DE123456789-00001", "DE12345678", "AT123456789", "123456789"):
			with self.subTest(value=value), self.assertRaises(XmlError) as raised:
				filer(wid_nr=value)
			self.assertEqual(
				(raised.exception.template, raised.exception.values), (ustva_xml.NOT_A_WID_NR, (value,))
			)

	def test_writes_the_wid_nr_after_the_steuernummer(self):
		document = to_import_file(filer(wid_nr="DE123456789"), voranmeldung(), CREATED)
		self.assertEqual(
			elements(document)[:4],
			[
				("Jahr", "2026"),
				("Zeitraum", "10"),
				("Steuernummer", TEST_STEUERNUMMER),
				("WIdNr", "DE123456789"),
			],
		)

	def test_110085075_to_110085078_name_street_postal_code_and_town_are_required(self):
		labels = {
			"name": ustva_xml.NAME_LABEL,
			"street": ustva_xml.STREET_LABEL,
			"postal_code": ustva_xml.POSTAL_CODE_LABEL,
			"city": ustva_xml.TOWN_LABEL,
		}
		for field, label in labels.items():
			for value in ("", " \t ", None):
				with self.subTest(field=field, value=value), self.assertRaises(XmlError) as raised:
					filer(**{field: value})
				self.assertEqual(
					(raised.exception.template, raised.exception.label), (ustva_xml.TEXT_MISSING, label)
				)

	def test_texts_have_at_most_the_length_of_the_schema(self):
		lengths = {"name": 45, "street": 30, "postal_code": 12, "city": 30, "phone": 20, "email": 70}
		for field, length in lengths.items():
			with self.subTest(field=field):
				self.assertEqual(getattr(filer(**{field: "x" * length}), field), "x" * length)
				with self.assertRaises(XmlError) as raised:
					filer(**{field: "x" * (length + 1)})
				self.assertEqual(
					(raised.exception.template, raised.exception.values),
					(ustva_xml.TEXT_TOO_LONG, (length + 1, length)),
				)

	def test_texts_are_transliterated_on_one_line_and_trimmed(self):
		self.assertEqual(filer(name=f" {LOW_QUOTE}Beispiel{LEFT_QUOTE}\n  GmbH ").name, '"Beispiel" GmbH')

	def test_refuses_characters_elster_does_not_take(self):
		with self.assertRaises(XmlError) as raised:
			filer(city="Łódź")
		self.assertEqual(
			(raised.exception.template, raised.exception.values, raised.exception.label),
			(ustva_xml.TEXT_CHARACTERS, ("'Ł' (U+0141), 'ź' (U+017A)",), ustva_xml.TOWN_LABEL),
		)

	def test_writes_phone_and_email_when_given(self):
		def datenlieferant(**fields: object) -> list[tuple[str, str]]:
			root = parse(to_import_file(filer(**fields), voranmeldung(), CREATED))
			(element,) = root.iter("{*}DatenLieferant")
			return children(element)

		self.assertEqual(
			datenlieferant(phone="089 1234567", email="erika@example.org")[-2:],
			[("Telefon", "089 1234567"), ("Email", "erika@example.org")],
		)
		self.assertEqual(
			[name for name, _ in datenlieferant(phone="", email=None)], ["Name", "Strasse", "PLZ", "Ort"]
		)


class CorrectedReturnTest(TestCase):
	def test_writes_zero_for_each_kennzahl_reported_before_and_no_longer(self):
		written = write(
			{"81": d("1000"), "83": d("190.00")}, corrected=True, reported_before={"45", "46", "81"}
		)
		self.assertEqual(
			written,
			{"Kz10": "1", "Kz45": "0", "Kz46": "0", "Kz47": "0.00", "Kz81": "1000", "Kz83": "190.00"},
		)

	def test_only_a_corrected_return_writes_them(self):
		with self.assertRaises(ValueError):
			voranmeldung(reported_before={"45"})

	def test_kennzahlen_reported_before_hold_amounts_on_the_form(self):
		for numbers, template in (({"10"}, ustva_xml.NO_AMOUNT), ({"99"}, ustva_xml.UNKNOWN_KENNZAHL)):
			with self.subTest(numbers=numbers), self.assertRaises(XmlError) as raised:
				write(EXAMPLE_MONTH, corrected=True, reported_before=numbers)
			self.assertEqual(raised.exception.template, template)


class XmlErrorTest(TestCase):
	def test_formats_its_template_with_the_values_and_the_label(self):
		error = XmlError(ustva_xml.TEXT_TOO_LONG, 31, 30, label=ustva_xml.STREET_LABEL)
		self.assertEqual(
			str(error), "The street of the Datenlieferant has 31 characters, ELSTER takes at most 30."
		)
		self.assertEqual(
			(error.template, error.values, error.label),
			(ustva_xml.TEXT_TOO_LONG, (31, 30), ustva_xml.STREET_LABEL),
		)

	def test_every_template_and_label_is_listed_for_translation(self):
		templates = {
			value
			for name, value in vars(ustva_xml).items()
			if name.isupper()
			and isinstance(value, str)
			and value.endswith(".")
			and not name.endswith("_LABEL")
		}
		labels = {value for name, value in vars(ustva_xml).items() if name.endswith("_LABEL")}
		self.assertEqual(set(ustva_xml.MESSAGES), templates)
		self.assertEqual(set(ustva_xml.LABELS), labels)

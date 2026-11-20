from datetime import date
from decimal import Decimal
from pathlib import Path
from unittest import TestCase

from steuerbote.elster import zm_xml
from steuerbote.elster.charset import ALLOWED
from steuerbote.elster.tests.examples import FIXTURES, children
from steuerbote.elster.tests.zm_examples import (
	AUSTRIA,
	FRANCE,
	LINES,
	NORTHERN_IRELAND,
	OCTOBER,
	OWN_VAT_ID,
	child_names,
	find,
	line,
	nutzdaten,
	parse,
	text,
	unternehmer,
	zeilen,
	zm,
)
from steuerbote.elster.ustva_xml import TEXT_CHARACTERS, TEXT_MISSING, TEXT_TOO_LONG, XmlError
from steuerbote.elster.zm_xml import Meldeart, Zm, to_nutzdaten
from steuerbote.zm import rhythm
from steuerbote.zm.correction import as_filed
from steuerbote.zm.errors import ZmError
from steuerbote.zm.lines import NOT_A_VAT_ID, Art, Meldezeile
from steuerbote.zm.period import ReportingPeriod

DOC = Path(__file__).resolve().parents[3] / "docs" / "zm.md"

# The examples of BZSt „Berichtigung einer ZM“ all concern the Spanish Unternehmer P.
P = "ES111111112"
WRONG = "ES111111113"
FEBRUARY = ReportingPeriod.month(2026, 2)
MARCH = ReportingPeriod.month(2026, 3)


def raised(context) -> tuple[str, tuple[object, ...]]:
	return context.exception.template, context.exception.values


def doc_table(heading: str) -> list[list[str]]:
	"""The cells of each row of the table under the heading of docs/zm.md, without its head."""
	text = DOC.read_text(encoding="utf-8")
	section = text[text.index(f"\n{heading}\n") + len(heading) + 2 :]
	section = section[: section.find("\n#")]
	lines = [line for line in section.splitlines() if line.startswith("|")]
	return [[cell.strip() for cell in line.strip().strip("|").split("|")] for line in lines[2:]]


class NutzdatenTest(TestCase):
	def test_writes_the_statement_of_october_byte_for_byte(self):
		self.assertEqual(nutzdaten(), (FIXTURES / "zm_2026_10.xml").read_text(encoding="utf-8"))

	def test_the_root_is_zm_of_version_000005_in_the_namespace_of_elster_xml_11(self):
		"""zm_000005.xsd: „Version des XML-Schemas für ZM. Konstanter Wert: 000005“; the namespace is that of the
		sheet „XML-Schema Namensräume“ of the Jahresdokumentation ZMDO 2."""
		root = parse(nutzdaten())
		self.assertEqual(root.tag, "{http://www.elster.de/elsterxml/schema/v11}zm")
		self.assertEqual(dict(root.attrib), {"version": "000005"})
		self.assertEqual(child_names(root), ["unternehmer"])
		self.assertEqual(child_names(root[0]), ["knri", "zulassNr", "anschrift", "zm-zeilen"])

	def test_is_text_without_declaration_for_the_datenteil(self):
		"""ERiC takes the Nutzdaten into a DatenTeil that goes to ELSTER in UTF-8 (Entwicklerhandbuch, Kap. 5.3.2)."""
		document = nutzdaten()
		self.assertIsInstance(document, str)
		self.assertTrue(
			document.startswith('<zm xmlns="http://www.elster.de/elsterxml/schema/v11" version="000005">\n')
		)
		self.assertTrue(document.endswith("</zm>\n"))

	def test_escapes_what_xml_reserves(self):
		document = nutzdaten(name="Müller & <Söhne>")
		self.assertIn("<name>Müller &amp; &lt;Söhne&gt;</name>", document)
		self.assertEqual(text(document, "unternehmer/anschrift/name"), "Müller & <Söhne>")

	def test_writes_every_character_elster_takes_as_it_is(self):
		"""Standard_E_V2, the character set of the sheet „Allg. Information“, as charset.py holds it."""
		characters = sorted(ALLOWED - {" "})
		for start in range(0, len(characters), 90):
			name = "".join(characters[start : start + 90])
			with self.subTest(name=name):
				self.assertEqual(text(nutzdaten(name=name), "unternehmer/anschrift/name"), name)


class UnternehmerTest(TestCase):
	def test_170015001_170015002_names_the_filer_by_its_german_ust_idnr(self):
		self.assertEqual(text(nutzdaten(), "unternehmer/knri"), OWN_VAT_ID)
		self.assertEqual(unternehmer(ust_idnr="de 123.456.789").ust_idnr, OWN_VAT_ID)
		for value in ("", None, AUSTRIA, "DE12345678", "DE1234567890", "DEX23456789", 123456789):
			with self.subTest(value=value), self.assertRaises(XmlError) as context:
				unternehmer(ust_idnr=value)
			self.assertEqual(raised(context), (zm_xml.NOT_A_GERMAN_VAT_ID, (value,)))

	def test_the_teilnehmernummer_is_n_and_1111111_without_one_of_its_own(self):
		"""Jahresdokumentation ZMDO 2, sheet „ZMDO - Felder“: zulnr1 „Für ERiC ist hier der konstante Wert „N“ zu
		verwenden“ (rule 170015022); zulnr2 „Nachdem das BZSt keine neuen Teilnehmernummern vergibt ist hier, sofern
		keine eigene Teilnehmernummer vorhanden ist, der konstante Wert „1111111“ (siebenmal die 1) einzutragen.“"""
		document = nutzdaten()
		self.assertEqual(
			children(find(document, "unternehmer/zulassNr")), [("zulnr1", "N"), ("zulnr2", "1111111")]
		)
		self.assertIsNone(unternehmer(teilnehmernummer=" ").teilnehmernummer)

	def test_writes_a_teilnehmernummer_of_its_own(self):
		for number in ("0300000", "1234567", "99999999", "1111111"):
			with self.subTest(number=number):
				self.assertEqual(
					children(find(nutzdaten(teilnehmernummer=number), "unternehmer/zulassNr")),
					[("zulnr1", "N"), ("zulnr2", number)],
				)
		self.assertEqual(unternehmer(teilnehmernummer=" 1234567 ").teilnehmernummer, "1234567")

	def test_170015024_a_teilnehmernummer_has_seven_or_eight_digits_from_0300000(self):
		for number in (
			"0299999",
			"0000000",
			"123456",
			"123456789",
			"12a4567",
			"-123456",
			"123456\N{SUPERSCRIPT ONE}",
		):
			with self.subTest(number=number), self.assertRaises(XmlError) as context:
				unternehmer(teilnehmernummer=number)
			self.assertEqual(raised(context), (zm_xml.NOT_A_TEILNEHMERNUMMER, (number,)))

	def test_170025001_to_170025004_name_street_town_and_country_are_required(self):
		labels = {
			"name": zm_xml.NAME_LABEL,
			"street": zm_xml.STREET_LABEL,
			"city": zm_xml.TOWN_LABEL,
			"country": zm_xml.COUNTRY_LABEL,
		}
		for field, label in labels.items():
			for value in ("", " \t ", None):
				with self.subTest(field=field, value=value), self.assertRaises(XmlError) as context:
					unternehmer(**{field: value})
				self.assertEqual((context.exception.template, context.exception.label), (TEXT_MISSING, label))

	def test_texts_have_at_most_the_length_of_the_schema(self):
		lengths = {
			"name": 100,
			"address_suffix": 40,
			"street": 30,
			"house_number": 10,
			"house_number_suffix": 10,
			"city": 30,
		}
		for field, length in lengths.items():
			with self.subTest(field=field):
				self.assertEqual(getattr(unternehmer(**{field: "x" * length}), field), "x" * length)
				with self.assertRaises(XmlError) as context:
					unternehmer(**{field: "x" * (length + 1)})
				self.assertEqual(raised(context), (TEXT_TOO_LONG, (length + 1, length)))
				self.assertEqual(context.exception.label, zm_xml.ANSCHRIFT[field].label)

	def test_texts_are_transliterated_on_one_line_and_trimmed(self):
		filer = unternehmer(
			name=" \N{DOUBLE LOW-9 QUOTATION MARK}Beispiel\N{LEFT DOUBLE QUOTATION MARK}\n  GmbH "
		)
		self.assertEqual(filer.name, '"Beispiel" GmbH')
		self.assertEqual(unternehmer(street="Hauptstraße\N{NO-BREAK SPACE}1").street, "Hauptstraße 1")

	def test_refuses_characters_elster_does_not_take(self):
		with self.assertRaises(XmlError) as context:
			unternehmer(city="Łódź")
		self.assertEqual(raised(context), (TEXT_CHARACTERS, ("'Ł' (U+0141), 'ź' (U+017A)",)))
		self.assertEqual(context.exception.label, zm_xml.TOWN_LABEL)

	def test_writes_the_address_in_the_order_of_the_schema(self):
		document = nutzdaten(
			address_suffix="Hinterhaus",
			street="Hauptstraße",
			house_number="1",
			house_number_suffix="a",
			phone="089 1234567",
		)
		self.assertEqual(
			children(find(document, "unternehmer/anschrift")),
			[
				("name", "Beispiel GmbH"),
				("adresszusatz", "Hinterhaus"),
				("strasse", "Hauptstraße"),
				("hausnr", "1"),
				("hausnrzusatz", "a"),
				("plz", "80331"),
				("ort", "München"),
				("staat", "DE"),
				("telefon", "089 1234567"),
			],
		)
		self.assertEqual(
			child_names(find(nutzdaten(address_suffix=" ", phone=""), "unternehmer/anschrift")),
			["name", "strasse", "plz", "ort", "staat"],
		)

	def test_170025005_170025006_a_german_address_has_a_postal_code_from_01001_to_99999(self):
		for code in ("01001", "01099", "01100", "09999", "10000", "99999"):
			with self.subTest(code=code):
				self.assertEqual(unternehmer(postal_code=code).postal_code, code)
		with self.assertRaises(XmlError) as context:
			unternehmer(postal_code=None)
		self.assertEqual(
			(context.exception.template, context.exception.label), (TEXT_MISSING, zm_xml.POSTAL_CODE_LABEL)
		)
		for code in ("01000", "00999", "1234", "123456", "8033a", "803 31", "D-80331"):
			with self.subTest(code=code), self.assertRaises(XmlError) as context:
				unternehmer(postal_code=code)
			self.assertEqual(raised(context), (zm_xml.NOT_A_GERMAN_POSTAL_CODE, (code,)))

	def test_a_foreign_postal_code_is_optional_of_letters_digits_and_blanks(self):
		"""Field plz: „Im Feld '$Feld$' sind folgende Zeichen erlaubt: Ziffern (0-9), Buchstaben (a-z, A-Z) (keine
		Umlaute) und Leerzeichen.“"""
		self.assertIsNone(unternehmer(country="AT", postal_code=None).postal_code)
		self.assertEqual(unternehmer(country="NL", postal_code="1011 AB").postal_code, "1011 AB")
		self.assertEqual(unternehmer(country="XI", postal_code="BT1 1AA").postal_code, "BT1 1AA")
		for code in ("1011-AB", "Wien Ä"):
			with self.subTest(code=code), self.assertRaises(XmlError) as context:
				unternehmer(country="AT", postal_code=code)
			self.assertEqual(raised(context), (zm_xml.NOT_A_POSTAL_CODE, (code,)))
		with self.assertRaises(XmlError) as context:
			unternehmer(country="AT", postal_code="x" * 13)
		self.assertEqual(raised(context), (TEXT_TOO_LONG, (13, 12)))

	def test_the_country_is_a_code_the_documentation_lists(self):
		"""Field staat, the Benutzerdefinierte Typdefinition ISO_3166_1_2stellig 6 with XL, XI and XU."""
		self.assertEqual(unternehmer().country, "DE")
		self.assertEqual(text(nutzdaten(country="at", postal_code=None), "unternehmer/anschrift/staat"), "AT")
		self.assertEqual(unternehmer(country=" XU ", postal_code=None).country, "XU")
		self.assertEqual(len(zm_xml.COUNTRIES), 253)
		for value in ("XX", "D", "DEU", "Deutschland", "EL", 49):
			with self.subTest(value=value), self.assertRaises(XmlError) as context:
				unternehmer(country=value, postal_code=None)
			self.assertEqual(raised(context), (zm_xml.UNKNOWN_COUNTRY, (value,)))

	def test_170045020_the_address_names_northern_ireland_or_the_rest_of_the_united_kingdom_not_gb(self):
		with self.assertRaises(XmlError) as context:
			unternehmer(country="gb", postal_code=None)
		self.assertEqual(raised(context), (zm_xml.UNITED_KINGDOM_ADDRESS, ()))

	def test_the_phone_takes_digits_blanks_and_the_characters_of_the_schema(self):
		"""zm_000005.xsd, telefon: „Zulässige Zeichen sind die Ziffern 0-9, /, \\, (, ), +, - und das Leerzeichen.“;
		its pattern and the Jahresdokumentation ZMDO 2 leave out the backslash."""
		for phone in ("+49 (89) 123/456-78", "04711", "1" * 20):
			with self.subTest(phone=phone):
				self.assertEqual(unternehmer(phone=phone).phone, phone)
		for phone in ("089 1234567 ext. 5", "089\\1234", "+49 89 1234567 #2"):
			with self.subTest(phone=phone), self.assertRaises(XmlError) as context:
				unternehmer(phone=phone)
			self.assertEqual(raised(context), (zm_xml.NOT_A_PHONE, (phone,)))
		with self.assertRaises(XmlError) as context:
			unternehmer(phone="1" * 21)
		self.assertEqual(raised(context), (TEXT_TOO_LONG, (21, 20)))


class LinesTest(TestCase):
	def test_writes_art_ust_idnr_and_sum_of_each_line_in_the_order_given(self):
		self.assertEqual(
			zeilen(nutzdaten()),
			[("L", AUSTRIA, "12000"), ("S", FRANCE, "3500"), ("L", NORTHERN_IRELAND, "-250")],
		)
		zeile = find(nutzdaten(), "unternehmer/zm-zeilen")[3]
		self.assertEqual((dict(zeile.attrib), child_names(zeile)), ({"umsatzart": "L"}, ["knre", "betrag"]))

	def test_170045002_reports_at_least_one_line(self):
		"""„Es wurden keine Meldezeilen angegeben. Bitte beachten Sie, dass Nullmeldungen nicht zulässig sind.“"""
		with self.assertRaises(XmlError) as context:
			zm(())
		self.assertEqual(raised(context), (zm_xml.NO_LINES, ("Oktober 2026",)))

	def test_takes_at_most_5000_lines(self):
		"""Jahresdokumentation ZMDO 2, sheet „ZMDO - Felder“: max. Zeilen 5000 for umsatzart, knre and betrag."""
		lines = [line(f"ATU{number:08d}", Art.L, "1") for number in range(5001)]
		self.assertEqual(len(zm(lines[:5000]).reported), 5000)
		with self.assertRaises(XmlError) as context:
			zm(lines)
		self.assertEqual(raised(context), (zm_xml.TOO_MANY_LINES, (5001, 5000)))

	def test_170045003_to_170045005_reports_each_ust_idnr_and_art_once(self):
		"""„Bitte addieren Sie die Beträge. Die Eingabedatei enthält mindestens 1 weitere Zeile, die bis auf den
		Betrag identisch mit dieser Zeile ist“."""
		for art in Art:
			with self.subTest(art=art), self.assertRaises(XmlError) as context:
				zm([line(AUSTRIA, art, "100"), line(FRANCE, Art.L, "1"), line(AUSTRIA, art, "200")])
			self.assertEqual(raised(context), (zm_xml.LINE_TWICE, (AUSTRIA, art.value)))

	def test_one_ust_idnr_reports_each_art_in_a_line_of_its_own(self):
		lines = [line(AUSTRIA, Art.L, "100"), line(AUSTRIA, Art.D, "200"), line(AUSTRIA, Art.S, "300")]
		self.assertEqual(
			zeilen(nutzdaten(zm(lines))),
			[("L", AUSTRIA, "100"), ("D", AUSTRIA, "200"), ("S", AUSTRIA, "300")],
		)

	def test_sums_are_whole_euros_with_a_minus_sign_where_negative(self):
		"""betrag: GeldBetragOhneCent, Formatkennzeichen N „Mit Vorzeichen, Null erlaubt“, without leading zeros and
		without a sign for 0 (sheet „Formale Fehler“); a negative sum stays in its line (Anleitung zur ZM, IV.10)."""
		lines = [line(AUSTRIA, Art.L, "-1"), line(FRANCE, Art.L, "1000"), line(P, Art.L, "1E+3")]
		self.assertEqual([amount for _, _, amount in zeilen(nutzdaten(zm(lines)))], ["-1", "1000", "1000"])

	def test_sums_have_at_most_eleven_digits(self):
		"""zm_000005.xsd, betrag_Type from -99999999999 to 99999999999; „maximal 12 Stellen“ with the minus sign."""
		for amount in ("99999999999", "-99999999999"):
			with self.subTest(amount=amount):
				self.assertEqual(zeilen(nutzdaten(zm([line(AUSTRIA, Art.L, amount)])))[0][2], amount)
		for amount in ("100000000000", "-100000000000"):
			with self.subTest(amount=amount), self.assertRaises(XmlError) as context:
				zm([line(AUSTRIA, Art.L, amount)])
			self.assertEqual(raised(context), (zm_xml.TOO_MANY_DIGITS, (AUSTRIA, "L", int(amount))))

	def test_170045001_a_line_of_the_statement_reports_a_sum(self):
		"""„Nullmeldungen sind nicht abzugeben“; only a Berichtigung writes 0, for a line it cancels."""
		for fields in ({}, {"filed": {}}):
			for amount in ("0", "-0"):
				with self.subTest(fields=fields, amount=amount), self.assertRaises(XmlError) as context:
					zm([line(AUSTRIA, Art.L, "100"), line(FRANCE, Art.S, amount)], **fields)
				self.assertEqual(raised(context), (zm_xml.ZERO_LINE, (FRANCE, "S")))

	def test_170045021_northern_ireland_only_for_goods(self):
		"""„Nordirische UStIDs (Präfix XI) dürfen nicht für sonstige Leistungen verwendet werden“: a Meldezeile cannot
		hold such a line (steuerbote.zm.ustid), so the Nutzdaten never carry one."""
		lines = [line(NORTHERN_IRELAND, Art.L, "100"), line(NORTHERN_IRELAND, Art.D, "200")]
		self.assertEqual(
			zeilen(nutzdaten(zm(lines))), [("L", NORTHERN_IRELAND, "100"), ("D", NORTHERN_IRELAND, "200")]
		)
		with self.assertRaises(ZmError):
			line(NORTHERN_IRELAND, Art.S, "100")

	def test_170045022_northern_ireland_from_2021(self):
		"""„Nordirische Umsatzsteuer-Identifikationsnummern sind nur für Meldezeiträume ab dem 01.01.2021 erlaubt.“"""
		zm([line(NORTHERN_IRELAND, Art.L, "100")], ReportingPeriod.month(2021, 1))
		with self.assertRaises(XmlError) as context:
			zm(
				[line(AUSTRIA, Art.L, "1"), line(NORTHERN_IRELAND, Art.D, "100")],
				ReportingPeriod.quarter(2020, 4),
			)
		self.assertEqual(raised(context), (zm_xml.NORTHERN_IRELAND_TOO_EARLY, (NORTHERN_IRELAND, "D", 2020)))


class HeadOfTheLinesTest(TestCase):
	def test_writes_euro_meldeart_notices_and_the_meldezeitraum_before_the_lines(self):
		"""waehrung: „Im Feld '$Feld$' ist nur der Wert "1" zulässig.“ (Euro)."""
		element = find(nutzdaten(), "unternehmer/zm-zeilen")
		self.assertEqual(list(element.attrib.items()), [("waehrung", "1"), ("meldeart", "10")])
		self.assertEqual(child_names(element), ["anzeige", "widerruf", "mzr", "zeile", "zeile", "zeile"])
		self.assertEqual(children(element[2]), [("quart", "30"), ("jahr", "2026")])

	def test_writes_the_quart_of_each_meldezeitraum(self):
		"""quart: 21 to 32 for the months, 11 to 14 for two months, 1 to 4 for the quarters and 5 for the year."""
		periods = [
			*(ReportingPeriod.month(2025, month) for month in range(1, 13)),
			*(ReportingPeriod.two_months(2025, quarter) for quarter in range(1, 5)),
			*(ReportingPeriod.quarter(2025, quarter) for quarter in range(1, 5)),
			ReportingPeriod.calendar_year(2025),
		]
		codes = [text(nutzdaten(zm(period=period)), "unternehmer/zm-zeilen/mzr/quart") for period in periods]
		self.assertEqual(codes, [str(code) for code in (*range(21, 33), *range(11, 15), *range(1, 5), 5)])
		self.assertEqual(text(nutzdaten(zm(period=periods[0])), "unternehmer/zm-zeilen/mzr/jahr"), "2025")

	def test_anzeige_and_widerruf_are_always_written(self):
		"""Both are Pflichtfelder (170015006, 170015009) of the kind JaNein, true or false."""
		document = nutzdaten(zm(anzeige=True))
		self.assertEqual(text(document, "unternehmer/zm-zeilen/anzeige"), "true")
		self.assertEqual(text(document, "unternehmer/zm-zeilen/widerruf"), "false")
		document = nutzdaten(zm(period=ReportingPeriod.quarter(2026, 3), widerruf=True))
		self.assertEqual(text(document, "unternehmer/zm-zeilen/anzeige"), "false")
		self.assertEqual(text(document, "unternehmer/zm-zeilen/widerruf"), "true")

	def test_170015008_the_anzeige_comes_with_a_monthly_zm(self):
		for period in (
			ReportingPeriod.quarter(2026, 3),
			ReportingPeriod.two_months(2026, 3),
			ReportingPeriod.calendar_year(2025),
		):
			with self.subTest(period=period.label), self.assertRaises(XmlError) as context:
				zm(period=period, anzeige=True)
			self.assertEqual(raised(context), (rhythm.ANZEIGE_ONLY_MONTHLY, (period.label,)))

	def test_170015012_the_widerruf_comes_with_a_quarter_or_its_third_month(self):
		for period in (ReportingPeriod.quarter(2026, 3), ReportingPeriod.month(2026, 9)):
			with self.subTest(period=period.label):
				self.assertTrue(zm(period=period, widerruf=True).widerruf)
		for period in (
			ReportingPeriod.month(2026, 10),
			ReportingPeriod.two_months(2026, 3),
			ReportingPeriod.calendar_year(2025),
		):
			with self.subTest(period=period.label), self.assertRaises(XmlError) as context:
				zm(period=period, widerruf=True)
			self.assertEqual(raised(context), (rhythm.WIDERRUF_ONLY_QUARTERLY, (period.label,)))

	def test_170015013_not_both_anzeige_and_widerruf(self):
		with self.assertRaises(XmlError) as context:
			zm(period=ReportingPeriod.month(2026, 9), anzeige=True, widerruf=True)
		self.assertEqual(raised(context), (rhythm.ANZEIGE_AND_WIDERRUF, ()))

	def test_anzeige_and_widerruf_are_bools(self):
		for flags in ({"anzeige": 1}, {"widerruf": "false"}):
			with self.subTest(flags=flags), self.assertRaises(TypeError):
				zm(**flags)


class BerichtigungTest(TestCase):
	"""BZSt „Berichtigung einer ZM“: „Korrekt gemeldete Angaben sind in der berichtigten ZM nicht zu wiederholen.“
	A line with a wrong sum is reported with the right one (Anleitung zur ZM, IV.12.2), and a line filed under a
	wrong USt-IdNr., Art or Meldezeitraum with 0 (IV.12); steuerbote.zm.correction.correct() decides which lines,
	the cases are those of the BZSt."""

	def berichtigung(self, period: ReportingPeriod, filed: list[Meldezeile], current: list[Meldezeile]) -> Zm:
		return Zm(period, tuple(current), filed=as_filed(filed))

	def test_meldeart_10_for_an_erstmeldung_and_11_for_a_berichtigung(self):
		erstmeldung = zm()
		berichtigung = self.berichtigung(OCTOBER, [line(AUSTRIA, Art.L, "1")], list(LINES))
		self.assertEqual(
			(erstmeldung.meldeart, berichtigung.meldeart), (Meldeart.ERSTMELDUNG, Meldeart.BERICHTIGUNG)
		)
		self.assertEqual(find(nutzdaten(erstmeldung), "unternehmer/zm-zeilen").get("meldeart"), "10")
		self.assertEqual(find(nutzdaten(berichtigung), "unternehmer/zm-zeilen").get("meldeart"), "11")

	def test_an_erstmeldung_reports_every_line(self):
		self.assertEqual(zm().reported, LINES)

	def test_1_reports_only_the_missing_line(self):
		statement = self.berichtigung(
			MARCH, [line(FRANCE, Art.L, "700")], [line(FRANCE, Art.L, "700"), line(P, Art.L, "5000")]
		)
		self.assertEqual(zeilen(nutzdaten(statement)), [("L", P, "5000")])

	def test_2_cancels_a_line_of_the_wrong_meldezeitraum_with_0(self):
		statement = self.berichtigung(FEBRUARY, [line(P, Art.L, "13000")], [])
		self.assertEqual(zeilen(nutzdaten(statement)), [("L", P, "0")])

	def test_3_cancels_a_wrong_ust_idnr_with_0_and_reports_the_right_one(self):
		statement = self.berichtigung(MARCH, [line(WRONG, Art.L, "21000")], [line(P, Art.L, "21000")])
		self.assertEqual(zeilen(nutzdaten(statement)), [("L", WRONG, "0"), ("L", P, "21000")])

	def test_4_reports_the_right_sum_not_the_difference(self):
		statement = self.berichtigung(MARCH, [line(P, Art.L, "30000")], [line(P, Art.L, "20000")])
		self.assertEqual(zeilen(nutzdaten(statement)), [("L", P, "20000")])

	def test_5_cancels_a_wrong_art_with_0_and_reports_the_right_one(self):
		statement = self.berichtigung(MARCH, [line(P, Art.S, "20000")], [line(P, Art.L, "20000")])
		self.assertEqual(zeilen(nutzdaten(statement)), [("S", P, "0"), ("L", P, "20000")])

	def test_a_berichtigung_that_changes_nothing_is_not_filed(self):
		with self.assertRaises(XmlError) as context:
			self.berichtigung(OCTOBER, list(LINES), list(LINES))
		self.assertEqual(raised(context), (zm_xml.NOTHING_TO_CORRECT, ("Oktober 2026",)))

	def test_cancels_only_lines_the_zm_can_have_reported(self):
		with self.assertRaises(XmlError) as context:
			Zm(OCTOBER, LINES, filed={(OWN_VAT_ID, Art.L): Decimal("5")})
		self.assertEqual(raised(context), (NOT_A_VAT_ID, (OWN_VAT_ID, "L")))

	def test_keeps_what_the_bzst_holds_as_it_was_given(self):
		filed = {(AUSTRIA, Art.L): Decimal("12000")}
		statement = Zm(OCTOBER, LINES, filed=filed)
		filed[(AUSTRIA, Art.L)] = Decimal("1")
		self.assertEqual(dict(statement.filed), {(AUSTRIA, Art.L): Decimal("12000")})
		self.assertEqual(
			zeilen(nutzdaten(statement)), [("S", FRANCE, "3500"), ("L", NORTHERN_IRELAND, "-250")]
		)


class MeldezeitraumTest(TestCase):
	"""The rules of the Jahresdokumentation ZMDO 2 that compare the Meldezeitraum with „Heute“, the day of the
	transmission, which is the day the Nutzdaten are written."""

	def test_170015020_the_meldezeitraum_has_begun(self):
		to_nutzdaten(unternehmer(), zm(), date(2026, 10, 1))
		for created in (date(2026, 9, 30), date(2025, 12, 31)):
			with self.subTest(created=created), self.assertRaises(XmlError) as context:
				to_nutzdaten(unternehmer(), zm(), created)
			self.assertEqual(raised(context), (zm_xml.NOT_BEGUN, ("Oktober 2026",)))
		quarter = zm(period=ReportingPeriod.quarter(2026, 4))
		to_nutzdaten(unternehmer(), quarter, date(2026, 10, 1))
		with self.assertRaises(XmlError):
			to_nutzdaten(unternehmer(), quarter, date(2026, 9, 30))

	def test_170015019_a_zm_for_two_months_from_the_first_day_of_its_second_month(self):
		"""„Eine Abgabe der ZM für diesen Meldezeitraum ist erst ab dem 1. Tag des zweiten Monats des Quartals
		möglich.“"""
		statement = zm(period=ReportingPeriod.two_months(2026, 2))
		to_nutzdaten(unternehmer(), statement, date(2026, 5, 1))
		with self.assertRaises(XmlError) as context:
			to_nutzdaten(unternehmer(), statement, date(2026, 4, 30))
		self.assertEqual(raised(context), (zm_xml.TWO_MONTHS_TOO_EARLY, ("April und Mai 2026",)))

	def test_170015016_ten_years_back(self):
		"""„Es werden 10 Jahre rückwirkend unterstützt“: a year before the year of the day less 10 is refused."""
		austria = [line(AUSTRIA, Art.L, "100")]
		to_nutzdaten(unternehmer(), zm(austria, ReportingPeriod.month(2016, 1)), date(2026, 12, 31))
		with self.assertRaises(XmlError) as context:
			to_nutzdaten(unternehmer(), zm(austria, ReportingPeriod.month(2015, 12)), date(2026, 1, 1))
		self.assertEqual(raised(context), (zm_xml.TOO_OLD, ("Dezember 2015", 2016)))


class TransmissionTest(TestCase):
	def test_zmdo_is_a_datenart_of_elster_extern_sent_with_send_auth(self):
		"""ERiC-Entwicklerhandbuch 44.3.6.0, Tabelle 8-28: Verfahren ElsterExtern, Datenart ZMDO, send-Auth „Ja“,
		send-NoSig „Nein“."""
		self.assertEqual(
			(zm_xml.VERFAHREN, zm_xml.DATENART, zm_xml.VORGANG), ("ElsterExtern", "ZMDO", "send-Auth")
		)

	def test_the_datenart_version_and_plugin_of_zmdo(self):
		"""Datenartversionmatrix.ods: datenartVersion ZMDO without a year, Plugin-Bibliothek checkZMDO, on Linux
		lib<eric_plugin_bibliothek>.so (Entwicklerhandbuch, Kap. 3.1.6.1)."""
		self.assertEqual(
			(zm_xml.DATENART_VERSION, zm_xml.PLUGIN, zm_xml.PLUGIN_LIBRARY),
			("ZMDO", "checkZMDO", "libcheckZMDO.so"),
		)

	def test_the_recipient_is_bf(self):
		"""Tabelle 8-28: <Empfaenger> with the attribute id "L"; Jahresdokumentation ZMDO 2: EmpfaengerName BF with
		the NutzdatenHeader version 11."""
		self.assertEqual((zm_xml.EMPFAENGER_ID, zm_xml.EMPFAENGER), ("L", "BF"))


class XmlErrorTest(TestCase):
	def test_formats_its_template_with_the_values(self):
		error = XmlError(zm_xml.LINE_TWICE, AUSTRIA, "L")
		self.assertEqual(
			str(error), "The Meldezeile ATU12345678 L appears twice; its amounts belong in one line."
		)

	def test_every_template_and_label_is_listed_for_translation(self):
		templates = {
			value
			for name, value in vars(zm_xml).items()
			if name.isupper()
			and isinstance(value, str)
			and value.endswith(".")
			and not name.endswith("_LABEL")
		}
		labels = {value for name, value in vars(zm_xml).items() if name.endswith("_LABEL")}
		self.assertEqual(set(zm_xml.MESSAGES), templates)
		self.assertEqual(set(zm_xml.LABELS), labels)
		self.assertEqual({field.label for field in zm_xml.ANSCHRIFT.values()}, labels)


class DocsTest(TestCase):
	def test_the_documentation_names_what_the_transmission_needs(self):
		"""docs/zm.md, „Was die Übermittlung braucht“."""
		cells = {row[0]: row[1] for row in doc_table("### Was die Übermittlung braucht")}
		expected = {
			"Verfahren": zm_xml.VERFAHREN,
			"Datenart": zm_xml.DATENART,
			"Vorgang": zm_xml.VORGANG,
			"datenartVersion": zm_xml.DATENART_VERSION,
			"Plugin": zm_xml.PLUGIN,
		}
		self.assertEqual({name: cells[name].split("`")[1] for name in expected}, expected)
		self.assertIn(f"`{zm_xml.PLUGIN_LIBRARY}`", cells["Plugin"])
		self.assertIn(
			f'`<Empfaenger id="{zm_xml.EMPFAENGER_ID}">{zm_xml.EMPFAENGER}</Empfaenger>`',
			cells["Empfänger im NutzdatenHeader"],
		)

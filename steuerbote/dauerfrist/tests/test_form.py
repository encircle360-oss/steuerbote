"""Form USt 1 H as ELSTER takes it: the two contexts, their fields and the rules of the Jahresdokumentation."""

from decimal import Decimal
from unittest import TestCase

from lxml import etree

from steuerbote.dauerfrist.form import (
	BEGRUENDUNG_TOO_LONG,
	BEGRUENDUNG_WITHOUT_CODE,
	CODE_WITHOUT_BEGRUENDUNG,
	LATEST_YEAR,
	LAYOUTS,
	MESSAGES,
	NEGATIVE,
	NO_LAYOUT,
	NOT_IN_CONTEXT,
	NOT_WHOLE_EUROS,
	OFFSET_WITHOUT_CORRECTION,
	SONDERVORAUSZAHLUNG_MISSING,
	TOO_MANY_DIGITS,
	UNKNOWN_CODE,
	Context,
	Format,
	FormError,
	Severity,
	Ust1H,
	layout_for,
)
from steuerbote.dauerfrist.tests import jahresdokumentation
from steuerbote.elster.tests import eric_schema
from steuerbote.ustva import Rhythm

DF = Context.DAUERFRISTVERLAENGERUNG
SVZ = Context.UMSATZSTEUERSONDERVORAUSZAHLUNG
XS = {"xs": "http://www.w3.org/2001/XMLSchema"}


def anmeldung(**changes: object) -> Ust1H:
	"""An Anmeldung der Sondervorauszahlung 2026 of 4.000 €, as in the example of the Anleitung USt 5 E."""
	values: dict[str, object] = {"year": 2026, "context": SVZ, "sondervorauszahlung": Decimal("4000")}
	values.update(changes)
	return Ust1H(**values)  # type: ignore[arg-type]


def antrag(**changes: object) -> Ust1H:
	"""The Antrag auf Dauerfristverlängerung 2026 of a quarterly filer."""
	values: dict[str, object] = {"year": 2026, "context": DF}
	values.update(changes)
	return Ust1H(**values)  # type: ignore[arg-type]


class ContextTest(TestCase):
	def test_a_monthly_filer_files_the_sondervorauszahlung(self):
		self.assertIs(Context.for_rhythm(Rhythm.MONTHLY), SVZ)
		self.assertTrue(SVZ.with_sondervorauszahlung)

	def test_a_quarterly_filer_files_the_antrag_alone(self):
		self.assertIs(Context.for_rhythm(Rhythm.QUARTERLY), DF)
		self.assertFalse(DF.with_sondervorauszahlung)

	def test_takes_the_value_of_the_rhythm(self):
		self.assertIs(Context.for_rhythm("monthly"), SVZ)  # type: ignore[arg-type]
		with self.assertRaises(ValueError):
			Context.for_rhythm("yearly")  # type: ignore[arg-type]

	def test_values_are_the_element_names_of_the_schema(self):
		self.assertEqual(DF.value, "Dauerfristverlaengerung")
		self.assertEqual(SVZ.value, "Umsatzsteuersondervorauszahlung")


class LayoutTest(TestCase):
	def test_knows_2026(self):
		self.assertEqual(LATEST_YEAR, max(LAYOUTS))
		self.assertEqual(layout_for(2026).year, 2026)
		self.assertIs(layout_for(2026), LAYOUTS[2026])

	def test_refuses_a_year_without_layout(self):
		with self.assertRaises(FormError) as caught:
			layout_for(LATEST_YEAR + 1)
		self.assertEqual(caught.exception.template, NO_LAYOUT)
		self.assertEqual(
			str(caught.exception), f"Steuerbote does not know form USt 1 H for {LATEST_YEAR + 1} yet."
		)

	def test_refuses_what_is_no_year(self):
		for year in ("2026", True, 2026.0):
			with self.subTest(year=year), self.assertRaises(TypeError):
				layout_for(year)  # type: ignore[arg-type]

	def test_the_antrag_alone_carries_kz09_and_kz500(self):
		self.assertEqual(
			layout_for(2026).elements(DF),
			("Jahr", "Steuernummer", "WIdNr", "Kz09", "Kz500", "Kz500_Begruendung"),
		)

	def test_the_sondervorauszahlung_carries_its_kennzahlen(self):
		self.assertEqual(
			layout_for(2026).elements(SVZ),
			(
				*("Jahr", "Steuernummer", "WIdNr", "Kz09", "Kz10", "Kz26", "Kz29", "Kz38", "Kz500"),
				"Kz500_Begruendung",
			),
		)

	def test_names_the_line_of_the_form(self):
		layout = layout_for(2026)
		lines = {field.element: field.line for field in layout.fields[SVZ]}
		self.assertEqual(
			lines,
			{
				**{"Jahr": None, "Steuernummer": None, "WIdNr": 2, "Kz09": 6, "Kz10": 7, "Kz26": 11},
				**{"Kz29": 10, "Kz38": 9, "Kz500": 12, "Kz500_Begruendung": 12},
			},
		)

	def test_kz38_is_whole_euros_without_sign(self):
		field = layout_for(2026).field(SVZ, "Kz38")
		self.assertIs(field.format, Format.WHOLE_EUROS)
		self.assertEqual((field.min_length, field.max_length), (1, 13))

	def test_a_context_has_no_field_of_the_other(self):
		with self.assertRaises(KeyError):
			layout_for(2026).field(DF, "Kz38")

	def test_rules_are_fehler_or_hinweis(self):
		rules = layout_for(2026).rules
		self.assertEqual(
			{rule.code for rule in rules if rule.severity is Severity.HINT},
			{"11085154", "11085155", "110085049"},
		)
		self.assertEqual(len(rules), 20)

	def test_finds_a_rule_by_its_name(self):
		rule = layout_for(2026).rule(SVZ, "Svz_Kz29_ohne_Kz10")
		self.assertEqual((rule.code, rule.severity, rule.context), ("11085150", Severity.ERROR, SVZ))
		with self.assertRaises(KeyError):
			layout_for(2026).rule(DF, "Svz_Kz29_ohne_Kz10")


class Layout2027Test(TestCase):
	"""Form USt 1 H 2027 as Jahresdokumentation_UStVA_2027.ods of the beta ERiC 45.1.5.0 has it, against 2026: the
	same fields in both contexts but Kz 09, which takes the Hersteller-ID alone, without the two rules on its length;
	the lines and labels of form USt 1 H 2026 until the BMF letter with the form of 2027 (steuerbote/ustva/years.py)."""

	def setUp(self):
		self.layout = layout_for(2027)
		self.before = layout_for(2026)

	def test_knows_2027(self):
		self.assertIs(self.layout, LAYOUTS[2027])
		self.assertEqual(self.layout.year, 2027)

	def test_both_contexts_keep_the_fields_of_2026(self):
		for context in Context:
			with self.subTest(context=context):
				self.assertEqual(self.layout.elements(context), self.before.elements(context))

	def test_every_field_but_kz09_and_the_year_of_kz38_is_that_of_2026(self):
		for context in Context:
			for field in self.layout.fields[context]:
				if field.element in ("Kz09", "Kz38"):
					continue
				with self.subTest(context=context, element=field.element):
					self.assertEqual(field, self.before.field(context, field.element))

	def test_kz09_takes_the_hersteller_id_of_five_digits_alone(self):
		for context in Context:
			field = self.layout.field(context, "Kz09")
			with self.subTest(context=context):
				self.assertEqual(
					(field.regex, field.format, field.min_length, field.max_length, field.line),
					(r"^(?=.{5,5}$)[0-9]+", Format.GENERAL, 5, 5, 6),
				)
				self.assertTrue(field.accepts("12345"))
				for text in ("12345*Berater*Mandant*1*2*3", "1234", "123456", "1234a"):
					self.assertFalse(field.accepts(text), text)
				self.assertTrue(self.before.field(context, "Kz09").accepts("12345*Berater*Mandant*1*2*3"))

	def test_110085046_the_rules_on_the_length_of_kz09_are_gone(self):
		names = {rule.name for rule in self.layout.rules}
		self.assertFalse({"Df_Kz09_Laenge", "Svz_Kz09_Laenge"} & names)
		self.assertEqual(
			[rule for rule in self.before.rules if rule.code != "110085046"], list(self.layout.rules)
		)
		self.assertEqual(len(self.layout.rules), 18)

	def test_kz38_is_the_sondervorauszahlung_2027_on_line_9(self):
		field = self.layout.field(SVZ, "Kz38")
		self.assertEqual((field.label, field.line), ("Davon 1/11 = Sondervorauszahlung 2027", 9))
		self.assertEqual(field.regex, self.before.field(SVZ, "Kz38").regex)

	def test_files_the_anmeldung_and_the_antrag_of_2027(self):
		filing = anmeldung(year=2027, corrected=True, offset_requested=True)
		self.assertEqual(
			list(filing.texts().items()),
			[("Jahr", "2027"), ("Kz10", "1"), ("Kz29", "1"), ("Kz38", "4000")],
		)
		self.assertEqual(antrag(year=2027).texts(), {"Jahr": "2027"})

	def test_110085049_the_hint_on_kz500_stays(self):
		filing = antrag(year=2027, supplementary_code="1", begruendung="Sachverhalt")
		self.assertEqual(
			[(rule.code, rule.name, rule.severity) for rule in filing.hints],
			[("110085049", "Kz500_Hinweis", Severity.HINT)],
		)

	def test_11085150_kz29_still_needs_kz10(self):
		with self.assertRaises(FormError) as caught:
			anmeldung(year=2027, offset_requested=True)
		self.assertEqual(
			(caught.exception.template, caught.exception.rule.code), (OFFSET_WITHOUT_CORRECTION, "11085150")
		)


class FieldTest(TestCase):
	def accepts(self, context: Context, element: str, text: str) -> bool:
		return layout_for(2026).field(context, element).accepts(text)

	def test_jahr_has_four_digits(self):
		self.assertTrue(self.accepts(DF, "Jahr", "2026"))
		self.assertFalse(self.accepts(DF, "Jahr", "26"))
		self.assertFalse(self.accepts(DF, "Jahr", "٢٠٢٦"))

	def test_steuernummer_has_thirteen_digits_with_a_zero_in_the_fifth(self):
		self.assertTrue(self.accepts(SVZ, "Steuernummer", "9198011310010"))
		self.assertFalse(self.accepts(SVZ, "Steuernummer", "9198111310010"))
		self.assertFalse(self.accepts(SVZ, "Steuernummer", "919801131001"))

	def test_wid_nr_is_de_and_nine_digits(self):
		self.assertTrue(self.accepts(DF, "WIdNr", "DE123456789"))
		self.assertFalse(self.accepts(DF, "WIdNr", "DE123456789-00001"))

	def test_kz09_is_the_hersteller_id_with_or_without_the_data_of_a_berater(self):
		self.assertTrue(self.accepts(DF, "Kz09", "12345"))
		self.assertTrue(self.accepts(DF, "Kz09", "12345*Berater*Mandant*1*2*3"))
		self.assertFalse(self.accepts(DF, "Kz09", "1234"))
		self.assertFalse(self.accepts(DF, "Kz09", "12345*Berater"))
		self.assertFalse(self.accepts(DF, "Kz09", "12345" + ("*" + "x" * 20) * 5))

	def test_yes_fields_take_1(self):
		for element in ("Kz10", "Kz26", "Kz29"):
			with self.subTest(element=element):
				self.assertTrue(self.accepts(SVZ, element, "1"))
				self.assertFalse(self.accepts(SVZ, element, "2"))

	def test_kz38_takes_up_to_thirteen_digits_without_leading_zero(self):
		self.assertTrue(self.accepts(SVZ, "Kz38", "0"))
		self.assertTrue(self.accepts(SVZ, "Kz38", "4000"))
		self.assertTrue(self.accepts(SVZ, "Kz38", "9" * 13))
		for text in ("04000", "-1", "4000.00", "9" * 14, ""):
			with self.subTest(text=text):
				self.assertFalse(self.accepts(SVZ, "Kz38", text))

	def test_kz500_takes_the_keys_of_the_list(self):
		for code in ("1", "2", "3", "4"):
			with self.subTest(code=code):
				self.assertTrue(self.accepts(SVZ, "Kz500", code))
		self.assertFalse(self.accepts(SVZ, "Kz500", "5"))
		self.assertFalse(self.accepts(SVZ, "Kz500", "12"))
		self.assertFalse(self.accepts(SVZ, "Kz500", "\\Q1\\E"))

	def test_begruendung_takes_one_line_of_up_to_180_characters(self):
		self.assertTrue(self.accepts(DF, "Kz500_Begruendung", "x" * 180))
		self.assertFalse(self.accepts(DF, "Kz500_Begruendung", "x" * 181))
		self.assertFalse(self.accepts(DF, "Kz500_Begruendung", "eins\nzwei"))
		self.assertFalse(self.accepts(DF, "Kz500_Begruendung", ""))


class AnmeldungTest(TestCase):
	"""The Anmeldung der Sondervorauszahlung of a monthly filer (context Umsatzsteuersondervorauszahlung)."""

	def test_writes_the_year_and_kz38(self):
		self.assertEqual(anmeldung().texts(), {"Jahr": "2026", "Kz38": "4000"})

	def test_writes_the_yes_fields_in_the_order_of_the_schema(self):
		filing = anmeldung(corrected=True, no_sepa_mandate=True, offset_requested=True)
		self.assertEqual(
			list(filing.texts().items()),
			[("Jahr", "2026"), ("Kz10", "1"), ("Kz26", "1"), ("Kz29", "1"), ("Kz38", "4000")],
		)

	def test_writes_kz500_with_its_begruendung(self):
		filing = anmeldung(supplementary_code="2", begruendung="Abweichende Rechtsauffassung")
		self.assertEqual(
			filing.texts(),
			{
				"Jahr": "2026",
				"Kz38": "4000",
				"Kz500": "2",
				"Kz500_Begruendung": "Abweichende Rechtsauffassung",
			},
		)

	def test_every_text_is_one_the_field_takes(self):
		filing = anmeldung(
			corrected=True,
			no_sepa_mandate=True,
			offset_requested=True,
			supplementary_code="4",
			begruendung="x" * 180,
			sondervorauszahlung=Decimal("9" * 13),
		)
		layout = layout_for(2026)
		for element, text in filing.texts().items():
			with self.subTest(element=element):
				self.assertTrue(layout.field(SVZ, element).accepts(text))

	def test_kz38_of_zero_is_written(self):
		self.assertEqual(anmeldung(sondervorauszahlung=Decimal("0")).texts()["Kz38"], "0")

	def test_kz38_is_kept_in_whole_euros(self):
		for amount in (Decimal("4000.00"), Decimal("4E+3"), Decimal("4000")):
			with self.subTest(amount=amount):
				filing = anmeldung(sondervorauszahlung=amount)
				self.assertEqual(str(filing.sondervorauszahlung), "4000")
				self.assertEqual(filing.texts()["Kz38"], "4000")

	def test_needs_kz38(self):
		with self.assertRaises(FormError) as caught:
			anmeldung(sondervorauszahlung=None)
		self.assertEqual(caught.exception.template, SONDERVORAUSZAHLUNG_MISSING)
		self.assertEqual(caught.exception.rule.code, "110085143")

	def test_kz38_takes_no_cents(self):
		with self.assertRaises(FormError) as caught:
			anmeldung(sondervorauszahlung=Decimal("4000.50"))
		self.assertEqual(caught.exception.template, NOT_WHOLE_EUROS)
		self.assertEqual(str(caught.exception), "Kennzahl 38 takes whole euros, not 4000.50.")

	def test_kz38_takes_no_sign(self):
		with self.assertRaises(FormError) as caught:
			anmeldung(sondervorauszahlung=Decimal("-1"))
		self.assertEqual(caught.exception.template, NEGATIVE)
		self.assertEqual(str(caught.exception), "Kennzahl 38 takes no negative amount: -1.")

	def test_kz38_has_at_most_thirteen_digits(self):
		with self.assertRaises(FormError) as caught:
			anmeldung(sondervorauszahlung=Decimal("1" + "0" * 13))
		self.assertEqual(caught.exception.template, TOO_MANY_DIGITS)
		self.assertEqual(caught.exception.values, ("38", "10000000000000"))

	def test_kz38_is_an_amount(self):
		with self.assertRaises(TypeError):
			anmeldung(sondervorauszahlung=4000)
		with self.assertRaisesRegex(ValueError, "not an amount"):
			anmeldung(sondervorauszahlung=Decimal("NaN"))

	def test_kz29_needs_kz10(self):
		with self.assertRaises(FormError) as caught:
			anmeldung(offset_requested=True)
		self.assertEqual(caught.exception.template, OFFSET_WITHOUT_CORRECTION)
		self.assertEqual(caught.exception.rule.code, "11085150")
		self.assertEqual(anmeldung(offset_requested=True, corrected=True).texts()["Kz29"], "1")

	def test_hints_of_kz26_and_kz500(self):
		self.assertEqual(anmeldung().hints, ())
		self.assertEqual([rule.name for rule in anmeldung(no_sepa_mandate=True).hints], ["Kz26_Hinweis"])
		filing = anmeldung(no_sepa_mandate=True, supplementary_code="1", begruendung="Sachverhalt")
		self.assertEqual([rule.code for rule in filing.hints], ["11085155", "110085049"])
		self.assertTrue(all(rule.severity is Severity.HINT for rule in filing.hints))


class AntragTest(TestCase):
	"""The Antrag auf Dauerfristverlängerung of a quarterly filer (context Dauerfristverlaengerung)."""

	def test_writes_the_year_alone(self):
		self.assertEqual(antrag().texts(), {"Jahr": "2026"})

	def test_carries_no_sondervorauszahlung(self):
		for changes, kennzahl in (
			({"sondervorauszahlung": Decimal("0")}, "38"),
			({"corrected": True}, "10"),
			({"no_sepa_mandate": True}, "26"),
			({"offset_requested": True, "corrected": True}, "10"),
		):
			with self.subTest(kennzahl=kennzahl), self.assertRaises(FormError) as caught:
				antrag(**changes)
			self.assertEqual(caught.exception.template, NOT_IN_CONTEXT)
			self.assertEqual(caught.exception.values, ("Dauerfristverlaengerung", kennzahl))

	def test_kz29_alone_is_refused_too(self):
		with self.assertRaises(FormError) as caught:
			antrag(offset_requested=True)
		self.assertEqual(caught.exception.values, ("Dauerfristverlaengerung", "29"))

	def test_takes_kz500_with_its_begruendung(self):
		filing = antrag(supplementary_code="3", begruendung="Prüfung")
		self.assertEqual(filing.texts(), {"Jahr": "2026", "Kz500": "3", "Kz500_Begruendung": "Prüfung"})
		self.assertEqual([rule.name for rule in filing.hints], ["Kz500_Hinweis"])

	def test_has_no_hints_without_kz500(self):
		self.assertEqual(antrag().hints, ())


class Kz500Test(TestCase):
	def test_needs_its_begruendung(self):
		for filing in (antrag, anmeldung):
			with self.subTest(filing=filing.__name__), self.assertRaises(FormError) as caught:
				filing(supplementary_code="1")
			self.assertEqual(caught.exception.template, CODE_WITHOUT_BEGRUENDUNG)
			self.assertEqual(caught.exception.rule.code, "11085137")

	def test_the_begruendung_needs_kz500(self):
		with self.assertRaises(FormError) as caught:
			antrag(begruendung="Sachverhalt")
		self.assertEqual(caught.exception.template, BEGRUENDUNG_WITHOUT_CODE)
		self.assertEqual(caught.exception.rule.code, "11085137")

	def test_takes_the_keys_1_to_4(self):
		with self.assertRaises(FormError) as caught:
			antrag(supplementary_code="5", begruendung="Sachverhalt")
		self.assertEqual(caught.exception.template, UNKNOWN_CODE)
		self.assertEqual(str(caught.exception), "Kennzahl 500 takes 1, 2, 3 or 4, not 5.")

	def test_an_empty_key_is_no_key(self):
		self.assertIsNone(antrag(supplementary_code="").supplementary_code)
		self.assertEqual(antrag(supplementary_code="", begruendung=" \n ").texts(), {"Jahr": "2026"})

	def test_the_begruendung_is_one_line_without_blanks_at_either_end(self):
		filing = antrag(supplementary_code="1", begruendung="  Zwei\nZeilen\t und  Leerzeichen ")
		self.assertEqual(filing.begruendung, "Zwei Zeilen und Leerzeichen")

	def test_the_begruendung_has_at_most_180_characters(self):
		self.assertEqual(len(antrag(supplementary_code="1", begruendung="x" * 180).begruendung or ""), 180)
		with self.assertRaises(FormError) as caught:
			antrag(supplementary_code="1", begruendung="x" * 181)
		self.assertEqual(caught.exception.template, BEGRUENDUNG_TOO_LONG)
		self.assertEqual(caught.exception.values, (181, 180))

	def test_the_begruendung_is_text(self):
		with self.assertRaises(TypeError):
			antrag(supplementary_code="1", begruendung=12)
		with self.assertRaises(TypeError):
			antrag(supplementary_code=1, begruendung="Sachverhalt")


class Ust1HTest(TestCase):
	def test_takes_the_value_of_the_context(self):
		self.assertIs(anmeldung(context="Umsatzsteuersondervorauszahlung").context, SVZ)
		with self.assertRaises(ValueError):
			anmeldung(context="Umsatzsteuervoranmeldung")

	def test_needs_the_layout_of_its_year(self):
		with self.assertRaises(FormError) as caught:
			anmeldung(year=2025)
		self.assertEqual(caught.exception.template, NO_LAYOUT)

	def test_yes_fields_are_booleans(self):
		for name in ("corrected", "no_sepa_mandate", "offset_requested"):
			with self.subTest(name=name), self.assertRaisesRegex(TypeError, name):
				anmeldung(**{name: 1})

	def test_is_immutable(self):
		with self.assertRaises(AttributeError):
			anmeldung().year = 2027  # type: ignore[misc]


class MessagesTest(TestCase):
	def test_every_template_is_listed_for_translation(self):
		self.assertEqual(
			set(MESSAGES),
			{
				NO_LAYOUT,
				NOT_IN_CONTEXT,
				SONDERVORAUSZAHLUNG_MISSING,
				NOT_WHOLE_EUROS,
				NEGATIVE,
				TOO_MANY_DIGITS,
				OFFSET_WITHOUT_CORRECTION,
				UNKNOWN_CODE,
				CODE_WITHOUT_BEGRUENDUNG,
				BEGRUENDUNG_WITHOUT_CODE,
				BEGRUENDUNG_TOO_LONG,
			},
		)

	def test_an_error_keeps_template_and_values_apart(self):
		error = FormError(NOT_IN_CONTEXT, "Dauerfristverlaengerung", "38")
		self.assertEqual(error.template, NOT_IN_CONTEXT)
		self.assertEqual(error.values, ("Dauerfristverlaengerung", "38"))
		self.assertIsNone(error.rule)
		self.assertIsInstance(error, ValueError)


class JahresdokumentationTest(TestCase):
	"""The layout of 2026 against the ERiC documentation 44.3.6.0; skipped without it, see eric_schema.py."""

	def setUp(self):
		self.layout = layout_for(2026)

	def test_fields_follow_the_sheet_felder(self):
		rows = {
			(row["Kontext"], row["Name"]): row
			for row in jahresdokumentation.sheet(2026, "Anmeldungssteuern - Felder")
		}
		for context in Context:
			kontext = f"Steuerfall/{context.value}"
			with self.subTest(context=context):
				self.assertEqual(
					tuple(name for (row_kontext, name) in rows if row_kontext == kontext),
					self.layout.elements(context),
				)
			for field in self.layout.fields[context]:
				row = rows[(kontext, field.element)]
				with self.subTest(context=context, element=field.element):
					self.assertEqual(field.regex, row["Format als regulärer Ausdruck"])
					self.assertEqual(field.format.value, row["Formatkennzeichen"])
					self.assertEqual(field.min_length, _number(row["Min. Länge"]))
					self.assertEqual(field.max_length, _number(row["Max. Länge"]))
					self.assertEqual(field.line, _number(row["Vordruckzeile"]))

	def test_rules_follow_the_sheet_regeln(self):
		documented = {
			(row["Kontext"], row["Name"], row["Fehlercode"], row["Regelart"])
			for row in jahresdokumentation.sheet(2026, "Anmeldungssteuern - Regeln")
			if row["Kontext"] in {f"Steuerfall/{context.value}" for context in Context}
			or (
				row["Kontext"] == "Steuerfall"
				and any(context.value in row["Prüfbedingung"] for context in Context)
			)
		}
		ours = {
			(
				"Steuerfall" if rule.context is None else f"Steuerfall/{rule.context.value}",
				rule.name,
				rule.code,
				rule.severity.value,
			)
			for rule in self.layout.rules
		}
		self.assertEqual(ours, documented)

	def test_elements_follow_the_sequence_of_the_schema(self):
		schema = etree.parse(str(eric_schema.nutzdaten_xsd(2026)))
		for context in Context:
			(type_name,) = schema.xpath("//xs:element[@name=$name]/@type", name=context.value, namespaces=XS)
			elements = schema.xpath(
				"//xs:complexType[@name=$type]/xs:sequence/xs:element/@name", type=type_name, namespaces=XS
			)
			with self.subTest(context=context):
				self.assertEqual(tuple(elements), self.layout.elements(context))

	def test_the_examples_of_the_documentation_fit_the_fields(self):
		for context, example in ((DF, "UStVA_Df_2026.xml"), (SVZ, "UStVA_SoVZ_2026.xml")):
			path = eric_schema.nutzdaten_xsd(2026).parents[2] / "Beispiele" / example
			(element,) = etree.parse(str(path)).iter(f"{{*}}{context.value}")
			for child in element.iterchildren(etree.Element):
				name = etree.QName(child).localname
				with self.subTest(example=example, element=name):
					self.assertTrue(self.layout.field(context, name).accepts(child.text.strip()))


class Jahresdokumentation2027Test(TestCase):
	"""The layout of 2027 against the beta ERiC 45.1.5.0; skipped with a documentation that holds no UStVA 2027, such as
	44.3.6.0 of the CI, see eric_schema.ustva_year."""

	@classmethod
	def setUpClass(cls) -> None:
		super().setUpClass()
		cls.documentation = eric_schema.ustva_year(2027)
		cls.layout = layout_for(2027)

	def test_fields_follow_the_sheet_felder(self):
		rows = {
			(row["Kontext"], row["Name"]): row
			for row in jahresdokumentation.sheet(2027, "Anmeldungssteuern - Felder")
		}
		for context in Context:
			kontext = f"Steuerfall/{context.value}"
			with self.subTest(context=context):
				self.assertEqual(
					tuple(name for (row_kontext, name) in rows if row_kontext == kontext),
					self.layout.elements(context),
				)
			for field in self.layout.fields[context]:
				row = rows[(kontext, field.element)]
				with self.subTest(context=context, element=field.element):
					self.assertEqual(
						(field.regex, field.format.value, field.min_length, field.max_length, field.line),
						(
							row["Format als regulärer Ausdruck"],
							row["Formatkennzeichen"],
							_number(row["Min. Länge"]),
							_number(row["Max. Länge"]),
							_number(row["Vordruckzeile"]),
						),
					)

	def test_rules_follow_the_sheet_regeln(self):
		documented = {
			(row["Kontext"], row["Name"], row["Fehlercode"], row["Regelart"])
			for row in jahresdokumentation.sheet(2027, "Anmeldungssteuern - Regeln")
			if row["Kontext"] in {f"Steuerfall/{context.value}" for context in Context}
			or (
				row["Kontext"] == "Steuerfall"
				and any(context.value in row["Prüfbedingung"] for context in Context)
			)
		}
		ours = {
			(
				"Steuerfall" if rule.context is None else f"Steuerfall/{rule.context.value}",
				rule.name,
				rule.code,
				rule.severity.value,
			)
			for rule in self.layout.rules
		}
		self.assertEqual(ours, documented)

	def test_elements_follow_the_sequence_of_the_schema(self):
		schema = etree.parse(str(eric_schema.nutzdaten_xsd(2027)))
		for context in Context:
			(type_name,) = schema.xpath("//xs:element[@name=$name]/@type", name=context.value, namespaces=XS)
			elements = schema.xpath(
				"//xs:complexType[@name=$type]/xs:sequence/xs:element/@name", type=type_name, namespaces=XS
			)
			with self.subTest(context=context):
				self.assertEqual(tuple(elements), self.layout.elements(context))

	def test_the_examples_of_the_documentation_fit_the_fields(self):
		for context, example in ((DF, "UStVA_Df_2027.xml"), (SVZ, "UStVA_SoVZ_2027.xml")):
			path = eric_schema.nutzdaten_xsd(2027).parents[2] / "Beispiele" / example
			(element,) = etree.parse(str(path)).iter(f"{{*}}{context.value}")
			for child in element.iterchildren(etree.Element):
				name = etree.QName(child).localname
				with self.subTest(example=example, element=name):
					self.assertTrue(self.layout.field(context, name).accepts(child.text.strip()))


def _number(cell: str) -> int | None:
	return int(cell) if cell else None

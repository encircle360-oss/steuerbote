"""The catalogue of form USt 2 A 2026: fields, Kennzahlen, formats, the place of each Kennzahl of the Voranmeldung,
the rate lines, the sums and the rules of the Jahresdokumentation."""

from dataclasses import replace
from decimal import Decimal
from unittest import TestCase

from steuerbote.ustjahr.form import (
	CATALOGUES,
	SOLL,
	Catalogue,
	Field,
	Format,
	Rule,
	Scope,
	Severity,
	Source,
	catalogue_for,
)
from steuerbote.ustva.kennzahlen import BALANCE_KENNZAHL, SONDERVORAUSZAHLUNG_KENNZAHL, Effect
from steuerbote.ustva.kennzahlen import catalogue_for as ustva_catalogue_for
from steuerbote.ustva.years import UnknownYearError

CATALOGUE = CATALOGUES[2026]

# Kennzahl: (Feldkennung, line) as form USt 2 A 2026 prints them; the Feldkennung after the JD sheet "USt2A - Kennzahlen".
KENNZAHLEN_2026 = {
	"110": ("E3000601", 3),
	"125": ("E3001402", 16),
	"126": ("E3001801", 17),
	"136": ("E3001601", 18),
	"133": ("E3002203", 21),
	"129": ("E3001701", 22),
	"500": ("E3002201", 23),
	"177": ("E3003303", 24),
	"178": ("E3003405", 25),
	"179": ("E3003505", 26),
	"275": ("E3004401", 27),
	"195": ("E3003703", 28),
	"196": ("E3003803", 29),
	"157": ("E3002801", 30),
	"158": ("E3002901", 31),
	"159": ("E3003001", 32),
	"155": ("E3005001", 33),
	"156": ("E3005002", 33),
	"777": ("E3005201", 34),
	"346": ("E3005005", 35),
	"347": ("E3005006", 35),
	"361": ("E3005801", 36),
	"308": ("E3005401", 37),
	"309": ("E3005402", 37),
	"310": ("E3005403", 38),
	"317": ("E3102901", 39),
	"319": ("E3005901", 40),
	"741": ("E3103301", 42),
	"744": ("E3103401", 43),
	"749": ("E3103501", 44),
	"752": ("E3103801", 45),
	"237": ("E3104201", 50),
	"286": ("E3104401", 51),
	"287": ("E3104502", 52),
	"236": ("E3104701", 53),
	"240": ("E3104902", 54),
	"789": ("E3100801", 55),
	"791": ("E3100901", 56),
	"781": ("E3100902", 57),
	"793": ("E3101301", 58),
	"780": ("E3101305", 59),
	"798": ("E3101303", 60),
	"799": ("E3101304", 60),
	"794": ("E3101401", 61),
	"796": ("E3101402", 61),
	"852": ("E3102804", 63),
	"853": ("E3102805", 63),
	"742": ("E3101801", 65),
	"751": ("E3101701", 66),
	"746": ("E3102301", 67),
	"750": ("E3102305", 68),
	"747": ("E3102303", 69),
	"748": ("E3102304", 69),
	"846": ("E3102205", 71),
	"847": ("E3102206", 71),
	"873": ("E3102307", 72),
	"874": ("E3102308", 72),
	"877": ("E3102503", 73),
	"878": ("E3102504", 73),
	"209": ("E3105301", 76),
	"213": ("E3105101", 77),
	"214": ("E3105102", 78),
	"211": ("E3105602", 79),
	"721": ("E3105702", 80),
	"205": ("E3105801", 81),
	"204": ("E3105901", 82),
	"212": ("E3106001", 83),
	"650": ("E3106101", 84),
	"320": ("E3006201", 85),
	"761": ("E3006301", 86),
	"762": ("E3006401", 87),
	"466": ("E3006503", 88),
	"467": ("E3006502", 89),
	"334": ("E3006601", 90),
	"759": ("E3006701", 91),
	"760": ("E3006801", 92),
	"637": ("E3007001", 94),
	"370": ("E3007301", 95),
	"371": ("E3007601", 96),
	"372": ("E3008501", 97),
	"369": ("E3008601", 98),
	"357": ("E3008901", 108),
	"359": ("E3008902", 108),
	"318": ("E3010301", 119),
	"331": ("E3010401", 120),
	"391": ("E3010501", 121),
	"816": ("E3011101", 124),
	"820": ("E3011401", 126),
}

# Every amount Kennzahl of the Voranmeldung 2026 but Kz 39 and Kz 83, which go into the Vorauszahlungssoll, with the
# fields of the annual return that take its amounts: USt 1 E 2026 and USt 2 E 2026 (see the docstring of form.py).
CHILDREN_2026 = {
	"81": {"E3003303", "E3003405", "E3003505"},
	"86": {"E3004401", "E3003703", "E3003803"},
	"87": {"E3002801", "E3002901", "E3003001"},
	"35": {"E3005001"},
	"36": {"E3005002"},
	"77": {"E3005201"},
	"76": {"E3005005"},
	"80": {"E3005006"},
	"41": {"E3103301"},
	"44": {"E3103401"},
	"49": {"E3103501"},
	"43": {"E3103801", "E3103902", "E3104001", "E3104002", "E3104101"},
	"48": {"E3104401", "E3104502", "E3104701", "E3104902"},
	"91": {"E3100901"},
	"89": {"E3100902"},
	"93": {"E3101301"},
	"90": {"E3101305"},
	"95": {"E3101303"},
	"98": {"E3101304"},
	"94": {"E3101401"},
	"96": {"E3101402"},
	"46": {"E3102205"},
	"47": {"E3102206"},
	"73": {"E3102307"},
	"74": {"E3102308"},
	"84": {"E3102503"},
	"85": {"E3102504"},
	"42": {"E3101801"},
	"60": {"E3105301"},
	"21": {"E3105702"},
	"45": {"E3105801", "E3105102"},
	"66": {"E3006201", "E3006503", "E3006801"},
	"61": {"E3006301"},
	"62": {"E3006401"},
	"67": {"E3006502"},
	"63": {"E3006601"},
	"59": {"E3006701"},
	"64": {"E3008701", "E3008702", "E3008801", "E3008802", "E3008803", "E3008804"},
	"65": {"E3102901", "E3005901"},
	"69": {"E3010301", "E3010401", "E3102805", "E3101702", "E3102302", "E3102304"},
	"50": {"E3106101"},
	"37": {"E3007001"},
}
DEFAULT_CHILDREN_2026 = {
	"81": "E3003303",
	"86": "E3004401",
	"87": "E3002801",
	"43": "E3103902",
	"48": "E3104502",
	"45": "E3105801",
	"65": "E3005901",
	"66": "E3006201",
	"69": "E3010301",
}
# Amounts the ledger or a person feeds that no Kennzahl of the Voranmeldung holds.
ANNUAL_ONLY_2026 = {
	"E3005801",  # Kz 361, übrige Umsätze land- und forstwirtschaftlicher Betriebe ohne Steuer
	"E3005401",  # Kz 308, § 25 UStG
	"E3005402",  # Kz 309, its tax
	"E3005403",  # Kz 310, § 25a UStG
	"E3100801",  # Kz 789, Erwerbe des ersten Abnehmers (§ 25b Absatz 3 UStG)
	"E3102804",  # Kz 852, Lieferungen vor der Auslagerung
	"E3101701",  # Kz 751
	"E3102301",  # Kz 746
	"E3102305",  # Kz 750
	"E3102303",  # Kz 747
	"E3105201",  # line 75, Verzicht nach § 9 UStG
	"E3105101",  # Kz 213
	"E3105602",  # Kz 211, Geschäftsveräußerung im Ganzen
	"E3105901",  # Kz 204
	"E3106001",  # Kz 212
	"E3010501",  # Kz 391, Kleinunternehmer
	"E3010602",  # line 123, from Anlage UN
}
RATE_LINES_2026 = {
	"E3003304": ("19", "E3003303"),
	"E3003406": ("19", "E3003405"),
	"E3003506": ("19", "E3003505"),
	"E3004402": ("7", "E3004401"),
	"E3003704": ("7", "E3003703"),
	"E3003804": ("7", "E3003803"),
	"E3100903": ("19", "E3100902"),
	"E3101302": ("7", "E3101301"),
	"E3005404": ("19", "E3005403"),
}
# Bases and their tax, which ERiC takes only together (FelderNichtGemeinsamAngegeben in the JD).
PAIRS_2026 = {
	"E3003303": "E3003304",
	"E3003405": "E3003406",
	"E3003505": "E3003506",
	"E3004401": "E3004402",
	"E3003703": "E3003704",
	"E3003803": "E3003804",
	"E3005001": "E3005002",
	"E3005005": "E3005006",
	"E3005401": "E3005402",
	"E3005403": "E3005404",
	"E3100902": "E3100903",
	"E3101301": "E3101302",
	"E3101303": "E3101304",
	"E3101401": "E3101402",
	"E3102804": "E3102805",
	"E3101701": "E3101702",
	"E3102301": "E3102302",
	"E3102303": "E3102304",
	"E3102205": "E3102206",
	"E3102307": "E3102308",
	"E3102503": "E3102504",
}
PLUS, MINUS = 1, -1
# The sums and differences of the form, as the rules of the JD check them.
SUMS_2026 = {
	# line 41, rule 30314
	"E3006001": tuple(
		(element, PLUS)
		for element in (
			"E3003304",
			"E3003406",
			"E3003506",
			"E3004402",
			"E3003704",
			"E3003804",
			"E3005002",
			"E3005006",
			"E3005402",
			"E3005404",
			"E3102901",
			"E3005901",
		)
	),
	# line 50, Kz 237, rule 30345
	"E3104201": tuple((element, PLUS) for element in ("E3103902", "E3104001", "E3104002", "E3104101")),
	# line 62, rule 30342
	"E3101501": tuple((element, PLUS) for element in ("E3100903", "E3101302", "E3101304", "E3101402")),
	# line 64, rule 30354
	"E3102904": (("E3102805", PLUS),),
	# line 70, rule 30356
	"E3102401": tuple((element, PLUS) for element in ("E3101702", "E3102302", "E3102304")),
	# line 74, rule 30358
	"E3102601": tuple((element, PLUS) for element in ("E3102206", "E3102308", "E3102504")),
	# line 93, rule 30317
	"E3006901": tuple(
		(element, PLUS)
		for element in (
			"E3006201",
			"E3006301",
			"E3006401",
			"E3006503",
			"E3006502",
			"E3006601",
			"E3006701",
			"E3006801",
		)
	),
	# line 108, Kz 357 and Kz 359, rules 30321 and 30331
	"E3008901": tuple((element, PLUS) for element in ("E3008701", "E3008801", "E3008803")),
	"E3008902": tuple((element, PLUS) for element in ("E3008702", "E3008802", "E3008804")),
	# lines 109 to 113, brought forward from lines 41, 62, 64, 70 and 74 (rules 30232, 30270, 30311, 30280, 30283)
	"E3009201": (("E3006001", PLUS),),
	"E3009401": (("E3101501", PLUS),),
	"E3009602": (("E3102904", PLUS),),
	"E3009501": (("E3102401", PLUS),),
	"E3009502": (("E3102601", PLUS),),
	# line 114, rule 30630
	"E3009801": tuple(
		(element, PLUS) for element in ("E3009201", "E3009401", "E3009501", "E3009502", "E3009602")
	),
	# lines 115 and 116 from lines 93 and 108 (rules 30240 and 30250)
	"E3009901": (("E3006901", PLUS),),
	"E3010001": (("E3008901", PLUS),),
	# line 117, rule 30632
	"E3010201": (("E3009801", PLUS), ("E3009901", MINUS), ("E3010001", MINUS)),
	# line 118 from line 108 (rule 30260)
	"E3009701": (("E3008902", PLUS),),
	# line 122, rule 30634
	"E3010601": tuple(
		(element, PLUS) for element in ("E3010201", "E3009701", "E3010301", "E3010401", "E3010501")
	),
	# line 124, Kz 816, rule 30636
	"E3011101": (("E3010601", PLUS), ("E3010602", MINUS)),
	# line 126, Kz 820, rule 30638
	"E3011401": (("E3011101", PLUS), ("E3011301", MINUS)),
}


def ustva_amount_kennzahlen() -> set[str]:
	catalogue = ustva_catalogue_for(2026)
	return {
		number
		for number, kennzahl in catalogue.items()
		if kennzahl.holds_amount and number not in (BALANCE_KENNZAHL, SONDERVORAUSZAHLUNG_KENNZAHL)
	}


class FieldsTest(TestCase):
	def test_holds_the_176_leaves_of_ust2a_in_the_order_of_the_schema(self):
		elements = [field.element for field in CATALOGUE.fields]
		self.assertEqual(len(elements), 176)
		self.assertEqual(len(set(elements)), 176)
		self.assertEqual((elements[0], elements[-1]), ("E3000601", "E3011401"))
		self.assertEqual(elements.index("E3003304"), elements.index("E3003303") + 1)
		self.assertLess(elements.index("E3002602"), elements.index("E3003303"))

	def test_carries_the_88_kennzahlen_of_the_printed_form(self):
		self.assertEqual(len(KENNZAHLEN_2026), 88)
		self.assertEqual(set(CATALOGUE.kennzahlen), set(KENNZAHLEN_2026))
		for number, (element, line) in KENNZAHLEN_2026.items():
			field = CATALOGUE.kennzahl(number)
			with self.subTest(kennzahl=number):
				self.assertEqual((field.element, field.line, field.kennzahl), (element, line, number))
				self.assertIs(CATALOGUE.field(element), field)

	def test_lines_follow_the_printed_form_from_3_to_129(self):
		"""The schema keeps the order of the form, but for the Mitwirkung, which it puts after line 23."""
		lines = [field.line for field in CATALOGUE.fields if not field.context.startswith("Mitwirk/")]
		self.assertEqual((lines[0], lines[-1]), (3, 126))
		self.assertEqual(lines, sorted(lines))
		self.assertEqual(max(field.line for field in CATALOGUE.fields), 128)
		self.assertEqual(CATALOGUE.field("E3003304").line, 24)
		self.assertEqual(CATALOGUE.field("E3006001").line, 41)
		self.assertEqual(CATALOGUE.field("E3103902").line, 46)
		self.assertEqual(CATALOGUE.field("E3011301").line, 125)

	def test_the_mitwirkung_stands_in_lines_127_to_129_as_on_the_form(self):
		"""The JD gives the lines 123 and 23; the form prints the Mitwirkung after line 126, its details in the
		block of lines 128 and 129."""
		self.assertEqual(CATALOGUE.field("E3002602").line, 127)
		mitwirkung = [field for field in CATALOGUE.fields if field.context.startswith("Mitwirk/")]
		self.assertEqual(len(mitwirkung), 10)
		for field in mitwirkung:
			if field.element != "E3002602":
				with self.subTest(element=field.element):
					self.assertEqual(field.line, 128)

	def test_labels_are_those_of_the_jahresdokumentation(self):
		self.assertEqual(CATALOGUE.field("E3003303").label, "Lieferungen und sonstige Leistungen zu 19 %")
		self.assertEqual(CATALOGUE.field("E3100902").label, "zum Steuersatz von 19 %")
		self.assertEqual(
			CATALOGUE.field("E3011301").label, "Vorauszahlungssoll $VZ$ (einschließlich Sondervorauszahlung)"
		)
		for field in CATALOGUE.fields:
			with self.subTest(element=field.element):
				self.assertTrue(field.label)
				self.assertEqual(field.label, " ".join(field.label.split()))

	def test_contexts_are_the_paths_below_ust2a(self):
		self.assertEqual(CATALOGUE.field("E3000601").context, "Ber_Erkl")
		self.assertEqual(CATALOGUE.field("E3003405").context, "Umsaetze/Tabelle/Ums_allg/Unent_Wertabgaben")
		self.assertEqual(CATALOGUE.field("E3011401").context, "Berech_USt/Tabelle/Zahl_Erstatt")


class FormatTest(TestCase):
	"""The Formatkennzeichen of the JD, sheet "Allg. Information"."""

	def test_amounts_are_whole_euros_or_cents_with_or_without_sign(self):
		expected = {
			Format.EUROS: (True, True, True),
			Format.UNSIGNED_EUROS: (True, True, False),
			Format.CENTS: (True, False, True),
			Format.UNSIGNED_CENTS: (True, False, False),
		}
		for format_, (amount, whole_euros, signed) in expected.items():
			with self.subTest(format=format_):
				self.assertEqual(
					(format_.amount, format_.whole_euros, format_.signed), (amount, whole_euros, signed)
				)
		for format_ in (Format.YES, Format.CROSS, Format.LIST, Format.DATE, Format.DAYS, Format.TEXT):
			with self.subTest(format=format_):
				self.assertFalse(format_.amount)

	def test_takes_the_codes_of_the_jahresdokumentation(self):
		self.assertEqual(
			{format_.value for format_ in Format}, {"N", "U", "P", "%", "J", "X", "H", "D", "B", "C"}
		)
		self.assertIs(Format("%"), Format.UNSIGNED_CENTS)

	def test_fields_carry_their_format(self):
		expected = {
			"E3000601": Format.YES,
			"E3000901": Format.TEXT,
			"E3001601": Format.DATE,
			"E3001401": Format.DAYS,
			"E3002203": Format.LIST,
			"E3003303": Format.EUROS,
			"E3003304": Format.CENTS,
			"E3102901": Format.UNSIGNED_CENTS,
			"E3106101": Format.UNSIGNED_EUROS,
			"E3007801": Format.CROSS,
			"E3008701": Format.UNSIGNED_CENTS,
			"E3011401": Format.CENTS,
		}
		for element, format_ in expected.items():
			with self.subTest(element=element):
				self.assertIs(CATALOGUE.field(element).format, format_)

	def test_texts_carry_their_length(self):
		expected = {
			"E3000401": 11,
			"E3000901": 999,
			"E3001203": 4,
			"E3001207": 72,
			"E3002509": 55,
			"E3002506": 60,
		}
		for element, length in expected.items():
			with self.subTest(element=element):
				self.assertEqual(CATALOGUE.field(element).length, length)
		for field in CATALOGUE.fields:
			with self.subTest(element=field.element):
				self.assertEqual(field.length is not None, field.format is Format.TEXT)

	def test_four_fields_are_mandatory(self):
		mandatory = {field.element for field in CATALOGUE.fields if field.mandatory}
		self.assertEqual(mandatory, {"E3000901", "E3011101", "E3011301", "E3011401"})

	def test_the_grundstuecke_of_line_95_repeat_up_to_99_times(self):
		repeated = {field.element: field.repeat for field in CATALOGUE.fields if field.repeat != 1}
		self.assertEqual(
			repeated,
			dict.fromkeys(("E3007401", "E3007402", "E3007403", "E3007404", "E3007405", "E3007406"), 99),
		)


class UstvaKennzahlenTest(TestCase):
	"""Where the Kennzahlen of the Voranmeldung land in the annual return."""

	def test_every_amount_of_the_voranmeldung_has_a_place(self):
		self.assertEqual(set(CHILDREN_2026), ustva_amount_kennzahlen())
		for number, children in CHILDREN_2026.items():
			with self.subTest(kennzahl=number):
				self.assertEqual({field.element for field in CATALOGUE.children(number)}, children)

	def test_nothing_else_names_a_kennzahl_of_the_voranmeldung(self):
		named = {field.element for field in CATALOGUE.fields if field.ustva is not None}
		self.assertEqual(named, set().union(*CHILDREN_2026.values()))
		self.assertEqual(CATALOGUE.children("39"), ())
		self.assertEqual(CATALOGUE.children("83"), ())

	def test_ten_kennzahlen_split_into_several_lines(self):
		self.assertEqual(set(CATALOGUE.split), {"81", "86", "87", "43", "48", "64", "65", "66", "69", "45"})

	def test_a_split_kennzahl_has_a_default_line_but_kz_64(self):
		for number in CATALOGUE.split:
			with self.subTest(kennzahl=number):
				default = CATALOGUE.default_child(number)
				self.assertEqual(
					None if default is None else default.element, DEFAULT_CHILDREN_2026.get(number)
				)
		self.assertIsNone(CATALOGUE.default_child("64"))

	def test_the_other_kennzahlen_go_one_to_one(self):
		for number in set(CHILDREN_2026) - set(CATALOGUE.split):
			with self.subTest(kennzahl=number):
				(child,) = CATALOGUE.children(number)
				self.assertIs(CATALOGUE.default_child(number), child)
				self.assertFalse(child.default)

	def test_a_kennzahl_without_a_place_has_no_default(self):
		self.assertIsNone(CATALOGUE.default_child("83"))

	def test_the_columns_of_section_15a_carry_the_direction_of_the_correction(self):
		"""Kz 64 is positive for Vorsteuer deducted later, negative for Vorsteuer repaid (USt 1 E 2026, line 44)."""
		signs = {field.element: field.sign for field in CATALOGUE.children("64")}
		self.assertEqual(
			signs,
			{"E3008701": 1, "E3008702": -1, "E3008801": 1, "E3008802": -1, "E3008803": 1, "E3008804": -1},
		)
		self.assertEqual({field.sign for field in CATALOGUE.fields if field.ustva not in (None, "64")}, {1})

	def test_annual_only_amounts_name_no_kennzahl_of_the_voranmeldung(self):
		fed = {
			field.element
			for field in CATALOGUE.fields
			if field.source is Source.LEDGER and field.ustva is None
		}
		self.assertEqual(fed, ANNUAL_ONLY_2026)

	def test_kz_789_is_annual_only_and_kz_742_takes_kz_42(self):
		self.assertIsNone(CATALOGUE.kennzahl("789").ustva)
		self.assertEqual(CATALOGUE.kennzahl("742").ustva, "42")

	def test_a_tax_of_the_voranmeldung_enters_kz_816_as_it_enters_kz_83(self):
		ustva = ustva_catalogue_for(2026)
		effects = {Effect.INCREASES: 1, Effect.REDUCES: -1, Effect.NONE: 0}
		for number, children in CHILDREN_2026.items():
			kennzahl = ustva[number]
			for element in children:
				field = CATALOGUE.field(element)
				with self.subTest(kennzahl=number, element=element):
					if kennzahl.derives_tax:
						self.assertEqual(CATALOGUE.effect(element), 0)
						self.assertEqual(CATALOGUE.effect(field.tax), 1)
					else:
						self.assertEqual(CATALOGUE.effect(element) * field.sign, effects[kennzahl.effect])

	def test_a_base_with_a_tax_of_its_own_puts_it_where_the_tax_kennzahl_goes(self):
		ustva = ustva_catalogue_for(2026)
		for number, kennzahl in ustva.items():
			if kennzahl.tax_kennzahl is None:
				continue
			(base,) = CATALOGUE.children(number)
			with self.subTest(kennzahl=number):
				self.assertEqual(CATALOGUE.field(base.tax).ustva, kennzahl.tax_kennzahl)


class RateAndPairTest(TestCase):
	def test_the_rate_lines_compute_their_tax_from_the_base(self):
		rated = {
			field.element: (str(field.rate), field.base)
			for field in CATALOGUE.fields
			if field.rate is not None
		}
		self.assertEqual(rated, RATE_LINES_2026)
		for element in RATE_LINES_2026:
			self.assertIs(CATALOGUE.field(element).source, Source.RATE)

	def test_a_rate_line_takes_the_rate_of_the_voranmeldung(self):
		ustva = ustva_catalogue_for(2026)
		for element, (rate, base) in RATE_LINES_2026.items():
			parent = CATALOGUE.field(base).ustva
			if parent is not None:
				with self.subTest(element=element):
					self.assertEqual(ustva[parent].rate, Decimal(rate))
					self.assertTrue(ustva[parent].derives_tax)

	def test_bases_and_taxes_go_in_pairs(self):
		pairs = {field.element: field.tax for field in CATALOGUE.fields if field.tax is not None}
		self.assertEqual(pairs, PAIRS_2026)
		for base, tax in PAIRS_2026.items():
			with self.subTest(base=base):
				self.assertEqual(CATALOGUE.field(tax).base, base)
				self.assertTrue(CATALOGUE.field(base).format.whole_euros)
				self.assertFalse(CATALOGUE.field(tax).format.whole_euros)
				self.assertEqual(CATALOGUE.field(base).line, CATALOGUE.field(tax).line)


class ParagraphTest(TestCase):
	"""Lines 46, 52 and 54 name the paragraph of their sales in a text field of the same line."""

	def test_three_lines_name_their_paragraph(self):
		named = {field.element: field.paragraph for field in CATALOGUE.fields if field.paragraph is not None}
		self.assertEqual(named, {"E3103902": "E3103901", "E3104502": "E3104501", "E3104902": "E3104901"})
		for amount, text in named.items():
			with self.subTest(amount=amount):
				self.assertIs(CATALOGUE.field(text).format, Format.TEXT)
				self.assertEqual(CATALOGUE.field(text).line, CATALOGUE.field(amount).line)
				self.assertIs(CATALOGUE.field(text).source, Source.DETAIL)

	def test_refuses_a_paragraph_that_is_no_text_of_the_same_line(self):
		for text in ("E3103801", "E3104501", "E9999999"):
			with (
				self.subTest(text=text),
				self.assertRaisesRegex(ValueError, f"E3103902: {text} is no text of line 46"),
			):
				Catalogue(
					2026,
					tuple(
						replace(field, paragraph=text) if field.element == "E3103902" else field
						for field in CATALOGUE.fields
					),
					CATALOGUE.rules,
				)


class SumsTest(TestCase):
	def test_the_sums_and_differences_of_the_form(self):
		sums = {field.element: field.parts for field in CATALOGUE.fields if field.parts}
		self.assertEqual(sums, SUMS_2026)
		for element in SUMS_2026:
			self.assertIs(CATALOGUE.field(element).source, Source.SUM)

	def test_the_vorauszahlungssoll_comes_from_outside_the_form(self):
		self.assertEqual(SOLL, "E3011301")
		self.assertIs(CATALOGUE.field(SOLL).source, Source.SOLL)

	def test_effect_on_kz_816(self):
		expected = {
			"E3003304": 1,
			"E3005901": 1,
			"E3100903": 1,
			"E3102805": 1,
			"E3101702": 1,
			"E3102206": 1,
			"E3006201": -1,
			"E3006801": -1,
			"E3008701": -1,
			"E3008702": 1,
			"E3010301": 1,
			"E3010401": 1,
			"E3010501": 1,
			"E3010602": -1,
			"E3003303": 0,
			"E3106101": 0,
			"E3007001": 0,
			"E3011301": 0,
			"E3011401": 0,
			"E3011101": 1,
		}
		for element, effect in expected.items():
			with self.subTest(element=element):
				self.assertEqual(CATALOGUE.effect(element), effect)


class SourceAndScopeTest(TestCase):
	def test_details_are_what_the_company_states(self):
		for element in ("E3000601", "E3000901", "E3002203", "E3103901", "E3007301", "E3007405", "E3007801"):
			with self.subTest(element=element):
				self.assertIs(CATALOGUE.field(element).source, Source.DETAIL)

	def test_marks_what_steuerbote_does_not_file(self):
		scopes = {field.element: field.scope for field in CATALOGUE.fields if field.scope is not Scope.IN}
		self.assertEqual(
			scopes,
			{
				"E3001208": Scope.FOREIGN,
				"E3001209": Scope.FOREIGN,
				"E3001402": Scope.FOREIGN,
				"E3001801": Scope.FOREIGN,
				"E3010602": Scope.FOREIGN,
				"E3005401": Scope.TRAVEL_AND_MARGIN,
				"E3005402": Scope.TRAVEL_AND_MARGIN,
				"E3005403": Scope.TRAVEL_AND_MARGIN,
				"E3005404": Scope.TRAVEL_AND_MARGIN,
				"E3001601": Scope.KLEINUNTERNEHMER,
				"E3104701": Scope.KLEINUNTERNEHMER,
				"E3007804": Scope.KLEINUNTERNEHMER,
				"E3010501": Scope.KLEINUNTERNEHMER,
			},
		)

	def test_the_ledger_feeds_the_amounts_steuerbote_files_and_the_kleinunternehmer_lines(self):
		self.assertTrue(CATALOGUE.field("E3003303").fed)
		self.assertTrue(CATALOGUE.field("E3104701").fed)
		self.assertTrue(CATALOGUE.field("E3100801").fed)
		for element in ("E3003304", "E3006001", SOLL, "E3005401", "E3010602", "E3000901", "E3007405"):
			with self.subTest(element=element):
				self.assertFalse(CATALOGUE.field(element).fed)


class RulesTest(TestCase):
	"""The 175 rules of the JD sheet "USt2A - Regeln": 142 errors and 33 hints."""

	def test_lists_every_rule_once(self):
		self.assertEqual(len(CATALOGUE.rules), 175)
		self.assertEqual(len({rule.code for rule in CATALOGUE.rules}), 175)
		self.assertEqual(len({rule.name for rule in CATALOGUE.rules}), 175)
		severities = [rule.severity for rule in CATALOGUE.rules]
		self.assertEqual((severities.count(Severity.ERROR), severities.count(Severity.HINT)), (142, 33))

	def test_names_each_rule_by_code_name_context_and_severity(self):
		self.assertEqual(
			CATALOGUE.rule("30639"),
			Rule("30639", "USt_30639", "Umsaetze/Tabelle/Ums_allg", Severity.ERROR),
		)
		self.assertEqual(
			CATALOGUE.rule("30013"),
			Rule("30013", "USt_2026_30013", "Ig_Erw/Tabelle/Erwerbe_25b", Severity.ERROR),
		)
		self.assertEqual(CATALOGUE.rule("30002"), Rule("30002", "USt_2024_30002", "Ber_Erkl", Severity.HINT))
		self.assertEqual(CATALOGUE.rule("30620").context, "Berech_USt/Tabelle/Zahl_Erstatt")

	def test_an_unknown_rule_is_a_key_error(self):
		with self.assertRaises(KeyError):
			CATALOGUE.rule("99999")


class CatalogueTableTest(TestCase):
	def test_holds_each_catalogue_under_its_year(self):
		self.assertEqual({year: catalogue.year for year, catalogue in CATALOGUES.items()}, {2026: 2026})
		self.assertIs(catalogue_for(2026), CATALOGUE)

	def test_an_unknown_year_has_no_catalogue(self):
		with self.assertRaisesRegex(
			UnknownYearError, "no catalogue of form USt 2 A for 2027; known years: 2026"
		):
			catalogue_for(2027)

	def test_unknown_fields_and_kennzahlen_are_key_errors(self):
		with self.assertRaises(KeyError):
			CATALOGUE.field("E9999999")
		with self.assertRaises(KeyError):
			CATALOGUE.kennzahl("999")


class CatalogueValidationTest(TestCase):
	"""A broken table is refused when it is built."""

	def build(self, fields: tuple[Field, ...]) -> Catalogue:
		return Catalogue(2026, fields, CATALOGUE.rules)

	def replaced(self, element: str, **changes: object) -> tuple[Field, ...]:
		return tuple(
			replace(field, **changes) if field.element == element else field for field in CATALOGUE.fields
		)

	def test_the_table_of_2026_builds(self):
		self.assertEqual(self.build(CATALOGUE.fields).fields, CATALOGUE.fields)

	def test_refuses_a_field_listed_twice(self):
		with self.assertRaisesRegex(ValueError, "E3003303 is listed twice"):
			self.build((*CATALOGUE.fields, CATALOGUE.field("E3003303")))

	def test_refuses_a_kennzahl_listed_twice(self):
		with self.assertRaisesRegex(ValueError, "Kennzahl 177 is listed twice"):
			self.build(self.replaced("E3003405", kennzahl="177"))

	def test_refuses_a_part_that_is_no_amount_of_the_form(self):
		with self.assertRaisesRegex(ValueError, "E3006001: E3000901 is no amount of the form"):
			self.build(self.replaced("E3006001", parts=(("E3000901", 1),)))
		with self.assertRaisesRegex(ValueError, "E3006001: E9999999 is no amount of the form"):
			self.build(self.replaced("E3006001", parts=(("E9999999", 1),)))

	def test_refuses_a_base_and_tax_that_do_not_name_each_other(self):
		with self.assertRaisesRegex(ValueError, "E3003303 and E3003304 do not name each other"):
			self.build(self.replaced("E3003304", base="E3003405"))
		with self.assertRaisesRegex(ValueError, "E3005201 and E3005801 do not name each other"):
			self.build(self.replaced("E3005801", base="E3005201"))

	def test_refuses_two_default_lines_of_one_kennzahl(self):
		with self.assertRaisesRegex(ValueError, "Kennzahl 81 has two default lines: E3003303 and E3003405"):
			self.build(self.replaced("E3003405", default=True))

	def test_refuses_a_default_line_of_a_kennzahl_that_does_not_split(self):
		with self.assertRaisesRegex(ValueError, "E3103301 is the only line of Kennzahl 41"):
			self.build(self.replaced("E3103301", default=True))

	def test_refuses_a_line_of_a_kennzahl_that_holds_no_amount_of_the_voranmeldung(self):
		for number in ("99", "10", "83", "39"):
			with (
				self.subTest(kennzahl=number),
				self.assertRaisesRegex(
					ValueError,
					f"E3105301: Kennzahl {number} is no amount of the Voranmeldung 2026 that a line takes",
				),
			):
				self.build(self.replaced("E3105301", ustva=number))

	def test_refuses_a_rule_listed_twice(self):
		with self.assertRaisesRegex(ValueError, "rule 30639 is listed twice"):
			Catalogue(2026, CATALOGUE.fields, (*CATALOGUE.rules, CATALOGUE.rule("30639")))

	def test_refuses_to_leave_an_amount_of_the_voranmeldung_without_a_line(self):
		with self.assertRaisesRegex(ValueError, "Kennzahl 21 of the Voranmeldung 2026 has no line"):
			self.build(self.replaced("E3105702", ustva=None))


class FieldTest(TestCase):
	def test_a_field_is_named_by_its_feldkennung(self):
		with self.assertRaisesRegex(ValueError, "'3003303' is no Feldkennung"):
			Field("3003303", "Umsaetze", 24, Format.EUROS, "Test")

	def test_a_sign_is_plus_or_minus_one(self):
		with self.assertRaisesRegex(ValueError, "E3003303: sign must be 1 or -1, not 2"):
			Field("E3003303", "Umsaetze", 24, Format.EUROS, "Test", sign=2)

	def test_only_a_tax_in_cents_takes_a_rate_and_it_needs_its_base(self):
		with self.assertRaisesRegex(ValueError, "E3003303: only a tax in cents takes a rate"):
			Field("E3003303", "Umsaetze", 24, Format.EUROS, "Test", rate=Decimal("19"), base="E3003302")
		with self.assertRaisesRegex(ValueError, "E3003304: a rate needs its base"):
			Field("E3003304", "Umsaetze", 24, Format.CENTS, "Test", rate=Decimal("19"))

	def test_only_amounts_add_up(self):
		with self.assertRaisesRegex(ValueError, "E3000901: only an amount is a sum"):
			Field("E3000901", "Allg", 5, Format.TEXT, "Test", length=999, parts=(("E3003304", 1),))

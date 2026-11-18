from unittest import TestCase

from steuerbote.elster.charset import ALLOWED, CharsetError, describe, transliterate

# The character set Standard_E_V2 as the specification of the XML lists it: printable ASCII,
# ¡¢£¥§ª«¬®¯°±²³µ¹º», ¿ to ÿ, and the characters ISO-8859-15 puts in place of eight of ISO-8859-1.
SPECIFIED = (
	{chr(code) for code in range(0x20, 0x7F)}
	| set("¡¢£¥§ª«¬®¯°±²³µ¹º»")
	| {chr(code) for code in range(0xBF, 0x100)}
	| set("ŒœŠšŸŽž€")
)

LOW_QUOTE = "\N{DOUBLE LOW-9 QUOTATION MARK}"
LEFT_QUOTE = "\N{LEFT DOUBLE QUOTATION MARK}"
RIGHT_QUOTE = "\N{RIGHT DOUBLE QUOTATION MARK}"
LOW_SINGLE_QUOTE = "\N{SINGLE LOW-9 QUOTATION MARK}"
LEFT_SINGLE_QUOTE = "\N{LEFT SINGLE QUOTATION MARK}"
APOSTROPHE = "\N{RIGHT SINGLE QUOTATION MARK}"
NO_BREAK_SPACE = "\N{NO-BREAK SPACE}"


class AllowedTest(TestCase):
	def test_is_the_specified_set(self):
		self.assertEqual(ALLOWED, SPECIFIED)

	def test_is_printable_iso_8859_15_without_five_characters(self):
		latin_9 = {bytes([code]).decode("iso-8859-15") for code in (*range(0x20, 0x7F), *range(0xA0, 0x100))}
		self.assertEqual(
			latin_9 - ALLOWED,
			{NO_BREAK_SPACE, "\N{COPYRIGHT SIGN}", "\N{SOFT HYPHEN}", "\N{PILCROW SIGN}", "\N{MIDDLE DOT}"},
		)
		self.assertLessEqual(ALLOWED, latin_9)

	def test_has_no_line_breaks(self):
		self.assertTrue(ALLOWED.isdisjoint("\n\r\t"))


class TransliterateTest(TestCase):
	def test_keeps_what_elster_takes(self):
		text = "Müller & Söhne GmbH, Straße 1a, 80331 München, Œuvre «Žižek» 100 €"
		self.assertEqual(transliterate(text), text)

	def test_replaces_typographic_quotation_marks(self):
		self.assertEqual(
			transliterate(
				f"{LOW_QUOTE}Beispiel{LEFT_QUOTE} und {LEFT_QUOTE}example{RIGHT_QUOTE} "
				f"and {LOW_SINGLE_QUOTE}so{LEFT_SINGLE_QUOTE}"
			),
			'"Beispiel" und "example" and \'so\'',
		)

	def test_replaces_apostrophes_and_single_guillemets(self):
		self.assertEqual(
			transliterate(
				f"Müller{APOSTROPHE}s \N{SINGLE LEFT-POINTING ANGLE QUOTATION MARK}Laden"
				"\N{SINGLE RIGHT-POINTING ANGLE QUOTATION MARK}"
			),
			"Müller's 'Laden'",
		)

	def test_replaces_dashes_and_the_minus_sign(self):
		self.assertEqual(
			transliterate("1\N{EN DASH}3 \N{EM DASH} Nord\N{HYPHEN}Süd \N{MINUS SIGN} 5"),
			"1-3 - Nord-Süd - 5",
		)

	def test_replaces_the_ellipsis(self):
		self.assertEqual(transliterate("und so weiter\N{HORIZONTAL ELLIPSIS}"), "und so weiter...")

	def test_replaces_special_spaces_and_line_breaks_by_a_blank(self):
		self.assertEqual(
			transliterate(f"a{NO_BREAK_SPACE}b\N{NARROW NO-BREAK SPACE}c\td\ne\r\nf\N{LINE SEPARATOR}g"),
			"a b c d e  f g",
		)

	def test_drops_invisible_characters(self):
		self.assertEqual(
			transliterate("Steuer\N{SOFT HYPHEN}bote\N{ZERO WIDTH SPACE}\N{ZERO WIDTH NO-BREAK SPACE}"),
			"Steuerbote",
		)

	def test_composes_letters_with_their_combining_marks(self):
		self.assertEqual(transliterate("Mu\N{COMBINING DIAERESIS}nchen"), "München")

	def test_refuses_what_has_no_replacement(self):
		with self.assertRaises(CharsetError) as raised:
			transliterate("Łódź \N{COPYRIGHT SIGN} 2026 ł")
		self.assertEqual(raised.exception.characters, ("Ł", "ź", "\N{COPYRIGHT SIGN}", "ł"))

	def test_names_each_refused_character_once_in_the_order_it_occurs(self):
		with self.assertRaises(CharsetError) as raised:
			transliterate("ł, ł and \N{CJK UNIFIED IDEOGRAPH-4E2D}")
		self.assertEqual(raised.exception.characters, ("ł", "\N{CJK UNIFIED IDEOGRAPH-4E2D}"))
		self.assertEqual(
			str(raised.exception),
			"characters outside the ELSTER character set: 'ł' (U+0142), "
			"'\N{CJK UNIFIED IDEOGRAPH-4E2D}' (U+4E2D)",
		)

	def test_describes_a_character_by_its_code_point(self):
		self.assertEqual(describe("\x07"), "'\\x07' (U+0007)")
		self.assertEqual(describe("\N{GRINNING FACE}"), "'\N{GRINNING FACE}' (U+1F600)")

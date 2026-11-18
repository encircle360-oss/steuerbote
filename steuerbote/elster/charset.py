"""The characters ELSTER takes in a text, and plain replacements for common others.

Every text of the Umsatzsteuer-Voranmeldung is restricted to the character set Standard_E_V2 (sheet
"Allg. Information" of Jahresdokumentation_UStVA_2026.ods, ERiC documentation 44.3.6.0): the characters
the pattern of StringZUBaseSType in UStVA-2026.xsd allows and the sheet "Zeichensatz" lists. These are
the printable characters of ISO-8859-15 except the no-break space, the copyright sign, the soft hyphen,
the pilcrow and the middle dot. The set also holds the line breaks, but every text element of the form
refuses them (StringBaseSType). A character outside the set fails the schema even as a character
reference such as &#8222;.

Texts from ERPNext often carry typographic characters, so ``transliterate`` replaces the common ones by
their plain equivalents: quotation marks, apostrophes, dashes, the minus sign and the ellipsis, special
spaces and line breaks by a blank, and invisible characters such as the soft hyphen are dropped. Anything
else outside the set, such as a Polish ł, is refused: how to spell a name without it is for the user to
decide.
"""

import unicodedata
from types import MappingProxyType

EXCLUDED = frozenset("\N{NO-BREAK SPACE}\N{COPYRIGHT SIGN}\N{SOFT HYPHEN}\N{PILCROW SIGN}\N{MIDDLE DOT}")
ALLOWED: frozenset[str] = (
	frozenset(bytes([*range(0x20, 0x7F), *range(0xA0, 0x100)]).decode("iso-8859-15")) - EXCLUDED
)

_QUOTATION_MARKS = dict.fromkeys(
	"\N{LEFT DOUBLE QUOTATION MARK}\N{RIGHT DOUBLE QUOTATION MARK}\N{DOUBLE LOW-9 QUOTATION MARK}"
	"\N{DOUBLE HIGH-REVERSED-9 QUOTATION MARK}\N{DOUBLE PRIME}",
	'"',
)
_APOSTROPHES = dict.fromkeys(
	"\N{LEFT SINGLE QUOTATION MARK}\N{RIGHT SINGLE QUOTATION MARK}\N{SINGLE LOW-9 QUOTATION MARK}"
	"\N{SINGLE HIGH-REVERSED-9 QUOTATION MARK}\N{PRIME}\N{SINGLE LEFT-POINTING ANGLE QUOTATION MARK}"
	"\N{SINGLE RIGHT-POINTING ANGLE QUOTATION MARK}",
	"'",
)
_DASHES = dict.fromkeys(
	"\N{HYPHEN}\N{NON-BREAKING HYPHEN}\N{FIGURE DASH}\N{EN DASH}\N{EM DASH}\N{HORIZONTAL BAR}\N{MINUS SIGN}",
	"-",
)
_SPACES = dict.fromkeys(
	"\t\n\x0b\x0c\r\x85\N{NO-BREAK SPACE}\N{EN QUAD}\N{EM QUAD}\N{EN SPACE}\N{EM SPACE}"
	"\N{THREE-PER-EM SPACE}\N{FOUR-PER-EM SPACE}\N{SIX-PER-EM SPACE}\N{FIGURE SPACE}"
	"\N{PUNCTUATION SPACE}\N{THIN SPACE}\N{HAIR SPACE}\N{LINE SEPARATOR}\N{PARAGRAPH SEPARATOR}"
	"\N{NARROW NO-BREAK SPACE}\N{MEDIUM MATHEMATICAL SPACE}\N{IDEOGRAPHIC SPACE}",
	" ",
)
_INVISIBLE = dict.fromkeys(
	"\N{SOFT HYPHEN}\N{ZERO WIDTH SPACE}\N{ZERO WIDTH NON-JOINER}\N{ZERO WIDTH JOINER}"
	"\N{WORD JOINER}\N{ZERO WIDTH NO-BREAK SPACE}",
	"",
)
REPLACEMENTS: MappingProxyType[str, str] = MappingProxyType(
	{
		**_QUOTATION_MARKS,
		**_APOSTROPHES,
		**_DASHES,
		"\N{HORIZONTAL ELLIPSIS}": "...",
		**_SPACES,
		**_INVISIBLE,
	}
)


class CharsetError(ValueError):
	"""Characters outside the ELSTER character set without a replacement, each once, in order of occurrence."""

	def __init__(self, characters: tuple[str, ...]) -> None:
		super().__init__(
			"characters outside the ELSTER character set: "
			+ ", ".join(describe(character) for character in characters)
		)
		self.characters = characters


def transliterate(text: str) -> str:
	"""The text in the ELSTER character set, with the common typographic characters replaced.

	Letters and their combining marks are composed first (NFC), so that a decomposed ü stays an ü.
	"""
	composed = unicodedata.normalize("NFC", text)
	replaced = "".join(REPLACEMENTS.get(character, character) for character in composed)
	refused = tuple(dict.fromkeys(character for character in replaced if character not in ALLOWED))
	if refused:
		raise CharsetError(refused)
	return replaced


def describe(character: str) -> str:
	"""A character as a message shows it, with its code point, since some are invisible."""
	return f"{character!r} (U+{ord(character):04X})"

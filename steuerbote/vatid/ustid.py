"""The USt-IdNr. of a business in another member state, as steuerbote checks it before a confirmation.

A plausible USt-IdNr. has 7 to 14 characters: the country code of two capital letters, then letters,
digits or the characters + and *. This is the pattern and these are the lengths that ERiC enforces for the
USt-IdNr. of a line of the Zusammenfassende Meldung (ERiC-Dokumentation 44.3.6.0,
Jahresdokumentation_ZMDO_2.ods, sheet "ZMDO - Felder", field knre_UstIdNr_Erwerber), and the
confirmation takes the same rule so that the number it confirms is the number the ZM reports. normalize
keeps only those characters, so blanks, dots and dashes as people write a number do not count.

The country codes are those of the BZSt's list of member states for the confirmation
(https://api.evatr.vies.bzst.de/v1/info/eu_mitgliedstaaten, retrieved 20 November 2026) without DE:
Greece is EL, and Northern Ireland is XI, whose numbers the Bestätigungsverfahren takes since 1 January
2021 (BZSt, "Fragen und Antworten" zur USt-IdNr.). The BZSt confirms „die Gültigkeit einer
Umsatzsteuer-Identifikationsnummer sowie den Namen und die Anschrift der Person, der die
Umsatzsteuer-Identifikationsnummer von einem anderen Mitgliedstaat erteilt wurde“ (§ 18e Nr. 1 UStG), so
a German number is refused, and „Nach dem 31.12.2020 können USt-IdNrn. mit dem Länderkennzeichen "GB"
nicht mehr im Bestätigungsverfahren nach § 18e UStG geprüft werden.“ (same FAQ).

How each member state builds its numbers comes from the BZSt's Merkblatt "Aufbau der
Umsatzsteuer-Identifikationsnummer (USt-IdNr.) in den EU-Mitgliedstaaten"
(https://www.bzst.de/SharedDocs/Downloads/DE/Merkblaetter/ust_idnr_aufbau.pdf?__blob=publicationFile&v=8,
retrieved 20 November 2026), published on www.bzst.de, where UStAE 18e.2 sends readers for the structure.
Where the Merkblatt names no letter for a position, the position is a digit.

A plausible number without that structure only gets a hint: ERiC reports it as a Hinweis, not as an error
(rule 17004518, „Unschlüssige Umsatzsteuer-Identifikationsnummer“), and the BZSt checks the structure
itself and answers with evatr-0005 or evatr-0012, an answer that is kept as proof like any other. For
Romania the Merkblatt gives at most ten digits that do not begin with 0, while ERiC asks the ZM to fill
a number of two to four digits up to five with leading zeros; such a number is plausible here and gets
the hint of the Merkblatt.
"""

import re
from dataclasses import dataclass
from string import ascii_letters, digits
from types import MappingProxyType

CHARACTERS = frozenset(ascii_letters + digits + "+*")
MIN_LENGTH = 7
MAX_LENGTH = 14
COUNTRY_CODE = re.compile(r"[A-Z]{2}")
GERMAN = re.compile(r"DE[0-9]{9}")
"""DE and nine digits, as the Merkblatt describes the German USt-IdNr."""


@dataclass(frozen=True, slots=True)
class MemberState:
	"""A member state as the confirmation knows it: country code, name and how it builds its numbers."""

	code: str
	name: str
	"""The German name, as the BZSt's list of member states gives it."""
	structure: str
	"""The positions after the country code, in the words of the Merkblatt."""
	pattern: str
	"""The same as a regular expression over the positions after the country code."""

	def fits(self, number: str) -> bool:
		return re.fullmatch(self.pattern, number[2:]) is not None


_STATES = (
	MemberState("AT", "Österreich", "neun, die erste Stelle muss der Buchstabe „U“ sein", r"U[0-9]{8}"),
	MemberState(
		"BE",
		"Belgien",
		"zehn, nur Ziffern; alte neunstellige USt-IdNrn. werden durch Voranstellen der Ziffer 0 ergänzt",
		r"[0-9]{10}",
	),
	MemberState("BG", "Bulgarien", "neun oder zehn, nur Ziffern", r"[0-9]{9,10}"),
	MemberState("CY", "Zypern", "neun, die letzte Stelle muss ein Buchstabe sein", r"[0-9]{8}[A-Z]"),
	MemberState("CZ", "Tschechien", "acht, neun oder zehn, nur Ziffern", r"[0-9]{8,10}"),
	MemberState("DK", "Dänemark", "acht, nur Ziffern", r"[0-9]{8}"),
	MemberState("EE", "Estland", "neun, nur Ziffern", r"[0-9]{9}"),
	MemberState("EL", "Griechenland", "neun, nur Ziffern", r"[0-9]{9}"),
	MemberState(
		"ES",
		"Spanien",
		"neun, die erste und die letzte Stelle bzw. die erste oder die letzte Stelle kann ein Buchstabe sein",
		r"[0-9A-Z][0-9]{7}[0-9A-Z]",
	),
	MemberState("FI", "Finnland", "acht, nur Ziffern", r"[0-9]{8}"),
	MemberState(
		"FR",
		"Frankreich",
		"elf, nur Ziffern bzw. die erste und/oder die zweite Stelle kann ein Buchstabe sein",
		r"[0-9A-Z]{2}[0-9]{9}",
	),
	MemberState("HR", "Kroatien", "elf, nur Ziffern", r"[0-9]{11}"),
	MemberState("HU", "Ungarn", "acht, nur Ziffern", r"[0-9]{8}"),
	MemberState(
		"IE",
		"Irland",
		"acht, die zweite Stelle kann und die letzte Stelle muss ein Buchstabe sein, oder neun Stellen "
		"(ab 01.01.2013): 1. bis 7. Stelle Ziffern, 8. Stelle Buchstaben von A bis W, 9. Stelle "
		"Buchstaben von A bis I",
		r"[0-9][0-9A-Z][0-9]{5}[A-Z]|[0-9]{7}[A-W][A-I]",
	),
	MemberState("IT", "Italien", "elf, nur Ziffern", r"[0-9]{11}"),
	MemberState("LT", "Litauen", "neun oder zwölf, nur Ziffern", r"[0-9]{9}|[0-9]{12}"),
	MemberState("LU", "Luxemburg", "acht, nur Ziffern", r"[0-9]{8}"),
	MemberState("LV", "Lettland", "elf, nur Ziffern", r"[0-9]{11}"),
	MemberState("MT", "Malta", "acht, nur Ziffern", r"[0-9]{8}"),
	MemberState(
		"NL",
		"Niederlande",
		"zwölf, Ziffern, Buchstaben und die Zeichen „+“ und „*“ in zufälliger Reihenfolge",
		r"[0-9A-Z+*]{12}",
	),
	MemberState("PL", "Polen", "zehn, nur Ziffern", r"[0-9]{10}"),
	MemberState("PT", "Portugal", "neun, nur Ziffern", r"[0-9]{9}"),
	MemberState(
		"RO",
		"Rumänien",
		"maximal zehn, nur Ziffern, Ziffernfolge nicht mit 0 beginnend",
		r"[1-9][0-9]{0,9}",
	),
	MemberState(
		"SE",
		"Schweden",
		"zwölf, nur Ziffern, die beiden letzten Stellen bestehen immer aus der Ziffernkombination „01“",
		r"[0-9]{10}01",
	),
	MemberState("SI", "Slowenien", "acht, nur Ziffern", r"[0-9]{8}"),
	MemberState("SK", "Slowakei", "zehn, nur Ziffern", r"[0-9]{10}"),
	MemberState(
		"XI",
		"Nordirland",
		"neun oder zwölf, nur Ziffern; für Verwaltungen und Gesundheitswesen fünf, die ersten zwei "
		"Stellen GD oder HA",
		r"[0-9]{9}|[0-9]{12}|(?:GD|HA)[0-9]{3}",
	),
)
MEMBER_STATES: MappingProxyType[str, MemberState] = MappingProxyType({state.code: state for state in _STATES})

REFUSED: MappingProxyType[str, str] = MappingProxyType(
	{
		"DE": (
			"Das BZSt bestätigt Unternehmern USt-IdNrn., die ein anderer Mitgliedstaat erteilt hat, keine "
			"deutschen (§ 18e Nr. 1 UStG)."
		),
		"GB": (
			"USt-IdNrn. mit GB lassen sich seit dem 1. Januar 2021 nicht mehr bestätigen; Unternehmen in "
			"Nordirland haben eine USt-IdNr. mit XI."
		),
		"GR": "Griechenland hat in der USt-IdNr. das Länderkennzeichen EL, nicht GR.",
	}
)
"""Country codes that look right and are not, with the reason in German."""


def normalize(value: str) -> str:
	"""The number in capitals with nothing but letters, digits, + and *: "atu 123 456 78" is ATU12345678."""
	if not isinstance(value, str):
		raise TypeError(f"a USt-IdNr. is text, not {type(value).__name__}")
	return "".join(char for char in value if char in CHARACTERS).upper()


def problem(value: str | None) -> str | None:
	"""Why the value is no plausible USt-IdNr. of another member state, in German; None when it is one."""
	number = normalize(value) if isinstance(value, str) else ""
	if not number:
		return "Die USt-IdNr. fehlt."
	code = number[:2]
	if not COUNTRY_CODE.fullmatch(code):
		return f"{number} beginnt nicht mit einem Länderkennzeichen aus zwei Buchstaben."
	if code in REFUSED:
		return REFUSED[code]
	if code not in MEMBER_STATES:
		return f"{code} ist kein Länderkennzeichen eines anderen Mitgliedstaats der EU."
	if not MIN_LENGTH <= len(number) <= MAX_LENGTH:
		return f"Eine USt-IdNr. hat {MIN_LENGTH} bis {MAX_LENGTH} Zeichen, {number} hat {len(number)}."
	return None


def is_plausible(value: str | None) -> bool:
	"""True for a plausible USt-IdNr. of another member state, written in any way normalize reads."""
	return problem(value) is None


def structure_hint(value: str | None) -> str | None:
	"""A German hint when a plausible number lacks the structure the BZSt describes for its member state."""
	if not isinstance(value, str) or not is_plausible(value):
		return None
	number = normalize(value)
	state = MEMBER_STATES[number[:2]]
	if state.fits(number):
		return None
	return (
		f"{number} hat nicht den Aufbau, den das BZSt für {state.name} beschreibt "
		f"(Stellen nach dem Länderkennzeichen): {state.structure}."
	)


def is_german(value: str | None) -> bool:
	"""True for a German USt-IdNr., the number of the business that asks for a confirmation."""
	return isinstance(value, str) and GERMAN.fullmatch(normalize(value)) is not None


def german_check_digit(first_eight: str) -> int:
	"""The ninth digit of a German USt-IdNr. from its first eight, by the procedure the Konstruktionsregeln of the
	Austrian BMF give for Germany, the hybrid system ISO/IEC 7064 MOD 11,10 („Information über die Konstruktionsregeln der
	Umsatzsteuer-Identifikationsnummern (UID)“, Stand November 2020, section „DE - Deutsche UID“,
	https://bmf.gv.at/dam/jcr:d6794f8f-d321-43df-9840-1a841f9bf5dc/BMF_UID_Konstruktionsregeln_Stand_November%202020.pdf,
	retrieved 25 November 2026): „Folgende Konstruktionsregeln wurden vom jeweiligen Mitgliedstaat aufgrund
	bilateraler Vereinbarungen zur Veröffentlichung freigegeben.“ P = 10; for each digit M = (digit + P) modulo 10,
	10 where that is 0, and P = 2 M modulo 11; R = 11 - P, and the check digit is 0 where R is 10, else R. The BZSt
	and the BMF of Germany publish no rule of their own; the BZSt names a number that breaks the scheme
	„syntaktisch falsch“ (evatr-0004, evatr-0012)."""
	if len(first_eight) != 8 or not first_eight.isascii() or not first_eight.isdigit():
		raise ValueError(f"the check digit is computed from eight digits, not from {first_eight!r}")
	product = 10
	for digit in first_eight:
		total = (int(digit) + product) % 10 or 10
		product = (2 * total) % 11
	remainder = 11 - product
	return 0 if remainder == 10 else remainder


def has_german_check_digit(value: str | None) -> bool:
	"""True for a German USt-IdNr. or W-IdNr. whose ninth digit is the check digit of the eight before it
	(german_check_digit)."""
	if not is_german(value):
		return False
	number = normalize(value)
	return german_check_digit(number[2:10]) == int(number[10])


def german_problem(value: str | None) -> str | None:
	"""Why the value is no German USt-IdNr. as Germany builds them, in German; None when it is one: DE and nine digits,
	the first not 0 („C1 > 0“, Konstruktionsregeln), the last the check digit of german_check_digit."""
	number = normalize(value) if isinstance(value, str) else ""
	if not GERMAN.fullmatch(number):
		return f"Eine deutsche USt-IdNr. besteht aus DE und neun Ziffern, „{number}“ nicht."
	if number[2] == "0":
		return f"Eine deutsche USt-IdNr. beginnt nach DE nicht mit 0, {number} schon."
	if not has_german_check_digit(number):
		expected = german_check_digit(number[2:10])
		return (
			f"Die Prüfziffer von {number} stimmt nicht: Nach dem Verfahren der deutschen USt-IdNr. wäre die "
			f"letzte Ziffer {expected}."
		)
	return None


def checked_german_pair(requested: str, requester: str) -> tuple[str, str]:
	"""Both numbers of a query about a German USt-IdNr., normalized; ValueError unless requested is a German number
	with the right check digit and requester a German number."""
	reason = german_problem(requested)
	if reason is not None:
		raise ValueError(f"{requested!r} is no German USt-IdNr.: {reason}")
	if not is_german(requester):
		raise ValueError(f"{requester!r} is no German USt-IdNr. of DE and nine digits")
	return normalize(requested), normalize(requester)


def checked_pair(requested: str, requester: str) -> tuple[str, str]:
	"""Both numbers of a query, normalized; ValueError unless requested is plausible and requester German.

	Only a holder of a German USt-IdNr. may ask, and the query names it (UStAE 18e.1 Abs. 1 und 3).
	"""
	reason = problem(requested)
	if reason is not None:
		raise ValueError(f"{requested!r} is no plausible USt-IdNr. of another member state: {reason}")
	if not is_german(requester):
		raise ValueError(f"{requester!r} is no German USt-IdNr. of DE and nine digits")
	return normalize(requested), normalize(requester)

"""The Steuernummer as the Finanzamt issues it and as ELSTER takes it.

A Steuernummer has two forms: the Standardschema der Länder, in which each state writes it, such as
FF/BBB/UUUUP for Baden-Württemberg, and the vereinheitlichte Bundesschema of 13 digits, such as
28FF0BBBUUUUP, for the electronic filing. Both schemas of all 16 states come from the table
"Aufbau einer Steuernummer" of the ELSTER help topic "Wo ist meine Steuernummer?" (retrieved
18 November 2026):

https://www.elster.de/eportal/helpGlobal?themaGlobal=wo_ist_meine_steuernummer

The page explains the letters: „F = Ziffer der Finanzamtsnummer, B= Ziffer der Bezirksnummer, U = Ziffer
aus der persönlichen Unterscheidungsnummer, P = Prüfziffer“, and warns that a Steuernummer from Hessen
keeps its leading 0 in the Standardschema. Converting keeps the digits in the order of the letters and
writes the fixed digits of the target schema. Only the shape is checked: the page does not say how the
Prüfziffer is computed.

The Standardschema separates the groups with slashes; a number typed with blanks between the groups,
or without separators, is read as well. States are identified by their ISO 3166-2 codes.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from string import digits
from types import MappingProxyType

DIGITS = frozenset(digits)
GROUP_SEPARATOR = "/"
SEPARATORS = frozenset(GROUP_SEPARATOR + " ")


class SteuernummerError(ValueError):
	pass


@dataclass(frozen=True, slots=True)
class Scheme:
	"""How a state writes its Steuernummer: as the Finanzamt prints it and as ELSTER takes it.

	Each letter stands for one digit of the number, the digits are fixed, and the slashes of
	``standard`` separate the groups as printed.
	"""

	standard: str
	federal: str


STATES: Mapping[str, str] = MappingProxyType(
	{
		"BW": "Baden-Württemberg",
		"BY": "Bayern",
		"BE": "Berlin",
		"BB": "Brandenburg",
		"HB": "Bremen",
		"HH": "Hamburg",
		"HE": "Hessen",
		"MV": "Mecklenburg-Vorpommern",
		"NI": "Niedersachsen",
		"NW": "Nordrhein-Westfalen",
		"RP": "Rheinland-Pfalz",
		"SL": "Saarland",
		"SN": "Sachsen",
		"ST": "Sachsen-Anhalt",
		"SH": "Schleswig-Holstein",
		"TH": "Thüringen",
	}
)

SCHEMES: Mapping[str, Scheme] = MappingProxyType(
	{
		"BW": Scheme("FF/BBB/UUUUP", "28FF0BBBUUUUP"),
		"BY": Scheme("FFF/BBB/UUUUP", "9FFF0BBBUUUUP"),
		"BE": Scheme("FF/BBB/UUUUP", "11FF0BBBUUUUP"),
		"BB": Scheme("FFF/BBB/UUUUP", "3FFF0BBBUUUUP"),
		"HB": Scheme("FF/BBB/UUUUP", "24FF0BBBUUUUP"),
		"HH": Scheme("FF/BBB/UUUUP", "22FF0BBBUUUUP"),
		"HE": Scheme("0FF/BBB/UUUUP", "26FF0BBBUUUUP"),
		"MV": Scheme("FFF/BBB/UUUUP", "4FFF0BBBUUUUP"),
		"NI": Scheme("FF/BBB/UUUUP", "23FF0BBBUUUUP"),
		"NW": Scheme("FFF/BBBB/UUUP", "5FFF0BBBBUUUP"),
		"RP": Scheme("FF/BBB/UUUUP", "27FF0BBBUUUUP"),
		"SL": Scheme("FFF/BBB/UUUUP", "1FFF0BBBUUUUP"),
		"SN": Scheme("FFF/BBB/UUUUP", "3FFF0BBBUUUUP"),
		"ST": Scheme("FFF/BBB/UUUUP", "3FFF0BBBUUUUP"),
		"SH": Scheme("FF/BBB/UUUUP", "21FF0BBBUUUUP"),
		"TH": Scheme("FFF/BBB/UUUUP", "4FFF0BBBUUUUP"),
	}
)

STATE_CODES: Mapping[str, str] = MappingProxyType({name: code for code, name in STATES.items()})


def validate(state: str, tax_number: str) -> None:
	"""Raise a SteuernummerError unless tax_number has the shape the Finanzamt of the state issues."""
	to_elster(state, tax_number)


def to_elster(state: str, tax_number: str) -> str:
	"""The 13-digit Steuernummer for ELSTER from the Steuernummer as the Finanzamt issued it."""
	scheme = _scheme(state)
	number = _without_separators(scheme.standard, _text(tax_number))
	letters = None if number is None else _letters(scheme.standard.replace(GROUP_SEPARATOR, ""), number)
	if letters is None:
		raise SteuernummerError(
			f"{tax_number!r} is not a Steuernummer of {STATES[state]}: expected {scheme.standard}"
		)
	return _fill(scheme.federal, letters)


def from_elster(state: str, elster_tax_number: str) -> str:
	"""The Steuernummer as the Finanzamt of the state prints it, from the 13-digit form for ELSTER."""
	scheme = _scheme(state)
	letters = _letters(scheme.federal, _text(elster_tax_number))
	if letters is None:
		raise SteuernummerError(
			f"{elster_tax_number!r} is not a 13-digit Steuernummer of {STATES[state]}: "
			f"expected {scheme.federal}"
		)
	return _fill(scheme.standard, letters)


def _scheme(state: str) -> Scheme:
	if not isinstance(state, str) or state not in SCHEMES:
		raise SteuernummerError(f"unknown state {state!r}, expected one of {', '.join(STATES)}")
	return SCHEMES[state]


def _text(value: str) -> str:
	if not isinstance(value, str):
		raise SteuernummerError(f"a Steuernummer is text, not {type(value).__name__}")
	return value.strip()


def _without_separators(standard: str, text: str) -> str | None:
	"""The number without separators, if it has one wherever the scheme has a slash, or none at all."""
	if SEPARATORS.isdisjoint(text):
		return text
	if len(text) != len(standard):
		return None
	if any(
		(expected == GROUP_SEPARATOR) != (char in SEPARATORS)
		for expected, char in zip(standard, text, strict=True)
	):
		return None
	return "".join(char for char in text if char not in SEPARATORS)


def _letters(pattern: str, number: str) -> str | None:
	"""The digits of the number that stand for the letters of the pattern, if it fits the pattern."""
	if len(number) != len(pattern) or not DIGITS.issuperset(number):
		return None
	if any(expected in DIGITS and char != expected for expected, char in zip(pattern, number, strict=True)):
		return None
	return "".join(char for expected, char in zip(pattern, number, strict=True) if expected not in DIGITS)


def _fill(pattern: str, letters: str) -> str:
	"""The pattern with its letters replaced by the digits, in their order."""
	remaining = iter(letters)
	return "".join(char if char in DIGITS or char == GROUP_SEPARATOR else next(remaining) for char in pattern)

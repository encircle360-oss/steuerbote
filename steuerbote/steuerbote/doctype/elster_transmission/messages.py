"""The errors and hints among the messages of an ELSTER Transmission, as the form of its document names them.

Hints never stop a run: „Grundsätzlich ist aber ein Datensatz, für den Hinweise aber keine Fehler gemeldet werden,
valide und könnte versendet oder gedruckt werden. Hinweise werden im Rückgabepuffer von EricBearbeiteVorgang()
zurückgegeben und können dem Anwender des Steuerprogramms angezeigt werden.“ (ERiC-Entwicklerhandbuch 44.3.6.0,
Kap. 5.1.2.4.1) A check with hints succeeds, so only its messages tell what ELSTER remarks.
"""

import re
from collections.abc import Iterable
from typing import Any, Protocol

from steuerbote.eric.result import ERROR, HINT, SCHEMA_NOT_CHECKED

ERIC_PATH = re.compile(r"\$(/[^$]*)\$")
"""A field in the text of a message of ERiC, its path in the delivery between dollar signs."""
PLACE = re.compile(r"^\[\d+,\d+\]\s*")
"""Line and column of the instance, which ERiC puts before a message of the rules of the XBRL taxonomy."""
CLARK = re.compile(r"\{[^{}]*\}([\w.\-]+)")
"""A fact named with the namespace of its taxonomy in Clark notation, such as {http://…/de-gaap-ci-…}bs.ass."""
SPACES = re.compile(r" {2,}")
HYPERCUBE = re.compile(r"\w+:all")
"""The field ERiC names for a rule on the dimensions of a fact: the hypercube, not a position of the E-Bilanz."""
KENNZAHL = re.compile(r"Kz(\d+)")
FELDKENNUNG = re.compile(r"E\d{7}")
SHOWN = 3
"""How many errors and how many hints the form of the document names; the rest stays on the ELSTER Transmission."""


class Row(Protocol):
	"""A message of an ELSTER Transmission: a dict, or a child document of Frappe, which reads the same way."""

	def get(self, key: str, default: Any = None) -> Any: ...


def summary(rows: Iterable[Row], shown: int = SHOWN) -> dict[str, Any]:
	"""How many errors and how many hints ``rows`` hold, the first ``shown`` of each with code and text, and whether the
	simulation checked no schema (SCHEMA_NOT_CHECKED), which a run that succeeds may not hide."""
	messages = [
		(row.get("severity"), {"code": row.get("code") or "", "text": row.get("text") or ""}) for row in rows
	]
	errors = [message for severity, message in messages if severity == ERROR]
	hints = [message for severity, message in messages if severity == HINT]
	return {
		"errors": len(errors),
		"hints": len(hints),
		"first_errors": errors[:shown],
		"first_hints": hints[:shown],
		"schema_unchecked": any(message["code"] == SCHEMA_NOT_CHECKED for _severity, message in messages),
	}


def readable(text: str, field: str | None, datenart: str, year: int | None) -> tuple[str, str | None]:
	"""Text and field of a message of ERiC with each field named as the Vordruck names it, where ERiC names its path in
	the delivery: a Kennzahl as „Kz 61“, a field of an Erklärung by its line, such as „KSt1 Zeile 22c (E8122101)“, any
	other by the last element of its path. A message of the rules of the XBRL taxonomy names its fact without the
	namespace and without its place in the instance, and the fact is its field instead of the hypercube. A field that is
	no path stays as it is."""
	facts = CLARK.findall(text)
	text = SPACES.sub(" ", CLARK.sub(r"\1", PLACE.sub("", text)))
	if field and facts and HYPERCUBE.fullmatch(field):
		field = facts[0]
	text = ERIC_PATH.sub(lambda found: _named(found.group(1), datenart, year), text)
	if field and field.startswith("/"):
		field = _named(field, datenart, year)
	return text, field


def _named(path: str, datenart: str, year: int | None) -> str:
	name = path.rstrip("/").rpartition("/")[2].partition("[")[0]
	if kennzahl := KENNZAHL.fullmatch(name):
		return f"Kz {kennzahl.group(1)}"
	if year is not None and FELDKENNUNG.fullmatch(name):
		return _line(datenart, year, name) or name
	return name


def _line(datenart: str, year: int, feldkennung: str) -> str | None:
	"""The Vordruck and line of a field of an Erklärung of a year Steuerbote has a catalogue of, else None."""
	from steuerbote.gewst.form import CATALOGUES as GEWST
	from steuerbote.kst.form import CATALOGUES as KST
	from steuerbote.ustjahr.form import CATALOGUES as UST

	if datenart == "USt" and year in UST:
		line = next((field.line for field in UST[year].fields if field.element == feldkennung), None)
		return None if line is None else f"Zeile {line} ({feldkennung})"
	catalogue = {"KSt": KST, "GewSt": GEWST}.get(datenart, {}).get(year)
	if catalogue is None:
		return None
	try:
		field = catalogue.field(feldkennung)
	except KeyError:
		return None
	return f"{field.form} Zeile {field.line} ({feldkennung})"

"""Acknowledgements: the deliberate decision to file a document although an error of its findings holds it back.

An error of the findings holds a document back from „Bereit“ (steuerbote/jahresmeldung/findings.py). Some errors only
say that something is not certain, such as forms that are provisional, an account whose place is not decided or a
review not yet noted: the company may file nonetheless, once it says why. It does so per finding, on the finding
itself, with a reason, its name and the time, so that the remarks of a document stay a note that files nothing and a
later reader sees which error was accepted and by whom. An acknowledgement counts only with a reason.

Other errors make the file wrong by construction, and no reason makes it right; they are never acknowledged (NEVER,
with the ground and its source in SOURCES):

- ERIC: an error of a rule of a Jahresdokumentation, whose code is its numeric Fehlercode: „ein Datensatz, für den
  Hinweise aber keine Fehler gemeldet werden, [ist] valide und könnte versendet oder gedruckt werden“
  (ERiC-Entwicklerhandbuch 44.3.6.0, Kap. 5.1.2.4.1), so ERiC and ELSTER refuse a Datensatz with an error.
- NOT_BALANCED: Aktiva and Passiva apart, „Die Bilanz ... [hat] auf der Aktivseite ... und auf der Passivseite ...
  auszuweisen“ in one sum (§ 242 Abs. 1, § 266 Abs. 1 HGB).
- RESULT: a Jahresergebnis other than that of the GuV, or a return whose result is not that of the E-Bilanz it reads.
- INCOMPLETE: a balance without a place, so the balance sheet lacks it: „Der Jahresabschluß hat sämtliche
  Vermögensgegenstände, Schulden ... zu enthalten“ (§ 246 Abs. 1 Satz 1 HGB).
- STRUCTURE: sums, Mussfelder and positions the HGB-Taxonomie demands of the „amtlich vorgeschriebener Datensatz“ (§ 5b
  Abs. 1 Satz 1 EStG; Technischer Leitfaden zur HGB-Taxonomie A.10, B.10).
- VERSION: a mapping of another version of the taxonomy than the document's.
- STALE: a calculation older than what it reads; Berechnen comes first. So is a correction made against another amount
  than Berechnen computes now (jahresmeldung.overrides.stale): it is confirmed or removed, not acknowledged.
- FILE: Nutzdaten that do not pass their schema.

Berechnen writes the findings anew and keeps the acknowledgement of a finding that stays the same, by its code,
reference and text: an error whose amount or wording changed asks again (carried). A document is fit for filing when
no error is open (open_errors) and none can never be acknowledged (never), which steuerbote.jahresmeldung.lifecycle
checks.

The model is shared: a row is a mapping with the columns of the table Befunde (Annual Filing Finding), code,
blocking, text and reference, and the columns of this module, ACKNOWLEDGEABLE, ACKNOWLEDGED, REASON, BY and ON. Another
document with a table of findings, such as the Voranmeldung or the Zusammenfassende Meldung, takes it by giving its
table these columns and its codes a place in NEVER where they make the file wrong by construction.

This module is pure Python and never imports Frappe.
"""

from collections.abc import Iterable, Mapping
from datetime import datetime
from enum import Enum, StrEnum
from types import MappingProxyType
from typing import Any

ACKNOWLEDGEABLE = "acknowledgeable"
ACKNOWLEDGED = "acknowledged"
REASON = "acknowledgement_reason"
BY = "acknowledged_by"
ON = "acknowledged_on"
FIELDS = (ACKNOWLEDGED, REASON, BY, ON)
"""The columns an acknowledgement writes on its row."""

type Row = Mapping[str, Any]


class Ground(StrEnum):
	"""Why an error can never be acknowledged."""

	ERIC = "eric"
	NOT_BALANCED = "not_balanced"
	RESULT = "result"
	INCOMPLETE = "incomplete"
	STRUCTURE = "structure"
	VERSION = "version"
	STALE = "stale"
	FILE = "file"


SOURCES: MappingProxyType[Ground, str] = MappingProxyType(
	{
		Ground.ERIC: "ERiC-Entwicklerhandbuch 44.3.6.0, Kap. 5.1.2.4.1: a Datensatz with an error is not valid",
		Ground.NOT_BALANCED: "§ 242 Abs. 1, § 266 Abs. 1 HGB: Aktiva and Passiva are the two sides of one sum",
		Ground.RESULT: "§ 266 Abs. 3 A. V., § 275 HGB; § 5b Abs. 1 EStG: one Jahresergebnis in Bilanz, GuV and returns",
		Ground.INCOMPLETE: "§ 246 Abs. 1 Satz 1 HGB: the Jahresabschluss holds every Vermögensgegenstand and Schuld",
		Ground.STRUCTURE: "§ 5b Abs. 1 Satz 1 EStG; Technischer Leitfaden zur HGB-Taxonomie A.10, B.10",
		Ground.VERSION: "§ 5b Abs. 1 Satz 1 EStG: the amtlich vorgeschriebener Datensatz of the version of the year",
		Ground.STALE: "§ 150 Abs. 2 Satz 1 AO: the return as the books stand, calculated from what it reads today",
		Ground.FILE: "§ 150 Abs. 6 AO: the Datensatz in the form and schema the administration prescribes",
	}
)

NEVER: MappingProxyType[str, Ground] = MappingProxyType(
	{
		"JA-BILANZ-UNGLEICH": Ground.NOT_BALANCED,
		"JA-BILANZGEWINN": Ground.RESULT,
		"KST-EBILANZ-ABWEICHUNG": Ground.RESULT,
		"BILANZ-OHNE-PLATZ": Ground.INCOMPLETE,
		"BILANZ-OHNE-KONTONUMMER": Ground.INCOMPLETE,
		"BILANZ-BEOBACHTET": Ground.INCOMPLETE,
		"BILANZ-POSITION": Ground.INCOMPLETE,
		"BILANZ-NICHT-GUELTIG": Ground.INCOMPLETE,
		"BILANZ-ABSCHLUSSKONTO": Ground.INCOMPLETE,
		"EB-NICHT-ZUGEORDNET": Ground.INCOMPLETE,
		"JA-OHNE-POSTEN": Ground.INCOMPLETE,
		"JA-RECHENPOSTEN": Ground.INCOMPLETE,
		"JA-OHNE-UNTERPOSTEN": Ground.INCOMPLETE,
		"EB-SUMME": Ground.STRUCTURE,
		"EB-KORREKTUR-SUMME": Ground.STRUCTURE,
		"EB-BERECHNET": Ground.STRUCTURE,
		"EB-UEBERLEITUNG-SUMME": Ground.STRUCTURE,
		"XBRL-RECHNUNG": Ground.STRUCTURE,
		"XBRL-MUSSFELD": Ground.STRUCTURE,
		"XBRL-SUMMENMUSSFELD": Ground.STRUCTURE,
		"XBRL-UNZULAESSIG": Ground.STRUCTURE,
		"XBRL-NICHT-UEBERMITTELBAR": Ground.STRUCTURE,
		"XBRL-RECHTSFORM": Ground.STRUCTURE,
		"XBRL-SONDERBILANZ": Ground.STRUCTURE,
		"XBRL-KONTEXT": Ground.STRUCTURE,
		"XBRL-BERICHTSBESTANDTEIL": Ground.STRUCTURE,
		"XBRL-OBERPOSITION": Ground.STRUCTURE,
		"XBRL-GUV-FORMAT": Ground.STRUCTURE,
		"BILANZ-TAXONOMIE": Ground.VERSION,
		"SB-ZUORDNUNG-VERSION": Ground.VERSION,
		"SB-NEU-BERECHNEN": Ground.STALE,
		"SB-KORREKTUR-UEBERHOLT": Ground.STALE,
		"KST-NUTZDATEN": Ground.FILE,
		"GEWST-NUTZDATEN": Ground.FILE,
	}
)
"""The codes of Steuerbote whose error makes the file wrong by construction, with the ground."""


class Problem(Enum):
	NEVER = "never"
	NOT_AN_ERROR = "not_an_error"


class AcknowledgementError(ValueError):
	"""An acknowledgement refused: of an error that can never be acknowledged, or of a hint."""

	def __init__(self, problem: Problem, code: str) -> None:
		super().__init__(f"{code}: {problem.value}")
		self.problem = problem
		self.code = code


def ground_of(code: str) -> Ground | None:
	"""Why an error of the code can never be acknowledged, None where it can."""
	code = str(code or "").strip()
	if code.isdigit():
		return Ground.ERIC
	return NEVER.get(code)


def acknowledgeable(code: str) -> bool:
	return ground_of(code) is None


def acknowledge(row: Row, reason: str | None, by: str, on: datetime) -> dict[str, Any]:
	"""The row with its error acknowledged for the reason, by the user, at the time; an empty reason withdraws it."""
	code = str(row.get("code") or "")
	if not row.get("blocking"):
		raise AcknowledgementError(Problem.NOT_AN_ERROR, code)
	if not acknowledgeable(code):
		raise AcknowledgementError(Problem.NEVER, code)
	reason = (reason or "").strip()
	if not reason:
		return {**row, ACKNOWLEDGED: 0, REASON: None, BY: None, ON: None}
	return {**row, ACKNOWLEDGED: 1, REASON: reason, BY: by, ON: on}


def is_acknowledged(row: Row) -> bool:
	"""Whether the error of the row is acknowledged with a reason, and may be."""
	return (
		bool(row.get(ACKNOWLEDGED))
		and bool(str(row.get(REASON) or "").strip())
		and acknowledgeable(str(row.get("code") or ""))
	)


def open_errors(rows: Iterable[Row]) -> tuple[Row, ...]:
	"""The errors that hold the document: not acknowledged, or never to be."""
	return tuple(row for row in rows if row.get("blocking") and not is_acknowledged(row))


def never(rows: Iterable[Row]) -> tuple[Row, ...]:
	"""The errors that can never be acknowledged."""
	return tuple(
		row for row in rows if row.get("blocking") and not acknowledgeable(str(row.get("code") or ""))
	)


def carried(rows: Iterable[Row], before: Iterable[Row]) -> list[dict[str, Any]]:
	"""The new rows of Berechnen, each with the acknowledgement the same finding had before."""
	kept = {_key(row): row for row in before if is_acknowledged(row)}
	result = []
	for row in rows:
		earlier = kept.get(_key(row)) if row.get("blocking") else None
		result.append({**row, **{name: earlier.get(name) for name in FIELDS}} if earlier else dict(row))
	return result


def _key(row: Row) -> tuple[str, str, str]:
	return tuple(str(row.get(name) or "").strip() for name in ("code", "reference", "text"))

"""The errors and hints among the messages of an ELSTER Transmission, as the form of its document names them.

Hints never stop a run: „Grundsätzlich ist aber ein Datensatz, für den Hinweise aber keine Fehler gemeldet werden,
valide und könnte versendet oder gedruckt werden. Hinweise werden im Rückgabepuffer von EricBearbeiteVorgang()
zurückgegeben und können dem Anwender des Steuerprogramms angezeigt werden.“ (ERiC-Entwicklerhandbuch 44.3.6.0,
Kap. 5.1.2.4.1) A check with hints succeeds, so only its messages tell what ELSTER remarks.
"""

from collections.abc import Iterable
from typing import Any, Protocol

from steuerbote.eric.result import ERROR, HINT

SHOWN = 3
"""How many errors and how many hints the form of the document names; the rest stays on the ELSTER Transmission."""


class Row(Protocol):
	"""A message of an ELSTER Transmission: a dict, or a child document of Frappe, which reads the same way."""

	def get(self, key: str, default: Any = None) -> Any: ...


def summary(rows: Iterable[Row], shown: int = SHOWN) -> dict[str, Any]:
	"""How many errors and how many hints ``rows`` hold, and the first ``shown`` of each with code and text."""
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
	}

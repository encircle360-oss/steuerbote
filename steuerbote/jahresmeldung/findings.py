"""Findings on an annual document: what holds it back from „Bereit“, and what someone should look at.

Every annual document keeps what the checks of its module found in one table, „Befunde“ (the child DocType Annual
Filing Finding), with the Art, the Code, the Nachricht and the Referenz of each finding. A finding is a Fehler or a
Hinweis, as the Jahresdokumentationen of the ERiC documentation 44.3.6.0 mark each rule with its „Regelart“: an
error blocks „Bereit“, a hint changes nothing, since „ein Datensatz, für den Hinweise aber keine Fehler gemeldet
werden, [ist] valide und könnte versendet oder gedruckt werden“ (ERiC-Entwicklerhandbuch, Kap. 5.1.2.4.1). A
document that is not ready is filed only once its remarks say why (steuerbote.jahresmeldung.lifecycle).

The code is the Fehlercode of a rule of a Jahresdokumentation, such as 30639, or a code of Steuerbote; the reference
names what the finding is about, such as a field, a position, an account, a voucher or a period. The text is the
message for the person who files the document, in the language the Frappe layer wrote it in.
"""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

DATA_LENGTH = 140
"""The characters a Data field of Frappe holds, which takes the code and the reference."""


class FindingError(ValueError):
	"""A finding that the table Befunde cannot hold."""


class Severity(StrEnum):
	ERROR = "Fehler"
	HINT = "Hinweis"

	@classmethod
	def of(cls, value: object) -> Severity:
		"""The severity of a value, or of an enum whose value is Fehler or Hinweis, such as the severity a core of a
		module gives its findings."""
		try:
			return cls(getattr(value, "value", value))
		except ValueError:
			raise FindingError(f"{value!r} is neither Fehler nor Hinweis") from None


@dataclass(frozen=True, slots=True)
class Finding:
	"""What a check of an annual document found. Code, text and reference are kept without blanks at either end."""

	code: str
	severity: Severity
	text: str
	reference: str = ""

	def __post_init__(self) -> None:
		object.__setattr__(self, "severity", Severity.of(self.severity))
		for name, required in (("code", True), ("text", True), ("reference", False)):
			value = getattr(self, name)
			if not isinstance(value, str):
				raise FindingError(f"the {name} of a finding is a text, not {value!r}")
			value = value.strip()
			if required and not value:
				raise FindingError(f"a finding needs a {name}")
			object.__setattr__(self, name, value)
		for name in ("code", "reference"):
			if len(getattr(self, name)) > DATA_LENGTH:
				raise FindingError(f"the {name} of a finding has at most {DATA_LENGTH} characters")

	@property
	def blocking(self) -> bool:
		"""Whether the finding holds the document back from „Bereit“: an error does, a hint does not."""
		return self.severity is Severity.ERROR


def ready(findings: Iterable[Finding], *passed: bool) -> bool:
	"""„Bereit zur Abgabe“: no finding blocks, and every check the module reports besides passed."""
	return all(passed) and not blocking(findings)


def blocking(findings: Iterable[Finding]) -> tuple[Finding, ...]:
	return tuple(finding for finding in findings if finding.blocking)


def ordered(findings: Iterable[Finding]) -> tuple[Finding, ...]:
	"""The findings as the table lists them: the errors first, then the hints, each in the order found and once."""
	unique = tuple(dict.fromkeys(findings))
	return (*blocking(unique), *(finding for finding in unique if not finding.blocking))


def rows(findings: Iterable[Finding]) -> list[dict[str, Any]]:
	"""The rows of the table Befunde, in their order."""
	return [
		{
			"severity": finding.severity.value,
			"blocking": int(finding.blocking),
			"code": finding.code,
			"text": finding.text,
			"reference": finding.reference,
		}
		for finding in ordered(findings)
	]


def of_rows(stored: Iterable[Mapping[str, Any]]) -> tuple[Finding, ...]:
	"""The findings of the rows of the table Befunde, as rows() wrote them."""
	return tuple(
		Finding(row.get("code"), row.get("severity"), row.get("text"), row.get("reference") or "")
		for row in stored
	)

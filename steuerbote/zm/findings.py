"""Findings on a Zusammenfassende Meldung: what holds it back, and what someone should look at.

A finding is one sentence in German for the person who files the ZM, with the voucher and party it is about
where there is one. An error holds the ZM back from „Bereit“ until it is fixed or, where the module that finds
it allows, overridden with a Begründung; a hint changes nothing. Amounts in the sentences are written by the
Figures of steuerbote.ustva.plausibility, in the number format of the site.
"""

from dataclasses import dataclass
from enum import Enum, StrEnum


class Severity(Enum):
	ERROR = "Fehler"
	HINT = "Hinweis"


class Code(StrEnum):
	NO_PARTY = "ZM-OHNE-KUNDE"
	NO_VAT_ID = "ZM-OHNE-USTID"
	MALFORMED_VAT_ID = "ZM-USTID-FORMAT"
	INVALID_VAT_ID = "ZM-USTID-UNGUELTIG"
	UNCONFIRMED_VAT_ID = "ZM-USTID-UNBESTAETIGT"
	DESTINATION = "ZM-DREIECK-LAND"
	THRESHOLD = "ZM-SCHWELLE"
	LEDGER = "ZM-ABGLEICH-HAUPTBUCH"
	FILED_RETURNS = "ZM-ABGLEICH-VORANMELDUNG"
	PREVIOUS_PERIOD = "ZM-ABWEICHUNG-VORPERIODE"


# The rounding of a ZM may part from the filed Voranmeldungen by some euros, and a quieter period explains a
# change; neither holds the ZM back.
BLOCKING: frozenset[Code] = frozenset(set(Code) - {Code.FILED_RETURNS, Code.PREVIOUS_PERIOD})


@dataclass(frozen=True, slots=True)
class Finding:
	"""``voucher`` is the key "<voucher type>:<voucher name>" of steuerbote.ledger."""

	code: Code
	text: str
	voucher: str | None = None
	party: str = ""

	@property
	def severity(self) -> Severity:
		return Severity.ERROR if self.code in BLOCKING else Severity.HINT

	@property
	def blocking(self) -> bool:
		return self.severity is Severity.ERROR


def voucher_no(voucher: str | None) -> str:
	"""The name of the voucher in a key "<voucher type>:<voucher name>", as a sentence names it."""
	return (voucher or "").partition(":")[2] or (voucher or "")

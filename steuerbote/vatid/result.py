"""What a query to confirm a USt-IdNr. asked, what came back, and what that means.

A Confirmation is the record of one query, to the BZSt or to VIES. The BZSt sends no written confirmation
(„Das BZSt versendet keine schriftliche Bestätigungsmitteilung.“, BZSt, "Fragen und Antworten" zur
USt-IdNr.); for a query over its interface the data record it returns is the proof: „In diesen Fällen ist
der Nachweis einer durchgeführten qualifizierten Anfrage einer USt-IdNr. über den vom BZSt empfangenen
Datensatz zu führen.“ (UStAE 18e.1 Abs. 2 Satz 5). A record keeps that answer as it came in response_text,
together with what was asked, which the answer does not repeat: both numbers and, for a qualified query,
name and address.

A confirmation can take two queries: the simple one before the qualified one, or the BZSt before VIES.
Each is a record of its own, and the later one holds the earlier one in previous.
"""

from dataclasses import dataclass
from datetime import date, datetime
from enum import Enum

NO_ANSWER = "SB-NO-ANSWER"
"""The status of a record without an answer: no response came, whichever the service."""
UNREADABLE = "SB-UNREADABLE"
"""The status of a record whose answer is not what the service documents."""


class Service(Enum):
	BZST = "bzst"
	"""The eVatR REST API of the Bundeszentralamt für Steuern."""
	VIES = "vies"
	"""The VAT Information Exchange System of the European Commission."""


class Outcome(Enum):
	VALID = "valid"
	"""The service confirmed the number as valid at the time of the query."""
	INVALID = "invalid"
	"""The service answered that the number was not valid at the time of the query: not issued, not yet or
	no longer valid, or not built the way its member state builds its numbers."""
	UNKNOWN = "unknown"
	"""No answer about the number: the service was unavailable, refused the request or answered something
	unreadable."""


class Match(Enum):
	"""How a detail of a qualified query compares with what the member state has registered.

	The values are the letters of the BZSt (OpenAPI document of the eVatR API, description of
	/v1/abfrage). VIES answers 1 (VALID), 2 (INVALID) and 3 (NOT_PROCESSED), read as A, B and D.
	"""

	MATCHES = "A"
	"""„Die Angaben … stimmen mit den registrierten Daten überein.“"""
	DIFFERS = "B"
	"""„Die Angaben … stimmen mit den registrierten Daten nicht überein.“"""
	NOT_REQUESTED = "C"
	"""„Die Angaben … wurden nicht angefragt.“"""
	NOT_PROVIDED = "D"
	"""„Die Angaben … wurden vom EU-Mitgliedsstaat nicht mitgeteilt.“"""


@dataclass(frozen=True, slots=True)
class Details:
	"""Name and address of the holder of the requested number, for the qualified query.

	The BZSt runs the qualified query when name and city are given; street and postcode are optional
	(OpenAPI document of the eVatR API, description of /v1/abfrage).
	"""

	name: str
	"""Firmenname, with the legal form (BZSt FAQ: „Firmenname (einschließlich der Rechtsform)“)."""
	city: str
	postcode: str = ""
	street: str = ""
	"""Street and house number."""

	def __post_init__(self):
		for field in ("name", "city", "postcode", "street"):
			value = getattr(self, field)
			if not isinstance(value, str):
				raise TypeError(f"{field} is text, not {type(value).__name__}")
			if any(ord(char) < 0x20 for char in value):
				raise ValueError(f"{field} holds a control character")
			object.__setattr__(self, field, value.strip())
		if not (self.name and self.city):
			raise ValueError("the qualified query needs the name and the city")


@dataclass(frozen=True, slots=True)
class Confirmation:
	requested: str
	"""The USt-IdNr. asked about, normalized."""
	requester: str
	"""The German USt-IdNr. of the business that asked."""
	service: Service
	outcome: Outcome
	status: str
	"""The status of the BZSt (evatr-…), the fault of VIES or VALID and INVALID for its answer, or a code
	of steuerbote (SB-…) when no readable answer came."""
	message: str
	"""What the status means, in German: for the BZSt the text of its status catalogue."""
	requested_at: datetime
	"""When the request left, by the clock the caller passed."""
	answered_at: datetime
	"""When the answer came, or the transport gave up, by the same clock."""
	details: Details | None = None
	"""Name and address the query asked about; None for a simple query."""
	consultation_id: str | None = None
	"""The id the BZSt gives its answer, or the requestIdentifier of VIES."""
	service_time: datetime | None = None
	"""The anfrageZeitpunkt of the BZSt; VIES names the day only."""
	service_date: date | None = None
	"""The day of the query as the service names it: the date of anfrageZeitpunkt or the requestDate of VIES."""
	valid_from: date | None = None
	"""gueltigAb of the BZSt, for a number that is not or no longer valid."""
	valid_until: date | None = None
	"""gueltigBis of the BZSt, for a number that is no longer valid."""
	name_match: Match | None = None
	street_match: Match | None = None
	postcode_match: Match | None = None
	city_match: Match | None = None
	http_status: int | None = None
	"""The HTTP status of the answer; None when none came."""
	response_text: str | None = None
	"""The answer as it came, the proof of the query; None when none came."""
	unavailable: bool = False
	"""The service could not process the query now: no answer, a server error, or a status that says so."""
	fallback_reason: str | None = None
	"""Why VIES answered in place of the BZSt, in German."""
	previous: Confirmation | None = None
	"""The query this one followed within the same confirmation."""

	def __post_init__(self):
		for name in ("requested_at", "answered_at"):
			if getattr(self, name).tzinfo is None:
				raise ValueError(f"{name} needs a time zone")
		if self.service_time is not None and self.service_date != self.service_time.date():
			raise ValueError("service_date is the day of service_time")
		if self.unavailable and self.outcome is not Outcome.UNKNOWN:
			raise ValueError("an unavailable service leaves the outcome unknown")
		if self.outcome is not Outcome.UNKNOWN and self.response_text is None:
			raise ValueError("a definite outcome keeps the answer it comes from")
		if self.details is None and self.matches() != (None, None, None, None):
			raise ValueError("only a qualified query compares name and address")
		if self.fallback_reason is not None and self.service is not Service.VIES:
			raise ValueError("only VIES answers in place of the BZSt")

	@property
	def qualified(self) -> bool:
		"""True when the query asked about name and address as well."""
		return self.details is not None

	def matches(self) -> tuple[Match | None, Match | None, Match | None, Match | None]:
		"""The results for name, street, postcode and city."""
		return (self.name_match, self.street_match, self.postcode_match, self.city_match)

	def queries(self) -> tuple[Confirmation, ...]:
		"""The queries of this confirmation, from the first to this one."""
		earlier = () if self.previous is None else self.previous.queries()
		return (*earlier, self)

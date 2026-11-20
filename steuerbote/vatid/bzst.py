"""The confirmation of a USt-IdNr. over the eVatR REST API of the BZSt.

A query is one POST of a Bestaetigungsabfrage to https://api.evatr.vies.bzst.de/app/v1/abfrage (OpenAPI
3.0.1 "eVATR API", version v:1.2.3.19.886, https://api.evatr.vies.bzst.de/api-docs, retrieved 20 November
2026): anfragendeUstid and angefragteUstid for the simple query, and for the qualified query firmenname
and ort as well, with strasse and plz when they are known. The answer is a Bestaetigungsantwort with
anfrageZeitpunkt and status, and where they apply id, gueltigAb, gueltigBis and the results ergFirmenname,
ergStrasse, ergPlz and ergOrt of a qualified query, each a letter from A to D. The OpenAPI document names a
status for every HTTP code it lists; a probe on 20 November 2026, asking with the example number
DE123456789 about an invented number, got HTTP 400 with id, anfrageZeitpunkt and status evatr-0004.

STATUSES is the status catalogue of the BZSt (https://api.evatr.vies.bzst.de/v1/info/statusmeldungen,
retrieved 20 November 2026), each status with the outcome its message states. Valid are the statuses that
say „ist zum Anfragezeitpunkt gültig“, invalid those that say the number is not issued, not yet or no
longer valid, has no valid country code or is not built the way its member state builds its numbers.
Every other status says nothing about the number. A status the catalogue gives with HTTP 500 or 503 means
that the BZSt could not process the query: then, and when no answer came at all or a server error came
without a readable status, the BZSt is unavailable, and service.confirm may ask VIES.

A query sends one request and never repeats it: after long waits or timeouts the BZSt asks for another
try at another time of day, „Bitte sehen Sie von einem unmittelbaren Wiederholen der Anfrage ab.“ (BZSt,
"Bestätigung ausländischer USt-IdNrn", "Hinweis zum Bestätigungsverfahren").
"""

import json
from dataclasses import dataclass
from datetime import date, datetime
from types import MappingProxyType

from steuerbote.vatid.result import NO_ANSWER, UNREADABLE, Confirmation, Details, Match, Outcome, Service
from steuerbote.vatid.transport import SERVER_ERROR, Clock, Fetch, Request, Response
from steuerbote.vatid.ustid import checked_pair

URL = "https://api.evatr.vies.bzst.de/app/v1/abfrage"
HEADERS = MappingProxyType({"Content-Type": "application/json", "Accept": "application/json"})
RESULTS = (
	("ergFirmenname", "name_match"),
	("ergStrasse", "street_match"),
	("ergPlz", "postcode_match"),
	("ergOrt", "city_match"),
)
"""The results of a qualified query and the fields of the record that keep them."""

_MATCHES = MappingProxyType({match.value: match for match in Match})


@dataclass(frozen=True, slots=True)
class Status:
	code: str
	http: int | None
	"""The HTTP status the catalogue gives the code; evatr-0001 has none."""
	category: str
	"""Ergebnis, Hinweis or Fehler, as the catalogue sorts the code."""
	field: str | None
	"""The field of the query the code is about, as the catalogue names it."""
	message: str
	"""The text of the catalogue, word for word."""
	outcome: Outcome

	@property
	def unavailable(self) -> bool:
		"""The catalogue gives the code a server error: the BZSt could not process the query now."""
		return self.http is not None and self.http >= SERVER_ERROR


_LATER = (
	"Eine Bearbeitung Ihrer Anfrage ist zurzeit nicht möglich. Bitte versuchen Sie es später noch einmal."
)

STATUSES: MappingProxyType[str, Status] = MappingProxyType(
	{
		status.code: status
		for status in (
			Status(
				"evatr-0000",
				200,
				"Ergebnis",
				None,
				"Die angefragte USt-IdNr. ist zum Anfragezeitpunkt gültig.",
				Outcome.VALID,
			),
			Status(
				"evatr-0001",
				None,
				"Hinweis",
				"datenschutz",
				"Bitte bestätigen Sie den Datenschutzhinweis.",
				Outcome.UNKNOWN,
			),
			Status(
				"evatr-0002",
				400,
				"Hinweis",
				"angefragteUstid",
				"Mindestens eins der Pflichtfelder ist nicht besetzt.",
				Outcome.UNKNOWN,
			),
			Status(
				"evatr-0003",
				400,
				"Hinweis",
				"firmenname,ort",
				"Die angefragte USt-IdNr. ist zum Anfragezeitpunkt gültig. Mindestens eines der Pflichtfelder für "
				"eine qualifizierte Bestätigungsanfrage ist nicht besetzt.",
				Outcome.VALID,
			),
			Status(
				"evatr-0004",
				400,
				"Fehler",
				"anfragendeUstid",
				"Die anfragende DE USt-IdNr. ist syntaktisch falsch. Sie passt nicht in das deutsche "
				"Erzeugungsschema.",
				Outcome.UNKNOWN,
			),
			Status(
				"evatr-0005",
				400,
				"Fehler",
				"angefragteUstid",
				"Die angegebene angefragte USt-IdNr. ist syntaktisch falsch.",
				Outcome.INVALID,
			),
			Status(
				"evatr-0006",
				403,
				"Hinweis",
				"anfragendeUstid",
				"Die anfragende DE USt-IdNr. ist nicht berechtigt eine DE USt-IdNr. anzufragen.",
				Outcome.UNKNOWN,
			),
			Status("evatr-0007", 403, "Hinweis", None, "Fehlerhafter Aufruf.", Outcome.UNKNOWN),
			Status(
				"evatr-0008",
				403,
				"Hinweis",
				None,
				"Die maximale Anzahl von qualifizierten Bestätigungsabfragen für diese Session wurde erreicht. "
				"Bitte starten Sie erneut mit einer einfachen Bestätigungsabfrage.",
				Outcome.UNKNOWN,
			),
			Status("evatr-0011", 503, "Fehler", None, _LATER, Outcome.UNKNOWN),
			Status(
				"evatr-0012",
				400,
				"Fehler",
				"angefragteUstid",
				"Die angefragte USt-IdNr. ist syntaktisch falsch. Sie passt nicht in das Erzeugungsschema.",
				Outcome.INVALID,
			),
			Status("evatr-0013", 503, "Fehler", None, _LATER, Outcome.UNKNOWN),
			Status("evatr-1001", 503, "Fehler", None, _LATER, Outcome.UNKNOWN),
			Status("evatr-1002", 500, "Fehler", None, _LATER, Outcome.UNKNOWN),
			Status("evatr-1003", 500, "Fehler", None, _LATER, Outcome.UNKNOWN),
			Status("evatr-1004", 500, "Fehler", None, _LATER, Outcome.UNKNOWN),
			Status(
				"evatr-2001",
				404,
				"Hinweis",
				"angefragteUstid",
				"Die angefragte USt-IdNr. ist zum Anfragezeitpunkt nicht vergeben.",
				Outcome.INVALID,
			),
			Status(
				"evatr-2002",
				200,
				"Hinweis",
				"angefragteUstid",
				"Die angefragte USt-IdNr. ist zum Anfragezeitpunkt nicht gültig. Sie ist erst gültig ab dem Datum "
				"im Feld gueltigAb.",
				Outcome.INVALID,
			),
			Status(
				"evatr-2003",
				400,
				"Fehler",
				"angefragteUstid",
				"Das angegebene Länderkennzeichen der angefragten USt-IdNr. ist nicht gültig.",
				Outcome.INVALID,
			),
			Status("evatr-2004", 500, "Fehler", None, _LATER, Outcome.UNKNOWN),
			Status(
				"evatr-2005",
				404,
				"Fehler",
				"anfragendeUstid",
				"Die angegebene eigene DE USt-IdNr. ist zum Anfragezeitpunkt nicht gültig.",
				Outcome.UNKNOWN,
			),
			Status(
				"evatr-2006",
				200,
				"Hinweis",
				"angefragteUstid",
				"Die angefragte USt-IdNr. ist zum Anfragezeitpunkt nicht gültig. Sie war gültig im Zeitraum, der "
				"durch die Werte in den Feldern gueltigAb und gueltigBis beschrieben ist.",
				Outcome.INVALID,
			),
			Status(
				"evatr-2007",
				500,
				"Fehler",
				None,
				"Bei der Verarbeitung der Daten aus dem angefragten EU-Mitgliedstaat ist ein Fehler aufgetreten. "
				"Ihre Anfrage kann deshalb nicht bearbeitet werden.",
				Outcome.UNKNOWN,
			),
			Status(
				"evatr-2008",
				200,
				"Hinweis",
				None,
				"Die angefragte USt-IdNr. ist zum Anfragezeitpunkt gültig. Für die qualifizierte "
				"Bestätigungsanfrage liegt einer Besonderheit vor. Für Rückfragen wenden Sie sich an das BZSt.",
				Outcome.VALID,
			),
			Status("evatr-2011", 500, "Fehler", None, _LATER, Outcome.UNKNOWN),
			Status("evatr-3011", 500, "Fehler", None, _LATER, Outcome.UNKNOWN),
		)
	}
)


class _Unreadable(ValueError):
	"""The answer is not a Bestaetigungsantwort; the message says why, in German."""


@dataclass(frozen=True, slots=True)
class _Answer:
	status: str
	time: datetime
	id: str | None
	valid_from: date | None
	valid_until: date | None
	results: dict[str, Match]


def query(
	requested: str, requester: str, details: Details | None, fetch: Fetch, clock: Clock
) -> Confirmation:
	"""One query to the BZSt, the simple one without details and the qualified one with them.

	requested is a plausible USt-IdNr. of another member state and requester the German USt-IdNr. of the
	business that asks, both in any form ustid.normalize reads; anything else is a ValueError before any
	request. Whatever comes back, or does not, becomes the record; nothing is raised for an answer.
	"""
	requested, requester = checked_pair(requested, requester)
	request = Request(URL, HEADERS, _body(requested, requester, details))
	asked = {"requested": requested, "requester": requester, "service": Service.BZST, "details": details}
	requested_at = clock()
	try:
		response = fetch(request)
	except OSError as error:
		return Confirmation(
			**asked,
			outcome=Outcome.UNKNOWN,
			status=NO_ANSWER,
			message=f"Keine Antwort vom BZSt: {str(error) or type(error).__name__}.",
			requested_at=requested_at,
			answered_at=clock(),
			unavailable=True,
		)
	return _record(response, asked, requested_at, clock())


def _body(requested: str, requester: str, details: Details | None) -> bytes:
	fields = {"anfragendeUstid": requester, "angefragteUstid": requested}
	if details is not None:
		qualified = {
			"firmenname": details.name,
			"strasse": details.street,
			"plz": details.postcode,
			"ort": details.city,
		}
		fields |= {name: value for name, value in qualified.items() if value}
	return json.dumps(fields, ensure_ascii=False).encode()


def _record(response: Response, asked: dict, requested_at: datetime, answered_at: datetime) -> Confirmation:
	server_error = response.status >= SERVER_ERROR
	received = {
		**asked,
		"requested_at": requested_at,
		"answered_at": answered_at,
		"http_status": response.status,
		"response_text": response.body.decode(errors="replace"),
	}
	try:
		answer = _answer(response.body)
	except _Unreadable as reason:
		return Confirmation(
			**received,
			outcome=Outcome.UNKNOWN,
			status=UNREADABLE,
			message=f"Die Antwort des BZSt (HTTP {response.status}) ist nicht lesbar: {reason}.",
			unavailable=server_error,
		)
	status = STATUSES.get(answer.status)
	if status is None:
		meaning = {
			"outcome": Outcome.UNKNOWN,
			"message": f"Das BZSt hat mit dem Status {answer.status} geantwortet, den sein Katalog nicht kennt.",
			"unavailable": server_error,
		}
	else:
		meaning = {"outcome": status.outcome, "message": status.message, "unavailable": status.unavailable}
	results = {} if asked["details"] is None else {field: answer.results.get(key) for key, field in RESULTS}
	return Confirmation(
		**received,
		**meaning,
		**results,
		status=answer.status,
		consultation_id=answer.id,
		service_time=answer.time,
		service_date=answer.time.date(),
		valid_from=answer.valid_from,
		valid_until=answer.valid_until,
	)


def _answer(body: bytes) -> _Answer:
	try:
		data = json.loads(body.decode())
	except ValueError:
		raise _Unreadable("kein JSON in UTF-8") from None
	if not isinstance(data, dict):
		raise _Unreadable("kein JSON-Objekt")
	status = _text(data, "status")
	if not status:
		raise _Unreadable("status fehlt")
	time = _text(data, "anfrageZeitpunkt")
	if time is None:
		raise _Unreadable("anfrageZeitpunkt fehlt")
	results = {}
	for key, _ in RESULTS:
		letter = _text(data, key)
		if letter is not None:
			if letter not in _MATCHES:
				raise _Unreadable(f"{key} ist keiner der Buchstaben A bis D: {letter!r}")
			results[key] = _MATCHES[letter]
	return _Answer(
		status=status,
		time=_moment(time, "anfrageZeitpunkt", "Zeitpunkt"),
		id=_text(data, "id"),
		valid_from=_day(_text(data, "gueltigAb"), "gueltigAb"),
		valid_until=_day(_text(data, "gueltigBis"), "gueltigBis"),
		results=results,
	)


def _text(data: dict, key: str) -> str | None:
	value = data.get(key)
	if value is not None and not isinstance(value, str):
		raise _Unreadable(f"{key} ist kein Text")
	return value


def _moment(value: str, key: str, kind: str) -> datetime:
	try:
		return datetime.fromisoformat(value)
	except ValueError:
		raise _Unreadable(f"{key} ist kein {kind}: {value!r}") from None


def _day(value: str | None, key: str) -> date | None:
	return None if value is None else _moment(value, key, "Datum").date()

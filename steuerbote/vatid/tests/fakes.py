"""A fake transport and a fake clock, and answers in the shape the BZSt and VIES send them.

The numbers are the examples of the OpenAPI document of the eVatR API (https://api.evatr.vies.bzst.de/api-docs):
DE123456789 asks about ATU12345678, for the qualified query with the company "Musterhaus GmbH & Co KG",
Musterstrasse 22, 12345 musterort. The shape of an answer with HTTP 400 is that of a probe of the API on
20 November 2026, with another id.
"""

import json
from datetime import UTC, datetime, timedelta
from xml.sax.saxutils import escape

from steuerbote.vatid.result import Details
from steuerbote.vatid.transport import Request, Response

REQUESTER = "DE123456789"
REQUESTED = "ATU12345678"
GERMAN_REQUESTED = "DE111111125"
"""The example of the German USt-IdNr. in the Konstruktionsregeln the Austrian BMF publishes (Stand November 2020),
whose check digit is right."""
DETAILS = Details("Musterhaus GmbH & Co KG", "musterort", "12345", "Musterstrasse 22")
START = datetime(2026, 11, 20, 14, 0, tzinfo=UTC)
BZST_ID = "0a1b2c3d4e5f6071"
BZST_TIME = "2026-11-20T15:00:00.123456789+01:00"
VIES_IDENTIFIER = "WAPIAAAAZ0a1b2c3d"


class FakeFetch:
	"""Answers each request with the next of its answers, or raises it, and keeps the requests."""

	def __init__(self, *answers: Response | OSError) -> None:
		self.answers = list(answers)
		self.requests: list[Request] = []

	def __call__(self, request: Request) -> Response:
		self.requests.append(request)
		answer = self.answers.pop(0)
		if isinstance(answer, OSError):
			raise answer
		return answer

	def urls(self) -> list[str]:
		return [request.url for request in self.requests]


class FakeBzst:
	"""Answers each query with the next of the answers for its number, as the eVatR API would, and keeps the
	queries as JSON; for the confirmations of a document with several numbers."""

	def __init__(self, answers: dict[str, list[Response]]) -> None:
		self.answers = {number: list(queue) for number, queue in answers.items()}
		self.requests: list[dict] = []

	def __call__(self, request: Request) -> Response:
		query = json.loads(request.body)
		self.requests.append(query)
		return self.answers[query["angefragteUstid"]].pop(0)


class FakeClock:
	"""Starts at START and moves on by one second with each reading."""

	def __init__(self) -> None:
		self.now = START

	def __call__(self) -> datetime:
		reading = self.now
		self.now += timedelta(seconds=1)
		return reading


def bzst(status: str, http: int = 200, **fields: object) -> Response:
	"""A Bestaetigungsantwort with id, anfrageZeitpunkt and status, and the given fields."""
	answer = {"id": BZST_ID, "anfrageZeitpunkt": BZST_TIME, "status": status} | fields
	return Response(http, json.dumps(answer).encode())


def vies(valid: bool | str | None = True, http: int = 200, **elements: str | None) -> Response:
	"""A checkVatApproxResponse in its SOAP envelope.

	valid is true or false, or the text of the element; elements replace or add the elements of that name,
	in the order of the WSDL before requestIdentifier. None leaves an element out.
	"""
	fields = {
		"countryCode": REQUESTED[:2],
		"vatNumber": REQUESTED[2:],
		"requestDate": "2026-11-20+01:00",
		"valid": ("true" if valid else "false") if isinstance(valid, bool) else valid,
		"traderName": "---",
		"traderCompanyType": "---",
		"traderAddress": "---",
	} | elements
	fields["requestIdentifier"] = fields.pop("requestIdentifier", VIES_IDENTIFIER)
	children = "".join(
		f"<ns2:{name}>{escape(value)}</ns2:{name}>" for name, value in fields.items() if value is not None
	)
	return _envelope(
		f'<ns2:checkVatApproxResponse xmlns:ns2="urn:ec.europa.eu:taxud:vies:services:checkVat:types">'
		f"{children}</ns2:checkVatApproxResponse>",
		http,
	)


def vies_fault(faultstring: str, http: int = 500) -> Response:
	"""A SOAP 1.1 fault as VIES sends it."""
	return _envelope(
		f"<env:Fault><faultcode>env:Server</faultcode><faultstring>{escape(faultstring)}</faultstring></env:Fault>",
		http,
	)


def _envelope(body: str, http: int) -> Response:
	return Response(
		http,
		(
			'<env:Envelope xmlns:env="http://schemas.xmlsoap.org/soap/envelope/">'
			f"<env:Header/><env:Body>{body}</env:Body></env:Envelope>"
		).encode(),
	)

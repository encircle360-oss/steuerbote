"""The confirmation of a USt-IdNr. over VIES, the service of the European Commission, for when the BZSt
cannot answer.

A query is one call of checkVatApprox over SOAP 1.1 at
https://ec.europa.eu/taxation_customs/vies/services/checkVatService, as the WSDL describes it
(https://ec.europa.eu/taxation_customs/vies/checkVatService.wsdl, retrieved 20 November 2026):
countryCode and vatNumber of the number, traderName, traderStreet, traderPostcode and traderCity for a
qualified query, and requesterCountryCode and requesterVatNumber of the business that asks. The answer
says whether the number is valid, names the requestDate and, for each detail asked about, the match
(1 VALID, 2 INVALID, 3 NOT_PROCESSED), and carries the requestIdentifier that steuerbote keeps as the
consultation number. A failed call is a SOAP fault whose faultstring is one of the values the WSDL
documents; FAULTS maps each of them.

VIES confirms numbers „in accordance to article 31 of Council Regulation (EC) No. 904/2010“, and its
answer „does not in itself give a right to exempt intra-Community supplies from Value Added Tax“ (WSDL,
documentation). The proof UStAE 18e.1 Abs. 2 names is the record of the BZSt, which is why VIES only
answers when the BZSt cannot (service.py).
"""

import re
from dataclasses import dataclass
from datetime import date, datetime
from types import MappingProxyType

from lxml import etree

from steuerbote.vatid.result import NO_ANSWER, UNREADABLE, Confirmation, Details, Match, Outcome, Service
from steuerbote.vatid.transport import SERVER_ERROR, Clock, Fetch, Request, Response
from steuerbote.vatid.ustid import checked_pair

URL = "https://ec.europa.eu/taxation_customs/vies/services/checkVatService"
SOAP = "http://schemas.xmlsoap.org/soap/envelope/"
TYPES = "urn:ec.europa.eu:taxud:vies:services:checkVat:types"
HEADERS = MappingProxyType({"Content-Type": "text/xml; charset=utf-8", "SOAPAction": '""'})
"""SOAP 1.1 over HTTP; the binding of checkVatApprox has the soapAction "" (WSDL)."""
RESULTS = (
	("traderNameMatch", "name_match"),
	("traderStreetMatch", "street_match"),
	("traderPostcodeMatch", "postcode_match"),
	("traderCityMatch", "city_match"),
)
"""The matches of a qualified query and the fields of the record that keep them."""
REQUEST_DATE = re.compile(r"(\d{4}-\d{2}-\d{2})(?:Z|[+-]\d{2}:\d{2})?")
"""An xsd:date, with or without its time zone."""

_MATCHES = MappingProxyType({"1": Match.MATCHES, "2": Match.DIFFERS, "3": Match.NOT_PROVIDED})
_BOOLEANS = MappingProxyType({"true": True, "1": True, "false": False, "0": False})


@dataclass(frozen=True, slots=True)
class Fault:
	code: str
	"""The faultstring as the WSDL documents it."""
	outcome: Outcome
	unavailable: bool
	"""VIES or the member state could not process the query now; the WSDL says to try again later."""
	message: str
	"""The meaning the WSDL gives, in German."""


_FAULTS = (
	Fault(
		"INVALID_INPUT",
		Outcome.INVALID,
		False,
		"Laut VIES ist das Länderkennzeichen ungültig oder die USt-IdNr. leer.",
	),
	Fault(
		"GLOBAL_MAX_CONCURRENT_REQ",
		Outcome.UNKNOWN,
		True,
		"VIES hat die Anfrage nicht bearbeitet, weil die Höchstzahl gleichzeitiger Anfragen erreicht ist. "
		"Bitte später erneut versuchen.",
	),
	Fault(
		"MS_MAX_CONCURRENT_REQ",
		Outcome.UNKNOWN,
		True,
		"VIES hat die Anfrage nicht bearbeitet, weil die Höchstzahl gleichzeitiger Anfragen an diesen "
		"Mitgliedstaat erreicht ist. Bitte später erneut versuchen.",
	),
	Fault(
		"SERVICE_UNAVAILABLE",
		Outcome.UNKNOWN,
		True,
		"Bei VIES ist ein Fehler im Netz oder in der Anwendung aufgetreten. Bitte später erneut versuchen.",
	),
	Fault(
		"MS_UNAVAILABLE",
		Outcome.UNKNOWN,
		True,
		"Der Dienst des Mitgliedstaats antwortet nicht oder ist nicht verfügbar. Bitte später erneut "
		"versuchen.",
	),
	Fault(
		"TIMEOUT",
		Outcome.UNKNOWN,
		True,
		"VIES hat in der vorgesehenen Zeit keine Antwort erhalten. Bitte später erneut versuchen.",
	),
)
FAULTS: MappingProxyType[str, Fault] = MappingProxyType({fault.code: fault for fault in _FAULTS})


class _Unreadable(ValueError):
	"""The answer is neither a checkVatApproxResponse nor a fault; the message says why, in German."""


@dataclass(frozen=True, slots=True)
class _Answer:
	valid: bool
	day: date
	identifier: str
	results: dict[str, Match]


def query(
	requested: str, requester: str, details: Details | None, fetch: Fetch, clock: Clock
) -> Confirmation:
	"""One call of checkVatApprox, with name and address when details are given.

	The numbers are checked as for the BZSt (ustid.checked_pair); whatever comes back, or does not,
	becomes the record.
	"""
	requested, requester = checked_pair(requested, requester)
	request = Request(URL, HEADERS, _body(requested, requester, details))
	asked = {"requested": requested, "requester": requester, "service": Service.VIES, "details": details}
	requested_at = clock()
	try:
		response = fetch(request)
	except OSError as error:
		return Confirmation(
			**asked,
			outcome=Outcome.UNKNOWN,
			status=NO_ANSWER,
			message=f"Keine Antwort von VIES: {str(error) or type(error).__name__}.",
			requested_at=requested_at,
			answered_at=clock(),
			unavailable=True,
		)
	return _record(response, asked, requested_at, clock())


def _body(requested: str, requester: str, details: Details | None) -> bytes:
	envelope = etree.Element(f"{{{SOAP}}}Envelope", nsmap={"soap": SOAP, "v": TYPES})
	check = etree.SubElement(etree.SubElement(envelope, f"{{{SOAP}}}Body"), f"{{{TYPES}}}checkVatApprox")
	elements = [("countryCode", requested[:2]), ("vatNumber", requested[2:])]
	if details is not None:
		elements += [
			("traderName", details.name),
			("traderStreet", details.street),
			("traderPostcode", details.postcode),
			("traderCity", details.city),
		]
	elements += [("requesterCountryCode", requester[:2]), ("requesterVatNumber", requester[2:])]
	for name, text in elements:
		if text:
			etree.SubElement(check, f"{{{TYPES}}}{name}").text = text
	return etree.tostring(envelope, xml_declaration=True, encoding="UTF-8")


def _record(response: Response, asked: dict, requested_at: datetime, answered_at: datetime) -> Confirmation:
	received = {
		**asked,
		"requested_at": requested_at,
		"answered_at": answered_at,
		"http_status": response.status,
		"response_text": response.body.decode(errors="replace"),
	}
	try:
		answer = _answer(_soap_body(response.body))
	except _Unreadable as reason:
		return Confirmation(
			**received,
			outcome=Outcome.UNKNOWN,
			status=UNREADABLE,
			message=f"Die Antwort von VIES (HTTP {response.status}) ist nicht lesbar: {reason}.",
			unavailable=response.status >= SERVER_ERROR,
		)
	if isinstance(answer, str):
		fault = FAULTS.get(answer)
		return Confirmation(
			**received,
			outcome=Outcome.UNKNOWN if fault is None else fault.outcome,
			status=answer,
			message=f"VIES hat mit dem Fehler {answer} geantwortet." if fault is None else fault.message,
			unavailable=fault is not None and fault.unavailable,
		)
	results = {} if asked["details"] is None else {field: answer.results.get(key) for key, field in RESULTS}
	state = "gültig" if answer.valid else "nicht gültig"
	return Confirmation(
		**received,
		**results,
		outcome=Outcome.VALID if answer.valid else Outcome.INVALID,
		status="VALID" if answer.valid else "INVALID",
		message=f"Laut VIES ist die USt-IdNr. zum Zeitpunkt der Anfrage {state}.",
		consultation_id=answer.identifier or None,
		service_date=answer.day,
	)


def _soap_body(body: bytes) -> etree._Element:
	parser = etree.XMLParser(resolve_entities=False, no_network=True, load_dtd=False)
	try:
		root = etree.fromstring(body, parser)
	except etree.XMLSyntaxError:
		raise _Unreadable("kein XML") from None
	# A SOAP 1.1 message must not contain a document type declaration, and entities stay out with it.
	if root.getroottree().docinfo.doctype:
		raise _Unreadable("enthält eine DTD")
	if root.tag != f"{{{SOAP}}}Envelope":
		raise _Unreadable("kein SOAP-Umschlag")
	soap_body = root.find(f"{{{SOAP}}}Body")
	if soap_body is None:
		raise _Unreadable("kein SOAP-Body")
	return soap_body


def _answer(soap_body: etree._Element) -> _Answer | str:
	"""The answer of checkVatApprox, or the faultstring of a fault."""
	fault = soap_body.find(f"{{{SOAP}}}Fault")
	if fault is not None:
		faultstring = (fault.findtext("faultstring") or "").strip()
		if not faultstring:
			raise _Unreadable("Fehler ohne faultstring")
		return faultstring
	answer = soap_body.find(f"{{{TYPES}}}checkVatApproxResponse")
	if answer is None:
		raise _Unreadable("weder Antwort noch Fehler")
	valid = _element(answer, "valid")
	if valid not in _BOOLEANS:
		raise _Unreadable(f"valid ist kein Wahrheitswert: {valid!r}")
	identifier = answer.findtext(f"{{{TYPES}}}requestIdentifier")
	if identifier is None:
		raise _Unreadable("requestIdentifier fehlt")
	results = {}
	for key, _ in RESULTS:
		code = answer.findtext(f"{{{TYPES}}}{key}")
		if code is not None:
			if code not in _MATCHES:
				raise _Unreadable(f"{key} ist keiner der Werte 1 bis 3: {code!r}")
			results[key] = _MATCHES[code]
	return _Answer(
		_BOOLEANS[valid], _request_date(_element(answer, "requestDate")), identifier.strip(), results
	)


def _element(answer: etree._Element, name: str) -> str:
	text = answer.findtext(f"{{{TYPES}}}{name}")
	if text is None:
		raise _Unreadable(f"{name} fehlt")
	return text.strip()


def _request_date(text: str) -> date:
	unreadable = _Unreadable(f"requestDate ist kein Datum: {text!r}")
	match = REQUEST_DATE.fullmatch(text)
	if match is None:
		raise unreadable
	try:
		return date.fromisoformat(match[1])
	except ValueError:
		raise unreadable from None

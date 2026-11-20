"""The VAT ID Confirmation records of a confirmation of steuerbote.vatid. Pure Python, no Frappe.

„In diesen Fällen ist der Nachweis einer durchgeführten qualifizierten Anfrage einer USt-IdNr. über den vom
BZSt empfangenen Datensatz zu führen.“ (UStAE 18e.1 Abs. 2 Satz 5). A confirmation can take two queries, the
simple and the qualified one, or the BZSt and VIES, and each is a record of its own with what was asked and
what came back, the answer itself kept as a file beside it. The answer does not repeat what was asked, so the
record holds both numbers and, for a qualified query, name and address.

result() says what the queries so far say about the number: a qualified query that fails after the simple one
confirmed the number leaves it confirmed, and an answer of VIES after the BZSt could not answer counts. The
times stay aware of their zone; the Frappe layer writes them in the time of the site.
"""

from collections.abc import Sequence
from types import MappingProxyType
from typing import Any

from steuerbote.vatid.result import Confirmation, Outcome, Service

DETAILS_FIELDS = ("details_name", "details_street", "details_postcode", "details_city")
MATCH_FIELDS = ("name_match", "street_match", "postcode_match", "city_match")
TIME_FIELDS = ("requested_at", "answered_at", "service_time")
# The BZSt answers in JSON, VIES in a SOAP envelope.
RESPONSE_EXTENSIONS = MappingProxyType({Service.BZST: "json", Service.VIES: "xml"})


def records(confirmation: Confirmation) -> list[dict[str, Any]]:
	"""A record per query of the confirmation, the first first, each with the result of the queries up to it."""
	queries = confirmation.queries()
	return [
		{**values(query), "result": result(queries[: index + 1]).value} for index, query in enumerate(queries)
	]


def values(query: Confirmation) -> dict[str, Any]:
	"""The fields of the record of one query."""
	details = query.details
	asked = (details.name, details.street, details.postcode, details.city) if details else (None,) * 4
	return {
		"requested": query.requested,
		"requester": query.requester,
		"service": query.service.value,
		"outcome": query.outcome.value,
		"status_code": query.status,
		"message": query.message,
		"consultation_id": query.consultation_id,
		"requested_at": query.requested_at,
		"answered_at": query.answered_at,
		"service_time": query.service_time,
		"service_date": query.service_date,
		"valid_from": query.valid_from,
		"valid_until": query.valid_until,
		"qualified": int(query.qualified),
		**dict(zip(DETAILS_FIELDS, asked, strict=True)),
		**{
			name: match.value if match else None
			for name, match in zip(MATCH_FIELDS, query.matches(), strict=True)
		},
		"http_status": query.http_status,
		"unavailable": int(query.unavailable),
		"fallback_reason": query.fallback_reason,
	}


def result(queries: Sequence[Confirmation]) -> Outcome:
	"""The outcome of the last query that has one, or unknown."""
	return next(
		(query.outcome for query in reversed(queries) if query.outcome is not Outcome.UNKNOWN),
		Outcome.UNKNOWN,
	)


def response_file_name(name: str, query: Confirmation) -> str:
	"""The name of the file that keeps the answer of a query, after its record."""
	return f"{name}-{query.service.value}.{RESPONSE_EXTENSIONS[query.service]}"

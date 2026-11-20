"""Confirm a USt-IdNr.: at the BZSt first, at VIES only when the BZSt cannot answer.

The BZSt is the service § 18e Nr. 1 UStG names, and the record it returns is the proof UStAE 18e.1 Abs. 2
names. So every confirmation begins with the simple query at the BZSt, which the BZSt wants before a
qualified one: „Eine einfache Bestätigung muss zwingend vor einer qualifizierten Bestätigung durchgeführt
werden.“ (BZSt, "Fragen und Antworten" zur USt-IdNr.). With name and address, the qualified query follows
once the BZSt has confirmed the number as valid; for a number it did not confirm there is nothing to
compare.

VIES answers only when the BZSt did not answer the simple query (bzst.query marks the record unavailable):
no response, a server error without a readable status, or a status the catalogue gives with HTTP 500 or
503. A definite answer of the BZSt, valid or invalid, and a request the BZSt refused never go to VIES.
Neither does a qualified query that fails after the BZSt has confirmed the number: the BZSt has then
answered whether the number is valid, and the qualified query can be asked again later.
"""

from dataclasses import replace

from steuerbote.vatid import bzst, vies
from steuerbote.vatid.result import Confirmation, Details, Outcome
from steuerbote.vatid.transport import Clock, Fetch


def confirm(
	requested: str, requester: str, details: Details | None, fetch: Fetch, clock: Clock
) -> Confirmation:
	"""Confirm the USt-IdNr. requested for the business with the German USt-IdNr. requester.

	The record returned is that of the last query, with the earlier ones in previous (Confirmation.queries).
	Its service says who answered, and fallback_reason why VIES did. ValueError, before any request, unless
	requested is a plausible number of another member state and requester a German number.
	"""
	simple = bzst.query(requested, requester, None, fetch, clock)
	if simple.unavailable:
		answer = vies.query(simple.requested, simple.requester, details, fetch, clock)
		reason = f"Das BZSt konnte die Anfrage nicht beantworten ({simple.status}): {simple.message}"
		return replace(answer, fallback_reason=reason, previous=simple)
	if details is None or simple.outcome is not Outcome.VALID:
		return simple
	qualified = bzst.query(simple.requested, simple.requester, details, fetch, clock)
	return replace(qualified, previous=simple)

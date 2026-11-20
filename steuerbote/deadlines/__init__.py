"""The deadlines of a company: the Umsatzsteuer-Voranmeldung, the Zusammenfassende Meldung and the
Sondervorauszahlung, when each is due and whether it is filed.

This package is pure Python. It never imports Frappe, so it can be tested without a bench. The rules of the
deadlines come from the cores (steuerbote.ustva.period, steuerbote.zm and steuerbote.dauerfrist) and the rules of
the VAT Return Settings; obligations.py asks them period by period, and overview.py sets the documents of the
company beside them. The rules and their sources are in docs/fristen.md.
"""

from steuerbote.deadlines.obligations import (
	Kind,
	Obligation,
	first_voranmeldungszeitraum,
	obligations,
	sondervorauszahlungen,
	voranmeldungen,
	zusammenfassende_meldungen,
)
from steuerbote.deadlines.overview import (
	DOCUMENT_TYPES,
	CompanyRules,
	Deadline,
	Filing,
	Status,
	new_document_values,
	upcoming,
)

__all__ = [
	"DOCUMENT_TYPES",
	"CompanyRules",
	"Deadline",
	"Filing",
	"Kind",
	"Obligation",
	"Status",
	"first_voranmeldungszeitraum",
	"new_document_values",
	"obligations",
	"sondervorauszahlungen",
	"upcoming",
	"voranmeldungen",
	"zusammenfassende_meldungen",
]

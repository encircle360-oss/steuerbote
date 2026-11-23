"""The deadlines of a company: the Umsatzsteuer-Voranmeldung, the Zusammenfassende Meldung and the
Sondervorauszahlung, and with Annual Filing Settings the annual filings from the Umsatzsteuererklärung to the
Offenlegung des Jahresabschlusses, when each is due and whether it is filed.

This package is pure Python. It never imports Frappe, so it can be tested without a bench. The rules of the
deadlines come from the cores (steuerbote.ustva.period, steuerbote.zm, steuerbote.dauerfrist, steuerbote.ustjahr and
steuerbote.hgb), the rules of the VAT Return Settings and those of the Annual Filing Settings; obligations.py asks them
period by period, annual.py year by year, and overview.py sets the documents of the company beside them. The rules
and their sources are in docs/fristen.md.
"""

from steuerbote.deadlines import annual
from steuerbote.deadlines.annual import (
	AnnualDocType,
	AnnualDocument,
	AnnualRules,
	AnnualYear,
	Note,
	OpeningBalance,
	annual_due,
	annual_obligations,
)
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
	annual_filings,
	new_document_values,
	upcoming,
)

__all__ = [
	"DOCUMENT_TYPES",
	"AnnualDocType",
	"AnnualDocument",
	"AnnualRules",
	"AnnualYear",
	"CompanyRules",
	"Deadline",
	"Filing",
	"Kind",
	"Note",
	"Obligation",
	"OpeningBalance",
	"Status",
	"annual",
	"annual_due",
	"annual_filings",
	"annual_obligations",
	"first_voranmeldungszeitraum",
	"new_document_values",
	"obligations",
	"sondervorauszahlungen",
	"upcoming",
	"voranmeldungen",
	"zusammenfassende_meldungen",
]

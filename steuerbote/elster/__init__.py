"""ELSTER: the data of a company in the form the electronic filing takes it.

This package is pure Python. It never imports Frappe, so it can be tested without a bench.
"""

from steuerbote.elster.steuernummer import (
	SCHEMES,
	STATE_CODES,
	STATES,
	Scheme,
	SteuernummerError,
	ZeroSteuernummerError,
	from_elster,
	to_elster,
	validate,
)

__all__ = [
	"SCHEMES",
	"STATES",
	"STATE_CODES",
	"Scheme",
	"SteuernummerError",
	"ZeroSteuernummerError",
	"from_elster",
	"to_elster",
	"validate",
]

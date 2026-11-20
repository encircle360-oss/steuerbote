"""Dauerfristverlängerung and Sondervorauszahlung (form USt 1 H, §§ 46 to 48 UStDV).

This package is pure Python. It never imports Frappe, so it can be tested without a bench. The rules and their
sources are in docs/dauerfristverlaengerung.md.
"""

from steuerbote.dauerfrist.calculation import (
	expected_sondervorauszahlung,
	months_of_activity,
	previous_year_base,
	sondervorauszahlung,
)
from steuerbote.dauerfrist.form import (
	LATEST_YEAR,
	LAYOUTS,
	Context,
	Field,
	Format,
	FormError,
	Layout,
	Rule,
	Severity,
	Ust1H,
	layout_for,
)

__all__ = [
	"LATEST_YEAR",
	"LAYOUTS",
	"Context",
	"Field",
	"FormError",
	"Format",
	"Layout",
	"Rule",
	"Severity",
	"Ust1H",
	"expected_sondervorauszahlung",
	"layout_for",
	"months_of_activity",
	"previous_year_base",
	"sondervorauszahlung",
]

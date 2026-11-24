"""When a mapping takes over the defaults of today.

A mapping keeps the version of the defaults it took over last and the rows they gave (defaults_version and
defaults_rows of the VAT Return Mapping, the Income Tax Mapping and the Balance Sheet Mapping): the base of
steuerbote.mappings.diff. Against the base, a row that still reads as the defaults gave it differs from the defaults of
today only because they moved, and Vorgaben aktualisieren proposes the change; a row that differs from the base is the
user's own. Noting the defaults of today makes them the base, so from then on every difference left counts as the
user's own and is no longer proposed.

waits_for_defaults() tells the mapping that Steuerbote einrichten loads the defaults of today into, as into a new one,
and notes_defaults() whether Vorgaben aktualisieren notes them: once it takes over a difference, or when the user
declined them all.

This module is pure Python and never imports Frappe.
"""

from collections.abc import Iterable, Sized


def waits_for_defaults(tables: Iterable[Sized], taken_over: str | None, today: str | None) -> bool:
	"""Whether a mapping waits for the defaults of today: its chart has defaults, whose version of today is ``today``
	(None for a chart without defaults), it holds no row in any of its tables, and the defaults it took over
	(``taken_over``) are others or none, as for a mapping made while the defaults of its chart were still empty.

	A mapping without rows that took over the defaults of today stays as it is: they are its base, so every row of
	them it lacks is one the user removed or one of an account the company does not have."""
	return today is not None and taken_over != today and not any(tables)


def notes_defaults(taken: int, acknowledged: bool) -> bool:
	"""Whether Vorgaben aktualisieren notes the defaults of today as taken over after taking over ``taken`` differences:
	once it takes over one, or when the user acknowledged the differences and declined them, as the dialog of the form
	does for a choice of none. Without either, the mapping and its base stay as they are, and the differences stay
	proposed."""
	return taken > 0 or bool(acknowledged)

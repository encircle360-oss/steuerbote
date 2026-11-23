"""The Umsatzerlöse of the year against the sales of the Umsatzsteuererklärung, without Frappe: the hint of the return
when the Umsatzerlöse of the festgestellter Jahresabschluss, or else of the filed E-Bilanz, are not the
Bemessungsgrundlagen of the Lieferungen und sonstigen Leistungen it files.

Why. The Umsatzerlöse are „die Erlöse aus dem Verkauf und der Vermietung oder Verpachtung von Produkten sowie aus der
Erbringung von Dienstleistungen der Kapitalgesellschaft nach Abzug von Erlösschmälerungen und der Umsatzsteuer“
(§ 277 Abs. 1 HGB), and „Der Umsatz wird bei Lieferungen und sonstigen Leistungen [...] nach dem Entgelt bemessen“
(§ 10 Abs. 1 Satz 1 UStG): both count the same sales of the year without the tax. They need not agree, as a sale of
fixed assets is a Lieferung but no Umsatzerlös, an Anzahlung is taxed on receipt (§ 13 Abs. 1 Nr. 1 Buchstabe a Satz 4
UStG) and an Erlös without a line of the return is no Umsatz of it; whether a difference is explained, the company
decides. So the difference is a hint and never holds the return.

What. The sales of the return are the fields of form USt 2 A that take the Kennzahlen of the Voranmeldung holding the
Bemessungsgrundlagen of Lieferungen und sonstigen Leistungen (SALES): the taxable sales of lines 24, 27, 30 and 33 to
35, the steuerfreie of lines 42 to 49 and 51 to 54, the Lieferungen des ersten Abnehmers of line 65 and the sales of
lines 76, 78, 80 and 81, whose tax another owes or that are not taxable in Germany (steuerbote/ustjahr/form.py). The
unentgeltliche Wertabgaben of § 3 Abs. 1b and 9a UStG (lines 25, 26, 28, 29, 31 and 32) are left out: they earn no
Erlös, and the DATEV charts place their accounts among the sonstige betriebliche Erträge (SKR04 4600 to 4686,
steuerbote/ebilanz/defaults.py). The return files each of its lines in whole euros with the cents dropped
(steuerbote/ustva/rounding.py), so up to a euro a line is rounding; beyond it and the tolerance the hint names both
figures, the lines and the difference.

This module is pure Python and never imports Frappe.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal
from enum import Enum

from steuerbote.ustjahr.form import Catalogue, Field, Finding, Severity
from steuerbote.ustva.rounding import ZERO, to_cents

CODE = "SB-UMSATZERLOESE"
SALES = ("81", "86", "87", "35", "77", "76", "41", "44", "49", "43", "48", "42", "60", "21", "45")
"""The Kennzahlen of the Voranmeldung that hold the Bemessungsgrundlagen of Lieferungen und sonstigen Leistungen of
the company (Vordruck USt 1 A 2026, BMF letter of 29 December 2025, GZ III C 3 - S 7344/00039/007/036): Kz 81, 86, 87
and 35 the taxable sales at 19, 7 and 0 % and at other rates, Kz 77 and 76 those of § 24 UStG, Kz 41, 44 and 49 the
innergemeinschaftliche Lieferungen, Kz 43 and 48 the other steuerfreie sales with and without Vorsteuerabzug, Kz 42
the Lieferungen des ersten Abnehmers in a Dreiecksgeschäft, Kz 60 the sales whose tax the recipient owes under § 13b
Abs. 5 UStG, Kz 21 the sonstige Leistungen of § 18b Satz 1 Nr. 2 UStG and Kz 45 the other sales not taxable in
Germany."""
WERTABGABEN = "Unent_Wertabgaben"
"""The context of the unentgeltlichen Wertabgaben below USt2A (JD sheet „USt2A - Kontexte“)."""
ONE_EURO = Decimal("1")


class Source(Enum):
	"""Where the Umsatzerlöse come from: the festgestellter Jahresabschluss, or else the filed E-Bilanz."""

	ACCOUNTS = "accounts"
	EBILANZ = "ebilanz"


FROM_ACCOUNTS = (
	"The Umsatzerlöse of the festgestellter Jahresabschluss {0} are {1} euros, the Bemessungsgrundlagen of the "
	"Lieferungen und sonstigen Leistungen of the return {2} euros (lines {3}): a difference of {4} euros, more than a "
	"euro a line and the tolerance of {5} euros. Sales of fixed assets, Anzahlungen and Erlöse that no line of the "
	"return takes explain such a difference; check it."
)
FROM_EBILANZ = (
	"The Umsatzerlöse of the filed E-Bilanz {0} are {1} euros, the Bemessungsgrundlagen of the Lieferungen und sonstigen "
	"Leistungen of the return {2} euros (lines {3}): a difference of {4} euros, more than a euro a line and the "
	"tolerance of {5} euros. Sales of fixed assets, Anzahlungen and Erlöse that no line of the return takes explain "
	"such a difference; check it."
)
NONE_FROM_ACCOUNTS = (
	"The Umsatzerlöse of the festgestellter Jahresabschluss {0} are {1} euros, but the return files no "
	"Bemessungsgrundlage of Lieferungen und sonstigen Leistungen. Check that the VAT Return Mapping takes the accounts "
	"of the sales."
)
NONE_FROM_EBILANZ = (
	"The Umsatzerlöse of the filed E-Bilanz {0} are {1} euros, but the return files no Bemessungsgrundlage of "
	"Lieferungen und sonstigen Leistungen. Check that the VAT Return Mapping takes the accounts of the sales."
)
TEMPLATES = {
	(True, Source.ACCOUNTS): FROM_ACCOUNTS,
	(True, Source.EBILANZ): FROM_EBILANZ,
	(False, Source.ACCOUNTS): NONE_FROM_ACCOUNTS,
	(False, Source.EBILANZ): NONE_FROM_EBILANZ,
}
"""The hint by whether the return files any of the sales and by the source of the Umsatzerlöse."""
MESSAGES = tuple(TEMPLATES.values())


@dataclass(frozen=True, slots=True)
class Revenue:
	"""The Umsatzerlöse of the year in euros and cents, with the document they come from."""

	amount: Decimal
	source: Source
	name: str


def sales_fields(catalogue: Catalogue) -> tuple[Field, ...]:
	"""The fields of the return that hold the Bemessungsgrundlagen of its Lieferungen und sonstigen Leistungen, in the
	order of the form; see the module docstring."""
	return tuple(
		field
		for field in catalogue.fields
		if field.ustva in SALES and field.fed and WERTABGABEN not in field.context.split("/")
	)


def findings(
	catalogue: Catalogue, amounts: Mapping[str, Decimal], revenue: Revenue | None, tolerance: Decimal
) -> tuple[Finding, ...]:
	"""The hint of the comparison, none where the return and the Umsatzerlöse agree but for the rounding of the lines
	and the tolerance, or where the year has no Umsatzerlöse to compare with. ``amounts`` are what the lines of the
	return file, by Feldkennung."""
	if revenue is None:
		return ()
	fields = tuple(field for field in sales_fields(catalogue) if amounts.get(field.element))
	sales = sum((field.sign * amounts[field.element] for field in fields), ZERO)
	difference = revenue.amount - sales
	if abs(difference) <= tolerance + ONE_EURO * len(fields):
		return ()
	template = TEMPLATES[(bool(fields), revenue.source)]
	lines = ", ".join(str(line) for line in dict.fromkeys(field.line for field in fields))
	values = (
		revenue.name,
		_euros(revenue.amount),
		_euros(sales),
		lines,
		_euros(difference),
		_euros(tolerance),
	)
	return (Finding(CODE, Severity.HINT, template, values, tuple(field.element for field in fields)),)


def _euros(amount: Decimal) -> str:
	return format(to_cents(amount), "f")

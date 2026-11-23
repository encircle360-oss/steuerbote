"""Which DATEV chart a company books in: SKR03, SKR04 or neither, for the defaults of its VAT Return Mapping.

Two things tell, in this order:

- The template of the chart of accounts the company was set up with (Company.chart_of_accounts). ERPNext 16 ships
  „SKR03 mit Kontonummern“ and „SKR04 mit Kontonummern“ (de_kontenplan_SKR03.json and de_kontenplan_SKR04.json
  under erpnext/accounts/doctype/account/chart_of_accounts/verified); a template that names exactly one of the two
  charts decides. A company whose chart was copied from another company takes the template of that one; the Frappe
  layer follows the copy.
- Otherwise the account numbers. Both charts number the three accounts every company with Umsatzsteuer books on
  differently: Erlöse 19 % USt, Umsatzsteuer 19 % and Abziehbare Vorsteuer 19 % are 8400, 1776 and 1576 in SKR03
  and 4400, 3806 and 1406 in SKR04 (the roles revenue_19, output_tax_19 and input_tax_19 of defaults.py, after the
  DATEV editions „Gültig für 2026“, and the same numbers in the templates of ERPNext). A company with all three of
  one chart and not all three of the other books in that chart.

A company that has all three of both, or a template that names both, is ambiguous; one with neither books in a chart
of its own. Neither gets defaults, and the setup says why. This module is pure Python and never imports Frappe.
"""

import re
from collections.abc import Collection
from dataclasses import dataclass
from enum import Enum
from types import MappingProxyType

from steuerbote.ustva.defaults import SKR03_ACCOUNTS, SKR04_ACCOUNTS

SKR03 = "SKR03"
SKR04 = "SKR04"
SIGNATURE_ROLES = ("revenue_19", "output_tax_19", "input_tax_19")
SIGNATURES = MappingProxyType(
	{
		SKR03: frozenset(SKR03_ACCOUNTS[role] for role in SIGNATURE_ROLES),
		SKR04: frozenset(SKR04_ACCOUNTS[role] for role in SIGNATURE_ROLES),
	}
)
# „SKR03“, „SKR 04“ or „skr3“ in the name of a template.
_TEMPLATE_CHART = re.compile(r"\bSKR\s*0?([34])\b", re.IGNORECASE)


class Basis(Enum):
	"""What the detection rests on."""

	TEMPLATE = "template"
	ACCOUNTS = "accounts"
	AMBIGUOUS = "ambiguous"
	NONE = "none"


@dataclass(frozen=True, slots=True)
class Detection:
	"""The chart a company books in, None for a chart of its own or an ambiguous one, and why."""

	chart: str | None
	basis: Basis


def detect(template: str | None, account_numbers: Collection[str]) -> Detection:
	"""The chart of a company from the name of its template and the numbers of its accounts."""
	named = sorted({f"SKR0{digit}" for digit in _TEMPLATE_CHART.findall(template or "")})
	if len(named) == 1:
		return Detection(named[0], Basis.TEMPLATE)
	if named:
		return Detection(None, Basis.AMBIGUOUS)
	numbers = frozenset(account_numbers)
	matching = [chart for chart, signature in SIGNATURES.items() if signature <= numbers]
	if len(matching) == 1:
		return Detection(matching[0], Basis.ACCOUNTS)
	return Detection(None, Basis.AMBIGUOUS if matching else Basis.NONE)

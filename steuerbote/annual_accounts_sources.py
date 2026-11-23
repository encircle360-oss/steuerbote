"""What the Jahresabschluss reads from ERPNext for its core in steuerbote/hgb.

- The books of the fiscal year and of the year before (steuerbote/balances.py, fiscal_year_books) in the Finanzbuch der
  Handelsbilanz of the Annual Filing Settings, with the closing account of the settings, to which the result of earlier
  years goes where no Period Closing Voucher closed it.
- The Balance Sheet Mapping of the company puts them on the positions of the Handelsbilanz (Purpose.COMMERCIAL) against
  the fiscal view of the installed HGB-Taxonomie (Balance Sheet Mapping.place), and steuerbote/balance_mapping_sync.py
  makes the placed balances the Balance rows of steuerbote/hgb/statement.py; the findings of the placement (BILANZ-…)
  become rows of the table Befunde, those of the year before marked „Vorjahr“.
- The hierarchy the statement sums the balances up along: the calculation of the Bilanz and of the GuV in the
  commercial view of the same taxonomy (Taxonomy.parents), „Einzelabschluss“, whose positions the schemes of
  steuerbote/hgb/schemes.py name.
- The Annual Filing Settings of the company and its name and founding.
"""

from dataclasses import dataclass
from datetime import date

import frappe
from frappe import _
from frappe.utils import escape_html, getdate

from steuerbote import balances
from steuerbote.balance_mapping_sync import statement_balances
from steuerbote.dauerfrist_sources import date_of_establishment
from steuerbote.hgb.statement import Balance
from steuerbote.jahresmeldung.findings import Finding
from steuerbote.steuerbote.doctype.annual_accounts import bridge
from steuerbote.steuerbote.doctype.annual_filing_settings.annual_filing_settings import (
	AnnualFilingSettings,
	settings_of,
)
from steuerbote.steuerbote.doctype.eric_settings import eric_settings
from steuerbote.xbrl.mapping import Purpose
from steuerbote.xbrl.taxonomy import BALANCE_SHEET, INCOME_STATEMENT, View

MAPPING = "Balance Sheet Mapping"


@dataclass(frozen=True)
class Sources:
	"""The balances of the fiscal year and of the year before, None without one, its days, the hierarchy of the
	taxonomy, the findings of the placement, the chart of the mapping and the number of the closing account."""

	balances: tuple[Balance, ...]
	prior: tuple[Balance, ...] | None
	prior_dates: tuple[date, date] | None
	parents: dict[str, str]
	findings: tuple[Finding, ...]
	chart: str
	closing_account: str | None


def settings(company: str) -> AnnualFilingSettings:
	"""The Annual Filing Settings of the company, which the Jahresabschluss needs for its register data, its
	Geschäftsführer and its size."""
	found = settings_of(company)
	if found is None:
		frappe.throw(
			_("Enter the Annual Filing Settings of {0} first.").format(escape_html(company)),
			title=_("Annual Filing Settings"),
		)
	return found


def mapping(company: str):
	"""The Balance Sheet Mapping of the company."""
	if not frappe.db.exists(MAPPING, company):
		frappe.throw(
			_(
				"{0} has no Balance Sheet Mapping. Make it with Steuerbote einrichten or by hand before calculating the Jahresabschluss."
			).format(escape_html(company))
		)
	return frappe.get_doc(MAPPING, company)


def statement_sources(company: str, fiscal_year: str) -> Sources:
	"""The books of the Fiscal Year and of the one before it on the positions of the Handelsbilanz."""
	found_settings = settings(company)
	found_mapping = mapping(company)
	closing = balances.closing_account(company)
	closing_name, closing_number = closing if closing else (None, None)
	books = balances.fiscal_year_books(
		company,
		fiscal_year,
		finance_book=found_settings.commercial_finance_book or None,
		closing_account=closing_name,
	)
	placement = found_mapping.place(
		books.current,
		Purpose.COMMERCIAL,
		closing_account=closing_number or None,
		fiscal_year=(books.from_date, books.to_date),
	)
	findings = list(bridge.annual_findings(placement.findings))
	prior, prior_dates = None, None
	if books.prior is not None:
		prior_dates = (books.prior_from_date, books.prior_to_date)
		prior_placement = found_mapping.place(
			books.prior,
			Purpose.COMMERCIAL,
			closing_account=closing_number or None,
			fiscal_year=prior_dates,
		)
		prior = statement_balances(prior_placement)
		findings.extend(bridge.annual_findings(prior_placement.findings, prior_year=True))
	view = eric_settings.taxonomy_view(found_mapping.taxonomy_version, View.COMMERCIAL)
	return Sources(
		statement_balances(placement),
		prior,
		prior_dates,
		view.parents((BALANCE_SHEET, INCOME_STATEMENT)),
		tuple(findings),
		found_mapping.chart,
		closing_number or None,
	)


def company_name(company: str) -> str:
	return frappe.db.get_value("Company", company, "company_name") or company


def founded_in(company: str, from_date: date | str, to_date: date | str) -> bool:
	"""Whether the company was founded within the fiscal year, the first after its Neugründung (§ 267 Abs. 4
	Satz 2 HGB)."""
	founded = date_of_establishment(company)
	return founded is not None and getdate(from_date) <= founded <= getdate(to_date)


def founded_on(company: str) -> date | None:
	return date_of_establishment(company)

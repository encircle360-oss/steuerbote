"""The Kontenzuordnung of a company: which account feeds which Kennzahl, what is checked and what is watched.

steuerbote.mapping_sync turns the rows into the core Mapping; this controller only reads and fills them.
"""

import frappe
from frappe import _
from frappe.model.document import Document

from steuerbote.mapping_sync import defaults_for_accounts, rows_to_mapping
from steuerbote.ustva import DEFAULTS, LATEST_YEAR, Mapping, MappingError, UnknownYearError


class VATReturnMapping(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		from steuerbote.steuerbote.doctype.vat_return_mapping_check.vat_return_mapping_check import (
			VATReturnMappingCheck,
		)
		from steuerbote.steuerbote.doctype.vat_return_mapping_rule.vat_return_mapping_rule import (
			VATReturnMappingRule,
		)
		from steuerbote.steuerbote.doctype.vat_return_watched_account.vat_return_watched_account import (
			VATReturnWatchedAccount,
		)

		chart: DF.Literal["SKR03", "SKR04", "Eigener Kontenrahmen"]
		checks: DF.Table[VATReturnMappingCheck]
		company: DF.Link
		rules: DF.Table[VATReturnMappingRule]
		watched: DF.Table[VATReturnWatchedAccount]
	# end: auto-generated types

	def validate(self):
		self.validate_accounts()
		self.to_mapping(LATEST_YEAR)

	def validate_accounts(self):
		"""The form offers only ledger accounts of the company; rows that arrive another way are checked here."""
		names = sorted({row.account for row in (*self.rules, *self.watched) if row.account})
		if not names:
			return
		for account in frappe.get_all(
			"Account", filters={"name": ["in", names]}, fields=["name", "company", "is_group"]
		):
			if account.company != self.company:
				frappe.throw(
					_("Account {0} does not belong to company {1}.").format(
						frappe.bold(account.name), frappe.bold(self.company)
					)
				)
			if account.is_group:
				frappe.throw(
					_("Account {0} is a group and takes no postings.").format(frappe.bold(account.name))
				)

	def to_mapping(self, year: int) -> Mapping:
		"""The core Mapping of the rows, validated against the form of ``year``."""
		try:
			return rows_to_mapping(
				self.chart,
				[row.as_dict() for row in self.rules],
				[row.as_dict() for row in self.checks],
				[row.as_dict() for row in self.watched],
				year,
			)
		except (MappingError, UnknownYearError) as error:
			frappe.throw(str(error), title=_("Invalid VAT Return Mapping"))

	@frappe.whitelist(methods=["POST"])
	def load_defaults(self) -> list[str]:
		"""Replace the rows by the defaults of the chart, reduced to the ledger accounts of the company.

		A watched account keeps the level its row had. Returns the accounts of the defaults that the company
		does not have, for the message of the form.
		"""
		if not self.company:
			frappe.throw(_("Select the company first."))
		if self.chart not in DEFAULTS:
			frappe.throw(_("There are no defaults for {0}.").format(self.chart))
		names = {
			account.account_number: account.name
			for account in frappe.get_all(
				"Account",
				filters={"company": self.company, "is_group": 0, "account_number": ["!=", ""]},
				fields=["name", "account_number"],
			)
		}
		levels = {row.account_number: row.level for row in self.watched if row.account_number}
		defaults = defaults_for_accounts(self.chart, LATEST_YEAR, names.keys(), levels)
		self.set("rules", [{"account": names[row["account_number"]], **row} for row in defaults.rule_rows])
		self.set("checks", defaults.check_rows)
		self.set(
			"watched", [{"account": names[row["account_number"]], **row} for row in defaults.watched_rows]
		)
		return defaults.missing

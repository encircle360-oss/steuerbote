"""The Bilanzzuordnung of a company: which position of the HGB-Taxonomie each account of its books goes to
(steuerbote.xbrl.mapping)."""

from frappe.model.document import Document


class BalanceSheetMapping(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		from steuerbote.steuerbote.doctype.balance_sheet_mapping_excluded_account.balance_sheet_mapping_excluded_account import (
			BalanceSheetMappingExcludedAccount,
		)
		from steuerbote.steuerbote.doctype.balance_sheet_mapping_rule.balance_sheet_mapping_rule import (
			BalanceSheetMappingRule,
		)
		from steuerbote.steuerbote.doctype.balance_sheet_mapping_watched_account.balance_sheet_mapping_watched_account import (
			BalanceSheetMappingWatchedAccount,
		)

		chart: DF.Literal["SKR03", "SKR04", "Eigener Kontenrahmen"]
		company: DF.Link
		defaults_rows: DF.LongText | None
		defaults_version: DF.Data | None
		excluded: DF.Table[BalanceSheetMappingExcludedAccount]
		rules: DF.Table[BalanceSheetMappingRule]
		taxonomy_version: DF.Literal["6.9"]
		watched: DF.Table[BalanceSheetMappingWatchedAccount]
	# end: auto-generated types

	pass

"""The Kontenzuordnung of a company: which account feeds which Kennzahl, what is checked and what is watched.

steuerbote.mapping_sync turns the rows into the core Mapping; this controller only reads and fills them. „Steuervorlagen
prüfen“ (check_tax_templates) lists the accounts of the company's tax templates that have no place in the mapping
(steuerbote.ustva.tax_templates), and watch_template_accounts watches them at the level Sperrt.

„Vorgaben laden“ (load_defaults) replaces the rows by the defaults of the chart and keeps, besides the version of
those defaults (defaults_version), the rows they gave (defaults_rows). „Vorgaben aktualisieren“ compares the rows
with the defaults of today and with those kept (compare_with_defaults, steuerbote.mappings.diff), so that it can tell
a change of the defaults from a change the user made, and takes over the differences chosen (update_from_defaults).
"""

from collections.abc import Collection, Iterator
from contextlib import contextmanager

import frappe
from frappe import _
from frappe.model.document import Document

from steuerbote.mapping_sync import (
	ACCOUNT,
	CHECK,
	WATCHED,
	default_items,
	defaults_for_accounts,
	dump_items,
	items_of_rows,
	load_items,
	rows_of_items,
	rows_to_mapping,
)
from steuerbote.mappings import diff
from steuerbote.tax_templates import template_accounts
from steuerbote.ustva import DEFAULTS, LATEST_YEAR, Mapping, MappingError, UnknownYearError, WatchLevel
from steuerbote.ustva.defaults import defaults_version, deliberately_without_kennzahl
from steuerbote.ustva.tax_templates import TemplateAccount, without_place

CHANGES = {
	diff.Change.ADDED: "Will Be Added",
	diff.Change.REMOVED: "Will Be Removed",
	diff.Change.CHANGED: "Will Change",
}
ORIGINS = {
	diff.Origin.DEFAULTS: "The defaults changed",
	diff.Origin.OWN: "Your own change",
	diff.Origin.UNKNOWN: "Origin unknown",
}
FIELD_LABELS = {
	"place": "Place in the Mapping",
	"kennzahl": "Kennzahl",
	"side": "Balance Side",
	"tax_rate": "Tax Rate (%)",
	"also_kennzahl": "Additional Kennzahl",
	"also_side": "Side for Additional Kennzahl",
	"level": "Watch Level",
	"base_accounts": "Base Accounts",
	"tax_accounts": "Tax Accounts",
}


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
		defaults_rows: DF.LongText | None
		defaults_version: DF.Data | None
		rules: DF.Table[VATReturnMappingRule]
		watched: DF.Table[VATReturnWatchedAccount]
	# end: auto-generated types

	def validate(self):
		self.validate_accounts()
		self.current_items()
		self.to_mapping(LATEST_YEAR)
		self.defaults_taken_over()

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

	def current_items(self) -> dict[diff.Key, dict]:
		"""The rows as items of steuerbote.mappings.diff; an account or a label in two rows is refused."""
		with mapping_errors():
			return items_of_rows(
				[row.as_dict() for row in self.rules],
				[row.as_dict() for row in self.checks],
				[row.as_dict() for row in self.watched],
			)

	def defaults_taken_over(self) -> dict[diff.Key, dict] | None:
		"""The rows the defaults gave when Vorgaben laden or Vorgaben aktualisieren took them over last, as items;
		None for a mapping that never took them over, or did so before Steuerbote kept them."""
		if not self.defaults_rows:
			return None
		with mapping_errors():
			return load_items(self.defaults_rows)

	@frappe.whitelist(methods=["POST"])
	def load_defaults(self) -> list[str]:
		"""Replace the rows by the defaults of the chart, reduced to the ledger accounts of the company, and note
		the version of the defaults and the rows they gave.

		A watched account keeps the level its row had; the rows kept as taken over hold the level of the
		defaults, so that Vorgaben aktualisieren sees the level kept as the user's own. Returns the accounts of the
		defaults that the company does not have, for the message of the form.
		"""
		self._require_defaults()
		names = self._account_names()
		levels = {row.account_number: row.level for row in self.watched if row.account_number}
		defaults = defaults_for_accounts(self.chart, LATEST_YEAR, names.keys(), levels)
		self.set("rules", [{"account": names[row["account_number"]], **row} for row in defaults.rule_rows])
		self.set("checks", defaults.check_rows)
		self.set(
			"watched", [{"account": names[row["account_number"]], **row} for row in defaults.watched_rows]
		)
		self._note_defaults(names.keys())
		return defaults.missing

	@frappe.whitelist(methods=["POST"])
	def compare_with_defaults(self) -> dict:
		"""Vorgaben aktualisieren: each difference between the rows and the defaults of today, with whether it comes
		from the defaults, which the form proposes to take over, or from the user."""
		self._require_defaults()
		base = self.defaults_taken_over()
		comparison = diff.compare(self.current_items(), self._defaults_now(), base)
		return {
			"version": defaults_version(self.chart),
			"taken_over": self.defaults_version or "",
			"base_known": base is not None,
			"differences": [presented(difference) for difference in comparison.differences],
			"unchanged": len(comparison.unchanged),
		}

	@frappe.whitelist(methods=["POST"])
	def update_from_defaults(self, chosen: list[str] | None = None) -> int:
		"""Take over the chosen differences of compare_with_defaults, by their id, keep every other row, note the
		defaults of today as taken over, and save. Returns how many differences it took over."""
		self._require_defaults()
		current, proposed = self.current_items(), self._defaults_now()
		keys = chosen_keys(diff.compare(current, proposed, self.defaults_taken_over()), chosen or [])
		self._set_items(diff.apply(current, proposed, keys))
		self._note_defaults(self._account_names().keys())
		self.save()
		return len(keys)

	def _require_defaults(self) -> None:
		if not self.company:
			frappe.throw(_("Select the company first."))
		if self.chart not in DEFAULTS:
			frappe.throw(_("There are no defaults for {0}.").format(self.chart))

	def _account_names(self) -> dict[str, str]:
		"""The ledger accounts of the company with a number, the name of each by its number."""
		return {
			account.account_number: account.name
			for account in frappe.get_all(
				"Account",
				filters={"company": self.company, "is_group": 0, "account_number": ["!=", ""]},
				fields=["name", "account_number"],
			)
		}

	def _defaults_now(self) -> dict[diff.Key, dict]:
		return default_items(self.chart, LATEST_YEAR, self._account_names().keys())

	def _note_defaults(self, numbers: Collection[str]) -> None:
		self.defaults_version = defaults_version(self.chart)
		self.defaults_rows = dump_items(default_items(self.chart, LATEST_YEAR, numbers))

	def _set_items(self, items: dict[diff.Key, dict]) -> None:
		"""Write the items into the rows, each account by the name of the account of the company with its number."""
		names = self._account_names()
		rows = rows_of_items(items)
		self.set("rules", [{"account": names.get(row["account_number"]), **row} for row in rows.rule_rows])
		self.set("checks", rows.check_rows)
		self.set(
			"watched", [{"account": names.get(row["account_number"]), **row} for row in rows.watched_rows]
		)

	@frappe.whitelist(methods=["POST"])
	def check_tax_templates(self) -> list[dict]:
		"""Steuervorlagen prüfen: the accounts the tax templates of the company name that the mapping, as the form
		holds it, gives no place, each with its number, its name and its templates."""
		return [
			{
				"account": account.account,
				"account_number": account.account_number or "",
				"account_name": account.account_name,
				"templates": list(account.templates),
			}
			for account in self._template_accounts_without_place()
		]

	@frappe.whitelist(methods=["POST"])
	def watch_template_accounts(self) -> list[str]:
		"""Watch every account of check_tax_templates that has an account number at the level Sperrt, then save.

		Returns the accounts it adds. An account without number can have no row, since every row of the mapping
		names its account by number.
		"""
		added = [account for account in self._template_accounts_without_place() if account.account_number]
		if not added:
			frappe.throw(
				_("No account of the tax templates with an account number lacks a place in the mapping.")
			)
		for account in added:
			self.append(
				"watched",
				{
					"account": account.account,
					"account_number": account.account_number,
					"level": WatchLevel.BLOCKING.value,
				},
			)
		self.save()
		return [account.account for account in added]

	def _template_accounts_without_place(self) -> tuple[TemplateAccount, ...]:
		if not self.company:
			frappe.throw(_("Select the company first."))
		return without_place(
			template_accounts(self.company),
			self.to_mapping(LATEST_YEAR),
			deliberately_without_kennzahl(self.chart),
		)


def chosen_keys(comparison: diff.Comparison, chosen: Collection[str]) -> set[diff.Key]:
	"""The keys of the differences the form chose by their id; an id that names no difference changes nothing."""
	ids = set(chosen)
	return {difference.key for difference in comparison.differences if difference_id(difference) in ids}


def difference_id(difference: diff.Difference) -> str:
	kind, key = difference.key
	return f"{kind}:{key}"


def presented(difference: diff.Difference) -> dict:
	"""A difference as the dialog of the form shows it, in the language of the user."""
	kind, key = difference.key
	return {
		"id": difference_id(difference),
		"subject": (_("Account {0}") if kind == ACCOUNT else _("Tax Check {0}")).format(key),
		"change": _(CHANGES[difference.change]),
		"fields": ", ".join(_(FIELD_LABELS[name]) for name in difference.fields)
		if difference.change is diff.Change.CHANGED
		else "",
		"current": described(kind, difference.current),
		"proposed": described(kind, difference.proposed),
		"origin": _(ORIGINS[difference.origin]),
		"proposes": difference.proposes,
	}


def described(kind: str, fields: dict | None) -> str:
	"""The place of an account or the accounts of a check in a few words; empty where there is none."""
	if fields is None:
		return ""
	if kind == CHECK:
		return _("Bases {0}; tax accounts {1}; {2}").format(
			fields["base_accounts"], fields["tax_accounts"], _(fields["side"])
		)
	if fields["place"] == WATCHED:
		return _("Watched, level {0}").format(_(fields["level"]))
	text = _("Kz {0}, {1}").format(fields["kennzahl"], _(fields["side"]))
	if fields["tax_rate"]:
		text += ", " + _("tax rate {0} %").format(fields["tax_rate"])
	if fields["also_kennzahl"]:
		text += ", " + _("also Kz {0}, {1}").format(fields["also_kennzahl"], _(fields["also_side"]))
	return text


@contextmanager
def mapping_errors() -> Iterator[None]:
	"""Show a row the core refuses as the message of the mapping."""
	try:
		yield
	except MappingError as error:
		frappe.throw(str(error), title=_("Invalid VAT Return Mapping"))

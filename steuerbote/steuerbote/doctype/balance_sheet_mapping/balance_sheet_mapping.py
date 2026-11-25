"""The Bilanzzuordnung of a company: which position of the HGB-Taxonomie each account of its books goes to.

steuerbote.balance_mapping_sync turns the rows into the core Mapping of steuerbote.xbrl.mapping; this controller only
reads and fills them. Saving refuses rows the core refuses, a row on an account of another company or on a group,
and, once the HGB-Taxonomie of the mapping is installed („Taxonomie einrichten“ in the ERiC Settings), every position
a rule may not name, with the part of each account by its report type (steuerbote.xbrl.mapping.check). It writes each
position without the prefix of the GAAP module and with its label in the taxonomy. Without the taxonomy the positions
wait for it, and saving says so.

„Vorgaben laden“ (load_defaults) replaces the rows by the defaults of the chart for the version of the taxonomy
(steuerbote/ebilanz/defaults.py), reduced to the ledger accounts of the company, keeping the level a watched account
had, and keeps the version of those defaults (defaults_version) and the rows they gave (defaults_rows). „Vorgaben
aktualisieren“ (compare_with_defaults, update_from_defaults) compares the rows with the defaults of today and with
those kept (steuerbote.mappings.diff), and „Zuordnung exportieren“ and „Zuordnung importieren“ (export_mapping,
compare_with_file, import_file) write and read the file of the mapping (steuerbote.mappings.transfer), all as in the
VAT Return Mapping. The file names the version of the taxonomy whose positions its rows name; an import refuses
another. „Konten prüfen“ (accounts_without_place) lists the ledger accounts of the company without a place in the
mapping, and watch_accounts_without_place watches those with a number at the level Sperrt. A mapping without rows that
has not taken over the defaults of today waits for them (waits_for_defaults), as one made while they were the empty
table of revision 0: Steuerbote einrichten loads them into it, and its form names them above its fields.

The E-Bilanz and the Jahresabschluss read the mapping through to_mapping() and place(), which puts the books of
steuerbote/balances.py on the positions of the fiscal view of the taxonomy (steuerbote.xbrl.mapping.place).

„Auf neue Taxonomie heben“ (lift_taxonomy) takes the rows to the positions of a later version through its changes
(steuerbote/xbrl/changes.py), against its fiscal view, which has to be installed: a rule the lift cannot carry is
watched at the level Sperrt, a row to decide. The mapping keeps the version and the rows before
(previous_taxonomy_version, previous_rows), which export_previous_mapping gives as the file of that version, and the
defaults it took over, so that Vorgaben aktualisieren proposes what the defaults of the later version change. A file
of an earlier version comes in lifted the same way; one of a later version stays out.
"""

import re
from collections.abc import Collection, Iterator
from collections.abc import Mapping as ReadOnlyMapping
from contextlib import contextmanager
from datetime import date

import frappe
from frappe import _
from frappe.core.doctype.file.utils import get_content_hash
from frappe.model.document import Document
from frappe.utils import escape_html, formatdate, getdate

import steuerbote
from steuerbote.balance_mapping_sync import (
	EXCLUDED,
	FILE_FORMAT,
	WATCHED,
	MappingRows,
	default_items,
	defaults_rows,
	dump_items,
	file_body,
	items_of_file_body,
	items_of_rows,
	lifted_items,
	load_items,
	rows_of_items,
	rows_to_mapping,
	without_defaults,
)
from steuerbote.ebilanz.defaults import CHARTS, defaults_version
from steuerbote.mappings import diff, taking_over, transfer
from steuerbote.steuerbote.doctype.eric_settings import eric_settings
from steuerbote.steuerbote.doctype.vat_return_mapping.vat_return_mapping import (
	CHANGES,
	INVALID_FILE_MAPPING,
	MISSING_ACCOUNTS,
	NO_FILE,
	NO_SUCH_FILE,
	NO_TEXT,
	ORIGINS,
	OTHER_CHART,
	PUBLIC_FILE,
	chosen_keys,
	difference_id,
)
from steuerbote.ustva import WatchLevel
from steuerbote.xbrl import taxonomy
from steuerbote.xbrl.mapping import Books, Mapping, MappingError, Part, Placement, Purpose, check, place
from steuerbote.xbrl.taxonomy import Taxonomy, View
from steuerbote.xbrl.versions import LATEST, TAXONOMIES

INVALID = "Invalid Balance Sheet Mapping"
NOT_CHECKED = (
	"The HGB-Taxonomie {0} is not installed, so saving has not checked the positions: Install Taxonomy in the ERiC "
	"Settings."
)
OTHER_TAXONOMY = (
	"The file holds a mapping to the positions of the HGB-Taxonomie {0}, this mapping names those of {1}."
)
NOTHING_TO_WATCH = "No account of the company with an account number lacks a place in the mapping."
NOT_INSTALLED = (
	"The HGB-Taxonomie {0} is not installed: Install Taxonomy in the ERiC Settings before the mapping takes its "
	"positions."
)
NOT_LATER = "The mapping names the positions of the HGB-Taxonomie {0} and rises to a later version only."
NOT_LIFTED = "The mapping was never lifted to a new taxonomy, so it holds no rows of a previous version."
NO_DEFAULTS = "There are no defaults of {0} for the HGB-Taxonomie {1}."
FILE_MESSAGES = (
	NO_FILE,
	NO_SUCH_FILE,
	PUBLIC_FILE,
	NO_TEXT,
	OTHER_CHART,
	OTHER_TAXONOMY,
	MISSING_ACCOUNTS,
	INVALID_FILE_MAPPING,
)
FIELD_LABELS = {
	"place": "Place in the Mapping",
	"concept": "Position",
	"opposite_concept": "Position for the Opposite Balance",
	"purpose": "Abschlusszweck",
	"shareholder": "Owed to or by Shareholders",
	"remaining_term": "Remaining Term",
	"netting_group": "Netting Group",
	"level": "Watch Level",
	"reason": "Reason",
}
OWN_CHART = "Eigener Kontenrahmen"


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
		previous_rows: DF.LongText | None
		previous_taxonomy_version: DF.Data | None
		rules: DF.Table[BalanceSheetMappingRule]
		taxonomy_version: DF.Literal["6.9", "6.10"]
		watched: DF.Table[BalanceSheetMappingWatchedAccount]
	# end: auto-generated types

	def onload(self) -> None:
		"""The defaults the form names above its fields while the mapping waits for them."""
		self.set_onload("defaults_to_load", self.defaults_of_today() if self.waits_for_defaults() else None)

	def validate(self):
		self.validate_accounts()
		self.current_items()
		mapping = self.to_mapping()
		for row, rule in zip(self.rules, mapping.rules, strict=True):
			row.concept, row.opposite_concept = rule.concept, rule.opposite
		self.check_positions(mapping)
		self.defaults_taken_over()

	def validate_accounts(self):
		"""The form offers only ledger accounts of the company; rows that arrive another way are checked here."""
		names = sorted({row.account for row in (*self.rules, *self.watched, *self.excluded) if row.account})
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

	def to_mapping(self) -> Mapping:
		"""The core Mapping of the rows."""
		with mapping_errors():
			return rows_to_mapping(self.chart, *self._rows(), self.taxonomy_version)

	def check_positions(self, mapping: Mapping) -> None:
		"""Every position the rules may not name, against the fiscal view of the taxonomy of the mapping, with the label
		of each position; without the taxonomy installed, a note that the positions wait for it, unless the caller notes
		that itself (flags.taxonomy_noted), as Steuerbote einrichten does."""
		view = position_taxonomy(self.taxonomy_version)
		if view is None:
			for row in self.rules:
				row.concept_label = None
			if mapping.rules and not self.flags.taxonomy_noted:
				frappe.msgprint(_(NOT_CHECKED).format(self.taxonomy_version), alert=True, indicator="orange")
			return
		for row in self.rules:
			row.concept_label = view.label(row.concept) if row.concept and view.has(row.concept) else None
		if problems := check(mapping, view, self._parts()):
			frappe.throw(
				"<br>".join(
					escape_html(_(problem.refusal.template).format(*problem.values)) for problem in problems
				),
				title=_(INVALID),
			)

	def _parts(self) -> dict[str, Part]:
		"""The part of each account of the rules by its report type in ERPNext."""
		names = sorted({row.account for row in self.rules if row.account})
		if not names:
			return {}
		return {
			account.account_number: Part.of_report_type(account.report_type)
			for account in frappe.get_all(
				"Account", filters={"name": ["in", names]}, fields=["account_number", "report_type"]
			)
			if account.account_number and account.report_type
		}

	def place(
		self,
		books: Books,
		purpose: Purpose,
		*,
		closing_account: str | None = None,
		fiscal_year: tuple[date, date] | None = None,
	) -> Placement:
		"""The books on the positions of the mapping in the balance sheet of the purpose, against the fiscal view of its
		taxonomy, which has to be installed; ``closing_account`` is the number of the account the result of earlier
		fiscal years goes to (steuerbote.xbrl.mapping.place)."""
		view = eric_settings.taxonomy_view(self.taxonomy_version, View.FISCAL)
		return place(
			self.to_mapping(), books, view, purpose, closing_account=closing_account, fiscal_year=fiscal_year
		)

	def current_items(self) -> dict[diff.Key, dict]:
		"""The rows as items of steuerbote.mappings.diff; an account in two rows is refused."""
		with mapping_errors():
			return items_of_rows(*self._rows())

	def _rows(self) -> MappingRows:
		return MappingRows(
			[row.as_dict() for row in self.rules],
			[row.as_dict() for row in self.watched],
			[row.as_dict() for row in self.excluded],
		)

	def defaults_taken_over(self) -> dict[diff.Key, dict] | None:
		"""The rows the defaults gave when Vorgaben laden or Vorgaben aktualisieren took them over last, as items;
		None for a mapping that never took them over."""
		if not self.defaults_rows:
			return None
		with mapping_errors():
			return load_items(self.defaults_rows)

	def defaults_of_today(self) -> str | None:
		"""The version of the defaults of today for the chart and the taxonomy of the mapping, None where there are
		none: for a chart of its own or a version of the taxonomy without defaults."""
		try:
			return defaults_version(self.chart, self.taxonomy_version)
		except KeyError:
			return None

	def waits_for_defaults(self) -> bool:
		"""Whether the mapping has no rows and has not taken over the defaults of today, which Steuerbote einrichten
		then loads into it (steuerbote.mappings.taking_over)."""
		return taking_over.waits_for_defaults(
			(self.rules, self.watched, self.excluded), self.defaults_version, self.defaults_of_today()
		)

	@frappe.whitelist(methods=["POST"])
	def load_defaults(self) -> list[str]:
		"""Replace the rows by the defaults of the chart, reduced to the ledger accounts of the company, and note the
		version of the defaults and the rows they gave. A watched account keeps the level its row had, by the number of
		the row or, before Frappe has fetched it, of its account; the rows kept as taken over hold the level of the
		defaults, so that Vorgaben aktualisieren sees a kept level as the user's own. Returns the numbers of the
		accounts of the company the defaults give no place, for the message of the form."""
		self._require_defaults()
		names = self._account_names()
		numbers = {name: number for number, name in names.items()}
		levels = {
			number: row.level
			for row in self.watched
			if (number := row.account_number or numbers.get(row.account))
		}
		self._set_rows(defaults_rows(self.chart, self.taxonomy_version, names.keys(), levels), names)
		self._note_defaults(names.keys())
		return list(without_defaults(self.chart, self.taxonomy_version, names.keys()))

	@frappe.whitelist(methods=["POST"])
	def compare_with_defaults(self) -> dict:
		"""Vorgaben aktualisieren: each difference between the rows and the defaults of today, with whether it comes
		from the defaults, which the form proposes to take over, or from the user."""
		self._require_defaults()
		base = self.defaults_taken_over()
		comparison = diff.compare(self.current_items(), self._defaults_now(), base)
		return {
			"version": defaults_version(self.chart, self.taxonomy_version),
			"taken_over": self.defaults_version or "",
			"base_known": base is not None,
			"differences": [presented(difference) for difference in comparison.differences],
			"unchanged": len(comparison.unchanged),
		}

	@frappe.whitelist(methods=["POST"])
	def update_from_defaults(self, chosen: list[str] | None = None, acknowledge: bool = False) -> int:
		"""Take over the chosen differences of compare_with_defaults, by their id, keep every other row, note the
		defaults of today as taken over, and save. Taking over none notes them only with ``acknowledge``, the word of
		the user that the differences are declined, which the dialog of the form gives; without it the mapping stays as
		it is (steuerbote.mappings.taking_over.notes_defaults). Returns how many differences it took over."""
		self._require_defaults()
		current, proposed = self.current_items(), self._defaults_now()
		keys = chosen_keys(diff.compare(current, proposed, self.defaults_taken_over()), chosen or [])
		if not taking_over.notes_defaults(len(keys), acknowledge):
			return 0
		self._set_items(diff.apply(current, proposed, keys))
		self._note_defaults(self._account_names().keys())
		self.save()
		return len(keys)

	@frappe.whitelist(methods=["POST"])
	def export_mapping(self) -> dict:
		"""Zuordnung exportieren: the mapping as saved, with the version of its taxonomy and the defaults it took over,
		as a file attached privately, where a file of the same content attached before is kept instead. Returns the
		name, the address and the text of the file, which the form hands to the browser to save."""
		saved = frappe.get_doc(self.doctype, self.name)
		today = getdate()
		text = transfer.write(
			FILE_FORMAT,
			file_body(saved.taxonomy_version, saved.current_items(), saved.defaults_taken_over()),
			app_version=steuerbote.__version__,
			company=saved.company,
			chart=saved.chart,
			defaults_version=saved.defaults_version or "",
			exported_on=today,
		)
		file_name = export_file_name(saved.company, today)
		return {
			"file_name": file_name,
			"file_url": saved._attach(file_name, text.encode("utf-8")),
			"content": text,
		}

	@frappe.whitelist(methods=["POST"])
	def compare_with_file(self, file_url: str | None = None, content: str | None = None) -> dict:
		"""Zuordnung importieren: what the file of a mapping, uploaded privately to this mapping or pasted, would change
		here, each difference proposed, and what its header says, with the earlier version it was lifted from."""
		header, items, _defaults, version = self._read_file(file_url, content)
		comparison = diff.compare(self.current_items(), items, None)
		return {
			"company": header.company,
			"chart": header.chart,
			"defaults_version": header.defaults_version,
			"exported_on": formatdate(header.exported_on),
			"app_version": header.app_version,
			"lifted_from": "" if version == self.taxonomy_version else version,
			"differences": [
				{**presented(difference), "proposes": True} for difference in comparison.differences
			],
			"unchanged": len(comparison.unchanged),
		}

	@frappe.whitelist(methods=["POST"])
	def import_file(
		self, file_url: str | None = None, content: str | None = None, chosen: list[str] | None = None
	) -> int:
		"""Take over the chosen differences of compare_with_file, by their id, keep every other row, note the defaults
		the file names as taken over, and save. Returns how many differences it took over."""
		header, items, defaults, _version = self._read_file(file_url, content)
		current = self.current_items()
		keys = chosen_keys(diff.compare(current, items, None), chosen or [])
		self._set_items(diff.apply(current, items, keys))
		self.defaults_version = header.defaults_version or None
		self.defaults_rows = None if defaults is None else dump_items(defaults)
		self.save()
		return len(keys)

	@frappe.whitelist(methods=["POST"])
	def accounts_without_place(self) -> list[dict]:
		"""Konten prüfen: the ledger accounts of the company that the mapping, as the form holds it, gives no place,
		each with its number, its name and its root type; an account without number can have no place."""
		if not self.company:
			frappe.throw(_("Select the company first."))
		numbers = self.to_mapping().numbers
		return [
			{
				"account": account.name,
				"account_number": account.account_number or "",
				"account_name": account.account_name,
				"root_type": account.root_type,
			}
			for account in frappe.get_all(
				"Account",
				filters={"company": self.company, "is_group": 0},
				fields=["name", "account_number", "account_name", "root_type"],
				order_by="account_number, name",
			)
			if not account.account_number or account.account_number not in numbers
		]

	@frappe.whitelist(methods=["POST"])
	def watch_accounts_without_place(self) -> list[str]:
		"""Watch every account of accounts_without_place that has an account number at the level Sperrt, then save.
		Returns the accounts it adds."""
		added = [account for account in self.accounts_without_place() if account["account_number"]]
		if not added:
			frappe.throw(_(NOTHING_TO_WATCH))
		for account in added:
			self.append(
				"watched",
				{
					"account": account["account"],
					"account_number": account["account_number"],
					"level": WatchLevel.BLOCKING.value,
				},
			)
		self.save()
		return [account["account"] for account in added]

	@frappe.whitelist(methods=["POST"])
	def lift_taxonomy(self, target: str | None = None) -> dict:
		"""Auf neue Taxonomie heben: the rows on the positions of a later version of the HGB-Taxonomie, by default the
		latest, through its changes (steuerbote.balance_mapping_sync.lifted_items), against its fiscal view, which
		Taxonomie einrichten has to have installed; a rule the lift cannot carry is watched at the level Sperrt. Keeps
		the version and the rows before, saves, and returns what the lift renamed, the rows left to decide and the new
		Mussfelder with their labels, for the dialog of the form."""
		target = target or LATEST.version
		order = list(TAXONOMIES)
		if target not in order or order.index(target) <= order.index(self.taxonomy_version):
			frappe.throw(_(NOT_LATER).format(self.taxonomy_version))
		view = position_taxonomy(target)
		if view is None:
			frappe.throw(_(NOT_INSTALLED).format(target))
		before = self.current_items()
		with mapping_errors():
			items, lifted = lifted_items(
				self.chart, before, self.taxonomy_version, target, taxonomy=view, parts=self._parts()
			)
		previous = self.taxonomy_version
		self.previous_taxonomy_version = previous
		self.previous_rows = dump_items(before)
		self.taxonomy_version = target
		self._set_items(items)
		self.save()
		return {
			"version": target,
			"previous": previous,
			"renamed": [{"account": account, "old": old, "new": new} for account, old, new in lifted.renamed],
			"to_decide": [
				{
					"account": decision.rule.account_number,
					"position": decision.position,
					"text": decision.text,
				}
				for decision in lifted.to_decide
			],
			"mussfelder": [{"position": name, "label": view.label(name)} for name in lifted.mussfelder],
		}

	@frappe.whitelist(methods=["POST"])
	def export_previous_mapping(self) -> dict:
		"""The rows before Auf neue Taxonomie heben as the file of Zuordnung exportieren on the positions of the
		previous version, attached privately as export_mapping attaches its file."""
		saved = frappe.get_doc(self.doctype, self.name)
		if not saved.previous_rows:
			frappe.throw(_(NOT_LIFTED))
		with mapping_errors():
			items = load_items(saved.previous_rows)
		today = getdate()
		text = transfer.write(
			FILE_FORMAT,
			file_body(saved.previous_taxonomy_version, items, saved.defaults_taken_over()),
			app_version=steuerbote.__version__,
			company=saved.company,
			chart=saved.chart,
			defaults_version=saved.defaults_version or "",
			exported_on=today,
		)
		file_name = (
			export_file_name(saved.company, today).removesuffix(".json")
			+ f"-Taxonomie-{saved.previous_taxonomy_version}.json"
		)
		return {
			"file_name": file_name,
			"file_url": saved._attach(file_name, text.encode("utf-8")),
			"content": text,
		}

	def _read_file(
		self, file_url: str | None, content: str | None
	) -> tuple[transfer.Header, dict[diff.Key, dict], dict[diff.Key, dict] | None, str]:
		"""The header, the rows, the defaults and the version of the taxonomy of a file this mapping can take: of its
		kind, unchanged since the export, of the chart and the taxonomy of the mapping or an earlier one, whose rows
		come lifted to the version of the mapping, with accounts the company has and rows the core takes."""
		title = _("Import Mapping")
		try:
			found = transfer.read(self._file_text(file_url, content), FILE_FORMAT)
		except transfer.TransferError as error:
			frappe.throw(transfer.message(error, _, escape_html), title=title)
		if found.header.chart != self.chart:
			frappe.throw(_(OTHER_CHART).format(escape_html(found.header.chart), self.chart), title=title)
		try:
			version, items, defaults = items_of_file_body(found.body)
		except MappingError as error:
			frappe.throw(
				_(INVALID_FILE_MAPPING).format(escape_html(_(error.template).format(*error.values))),
				title=title,
			)
		if version != self.taxonomy_version:
			order = list(TAXONOMIES)
			if version not in order or order.index(version) > order.index(self.taxonomy_version):
				frappe.throw(
					_(OTHER_TAXONOMY).format(escape_html(version), self.taxonomy_version), title=title
				)
			with mapping_errors():
				items, _lifted = lifted_items(
					self.chart,
					items,
					version,
					self.taxonomy_version,
					taxonomy=position_taxonomy(self.taxonomy_version),
				)
		if missing := sorted({number for _kind, number in items} - self._account_names().keys()):
			frappe.throw(_(MISSING_ACCOUNTS).format(escape_html(", ".join(missing))), title=title)
		return found.header, items, defaults, version

	def _file_text(self, file_url: str | None, content: str | None) -> str:
		"""The pasted content, or else the text of the private file at the address, attached to this mapping."""
		if content and content.strip():
			return content
		if not file_url:
			frappe.throw(_(NO_FILE))
		attached = frappe.get_all(
			"File",
			filters={
				"file_url": file_url,
				"attached_to_doctype": self.doctype,
				"attached_to_name": self.name,
			},
			fields=["name", "is_private"],
			limit=1,
		)
		if not attached:
			frappe.throw(_(NO_SUCH_FILE).format(escape_html(file_url)))
		if not attached[0].is_private:
			frappe.throw(_(PUBLIC_FILE).format(escape_html(file_url)))
		text = frappe.get_doc("File", attached[0].name).get_content()
		if not isinstance(text, str):
			frappe.throw(_(NO_TEXT))
		return text

	def _attach(self, file_name: str, content: bytes) -> str:
		"""Attach the file privately; a file of the same content attached before is kept instead."""
		attached = frappe.db.get_value(
			"File",
			{
				"attached_to_doctype": self.doctype,
				"attached_to_name": self.name,
				"content_hash": get_content_hash(content),
			},
			"file_url",
		)
		if attached:
			return attached
		file = frappe.get_doc(
			{
				"doctype": "File",
				"file_name": file_name,
				"attached_to_doctype": self.doctype,
				"attached_to_name": self.name,
				"is_private": 1,
				"content": content,
			}
		)
		file.insert()
		return file.file_url

	def _require_defaults(self) -> None:
		if not self.company:
			frappe.throw(_("Select the company first."))
		if self.chart not in CHARTS:
			frappe.throw(_("There are no defaults for {0}.").format(self.chart))
		try:
			defaults_version(self.chart, self.taxonomy_version)
		except KeyError:
			frappe.throw(_(NO_DEFAULTS).format(self.chart, self.taxonomy_version))

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
		return default_items(self.chart, self.taxonomy_version, self._account_names().keys())

	def _note_defaults(self, numbers: Collection[str]) -> None:
		self.defaults_version = defaults_version(self.chart, self.taxonomy_version)
		self.defaults_rows = dump_items(default_items(self.chart, self.taxonomy_version, numbers))

	def _set_items(self, items: dict[diff.Key, dict]) -> None:
		self._set_rows(rows_of_items(items), self._account_names())

	def _set_rows(self, rows: MappingRows, names: ReadOnlyMapping[str, str]) -> None:
		"""Write the rows into the tables, each account by the name of the account of the company with its number."""
		for table, table_rows in (
			("rules", rows.rule_rows),
			("watched", rows.watched_rows),
			("excluded", rows.excluded_rows),
		):
			self.set(table, [{"account": names.get(row["account_number"]), **row} for row in table_rows])


def position_taxonomy(version: str) -> Taxonomy | None:
	"""The fiscal view of the version of the taxonomy whose positions a mapping names, None while Taxonomie
	einrichten has not installed it."""
	if taxonomy.installed(eric_settings.taxonomy_root(), TAXONOMIES[version]) is None:
		return None
	return eric_settings.taxonomy_view(version, View.FISCAL)


def export_file_name(company: str, day: date) -> str:
	"""Bilanzzuordnung-<company>-<day>.json, the company with its letters and digits and a hyphen for the rest."""
	return f"Bilanzzuordnung-{re.sub(r'[^\w]+', '-', company).strip('-')}-{day.isoformat()}.json"


def presented(difference: diff.Difference) -> dict:
	"""A difference as the dialog of the form shows it, in the language of the user."""
	_kind, number = difference.key
	return {
		"id": difference_id(difference),
		"subject": _("Account {0}").format(number),
		"change": _(CHANGES[difference.change]),
		"fields": ", ".join(_(FIELD_LABELS[name]) for name in difference.fields)
		if difference.change is diff.Change.CHANGED
		else "",
		"current": described(difference.current),
		"proposed": described(difference.proposed),
		"origin": _(ORIGINS[difference.origin]),
		"proposes": difference.proposes,
	}


def described(fields: dict | None) -> str:
	"""The place of an account in a few words; empty where it has none."""
	if fields is None:
		return ""
	if fields["place"] == WATCHED:
		return _("Watched, level {0}").format(_(fields["level"]))
	if fields["place"] == EXCLUDED:
		return _("Outside the Bilanz and the GuV: {0}").format(fields["reason"])
	parts = [_("Position {0}").format(fields["concept"])]
	if fields["opposite_concept"]:
		parts.append(_("opposite balance {0}").format(fields["opposite_concept"]))
	parts.append(_(fields["purpose"]))
	if fields["shareholder"]:
		parts.append(_("owed to or by shareholders"))
	if fields["remaining_term"]:
		parts.append(_(fields["remaining_term"]))
	if fields.get("netting_group"):
		parts.append(_("netting group {0}").format(fields["netting_group"]))
	return ", ".join(parts)


@contextmanager
def mapping_errors() -> Iterator[None]:
	"""Show a row the core refuses as the message of the mapping, in the language of the user."""
	try:
		yield
	except MappingError as error:
		frappe.throw(_(error.template).format(*error.values), title=_(INVALID))

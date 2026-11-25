"""The Kontenzuordnung Ertragsteuern of a company: what the balance of each account is for the Körperschaftsteuer and
the Gewerbesteuer, and which accounts are watched.

steuerbote.income_tax_mapping_sync turns the rows into the core Mapping of steuerbote.kst.categories; this controller
only reads and fills them.

„Vorgaben laden“ (load_defaults) replaces the rows by the defaults of the chart (steuerbote.kst.defaults), reduced to
the ledger accounts of the company, keeps the version of those defaults (defaults_version) and the rows they gave
(defaults_rows), and names the DATEV accounts of the defaults the company lacks with their labels. „Vorgaben
aktualisieren“ compares the rows with the defaults of today and with those kept (compare_with_defaults,
steuerbote.mappings.diff), so that it can tell a change of the defaults from a change the user made, and takes over
the differences chosen (update_from_defaults). A mapping without rows that has not taken over the defaults of today
waits for them (waits_for_defaults): Steuerbote einrichten loads them into it, and its form names them above its
fields.

„Zuordnung exportieren“ (export_mapping) writes the saved mapping into a file of the format
steuerbote/income-tax-mapping (steuerbote.mappings.transfer) and attaches it privately. „Zuordnung importieren“ reads
such a file, uploaded privately to the mapping or pasted, checks its checksum, its chart, its accounts and its rows,
shows what differs (compare_with_file) and takes over what the user chose (import_file), with the version and the
rows of the defaults the file names. Both work as those of the VAT Return Mapping, whose messages they share.
"""

import re
from collections.abc import Collection, Iterator
from contextlib import contextmanager
from datetime import date

import frappe
from frappe import _
from frappe.core.doctype.file.utils import get_content_hash
from frappe.model.document import Document
from frappe.utils import escape_html, formatdate, getdate

import steuerbote
from steuerbote.income_tax_mapping_sync import (
	FILE_FORMAT,
	WATCHED,
	default_items,
	defaults_for_accounts,
	dump_items,
	file_body,
	items_of_file_body,
	items_of_rows,
	load_items,
	rows_of_items,
	rows_to_mapping,
)
from steuerbote.kst.categories import Mapping
from steuerbote.kst.defaults import DEFAULTS, defaults_version
from steuerbote.mappings import diff, taking_over, transfer
from steuerbote.steuerbote import guards
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
from steuerbote.ustva.mapping import MappingError

FIELD_LABELS = {
	"place": "Place in the Mapping",
	"category": "Category",
	"trading_class": "Trading Class",
	"level": "Watch Level",
}
INVALID_MAPPING = "Invalid Income Tax Mapping"


class IncomeTaxMapping(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		from steuerbote.steuerbote.doctype.income_tax_mapping_rule.income_tax_mapping_rule import (
			IncomeTaxMappingRule,
		)
		from steuerbote.steuerbote.doctype.income_tax_watched_account.income_tax_watched_account import (
			IncomeTaxWatchedAccount,
		)

		chart: DF.Literal["SKR03", "SKR04", "Eigener Kontenrahmen"]
		company: DF.Link
		defaults_rows: DF.LongText | None
		defaults_version: DF.Data | None
		rules: DF.Table[IncomeTaxMappingRule]
		watched: DF.Table[IncomeTaxWatchedAccount]
	# end: auto-generated types

	def onload(self) -> None:
		"""The defaults the form names above its fields while the mapping waits for them."""
		self.set_onload("defaults_to_load", self.defaults_of_today() if self.waits_for_defaults() else None)

	def validate(self):
		self.validate_accounts()
		self.current_items()
		self.to_mapping()
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

	def to_mapping(self) -> Mapping:
		"""The core Mapping of the rows."""
		with mapping_errors():
			return rows_to_mapping(
				self.chart, [row.as_dict() for row in self.rules], [row.as_dict() for row in self.watched]
			)

	def current_items(self) -> dict[diff.Key, dict]:
		"""The rows as items of steuerbote.mappings.diff; an account in two rows is refused."""
		with mapping_errors():
			return items_of_rows(
				[row.as_dict() for row in self.rules], [row.as_dict() for row in self.watched]
			)

	def defaults_taken_over(self) -> dict[diff.Key, dict] | None:
		"""The rows the defaults gave when Vorgaben laden or Vorgaben aktualisieren took them over last, as items;
		None for a mapping that never took them over."""
		if not self.defaults_rows:
			return None
		with mapping_errors():
			return load_items(self.defaults_rows)

	def defaults_of_today(self) -> str | None:
		"""The version of the defaults of today for the chart of the mapping, None for a chart without defaults."""
		return defaults_version(self.chart) if self.chart in DEFAULTS else None

	def waits_for_defaults(self) -> bool:
		"""Whether the mapping has no rows and has not taken over the defaults of today, which Steuerbote einrichten
		then loads into it (steuerbote.mappings.taking_over)."""
		return taking_over.waits_for_defaults(
			(self.rules, self.watched), self.defaults_version, self.defaults_of_today()
		)

	@frappe.whitelist(methods=["POST"])
	@guards.on_stored("write", new=True)
	def load_defaults(self) -> list[dict]:
		"""Replace the rows by the defaults of the chart, reduced to the ledger accounts of the company, and note the
		version of the defaults and the rows they gave.

		A watched account keeps the level its row had; the rows kept as taken over hold the level of the defaults, so
		that Vorgaben aktualisieren sees the level kept as the user's own. Returns the accounts of the defaults that the
		company does not have, each with its number and its DATEV label, for the message of the form.
		"""
		self._require_defaults()
		names = self._account_names()
		levels = {row.account_number: row.level for row in self.watched if row.account_number}
		defaults = defaults_for_accounts(self.chart, names.keys(), levels)
		self.set("rules", [{"account": names[row["account_number"]], **row} for row in defaults.rule_rows])
		self.set(
			"watched", [{"account": names[row["account_number"]], **row} for row in defaults.watched_rows]
		)
		self._note_defaults(names.keys())
		return [account._asdict() for account in defaults.missing]

	@frappe.whitelist(methods=["POST"])
	@guards.on_stored("read", new=True)
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
	@guards.on_stored("write")
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
	@guards.on_stored("write")
	def export_mapping(self) -> dict:
		"""Zuordnung exportieren: the mapping as saved, with the defaults it took over, as a file attached privately,
		where a file of the same content attached before is kept instead. Returns the name, the address and the text
		of the file, which the form hands to the browser to save."""
		saved = frappe.get_doc(self.doctype, self.name)
		today = getdate()
		text = transfer.write(
			FILE_FORMAT,
			file_body(saved.current_items(), saved.defaults_taken_over()),
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
	@guards.on_stored("read")
	def compare_with_file(self, file_url: str | None = None, content: str | None = None) -> dict:
		"""Zuordnung importieren: what the file of a mapping, uploaded privately to this mapping or pasted, would change
		here, each difference proposed, and what its header says."""
		header, items, _defaults = self._read_file(file_url, content)
		comparison = diff.compare(self.current_items(), items, None)
		return {
			"company": header.company,
			"chart": header.chart,
			"defaults_version": header.defaults_version,
			"exported_on": formatdate(header.exported_on),
			"app_version": header.app_version,
			"differences": [
				{**presented(difference), "proposes": True} for difference in comparison.differences
			],
			"unchanged": len(comparison.unchanged),
		}

	@frappe.whitelist(methods=["POST"])
	@guards.on_stored("write")
	def import_file(
		self, file_url: str | None = None, content: str | None = None, chosen: list[str] | None = None
	) -> int:
		"""Take over the chosen differences of compare_with_file, by their id, keep every other row, note the defaults
		the file names as taken over, and save. Returns how many differences it took over."""
		header, items, defaults = self._read_file(file_url, content)
		current = self.current_items()
		keys = chosen_keys(diff.compare(current, items, None), chosen or [])
		self._set_items(diff.apply(current, items, keys))
		self.defaults_version = header.defaults_version or None
		self.defaults_rows = None if defaults is None else dump_items(defaults)
		self.save()
		return len(keys)

	def _read_file(
		self, file_url: str | None, content: str | None
	) -> tuple[transfer.Header, dict[diff.Key, dict], dict[diff.Key, dict] | None]:
		"""The header, the rows and the defaults of a file this mapping can take: of its kind, unchanged since the
		export, of the chart of the mapping, with accounts the company has and rows the core takes."""
		title = _("Import Mapping")
		try:
			found = transfer.read(self._file_text(file_url, content), FILE_FORMAT)
		except transfer.TransferError as error:
			frappe.throw(transfer.message(error, _, escape_html), title=title)
		if found.header.chart != self.chart:
			frappe.throw(_(OTHER_CHART).format(escape_html(found.header.chart), self.chart), title=title)
		try:
			items, defaults = items_of_file_body(found.body)
			rows_to_mapping(self.chart, *rows_of_items(items))
		except MappingError as error:
			frappe.throw(_(INVALID_FILE_MAPPING).format(escape_html(str(error))), title=title)
		if missing := sorted({number for _kind, number in items} - self._account_names().keys()):
			frappe.throw(_(MISSING_ACCOUNTS).format(escape_html(", ".join(missing))), title=title)
		return found.header, items, defaults

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
		return default_items(self.chart, self._account_names().keys())

	def _note_defaults(self, numbers: Collection[str]) -> None:
		self.defaults_version = defaults_version(self.chart)
		self.defaults_rows = dump_items(default_items(self.chart, numbers))

	def _set_items(self, items: dict[diff.Key, dict]) -> None:
		"""Write the items into the rows, each account by the name of the account of the company with its number."""
		names = self._account_names()
		rows = rows_of_items(items)
		self.set("rules", [{"account": names.get(row["account_number"]), **row} for row in rows.rule_rows])
		self.set(
			"watched", [{"account": names.get(row["account_number"]), **row} for row in rows.watched_rows]
		)


def export_file_name(company: str, day: date) -> str:
	"""Kontenzuordnung-Ertragsteuern-<company>-<day>.json, the company with its letters and digits and a hyphen for
	the rest."""
	return (
		f"Kontenzuordnung-Ertragsteuern-{re.sub(r'[^\w]+', '-', company).strip('-')}-{day.isoformat()}.json"
	)


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
	"""The place of an account in a few words: its category with its trading class, or the level it is watched at;
	empty where there is none."""
	if fields is None:
		return ""
	if fields["place"] == WATCHED:
		return _("Watched, level {0}").format(_(fields["level"]))
	if fields["trading_class"]:
		return f"{_(fields['category'])}, {_(fields['trading_class'])}"
	return _(fields["category"])


@contextmanager
def mapping_errors() -> Iterator[None]:
	"""Show a row the core refuses as the message of the mapping, which quotes what the row holds as text."""
	try:
		yield
	except MappingError as error:
		frappe.throw(escape_html(str(error)), title=_(INVALID_MAPPING))

"""Who may act on the documents of Steuerbote and how, checked in one place for every DocType of the app.

- **Records of the app.** An ELSTER Transmission, a VAT ID Confirmation and a Deadline Reminder record what Steuerbote
  did: a run through ERiC or the note of a filing, a query at the BZSt or at VIES, a reminder that went out
  (_RECORDS in hooks.py). Only Steuerbote writes them. Its own code inserts and saves one through insert_record() and
  save_record(), which mark the document with a token of this module for the time of the write; the doc_events of
  hooks.py refuse an insert and a rename without it, and the ELSTER Transmission refuses a change without it
  (recorded). The token is an object of this process: Frappe takes no flags from a request (RESERVED_KEYWORDS of
  frappe.model.document), and no JSON stands for an object, so no request sets it, whatever its role, the
  Administrator's neither: not the REST API, the desk, frappe.client, the Data Import, Duplicate or the restore of a
  Deleted Document. What happens in the database directly is beyond these checks.
- **What a filing is for.** The company and the period or year of a filing, with what else names it, such as the
  rhythm of a Voranmeldung or the Bilanzart of an E-Bilanz, are fixed once it is created: the fields that its
  DocType marks set_only_once. The desk shows them read-only on a saved document, and Filing, which the controller of
  every filing inherits, refuses a change by any way of saving before the controller validates it, and refuses to
  rename or merge the filing, since its records name it. Another company or period is a new document.
- **The stored document.** The desk calls a method of a document through run_doc_method with the copy of the
  document that the client sends, and Frappe checks the permission to read that copy, not the document stored under
  its name. on_stored() checks the permission the method needs on the stored document, with the User Permissions on
  its company, and on the copy; a copy the database does not hold is refused, unless the method works on the unsaved
  form, whose copy is all there is, and then the permission to create it counts.
- **Data that leaves the site.** Testsenden and Senden send the data of a filing to ELSTER, and the confirmation of
  USt-IdNrn. sends the company's own USt-IdNr. with those of its customers to the BZSt or VIES. Each needs the
  permission to submit the stored document, Buchen, as Senden itself files it: require_permission_to_send().
"""

import functools
from collections.abc import Callable
from typing import Any

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cast

RECORDED = "steuerbote_recorded"
_BY_STEUERBOTE = object()


def insert_record(doc: Document) -> Document:
	"""Insert a record of the app as Steuerbote writes it."""
	with _recording(doc):
		return doc.insert(ignore_permissions=True)


def save_record(doc: Document) -> Document:
	"""Save a record of the app as Steuerbote writes it."""
	with _recording(doc):
		return doc.save(ignore_permissions=True)


class _recording:
	"""The token on the document for the time of one write of Steuerbote."""

	def __init__(self, doc: Document) -> None:
		self.doc = doc

	def __enter__(self) -> None:
		self.doc.flags[RECORDED] = _BY_STEUERBOTE

	def __exit__(self, *exc_info: object) -> None:
		self.doc.flags.pop(RECORDED, None)


def recorded(doc: Document) -> bool:
	"""Whether Steuerbote writes the document now."""
	return doc.flags.get(RECORDED) is _BY_STEUERBOTE


def refuse_unless_recorded(doc: Document, method: str | None = None) -> None:
	"""doc_event before_insert of the records of the app."""
	if not recorded(doc):
		frappe.throw(
			_(
				"Only Steuerbote writes a {0}: it records what Steuerbote did, so it cannot be created by hand, through the API, by a copy or by an import."
			).format(_(doc.doctype)),
			frappe.PermissionError,
		)


def refuse_rename(doc: Document, method: str | None = None, *args: Any) -> None:
	"""doc_event before_rename of the records of the app and of the filings: other records name them."""
	frappe.throw(
		_("{0} {1} keeps its name: the records of Steuerbote name it.").format(_(doc.doctype), doc.name),
		frappe.PermissionError,
	)


def keep_identity(doc: Document, method: str | None = None) -> None:
	"""doc_event before_validate of the filings: what the document is for stays as it was created."""
	before = doc.get_doc_before_save()
	if doc.is_new() or before is None:
		return
	for field in doc.meta.get_set_only_once_fields():
		if cast(field.fieldtype, before.get(field.fieldname)) != cast(
			field.fieldtype, doc.get(field.fieldname)
		):
			frappe.throw(
				_(
					"{0} of {1} stays as it was created: for another company or period, create a new document."
				).format(_(field.label), doc.name),
				frappe.CannotChangeConstantError,
			)


class Filing:
	"""A filing, mixed into its controller before Document: the VAT Return, the VAT Return Extension, the Recapitulative
	Statement, the VAT Return Prior Filing and, through AnnualFiling, every annual document."""

	def before_validate(self) -> None:
		keep_identity(self)

	def before_rename(self, old: str, new: str, merge: bool = False) -> None:
		refuse_rename(self)


def on_stored(ptype: str, *, new: bool = False) -> Callable:
	"""Decorator of a whitelisted method of a document, under @frappe.whitelist: the method runs only for a user with
	``ptype`` on the stored document and on the copy the request sent; with ``new``, also on an unsaved document for a
	user who may create it."""

	def decorate(method: Callable) -> Callable:
		@functools.wraps(method)
		def guarded(doc: Document, *args: Any, **kwargs: Any) -> Any:
			check_stored(doc, ptype, new=new)
			return method(doc, *args, **kwargs)

		return guarded

	return decorate


def check_stored(doc: Document, ptype: str, *, new: bool = False) -> Document | None:
	"""Check ``ptype`` on the stored document and on ``doc``, the copy a request may have sent; returns the stored
	document, or None for an unsaved one that ``new`` admits."""
	if doc.is_new() or not doc.name:
		if not new:
			frappe.throw(_("Save the {0} first.").format(_(doc.doctype)))
		doc.check_permission("create")
		return None
	if not frappe.db.exists(doc.doctype, doc.name):
		frappe.throw(_("{0} {1} does not exist.").format(_(doc.doctype), doc.name), frappe.DoesNotExistError)
	stored = frappe.get_doc(doc.doctype, doc.name)
	stored.check_permission(ptype)
	doc.check_permission(ptype)
	return stored


def require_permission_to_send(doc: Document) -> None:
	"""Testsenden, Senden and the confirmation of USt-IdNrn. send data off the site, to ELSTER, the BZSt or VIES: only
	who may submit the stored document may start them."""
	stored = check_stored(doc, "write")
	if not stored.has_permission("submit"):
		frappe.throw(
			_(
				"Testsenden, Senden and the confirmation of USt-IdNrn. send data of {0} off the site, to ELSTER, the BZSt or VIES: they need the permission to submit it, which Accounts Manager and System Manager have by default."
			).format(doc.name),
			frappe.PermissionError,
		)

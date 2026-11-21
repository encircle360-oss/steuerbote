"""The files of the records Steuerbote keeps for the tax authorities stay as they were stored.

An ELSTER Transmission keeps the Nutzdaten, the protocol and the answer of the ELSTER server of its run, a VAT ID
Confirmation the answer of its query, which is the proof of the query (UStAE 18e.1 Abs. 2 Satz 5). Each is a
private File of the user whose background job stored it, and Frappe lets the owner of a File change and delete it
(has_permission of File). These doc_events of File refuse, for a File attached to such a record, to change what it
is attached to, whether it is private, the file it points to and its name, to rename it, and to delete it while
the record exists. They compare with the File as it is stored, never with what a request sends: a File detached in
the same request is still the File of its record. Deleting a record deletes its Files after the record, as Frappe
does it (delete_doc), so they go with a transmission a System Manager deletes.

Frappe keeps equal content once: a File of its own with the content of a record's File shares the file on disk,
and making it public moves that file and points every File with the same content to the new address
(update_existing_file_docs of File), so that is refused as well. The checks run before the validation of File,
which moves the file. Migrations and installations are left alone, and what happens in the database or on the disk
directly is beyond these checks.
"""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, cstr

TRANSMISSION = "ELSTER Transmission"
CONFIRMATION = "VAT ID Confirmation"
RECORDS = (TRANSMISSION, CONFIRMATION)
KEPT = (
	"attached_to_doctype",
	"attached_to_name",
	"attached_to_field",
	"file_name",
	"file_url",
	"is_private",
	"is_folder",
	"content_hash",
)
FLAGS = ("is_private", "is_folder")


def keep_unchanged(file: Document, method: str | None = None) -> None:
	"""doc_event before_validate of File."""
	if file.is_new() or _setting_up():
		return
	stored = file.get_doc_before_save() or frappe.get_doc("File", file.name)
	if _record_of(stored):
		if any(_value(stored, field) != _value(file, field) for field in KEPT):
			_refuse(stored)
		return
	if _value(stored, "is_private") != _value(file, "is_private"):
		_refuse_to_move_the_file_of_a_record(stored)


def keep_while_recorded(file: Document, method: str | None = None) -> None:
	"""doc_event on_trash of File: the File of a record goes only after its record."""
	if _setting_up():
		return
	stored = frappe.db.get_value(
		"File", file.name, ("name", "file_name", "attached_to_doctype", "attached_to_name"), as_dict=True
	)
	record = _record_of(stored) if stored else None
	if record and frappe.db.exists(*record):
		_refuse(stored)


def keep_name(file: Document, method: str | None = None, *args) -> None:
	"""doc_event before_rename of File."""
	if not _setting_up() and _record_of(file):
		_refuse(file)


def _record_of(file) -> tuple[str, str] | None:
	if file.attached_to_doctype in RECORDS and file.attached_to_name:
		return file.attached_to_doctype, file.attached_to_name
	return None


def _refuse(stored) -> None:
	if stored.attached_to_doctype == CONFIRMATION:
		frappe.throw(
			_("The answer of {0} is part of the proof of the query and cannot be changed or deleted.").format(
				stored.attached_to_name
			)
		)
	frappe.throw(
		_("The file {0} belongs to the ELSTER Transmission {1} and stays as the run stored it.").format(
			stored.get("file_name") or stored.get("name"), stored.attached_to_name
		)
	)


def _refuse_to_move_the_file_of_a_record(stored: Document) -> None:
	if not stored.content_hash:
		return
	sharing = frappe.get_all(
		"File",
		filters={
			"content_hash": stored.content_hash,
			"name": ["!=", stored.name],
			"attached_to_doctype": ["in", RECORDS],
		},
		fields=["attached_to_doctype", "attached_to_name"],
		limit=1,
	)
	if sharing:
		frappe.throw(
			_(
				"The file {0} shares its content with a file of {1} {2}, which stays private and in its place."
			).format(stored.file_name, _(sharing[0].attached_to_doctype), sharing[0].attached_to_name)
		)


def _value(file, field: str) -> int | str:
	value = file.get(field)
	return cint(value) if field in FLAGS else cstr(value)


def _setting_up() -> bool:
	return bool(frappe.flags.in_install or frappe.flags.in_migrate or frappe.flags.in_patch)

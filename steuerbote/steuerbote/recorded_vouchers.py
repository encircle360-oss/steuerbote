"""What a filing records of the vouchers of the ledger, which may change after it was calculated.

The deviations, hints and late changes of a VAT Return and the hints and vouchers of a Zusammenfassende Meldung name
the voucher behind each row through a Dynamic Link, so that the form links it. A row records what the ledger held when
Berechnen ran: the voucher may be cancelled, amended or deleted since, and with „Unveränderliches Hauptbuch
aktivieren“ in the Accounts Settings a cancelled voucher stays in the ledger beside its reversal. Frappe refuses to
save a document that links a cancelled or missing document (Document._validate_links), which would leave a filing that
can no longer be calculated or saved, so these rows skip that check. hooks.py lists their DocTypes in
ignore_links_on_delete, so that no recorded row keeps a voucher from being cancelled or deleted either: what changed
in a filed period shows as a change after its filing.

The Journal Entries an annual filing proposes, the Rückstellungen of the Körperschaftsteuererklärung and the
Ergebnisverwendung of the Jahresabschluss, are the company's to check, submit, cancel or delete; the filing keeps
naming one that was cancelled, and forgets one that was deleted: hooks.py runs forget_proposed_entry when a Journal
Entry is deleted, before Frappe looks for the documents that link it.
"""

import frappe

PROPOSING = (
	("Corporate Income Tax Return", "provisions_entry"),
	("Annual Accounts", "appropriation_entry"),
)
"""The filings that propose Journal Entries, with the field that links the one proposed."""


class RecordedVoucherRow:
	"""A row that names a voucher as Berechnen found it, whatever became of the voucher since."""

	def get_invalid_links(self, is_submittable: bool = False) -> tuple[list, list]:
		return [], []


class ProposedJournalEntries:
	"""A filing whose fields PROPOSED_ENTRIES link the Journal Entries it proposed."""

	PROPOSED_ENTRIES: tuple[str, ...] = ()

	def get_invalid_links(self, is_submittable: bool = False) -> tuple[list, list]:
		invalid, cancelled = super().get_invalid_links(is_submittable)
		return (
			[link for link in invalid if link[0] not in self.PROPOSED_ENTRIES],
			[link for link in cancelled if link[0] not in self.PROPOSED_ENTRIES],
		)


def forget_proposed_entry(doc, method: str | None = None) -> None:
	"""Doc event on_trash of a Journal Entry: the filings that proposed it no longer name it, so that it can be deleted
	and proposed again."""
	for doctype, fieldname in PROPOSING:
		for name in frappe.get_all(doctype, filters={fieldname: doc.name}, pluck="name"):
			frappe.db.set_value(doctype, name, fieldname, None, update_modified=False)

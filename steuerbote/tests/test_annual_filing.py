"""The base of the annual documents, steuerbote/steuerbote/annual_filing.py, on the test documents of
steuerbote/tests/annual_document.py: the start as a draft of its Fiscal Year, Berechnen with the corrections and lines
by hand, what a save keeps, one draft and one filing per key, the Berichtigung, the note of a filing and the amounts
computed again before it; and the Jahresabschluss, adopted by Buchen, transmitted, eingestellt, and cancelled and
amended when it changes."""

import html
import re
from datetime import date
from decimal import Decimal

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import add_days, flt, getdate, today

from steuerbote import __version__
from steuerbote.jahresmeldung import corrections, lifecycle, overrides
from steuerbote.tests import annual_document
from steuerbote.tests.annual_document import (
	ACCOUNTS_DOCTYPE,
	COMPANY,
	DOCTYPE,
	LINE_DOCTYPE,
	LINES,
	NEGATIVE,
	source,
)
from steuerbote.tests.helpers import make_company
from steuerbote.tests.transmitting import TICKET, TRANSMISSION, Transmitting

# The form of TransferTicketSType in headerbasis_datentypen.xsd, invented.
MEIN_ELSTER_TICKET = "ab123cdefghijkmnopqrstuvwxyz0123"
SOURCE_ERROR = {
	"finding": "SB-QUELLE",
	"severity": "Fehler",
	"text": "Ein Konto ohne Zuordnung hat einen Saldo.",
	"reference": "Konto 1590",
}
SOURCE_HINT = {"finding": "SB-HINWEIS", "severity": "Hinweis", "text": "Die Umsatzerlöse weichen ab."}
REASON = "Gutschrift vom 30. Dezember 2026, gebucht im Januar"


class AnnualFilingTestCase(Transmitting, IntegrationTestCase):
	"""The test document of the company of annual_document, its sources LINES unless a test names others."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		annual_document.install()
		annual_document.make_company_with_settings()

	def setUp(self):
		super().setUp()
		self.enterContext(annual_document.use_controller())
		self.addCleanup(annual_document.discard_all)

	def document(self, *entries, **fields):
		doc = frappe.get_doc(
			{
				"doctype": DOCTYPE,
				"company": COMPANY,
				"year": 2026,
				"source": source(*(entries or LINES)),
				**fields,
			}
		).insert()
		doc.reload()
		return doc

	def calculated(self, *entries, **fields):
		doc = self.document(*entries, **fields)
		doc.calculate()
		doc.reload()
		return doc

	def filed(self, doc, filed_via: str = "mein_elster", **values):
		doc.mark_filed_outside(filed_via, **values)
		doc.reload()
		return doc

	def lines(self, doc) -> list[tuple]:
		return [(row.key, flt(row.computed), flt(row.reported), row.manual) for row in doc.lines]


class TestDraft(AnnualFilingTestCase):
	def test_a_new_document_starts_as_a_draft_of_its_fiscal_year(self):
		doc = self.document(
			status="Abgegeben",
			ready=1,
			lines_read=7,
			filed_via="eric",
			transferticket=TICKET,
			findings=[{"severity": "Fehler", "code": "SB-X", "text": "Alt."}],
		)
		self.assertEqual((doc.status, doc.ready, doc.lines_read, doc.findings), ("Entwurf", 0, 0, []))
		self.assertFalse(doc.filed_via or doc.transferticket)
		fiscal_year = frappe.db.get_value(
			"Fiscal Year", {"year_start_date": "2026-01-01", "year_end_date": "2026-12-31"}
		)
		self.assertEqual(
			(doc.fiscal_year, getdate(doc.from_date), getdate(doc.to_date), getdate(doc.deadline)),
			(fiscal_year, date(2026, 1, 1), date(2026, 12, 31), date(2027, 7, 31)),
		)

	def test_the_fiscal_year_of_the_company_comes_before_the_one_of_every_company(self):
		"""A short first Wirtschaftsjahr beside the calendar year that serves every company: ERPNext takes the Fiscal
		Year that names the company first (_get_fiscal_years in erpnext/accounts/utils.py), and so does the document."""
		own = frappe.get_doc(
			{
				"doctype": "Fiscal Year",
				"year": "2026 Steuerbote Test Jahresmeldung",
				"year_start_date": "2026-04-01",
				"year_end_date": "2026-12-31",
				"is_short_year": 1,
				"companies": [{"company": COMPANY}],
			}
		).insert(ignore_permissions=True)
		self.addCleanup(frappe.delete_doc, "Fiscal Year", own.name, force=True, ignore_permissions=True)
		doc = self.document()
		self.assertEqual(
			(doc.fiscal_year, getdate(doc.from_date), getdate(doc.to_date)),
			(own.name, date(2026, 4, 1), date(2026, 12, 31)),
		)

	def test_a_copy_keeps_its_corrections_and_lines_by_hand_and_nothing_computed(self):
		doc = self.document(
			lines=[
				{"key": "A", "label": "Umsätze", "computed": 100, "reported": 100},
				{"key": "B", "computed": 30, "correction": 25, "correction_reason": REASON},
				{"key": "C", "manual": 1, "correction": 5, "correction_reason": "Von Hand"},
			]
		)
		self.assertEqual(self.lines(doc), [("B", 0, 25, 0), ("C", 0, 5, 1)])
		self.assertEqual(flt(doc.total), 30)

	def test_the_form_learns_the_statuses_and_the_ways_of_a_filing(self):
		state = self.document().annual_state()
		self.assertEqual(
			state,
			{
				"calculated": ["Berechnet", "Bereit"],
				"filings": ["Abgegeben"],
				"filed_outside": ["mein_elster", "other_way"],
				"submitted_by_hand": False,
				"can_correct": False,
			},
		)


class TestBerechnen(AnnualFilingTestCase):
	def test_writes_the_lines_and_makes_a_document_without_errors_ready(self):
		doc = self.calculated()
		self.assertEqual((doc.status, doc.ready, flt(doc.total), doc.lines_read), ("Bereit", 1, 130, 2))
		self.assertEqual(self.lines(doc), [("A", 100, 100, 0), ("B", 30, 30, 0)])
		self.assertEqual([row.label for row in doc.lines], ["Umsätze", "Vorsteuer"])
		self.assertEqual(doc.findings, [])

	def test_an_error_of_the_sources_leaves_it_berechnet_and_lists_the_errors_first(self):
		doc = self.calculated(*LINES, SOURCE_HINT, SOURCE_ERROR)
		self.assertEqual((doc.status, doc.ready), ("Berechnet", 0))
		self.assertEqual(
			[(row.severity, row.blocking, row.code, row.text, row.reference or "") for row in doc.findings],
			[
				("Fehler", 1, "SB-QUELLE", "Ein Konto ohne Zuordnung hat einen Saldo.", "Konto 1590"),
				("Hinweis", 0, "SB-HINWEIS", "Die Umsatzerlöse weichen ab.", ""),
			],
		)

	def test_a_hint_leaves_it_ready(self):
		doc = self.calculated(*LINES, SOURCE_HINT)
		self.assertEqual(
			(doc.status, doc.ready, [row.code for row in doc.findings]), ("Bereit", 1, ["SB-HINWEIS"])
		)

	def test_checks_the_lines_as_filed(self):
		doc = self.calculated({"key": "A", "computed": "-5.00"})
		self.assertEqual((doc.status, [row.code for row in doc.findings]), ("Berechnet", [NEGATIVE]))

	def test_keeps_the_corrections_and_the_lines_by_hand(self):
		doc = self.calculated()
		doc.lines[0].correction = 90
		doc.lines[0].correction_reason = REASON
		doc.append("lines", {"key": "C", "correction": 5, "correction_reason": "Von Hand"})
		doc.save()
		doc.source = source({"key": "A", "label": "Umsätze", "computed": "110.00"})
		doc.save()
		doc.calculate()
		doc.reload()
		self.assertEqual(self.lines(doc), [("A", 110, 90, 0), ("C", 0, 5, 1)])
		self.assertEqual(
			[(row.correction_reason, row.label or "") for row in doc.lines],
			[(REASON, "Umsätze"), ("Von Hand", "")],
		)
		self.assertEqual((doc.status, doc.ready, flt(doc.total), doc.findings), ("Bereit", 1, 95, []))

	def test_keeps_a_correction_of_a_line_it_no_longer_computes(self):
		doc = self.calculated()
		doc.lines[1].correction = 20
		doc.lines[1].correction_reason = REASON
		doc.save()
		doc.source = source(LINES[0])
		doc.save()
		doc.calculate()
		doc.reload()
		self.assertEqual(self.lines(doc), [("A", 100, 100, 0), ("B", 0, 20, 0)])

	def test_only_a_draft_is_calculated(self):
		doc = self.filed(self.calculated())
		with self.assertRaisesRegex(frappe.ValidationError, "is no draft"):
			doc.calculate()


class TestSave(AnnualFilingTestCase):
	def test_a_save_takes_only_what_the_company_enters(self):
		doc = self.calculated()
		doc.lines[0].update({"key": "Z", "label": "Anders", "computed": 999, "reported": 999, "manual": 1})
		doc.update({"status": "Abgegeben", "ready": 0, "lines_read": 7, "total": 1})
		doc.append("findings", {"severity": "Fehler", "code": "SB-X", "text": "Untergeschoben."})
		doc.save()
		doc.reload()
		self.assertEqual(self.lines(doc), [("A", 100, 100, 0), ("B", 30, 30, 0)])
		self.assertEqual(doc.lines[0].label, "Umsätze")
		self.assertEqual(
			(doc.status, doc.ready, doc.lines_read, flt(doc.total), doc.findings), ("Bereit", 1, 2, 130, [])
		)

	def test_a_changed_correction_leaves_the_document_berechnet_until_berechnen_checks_it(self):
		doc = self.calculated()
		doc.lines[0].correction = -10
		doc.lines[0].correction_reason = REASON
		doc.save()
		doc.reload()
		self.assertEqual(
			(doc.status, doc.ready, [row.code for row in doc.findings]),
			("Berechnet", 0, ["SB-NEU-BERECHNEN"]),
		)
		self.assertEqual(flt(doc.total), 20)
		doc.calculate()
		doc.reload()
		self.assertEqual((doc.status, [row.code for row in doc.findings]), ("Berechnet", [NEGATIVE]))

	def test_a_new_reason_for_the_same_amount_changes_nothing_berechnen_checked(self):
		doc = self.calculated()
		doc.lines[0].correction_reason = REASON
		doc.lines[0].correction = 100
		doc.save()
		doc.reload()
		self.assertEqual((doc.status, doc.ready), ("Bereit", 1))

	def test_a_correction_needs_a_reason(self):
		doc = self.calculated()
		doc.lines[0].correction = 90
		with self.assertRaisesRegex(frappe.ValidationError, "needs a reason"):
			doc.save()

	def test_a_line_berechnen_computed_stays(self):
		doc = self.calculated()
		doc.set("lines", doc.lines[1:])
		with self.assertRaisesRegex(frappe.ValidationError, "comes from Berechnen"):
			doc.save()

	def test_the_key_of_a_saved_document_stays_with_its_calculation(self):
		doc = self.calculated()
		before = (doc.status, doc.ready, doc.lines_read, len(doc.lines), getdate(doc.to_date))
		other = make_company("Steuerbote Test Andere Jahresmeldung GmbH", "STAJ")
		for field, value in (("year", 2027), ("company", other)):
			with self.subTest(field=field):
				doc.set(field, value)
				with self.assertRaises(frappe.CannotChangeConstantError):
					doc.save()
				doc.reload()
		self.assertEqual(
			(doc.status, doc.ready, doc.lines_read, len(doc.lines), getdate(doc.to_date)), before
		)

	def test_the_fields_of_a_berichtigung_are_set_when_it_is_made(self):
		first = self.filed(self.calculated())
		correction = frappe.get_doc(DOCTYPE, first.make_correction())
		correction.update({"is_correction": 0, "corrects": None})
		correction.save()
		correction.reload()
		self.assertEqual((correction.is_correction, correction.corrects), (1, first.name))


class TestFiling(AnnualFilingTestCase):
	def test_buchen_alone_files_nothing(self):
		doc = self.calculated()
		with self.assertRaisesRegex(frappe.ValidationError, "not by Buchen alone"):
			doc.submit()

	def test_the_note_of_a_filing_files_the_document_with_how_when_and_by_whom(self):
		yesterday = add_days(today(), -1)
		doc = self.filed(self.calculated(), transferticket=MEIN_ELSTER_TICKET, filed_on=yesterday)
		self.assertEqual(
			(
				doc.docstatus,
				doc.status,
				doc.filed_via,
				getdate(doc.filed_on),
				doc.transferticket,
				doc.filed_by,
			),
			(1, "Abgegeben", "mein_elster", getdate(yesterday), MEIN_ELSTER_TICKET, frappe.session.user),
		)
		record = frappe.get_doc(TRANSMISSION, {"document_type": DOCTYPE, "document": doc.name})
		self.assertEqual(
			(record.operation, record.status, record.filed_via, record.transferticket, record.simulated),
			("extern", "Erfolgreich", "mein_elster", MEIN_ELSTER_TICKET, 0),
		)
		self.assertTrue(doc.annual_state()["can_correct"])

	def test_another_way_needs_a_note_of_how_and_when(self):
		doc = self.calculated()
		with self.assertRaisesRegex(frappe.ValidationError, "Note how and when"):
			doc.mark_filed_outside("other_way")
		doc = self.filed(doc, "other_way", note="Von der Steuerberatung abgegeben")
		self.assertEqual((doc.filed_via, doc.filing_note), ("other_way", "Von der Steuerberatung abgegeben"))

	def test_refuses_a_way_it_does_not_know_a_ticket_of_another_shape_and_a_day_to_come(self):
		doc = self.calculated()
		for values, message in (
			({"filed_via": "fax"}, "knows no way of filing"),
			({"filed_via": "mein_elster", "transferticket": "123"}, "is no Transferticket"),
			({"filed_via": "mein_elster", "filed_on": add_days(today(), 1)}, "in the future"),
		):
			with self.subTest(values=values), self.assertRaisesRegex(frappe.ValidationError, message):
				doc.mark_filed_outside(**values)

	def test_a_draft_is_calculated_before_it_is_filed(self):
		doc = self.document()
		with self.assertRaisesRegex(frappe.ValidationError, "before filing it"):
			doc.mark_filed_outside("mein_elster")

	def test_a_document_that_is_not_ready_is_filed_with_its_remarks(self):
		doc = self.calculated(*LINES, SOURCE_ERROR)
		with self.assertRaisesRegex(frappe.ValidationError, "is not ready"):
			doc.mark_filed_outside("mein_elster")
		doc.reload()
		doc.remarks = "Das Konto 1590 ist mit der Steuerberatung abgestimmt."
		doc.save()
		self.assertEqual(self.filed(doc).status, "Abgegeben")

	def test_a_filed_document_is_not_cancelled(self):
		doc = self.filed(self.calculated())
		with self.assertRaisesRegex(frappe.ValidationError, "cannot be cancelled"):
			doc.cancel()

	def test_amounts_changed_past_the_save_are_found_before_a_filing(self):
		doc = self.calculated()
		frappe.db.set_value(LINE_DOCTYPE, doc.lines[0].name, {"correction": 50, "correction_reason": REASON})
		with self.assertRaisesRegex(frappe.ValidationError, "do not agree with its lines as stored"):
			doc.mark_filed_outside("mein_elster")


class TestOneFilingPerKey(AnnualFilingTestCase):
	def test_a_key_holds_one_draft(self):
		first = self.document()
		with self.assertRaisesRegex(
			frappe.ValidationError, f"{first.name} is a draft for the same company and year already"
		):
			self.document()

	def test_a_filed_key_takes_a_berichtigung_only(self):
		first = self.filed(self.calculated())
		with self.assertRaisesRegex(
			frappe.ValidationError, f"{first.name} is filed already for the same company and year"
		):
			self.document()

	def test_berichtigung_anlegen_makes_a_calculated_berichtigung_with_the_corrections(self):
		first = self.calculated()
		first.lines[0].correction = 90
		first.lines[0].correction_reason = REASON
		first.save()
		first.calculate()
		first = self.filed(frappe.get_doc(DOCTYPE, first.name))
		correction = frappe.get_doc(DOCTYPE, first.make_correction())
		self.assertEqual(
			(correction.is_correction, correction.corrects, correction.status, correction.docstatus),
			(1, first.name, "Bereit", 0),
		)
		self.assertEqual(self.lines(correction), [("A", 100, 90, 0), ("B", 30, 30, 0)])
		self.filed(correction)
		first.reload()
		self.assertEqual((first.status, correction.status), ("Ersetzt", "Abgegeben"))

	def test_a_berichtigung_is_made_from_a_filed_document(self):
		doc = self.calculated()
		with self.assertRaisesRegex(frappe.ValidationError, "A Berichtigung is made from a filed document"):
			doc.make_correction()

	def test_a_berichtigung_waits_for_a_draft_of_the_key(self):
		first = self.filed(self.calculated())
		draft = frappe.get_doc(DOCTYPE, first.make_correction())
		with self.assertRaisesRegex(
			frappe.ValidationError, f"{draft.name} is a draft for the same company and year already"
		):
			first.make_correction()

	def test_a_berichtigung_corrects_a_filed_document_of_its_key(self):
		draft = self.document()
		for corrects in (draft.name, None):
			with (
				self.subTest(corrects=corrects),
				self.assertRaisesRegex(
					frappe.ValidationError,
					"A Berichtigung corrects a filed document for the same company and year",
				),
			):
				self.document(is_correction=1, corrects=corrects)


class TestStatusDesBerichts(AnnualFilingTestCase):
	"""The Status des Berichts of a document of the Datenart Bilanz in its field revision_status (FAQ zur E-Bilanz,
	Version 2026-01, Tz. 4 d), and the Berichtigung of each Datenart."""

	def test_the_first_e_bilanz_is_erstmalig(self):
		doc = self.calculated(kind="Bilanz")
		self.assertEqual(doc.revision_status, "E")
		self.assertIs(doc.berichtigung(), corrections.BILANZ)

	def test_a_first_e_bilanz_names_no_status_of_a_berichtigung(self):
		with self.assertRaisesRegex(frappe.ValidationError, "The first E-Bilanz is erstmalig"):
			self.document(kind="Bilanz", revision_status="B")

	def test_a_berichtigung_names_its_status_by_the_time_it_is_filed(self):
		note = "Von der Steuerberatung übermittelt"
		first = self.filed(self.calculated(kind="Bilanz"), "other_way", note=note)
		correction = frappe.get_doc(DOCTYPE, first.make_correction())
		self.assertFalse(correction.revision_status)
		with self.assertRaisesRegex(frappe.ValidationError, "names its Status des Berichts"):
			correction.mark_filed_outside("other_way", note=note)
		correction.reload()
		correction.revision_status = "B"
		correction.save()
		correction = self.filed(correction, "other_way", note=note)
		self.assertEqual((correction.status, correction.revision_status), ("Abgegeben", "B"))

	def test_the_correction_by_the_tax_administration_is_not_for_a_filing(self):
		with self.assertRaisesRegex(
			frappe.ValidationError, "Korrektur durch Finanzverwaltung, is not for a filing"
		):
			self.document(kind="Bilanz", revision_status="K")

	def test_an_erklaerung_has_no_status_des_berichts(self):
		doc = self.calculated()
		self.assertIs(doc.berichtigung(), corrections.KST)
		self.assertFalse(doc.revision_status)


class TestWhatAModuleCalls(AnnualFilingTestCase):
	"""What a module calls of the base for its own actions, such as XBRL exportieren of the E-Bilanz."""

	def test_a_file_is_made_of_a_document_that_could_be_filed_or_is_filed(self):
		doc = self.document()
		with self.assertRaisesRegex(frappe.ValidationError, "before filing it"):
			doc.require_fit_for_export()
		doc.calculate()
		doc.reload()
		doc.require_fit_for_export()
		self.filed(doc).require_fit_for_export()

	def test_a_file_waits_for_the_remarks_of_a_document_that_is_not_ready(self):
		doc = self.calculated(*LINES, SOURCE_ERROR)
		with self.assertRaisesRegex(frappe.ValidationError, "is not ready"):
			doc.require_fit_for_export()

	def test_no_file_is_made_of_a_document_that_elster_may_have(self):
		doc = self.calculated()
		doc.new_transmission("send", simulated=False, status="Unbekannt")
		with self.assertRaisesRegex(frappe.ValidationError, "is unknown"):
			doc.require_fit_for_export()

	def test_no_file_is_made_of_amounts_changed_past_the_save(self):
		doc = self.calculated()
		frappe.db.set_value(LINE_DOCTYPE, doc.lines[0].name, {"correction": 50, "correction_reason": REASON})
		with self.assertRaisesRegex(frappe.ValidationError, "do not agree with its lines as stored"):
			frappe.get_doc(DOCTYPE, doc.name).require_fit_for_export()

	def test_no_file_is_made_of_a_cancelled_document(self):
		doc = self.calculated()
		frappe.db.set_value(DOCTYPE, doc.name, "docstatus", 2)
		with self.assertRaisesRegex(frappe.ValidationError, "is cancelled and makes no file"):
			frappe.get_doc(DOCTYPE, doc.name).require_fit_for_export()

	def test_names_the_lines_by_hand_for_a_module_whose_computation_takes_them_in(self):
		doc = self.calculated()
		doc.append("lines", {"key": "C", "correction": 5, "correction_reason": "Von Hand"})
		doc.save()
		self.assertEqual(doc.manual_lines(), (overrides.ManualLine("C", Decimal("5.00"), "Von Hand"),))


INCLUDES = "steuerbote/templates/includes/annual_filing"
# A print format of a module in short: the shared parts around a line of its own in the head.
PRINT_FORMAT = (
	"{% set annual = doc.annual_print() %}"
	f'{{% include "{INCLUDES}/style.html" %}}'
	'<div class="sb-annual">'
	'{% set head_rows = [("Finanzamt", "München")] %}'
	f'{{% include "{INCLUDES}/head.html" %}}'
	f'{{% include "{INCLUDES}/corrections.html" %}}'
	f'{{% include "{INCLUDES}/findings.html" %}}'
	f'{{% include "{INCLUDES}/remarks.html" %}}'
	f'{{% include "{INCLUDES}/footer.html" %}}'
	"</div>"
)


def cells(markup: str) -> str:
	"""The printed text with every table cell closed by " |", so that a line reads as one string."""
	text = re.sub(r"<(style|script)\b.*?</\1>", " ", markup, flags=re.DOTALL | re.IGNORECASE)
	text = re.sub(r"</t[dh]>", " |", text)
	text = re.sub(r"<br\s*/?>", " ", text)
	text = re.sub(r"<[^>]+>", " ", text)
	return re.sub(r"\s+", " ", html.unescape(text))


class TestPrint(AnnualFilingTestCase):
	"""The shared parts of the print formats, templates/includes/annual_filing, on the test document."""

	def printed(self, doc) -> str:
		return cells(frappe.render_template(PRINT_FORMAT, {"doc": doc}))

	def test_the_head_names_company_steuernummer_year_due_date_and_document(self):
		doc = self.calculated()
		elster = frappe.db.get_value("VAT Return Settings", COMPANY, "elster_tax_number")
		text = self.printed(doc)
		for expected in (
			f"Unternehmen | {COMPANY} |",
			"Steuernummer | 123/456/78901 |",
			f"Steuernummer im ELSTER-Format | {elster} |",
			"Jahr | 2026 |",
			"Geschäftsjahr | 01.01.2026 bis 31.12.2026 |",
			"Fällig am | 31.07.2027 |",
			"Finanzamt | München |",
			f"Beleg | {doc.name}, Bereit |",
		):
			with self.subTest(expected=expected):
				self.assertIn(expected, text)
		for missing in ("Berichtigung zu", "Abgegeben am", "Korrekturen", "Befunde", "Anmerkungen"):
			with self.subTest(missing=missing):
				self.assertNotIn(missing, text)

	def test_lists_the_corrections_the_lines_by_hand_the_findings_and_the_remarks(self):
		doc = self.calculated(*LINES, SOURCE_ERROR)
		doc.lines[0].correction = 90
		doc.lines[0].correction_reason = REASON
		doc.append("lines", {"key": "C", "correction": 5, "correction_reason": "Von Hand"})
		doc.remarks = "Mit der Steuerberatung abgestimmt."
		doc.save()
		text = self.printed(doc)
		for expected in (
			"Korrekturen und Zeilen von Hand",
			f"A | Umsätze | 100,00 | 90,00 | {REASON} |",
			"C | Zeile von Hand | | 5,00 | Von Hand |",
			"Befunde",
			"Fehler | SB-NEU-BERECHNEN |",
			"Fehler | SB-QUELLE | Ein Konto ohne Zuordnung hat einen Saldo. | Konto 1590 |",
			"Anmerkungen Mit der Steuerberatung abgestimmt.",
		):
			with self.subTest(expected=expected):
				self.assertIn(expected, text)

	def test_a_filed_berichtigung_names_what_it_corrects_and_how_and_when_it_was_filed(self):
		first = self.filed(self.calculated())
		correction = self.filed(frappe.get_doc(DOCTYPE, first.make_correction()))
		text = self.printed(correction)
		self.assertIn(f"Beleg | {correction.name}, Abgegeben |", text)
		self.assertIn(f"Berichtigung zu | {first.name} |", text)
		self.assertIn(f"Abgegeben am | {getdate(today()):%d.%m.%Y}, in Mein ELSTER |", text)

	def test_the_footer_leaves_mein_elster_out_for_the_e_bilanz_and_names_the_offenlegung_of_the_jahresabschluss(
		self,
	):
		doc = self.calculated()
		self.assertIn(
			"Zum Abgleich mit der Steuerberatung oder zum Übertragen in Mein ELSTER.", self.printed(doc)
		)
		self.assertIn("Dieser Ausdruck ist keine Abgabe.", self.printed(doc))
		doc.FILED_OUTSIDE = ("other_way",)
		text = self.printed(doc)
		self.assertIn("Zum Abgleich mit der Steuerberatung.", text)
		self.assertNotIn("Mein ELSTER", text)
		doc.LIFECYCLE = lifecycle.ACCOUNTS
		self.assertIn("Dieser Ausdruck ist keine Offenlegung.", self.printed(doc))

	def test_the_footer_ends_with_the_version_of_steuerbote_that_printed_it(self):
		self.assertTrue(
			self.printed(self.calculated()).rstrip().endswith(f"Erstellt mit Steuerbote {__version__}")
		)


class TestJahresabschluss(AnnualFilingTestCase):
	"""The lifecycle ACCOUNTS of the Jahresabschluss on its test document: Buchen is the Feststellung, the Übermittlung
	to the Unternehmensregister and the Einstellung follow it, and a change is a cancellation and an amendment
	(§ 42a Abs. 2 GmbHG, § 325 Abs. 1b HGB)."""

	def accounts(self, *entries, **fields):
		doc = frappe.get_doc(
			{
				"doctype": ACCOUNTS_DOCTYPE,
				"company": COMPANY,
				"year": 2026,
				"source": source(*(entries or LINES)),
				**fields,
			}
		).insert()
		doc.calculate()
		doc.reload()
		return doc

	def adopted(self):
		doc = self.accounts()
		doc.submit()
		doc.reload()
		return doc

	def test_buchen_adopts_a_calculated_jahresabschluss(self):
		doc = self.accounts()
		self.assertEqual((doc.status, doc.ready), ("Berechnet", 1))
		doc.submit()
		doc.reload()
		self.assertEqual((doc.docstatus, doc.status), (1, "Festgestellt"))

	def test_a_draft_is_calculated_before_its_feststellung(self):
		doc = frappe.get_doc(
			{"doctype": ACCOUNTS_DOCTYPE, "company": COMPANY, "year": 2026, "source": source(*LINES)}
		).insert()
		with self.assertRaisesRegex(frappe.ValidationError, "before filing it"):
			doc.submit()

	def test_the_uebermittlung_and_the_einstellung_follow_the_feststellung(self):
		doc = self.adopted()
		self.assertEqual(
			doc.move_on(lifecycle.Event.TRANSMIT, filed_via="upload", note="Auftrag 2027-0815"), "Übermittelt"
		)
		doc.reload()
		self.assertEqual(
			(doc.status, doc.filed_via, getdate(doc.filed_on), doc.filing_note, doc.filed_by),
			("Übermittelt", "upload", getdate(today()), "Auftrag 2027-0815", frappe.session.user),
		)
		doc.move_on(lifecycle.Event.PUBLISH)
		doc.reload()
		self.assertEqual((doc.docstatus, doc.status, doc.filed_via), (1, "Eingestellt", "upload"))

	def test_moves_on_only_as_its_lifecycle_does_and_only_once_adopted(self):
		doc = self.accounts()
		with self.assertRaisesRegex(frappe.ValidationError, "is not submitted, so its status stays"):
			doc.move_on(lifecycle.Event.TRANSMIT)
		doc.submit()
		doc.reload()
		for event in (lifecycle.Event.PUBLISH, lifecycle.Event.FILE, lifecycle.Event.CALCULATE):
			with (
				self.subTest(event=event),
				self.assertRaisesRegex(frappe.ValidationError, "cannot change from Festgestellt"),
			):
				doc.move_on(event)
		for values, message in (
			({"filed_via": "fax"}, "knows no way of filing"),
			({"filed_via": "upload", "filed_on": add_days(today(), 1)}, "in the future"),
		):
			with self.subTest(values=values), self.assertRaisesRegex(frappe.ValidationError, message):
				doc.move_on(lifecycle.Event.TRANSMIT, **values)
		self.assertEqual(
			frappe.db.get_value(ACCOUNTS_DOCTYPE, doc.name, ["status", "filed_via"]), ("Festgestellt", None)
		)

	def test_a_changed_jahresabschluss_is_cancelled_and_amended_and_the_amendment_replaces_it(self):
		first = self.adopted()
		first.cancel()
		amendment = frappe.copy_doc(first)
		amendment.update({"docstatus": 0, "amended_from": first.name})
		amendment.insert()
		self.assertEqual((amendment.status, amendment.ready, amendment.findings), ("Entwurf", 0, []))
		amendment.calculate()
		amendment.reload()
		amendment.submit()
		first.reload()
		self.assertEqual((first.docstatus, first.status), (2, "Ersetzt"))
		self.assertEqual((amendment.docstatus, amendment.status), (1, "Festgestellt"))

	def test_changes_by_stornieren_and_berichtigen_and_not_by_a_berichtigung_of_its_own(self):
		doc = self.adopted()
		self.assertFalse(doc.annual_state()["can_correct"])
		with self.assertRaisesRegex(frappe.ValidationError, "changes by Stornieren and Berichtigen"):
			doc.make_correction()
		with self.assertRaisesRegex(frappe.ValidationError, "changes by Stornieren and Berichtigen"):
			frappe.get_doc(
				{
					"doctype": ACCOUNTS_DOCTYPE,
					"company": COMPANY,
					"year": 2026,
					"is_correction": 1,
					"corrects": doc.name,
				}
			).insert()

	def test_goes_to_no_finanzamt_and_is_disclosed_again_when_it_changes(self):
		doc = self.accounts()
		self.assertEqual(
			doc.annual_state(),
			{
				"calculated": ["Berechnet"],
				"filings": ["Festgestellt", "Übermittelt", "Eingestellt"],
				"filed_outside": [],
				"submitted_by_hand": True,
				"can_correct": False,
			},
		)
		self.assertIs(doc.berichtigung(), corrections.OFFENLEGUNG)
		with self.assertRaisesRegex(frappe.ValidationError, "does not go to the Finanzamt"):
			doc.mark_filed_outside("other_way", note="Von der Steuerberatung übermittelt")

	def test_the_print_is_no_offenlegung(self):
		doc = self.adopted()
		text = cells(frappe.render_template(PRINT_FORMAT, {"doc": doc}))
		self.assertIn(f"Beleg | {doc.name}, Festgestellt |", text)
		self.assertIn("Dieser Ausdruck ist keine Offenlegung.", text)
		self.assertNotIn("Mein ELSTER", text)

"""The Jahresabschluss on the Frappe test site, with the invented companies of steuerbote/tests/annual_accounts.py and
the HGB-Taxonomie 6.9: Berechnen of a Kleinstkapitalgesellschaft and of a small company, the size class and the
Arbeitnehmer by hand, the corrections, each check that holds the Feststellung back, the Feststellung with its day in
the Annual Filing Settings, cancelling and amending, the Ergebnisverwendung, the Übermittlung and the Einstellung, the
print format with its Vorschau der Offenlegung as PDF, and the XBRL for the Unternehmensregister. Every name, number and
amount is invented.
"""

from datetime import date
from decimal import Decimal

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import flt, getdate

from steuerbote.steuerbote.doctype.annual_accounts import layout
from steuerbote.tests import annual_accounts as data
from steuerbote.tests.annual_accounts import KLEIN, KLEINST, blocking, codes, line

# The tests make the companies, their accounts, Fiscal Years, employees, Journal Entries and the custom field of the
# Employee themselves, and need no test records of users or DocTypes.
IGNORE_TEST_RECORD_DEPENDENCIES = [
	"Account",
	"Annual Accounts",
	"Company",
	"Custom Field",
	"DocType",
	"Employee",
	"Fiscal Year",
	"Journal Entry",
	"User",
]

DOCTYPE = data.DOCTYPE
PRINT_FORMAT = "Jahresabschluss"
REMARKS = "Mit der Steuerberatung abgestimmt."
FIXED_ASSETS = "bs.ass.fixAss"
CURRENT_ASSETS = "bs.ass.currAss"
EQUITY = "bs.eqLiab.equity"
NET_INCOME = "bs.eqLiab.equity.netIncome"


def money(value: object) -> Decimal:
	return Decimal(str(flt(value, 2))).quantize(Decimal("0.01"))


def d(value: str) -> Decimal:
	return Decimal(value)


class TestAnnualAccounts(IntegrationTestCase):
	"""One class, so that the companies and their books are made once; each test removes its Jahresabschlüsse and sets
	back what it changed."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		data.employment_type_field()
		cls.enterClassContext(data.installed_taxonomy())
		cls.accounts = {company: data.make_company_with_books(company) for company in (KLEINST, KLEIN)}

	def setUp(self):
		super().setUp()
		for company in (KLEINST, KLEIN):
			self.addCleanup(data.discard, company)

	def refused(self, doc, pattern: str, step=None):
		"""The step, submitting by default, is refused with the message; the document is read again, since a refused
		save leaves it with the timestamp of before."""
		with self.assertRaisesRegex(frappe.ValidationError, pattern):
			(step or doc.submit)()
		doc.reload()

	def corrected(self, doc, corrections: dict[str, str]):
		for concept, amount in corrections.items():
			row = line(doc, concept)
			row.correction = amount
			row.correction_reason = "Inventur zum Abschlussstichtag"
		doc.save()
		doc.calculate()
		doc.reload()
		return doc

	# Berechnen.

	def test_a_year_without_its_schemes_is_refused_when_it_is_made(self):
		"""As the Erklärungen refuse a year without their forms: no draft that Berechnen could not calculate."""
		for year in (2025, 2027):
			with (
				self.subTest(year=year),
				self.assertRaisesRegex(
					frappe.ValidationError, f"Steuerbote has no Jahresabschluss for {year} yet"
				),
			):
				data.new_accounts(KLEINST, year=year)

	def test_berechnen_decides_a_kleinstkapitalgesellschaft_and_builds_its_bilanz(self):
		doc = data.calculated(KLEINST)
		self.assertEqual(
			(doc.status, doc.ready, doc.size_class, doc.size_class_computed, doc.legal_form),
			("Berechnet", 0, "Kleinst", "Kleinst", "GmbH"),
		)
		self.assertEqual(
			{
				field: money(doc.get(field))
				for field in ("bilanzsumme", "umsatzerloese", "net_income", "equity")
			},
			{
				"bilanzsumme": d("65620.00"),
				"umsatzerloese": d("120000.00"),
				"net_income": d("21200.00"),
				"equity": d("58300.00"),
			},
		)
		self.assertEqual(money(doc.carried_forward), d("12100.00"))
		self.assertEqual(
			(doc.has_prior, getdate(doc.prior_from_date), getdate(doc.prior_to_date)),
			(1, date(2025, 1, 1), date(2025, 12, 31)),
		)
		self.assertEqual(
			(money(doc.prior_bilanzsumme), money(doc.prior_umsatzerloese), doc.prior_criteria_source),
			(d("37100.00"), d("60000.00"), "Hauptbuch des Vorjahres"),
		)
		shown = [
			(row.statement, row.marker, money(row.reported), money(row.prior))
			for row in doc.lines
			if row.shown and row.statement != "GuV"
		]
		self.assertEqual(
			shown,
			[
				("Aktiva", "A.", d("18000.00"), d("0.00")),
				("Aktiva", "B.", d("47620.00"), d("37100.00")),
				("Aktiva", "", d("65620.00"), d("37100.00")),
				("Passiva", "A.", d("58300.00"), d("37100.00")),
				("Passiva", "B.", d("1800.00"), d("0.00")),
				("Passiva", "C.", d("5520.00"), d("0.00")),
				("Passiva", "", d("5520.00"), d("0.00")),
				("Passiva", "", d("65620.00"), d("37100.00")),
			],
		)
		self.assertIn("1200 - Bank", line(doc, CURRENT_ASSETS).sources)
		self.assertEqual(
			[row.code for row in doc.notes], ["HAFTUNGSVERHAELTNISSE", "ORGANKREDITE", "ZUSAETZLICHE-ANGABEN"]
		)
		(signatory,) = doc.signatories
		self.assertEqual(
			(signatory.signatory_name, signatory.function, signatory.place, signatory.signed_on),
			(data.DIRECTOR, data.DIRECTOR_ROLE, data.SEAT, None),
		)
		self.assertEqual(
			(doc.firma, doc.sitz, doc.register_court, doc.register_number),
			(KLEINST.name, data.SEAT, data.COURT, "HRB 99901"),
		)
		self.assertEqual(
			(doc.disclosure_mode, doc.presentation), ("Hinterlegung", "vor Verwendung des Jahresergebnisses")
		)
		self.assertIn("BILANZ-ERGEBNISVORTRAG", codes(doc))
		self.assertEqual(
			sorted(set(blocking(doc))),
			["JA-ANGABE-OFFEN", "JA-NICHT-FESTGESTELLT", "JA-UNTERSCHRIFT-OHNE-DATUM"],
		)

	def test_berechnen_decides_a_small_company_with_its_anhang(self):
		doc = data.calculated(KLEIN)
		self.assertEqual(
			(doc.size_class, doc.size_class_computed, doc.disclosure_mode),
			("Klein", "Klein", "Veröffentlichung"),
		)
		self.assertTrue(doc.size_basis)
		self.assertEqual(
			(money(doc.bilanzsumme), money(doc.umsatzerloese), money(doc.net_income), money(doc.equity)),
			(d("714000.00"), d("1200000.00"), d("110000.00"), d("235000.00")),
		)
		self.assertEqual(money(line(doc, NET_INCOME).reported), d("110000.00"))
		self.assertIn("II.", [row.marker for row in doc.lines if row.statement == "Aktiva" and row.shown])
		notes = {row.code: row for row in doc.notes}
		self.assertTrue({"BEWERTUNGSMETHODEN", "ARBEITNEHMER", "AUSSERGEWOEHNLICHES"} <= set(notes))
		self.assertEqual((notes["ARBEITNEHMER"].answer, notes["AUSSERGEWOEHNLICHES"].published), ("ja", 0))
		data.answer(doc)
		doc = data.adopted(doc)
		self.assertEqual(blocking(doc), [])
		self.assertEqual(doc.ready, 1)

	def test_without_a_class_in_the_settings_the_feststellung_is_due_by_the_class_berechnen_applies(self):
		"""A small company has eleven months for the Feststellung (§ 42a Abs. 2 Satz 1 GmbHG); where the settings name no
		class for the Abschlussstichtag, the class the Jahresabschluss applies gives the deadline, not eight months."""
		doc = data.calculated(KLEINST)
		self.assertEqual(doc.size_class, "Kleinst")
		self.assertIn("JA-GROESSE-EINSTELLUNGEN", codes(doc))
		self.assertEqual(getdate(doc.deadline), date(2027, 11, 30))

	def test_the_size_class_and_the_arbeitnehmer_by_hand_count_with_their_reason(self):
		doc = data.calculated(KLEINST)
		doc.size_class_override = "Klein"
		with self.assertRaisesRegex(frappe.ValidationError, "by hand needs its reason"):
			doc.save()
		doc.reload()
		doc.size_class_override = "Klein"
		doc.size_class_override_reason = "Die Gesellschaft stellt freiwillig den Abschluss einer kleinen auf."
		doc.employees_override = 0
		doc.employees_override_reason = "Die Geschäftsführerin ist keine Arbeitnehmerin."
		doc.save()
		self.assertEqual(doc.status, "Berechnet")
		self.assertIn("SB-NEU-BERECHNEN", codes(doc))
		doc.calculate()
		doc.reload()
		self.assertEqual((doc.size_class_computed, doc.size_class), ("Kleinst", "Klein"))
		self.assertIn("JA-GROESSENKLASSE-HAND", codes(doc))
		self.assertIn("JA-ARBEITNEHMER-HAND", codes(doc))
		self.assertIn("ARBEITNEHMER", [row.code for row in doc.notes])

	def test_the_arbeitnehmer_are_those_of_the_quarter_ends_without_the_types_not_counted(self):
		data.employ(KLEINST, 1, "2025-01-01")
		data.employ(KLEINST, 2, "2026-07-01")
		data.employ(KLEINST, 3, "2025-08-01", kind="Apprentice")
		data.employ(KLEINST, 4, "2025-01-01", relieved="2026-04-30")
		data.change_settings(self, KLEINST, excluded_employment_types=[{"employment_type": "Apprentice"}])
		doc = data.calculated(KLEINST)
		self.assertEqual(flt(doc.employees_counted), 1.75)
		self.assertEqual(doc.headcount_detail, "31.03.2026: 2; 30.06.2026: 1; 30.09.2026: 2; 31.12.2026: 2")
		self.assertEqual(flt(doc.employees), 1.75)
		self.assertNotIn("JA-ARBEITNEHMER-ART", codes(doc))
		doc.employees_override = 3
		doc.employees_override_reason = "Zwei Teilzeitkräfte zählen nach Köpfen."
		doc.save()
		doc.calculate()
		doc.reload()
		self.assertEqual((flt(doc.employees_counted), flt(doc.employees)), (1.75, 3.0))
		self.assertIn("JA-ARBEITNEHMER-HAND", codes(doc))

	def test_a_correction_moves_the_totals_and_only_a_line_that_takes_balances_takes_one(self):
		doc = data.calculated(KLEINST)
		total = line(doc, "bs.ass")
		self.assertEqual(total.takes_correction, 0)
		total.correction = 1
		total.correction_reason = "Versuch"
		with self.assertRaisesRegex(frappe.ValidationError, "takes no correction"):
			doc.save()
		doc.reload()
		doc = self.corrected(doc, {FIXED_ASSETS: "19000", "bs.eqLiab.accruals": "2800"})
		self.assertEqual(
			(money(line(doc, FIXED_ASSETS).reported), money(line(doc, "bs.ass").reported)),
			(d("19000.00"), d("66620.00")),
		)
		self.assertEqual(money(line(doc, "bs.eqLiab").reported), d("66620.00"))
		self.assertEqual(money(doc.equity), d("58300.00"))

	# The Feststellung.

	def test_the_feststellung_records_its_day_in_the_settings(self):
		doc = data.ready_for_the_feststellung(KLEINST)
		self.assertEqual((doc.status, doc.ready, blocking(doc)), ("Berechnet", 1, []))
		with self.freeze_time(data.AFTER_ADOPTION):
			doc.submit()
		self.assertEqual(doc.status, "Festgestellt")
		self.assertEqual(adopted_in_settings(KLEINST), date(2027, 5, 12))

	def test_a_changed_jahresabschluss_is_cancelled_amended_and_festgestellt_again(self):
		doc = data.ready_for_the_feststellung(KLEINST)
		with self.freeze_time(data.AFTER_ADOPTION):
			doc.submit()
			doc.cancel()
		self.assertIsNone(adopted_in_settings(KLEINST))
		amended = frappe.copy_doc(doc)
		amended.update({"docstatus": 0, "amended_from": doc.name})
		amended.insert()
		self.assertEqual((amended.adopted_on, amended.status), (None, "Entwurf"))
		self.assertEqual([row.signed_on for row in amended.signatories], [None])
		self.assertEqual({row.answer for row in amended.notes}, {"nein"})
		amended.calculate()
		amended.reload()
		amended = data.adopted(amended, "2027-05-19")
		with self.freeze_time(data.AFTER_ADOPTION):
			amended.submit()
		self.assertEqual(frappe.db.get_value(DOCTYPE, doc.name, "status"), "Ersetzt")
		self.assertEqual(adopted_in_settings(KLEINST), date(2027, 5, 19))

	def test_without_the_day_of_the_feststellung_nothing_is_festgestellt(self):
		doc = data.calculated(KLEINST, remarks=REMARKS)
		data.answer(doc)
		doc.reload()
		doc.calculate()
		doc.reload()
		self.refused(doc, "Enter the day of the Feststellung")

	def test_aktiva_and_passiva_apart_hold_the_feststellung(self):
		doc = data.ready_for_the_feststellung(KLEINST, remarks=REMARKS)
		doc = self.corrected(doc, {FIXED_ASSETS: "19000"})
		self.assertIn("JA-BILANZ-UNGLEICH", blocking(doc))
		with self.freeze_time(data.AFTER_ADOPTION):
			self.refused(doc, r"Aktiva of 66\.620,00 € and Passiva of 65\.620,00 € differ")

	def test_a_jahresergebnis_of_the_bilanz_other_than_that_of_the_guv_holds_the_feststellung(self):
		"""As a line written outside Steuerbote would hold it: Berechnen keeps both the same."""
		doc = data.ready_for_the_feststellung(KLEIN, remarks=REMARKS)
		row = line(doc, NET_INCOME)
		frappe.db.set_value(row.doctype, row.name, {"amount": 100000, "reported": 100000})
		doc.reload()
		with self.freeze_time(data.AFTER_ADOPTION):
			self.refused(
				doc, r"The Jahresergebnis of the Bilanz, 100\.000,00 €, is not that of the GuV, 110\.000,00 €"
			)

	def test_missing_data_of_264_abs_1a_hold_the_feststellung(self):
		data.change_settings(self, KLEINST, register_number="")
		doc = data.ready_for_the_feststellung(KLEINST, remarks=REMARKS)
		self.assertFalse(doc.register_number)
		self.assertIn("JA-REGISTERANGABEN", blocking(doc))
		with self.freeze_time(data.AFTER_ADOPTION):
			self.refused(doc, "Registernummer")

	def test_an_angabe_not_answered_holds_the_feststellung(self):
		doc = data.ready_for_the_feststellung(KLEINST, {"ORGANKREDITE": ("", "", 0)}, remarks=REMARKS)
		self.assertIn("JA-ANGABE-OFFEN", blocking(doc))
		with self.freeze_time(data.AFTER_ADOPTION):
			self.refused(doc, "The Angaben are not complete")

	def test_an_eigenkapital_of_zero_needs_its_explanation(self):
		doc = data.ready_for_the_feststellung(KLEINST, remarks=REMARKS)
		doc = self.corrected(doc, {FIXED_ASSETS: "0", CURRENT_ASSETS: "7320", EQUITY: "0"})
		self.assertEqual(money(doc.equity), d("0.00"))
		notes = {row.code: row for row in doc.notes}
		self.assertEqual(notes["EIGENKAPITAL-NULL"].requirement, "Pflicht")
		notes["EIGENKAPITAL-NULL"].answer = "nein"
		doc.save()
		doc.calculate()
		doc.reload()
		with self.freeze_time(data.AFTER_ADOPTION):
			self.refused(doc, "The Eigenkapital is zero")

	# The steps after the Feststellung.

	def test_the_ergebnisverwendung_is_a_draft_journal_entry_on_the_day_of_the_feststellung(self):
		doc = data.ready_for_the_feststellung(KLEINST, appropriation_dividend=5000)
		self.assertEqual(money(doc.appropriation_carried), d("28300.00"))
		self.refused(doc, "follows the Feststellung", doc.make_appropriation_entry)
		with self.freeze_time(data.AFTER_ADOPTION):
			doc.submit()
			name = doc.make_appropriation_entry()
		entry = frappe.get_doc("Journal Entry", name)
		accounts = self.accounts[KLEINST]
		self.assertEqual((entry.docstatus, getdate(entry.posting_date)), (0, date(2027, 5, 12)))
		self.assertEqual(
			sorted(
				(row.account, money(row.debit_in_account_currency), money(row.credit_in_account_currency))
				for row in entry.accounts
			),
			sorted(
				[
					(accounts["0860"], d("5000.00"), d("0.00")),
					(accounts["0755"], d("0.00"), d("5000.00")),
				]
			),
		)
		with self.assertRaisesRegex(frappe.ValidationError, "holds the Ergebnisverwendung proposed before"):
			doc.make_appropriation_entry()

	def test_the_draft_of_the_ergebnisverwendung_may_be_deleted_to_make_it_again(self):
		doc = data.ready_for_the_feststellung(KLEINST, appropriation_dividend=5000)
		with self.freeze_time(data.AFTER_ADOPTION):
			doc.submit()
			name = doc.make_appropriation_entry()
			frappe.delete_doc("Journal Entry", name)
			self.assertIsNone(frappe.db.get_value(doc.doctype, doc.name, "appropriation_entry"))
			again = doc.make_appropriation_entry()
		self.assertNotEqual(again, name)

	def test_the_uebermittlung_and_the_einstellung_move_the_festgestellter_jahresabschluss_on(self):
		doc = data.ready_for_the_feststellung(KLEINST)
		with self.freeze_time(data.AFTER_ADOPTION):
			doc.submit()
			with self.assertRaisesRegex(frappe.ValidationError, "box ticked"):
				doc.record_transmission("2027-05-20", "Erika Beispiel", "A-2027-000123")
			status = doc.record_transmission(
				"2027-05-20", "Erika Beispiel", "A-2027-000123", kleinst_notice=1, fees=21.5
			)
		doc.reload()
		self.assertEqual(status, "Übermittelt")
		self.assertEqual(
			(
				doc.status,
				doc.filed_via,
				getdate(doc.filed_on),
				doc.order_number,
				doc.kleinst_notice,
				money(doc.fees),
			),
			("Übermittelt", "upload", date(2027, 5, 20), "A-2027-000123", 1, d("21.50")),
		)
		with self.freeze_time("2027-05-25 10:00:00"):
			self.refused(doc, "lies before the Übermittlung", lambda: doc.record_publication("2027-05-19"))
			status = doc.record_publication("2027-05-25")
		doc.reload()
		self.assertEqual(
			(status, doc.status, getdate(doc.published_on)), ("Eingestellt", "Eingestellt", date(2027, 5, 25))
		)

	# Print, Vorschau and XBRL.

	def test_the_print_format_shows_the_jahresabschluss_with_its_signatures_and_the_upload(self):
		doc = data.ready_for_the_feststellung(KLEINST)
		html = frappe.get_print(DOCTYPE, doc.name, PRINT_FORMAT, doc=doc)
		for text in (
			"Jahresabschluss zum 31.12.2026",
			"Bilanz zum 31.12.2026",
			"Gewinn- und Verlustrechnung für die Zeit vom 01.01.2026 bis 31.12.2026",
			"Angaben unter der Bilanz",
			"HRB 99901",
			"Musterstadt, 12. Mai 2027: gez. Erika Beispiel, Geschäftsführerin",
			"Upload zum Unternehmensregister",
			"Testplattform",
			"Nicht geprüft:",
		):
			with self.subTest(text=text):
				self.assertIn(text, html)

	def test_the_vorschau_der_offenlegung_is_a_private_pdf_of_what_becomes_visible(self):
		self.use_pdf_generator("PlutoPrint")
		doc = data.ready_for_the_feststellung(KLEINST)
		doc.flags.offenlegung = True
		html = frappe.get_print(DOCTYPE, doc.name, PRINT_FORMAT, doc=doc)
		doc.flags.offenlegung = False
		self.assertIn("Vorschau der Offenlegung", html)
		self.assertIn(layout.DEPOSITED, html)
		self.assertNotIn("Gewinn- und Verlustrechnung für die Zeit", html)
		url = doc.make_disclosure_preview()
		self.assertEqual(frappe.db.get_value(DOCTYPE, doc.name, "preview_file"), url)
		file = frappe.get_doc("File", {"file_url": url})
		self.assertEqual(
			(file.is_private, file.attached_to_doctype, file.attached_to_name), (1, DOCTYPE, doc.name)
		)
		self.assertTrue(file.get_content().startswith(b"%PDF"))

	def test_the_xbrl_of_a_festgestellter_jahresabschluss_is_a_private_file(self):
		doc = data.ready_for_the_feststellung(KLEINST)
		with self.freeze_time(data.AFTER_ADOPTION):
			doc.submit()
			result = doc.make_xbrl()
		self.assertEqual(result["held_back"], [])
		file = frappe.get_doc("File", {"file_url": result["file_url"]})
		self.assertEqual(
			(file.is_private, file.attached_to_name, file.file_name),
			(1, doc.name, f"Offenlegung-{doc.name}.xbrl"),
		)
		content = file.get_content()
		text = content.decode() if isinstance(content, bytes) else content
		self.assertIn("HRB 99901", text)
		self.assertIn("de-gaap-ci:bs.ass", text)
		self.assertEqual(frappe.db.get_value(DOCTYPE, doc.name, "xbrl_file"), result["file_url"])

	def test_what_holds_the_xbrl_back_goes_into_the_findings(self):
		answers = {"ZUSAETZLICHE-ANGABEN": ("ja", "Die Bürgschaft → endet 2028.", 0)}
		doc = data.ready_for_the_feststellung(KLEINST, answers)
		with self.freeze_time(data.AFTER_ADOPTION):
			doc.submit()
			result = doc.make_xbrl()
		doc.reload()
		self.assertEqual(result["file_url"], "")
		self.assertTrue(result["held_back"])
		self.assertIn("JA-XBRL-ZEICHEN", codes(doc))
		self.assertFalse(doc.xbrl_file)

	def use_pdf_generator(self, generator: str) -> None:
		before = frappe.db.get_single_value("Print Settings", "pdf_generator")
		self.addCleanup(frappe.db.set_single_value, "Print Settings", "pdf_generator", before)
		frappe.db.set_single_value("Print Settings", "pdf_generator", generator)


def adopted_in_settings(company) -> date | None:
	day = frappe.db.get_value(
		"Annual Filing Year",
		{"parent": company.name, "parenttype": data.SETTINGS, "year": data.YEAR},
		"adopted_on",
	)
	return getdate(day) if day else None

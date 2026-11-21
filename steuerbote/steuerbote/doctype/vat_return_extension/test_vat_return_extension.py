"""The Dauerfristverlängerung on a site: Berechnen from the VAT Returns filed for the previous year, the base by
hand, the deadlines with the holidays of the company, the filing marks that write the Sondervorauszahlung into
the VAT Return Settings, the guards around them, and the print format."""

from datetime import date
from decimal import Decimal
from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import add_days, getdate, today

from steuerbote import dauerfrist_sources
from steuerbote.steuerbote.print_format.umsatzsteuer_voranmeldung.test_umsatzsteuer_voranmeldung import cells
from steuerbote.tests.helpers import (
	make_account,
	make_company,
	make_mapping,
	make_settings,
	make_user,
	post_journal_entry,
)

# The companies, their accounts and the vouchers are made by the tests themselves.
IGNORE_TEST_RECORD_DEPENDENCIES = ["Company", "VAT Return"]

DOCTYPE = "VAT Return Extension"
PRINT_FORMAT = "Dauerfristverlängerung"
SVZ = "Umsatzsteuersondervorauszahlung"
FILED_IN_MEIN_ELSTER = "In Mein ELSTER abgegeben"
# 32 characters as in the protocol of ELSTER, invented.
TICKET = "ab123cdefghijkmnopqrstuvwxyz0123"
# May read nothing of the Dauerfristverlängerung, let alone change it.
SALES_USER = "steuerbote-dauerfrist-vertrieb@example.com"

# Files monthly from 2026, with the Dauerfristverlängerung and a Sondervorauszahlung of 5.000 € in 2026. Its
# Voranmeldungen for March and December 2026 make the example of the Anleitung USt 5 E: Kz 83 of 39.000 € and
# Kz 39 of 5.000 €.
COMPANY = "Steuerbote Test Sondervorauszahlung GmbH"
# Files monthly from 2026; the VAT Return Settings hold a Sondervorauszahlung 2026 of 1.000 €.
FILING_COMPANY = "Steuerbote Test Anmeldung Sondervorauszahlung GmbH"
# Began on 15 March 2026 and files monthly from April 2026.
NEW_COMPANY = "Steuerbote Test Neugründung GmbH"
# Began on 10 November 2026 and files monthly from October 2026.
YOUNG_COMPANY = "Steuerbote Test Gründung im Vorjahr GmbH"
# Files quarterly from 2026.
QUARTERLY_COMPANY = "Steuerbote Test Dauerfrist vierteljährlich GmbH"
# Files monthly from 2026; its Holiday List decides on 10 February 2027.
HOLIDAY_COMPANY = "Steuerbote Test Feiertage GmbH"

ACCOUNTS = {
	"8400": ("Erlöse 19 % USt", "Income"),
	"1776": ("Umsatzsteuer 19 %", "Liability"),
	"1576": ("Abziehbare Vorsteuer 19 %", "Asset"),
	"1200": ("Bank", "Asset"),
	"1400": ("Forderungen aus Lieferungen und Leistungen", "Asset"),
}


def money(value) -> Decimal:
	return Decimal(str(value)).quantize(Decimal("0.01"))


def accounts_of(company: str) -> dict[str, str]:
	return {
		number: make_account(company, number, name, root_type)
		for number, (name, root_type) in ACCOUNTS.items()
	}


def sale(company: str, accounts: dict[str, str], posting_date: str, base: int) -> None:
	"""A sale at 19 % with the tax booked as the Verprobung expects it."""
	tax = base * 19 // 100
	post_journal_entry(
		company,
		posting_date,
		[(accounts["1400"], base + tax, 0), (accounts["8400"], 0, base), (accounts["1776"], 0, tax)],
	)


def new_vat_return(company: str, period: int, **fields):
	return frappe.get_doc(
		{
			"doctype": "VAT Return",
			"company": company,
			"year": 2026,
			"rhythm": "monthly",
			"period_index": period,
			**fields,
		}
	).insert()


def filed_vat_return(company: str, period: int, **fields):
	doc = new_vat_return(company, period, **fields)
	doc.calculate()
	doc.reload()
	doc.mark_filed_outside(FILED_IN_MEIN_ELSTER)
	return doc


def make_holiday_list(name: str, day: str, weekly_off: int = 0) -> str:
	return (
		frappe.get_doc(
			{
				"doctype": "Holiday List",
				"holiday_list_name": name,
				"from_date": "2027-01-01",
				"to_date": "2027-12-31",
				"holidays": [{"holiday_date": day, "description": "Testtag", "weekly_off": weekly_off}],
			}
		)
		.insert(ignore_permissions=True)
		.name
	)


def remove(name: str) -> None:
	"""Take a form out again, so that the next test can make one for the same company and year. A filed Antrag
	cannot be cancelled, so the form leaves the database directly."""
	if frappe.db.get_value(DOCTYPE, name, "docstatus") == 1:
		frappe.db.set_value(DOCTYPE, name, "docstatus", 2)
	frappe.delete_doc(DOCTYPE, name, force=True)


def prepayments(company: str) -> list[tuple[int, int, Decimal]]:
	settings = frappe.get_doc("VAT Return Settings", company)
	return [
		(row.year, row.dauerfristverlaengerung, money(row.sondervorauszahlung))
		for row in settings.prepayments
	]


class TestVATReturnExtension(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		make_company(COMPANY, "SDSV")
		accounts = accounts_of(COMPANY)
		make_settings(COMPANY, [(2026, "monthly", 1)], [(2026, True, "5000.00")])
		make_mapping(COMPANY)
		sale(COMPANY, accounts, "2026-03-10", 90000)
		cls.replaced_march = filed_vat_return(COMPANY, 3)
		sale(COMPANY, accounts, "2026-03-25", 10000)
		cls.march = filed_vat_return(COMPANY, 3, is_correction=1)
		sale(COMPANY, accounts, "2026-12-10", 200000)
		post_journal_entry(
			COMPANY, "2026-12-15", [(accounts["1576"], 13000, 0), (accounts["1200"], 0, 13000)]
		)
		cls.december = filed_vat_return(COMPANY, 12)
		new_vat_return(COMPANY, 6).calculate()

		make_company(YOUNG_COMPANY, "SDGV")
		frappe.db.set_value("Company", YOUNG_COMPANY, "date_of_establishment", "2026-11-10")
		young = accounts_of(YOUNG_COMPANY)
		make_settings(YOUNG_COMPANY, [(2026, "monthly", 10)])
		make_mapping(YOUNG_COMPANY)
		sale(YOUNG_COMPANY, young, "2026-11-20", 10000)
		sale(YOUNG_COMPANY, young, "2026-12-20", 20000)
		filed_vat_return(YOUNG_COMPANY, 11)
		filed_vat_return(YOUNG_COMPANY, 12)

		make_company(FILING_COMPANY, "SDAN")
		make_settings(FILING_COMPANY, [(2026, "monthly", 1)], [(2026, True, "1000.00")])
		make_mapping(FILING_COMPANY)
		make_company(NEW_COMPANY, "SDNG")
		frappe.db.set_value("Company", NEW_COMPANY, "date_of_establishment", "2026-03-15")
		make_settings(NEW_COMPANY, [(2026, "monthly", 4)])
		make_company(QUARTERLY_COMPANY, "SDVJ")
		make_settings(QUARTERLY_COMPANY, [(2026, "quarterly", 1)])
		make_company(HOLIDAY_COMPANY, "SDFT")
		make_settings(HOLIDAY_COMPANY, [(2026, "monthly", 1)])
		cls.holiday_list = make_holiday_list("Steuerbote Test Feiertag 2027", "2027-02-10")
		cls.weekly_off_list = make_holiday_list("Steuerbote Test Wochenfrei 2027", "2027-02-10", weekly_off=1)

	def extension(self, company: str = COMPANY, year: int = 2027, **fields):
		doc = frappe.get_doc({"doctype": DOCTYPE, "company": company, "year": year, **fields}).insert()
		self.addCleanup(remove, doc.name)
		return doc

	def calculated(self, company: str = COMPANY, year: int = 2027, **fields):
		doc = self.extension(company, year, **fields)
		doc.calculate()
		doc.reload()
		return doc

	def printed(self, doc) -> str:
		return frappe.get_print(DOCTYPE, doc.name, print_format=PRINT_FORMAT, no_letterhead=1)

	def roll_back_afterwards(self) -> None:
		"""Undo what the test files, the Sondervorauszahlung in the VAT Return Settings among it."""
		frappe.db.savepoint("vat_return_extension_test")
		self.addCleanup(frappe.db.rollback, save_point="vat_return_extension_test")

	def test_a_save_keeps_the_base_berechnen_read(self):
		"""Frappe keeps no read-only field from a save through its API: a base of other amounts, without the
		missing Voranmeldungen and with another start of the company, would set another Kz 38."""
		doc = self.calculated()
		doc.base_rows[0].kz83 = 1
		doc.append(
			"base_rows", {"period_label": "Januar 2026", "period_code": "01", "kz83": 110000, "kz39": 0}
		)
		doc.update(
			{"missing_periods": None, "findings": None, "status": "Bereit", "established_on": "2026-11-01"}
		)
		doc.save()
		doc.reload()
		self.assertEqual(
			[(row.period_label, money(row.kz83)) for row in doc.base_rows],
			[("März 2026", money(19000)), ("Dezember 2026", money(20000))],
		)
		self.assertEqual(
			(doc.status, doc.established_on, doc.months_active, money(doc.sondervorauszahlung)),
			("Berechnet", None, 12, money(4000)),
		)
		self.assertIn("is missing from the base", doc.findings)

	def test_a_form_that_berechnen_has_not_read_stays_a_draft(self):
		"""A draft sent back as ready, with a base and a filing of its own, would file the Kz 38 of that base."""
		self.roll_back_afterwards()
		doc = self.extension(FILING_COMPANY, 2026)
		doc.update(
			{"status": "Bereit", "missing_periods": None, "filed_via": "eric", "transferticket": TICKET}
		)
		doc.append(
			"base_rows", {"period_label": "Januar 2025", "period_code": "01", "kz83": 110000, "kz39": 0}
		)
		doc.save()
		doc.reload()
		self.assertEqual(
			(doc.status, doc.base_rows, money(doc.sondervorauszahlung), doc.filed_via, doc.transferticket),
			("Entwurf", [], money(0), None, None),
		)
		with self.assertRaisesRegex(frappe.ValidationError, "Calculate the form before filing it"):
			doc.mark_filed_outside(filed_via="mein_elster")

	def test_kz38_changed_past_the_save_is_not_filed(self):
		"""Kz 38 follows the base on every save. Written past it, here straight into the database, it is neither
		transmitted nor filed, until Berechnen runs again."""
		self.roll_back_afterwards()
		doc = self.calculated(
			FILING_COMPANY, 2026, base_override=44000, base_override_reason="Voranmeldungen 2025 im Altsystem"
		)
		frappe.db.set_value(DOCTYPE, doc.name, "sondervorauszahlung", 100)
		refused = "do not agree with the form as stored"
		with patch("frappe.enqueue") as enqueue, self.assertRaisesRegex(frappe.ValidationError, refused):
			doc.transmit("validate")
		enqueue.assert_not_called()
		with self.assertRaisesRegex(frappe.ValidationError, refused):
			doc.mark_filed_outside(filed_via="mein_elster")
		doc.reload()
		doc.calculate()
		doc.reload()
		doc.mark_filed_outside(filed_via="mein_elster")
		self.assertEqual((doc.docstatus, money(doc.sondervorauszahlung)), (1, money(4000)))

	def test_buchen_after_an_accepted_send_files_kz38_as_stored(self):
		"""ELSTER accepted the form while its submission failed: Buchen submits it with the Kz 38 it holds, not with
		another base by hand sent along."""
		self.roll_back_afterwards()
		doc = self.calculated(
			FILING_COMPANY, 2026, base_override=44000, base_override_reason="Voranmeldungen 2025 im Altsystem"
		)
		doc.new_transmission("send", simulated=False, status="Erfolgreich", transferticket=TICKET)
		doc.reload()
		doc.base_override = 55000
		with self.assertRaisesRegex(frappe.ValidationError, "do not agree with the form as stored"):
			doc.submit()
		doc.reload()
		doc.submit()
		self.assertEqual(
			(doc.docstatus, money(doc.sondervorauszahlung), doc.filed_via, doc.transferticket),
			(1, money(4000), "eric", TICKET),
		)

	def test_takes_kz83_and_kz39_of_the_latest_filing_of_each_period(self):
		doc = self.calculated()
		self.assertEqual(
			[(row.period_label, row.vat_return, money(row.kz83), money(row.kz39)) for row in doc.base_rows],
			[
				("März 2026", self.march.name, money(19000), money(0)),
				("Dezember 2026", self.december.name, money(20000), money(5000)),
			],
		)
		self.replaced_march.reload()
		self.assertEqual(self.replaced_march.status, "Ersetzt")

	def test_computes_the_sondervorauszahlung_of_the_example_of_the_anleitung(self):
		doc = self.calculated()
		self.assertEqual(
			(
				doc.context,
				doc.rhythm,
				money(doc.kz83),
				money(doc.kz39),
				doc.months_active,
				money(doc.computed_base),
				money(doc.base),
				money(doc.sondervorauszahlung),
			),
			(SVZ, "monthly", money(39000), money(5000), 12, money(44000), money(44000), money(4000)),
		)

	def test_the_sondervorauszahlung_is_due_on_10_february_and_credited_in_december(self):
		doc = self.extension()
		self.assertEqual(
			(doc.deadline, doc.crediting_period_label, doc.status),
			(date(2027, 2, 10), "Dezember 2027", "Entwurf"),
		)

	def test_names_the_voranmeldungen_missing_from_the_base(self):
		doc = self.calculated()
		months = (
			"Januar",
			"Februar",
			"April",
			"Mai",
			"Juni",
			"Juli",
			"August",
			"September",
			"Oktober",
			"November",
		)
		missing = ", ".join(f"{month} 2026" for month in months)
		self.assertEqual(doc.missing_periods, missing)
		self.assertIn(f"Kz 83 of {missing} is missing from the base.", doc.findings)
		self.assertEqual(doc.status, "Berechnet")

	def test_a_year_whose_form_steuerbote_does_not_know_is_not_ready(self):
		doc = self.calculated(
			base_override=44000, base_override_reason="Januar bis November im Altsystem abgegeben"
		)
		self.assertEqual(
			(doc.status, doc.findings), ("Berechnet", "Steuerbote does not know form USt 1 H for 2027 yet.")
		)

	def test_the_base_by_hand_replaces_the_base_from_the_voranmeldungen(self):
		doc = self.calculated(
			base_override=55000, base_override_reason="Januar bis November im Altsystem abgegeben"
		)
		self.assertEqual(
			(money(doc.computed_base), money(doc.base), money(doc.sondervorauszahlung)),
			(money(44000), money(55000), money(5000)),
		)

	def test_kz38_follows_the_base_by_hand_when_the_form_is_saved(self):
		doc = self.calculated()
		doc.update({"base_override": 33000, "base_override_reason": "Vorjahr laut Steuerberatung"})
		doc.save()
		self.assertEqual((money(doc.base), money(doc.sondervorauszahlung)), (money(33000), money(3000)))
		doc.update({"base_override": 0, "base_override_reason": ""})
		doc.save()
		self.assertEqual((money(doc.base), money(doc.sondervorauszahlung)), (money(44000), money(4000)))

	def test_a_base_by_hand_needs_a_reason(self):
		doc = self.calculated()
		doc.base_override = 55000
		with self.assertRaisesRegex(frappe.ValidationError, "The base by hand needs a reason"):
			doc.save()

	def test_a_year_without_filed_voranmeldungen_needs_the_base_by_hand(self):
		doc = self.extension(year=2028)
		with self.assertRaisesRegex(frappe.ValidationError, f"No VAT Return of 2027 is filed for {COMPANY}"):
			doc.calculate()
		doc.reload()
		doc.update(
			{"base_override": 22000, "base_override_reason": "Voranmeldungen 2027 außerhalb von Steuerbote"}
		)
		doc.save()
		doc.calculate()
		doc.reload()
		self.assertEqual(
			(doc.base_rows, money(doc.base), money(doc.sondervorauszahlung), doc.deadline),
			([], money(22000), money(2000), date(2028, 2, 10)),
		)

	def test_a_start_in_the_previous_year_converts_the_vorauszahlungen_into_an_annual_sum(self):
		doc = self.calculated(YOUNG_COMPANY)
		self.assertEqual(
			(
				[row.period_label for row in doc.base_rows],
				doc.established_on,
				doc.months_active,
				money(doc.kz83),
				money(doc.computed_base),
				money(doc.sondervorauszahlung),
				doc.missing_periods,
			),
			(
				["November 2026", "Dezember 2026"],
				date(2026, 11, 10),
				2,
				money(5700),
				money(34200),
				money(3109),
				None,
			),
		)

	def test_a_company_that_began_this_year_pays_the_average_month_it_expects(self):
		doc = self.extension(NEW_COMPANY, 2026, antrag=1, first_month=4)
		self.assertEqual(
			(doc.context, doc.first_period_label, doc.deadline), (SVZ, "April 2026", date(2026, 5, 11))
		)
		with self.assertRaisesRegex(
			frappe.ValidationError, f"{NEW_COMPANY} began on .*: its Sondervorauszahlung is the average"
		):
			doc.calculate()
		doc.reload()
		doc.update({"base_override": 15000, "base_override_reason": "Erwartete Vorauszahlungen 2026"})
		doc.save()
		doc.calculate()
		doc.reload()
		self.assertEqual(
			(
				doc.established_on,
				doc.months_active,
				doc.base_rows,
				money(doc.base),
				money(doc.sondervorauszahlung),
			),
			(date(2026, 3, 15), 10, [], money(15000), money(1500)),
		)
		self.assertEqual((doc.status, doc.findings), ("Bereit", None))

	def test_a_quarterly_filer_files_nothing_while_the_extension_holds(self):
		with self.assertRaisesRegex(frappe.ValidationError, "nothing is due for 2027"):
			frappe.get_doc({"doctype": DOCTYPE, "company": QUARTERLY_COMPANY, "year": 2027}).insert()

	def test_a_quarterly_filer_applies_for_the_extension_alone(self):
		doc = self.extension(QUARTERLY_COMPANY, antrag=1, first_month=5, is_correction=1, no_sepa_mandate=1)
		self.assertEqual(
			(
				doc.context,
				doc.rhythm,
				doc.first_period_label,
				doc.deadline,
				doc.crediting_period_label,
				doc.is_correction,
				doc.no_sepa_mandate,
			),
			(
				"Dauerfristverlaengerung",
				"quarterly",
				"II. Kalendervierteljahr 2027",
				date(2027, 7, 12),
				None,
				0,
				0,
			),
		)
		doc.calculate()
		doc.reload()
		self.assertEqual(
			(doc.base_rows, money(doc.sondervorauszahlung), doc.status), ([], money(0), "Berechnet")
		)

	def test_the_filed_antrag_ticks_the_dauerfristverlaengerung_of_its_year_and_stays(self):
		doc = self.calculated(
			QUARTERLY_COMPANY, 2028, antrag=1, first_month=1, remarks="Vordruck 2028 in Mein ELSTER von Hand"
		)
		doc.mark_filed_outside(filed_via="mein_elster")
		self.assertEqual(prepayments(QUARTERLY_COMPANY), [(2028, 1, money(0))])
		doc.reload()
		with self.assertRaisesRegex(frappe.ValidationError, "cannot be corrected"):
			doc.cancel()

	def test_an_antrag_needs_the_first_month_it_covers(self):
		with self.assertRaisesRegex(frappe.ValidationError, "enter the first month it covers"):
			self.extension(HOLIDAY_COMPANY, 2029, antrag=1)

	def test_an_antrag_is_due_when_the_first_voranmeldung_it_covers_is_due(self):
		doc = self.extension(HOLIDAY_COMPANY, 2028, antrag=1, first_month=7)
		self.assertEqual((doc.first_period_label, doc.deadline), ("Juli 2028", date(2028, 8, 10)))

	def test_a_holiday_of_the_company_moves_the_deadline_to_the_next_working_day(self):
		frappe.db.set_value("Company", HOLIDAY_COMPANY, "default_holiday_list", self.holiday_list)
		self.assertEqual(self.extension(HOLIDAY_COMPANY).deadline, date(2027, 2, 11))

	def test_a_weekly_day_off_moves_no_deadline(self):
		frappe.db.set_value("Company", HOLIDAY_COMPANY, "default_holiday_list", self.weekly_off_list)
		self.assertEqual(self.extension(HOLIDAY_COMPANY).deadline, date(2027, 2, 10))

	def test_a_company_files_one_form_a_year(self):
		first = self.extension()
		with self.assertRaisesRegex(
			frappe.ValidationError, f"{COMPANY} has a Dauerfristverlängerung for 2027 already: {first.name}"
		):
			frappe.get_doc({"doctype": DOCTYPE, "company": COMPANY, "year": 2027}).insert()

	def test_berechnen_reads_nothing_for_a_user_who_may_not_change_the_form(self):
		doc = self.extension()
		with (
			self.set_user(make_user(SALES_USER, "Sales User")),
			patch.object(dauerfrist_sources, "filed_returns") as filed_returns,
			self.assertRaises(frappe.PermissionError),
		):
			doc.calculate()
		filed_returns.assert_not_called()

	def test_buchen_alone_files_nothing(self):
		doc = self.calculated(remarks="Abgestimmt mit der Steuerberatung")
		with self.assertRaisesRegex(frappe.ValidationError, "not by Buchen alone"):
			doc.submit()

	def test_filing_needs_a_calculation(self):
		doc = self.extension()
		with self.assertRaisesRegex(frappe.ValidationError, "Calculate the form before filing it"):
			doc.mark_filed_outside(filed_via="mein_elster")

	def test_a_form_that_is_not_ready_is_filed_with_remarks(self):
		doc = self.calculated()
		with self.assertRaisesRegex(frappe.ValidationError, "The form is not ready"):
			doc.mark_filed_outside(filed_via="mein_elster")
		doc.reload()
		doc.remarks = "Januar bis November liegen der Steuerberatung vor."
		doc.save()
		doc.mark_filed_outside(filed_via="mein_elster", transferticket=TICKET)
		doc.reload()
		self.assertEqual(
			(doc.docstatus, doc.status, doc.filed_via, doc.filed_on, doc.transferticket),
			(1, "Abgegeben", "mein_elster", getdate(), TICKET),
		)

	def test_filing_writes_the_sondervorauszahlung_into_the_row_of_its_year(self):
		doc = self.calculated(remarks="Januar bis November liegen der Steuerberatung vor.")
		doc.mark_filed_outside(filed_via="mein_elster")
		self.assertIn((2027, 1, money(4000)), prepayments(COMPANY))
		self.assertEqual(
			frappe.get_doc("VAT Return Settings", COMPANY).sondervorauszahlung(2027), money(4000)
		)

	def test_the_last_voranmeldung_of_the_year_deducts_the_sondervorauszahlung_filed(self):
		doc = self.calculated(
			FILING_COMPANY, 2026, base_override=44000, base_override_reason="Voranmeldungen 2025 im Altsystem"
		)
		self.assertEqual(
			(doc.status, doc.findings, doc.deadline, money(doc.sondervorauszahlung)),
			("Bereit", None, date(2026, 2, 10), money(4000)),
		)
		doc.mark_filed_outside(filed_via="other_way", note="Am 10. Februar 2026 durch die Steuerberatung")
		self.assertEqual(prepayments(FILING_COMPANY), [(2026, 1, money(4000))])
		december = new_vat_return(FILING_COMPANY, 12)
		december.calculate()
		december.reload()
		self.assertEqual(
			(money(december.sondervorauszahlung), money(december.kz83)), (money(4000), money(-4000))
		)

	def test_a_filing_outside_steuerbote_needs_a_note_a_day_not_to_come_and_a_true_transferticket(self):
		doc = self.calculated(
			FILING_COMPANY, 2026, base_override=0, base_override_reason="Keine Vorauszahlungen"
		)
		with self.assertRaisesRegex(frappe.ValidationError, "Note how and when the form was filed"):
			doc.mark_filed_outside(filed_via="other_way")
		with self.assertRaisesRegex(frappe.ValidationError, "is no Transferticket"):
			doc.mark_filed_outside(filed_via="mein_elster", transferticket="abc")
		with self.assertRaisesRegex(frappe.ValidationError, "cannot be filed in the future"):
			doc.mark_filed_outside(filed_via="mein_elster", filed_on=add_days(today(), 1))
		with self.assertRaisesRegex(frappe.ValidationError, "knows no way of filing"):
			doc.mark_filed_outside(filed_via="fax")

	def test_a_filed_anmeldung_is_corrected_by_amending_it_with_kz10(self):
		doc = self.calculated(remarks="Januar bis November liegen der Steuerberatung vor.")
		doc.mark_filed_outside(filed_via="mein_elster")
		doc.reload()
		doc.cancel()
		self.assertIn((2027, 1, money(4000)), prepayments(COMPANY))
		amendment = frappe.copy_doc(doc)
		amendment.update({"amended_from": doc.name, "docstatus": 0})
		# Amend in the form copies the calculation and the filing too, as copy_doc does.
		self.assertEqual(
			(amendment.status, amendment.filed_on, len(amendment.base_rows)), ("Abgegeben", doc.filed_on, 2)
		)
		with self.assertRaisesRegex(frappe.ValidationError, "mark it as a corrected Anmeldung"):
			amendment.insert()
		amendment.is_correction = 1
		amendment.insert()
		self.addCleanup(remove, amendment.name)
		self.assertEqual((amendment.status, amendment.filed_on, amendment.base_rows), ("Entwurf", None, []))

	def test_a_new_form_after_a_cancelled_filing_is_a_corrected_anmeldung(self):
		"""Cancelling in Steuerbote takes nothing back at the Finanzamt, so every further form of the year is a
		corrected Anmeldung (Kz 10), also one made anew instead of amended."""
		doc = self.calculated(remarks="Januar bis November liegen der Steuerberatung vor.")
		doc.mark_filed_outside(filed_via="mein_elster")
		doc.reload()
		doc.cancel()
		with self.assertRaisesRegex(
			frappe.ValidationError, f"{COMPANY} filed {doc.name} for 2027 already, which the Finanzamt keeps"
		):
			frappe.get_doc({"doctype": DOCTYPE, "company": COMPANY, "year": 2027}).insert()
		self.assertEqual(self.extension(is_correction=1).is_correction, 1)

	def test_the_print_format_is_installed_for_the_dauerfrist(self):
		self.assertEqual(
			frappe.db.get_value(
				"Print Format", PRINT_FORMAT, ["doc_type", "print_format_type", "standard", "module"]
			),
			(DOCTYPE, "Jinja", "Yes", "Steuerbote"),
		)

	def test_prints_the_base_kz38_the_deadline_and_the_status(self):
		doc = self.calculated()
		text = cells(self.printed(doc))
		for expected in (
			"Anmeldung der Sondervorauszahlung 2027",
			f"Unternehmen | {COMPANY} |",
			"Steuernummer | 123/456/78901 |",
			"Fällig am | 10.02.2027 |",
			"Angerechnet in Kz 39 von | Dezember 2027 |",
			f"Vordruck | {doc.name}, Berechnet |",
			f"März 2026 | {self.march.name} | 19.000,00 | 0,00 |",
			f"Dezember 2026 | {self.december.name} | 20.000,00 | 5.000,00 |",
			"Summe | 39.000,00 | 5.000,00 |",
			"Ohne abgegebene Voranmeldung: Januar 2026, Februar 2026,",
			"7 | Berichtigte Anmeldung | 10 | |",
			"8 | Summe der verbleibenden Umsatzsteuer-Vorauszahlungen zuzüglich der zu berücksichtigenden "
			"Sondervorauszahlung für das Kalenderjahr 2026 | | 44.000,00 |",
			"9 | Davon 1/11 = Sondervorauszahlung 2027 | 38 | 4.000 |",
			"Offene Punkte",
			"Dieser Ausdruck ist keine Abgabe",
		):
			with self.subTest(expected=expected):
				self.assertIn(expected, text)
		self.assertNotIn("{{", text)

	def test_prints_the_base_by_hand_and_the_filing(self):
		doc = self.calculated(
			FILING_COMPANY, 2026, base_override=44000, base_override_reason="Voranmeldungen 2025 im Altsystem"
		)
		doc.mark_filed_outside(filed_via="mein_elster", transferticket=TICKET)
		doc.reload()
		text = cells(self.printed(doc))
		for expected in (
			"Grundlage von Hand",
			"| 44.000,00 | Voranmeldungen 2025 im Altsystem |",
			"Keine abgegebene Voranmeldung",
			f"Vordruck | {doc.name}, Abgegeben |",
			"Abgegeben über | Mein ELSTER |",
			f"Transferticket | {TICKET} |",
		):
			with self.subTest(expected=expected):
				self.assertIn(expected, text)

	def test_prints_the_antrag_alone_without_the_sondervorauszahlung(self):
		doc = self.calculated(QUARTERLY_COMPANY, 2027, antrag=1, first_month=4)
		text = cells(self.printed(doc))
		self.assertIn("Antrag auf Dauerfristverlängerung 2027", text)
		self.assertIn("Verlängert ab | II. Kalendervierteljahr 2027 |", text)
		self.assertIn("Ich beantrage, die Fristen für die Übermittlung der Umsatzsteuer-Voranmeldungen", text)
		self.assertNotIn("Davon 1/11", text)

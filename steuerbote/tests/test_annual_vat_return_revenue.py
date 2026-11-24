"""The Umsatzsteuererklärung against the Umsatzerlöse of its year, on the Frappe test site with the invented company of
steuerbote/tests/annual_integration.py and the HGB-Taxonomie 6.9 installed: the Umsatzerlöse of the festgestellter
Jahresabschluss and of the filed E-Bilanz, a sale posted after them, the tolerance of the VAT Return Settings, and a
year with neither. Every name, number and amount is invented.
"""

from frappe.tests import IntegrationTestCase

from steuerbote.tests import annual_integration as data
from steuerbote.tests.annual_integration import (
	ABBR,
	AFTER_ADOPTION,
	COMPANY,
	EBILANZ,
	FILED_NOTE,
	VAT,
	calculated,
)
from steuerbote.tests.ebilanz import configured, taxonomy_root

HINT = "SB-UMSATZERLOESE"
LATE_SALE = (("1800", "5000", 0), ("4400", 0, "5000"))
"""A sale of 5,000 euros posted after the Jahresabschluss and the E-Bilanz: line 24 of the return holds it, their
Umsatzerlöse do not."""
REMARKS = "Mit der Steuerberatung abgestimmt: Die Handelsbilanz ist die des Jahresabschlusses."


def hints(doc) -> list:
	return [row for row in doc.findings if row.code == HINT]


class TestAnnualVATReturnRevenue(IntegrationTestCase):
	"""One class, so that the company and its books are made once; each test takes out its documents and postings."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.enterClassContext(configured(taxonomy_root()))
		cls.account = data.make_company_with_books()

	def setUp(self):
		super().setUp()
		self.addCleanup(data.discard)

	def post_late_sale(self) -> None:
		data.post_for_the_test(self, self.account, f"JV-{ABBR}-ERLOES-NACHTRAG", "2026-12-31", LATE_SALE)

	def test_the_sales_of_the_return_agree_with_the_festgestellten_jahresabschluss(self):
		with self.freeze_time(AFTER_ADOPTION):
			data.festgestellt()
		self.assertEqual(hints(calculated(VAT)), [])

	def test_a_sale_after_the_feststellung_gives_a_hint_that_holds_nothing_back(self):
		with self.freeze_time(AFTER_ADOPTION):
			accounts = data.festgestellt()
		self.post_late_sale()
		doc = calculated(VAT)
		(hint,) = hints(doc)
		self.assertEqual((hint.blocking, hint.reference), (0, "E3003303"))
		self.assertEqual(
			hint.text,
			f"The Umsatzerlöse of the festgestellter Jahresabschluss {accounts.name} are 200000.00 euros, the "
			"Bemessungsgrundlagen of the Lieferungen und sonstigen Leistungen of the return 205000.00 euros (lines 24): a "
			"difference of -5000.00 euros, more than a euro a line and the tolerance of 100.00 euros. Sales of fixed "
			"assets, Anzahlungen and Erlöse that no line of the return takes explain such a difference; check it.",
		)

	def test_the_tolerance_of_the_vat_return_settings_takes_a_difference_in(self):
		with self.freeze_time(AFTER_ADOPTION):
			data.festgestellt()
		self.post_late_sale()
		data.set_for_the_test(self, "VAT Return Settings", COMPANY, comparison_threshold_amount=5000)
		self.assertEqual(hints(calculated(VAT)), [])

	def test_without_a_festgestellten_jahresabschluss_the_filed_e_bilanz_counts(self):
		ebilanz = calculated(EBILANZ, remarks=REMARKS)
		with self.freeze_time(AFTER_ADOPTION):
			ebilanz.mark_filed_outside(note=FILED_NOTE)
		calculated(data.ACCOUNTS_DOCTYPE)
		self.post_late_sale()
		(hint,) = hints(calculated(VAT))
		self.assertTrue(
			hint.text.startswith(f"The Umsatzerlöse of the filed E-Bilanz {ebilanz.name} are 200000.00 euros")
		)

	def test_a_year_without_festgestellten_jahresabschluss_and_filed_e_bilanz_compares_nothing(self):
		self.post_late_sale()
		calculated(data.ACCOUNTS_DOCTYPE)
		data.new_document(EBILANZ)
		self.assertEqual(hints(calculated(VAT)), [])

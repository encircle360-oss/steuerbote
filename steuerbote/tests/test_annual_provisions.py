"""The provisions for the taxes on income in the Jahresabschluss and the E-Bilanz, on the Frappe test site with the
invented company of steuerbote/tests/annual_integration.py: after a sale posted since Rückstellungen vorschlagen, both
documents that would be filed with the provisions name the difference and the return that proposes it. Every name,
number and amount is invented.
"""

from frappe.tests import IntegrationTestCase

from steuerbote.tests import annual_integration as data
from steuerbote.tests.annual_integration import ABBR, ACCOUNTS_DOCTYPE, CORPORATE, EBILANZ, calculated
from steuerbote.tests.ebilanz import configured, taxonomy_root

HINT = "SB-RUECKSTELLUNG-ABWEICHUNG"
LATE_SALE = (("1800", "10000", 0), ("4400", 0, "10000"))


class TestAnnualProvisions(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.enterClassContext(configured(taxonomy_root()))
		cls.account = data.make_company_with_books()

	def setUp(self):
		super().setUp()
		self.addCleanup(data.discard)

	def test_the_jahresabschluss_and_the_e_bilanz_name_provisions_the_books_hold_too_low(self):
		corporate = calculated(CORPORATE)
		data.submitted_provisions(corporate)
		data.post_for_the_test(self, self.account, f"JV-{ABBR}-NACHTRAG", "2026-12-30", LATE_SALE)
		corporate.calculate()
		corporate.reload()
		for doctype in (EBILANZ, ACCOUNTS_DOCTYPE):
			with self.subTest(doctype=doctype):
				doc = calculated(doctype)
				(hint,) = [row for row in doc.findings if row.code == HINT]
				self.assertEqual((hint.severity, hint.blocking), ("Hinweis", 0))
				self.assertIn(corporate.name, hint.text)
				self.assertIn("1.500,00 €", hint.text)

	def test_no_hint_while_the_books_hold_the_provisions_as_computed(self):
		corporate = calculated(CORPORATE)
		data.submitted_provisions(corporate)
		for doctype in (EBILANZ, ACCOUNTS_DOCTYPE):
			with self.subTest(doctype=doctype):
				self.assertNotIn(HINT, data.finding_codes(calculated(doctype)))

"""The rows and the hint of the report E-Bilanz Positionen, without a bench."""

from decimal import Decimal
from unittest import TestCase

from steuerbote.steuerbote.doctype.electronic_balance_sheet import bridge
from steuerbote.steuerbote.doctype.electronic_balance_sheet.test_bridge import ebilanz
from steuerbote.steuerbote.report.e_bilanz_positionen import rows
from steuerbote.ustjahr.soll import Filed, FiledKennzahl
from steuerbote.ustva.period import Period

D = Decimal
SALES = {"concept": rows.REVENUE, "reported": D("120000.00")}


def kennzahl(final: str) -> FiledKennzahl:
	return FiledKennzahl(D(final), D(final), D(final))


def voranmeldung(month: int, **kennzahlen: str) -> Filed:
	return Filed(
		Period.month(2026, month),
		f"UStVA-2026-{month:02d}",
		D("0.00"),
		lines={number.removeprefix("kz"): kennzahl(amount) for number, amount in kennzahlen.items()},
	)


def node(found: list[dict], key: str) -> dict:
	(row,) = (row for row in found if row["key"] == key)
	return row


class ReportRowsTest(TestCase):
	@classmethod
	def setUpClass(cls):
		found = ebilanz()
		positions = [{**row, "reported": row["computed"]} for row in bridge.position_rows(found)]
		cls.rows = rows.report_rows(positions, bridge.account_rows(found))

	def test_each_position_stands_under_the_position_above_it(self):
		self.assertEqual(
			{
				key: (row["parent_key"], row["indent"], row["bold"])
				for key in ("bs.ass", "bs.ass.fixAss", "bs.ass.fixAss.intan", "is.netIncome.netSales")
				for row in [node(self.rows, key)]
			},
			{
				"bs.ass": (None, 0, 1),
				"bs.ass.fixAss": ("bs.ass", 1, 1),
				"bs.ass.fixAss.intan": ("bs.ass.fixAss", 2, 1),
				"is.netIncome.netSales": ("is.netIncome", 1, 0),
			},
		)

	def test_a_position_opens_to_the_accounts_it_consists_of(self):
		sales = node(self.rows, "is.netIncome.netSales")
		self.assertEqual(
			(sales["label"], sales["reported"], sales["mark"]),
			("Umsatzerlöse", D("119000.00"), sales["mark"]),
		)
		self.assertEqual(
			[
				(row["key"], row["parent_key"], row["indent"], row["label"], row["reported"])
				for row in self.rows
				if row["parent_key"] == "is.netIncome.netSales"
			],
			[
				("is.netIncome.netSales:4400", "is.netIncome.netSales", 2, "Erlöse 19 % USt", D("120000.00")),
				(
					"is.netIncome.netSales:4700",
					"is.netIncome.netSales",
					2,
					"Erlösschmälerungen",
					D("-1000.00"),
				),
			],
		)
		account = node(self.rows, "is.netIncome.netSales:4400")
		self.assertEqual(
			(account["account_number"], account["component"], account["bold"]), ("4400", "GuV", 0)
		)

	def test_a_position_reported_as_nil_is_left_out(self):
		keys = {row["key"] for row in self.rows}
		self.assertNotIn("bs.eqLiab.equity.profitLoss", keys)
		self.assertIn("bs.eqLiab.equity.netIncome", keys)

	def test_a_position_whose_position_above_is_not_shown_stands_at_the_top(self):
		(row,) = rows.report_rows(
			[{"concept": "bs.ass.fixAss.tan", "parent_concept": "bs.ass.fixAss", "reported": 30000}], []
		)
		self.assertEqual(
			(row["parent_key"], row["indent"], row["bold"], row["ledger_amount"]), (None, 0, 0, D("0.00"))
		)


class RevenueTest(TestCase):
	def test_the_umsatzerloese_against_kz_81_86_41_and_45_of_the_filed_voranmeldungen(self):
		found = rows.revenue(
			[{"concept": "bs.ass", "reported": 1}, SALES],
			[
				voranmeldung(1, kz81="50000.00", kz86="10000.00", kz66="9500.00"),
				voranmeldung(2, kz41="20000.00", kz45="5000.00", kz43="35000.00"),
			],
		)
		self.assertEqual(found, rows.Revenue(D("120000.00"), D("85000.00"), 2, 4))
		self.assertEqual(found.difference, D("35000.00"))
		self.assertEqual(
			rows.revenue_note(found),
			(rows.DIFFERENT, (D("120000.00"), 2, D("85000.00"), D("35000.00"))),
		)

	def test_the_cents_each_filed_amount_cuts_off_are_no_difference(self):
		"""steuerbote/ustva/rounding.py: a Voranmeldung files whole euros."""
		within = rows.Revenue(D("120001.98"), D("120000.00"), 2, 2)
		self.assertTrue(within.explained_by_rounding)
		self.assertIsNone(rows.revenue_note(within))
		beyond = rows.Revenue(D("120002.01"), D("120000.00"), 2, 2)
		self.assertFalse(beyond.explained_by_rounding)
		self.assertEqual(rows.revenue_note(beyond)[0], rows.DIFFERENT)

	def test_without_a_filed_voranmeldung_the_report_says_so(self):
		found = rows.revenue([SALES], [])
		self.assertEqual(found, rows.Revenue(D("120000.00"), D("0"), 0, 0))
		self.assertEqual(rows.revenue_note(found), (rows.NOT_FILED, (D("120000.00"),)))

	def test_an_e_bilanz_without_a_guv_compares_nothing(self):
		"""An Eröffnungsbilanz has no GuV."""
		found = rows.revenue([{"concept": "bs.ass", "reported": 1}], [voranmeldung(1, kz81="1.00")])
		self.assertIsNone(found)
		self.assertIsNone(rows.revenue_note(found))

	def test_every_template_is_one_the_frappe_layer_translates(self):
		self.assertEqual(set(rows.MESSAGES), {rows.DIFFERENT, rows.NOT_FILED})
		self.assertEqual(rows.KENNZAHLEN, ("81", "86", "41", "45"))

"""The print of the E-Bilanz from the tables of the document, without a bench."""

from decimal import Decimal
from unittest import TestCase

from steuerbote.steuerbote.doctype.electronic_balance_sheet import bridge, layout
from steuerbote.steuerbote.doctype.electronic_balance_sheet.test_bridge import ebilanz

D = Decimal


def reported(rows: list[dict]) -> list[dict]:
	"""The rows as the document keeps them after Berechnen: each reports what it computed."""
	return [{**row, "reported": row["computed"]} for row in rows]


class BilanzTest(TestCase):
	@classmethod
	def setUpClass(cls):
		found = ebilanz()
		cls.positions = reported(bridge.position_rows(found))
		cls.sections = layout.print_sections(cls.positions, bridge.account_rows(found))

	def test_the_aktiva_stand_beside_the_passiva_each_under_its_total(self):
		aktiva, passiva = self.sections["aktiva"], self.sections["passiva"]
		self.assertEqual(
			(aktiva[0]["label"], aktiva[0]["amount"], passiva[0]["label"], passiva[0]["amount"]),
			("Bilanzsumme, Summe Aktiva", "110.500,00", "Bilanzsumme, Summe Passiva", "110.500,00"),
		)
		self.assertTrue(all(row["concept"].startswith("bs.ass") for row in aktiva))
		self.assertTrue(all(row["concept"].startswith("bs.eqLiab") for row in passiva))
		self.assertEqual(
			[row["concept"] for row in (*aktiva, *passiva)],
			[row["concept"] for row in self.positions if row["component"] == "B" and not row["nil"]],
		)

	def test_a_position_above_others_is_a_sum_on_its_level(self):
		aktiva = {row["concept"]: row for row in self.sections["aktiva"]}
		self.assertEqual(
			(aktiva["bs.ass.fixAss"]["level"], aktiva["bs.ass.fixAss"]["sum"]),
			(1, True),
		)
		self.assertEqual(
			(
				aktiva["bs.ass.currAss.cashEquiv.bank"]["level"],
				aktiva["bs.ass.currAss.cashEquiv.bank"]["sum"],
			),
			(3, False),
		)

	def test_a_mussfeld_reported_as_nil_is_not_printed(self):
		printed = {row["concept"] for row in (*self.sections["passiva"], *self.sections["bvv"])}
		self.assertNotIn("bs.eqLiab.equity.profitLoss", printed)
		self.assertNotIn("BVV.profitLoss.contribution", printed)
		self.assertIn("BVV.profitLoss.assetsPreviousYear.assets", printed)

	def test_the_guv_and_the_betriebsvermoegensvergleich_in_the_order_of_their_presentation(self):
		self.assertEqual(
			[(row["label"], row["amount"]) for row in self.sections["guv"]],
			[
				("Jahresüberschuss/Jahresfehlbetrag", "40.000,00"),
				("Umsatzerlöse", "119.000,00"),
				("Materialaufwand", "70.000,00"),
				("Steuern vom Einkommen und vom Ertrag", "9.000,00"),
			],
		)
		self.assertEqual(self.sections["bvv"][0]["concept"], "BVV.profitLoss")

	def test_an_einheitsbilanz_prints_no_amount_of_the_steuerbilanz(self):
		self.assertFalse(self.sections["handelsbilanz"])
		self.assertEqual({row["tax"] for row in self.sections["aktiva"]}, {""})

	def test_a_handelsbilanz_prints_the_steuerbilanz_beside_it(self):
		rows = [
			{
				"concept": "bs.ass",
				"component": "B",
				"label": "Summe Aktiva",
				"reported": 100,
				"tax_amount": 120,
			},
			{"concept": "is.netIncome", "component": "GuV", "reported": 10, "tax_amount": 30},
			{"concept": "nt.ass.gross", "component": "", "reported": 5},
		]
		sections = layout.print_sections(rows, handelsbilanz=True)
		self.assertEqual(
			(sections["aktiva"][0]["amount"], sections["aktiva"][0]["tax"]), ("100,00", "120,00")
		)
		self.assertEqual((sections["guv"][0]["label"], sections["guv"][0]["tax"]), ("is.netIncome", "30,00"))
		self.assertEqual((sections["passiva"], sections["bvv"]), ([], []))
		self.assertEqual(len(sections["guv"]), 1)

	def test_the_kontennachweis_sums_up_the_accounts_of_each_position(self):
		kontennachweis = {group["concept"]: group for group in self.sections["kontennachweis"]}
		sales = kontennachweis["is.netIncome.netSales"]
		self.assertEqual(
			(sales["label"], sales["sum"], sales["accounts"]),
			(
				"Umsatzerlöse",
				"119.000,00",
				[
					{"number": "4400", "label": "Erlöse 19 % USt", "amount": "120.000,00"},
					{"number": "4700", "label": "Erlösschmälerungen", "amount": "-1.000,00"},
				],
			),
		)
		self.assertEqual(next(iter(kontennachweis)), "bs.ass.fixAss.intan.concessionBrands")


class AnlagenspiegelTest(TestCase):
	ROWS = (
		{
			"position": "bs.ass.fixAss.intan.concessionBrands",
			"position_label": "entgeltlich erworbene Konzessionen",
			"value_type": "HB",
			"asset_category": "Software",
			"cost_begin": 15000,
			"additions": 3000,
			"cost_end": 18000,
			"depreciation_begin": 4000,
			"depreciation_regular": 2000,
			"depreciation_extraordinary": 500,
			"depreciation_end": 6500,
			"book_value_end": 11500,
			"reason": "Wertminderung",
		},
		{
			"position": "bs.ass.fixAss.tan",
			"value_type": "HB",
			"manual": 1,
			"cost_begin": 30000,
			"cost_end": 30000,
			"book_value_end": 30000,
			"reason": "Grundstück",
		},
		{
			"position": "bs.ass.fixAss.intan.concessionBrands",
			"value_type": "Überleitung",
			"asset_category": "Software",
			"depreciation_7g": 1000,
			"depreciation_end": 1000,
			"book_value_end": -1000,
		},
	)

	def setUp(self):
		self.anlagenspiegel = layout.print_sections([], fixed_assets=self.ROWS)["anlagenspiegel"]

	def test_the_columns_of_the_two_parts_follow_the_value_development(self):
		self.assertEqual(
			self.anlagenspiegel["cost_columns"], ["Anfang", "Zugänge", "Abgänge", "Umbuchungen", "Ende"]
		)
		self.assertEqual(
			self.anlagenspiegel["depreciation_columns"],
			[
				"Anfang",
				"des Jahres",
				"Zugänge",
				"Abgänge",
				"Umbuchungen",
				"Ende",
				"Zuschreibungen",
				"Buchwert Ende",
			],
		)

	def test_a_row_names_its_position_value_type_and_source(self):
		software, land, transfer = self.anlagenspiegel["rows"]
		self.assertEqual(
			(software["label"], software["value_type"], software["source"], software["reason"]),
			("entgeltlich erworbene Konzessionen", "Handelsbilanzwert", "Software", "Wertminderung"),
		)
		self.assertEqual(software["cost"], ["15.000,00", "3.000,00", "0,00", "0,00", "18.000,00"])
		self.assertEqual(
			software["depreciation"],
			["4.000,00", "2.500,00", "0,00", "0,00", "0,00", "6.500,00", "0,00", "11.500,00"],
		)
		self.assertEqual((land["label"], land["source"]), ("bs.ass.fixAss.tan", "Zeile von Hand"))
		self.assertEqual(
			(transfer["value_type"], transfer["depreciation"][1]), ("Überleitungswert", "1.000,00")
		)

	def test_the_sums_of_each_value_type(self):
		handelsbilanz, transfer = self.anlagenspiegel["totals"]
		self.assertEqual(
			(handelsbilanz["value_type"], handelsbilanz["cost"][-1], handelsbilanz["depreciation"][-1]),
			("Handelsbilanzwert", "48.000,00", "41.500,00"),
		)
		self.assertEqual(
			(transfer["value_type"], transfer["depreciation"][-1]), ("Überleitungswert", "-1.000,00")
		)

	def test_without_fixed_assets_there_is_no_row(self):
		self.assertEqual(
			layout.print_sections([])["anlagenspiegel"]["rows"],
			[],
		)
		(row,) = layout.print_sections([], fixed_assets=[{"value_type": "", "position": ""}])[
			"anlagenspiegel"
		]["rows"]
		self.assertEqual((row["label"], row["value_type"], row["source"]), ("", "Steuerbilanzwert", ""))


class UeberleitungTest(TestCase):
	def test_each_entry_with_its_kind_amounts_and_reason(self):
		sections = layout.print_sections(
			[],
			transfers=[
				{
					"kind": "Wertänderung",
					"position": "bs.eqLiab.accruals.other",
					"position_label": "sonstige Rückstellungen",
					"current": -1500,
					"previous": 0,
					"reason": "Drohverlustrückstellung, § 5 Abs. 4a EStG",
				},
				{"position": "bs.ass.fixAss.tan"},
			],
			handelsbilanz=True,
		)
		self.assertEqual(
			sections["ueberleitung"],
			[
				{
					"kind": "Wertänderung",
					"label": "sonstige Rückstellungen",
					"concept": "bs.eqLiab.accruals.other",
					"current": "-1.500,00",
					"previous": "0,00",
					"reason": "Drohverlustrückstellung, § 5 Abs. 4a EStG",
				},
				{
					"kind": "",
					"label": "bs.ass.fixAss.tan",
					"concept": "bs.ass.fixAss.tan",
					"current": "0,00",
					"previous": "0,00",
					"reason": "",
				},
			],
		)


class HeadTest(TestCase):
	def test_names_the_bilanzierungsstandard_and_the_status_des_berichts_in_words(self):
		"""Leitfaden B.13; the labels of de-gcd-2025-04-01-label-de.xml."""
		for standard, status, words in (
			("HAOE", "", ("Einheitsbilanz (HAOE)", "")),
			("HGBM", "B", ("Handelsbilanz mit Überleitungsrechnung (HGBM)", "berichtigt")),
			("AO", "BG", ("Steuerbilanz (AO)", "berichtigt und geändert")),
		):
			with self.subTest(standard=standard):
				sections = layout.print_sections([], accounting_standard=standard, revision_status=status)
				self.assertEqual((sections["standard"], sections["revision_status"]), words)


class GermanTest(TestCase):
	def test_dots_between_the_thousands_and_a_comma_before_the_cents(self):
		self.assertEqual(layout.german(D("1234567.8")), "1.234.567,80")
		self.assertEqual(layout.german(D("-0.5")), "-0,50")
		self.assertEqual(layout.german(D("0")), "0,00")

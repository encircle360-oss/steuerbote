"""What the print format „Jahresabschluss“ and the Vorschau der Offenlegung show, from the rows of an Annual Accounts,
without a bench. The books are those of the invented Kleinstkapitalgesellschaft of steuerbote/hgb/tests/companies.py."""

from datetime import date
from decimal import Decimal
from unittest import TestCase

from steuerbote.hgb import upload
from steuerbote.hgb.disclosure import Mode
from steuerbote.hgb.size import SizeClass
from steuerbote.hgb.tests import companies
from steuerbote.steuerbote.doctype.annual_accounts import bridge, layout
from steuerbote.steuerbote.doctype.annual_accounts.bridge import Statement

KLEINST, KLEIN = SizeClass.KLEINST, SizeClass.KLEIN


def stored_rows():
	found = bridge.statements(
		2026, KLEINST, companies.KLEINST_2026, parents=companies.PARENTS, prior=companies.KLEINST_2025
	)
	rows = [
		{**row, "reported": row["amount"], "manual": 0} for row in bridge.line_rows(found, companies.PARENTS)
	]
	rows.append({"statement": "Aktiva", "concept": "x", "manual": 1, "shown": 1, "reported": 1})
	return rows


class BalanceSheetTest(TestCase):
	def setUp(self):
		self.rows = stored_rows()

	def test_shows_the_positions_with_an_amount_their_vermerke_and_the_total(self):
		aktiva = layout.balance_sheet(self.rows, Statement.AKTIVA)
		self.assertEqual(
			[(line["marker"], line["label"]) for line in aktiva],
			[
				("A.", "Anlagevermögen"),
				("B.", "Umlaufvermögen"),
				("", "davon Forderungen gegen Gesellschafter"),
				("C.", "Rechnungsabgrenzungsposten"),
				("", "Summe Aktiva"),
			],
		)
		self.assertEqual(
			{key: aktiva[0][key] for key in ("amount", "prior", "vermerk", "total", "level")},
			{
				"amount": Decimal("18400.40"),
				"prior": Decimal("21000.00"),
				"vermerk": False,
				"total": False,
				"level": "Buchstabe",
			},
		)
		self.assertTrue(aktiva[2]["vermerk"])
		self.assertTrue(aktiva[-1]["total"])
		passiva = layout.balance_sheet(self.rows, Statement.PASSIVA)
		self.assertEqual(passiva[-1]["amount"], aktiva[-1]["amount"])

	def test_puts_both_sides_side_by_side_with_the_totals_last(self):
		form = layout.account_form(self.rows)
		self.assertEqual(
			[(left and left["label"], right and right["label"]) for left, right in form[:2]],
			[("Anlagevermögen", "Eigenkapital"), ("Umlaufvermögen", "Rückstellungen")],
		)
		self.assertEqual(
			[(left and left["label"], right and right["label"]) for left, right in form[-2:]],
			[(None, "davon gegenüber Gesellschaftern"), ("Summe Aktiva", "Summe Passiva")],
		)
		left, right = form[-1]
		self.assertEqual(left["amount"], right["amount"])
		shorter = layout.account_form([row for row in self.rows if row.get("statement") != "Passiva"])
		self.assertEqual([right for _left, right in shorter], [None] * len(shorter))

	def test_shows_the_items_of_the_guv_with_an_amount(self):
		guv = layout.income_statement(self.rows)
		self.assertEqual(guv[0]["label"], "Umsatzerlöse")
		self.assertEqual(guv[-1]["label"], "Jahresüberschuss/Jahresfehlbetrag")
		self.assertNotIn("andere aktivierte Eigenleistungen", [line["label"] for line in guv])


class NotesTest(TestCase):
	def setUp(self):
		self.rows = [
			{"code": "ARBEITNEHMER", "label": "Arbeitnehmer", "answer": "ja", "published": 1, "amount": 0},
			{
				"code": "HAFTUNGSVERHAELTNISSE",
				"label": "Haftung",
				"answer": "ja",
				"text": "Bürgschaft",
				"published": 1,
				"amount": 15000,
			},
			{
				"code": "AUSSERGEWOEHNLICHES",
				"label": "Außergewöhnliches",
				"answer": "ja",
				"text": "Vergleich",
				"published": 0,
			},
			{"code": "FIRMENWERT", "label": "Firmenwert", "answer": "nein", "published": 1},
		]

	def test_shows_the_angaben_answered_ja(self):
		shown = layout.notes(self.rows, Decimal("23.75"), published_only=False)
		self.assertEqual(
			[(note["code"], note["text"], note["amount"]) for note in shown],
			[
				("ARBEITNEHMER", "", Decimal("23.75")),
				("HAFTUNGSVERHAELTNISSE", "Bürgschaft", Decimal("15000.00")),
				("AUSSERGEWOEHNLICHES", "Vergleich", None),
			],
		)

	def test_the_vorschau_shows_only_what_the_class_discloses(self):
		shown = layout.notes(self.rows, Decimal("23.75"), published_only=True)
		self.assertEqual([note["code"] for note in shown], ["ARBEITNEHMER", "HAFTUNGSVERHAELTNISSE"])


class RegisterAndSignaturesTest(TestCase):
	def test_names_the_data_of_264_abs_1a_and_the_liquidation(self):
		values = bridge.register_values(
			"Beispiel Werkstatt GmbH",
			{
				"registered_seat": "Musterstadt",
				"register_court": "Amtsgericht Musterstadt",
				"register_number": "HRB 12345",
			},
		)
		self.assertEqual(
			layout.register_lines(values, in_liquidation=False),
			[
				("Firma", "Beispiel Werkstatt GmbH"),
				("Sitz", "Musterstadt"),
				("Registergericht", "Amtsgericht Musterstadt"),
				("Registernummer", "HRB 12345"),
			],
		)
		self.assertEqual(
			layout.register_lines({}, in_liquidation=True)[-1], ("Liquidation", layout.LIQUIDATION)
		)

	def test_names_each_signature_with_place_day_and_gez(self):
		rows = [
			{
				"signatory_name": "Erika Beispiel",
				"function": "Geschäftsführerin",
				"place": "Musterstadt",
				"signed_on": date(2027, 5, 12),
			},
			{"signatory_name": "Max Muster", "function": "", "place": "", "signed_on": None},
			{"signatory_name": "Paula Prokura", "function": "", "place": "", "signed_on": "2027-05-13"},
		]
		self.assertEqual(
			layout.signature_lines(rows),
			[
				"Musterstadt, 12. Mai 2027: gez. Erika Beispiel, Geschäftsführerin",
				"gez. Max Muster",
				"13. Mai 2027: gez. Paula Prokura",
			],
		)


class VisibilityTest(TestCase):
	def test_a_kleinst_that_deposits_is_seen_only_on_request(self):
		shown = layout.visibility(KLEINST, Mode.HINTERLEGUNG)
		self.assertEqual(
			{key: shown[key] for key in ("parts", "below_balance_sheet", "public", "deposited")},
			{"parts": ["Bilanz"], "below_balance_sheet": True, "public": False, "deposited": True},
		)
		self.assertEqual(shown["notice"], layout.DEPOSITED)

	def test_klein_publishes_its_bilanz_and_its_anhang(self):
		shown = layout.visibility(KLEIN, Mode.OFFENLEGUNG)
		self.assertEqual(
			(shown["parts"], shown["public"], shown["notice"]), (["Bilanz", "Anhang"], True, layout.PUBLISHED)
		)

	def test_nothing_for_a_class_steuerbote_does_not_prepare(self):
		self.assertIsNone(layout.visibility(SizeClass.MITTELGROSS, Mode.OFFENLEGUNG))
		self.assertIsNone(layout.visibility(None, Mode.OFFENLEGUNG))


class UploadGuideTest(TestCase):
	def test_the_testplattform_comes_first_before_the_first_upload(self):
		guide = layout.upload_guide(KLEINST, Mode.HINTERLEGUNG, 2026, first_upload=True)
		self.assertEqual(guide["steps"][0]["title"], "Testplattform")
		self.assertIn("Hinterlegung wählen", [step["title"] for step in guide["steps"]])
		self.assertEqual(guide["steps"][0]["sources"], [upload.XBRL_TOOLS.title])
		self.assertEqual(
			(guide["filing"], guide["yearly"], guide["total"]),
			(Decimal("18.50"), Decimal("3.00"), Decimal("21.50")),
		)
		self.assertEqual(
			[method["fee"] for method in guide["identification"]],
			[Decimal("12.00"), Decimal("22.00"), Decimal("7.60")],
		)
		self.assertEqual(
			[record["label"] for record in guide["records"]],
			[
				"Übermittelt am",
				"Übermittelt von",
				"Auftragsnummer",
				"Auftragsbestätigung",
				"Eingestellt am",
				"Beleg",
				"Gebühren",
			],
		)

	def test_the_fields_of_the_web_form_are_unverified(self):
		guide = layout.upload_guide(KLEIN, Mode.OFFENLEGUNG, 2026, first_upload=False)
		self.assertNotIn("Testplattform", [step["title"] for step in guide["steps"]])
		form = guide["web_form"]
		self.assertEqual((form["text_field"], form["verified"]), ("Anhang", False))
		self.assertEqual(form["fields"][0], {"marker": "A.", "label": "Anlagevermögen"})

	def test_nothing_for_a_class_steuerbote_does_not_prepare(self):
		self.assertIsNone(layout.upload_guide(SizeClass.GROSS, Mode.OFFENLEGUNG, 2026, first_upload=True))
		self.assertIsNone(layout.upload_guide(None, Mode.OFFENLEGUNG, 2026, first_upload=True))

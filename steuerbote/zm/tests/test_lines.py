from decimal import Decimal
from unittest import TestCase

from steuerbote.zm.errors import ZmError
from steuerbote.zm.findings import Code
from steuerbote.zm.lines import (
	ART_KENNZAHL,
	KENNZAHL_ART,
	Art,
	Line,
	Meldezeile,
	Override,
	Validity,
	VoucherAmount,
	build,
)
from steuerbote.zm.tests.support import AUSTRIA, FIGURES, FRANCE, SPAIN, d, invoice


def statement(*amounts, validity=None, overrides=None):
	return build(amounts, FIGURES, validity=validity, overrides=overrides)


def codes(line: Line) -> list[Code]:
	return [finding.code for finding in line.findings]


class ArtTest(TestCase):
	def test_kennzahlen_41_42_and_21_are_the_arts_l_d_and_s(self):
		"""Form USt 1 A 2026, lines 19, 33 and 35, and the field umsatzart of ZMDO: L innergemeinschaftliche
		Lieferung, D Dreiecksgeschäft, S sonstige Leistung."""
		self.assertEqual(dict(KENNZAHL_ART), {"41": Art.L, "42": Art.D, "21": Art.S})
		self.assertEqual(dict(ART_KENNZAHL), {Art.L: "41", Art.D: "42", Art.S: "21"})

	def test_each_voucher_amount_has_the_art_of_its_kennzahl(self):
		self.assertIs(invoice("1", "10.00", kennzahl="42", destination="AT").art, Art.D)


class VoucherAmountTest(TestCase):
	def test_only_the_kennzahlen_of_the_zm(self):
		with self.assertRaisesRegex(ValueError, "no Art of the ZM"):
			invoice("1", "10.00", kennzahl="81")

	def test_amounts_are_exact_cents(self):
		with self.assertRaises(ValueError):
			invoice("1", "10.001")
		with self.assertRaises(TypeError):
			VoucherAmount("Sales Invoice:1", "41", 10.0)  # type: ignore[arg-type]

	def test_a_voucher_has_a_name(self):
		with self.assertRaisesRegex(ValueError, "voucher"):
			VoucherAmount("", "41", d("1.00"))
		with self.assertRaisesRegex(ValueError, "voucher"):
			VoucherAmount(None, "41", d("1.00"))  # type: ignore[arg-type]


class LinesTest(TestCase):
	def test_one_line_per_vat_id_and_art(self):
		"""Anleitung zur ZM, IV.8 and IV.11: the Bemessungsgrundlagen of one Erwerber „sind summiert für die jeweilige
		Umsatzart [...] in je einer Zeile gesondert einzutragen“; ZMDO rules 170045003 to 170045005 refuse a second
		line „die bis auf den Betrag identisch“ is."""
		result = statement(
			invoice("SINV-1", "20000.00"),
			invoice("SINV-2", "20000.00"),
			invoice("SINV-3", "15000.00", kennzahl="21"),
			invoice("SINV-4", "30000.00", kennzahl="42", vat_id=FRANCE, destination="FR"),
		)
		self.assertEqual(
			[(line.vat_id, line.art, line.amount) for line in result.lines],
			[
				(AUSTRIA, Art.L, d("40000.00")),
				(AUSTRIA, Art.S, d("15000.00")),
				(FRANCE, Art.D, d("30000.00")),
			],
		)
		self.assertEqual(
			[item.voucher for item in result.lines[0].vouchers],
			["Sales Invoice:SINV-1", "Sales Invoice:SINV-2"],
		)

	def test_spellings_of_one_vat_id_make_one_line(self):
		result = statement(
			invoice("1", "10.00", vat_id="ATU 123 456 78"), invoice("2", "5.00", vat_id="atu12345678")
		)
		self.assertEqual([(line.vat_id, line.amount) for line in result.lines], [(AUSTRIA, d("15.00"))])

	def test_lines_follow_the_vat_id_and_the_form(self):
		result = statement(
			invoice("1", "1.00", kennzahl="21", vat_id=SPAIN),
			invoice("2", "1.00", kennzahl="42", vat_id=AUSTRIA, destination="AT"),
			invoice("3", "1.00", vat_id=AUSTRIA),
			invoice("4", "1.00", kennzahl="21", vat_id=AUSTRIA),
		)
		self.assertEqual(
			[line.key for line in result.lines],
			[(AUSTRIA, Art.L), (AUSTRIA, Art.D), (AUSTRIA, Art.S), (SPAIN, Art.S)],
		)

	def test_amounts_drop_their_cents(self):
		"""The ZM reports whole euros (ZMDO betrag: GeldBetragOhneCent); Steuerbote drops the cents towards zero,
		as for the Bemessungsgrundlagen of the Voranmeldung."""
		line = statement(invoice("1", "1000.99")).lines[0]
		self.assertEqual((line.amount, line.computed, line.reported), (d("1000.99"), d("1000"), d("1000")))
		self.assertEqual(statement(invoice("1", "-1000.99")).lines[0].reported, d("-1000"))

	def test_discounts_and_credit_notes_reduce_the_line_of_their_period(self):
		"""BZSt „Berichtigung einer ZM“, Rabatte: 80,000 euros of deliveries less a discount of 5,000 euros on an
		earlier delivery are reported as 75,000 euros; Anleitung zur ZM, IV.10: a negative sum gets a minus."""
		netted = statement(
			invoice("SINV-2", "80000.00"), invoice("PE-1", "-5000.00", voucher_type="Payment Entry")
		)
		self.assertEqual(netted.meldezeilen, (Meldezeile(AUSTRIA, Art.L, d("75000")),))
		negative = statement(invoice("SINV-R", "-5000.00"))
		self.assertEqual(negative.meldezeilen, (Meldezeile(AUSTRIA, Art.L, d("-5000")),))

	def test_lines_of_zero_euros_are_not_reported(self):
		"""Anleitung zur ZM, III.1: „Sog. „Nullmeldungen“ sind nicht abzugeben.“ ZMDO rule 170045002."""
		result = statement(
			invoice("SINV-1", "100.00"),
			invoice("SINV-2", "-100.00"),
			invoice("SINV-3", "0.40", vat_id=FRANCE),
		)
		self.assertEqual([line.reported for line in result.lines], [d("0"), d("0")])
		self.assertEqual(result.meldezeilen, ())
		self.assertTrue(result.ready)


class BlockingTest(TestCase):
	def test_voucher_without_customer(self):
		result = statement(invoice("JV-1", "500.00", party=None, vat_id=None, voucher_type="Journal Entry"))
		line = result.lines[0]
		self.assertEqual((line.vat_id, codes(line)), ("", [Code.NO_PARTY]))
		self.assertEqual(
			line.findings[0].text, "Beleg JV-1 geht mit 500,00 € in Kz 41 ein, nennt aber keinen Kunden."
		)
		self.assertEqual(line.findings[0].voucher, "Journal Entry:JV-1")
		self.assertTrue(line.blocked)
		self.assertFalse(result.ready)
		self.assertEqual(result.meldezeilen, ())

	def test_voucher_without_customer_but_with_a_vat_id(self):
		line = statement(invoice("JV-1", "500.00", party=" ")).lines[0]
		self.assertEqual((line.vat_id, codes(line)), (AUSTRIA, [Code.NO_PARTY]))
		self.assertTrue(line.blocked)

	def test_voucher_without_vat_id(self):
		"""§ 18a Absatz 7 Satz 1 UStG: the ZM names „die Umsatzsteuer-Identifikationsnummer jedes Erwerbers“. The
		number is the one the voucher gives, as an invoice keeps it from when it was made, so the customer may well
		have one by now."""
		line = statement(invoice("SINV-1", "1200.50", party="Muster SARL", vat_id=" ")).lines[0]
		self.assertEqual(codes(line), [Code.NO_VAT_ID])
		self.assertEqual(
			line.findings[0].text,
			"Beleg SINV-1 geht mit 1.200,50 € in Kz 41 ein, nennt aber keine USt-IdNr. des Kunden Muster SARL.",
		)
		self.assertEqual(line.findings[0].party, "Muster SARL")
		self.assertTrue(line.blocked)

	def test_malformed_vat_ids(self):
		cases = {
			"AT12": "„AT12“ ist keine USt-IdNr. im Format der ZM: Länderkennzeichen und Buchstaben, Ziffern, + oder *, zusammen 7 bis 14 Zeichen.",
			"DE123456789": "„DE123456789“ ist eine deutsche USt-IdNr.; die ZM nennt nur USt-IdNrn. anderer Mitgliedstaaten.",
			"GB123456789": "„GB123456789“ ist eine britische USt-IdNr.; das Länderkennzeichen GB gilt nur für Meldezeiträume bis 2020.",
			"CH123456789": "„CH123456789“ beginnt mit keinem Länderkennzeichen eines anderen Mitgliedstaats.",
		}
		for vat_id, text in cases.items():
			with self.subTest(vat_id):
				line = statement(invoice("1", "10.00", vat_id=vat_id)).lines[0]
				self.assertEqual((line.vat_id, codes(line)), (vat_id, [Code.MALFORMED_VAT_ID]))
				self.assertEqual(line.findings[0].text, text)
				self.assertEqual(line.findings[0].party, "Muster GmbH")
				self.assertFalse(line.valid)
				self.assertTrue(line.blocked)
				self.assertIsNone(line.meldezeile)

	def test_northern_ireland_for_goods_but_not_for_services(self):
		result = statement(
			invoice("1", "10.00", vat_id="XI123456789"),
			invoice("2", "10.00", kennzahl="21", vat_id="XI123456789"),
		)
		goods, services = result.lines
		self.assertEqual((goods.art, codes(goods)), (Art.L, []))
		self.assertEqual((services.art, codes(services)), (Art.S, [Code.MALFORMED_VAT_ID]))
		self.assertEqual(
			services.findings[0].text,
			"„XI123456789“ ist eine nordirische USt-IdNr.; sie gilt in der ZM nur für Lieferungen, nicht für sonstige Leistungen.",
		)
		self.assertEqual(result.meldezeilen, (Meldezeile("XI123456789", Art.L, d("10")),))

	def test_invalid_and_unconfirmed_vat_ids(self):
		"""The confirmation of § 18e UStG lives in another package; its outcome is an input here."""
		result = statement(
			invoice("1", "10.00", vat_id=AUSTRIA),
			invoice("2", "10.00", vat_id=FRANCE),
			invoice("3", "10.00", vat_id=SPAIN),
			validity={AUSTRIA: Validity.INVALID, FRANCE: Validity.UNCONFIRMED, SPAIN: Validity.CONFIRMED},
		)
		austria, spain, france = result.lines
		self.assertEqual(codes(austria), [Code.INVALID_VAT_ID])
		self.assertEqual(
			austria.findings[0].text, f"Die USt-IdNr. {AUSTRIA} ist laut Bestätigungsabfrage ungültig."
		)
		self.assertEqual(codes(france), [Code.UNCONFIRMED_VAT_ID])
		self.assertEqual(france.findings[0].text, f"Die USt-IdNr. {FRANCE} ist nicht bestätigt.")
		self.assertEqual(codes(spain), [])
		self.assertEqual([line.blocked for line in result.lines], [True, False, True])

	def test_a_vat_id_without_a_check_result_passes(self):
		self.assertTrue(statement(invoice("1", "10.00")).ready)

	def test_dreiecksgeschaeft_needs_a_vat_id_of_the_destination(self):
		"""§ 18a Absatz 7 Satz 1 Nummer 4 Buchstabe a UStG: the USt-IdNr. of the last Abnehmer „die diesem in dem
		Mitgliedstaat erteilt worden ist, in dem die Versendung oder Beförderung beendet worden ist“."""
		fitting = statement(invoice("1", "10.00", kennzahl="42", vat_id=FRANCE, destination="France")).lines[
			0
		]
		self.assertEqual(codes(fitting), [])
		elsewhere = statement(
			invoice("2", "10.00", kennzahl="42", vat_id=FRANCE, destination="Austria")
		).lines[0]
		self.assertEqual(codes(elsewhere), [Code.DESTINATION])
		self.assertEqual(
			elsewhere.findings[0].text,
			f"Beleg 2: Die Lieferung endet in Austria, die USt-IdNr. {FRANCE} des letzten Abnehmers ist nicht in diesem Land erteilt.",
		)
		nowhere = statement(invoice("3", "10.00", kennzahl="42", vat_id=FRANCE)).lines[0]
		self.assertEqual(codes(nowhere), [Code.DESTINATION])
		self.assertEqual(
			nowhere.findings[0].text,
			f"Beleg 3 nennt nicht, in welchem Land die Lieferung an den letzten Abnehmer {FRANCE} endet.",
		)
		self.assertTrue(elsewhere.blocked and nowhere.blocked)

	def test_the_destination_matters_only_for_dreiecksgeschaefte(self):
		self.assertEqual(
			codes(statement(invoice("1", "10.00", vat_id=FRANCE, destination="Austria")).lines[0]), []
		)

	def test_findings_of_all_lines(self):
		result = statement(invoice("1", "10.00", party=None), invoice("2", "10.00", vat_id="DE123456789"))
		self.assertEqual(
			[finding.code for finding in result.findings], [Code.NO_PARTY, Code.MALFORMED_VAT_ID]
		)


class OverrideTest(TestCase):
	def test_an_override_with_a_reason_lifts_the_block(self):
		"""Decision of the maintainer: an invalid USt-IdNr. holds the ZM back, overridable per line."""
		override = Override(d("1000"), "Nummer am Liefertag bestätigt, Nachweis in der Akte")
		result = statement(
			invoice("1", "999.99"),
			validity={AUSTRIA: Validity.INVALID},
			overrides={(AUSTRIA, Art.L): override},
		)
		line = result.lines[0]
		self.assertEqual(codes(line), [Code.INVALID_VAT_ID])
		self.assertEqual((line.override, line.computed, line.reported), (override, d("999"), d("1000")))
		self.assertFalse(line.blocked)
		self.assertTrue(result.ready)
		self.assertEqual(result.meldezeilen, (Meldezeile(AUSTRIA, Art.L, d("1000")),))

	def test_a_line_without_a_valid_vat_id_can_only_be_dropped(self):
		dropped = statement(
			invoice("1", "10.00", vat_id=None), overrides={("", Art.L): Override(d("0"), "Verbringen")}
		)
		self.assertFalse(dropped.lines[0].blocked)
		self.assertTrue(dropped.ready)
		kept = statement(
			invoice("1", "10.00", vat_id="DE123456789"),
			overrides={("DE123456789", Art.L): Override(d("10"), "Kunde")},
		)
		self.assertTrue(kept.lines[0].blocked)
		self.assertIsNone(kept.lines[0].meldezeile)

	def test_an_override_of_zero_drops_a_valid_line(self):
		result = statement(
			invoice("1", "10.00"), overrides={(AUSTRIA, Art.L): Override(d("0"), "Gehört nicht in die ZM")}
		)
		self.assertEqual((result.meldezeilen, result.ready), ((), True))

	def test_an_override_without_vouchers_is_a_line_of_its_own(self):
		"""Verbringen (§ 6a Absatz 2 UStG) is reported under the company's own USt-IdNr. in the other member state
		(§ 18a Absatz 7 Satz 1 Nummer 2 UStG); no voucher names it, so it is entered by hand."""
		own = "ATU99999999"
		result = statement(
			overrides={("atu 99999999", Art.L): Override(d("2500"), "Verbringen in das Lager Wien")}
		)
		line = result.lines[0]
		self.assertEqual(
			(line.vat_id, line.amount, line.vouchers, line.reported), (own, d("0"), (), d("2500"))
		)
		self.assertEqual(result.meldezeilen, (Meldezeile(own, Art.L, d("2500")),))

	def test_two_overrides_of_one_line(self):
		overrides = {(AUSTRIA, Art.L): Override(d("1"), "a"), ("ATU 12345678", Art.L): Override(d("2"), "b")}
		with self.assertRaisesRegex(ZmError, "overridden twice"):
			statement(invoice("1", "1.00"), overrides=overrides)

	def test_an_override_has_whole_euros_and_a_reason(self):
		with self.assertRaisesRegex(ZmError, "whole euros"):
			Override(d("10.50"), "Grund")
		with self.assertRaisesRegex(ZmError, "whole euros"):
			Override(Decimal("Infinity"), "Grund")
		with self.assertRaises(TypeError):
			Override(10, "Grund")  # type: ignore[arg-type]
		with self.assertRaisesRegex(ZmError, "Begründung"):
			Override(d("10"), " ")
		with self.assertRaisesRegex(ZmError, "Begründung"):
			Override(d("10"), None)  # type: ignore[arg-type]
		self.assertEqual(Override(d("10.00"), "Grund").amount, d("10"))


class MeldezeileTest(TestCase):
	def test_a_meldezeile_holds_a_vat_id_the_zm_takes(self):
		self.assertEqual(Meldezeile(AUSTRIA, "L", d("10")).art, Art.L)  # type: ignore[arg-type]
		with self.assertRaisesRegex(ZmError, "not a USt-IdNr."):
			Meldezeile("atu12345678", Art.L, d("10"))
		with self.assertRaisesRegex(ZmError, "not a USt-IdNr."):
			Meldezeile("XI123456789", Art.S, d("10"))
		with self.assertRaisesRegex(ZmError, "not a USt-IdNr."):
			Meldezeile(None, Art.L, d("10"))  # type: ignore[arg-type]

	def test_a_line_without_a_vat_id_reports_nothing(self):
		for vat_id in (None, "", " "):
			with self.subTest(vat_id):
				line = Line(vat_id, Art.L, (invoice("1", "10.00", vat_id=vat_id),))  # type: ignore[arg-type]
				self.assertFalse(line.valid)
				self.assertIsNone(line.meldezeile)

	def test_a_meldezeile_holds_whole_euros(self):
		with self.assertRaisesRegex(ZmError, "whole euros"):
			Meldezeile(AUSTRIA, Art.L, d("10.10"))
		self.assertEqual(Meldezeile(AUSTRIA, Art.L, d("-7")).key, (AUSTRIA, Art.L))

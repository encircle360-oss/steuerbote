from datetime import date
from decimal import Decimal
from unittest import TestCase

from steuerbote.vatid.exemption import consequence
from steuerbote.zm.errors import ZmError
from steuerbote.zm.findings import Code, Severity
from steuerbote.zm.lines import (
	ART_KENNZAHL,
	KENNZAHL_ART,
	Art,
	ConfirmationAge,
	Line,
	Meldezeile,
	Override,
	Validity,
	VoucherAmount,
	build,
)
from steuerbote.zm.tests.support import AUSTRIA, FIGURES, FRANCE, SPAIN, d, invoice

NO_VAT_ID_ADVICE = (
	"Berichtige die Rechnung, oder nimm die Zeile mit der Korrektur 0 und einer Begründung aus der ZM."
)
MALFORMED_ADVICE = (
	"Berichtige die USt-IdNr. in der Rechnung, oder nimm die Zeile mit der Korrektur 0 und einer Begründung "
	"aus der ZM."
)
INVALID_ADVICE = (
	"Belegt eine frühere Bestätigung die Gültigkeit am Tag des Umsatzes, gib die USt-IdNr. mit Begründung frei; "
	"sonst berichtige die Rechnung."
)
UNCONFIRMED_ADVICE = (
	"Die Bestätigung soll spätestens zum Umsatz vorliegen (UStAE 6a.8 Abs. 6): „USt-IdNrn. prüfen“ fragt beim "
	"BZSt an; liegt eine Bestätigung anders vor, gib die USt-IdNr. mit Begründung frei."
)


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
			"Beleg SINV-1 geht mit 1.200,50 € in Kz 41 ein, nennt aber keine USt-IdNr. des Kunden Muster SARL. "
			f"{consequence('41')} {NO_VAT_ID_ADVICE}",
		)
		self.assertEqual(line.findings[0].party, "Muster SARL")
		self.assertTrue(line.blocked)

	def test_a_customer_whose_name_ends_with_a_full_stop_ends_the_sentence_once(self):
		line = statement(invoice("SINV-2", "10.00", party="Muster B.V.", vat_id=None)).lines[0]
		self.assertTrue(
			line.findings[0].text.startswith("Beleg SINV-2 geht mit 10,00 € in Kz 41 ein, nennt ")
		)
		self.assertIn("des Kunden Muster B.V. Ohne", line.findings[0].text)

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
				self.assertEqual(line.findings[0].text, f"{text} {consequence('41')} {MALFORMED_ADVICE}")
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
			"„XI123456789“ ist eine nordirische USt-IdNr.; sie gilt in der ZM nur für Lieferungen, nicht für "
			f"sonstige Leistungen. {consequence('21')} {MALFORMED_ADVICE}",
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
			austria.findings[0].text,
			f"Die USt-IdNr. {AUSTRIA} ist laut Bestätigungsabfrage ungültig. {consequence('41')} {INVALID_ADVICE}",
		)
		self.assertEqual(codes(france), [Code.UNCONFIRMED_VAT_ID])
		self.assertEqual(
			france.findings[0].text, f"Die USt-IdNr. {FRANCE} ist nicht bestätigt. {UNCONFIRMED_ADVICE}"
		)
		self.assertEqual(codes(spain), [])
		self.assertEqual([line.blocked for line in result.lines], [True, False, True])

	def test_the_findings_name_the_day_of_the_confirmation_they_rest_on(self):
		"""A confirmation holds for the moment of its query („Bestätigungen für zurückliegende Zeitpunkte oder
		Zeiträume sind nicht möglich.“, BZSt, FAQ), so the finding says how old it is."""
		result = build(
			(invoice("1", "10.00", vat_id=AUSTRIA), invoice("2", "10.00", vat_id=FRANCE)),
			FIGURES,
			validity={AUSTRIA: Validity.INVALID, FRANCE: Validity.UNCONFIRMED},
			asked={AUSTRIA: date(2025, 3, 2), FRANCE: date(2026, 11, 20)},
		)
		self.assertEqual(
			[finding.text for finding in result.findings],
			[
				f"Die USt-IdNr. {AUSTRIA} ist laut Bestätigungsabfrage vom 2. März 2025 ungültig. "
				f"{consequence('41')} {INVALID_ADVICE}",
				f"Die USt-IdNr. {FRANCE} ist nicht bestätigt; die Bestätigungsabfrage vom 20. November 2026 "
				f"ergab kein Ergebnis. {UNCONFIRMED_ADVICE}",
			],
		)

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
		self.assertEqual(
			(line.override, line.computed, line.reported),
			(Override(override.amount, override.reason, basis=d("999.99")), d("999"), d("1000")),
		)
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

	def test_a_line_of_its_own_says_that_it_was_entered_by_hand_and_why(self):
		"""No voucher in the ledger stands behind a Verbringen, so its Begründung explains the line: a hint names
		both, and the line holds nothing back."""
		own = "ATU99999999"
		result = statement(overrides={(own, Art.L): Override(d("2500"), "Verbringen in das Lager Wien")})
		line = result.lines[0]
		self.assertTrue(line.manual)
		self.assertEqual(
			[(finding.code, finding.severity, finding.text) for finding in line.findings],
			[
				(
					Code.OWN_LINE,
					Severity.HINT,
					"Die Zeile ATU99999999 (L) ist von Hand eingetragen und steht ohne Beleg im Hauptbuch mit "
					"2.500,00 € in der ZM; Begründung: Verbringen in das Lager Wien.",
				)
			],
		)
		self.assertEqual((line.blocked, result.ready), (False, True))

	def test_a_line_with_vouchers_is_no_line_of_its_own_even_with_an_override(self):
		result = statement(
			invoice("1", "999.99"), overrides={(AUSTRIA, Art.L): Override(d("1000"), "Nachweis liegt vor.")}
		)
		self.assertFalse(result.lines[0].manual)
		self.assertNotIn(Code.OWN_LINE, codes(result.lines[0]))

	def test_a_line_of_its_own_needs_the_vat_id_it_reports(self):
		"""§ 18a Absatz 7 Satz 1 Nummer 2 UStG: a Verbringen is reported under „die Umsatzsteuer-
		Identifikationsnummer des Unternehmers in den Mitgliedstaaten, in die er Gegenstände verbracht hat“."""
		with self.assertRaisesRegex(ZmError, "needs the USt-IdNr. it reports"):
			statement(overrides={("", Art.L): Override(d("2500"), "Verbringen")})
		left_over = statement(overrides={("", Art.L): Override(d("0"), "Verbringen")})
		self.assertEqual((left_over.meldezeilen, left_over.findings, left_over.ready), ((), (), True))

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


class OverrideBasisTest(TestCase):
	"""An override is made against the ledger amount of its line. When the ledger books another amount later, such
	as a late invoice of the same customer, the override would hide it from the ZM and from its Berichtigung, which
	has to report the full correct sum (§ 18a Absatz 10 UStG; Anleitung zur ZM, IV.12.2)."""

	def test_a_new_override_remembers_the_ledger_amount_of_its_line(self):
		line = statement(
			invoice("1", "999.99"), overrides={(AUSTRIA, Art.L): Override(d("1000"), "Nachweis")}
		).lines[0]
		self.assertEqual(line.override.basis, d("999.99"))
		self.assertNotIn(Code.OVERRIDE_STALE, codes(line))

	def test_an_override_made_against_another_ledger_amount_holds_the_line(self):
		override = Override(d("55000"), "Nummer war am Liefertag bestätigt", basis=d("55000.99"))
		result = statement(
			invoice("1", "55000.99"),
			invoice("2", "2000.00"),
			validity={AUSTRIA: Validity.UNCONFIRMED},
			overrides={(AUSTRIA, Art.L): override},
		)
		line = result.lines[0]
		self.assertEqual(codes(line), [Code.UNCONFIRMED_VAT_ID, Code.OVERRIDE_STALE])
		self.assertEqual(
			line.findings[1].text,
			f"Die Korrektur der Zeile {AUSTRIA} (L) auf 55.000,00 € wurde bei 55.000,99 € im Hauptbuch eingetragen; "
			"das Hauptbuch bucht jetzt 57.000,99 €. Die Zeile hält die Meldung an, bis die Korrektur bestätigt ist: "
			"Passe Betrag oder Begründung an, oder lösche die Korrektur, dann meldet die Zeile das Hauptbuch.",
		)
		self.assertIs(line.findings[1].severity, Severity.ERROR)
		self.assertEqual(line.override.basis, d("55000.99"))
		self.assertTrue(line.blocked)
		self.assertFalse(result.ready)

	def test_neither_the_override_nor_a_release_lifts_the_block_of_a_changed_ledger(self):
		result = build(
			(invoice("1", "10.00"),),
			FIGURES,
			overrides={(AUSTRIA, Art.L): Override(d("0"), "Gehört nicht in die ZM", basis=d("5.00"))},
			accepted={(AUSTRIA, Art.L): "Bestätigung liegt vor"},
		)
		self.assertTrue(result.lines[0].blocked)

	def test_an_override_of_its_ledger_amount_holds_nothing(self):
		result = statement(
			invoice("1", "10.00"),
			overrides={(AUSTRIA, Art.L): Override(d("12"), "Nachweis", basis=d("10.00"))},
		)
		self.assertEqual((codes(result.lines[0]), result.ready), ([], True))

	def test_a_line_by_hand_holds_once_vouchers_book_on_it(self):
		own = "ATU99999999"
		by_hand = Override(d("2500"), "Verbringen in das Lager Wien", basis=d("0"))
		self.assertTrue(statement(overrides={(own, Art.L): by_hand}).ready)
		booked = statement(invoice("1", "300.00", vat_id=own), overrides={(own, Art.L): by_hand})
		self.assertEqual(codes(booked.lines[0]), [Code.OVERRIDE_STALE])
		self.assertFalse(booked.ready)

	def test_a_line_without_vat_id_names_itself_so(self):
		result = statement(
			invoice("1", "10.00", vat_id=None),
			overrides={("", Art.L): Override(d("0"), "Steuerpflichtig behandelt", basis=d("4.00"))},
		)
		self.assertTrue(
			result.lines[0]
			.findings[-1]
			.text.startswith("Die Korrektur der Zeile ohne USt-IdNr. (L) auf 0,00 €")
		)

	def test_the_basis_is_an_amount_in_cents(self):
		with self.assertRaises(ValueError):
			Override(d("10"), "Grund", basis=d("1.001"))
		self.assertIsNone(Override(d("10"), "Grund").basis)

	def test_an_override_whose_basis_is_unknown_holds_the_line_until_it_is_confirmed(self):
		"""An override from before Steuerbote kept the basis has the ledger amount of the day of the update as its
		basis, which may already include a late invoice; it holds its line even where that amount is the ledger's."""
		override = Override(d("55000"), "Nachweis", basis=d("57000.99"), basis_unknown=True)
		result = statement(
			invoice("1", "55000.99"), invoice("2", "2000.00"), overrides={(AUSTRIA, Art.L): override}
		)
		line = result.lines[0]
		self.assertEqual(codes(line), [Code.OVERRIDE_STALE])
		self.assertEqual(
			line.findings[0].text,
			f"Die Korrektur der Zeile {AUSTRIA} (L) auf 55.000,00 € stammt aus einer Version von Steuerbote, die nicht "
			"festhielt, bei welchem Betrag im Hauptbuch sie eingetragen wurde; das Hauptbuch bucht jetzt 57.000,99 €. "
			"Die Zeile hält die Meldung an, bis die Korrektur bestätigt ist: Prüfen Sie sie gegen das Hauptbuch und "
			"ändern Sie Betrag oder Begründung, oder löschen Sie die Korrektur, dann meldet die Zeile das Hauptbuch.",
		)
		self.assertTrue(line.override.basis_unknown)
		self.assertTrue(line.blocked)
		self.assertFalse(result.ready)
		self.assertFalse(Override(d("10"), "Grund").basis_unknown)


class AcceptanceTest(TestCase):
	"""Releasing an unconfirmed or invalid USt-IdNr. is not the same as reporting another amount: the line keeps the
	ledger amount, and only the block of its number lifts (decision of the maintainer, docs/zm.md)."""

	def test_a_release_with_a_reason_lifts_the_block_of_the_number_and_keeps_the_ledger_amount(self):
		result = build(
			(invoice("1", "55000.99"), invoice("2", "2000.00")),
			FIGURES,
			validity={AUSTRIA: Validity.UNCONFIRMED, FRANCE: Validity.INVALID},
			accepted={("atu 12345678", Art.L): "Bestätigt am Liefertag, Ausdruck in der Akte"},
		)
		line = result.lines[0]
		self.assertEqual(codes(line), [Code.UNCONFIRMED_VAT_ID, Code.VAT_ID_ACCEPTED])
		self.assertEqual(
			line.findings[1].text,
			f"Die USt-IdNr. {AUSTRIA} ist für die Zeile L freigegeben; Begründung: Bestätigt am Liefertag, "
			"Ausdruck in der Akte.",
		)
		self.assertIs(line.findings[1].severity, Severity.HINT)
		self.assertEqual(
			(line.acceptance, line.override, line.reported),
			(
				"Bestätigt am Liefertag, Ausdruck in der Akte",
				None,
				d("57000"),
			),
		)
		self.assertFalse(line.blocked)
		self.assertTrue(result.ready)

	def test_a_line_names_the_findings_that_still_hold_it(self):
		result = build(
			(invoice("1", "10.00"), invoice("2", "10.00", vat_id=FRANCE)),
			FIGURES,
			validity={AUSTRIA: Validity.UNCONFIRMED, FRANCE: Validity.UNCONFIRMED},
			accepted={(AUSTRIA, Art.L): "Grund"},
		)
		austria, france = result.lines
		self.assertEqual(austria.holding_findings, ())
		self.assertEqual([finding.code for finding in france.holding_findings], [Code.UNCONFIRMED_VAT_ID])

	def test_a_release_lifts_an_invalid_number_as_well(self):
		result = build(
			(invoice("1", "10.00"),),
			FIGURES,
			validity={AUSTRIA: Validity.INVALID},
			accepted={(AUSTRIA, Art.L): "Gültig laut Bestätigung vom Liefertag"},
		)
		self.assertTrue(result.ready)

	def test_a_release_lifts_nothing_but_the_confirmation(self):
		cases = {
			"no vat id": invoice("1", "10.00", vat_id=None),
			"malformed": invoice("1", "10.00", vat_id="DE123456789"),
			"destination": invoice("1", "10.00", kennzahl="42", vat_id=FRANCE, destination="Austria"),
		}
		for name, voucher in cases.items():
			with self.subTest(name):
				art = voucher.art
				key = (build((voucher,), FIGURES).lines[0].vat_id, art)
				result = build((voucher,), FIGURES, accepted={key: "Grund"})
				self.assertTrue(result.lines[0].blocked)
				self.assertNotIn(Code.VAT_ID_ACCEPTED, codes(result.lines[0]))

	def test_a_release_without_reason_or_without_line_does_nothing(self):
		result = build(
			(invoice("1", "10.00"),),
			FIGURES,
			validity={AUSTRIA: Validity.UNCONFIRMED},
			accepted={(AUSTRIA, Art.L): " ", (FRANCE, Art.L): "Grund"},
		)
		self.assertEqual([line.vat_id for line in result.lines], [AUSTRIA])
		self.assertEqual(result.lines[0].acceptance, "")
		self.assertFalse(result.ready)

	def test_a_release_of_a_confirmed_number_says_nothing(self):
		result = build(
			(invoice("1", "10.00"),),
			FIGURES,
			validity={AUSTRIA: Validity.CONFIRMED},
			accepted={(AUSTRIA, Art.L): "Grund"},
		)
		self.assertEqual(codes(result.lines[0]), [])


class CorrectionReadinessTest(TestCase):
	"""A Berichtigung reports the lines that change what the BZSt holds; a line it repeats unchanged is not in its
	file, so the confirmation of its number does not hold the Berichtigung back. A changed ledger behind an override
	always does."""

	def test_an_unchanged_line_with_an_unconfirmed_number_holds_no_berichtigung(self):
		result = statement(
			invoice("1", "10000.00"),
			invoice("2", "4000.00", kennzahl="21", vat_id=FRANCE),
			validity={AUSTRIA: Validity.UNCONFIRMED, FRANCE: Validity.CONFIRMED},
		)
		held = {(AUSTRIA, Art.L): d("10000"), (FRANCE, Art.S): d("2500")}
		self.assertFalse(result.ready)
		self.assertEqual(result.holding(held), ())
		self.assertTrue(result.ready_against(held))
		self.assertEqual([line.vat_id for line in result.holding(None)], [AUSTRIA])
		self.assertFalse(result.ready_against(None))

	def test_a_changed_line_holds_it(self):
		result = statement(invoice("1", "12000.00"), validity={AUSTRIA: Validity.UNCONFIRMED})
		self.assertFalse(result.ready_against({(AUSTRIA, Art.L): d("10000")}))

	def test_a_changed_ledger_behind_an_override_holds_it_even_when_the_amount_is_as_filed(self):
		result = statement(
			invoice("1", "57000.99"),
			validity={AUSTRIA: Validity.UNCONFIRMED},
			overrides={(AUSTRIA, Art.L): Override(d("55000"), "Nachweis", basis=d("55000.99"))},
		)
		self.assertFalse(result.ready_against({(AUSTRIA, Art.L): d("55000")}))

	def test_a_new_line_the_zm_cannot_take_holds_it(self):
		result = statement(invoice("1", "10.00", vat_id="DE123456789"))
		self.assertFalse(result.ready_against({}))


class ConfirmationAgeTest(TestCase):
	"""As at the Voranmeldung, a confirmation older than the settings allow gets a hint; it holds nothing back."""

	def test_a_confirmation_older_than_allowed_gets_a_hint(self):
		result = build(
			(invoice("1", "10.00"), invoice("2", "10.00", vat_id=FRANCE)),
			FIGURES,
			validity={AUSTRIA: Validity.CONFIRMED, FRANCE: Validity.CONFIRMED},
			asked={AUSTRIA: date(2026, 7, 1), FRANCE: date(2026, 8, 2)},
			confirmation_age=ConfirmationAge(date(2026, 10, 31), 90),
		)
		austria, france = result.lines
		self.assertEqual(codes(austria), [Code.CONFIRMATION_STALE])
		self.assertEqual(
			austria.findings[0].text,
			f"Die USt-IdNr. {AUSTRIA} ist zuletzt am 1. Juli 2026 bestätigt worden, 122 Tage vor dem Ende der "
			"Monate der Meldung; die Einstellungen lassen höchstens 90 Tage zu. „USt-IdNrn. prüfen“ fragt erneut.",
		)
		self.assertIs(austria.findings[0].severity, Severity.HINT)
		self.assertEqual(codes(france), [])
		self.assertTrue(result.ready)

	def test_only_a_confirmed_number_ages(self):
		result = build(
			(invoice("1", "10.00"),),
			FIGURES,
			validity={AUSTRIA: Validity.UNCONFIRMED},
			asked={AUSTRIA: date(2025, 1, 1)},
			confirmation_age=ConfirmationAge(date(2026, 10, 31), 90),
		)
		self.assertEqual(codes(result.lines[0]), [Code.UNCONFIRMED_VAT_ID])

	def test_the_age_is_a_number_of_days_from_0_on(self):
		with self.assertRaises(ValueError):
			ConfirmationAge(date(2026, 10, 31), -1)


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

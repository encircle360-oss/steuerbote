"""The Vorauszahlungssoll of line 125, the Abschlusszahlung of Kz 820 and the day it is due."""

from datetime import date
from decimal import Decimal
from unittest import TestCase

from steuerbote.ustjahr.form import Finding, Severity
from steuerbote.ustjahr.soll import (
	MESSAGES,
	MISSING_PERIOD,
	OTHER_YEAR,
	OVERRIDDEN,
	PAYMENTS,
	PERIOD_TWICE,
	SONDERVORAUSZAHLUNG,
	WITHOUT_REASON,
	Filed,
	FiledKennzahl,
	Override,
	SollError,
	SollSource,
	abschlusszahlung,
	payment_due,
	vorauszahlungssoll,
)
from steuerbote.ustva.period import Period
from steuerbote.ustva.rounding import ZERO

MONTHS = tuple(Period.month(2026, month) for month in range(1, 13))
QUARTERS = tuple(Period.quarter(2026, quarter) for quarter in range(1, 5))
SONDERVORAUSZAHLUNG_2026 = Decimal("1100.00")


def monthly(kz83: str = "1000.00", december: str = "-100.00", kz39: str = "1100.00") -> list[Filed]:
	"""Twelve Voranmeldungen; the last credits the Sondervorauszahlung in Kz 39 (§ 48 Absatz 4 UStDV)."""
	filed = [Filed(period, f"UStVA-2026-{period.code}", Decimal(kz83)) for period in MONTHS[:-1]]
	return [*filed, Filed(MONTHS[-1], "UStVA-2026-12", Decimal(december), Decimal(kz39))]


class SollTest(TestCase):
	def test_is_the_sum_of_kz_83_and_the_sondervorauszahlung(self):
		"""USt 2 E 2026, lines 124 to 126: „Vorauszahlungssoll ist die Summe der angemeldeten bzw. festgesetzten
		Umsatzsteuer-Vorauszahlungen/Überschüsse aus dem Voranmeldungsverfahren einschließlich der
		Sondervorauszahlung für die Dauerfristverlängerung.“"""
		soll = vorauszahlungssoll(2026, monthly(), MONTHS, SONDERVORAUSZAHLUNG_2026)
		self.assertEqual(soll.voranmeldungen, Decimal("10900.00"))
		self.assertEqual(soll.amount, Decimal("12000.00"))
		self.assertEqual(
			(soll.source, soll.sondervorauszahlung, soll.credited),
			(SollSource.VORANMELDUNGEN, Decimal("1100.00"), Decimal("1100.00")),
		)
		self.assertEqual(soll.findings, ())
		self.assertTrue(soll.ready)

	def test_equals_the_sum_of_kz_83_and_kz_39_when_kz_39_credited_the_sondervorauszahlung(self):
		filed = monthly()
		soll = vorauszahlungssoll(2026, filed, MONTHS, SONDERVORAUSZAHLUNG_2026)
		self.assertEqual(soll.amount, sum((entry.kz83 + entry.kz39 for entry in filed), ZERO))

	def test_a_quarterly_filer_without_dauerfristverlaengerung_sums_kz_83(self):
		filed = [
			Filed(period, f"Q{period.index}", Decimal(amount))
			for period, amount in zip(QUARTERS, ("300.00", "-50.00", "120.55", "0.00"), strict=True)
		]
		soll = vorauszahlungssoll(2026, filed, QUARTERS)
		self.assertEqual(soll.amount, Decimal("370.55"))

	def test_lists_the_filed_voranmeldungen_in_the_order_of_the_year(self):
		filed = list(reversed(monthly()))
		soll = vorauszahlungssoll(2026, filed, MONTHS, SONDERVORAUSZAHLUNG_2026)
		self.assertEqual([entry.period for entry in soll.filed], list(MONTHS))

	def test_hints_when_kz_39_did_not_credit_the_sondervorauszahlung(self):
		"""§ 48 Absatz 4 UStDV: „Die festgesetzte Sondervorauszahlung ist bei der Festsetzung der Vorauszahlung für den
		letzten Voranmeldungszeitraum des Besteuerungszeitraums zu berücksichtigen“."""
		soll = vorauszahlungssoll(
			2026, monthly(december="1000.00", kz39="0.00"), MONTHS, SONDERVORAUSZAHLUNG_2026
		)
		self.assertEqual(soll.amount, Decimal("13100.00"))
		self.assertEqual(
			soll.findings,
			(
				Finding(
					"SONDERVORAUSZAHLUNG-KZ39", Severity.HINT, SONDERVORAUSZAHLUNG, ("0,00", "1.100,00", 2026)
				),
			),
		)
		self.assertEqual(
			soll.findings[0].text,
			"The Voranmeldungen credited 0,00 euros of Sondervorauszahlung in Kz 39, the settings name 1.100,00 euros "
			"for 2026. The last Voranmeldung of the year deducts it (§ 48 Absatz 4 UStDV); the Vorauszahlungssoll "
			"counts the Sondervorauszahlung of the settings.",
		)


class MissingPeriodTest(TestCase):
	def test_a_period_without_a_filed_voranmeldung_blocks(self):
		filed = monthly()[:-1]
		soll = vorauszahlungssoll(2026, filed, MONTHS, SONDERVORAUSZAHLUNG_2026)
		self.assertEqual(soll.missing, (MONTHS[-1],))
		self.assertFalse(soll.ready)
		(finding,) = (finding for finding in soll.findings if finding.code == "ZEITRAUM-FEHLT")
		self.assertEqual(
			finding, Finding("ZEITRAUM-FEHLT", Severity.ERROR, MISSING_PERIOD, ("Dezember 2026",))
		)
		self.assertTrue(finding.blocking)
		self.assertEqual(
			finding.text, "No filed Voranmeldung covers Dezember 2026: file it, or waive it with a reason."
		)

	def test_a_waived_period_does_not_block(self):
		filed = monthly()[:-1]
		waived = {MONTHS[-1]: " filed on paper "}
		soll = vorauszahlungssoll(2026, filed, MONTHS, ZERO, waived=waived)
		self.assertEqual((soll.missing, soll.waived), ((), ((MONTHS[-1], "filed on paper"),)))
		self.assertTrue(soll.ready)

	def test_a_waiver_needs_a_reason(self):
		with self.assertRaises(SollError) as caught:
			vorauszahlungssoll(2026, monthly()[:-1], MONTHS, waived={MONTHS[-1]: " "})
		self.assertEqual(
			(caught.exception.template, caught.exception.values), (WITHOUT_REASON, ("Dezember 2026",))
		)

	def test_a_month_the_settings_do_not_require_does_not_block(self):
		soll = vorauszahlungssoll(2026, monthly()[:6], MONTHS[:6])
		self.assertEqual(soll.missing, ())


class CorrectionTest(TestCase):
	"""USt 2 E 2026, lines 124 to 126: „In den Fällen, in denen bereits eine Festsetzung der Umsatzsteuer für den
	Besteuerungszeitraum erfolgt ist, tragen Sie bitte die bisher festgesetzte Umsatzsteuer als Vorauszahlungssoll
	ein.“"""

	def test_a_corrected_return_takes_the_kz_816_of_the_return_it_corrects(self):
		soll = vorauszahlungssoll(
			2026, monthly(), MONTHS, SONDERVORAUSZAHLUNG_2026, previous_kz816=Decimal("12500.00")
		)
		self.assertEqual(
			(soll.amount, soll.source, soll.computed),
			(Decimal("12500.00"), SollSource.PREVIOUS_RETURN, Decimal("12000.00")),
		)

	def test_an_override_takes_the_festsetzung_of_the_finanzamt_with_its_reason(self):
		override = Override(Decimal("12800.00"), " Bescheid vom 1. Oktober 2027 ")
		soll = vorauszahlungssoll(
			2026,
			monthly(),
			MONTHS,
			SONDERVORAUSZAHLUNG_2026,
			previous_kz816=Decimal("12500.00"),
			override=override,
		)
		self.assertEqual((soll.amount, soll.source), (Decimal("12800.00"), SollSource.OVERRIDE))
		self.assertEqual(soll.override, Override(Decimal("12800.00"), "Bescheid vom 1. Oktober 2027"))
		self.assertEqual(
			soll.findings,
			(
				Finding(
					"SOLL-UEBERSCHRIEBEN",
					Severity.HINT,
					OVERRIDDEN,
					("12.800,00", "12.000,00", "Bescheid vom 1. Oktober 2027"),
				),
			),
		)

	def test_an_override_needs_a_reason_and_cents(self):
		with self.assertRaises(SollError) as caught:
			Override(Decimal("1.00"), "")
		self.assertEqual(
			(caught.exception.template, caught.exception.values), (WITHOUT_REASON, ("Vorauszahlungssoll",))
		)
		with self.assertRaisesRegex(ValueError, "finite cents"):
			Override(Decimal("1.001"), "Bescheid")


class PaymentsTest(TestCase):
	def test_hints_when_the_payments_differ_from_the_soll(self):
		soll = vorauszahlungssoll(2026, monthly(), MONTHS, SONDERVORAUSZAHLUNG_2026, paid=Decimal("11000.00"))
		self.assertEqual(
			soll.findings, (Finding("ZAHLUNGEN", Severity.HINT, PAYMENTS, ("11.000,00", 2026, "12.000,00")),)
		)

	def test_no_hint_when_the_payments_match_or_are_unknown(self):
		self.assertEqual(
			vorauszahlungssoll(
				2026, monthly(), MONTHS, SONDERVORAUSZAHLUNG_2026, paid=Decimal("12000.00")
			).findings,
			(),
		)
		self.assertEqual(vorauszahlungssoll(2026, monthly(), MONTHS, SONDERVORAUSZAHLUNG_2026).findings, ())


class InputTest(TestCase):
	def test_refuses_a_voranmeldung_of_another_year(self):
		with self.assertRaises(SollError) as caught:
			vorauszahlungssoll(2026, [Filed(Period.month(2025, 12), "UStVA-2025-12", Decimal("1.00"))], ())
		self.assertEqual(
			(caught.exception.template, caught.exception.values), (OTHER_YEAR, ("Dezember 2025", 2026))
		)
		with self.assertRaises(SollError) as caught:
			vorauszahlungssoll(2026, (), (Period.month(2027, 1),))
		self.assertEqual(
			(caught.exception.template, caught.exception.values), (OTHER_YEAR, ("Januar 2027", 2026))
		)

	def test_refuses_two_voranmeldungen_of_one_period(self):
		filed = [Filed(MONTHS[0], "A", Decimal("1.00")), Filed(MONTHS[0], "B", Decimal("2.00"))]
		with self.assertRaises(SollError) as caught:
			vorauszahlungssoll(2026, filed, MONTHS[:1])
		self.assertEqual(
			(caught.exception.template, caught.exception.values), (PERIOD_TWICE, ("Januar 2026",))
		)

	def test_amounts_are_cents(self):
		with self.assertRaisesRegex(ValueError, "finite cents"):
			Filed(MONTHS[0], "A", Decimal("1.001"))
		with self.assertRaisesRegex(ValueError, "finite cents"):
			Filed(MONTHS[0], "A", Decimal("1.00"), Decimal("0.001"))
		with self.assertRaisesRegex(ValueError, "finite cents"):
			vorauszahlungssoll(2026, (), (), Decimal("0.001"))
		with self.assertRaises(TypeError):
			vorauszahlungssoll(2026, (), (), 1100.0)  # type: ignore[arg-type]

	def test_a_filed_return_may_carry_its_kennzahlen_for_the_reconciliation(self):
		lines = {"81": FiledKennzahl(Decimal("1000.40"), Decimal("1000"), Decimal("1000"))}
		filed = Filed(MONTHS[0], "A", Decimal("190.00"), lines=lines)
		self.assertEqual(filed.lines["81"].final, Decimal("1000"))
		self.assertEqual(Filed(MONTHS[0], "A", Decimal("1.00")).lines, {})
		with self.assertRaisesRegex(ValueError, "finite cents"):
			FiledKennzahl(Decimal("1.001"), Decimal("1"), Decimal("1"))


class AbschlusszahlungTest(TestCase):
	def test_kz_820_is_kz_816_less_the_soll(self):
		"""Rule 30638: [E3011401] != [E3011101] - [E3011301]."""
		self.assertEqual(abschlusszahlung(Decimal("12345.67"), Decimal("12000.00")), Decimal("345.67"))
		self.assertEqual(abschlusszahlung(Decimal("100.00"), Decimal("250.00")), Decimal("-150.00"))

	def test_is_due_one_month_after_the_return_arrived(self):
		"""§ 18 Absatz 4 Satz 1 UStG: „einen Monat nach dem Eingang der Steueranmeldung fällig“."""
		self.assertEqual(payment_due(date(2027, 3, 15)), date(2027, 4, 15))
		self.assertEqual(payment_due(date(2027, 12, 1)), date(2028, 1, 3))

	def test_a_month_without_the_day_ends_on_its_last_day(self):
		"""§ 188 Absatz 3 BGB through § 108 Absatz 1 AO; 28 February 2027 is a Sunday."""
		self.assertEqual(payment_due(date(2028, 1, 31)), date(2028, 2, 29))
		self.assertEqual(payment_due(date(2027, 1, 31)), date(2027, 3, 1))

	def test_a_due_day_on_a_holiday_moves_to_the_next_working_day(self):
		self.assertEqual(payment_due(date(2027, 9, 3), frozenset({date(2027, 10, 4)})), date(2027, 10, 5))


class MessagesTest(TestCase):
	def test_lists_every_template_once_for_the_translations(self):
		self.assertEqual(
			MESSAGES,
			(
				OTHER_YEAR,
				PERIOD_TWICE,
				WITHOUT_REASON,
				MISSING_PERIOD,
				SONDERVORAUSZAHLUNG,
				OVERRIDDEN,
				PAYMENTS,
			),
		)

	def test_an_error_keeps_template_and_values_apart(self):
		error = SollError(PERIOD_TWICE, "Januar 2026")
		self.assertEqual(
			(error.template, error.values, str(error)),
			(PERIOD_TWICE, ("Januar 2026",), PERIOD_TWICE.format("Januar 2026")),
		)
		self.assertIsInstance(error, ValueError)

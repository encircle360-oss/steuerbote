"""The Kontensalden of the E-Bilanz of the invented GmbH: a tuple per account with a balance, in the direction of its
position and in the characters of ELSTER, the checks of taxonomy 6.9 and the hints of 6.10, and the reason that
leaves them out in 6.9."""

from dataclasses import replace
from decimal import Decimal
from types import MappingProxyType
from unittest import TestCase

from steuerbote.ebilanz.calculation import AccountBalance, Adjustment, calculate
from steuerbote.ebilanz.kontennachweis import (
	ACCOUNT_BALANCES,
	ACCOUNT_DESCRIPTION,
	ACCOUNT_NUMBER,
	BALANCE,
	NOT_YET_POSSIBLE,
	POSITION_NAME,
	kontennachweis,
)
from steuerbote.ebilanz.positions import euro, structure
from steuerbote.ebilanz.tests.taxonomy import gaap, view
from steuerbote.ebilanz.tests.test_calculation import BOOKS, WITH_PRIOR, case
from steuerbote.xbrl.checks import Severity
from steuerbote.xbrl.facts import Period
from steuerbote.xbrl.taxonomy import Network

D = Decimal


def of(*balances, adjustments=(), reason="", taxonomy=None, **fields):
	calculation = calculate(structure(taxonomy or view(), case(**fields)), balances, adjustments)
	return kontennachweis(calculation, reason=reason)


def codes(found) -> list[str]:
	return [finding.code for finding in found.findings]


class TuplesTest(TestCase):
	@classmethod
	def setUpClass(cls):
		cls.found = of(*BOOKS)

	def test_has_a_tuple_per_account_with_a_balance_and_nothing_to_report(self):
		self.assertEqual([line.account for line in self.found.lines], [balance.account for balance in BOOKS])
		self.assertEqual(self.found.findings, ())
		self.assertEqual(self.found.reason, "")

	def test_names_the_position_with_its_prefix_and_the_balance_in_its_direction(self):
		"""Leitfaden B.12; ERiC E-Bilanz-Dokumentation, Kap. 3.12."""
		facts = self.found.facts()
		self.assertEqual(len(facts), len(BOOKS))
		sales_deduction = facts[8]
		self.assertEqual(sales_deduction.concept, ACCOUNT_BALANCES)
		self.assertEqual(
			[(item.concept, item.period, item.value) for item in sales_deduction.children],
			[
				(POSITION_NAME, Period.WIRTSCHAFTSJAHR, gaap("is.netIncome.netSales")),
				(ACCOUNT_NUMBER, Period.WIRTSCHAFTSJAHR, "4700"),
				(ACCOUNT_DESCRIPTION, Period.WIRTSCHAFTSJAHR, "Erlösschmälerungen"),
				(BALANCE, Period.WIRTSCHAFTSJAHR, D("-1000.00")),
			],
		)

	def test_leaves_out_the_previous_year(self):
		prior = AccountBalance("1800", "Bank", "bs.ass.currAss.cashEquiv.bank", D("68500.00"), prior=True)
		found = of(*BOOKS, prior, accounting_standard="HGBM", periods=WITH_PRIOR)
		self.assertEqual(len(found.lines), len(BOOKS))


class TextsTest(TestCase):
	def test_takes_the_texts_of_the_books_in_the_characters_of_elster(self):
		found = of(
			*BOOKS[:-1],
			AccountBalance(
				"7600", "Körperschaftsteuer \N{EN DASH} laufendes Jahr", "is.netIncome.tax", D("9000.00")
			),
		)
		self.assertEqual(found.lines[-1].description, "Körperschaftsteuer - laufendes Jahr")

	def test_refuses_a_character_elster_does_not_take_and_a_missing_description(self):
		"""ERiC E-Bilanz-Dokumentation, Kap. 3.16; Leitfaden B.12, structural error 170195097."""
		found = of(
			*BOOKS[:-1],
			AccountBalance("7600", "Podatek łączny", "is.netIncome.tax", D("8000.00")),
			AccountBalance("7601", " ", "is.netIncome.tax", D("1000.00")),
		)
		self.assertEqual(codes(found), ["EB-KONTENSALDEN", "170195097", "EB-KONTENSALDEN-FEHLEN"])
		self.assertEqual(
			[finding.reference for finding in found.findings], ["7600", "7601", "is.netIncome.tax"]
		)
		self.assertIn("'ł' (U+0142)", found.findings[0].text)
		self.assertEqual(len(found.lines), len(BOOKS) - 1)


class ChecksTest(TestCase):
	def test_the_bilanz_and_the_guv_each_have_a_kontensaldo(self):
		"""Leitfaden B.12, structural error 170195104 of the Jahresdokumentation 6.9."""
		found = of(*BOOKS[:7], adjustments=(Adjustment("is.netIncome.netSales", D("40000.00"), "von Hand"),))
		self.assertEqual(codes(found), ["170195104", "EB-KONTENSALDEN-FEHLEN"])
		self.assertEqual(found.findings[0].reference, "GuV")
		self.assertTrue(found.findings[0].blocking)
		empty = of()
		self.assertEqual(codes(empty), ["170195104", "170195104"])

	def test_hints_at_the_rules_of_taxonomy_6_10(self):
		"""Leitfaden 6.10, B.12.1: a valued position without a valued one under it has a Kontensaldo, and the
		Kontensalden of a position add up to it."""
		found = of(
			*BOOKS,
			AccountBalance("1000", "Kasse", "bs.ass.currAss.cashEquiv.bank", D("0.00")),
			adjustments=(
				Adjustment("bs.ass.fixAss.intan.concessionBrands", D("11000.00"), "Abschreibung nachgeholt"),
				Adjustment("bs.ass.currAss.cashEquiv.cash", D("1000.00"), "Kasse laut Zählprotokoll"),
			),
		)
		self.assertEqual(
			[(finding.code, finding.reference, finding.severity) for finding in found.findings],
			[
				("EB-KONTENSALDEN-SUMME", "bs.ass.fixAss.intan.concessionBrands", Severity.HINT),
				("EB-KONTENSALDEN-FEHLEN", "bs.ass.currAss.cashEquiv.cash", Severity.HINT),
			],
		)
		self.assertIn(euro(D("12000.00")), found.findings[0].text)


class WithoutKontensaldenTest(TestCase):
	def test_taxonomy_6_9_takes_a_reason_instead(self):
		"""BMF letter of 10 June 2025; rule 170405002."""
		found = of(*BOOKS, kontennachweis=False, reason=" Umstellung der Software noch nicht abgeschlossen ")
		self.assertEqual((found.lines, found.facts(), found.findings), ((), (), ()))
		self.assertEqual(found.reason, "Umstellung der Software noch nicht abgeschlossen")

	def test_without_a_reason_it_blocks(self):
		(finding,) = of(*BOOKS, kontennachweis=False).findings
		self.assertEqual((finding.code, finding.reference), ("170405002", NOT_YET_POSSIBLE))

	def test_a_taxonomy_without_the_reason_takes_no_e_bilanz_without_kontensalden(self):
		concepts = {name: concept for name, concept in view().concepts.items() if name != NOT_YET_POSSIBLE}
		presentation = {
			role: Network(
				role, tuple(arc for arc in network.arcs if NOT_YET_POSSIBLE not in (arc.parent, arc.child))
			)
			for role, network in view().presentation.items()
		}
		later = replace(
			view(), concepts=MappingProxyType(concepts), presentation=MappingProxyType(presentation)
		)
		(finding,) = of(*BOOKS, kontennachweis=False, reason="Grund", taxonomy=later).findings
		self.assertEqual(finding.code, "EB-KONTENSALDEN")

"""The steuerliches Einlagekonto of § 27 KStG: the roll-forward of KSt 1 F."""

from decimal import Decimal
from unittest import TestCase

from steuerbote.kst.chain import Severity
from steuerbote.kst.einlagekonto import Code, roll_forward
from steuerbote.kst.tests.support import FIGURES

ZERO = Decimal("0")


def euros(value: str) -> Decimal:
	return Decimal(value)


class RollForwardTest(TestCase):
	def test_a_company_without_einlagen_files_zero_to_zero(self):
		found = roll_forward(ZERO, FIGURES)
		self.assertEqual((found.opening, found.reduction, found.closing), (ZERO, ZERO, ZERO))
		self.assertEqual(found.findings, ())

	def test_adds_the_einlagen_of_the_year(self):
		found = roll_forward(
			euros("10000"),
			FIGURES,
			contributions_booked=euros("2000"),
			contributions_not_booked=euros("500"),
			other_contributions=euros("25000"),
		)
		self.assertEqual(found.closing, euros("37500"))

	def test_carries_the_sonderausweis_unchanged(self):
		found = roll_forward(ZERO, FIGURES, sonderausweis=euros("3000"))
		self.assertEqual((found.sonderausweis, found.closing_sonderausweis), (euros("3000"), euros("3000")))


class DistributionTest(TestCase):
	"""§ 27 Absatz 1 Satz 3 to 5 and Absatz 5 KStG; rules 8920021, 8920012, 8924401 and 8920076."""

	def distribute(self, distributions: str, certified: str = "0", opening: str = "30000", **kwargs: object):
		return roll_forward(
			euros(opening),
			FIGURES,
			distributions=euros(distributions),
			certified_reduction=euros(certified),
			previous_equity=kwargs.get("equity", euros("100000")),  # type: ignore[arg-type]
			previous_nominal_capital=euros("25000"),
		)

	def test_the_distributable_profit_is_the_equity_less_nominal_capital_and_einlagekonto(self):
		self.assertEqual(self.distribute("1").distributable, euros("45000"))
		self.assertEqual(self.distribute("1", equity=euros("50000")).distributable, ZERO)

	def test_a_distribution_within_the_distributable_profit_leaves_the_einlagekonto(self):
		found = self.distribute("40000", "10000")
		self.assertEqual(
			(found.excess, found.reduction, found.closing), (euros("-5000"), ZERO, euros("30000"))
		)
		self.assertIsNone(found.subtotal)

	def test_a_distribution_beyond_it_reduces_the_einlagekonto_as_far_as_certified(self):
		found = self.distribute("60000", "15000")
		self.assertEqual(
			(found.subtotal, found.excess, found.reduction), (euros("30000"), euros("15000"), euros("15000"))
		)
		self.assertEqual(found.closing, euros("15000"))
		self.assertEqual(self.distribute("60000", "5000").reduction, euros("5000"))

	def test_an_einlagenrueckgewaehr_without_certificate_counts_as_zero(self):
		self.assertEqual(self.distribute("60000").reduction, ZERO)

	def test_distributions_cannot_make_the_einlagekonto_negative(self):
		found = self.distribute("80000", "40000", opening="10000")
		self.assertEqual((found.reduction, found.closing), (euros("10000"), ZERO))

	def test_without_a_positive_einlagekonto_nothing_is_reduced_and_line_46_is_left_out(self):
		found = roll_forward(
			euros("0"), FIGURES, distributions=euros("60000"), certified_reduction=euros("1000")
		)
		self.assertEqual((found.subtotal, found.reduction, found.closing), (None, ZERO, ZERO))
		self.assertEqual(found.findings, ())

	def test_distributions_with_an_einlagekonto_need_the_equity_of_the_previous_year(self):
		found = roll_forward(euros("30000"), FIGURES, distributions=euros("10000"))
		(finding,) = found.findings
		self.assertEqual((finding.code, finding.severity), (Code.EQUITY_MISSING, Severity.ERROR))
		self.assertIn("8920011", finding.reference)
		self.assertIsNone(found.distributable)
		self.assertEqual(found.reduction, ZERO)

	def test_several_distributions_with_certificates_are_left_to_the_steuerberatung(self):
		found = roll_forward(
			euros("30000"),
			FIGURES,
			distributions=euros("60000"),
			certified_reduction=euros("15000"),
			several_certified=True,
			previous_equity=euros("100000"),
			previous_nominal_capital=euros("25000"),
		)
		(finding,) = found.findings
		self.assertEqual((finding.code, finding.severity), (Code.SEVERAL_CERTIFIED, Severity.ERROR))


class InputTest(TestCase):
	def test_takes_whole_euros(self):
		with self.assertRaisesRegex(
			ValueError, "the Bestand at the end of the previous Wirtschaftsjahr must be whole euros"
		):
			roll_forward(Decimal("0.50"), FIGURES)
		with self.assertRaisesRegex(ValueError, "the Leistungen must be whole euros of at least 0"):
			roll_forward(ZERO, FIGURES, distributions=Decimal("-1"))
		with self.assertRaisesRegex(ValueError, "the Eigenkapital laut Steuerbilanz must be whole euros"):
			roll_forward(ZERO, FIGURES, previous_equity=Decimal("1.5"))

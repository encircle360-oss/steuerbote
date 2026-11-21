"""Every account the charts hand to the Umsatzsteuer has exactly one place in the defaults.

The places are: mapped by a rule, a tax account of a check, watched, or deliberately ignored. The
accounts come from the DATEV charts valid for 2026, from ERPNext's own SKR03 and SKR04 templates and
from SKR03 numbers of charts in circulation that the DATEV edition for 2026 no longer uses. A new
edition of a chart that adds or marks an account fails here until the account has its place.
"""

from dataclasses import dataclass
from unittest import TestCase

from steuerbote.ustva.defaults import (
	SKR03,
	SKR03_IGNORED,
	SKR03_RANGES,
	SKR04,
	SKR04_IGNORED,
	SKR04_RANGES,
	with_ranges,
)
from steuerbote.ustva.mapping import Mapping
from steuerbote.ustva.tests.fixtures import datev_2026, erpnext_v16, skr03_legacy_numbers

FERNVERKAEUFE = "Kz 45: innergemeinschaftliche Fernverkäufe per Anleitung zu Zeile 36"
ELECTRONIC_SERVICES = "Kz 45: auf elektronischem Weg erbrachte sonstige Leistungen per Anleitung zu Zeile 36"
PREPAYMENT = "ignored like its SKR03 twin: prepayment without automatic tax, no VAT keyword in the name"
TRAVEL_AND_MARGIN = "watched like 8193 and 4138: Umsatzerlöse nach § 25 or § 25a UStG ohne USt"
OTHER_OPERATING_INCOME = "watched for a hint: other operating income with the Zusatzfunktion M, without „U“"
THIRD_COUNTRY = "ignored like 3558 and 5558: Wareneingang im Drittland steuerbar, without „U“ in the chart"


def _range(first: str, last: str, reason: str) -> dict[str, str]:
	return dict.fromkeys(with_ranges((first,), {first: last}), reason)


# Accounts with a place in the defaults that no fixture contains (neither marked by the DATEV chart,
# nor in ERPNext's template, nor a number in circulation), each with the reason.
NOT_IN_THE_FIXTURES = {
	"SKR03": {
		"8190": "watched: revenue under the averages of § 24 UStG, its Kennzahl depends on the case",
		**_range("8320", "8329", FERNVERKAEUFE),
		"8331": ELECTRONIC_SERVICES,
		"8727": FERNVERKAEUFE,
		**dict.fromkeys(("8189", "8197"), TRAVEL_AND_MARGIN),
		**dict.fromkeys(("8603", "8605", "8606"), OTHER_OPERATING_INCOME),
		"3551": THIRD_COUNTRY,
		"1390": "ignored like its twin SKR04 1490: F account of the Ist-Versteuerung, in 13xx outside 15xx and 17xx",
	},
	"SKR04": {
		"3798": "ignored like its twin SKR03 1728: OSS; an S account in 37xx, outside 14xx and 38xx",
		"4331": ELECTRONIC_SERVICES,
		**dict.fromkeys(("1190", "3250", "3280", "3284", "3285", "3695"), PREPAYMENT),
		**dict.fromkeys(("5744", "4499", "4869"), "Zwilling eines beobachteten SKR03-Kontos"),
		**dict.fromkeys(("4131", "4132"), TRAVEL_AND_MARGIN),
		**dict.fromkeys(("4830", "4832", "4835"), OTHER_OPERATING_INCOME),
		"5551": THIRD_COUNTRY,
	},
}

# Numbers both charts give a place, with what each chart means by them.
SHARED_NUMBERS = {
	"3798": "SKR03: Skonti on purchases at 5,5 % (earlier editions); SKR04: OSS tax account",
	"4300": "SKR03: non-deductible Vorsteuer (earlier editions); SKR04: Erlöse 7 % USt",
	"4301": "SKR03: non-deductible Vorsteuer 7 % (earlier editions); SKR04: member of 4300 to 4309",
	"4306": "SKR03: non-deductible Vorsteuer 19 % (earlier editions); SKR04: member of 4300 to 4309",
}


@dataclass(frozen=True)
class Chart:
	mapping: Mapping
	ignored: tuple[str, ...]
	ranges: dict[str, str]
	datev: tuple[str, ...]
	datev_ranges: dict[str, str]
	erpnext: tuple[str, ...]
	legacy: tuple[str, ...]

	@property
	def places(self) -> dict[str, set[str]]:
		return {
			"rule": {rule.account_number for rule in self.mapping.rules},
			"checked": {account for check in self.mapping.checks for account in check.tax_accounts},
			"watched": {watched.account_number for watched in self.mapping.watched},
			"ignored": set(with_ranges(self.ignored, self.ranges)),
		}

	@property
	def placed(self) -> set[str]:
		return set().union(*self.places.values())

	@property
	def covered(self) -> set[str]:
		"""The fixture accounts, with the members of the DATEV ranges that start at one of them."""
		sources = set(self.datev) | set(self.erpnext) | set(self.legacy)
		return set(with_ranges(sources, self.datev_ranges))


CHARTS = (
	Chart(
		SKR03,
		SKR03_IGNORED,
		SKR03_RANGES,
		datev_2026.SKR03_VAT_ACCOUNTS,
		datev_2026.SKR03_RANGES,
		erpnext_v16.SKR03_VAT_ACCOUNTS,
		skr03_legacy_numbers.SKR03_VAT_ACCOUNTS,
	),
	Chart(
		SKR04,
		SKR04_IGNORED,
		SKR04_RANGES,
		datev_2026.SKR04_VAT_ACCOUNTS,
		datev_2026.SKR04_RANGES,
		erpnext_v16.SKR04_VAT_ACCOUNTS,
		(),
	),
)


class FixtureTest(TestCase):
	def test_fixtures_list_each_account_once_in_order(self):
		for accounts in (
			datev_2026.SKR03_VAT_ACCOUNTS,
			datev_2026.SKR04_VAT_ACCOUNTS,
			erpnext_v16.SKR03_VAT_ACCOUNTS,
			erpnext_v16.SKR04_VAT_ACCOUNTS,
			skr03_legacy_numbers.SKR03_VAT_ACCOUNTS,
			skr03_legacy_numbers.MAPPED,
			skr03_legacy_numbers.WATCHED,
			skr03_legacy_numbers.IGNORED,
		):
			self.assertEqual(list(accounts), sorted(set(accounts)))

	def test_fixtures_hold_four_digit_account_numbers(self):
		for chart in CHARTS:
			for account in chart.datev + chart.erpnext + chart.legacy + tuple(chart.datev_ranges.values()):
				self.assertRegex(account, r"^\d{4}$")
			for first, last in chart.datev_ranges.items():
				self.assertRegex(first, r"^\d{4}$")
				self.assertLess(first, last)

	def test_datev_fixture_holds_every_member_of_its_ranges(self):
		for chart in CHARTS:
			for first in chart.datev_ranges:
				if first in chart.datev:
					with self.subTest(chart=chart.mapping.chart, range=first):
						members = with_ranges((first,), chart.datev_ranges)
						self.assertLessEqual(set(members), set(chart.datev))


class CompletenessTest(TestCase):
	def assert_one_place_each(self, chart: Chart, accounts: tuple[str, ...]) -> None:
		found = chart.places
		for account in accounts:
			where = [place for place, accounts in found.items() if account in accounts]
			with self.subTest(chart=chart.mapping.chart, account=account):
				self.assertEqual(len(where), 1, where)

	def test_every_vat_account_of_the_datev_chart_has_exactly_one_place(self):
		for chart in CHARTS:
			self.assert_one_place_each(chart, chart.datev)

	def test_every_vat_account_of_the_erpnext_template_has_exactly_one_place(self):
		for chart in CHARTS:
			self.assert_one_place_each(chart, chart.erpnext)

	def test_every_number_in_circulation_has_exactly_one_place(self):
		for chart in CHARTS:
			self.assert_one_place_each(chart, chart.legacy)

	def test_numbers_in_circulation_have_the_place_their_label_gives(self):
		skr03 = CHARTS[0]
		places = skr03.places
		self.assertLessEqual(set(skr03_legacy_numbers.MAPPED), places["rule"])
		self.assertLessEqual(set(skr03_legacy_numbers.WATCHED), places["watched"])
		self.assertLessEqual(set(skr03_legacy_numbers.IGNORED), places["ignored"])

	def test_accounts_outside_the_fixtures_are_the_listed_exceptions(self):
		for chart in CHARTS:
			with self.subTest(chart=chart.mapping.chart):
				outside = chart.placed - chart.covered
				self.assertEqual(outside, set(NOT_IN_THE_FIXTURES[chart.mapping.chart]))

	def test_ranges_are_those_of_the_datev_chart(self):
		for chart in CHARTS:
			with self.subTest(chart=chart.mapping.chart):
				placed = chart.placed
				expected = {first: last for first, last in chart.datev_ranges.items() if first in placed}
				self.assertEqual(chart.ranges, expected)

	def test_no_account_has_two_places(self):
		for chart in CHARTS:
			seen: dict[str, str] = {}
			for place, accounts in chart.places.items():
				for account in accounts:
					with self.subTest(chart=chart.mapping.chart, account=account):
						self.assertNotIn(account, seen, f"{account} is {seen.get(account)} and {place}")
					seen[account] = place

	def test_the_charts_share_only_the_listed_numbers(self):
		skr03, skr04 = (chart.placed for chart in CHARTS)
		self.assertEqual(skr03 & skr04, set(SHARED_NUMBERS))

	def test_tax_accounts_of_checks_are_not_mapped(self):
		for chart in CHARTS:
			for check in chart.mapping.checks:
				for account in check.tax_accounts:
					with self.subTest(chart=chart.mapping.chart, account=account):
						self.assertIsNone(chart.mapping.rule_for(account))

	def test_every_rated_rule_feeds_a_tax_kennzahl(self):
		for chart in CHARTS:
			for rule in chart.mapping.rules:
				if rule.tax_rate is not None:
					with self.subTest(chart=chart.mapping.chart, account=rule.account_number):
						self.assertIsNotNone(chart.mapping.catalogue[rule.kennzahl].tax_kennzahl)

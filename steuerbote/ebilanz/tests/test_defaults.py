"""The defaults of the Bilanzzuordnung for SKR03 and SKR04 per version of the HGB-Taxonomie, with the version of the
defaults (steuerbote/ebilanz/defaults.py): every account of the DATEV charts 2026 and of ERPNext's templates in its
place (steuerbote/ebilanz/tests/datev_charts.py), the source of each choice, and the positions against the package
of esteuer.de with an invented GmbH of each chart."""

import hashlib
import re
from collections import Counter
from dataclasses import replace
from datetime import date
from decimal import Decimal
from unittest import TestCase

from steuerbote.balance_mapping_sync import ebilanz_balances
from steuerbote.ebilanz import defaults
from steuerbote.ebilanz.calculation import calculate
from steuerbote.ebilanz.defaults import (
	CHARTS,
	DEFAULTS,
	GROUPS,
	REASONS,
	REVISIONS,
	Outside,
	Reason,
	defaults_for,
	defaults_version,
)
from steuerbote.ebilanz.positions import AccountingStandard, Case, Mark, structure
from steuerbote.ebilanz.tests.datev_charts import (
	BOTH_SIDES,
	COMMERCIAL,
	EUR,
	LABELLED,
	REMAINING_TERMS,
	TAX,
	TEMPLATE_GROUPS,
	TEMPLATES,
)
from steuerbote.hgb.statement import RemainingTerm
from steuerbote.mappings.transfer import canonical_json
from steuerbote.ustva.mapping import WatchLevel
from steuerbote.xbrl import changes, mapping
from steuerbote.xbrl.facts import Periods
from steuerbote.xbrl.mapping import (
	SHAREHOLDER_SCOPES,
	AccountBalance,
	Accounts,
	Books,
	Code,
	DefaultExcluded,
	DefaultRule,
	Defaults,
	DefaultWatched,
	Part,
	Purpose,
	place,
)
from steuerbote.xbrl.taxonomy import BALANCE_SHEET, INCOME_STATEMENT, LABEL, Balance
from steuerbote.xbrl.tests import real
from steuerbote.xbrl.versions import TAXONOMIES

DIGESTS = {
	"SKR03 Taxonomie 6.9 2026.0": "15628a4764c7c1ca0ae085ab0c50a1b8dce1c7275884704fb5015eb354a6ca95",
	"SKR04 Taxonomie 6.9 2026.0": "15628a4764c7c1ca0ae085ab0c50a1b8dce1c7275884704fb5015eb354a6ca95",
	"SKR03 Taxonomie 6.9 2026.1": "a7f62344e56a114f0eb216934ff9ee3c3a8a3a528f976c9479965e856a1a291b",
	"SKR04 Taxonomie 6.9 2026.1": "fe84fc7cd49dc4501a08ee102b5521b4a8c6712228ae80ba28a8c7d8da6525a4",
	"SKR03 Taxonomie 6.10 2026.1": "ba4f6076a3a50cd64445917fd4646cf269ef81afc57bc9044ceabd2b439182ad",
	"SKR04 Taxonomie 6.10 2026.1": "3deefe2a1ecffd0a3c5de1aefd8ddb652b19020fc0d580c7f946691dd4727154",
	"SKR03 Taxonomie 6.9 2026.2": "b48b4b4636dfd700ddc884e122981e695a946b74e4c00365ee4dd83dc181edc0",
	"SKR04 Taxonomie 6.9 2026.2": "1790d77536396dc29decb8ea65ed28538eb0a33a9e0aa8b4b9acbffde30ecdfe",
	"SKR03 Taxonomie 6.10 2026.2": "4f33471af195ba79cd19b73a36a92bb481088d450e026aee91c69f30d28a2978",
	"SKR04 Taxonomie 6.10 2026.2": "5c9ed0ef78bf12965109ff3603f0705231ecf0a12e84b4a5e8827c233c709032",
	"SKR03 Taxonomie 6.9 2026.3": "70a08abef3fba407aa1b61472bd8457159256f9fbe169bb7e8725b50c340ffd1",
	"SKR04 Taxonomie 6.9 2026.3": "1c2518fc04e9f59b49f99ea1108bbba5c2fb5c5bdebae2690411c36d559033d7",
	"SKR03 Taxonomie 6.10 2026.3": "b2577e60834ba4389024764bdd5fe6f7b9f442e3694bd5d428c13ae2ba414e41",
	"SKR04 Taxonomie 6.10 2026.3": "20e192acff328399ce94b09624802753eced4bbab08aa2635d9121ee77e6b9c5",
}
"""The SHA-256 of the canonical JSON of the rows of each version of the defaults."""

D = Decimal
YEAR = Periods(date(2026, 1, 1), date(2026, 12, 31))
FISCAL_YEAR = (date(2026, 1, 1), date(2026, 12, 31))
PARTS = {
	"Asset": Part.BALANCE_SHEET,
	"Liability": Part.BALANCE_SHEET,
	"Equity": Part.BALANCE_SHEET,
	"Income": Part.INCOME_STATEMENT,
	"Expense": Part.INCOME_STATEMENT,
}
# „größer 1 Jahr“ counts as more than one year, which is all the Vermerk of § 268 Abs. 4 Satz 1 HGB asks of a
# Forderung.
TERMS = {
	"bis 1 Jahr": RemainingTerm.UP_TO_ONE_YEAR,
	"1 bis 5 Jahre": RemainingTerm.ONE_TO_FIVE_YEARS,
	"größer 5 Jahre": RemainingTerm.OVER_FIVE_YEARS,
	"größer 1 Jahr": RemainingTerm.ONE_TO_FIVE_YEARS,
}
TEMPLATE_TERM = re.compile(r"\((b\. 1 J\.|1-5 J\.|größer 5 J\.|größer 1 J\.)\)")
TEMPLATE_TERMS = {
	"b. 1 J.": RemainingTerm.UP_TO_ONE_YEAR,
	"1-5 J.": RemainingTerm.ONE_TO_FIVE_YEARS,
	"größer 5 J.": RemainingTerm.OVER_FIVE_YEARS,
	"größer 1 J.": RemainingTerm.ONE_TO_FIVE_YEARS,
}
"""The remaining terms in the short labels of ERPNext's templates, such as „(b. 1 J.)“."""
SOURCES = ("Leitfaden", "definitionGuidance", "§", "Fußnote", "DATEV", "ERPNext", "taxonomy")
REQUIRED = frozenset({Mark.MUSSFELD, Mark.SUMMENMUSSFELD, Mark.RECHNERISCH_NOTWENDIG})


def entries(defaults_of: Defaults) -> tuple:
	return (*defaults_of.rules, *defaults_of.watched, *defaults_of.excluded)


def numbers(text: str) -> list[str]:
	"""The accounts of a range, such as 1410-1444, or the one account."""
	accounts = Accounts.of(text)
	return [
		str(number).zfill(len(accounts.first))
		for number in range(int(accounts.first), int(accounts.last) + 1)
	]


def template_numbers(chart: str) -> set[str]:
	return {number for accounts in TEMPLATES[chart].values() for number in accounts}


def accounts_of(chart: str):
	"""Each group with each account or range it holds in the chart."""
	for group in GROUPS["6.9"]:
		for account in group.accounts:
			number = account.number(chart)
			if number is not None:
				yield group, number


def labels_of(chart: str) -> dict[str, str]:
	return {
		account.number(chart): account.label
		for group in GROUPS["6.9"]
		for account in group.accounts
		if account.number(chart) is not None
	}


def on_side(taxonomy, concept: str, amount: Decimal) -> Decimal:
	"""The amount as a balance on the side of the position: debit minus credit."""
	return amount if taxonomy.concept(f"de-gaap-ci:{concept}").balance is Balance.DEBIT else -amount


class TablesTest(TestCase):
	def test_every_table_holds_exactly_the_versions_of_the_taxonomy(self):
		"""Every table keyed by the version holds exactly the versions of TAXONOMIES (steuerbote/xbrl/versions.py)."""
		self.assertEqual(set(DEFAULTS), set(TAXONOMIES))
		self.assertEqual(set(REVISIONS), set(TAXONOMIES))
		self.assertEqual(set(GROUPS), set(TAXONOMIES))

	def test_each_version_has_the_defaults_of_skr03_and_skr04(self):
		self.assertEqual(CHARTS, frozenset({"SKR03", "SKR04"}))
		for version, charts in DEFAULTS.items():
			with self.subTest(version=version):
				self.assertEqual(set(charts), CHARTS)
				for chart, entry in charts.items():
					self.assertIsInstance(entry, Defaults)
					self.assertEqual((entry.chart, entry.taxonomy_version), (chart, version))

	def test_a_revision_of_0_holds_no_rows(self):
		"""Revision 0 is the empty table of the Bilanzzuordnung before the defaults of the DATEV charts: a mapping that
		took it over takes the first defaults with Vorgaben aktualisieren as changes of the defaults."""
		for version, revision in REVISIONS.items():
			for chart, entry in DEFAULTS[version].items():
				with self.subTest(version=version, chart=chart):
					self.assertGreaterEqual(revision, 0)
					if revision == 0:
						self.assertEqual((entry.rules, entry.watched, entry.excluded), ((), (), ()))

	def test_the_defaults_are_the_entries_of_the_groups_in_their_order(self):
		for version, charts in DEFAULTS.items():
			for chart, entry in charts.items():
				with self.subTest(version=version, chart=chart):
					made = [found for group in GROUPS[version] for found in group.entries(chart)]
					self.assertEqual(
						entries(entry),
						(
							*(found for found in made if isinstance(found, DefaultRule)),
							*(found for found in made if isinstance(found, DefaultWatched)),
							*(found for found in made if isinstance(found, DefaultExcluded)),
						),
					)

	def test_the_tables_are_read_only(self):
		with self.assertRaises(TypeError):
			DEFAULTS["6.10"] = DEFAULTS["6.9"]  # type: ignore[index]
		with self.assertRaises(TypeError):
			REVISIONS["6.9"] = 1  # type: ignore[index]
		with self.assertRaises(TypeError):
			GROUPS["6.10"] = GROUPS["6.9"]  # type: ignore[index]
		with self.assertRaises(TypeError):
			REASONS[Reason.MIXED_LAND] = ""  # type: ignore[index]


class DefaultsForTest(TestCase):
	def test_gives_the_defaults_of_a_chart_for_a_version(self):
		self.assertIs(defaults_for("SKR04", "6.9"), DEFAULTS["6.9"]["SKR04"])

	def test_a_chart_without_defaults_has_none(self):
		with self.assertRaisesRegex(
			KeyError, "no defaults of the Bilanzzuordnung for chart 'Eigener Kontenrahmen'"
		):
			defaults_for("Eigener Kontenrahmen", "6.9")
		with self.assertRaisesRegex(KeyError, "no defaults of the Bilanzzuordnung for the HGB-Taxonomie 6.8"):
			defaults_for("SKR03", "6.8")


class DefaultsVersionTest(TestCase):
	def test_the_version_names_the_chart_the_taxonomy_the_datev_edition_and_the_revision(self):
		self.assertEqual(dict(REVISIONS), {"6.9": 3, "6.10": 3})
		self.assertEqual(
			[defaults_version(chart, "6.9") for chart in sorted(CHARTS)],
			["SKR03 Taxonomie 6.9 2026.3", "SKR04 Taxonomie 6.9 2026.3"],
		)

	def test_a_chart_without_defaults_has_no_version(self):
		with self.assertRaisesRegex(
			KeyError, "no defaults of the Bilanzzuordnung for chart 'Eigener Kontenrahmen'"
		):
			defaults_version("Eigener Kontenrahmen", "6.9")

	def test_a_version_always_means_the_same_defaults(self):
		for version, charts in DEFAULTS.items():
			for chart, entry in charts.items():
				with self.subTest(version=version, chart=chart):
					digest = hashlib.sha256(canonical_json(entry.rows()).encode("utf-8")).hexdigest()
					self.assertEqual(
						digest,
						DIGESTS.get(defaults_version(chart, version)),
						f"The defaults of {chart} for the taxonomy {version} changed: raise REVISIONS[{version!r}] in "
						"steuerbote/ebilanz/defaults.py and pin the digest of the new version in DIGESTS.",
					)

	def test_the_docstring_describes_the_format_of_the_tables(self):
		for part in ("DefaultRule", "DefaultWatched", "DefaultExcluded", "REVISIONS", "defaults_version"):
			with self.subTest(part=part):
				self.assertIn(part, defaults.__doc__)


class CoverageTest(TestCase):
	"""Every account the DATEV charts „Gültig für 2026“ label and every account of ERPNext's templates."""

	def test_the_entries_are_the_labelled_accounts_and_ranges_of_the_charts_and_the_accounts_of_the_templates(
		self,
	):
		"""An entry per account or range DATEV prints, so that an account the chart does not label gets no default;
		besides them the accounts of ERPNext's template the DATEV edition does not have."""
		for chart in sorted(CHARTS):
			with self.subTest(chart=chart):
				spans = [str(found.accounts) for found in entries(defaults_for(chart, "6.9"))]
				labelled = set(LABELLED[chart])
				covered = {number for span in labelled for number in numbers(span)}
				self.assertEqual(Counter(spans).most_common(1)[0][1], 1)
				self.assertEqual(set(spans), labelled | (template_numbers(chart) - covered))

	def test_every_account_of_the_templates_has_a_place(self):
		for chart in sorted(CHARTS):
			with self.subTest(chart=chart):
				self.assertEqual(defaults_for(chart, "6.9").uncovered(template_numbers(chart)), ())

	def test_no_account_has_two_places(self):
		"""Each account lies in one group, so that a balance never counts twice; the twins of SKR03 and SKR04 share
		theirs."""
		for chart in sorted(CHARTS):
			with self.subTest(chart=chart):
				found = Counter(number for _group, span in accounts_of(chart) for number in numbers(span))
				self.assertEqual([number for number, count in found.items() if count > 1], [])

	def test_every_group_holds_accounts_with_their_label(self):
		for group in GROUPS["6.9"]:
			with self.subTest(group=group.accounts[0]):
				self.assertTrue(group.accounts)
				for account in group.accounts:
					self.assertTrue(account.skr03 or account.skr04)
					self.assertTrue(account.label)
					self.assertEqual(account.label, " ".join(account.label.split()))


class SourcesTest(TestCase):
	"""Every choice the labels of the account and the position do not tell alone carries its reason, and every reason
	its source."""

	def test_every_reason_is_used_and_names_its_source(self):
		self.assertEqual(
			{group.reason for groups in GROUPS.values() for group in groups} - {None}, set(Reason)
		)
		self.assertEqual(set(REASONS), set(Reason))
		for reason, text in REASONS.items():
			with self.subTest(reason=reason):
				self.assertTrue(any(source in text for source in SOURCES), text)

	def test_every_reason_outside_the_bilanz_and_the_guv_is_used_on_one_line(self):
		self.assertEqual({group.outside for group in GROUPS["6.9"]} - {None}, set(Outside))
		for outside in Outside:
			with self.subTest(outside=outside):
				self.assertEqual(outside.value, " ".join(outside.value.split()))

	def test_a_group_has_one_kind_of_place(self):
		for group in GROUPS["6.9"]:
			with self.subTest(group=group.accounts[0]):
				kinds = [group.concept is not None, group.level is not None, group.outside is not None]
				self.assertEqual(kinds.count(True), 1)
				if group.concept is None:
					self.assertEqual(
						(group.opposite, group.purpose, group.shareholder, group.remaining_term),
						(None, Purpose.BOTH, False, None),
					)

	def test_a_watched_group_and_the_position_for_the_opposite_balance_say_why(self):
		for group in GROUPS["6.9"]:
			if group.level is not None or group.opposite is not None:
				with self.subTest(group=group.accounts[0]):
					self.assertIsNotNone(group.reason)

	def test_an_abschlusszweck_other_than_datevs_says_why(self):
		"""Where the content of an account exists in one balance sheet only, the defaults say so although DATEV marks
		the account for both: the latente Steuern, the Steuerstundung, the Aufwandsrückstellungen and the
		Ingangsetzungsaufwendungen for the Handelsbilanz, the release of steuerfreie Rücklagen and the transfer of a
		§ 6b-Rücklage for the Steuerbilanz. A mark of DATEV is never contradicted."""
		reasons = {
			Reason.DEFERRED_TAXES: Purpose.COMMERCIAL,
			Reason.DEFERRAL_PROVISION: Purpose.COMMERCIAL,
			Reason.EXPENSE_PROVISIONS: Purpose.COMMERCIAL,
			Reason.START_UP_COSTS: Purpose.COMMERCIAL,
			Reason.TAX_RESERVE_RELEASE: Purpose.TAX,
			Reason.SEC_6B_TRANSFER: Purpose.TAX,
		}
		departures = Counter()
		for chart in sorted(CHARTS):
			marked = {
				**dict.fromkeys(COMMERCIAL[chart], Purpose.COMMERCIAL),
				**dict.fromkeys(TAX[chart], Purpose.TAX),
			}
			for group, span in accounts_of(chart):
				mark = marked.get(Accounts.of(span).first, Purpose.BOTH)
				if group.concept is None or group.purpose is mark:
					continue
				with self.subTest(chart=chart, accounts=span):
					self.assertIs(mark, Purpose.BOTH)
					self.assertIs(reasons.get(group.reason), group.purpose)
				departures[chart] += 1
		self.assertEqual(departures, {"SKR03": 10, "SKR04": 17})


class PlacesTest(TestCase):
	"""The places against the columns of the DATEV charts (steuerbote/ebilanz/tests/datev_charts.py)."""

	def test_an_account_whose_bilanzposten_names_both_sides_has_the_position_for_the_opposite_balance(self):
		"""„... oder ...“ (Fußnote 2), a side in either chart; the Gegenkonto of a split by remaining term and the
		accounts set off under § 246 Abs. 2 Satz 2 HGB keep one position (REASONS)."""
		one_position = {Reason.SPLIT_COUNTER, Reason.OFFSET_PENSIONS, Reason.OFFSET_OTHER}
		# The currency translation takes the position of the other direction although DATEV names one side: ERPNext
		# books gains and losses onto one account (REASONS).
		by_reason = {Reason.CURRENCY_TRANSLATION}
		labelled = {chart: set(LABELLED[chart]) for chart in CHARTS}
		for group in GROUPS["6.9"]:
			if group.concept is None:
				continue
			for account in group.accounts:
				spans = {chart: account.number(chart) for chart in CHARTS}
				both = any(
					span is not None and Accounts.of(span).first in BOTH_SIDES[chart]
					for chart, span in spans.items()
				)
				datev = any(span in labelled[chart] for chart, span in spans.items())
				both = both or group.netting is not None
				with self.subTest(account=account):
					if group.opposite is not None:
						self.assertTrue(both or not datev or group.reason in by_reason)
					elif both:
						self.assertIn(group.reason, one_position)

	def test_the_remaining_term_is_the_one_the_label_names(self):
		"""The label of the DATEV chart, or that of ERPNext's template for an account the DATEV edition does not have;
		but ERPNext's SKR03 template books goods received and not yet invoiced on 1702, whose label names one to five
		years."""
		for chart in sorted(CHARTS):
			labelled = {
				number: TERMS[words] for words, found in REMAINING_TERMS[chart].items() for number in found
			}
			labels = labels_of(chart)
			for group, span in accounts_of(chart):
				if group.concept is None:
					continue
				with self.subTest(chart=chart, accounts=span):
					if span in LABELLED[chart]:
						expected = labelled.get(span)
					else:
						short = TEMPLATE_TERM.search(labels[span])
						expected = TEMPLATE_TERMS[short.group(1)] if short else None
					if group.reason is Reason.TEMPLATE_SRBNB:
						expected = None
					if group.due is not None and expected is None:
						expected = RemainingTerm.UP_TO_ONE_YEAR
					self.assertIs(group.remaining_term, expected)
		self.assertEqual(
			[span for group, span in accounts_of("SKR03") if group.reason is Reason.TEMPLATE_SRBNB], ["1702"]
		)

	def test_an_account_of_the_einnahmenueberschussrechnung_has_no_position(self):
		"""A GmbH keeps books (§ 238 HGB); in class 9 the accounts of the EÜR are statistical."""
		for chart in sorted(CHARTS):
			for number in EUR[chart]:
				with self.subTest(chart=chart, account=number):
					found = defaults_for(chart, "6.9").entry_for(number)
					self.assertIsInstance(found, DefaultExcluded if number[0] == "9" else DefaultWatched)

	def test_a_watched_account_holds_the_documents_back(self):
		for chart in sorted(CHARTS):
			with self.subTest(chart=chart):
				self.assertEqual(
					{found.level for found in defaults_for(chart, "6.9").watched}, {WatchLevel.BLOCKING}
				)

	def test_the_accounts_of_a_template_group_have_a_place_for_the_numbers_below_them(self):
		"""A group of the template holds no balance itself; its number is that of a DATEV account or of the
		Debitoren of ERPNext's SKR04 template."""
		self.assertEqual(
			{chart: sorted(groups) for chart, groups in TEMPLATE_GROUPS.items()},
			{"SKR03": ["1400", "1600"], "SKR04": ["10000"]},
		)
		for chart, groups in TEMPLATE_GROUPS.items():
			for number in groups:
				with self.subTest(chart=chart, account=number):
					self.assertIsInstance(defaults_for(chart, "6.9").entry_for(number), DefaultRule)

	def test_the_main_accounts_of_a_gmbh_take_the_positions_the_e_bilanz_asks_for(self):
		output = "is.netIncome.regular.operatingTC.grossTradingProfit.totalOutput.netSales.grossSales"
		expected = [
			("0027", "0135", "bs.ass.fixAss.intan.concessionBrands", None),
			("0480", "0670", "bs.ass.fixAss.tan.otherEquipm.gwg", None),
			("1200", "1800", "bs.ass.currAss.cashEquiv.bank", "bs.eqLiab.liab.bank.other"),
			("0800", "2900", "bs.eqLiab.equity.subscribed.corp", None),
			("0956", "3035", "bs.eqLiab.accruals.tax.gewst", None),
			("0963", "3040", "bs.eqLiab.accruals.tax.kst", None),
			("8400", "4400", f"{output}.generalRateVAT", None),
			("4124", "6024", "is.netIncome.regular.operatingTC.staff.salaries.managerPartner", None),
			(
				"4654",
				"6644",
				"is.netIncome.regular.operatingTC.otherCost.limitedDeductible.entertainment.nonDeductible",
				None,
			),
			("4320", "7610", "is.netIncome.tax.gewst", None),
			("2200", "7600", "is.netIncome.tax.kst", None),
		]
		for skr03, skr04, concept, opposite in expected:
			for chart, number in (("SKR03", skr03), ("SKR04", skr04)):
				with self.subTest(chart=chart, account=number):
					found = defaults_for(chart, "6.9").entry_for(number)
					self.assertEqual(
						(type(found), found.concept, found.opposite, found.purpose),
						(DefaultRule, concept, opposite, Purpose.BOTH),
					)


VAT_NETTED = {
	"SKR03": (
		"1528 1529 1556 1557 1558 1559 1570 1571 1572 1574 1576 1577 1578 1560 1561 1562 1563 1566 1567 1569 1545 "
		"1546 1539 1585 1584 1588 1573 1770 1771 1772 1774 1776 1777 1778 1779 1794 1780 1781 1782 1784 1785 1787 "
		"1769 1789 1790 1791 1783 1797 1725"
	),
	"SKR04": (
		"1376 1377 1396 1397 1398 1399 1400 1401 1402 1404 1406 1407 1408 1410 1411 1412 1413 1416 1417 1419 1420 "
		"1421 1422 1425 1431 1432 1433 1436 3800 3801 3802 3804 3806 3807 3808 3809 3819 3820 3830 3832 3834 3835 "
		"3837 3839 3840 3841 3845 3851 3852 3860 3865"
	),
}
"""The VAT accounts of SKR03 and SKR04 towards the Finanzamt that the defaults net as one settlement position: the
deductible Vorsteuer, the Umsatzsteuer, the Vorauszahlungen and the claims and debts of earlier years. Not among them:
the Vorsteuer deductible only in a later period (1548/1434) and the Umsatzsteuer not yet due, which are no claims or
debts that can be set off yet, the Einfuhrumsatzsteuer aufgeschoben owed to the customs office (3850), and the tax of
other member states."""


class NettingTest(TestCase):
	"""The usual assignments of the standard charts show the VAT accounts towards the Finanzamt on the asset or the
	liability side by the balance of the group: claims and debts of the same kind towards the same creditor that can
	be set off against each other (§ 387 BGB, § 226 Abs. 1 AO, § 16 Abs. 2 Satz 1 UStG) are netted; § 246 Abs. 2
	Satz 1 HGB bars netting only where no such set-off is possible."""

	def test_the_vat_accounts_towards_the_finanzamt_form_one_netting_group(self):
		for chart in sorted(CHARTS):
			with self.subTest(chart=chart):
				netted = [span for group, span in accounts_of(chart) if group.netting == defaults.VAT_NETTING]
				self.assertEqual(sorted(netted), sorted(VAT_NETTED[chart].split()))

	def test_every_netting_group_has_the_position_on_each_side_and_says_why(self):
		self.assertEqual(
			{group.netting for groups in GROUPS.values() for group in groups} - {None}, {defaults.VAT_NETTING}
		)
		for group in GROUPS["6.9"]:
			if group.netting is not None:
				with self.subTest(group=group.accounts[0]):
					self.assertEqual(
						{group.concept, group.opposite},
						{"bs.ass.currAss.receiv.other.vat", "bs.eqLiab.liab.other.theroffTax"},
					)
					self.assertIs(group.reason, Reason.VAT)

	def test_a_netted_group_of_vorsteuer_and_umsatzsteuer_is_one_position(self):
		taxonomy = real.view()
		for chart, (receivable, liability) in {"SKR03": ("1576", "1776"), "SKR04": ("1406", "3806")}.items():
			defaults_of = defaults_for(chart, taxonomy.version)
			books = Books(
				(
					AccountBalance(receivable, receivable, "Vorsteuer", Part.BALANCE_SHEET, D("300")),
					AccountBalance(liability, liability, "Umsatzsteuer", Part.BALANCE_SHEET, D(0), D("500")),
				)
			)
			placement = place(
				defaults_of.for_accounts([receivable, liability]), books, taxonomy, Purpose.BOTH
			)
			with self.subTest(chart=chart):
				self.assertEqual(
					{item.concept for item in placement.placed}, {"bs.eqLiab.liab.other.theroffTax"}
				)
				self.assertEqual(sum(item.value for item in placement.placed), D("200"))


class DueTest(TestCase):
	"""The Forderungen and Verbindlichkeiten that the law makes due within a year carry the remaining term „bis 1
	Jahr“, which the Vermerke of § 268 Abs. 4 Satz 1 and Abs. 5 Satz 1 HGB need, although their label names none."""

	def test_every_ground_of_a_due_date_is_used_and_names_its_source(self):
		self.assertEqual({group.due for group in GROUPS["6.9"]} - {None}, set(defaults.Due))
		self.assertEqual(set(defaults.DUE_SOURCES), set(defaults.Due))
		for due, text in defaults.DUE_SOURCES.items():
			with self.subTest(due=due):
				self.assertIn("§", text)

	def test_a_group_due_within_a_year_has_the_remaining_term_up_to_one_year(self):
		for group in GROUPS["6.9"]:
			if group.due is not None:
				with self.subTest(group=group.accounts[0]):
					self.assertIs(group.remaining_term, RemainingTerm.UP_TO_ONE_YEAR)

	def test_the_taxes_wages_and_contributions_due_by_law_are_due_within_a_year(self):
		expected = {
			defaults.Due.VAT: set(VAT_NETTED["SKR03"].split()) | {"1548"},
			defaults.Due.WAGE_TAX: {"1741", "1749"},
			defaults.Due.SOCIAL_SECURITY: {"1742", "1759"},
			defaults.Due.WAGES: {"1740", "1755"},
		}
		found: dict = {}
		for group, span in accounts_of("SKR03"):
			if group.due is not None:
				found.setdefault(group.due, set()).add(span)
		self.assertEqual(found, expected)


class PositionsTest(TestCase):
	"""Against the package of each version (steuerbote/xbrl/tests/real.py)."""

	def test_every_position_of_the_defaults_passes_the_checks_of_the_mapping(self):
		taxonomy = real.view()
		for chart, entry in DEFAULTS[taxonomy.version].items():
			with self.subTest(chart=chart):
				numbers = [rule.accounts.first for rule in entry.rules]
				self.assertEqual(
					[problem.message for problem in mapping.check(entry.for_accounts(numbers), taxonomy)], []
				)

	def test_every_position_belongs_to_the_part_of_the_account_of_the_template(self):
		"""ERPNext sums an account of the root types Asset, Liability and Equity up to the day, one of Income and
		Expense within the year (Part)."""
		taxonomy = real.view()
		for chart, entry in DEFAULTS[taxonomy.version].items():
			with self.subTest(chart=chart):
				parts = {
					number: PARTS[root]
					for root, found in TEMPLATES[chart].items()
					for number in found
					if number not in TEMPLATE_GROUPS[chart]
				}
				placed = entry.for_accounts(parts)
				self.assertEqual(len(placed.rules) + len(placed.watched) + len(placed.excluded), len(parts))
				self.assertEqual([problem.message for problem in mapping.check(placed, taxonomy, parts)], [])

	def test_every_position_is_the_deepest_the_e_bilanz_of_a_gmbh_asks_for(self):
		"""A Mussfeld or Summenmussfeld, or a position „Rechnerisch notwendig, soweit vorhanden“ or an Auffangposition
		beside Mussfeldern, and none of them below it (Leitfaden A.10.1, A.10.3, A.10.4)."""
		taxonomy = real.view()
		case = Case("GmbH", YEAR, AccountingStandard.HANDELSBILANZ)
		marks = {position.concept: position.mark for position in structure(taxonomy, case).positions}
		networks = (taxonomy.presentation[BALANCE_SHEET], taxonomy.presentation[INCOME_STATEMENT])

		def deepest(concept: str) -> bool:
			name = f"de-gaap-ci:{concept}"
			(network,) = (network for network in networks if name in network)
			below = [marks.get(arc.child) for arc in network.children(name)]
			parent = network.parent(name)
			beside = [marks.get(arc.child) for arc in network.children(parent)] if parent else []
			mark = marks.get(name)
			return (
				mark in REQUIRED | {Mark.AUFFANG}
				and not REQUIRED.intersection(below)
				and (mark in (Mark.MUSSFELD, Mark.SUMMENMUSSFELD) or bool(REQUIRED.intersection(beside)))
			)

		for group in GROUPS[taxonomy.version]:
			for concept in (group.concept, group.opposite):
				if concept is not None:
					with self.subTest(concept=concept):
						self.assertTrue(deepest(concept))

	def test_a_position_the_steuerbilanz_does_not_permit_is_one_of_the_handelsbilanz(self):
		"""„Die mit „steuerlich“ unzulässig (notPermittedFor) gekennzeichneten Positionen dürfen in der Steuerbilanz
		nicht enthalten sein“ (Leitfaden B.16.2)."""
		taxonomy = real.view()
		for group in GROUPS[taxonomy.version]:
			if group.concept is None:
				continue
			for concept in (group.concept, group.opposite):
				if (
					concept is not None
					and "steuerlich" in taxonomy.concept(f"de-gaap-ci:{concept}").fiscal.not_permitted_for
				):
					with self.subTest(concept=concept):
						self.assertIs(group.purpose, Purpose.COMMERCIAL)

	def test_the_shareholder_flag_is_on_every_position_gegenueber_gesellschaftern(self):
		"""The Ausleihungen, Forderungen and Verbindlichkeiten gegenüber Gesellschaftern (§ 42 Abs. 3 GmbHG); a stiller
		Gesellschafter is none of the GmbH."""
		taxonomy = real.view()
		network = taxonomy.presentation[BALANCE_SHEET]
		scopes = {f"de-gaap-ci:{scope}" for scope in SHAREHOLDER_SCOPES}

		def owed_to_shareholders(concept: str) -> bool:
			name = f"de-gaap-ci:{concept}"
			label = taxonomy.label(name, LABEL)
			within = name in network and bool(scopes.intersection((name, *network.ancestors(name))))
			return within and "Gesellschafter" in label and "still" not in label

		for group in GROUPS[taxonomy.version]:
			if group.concept is not None:
				with self.subTest(concept=group.concept):
					self.assertIs(group.shareholder, owed_to_shareholders(group.concept))

	def test_every_auffangposition_says_why_and_takes_its_balance_with_a_hint(self):
		"""„Ist eine durch Mussfelder vorgegebene Differenzierung für einen bestimmten Sachverhalt nicht aus der
		Buchhaltung ableitbar, können ... diese Auffangpositionen genutzt werden“ (Leitfaden A.10.4)."""
		taxonomy = real.view()
		for chart in sorted(CHARTS):
			by_purpose: dict[Purpose, list[AccountBalance]] = {}
			for group, span in accounts_of(chart):
				if group.concept is not None and mapping.catch_all(taxonomy, group.concept):
					with self.subTest(chart=chart, accounts=span):
						self.assertIsNotNone(group.reason)
					number = Accounts.of(span).first
					part = Part.BALANCE_SHEET if group.concept.startswith("bs.") else Part.INCOME_STATEMENT
					amount = on_side(taxonomy, group.concept, D("100.00"))
					by_purpose.setdefault(group.purpose, []).append(
						AccountBalance(number, number, "", part, max(amount, D(0)), max(-amount, D(0)))
					)
			self.assertGreater(sum(map(len, by_purpose.values())), 70)
			for purpose, balances in by_purpose.items():
				with self.subTest(chart=chart, purpose=purpose):
					placement = place(
						defaults_for(chart, "6.9").for_accounts(balance.number for balance in balances),
						Books(tuple(balances)),
						taxonomy,
						purpose,
						fiscal_year=FISCAL_YEAR,
					)
					self.assertEqual(
						[(finding.code, finding.account) for finding in placement.findings],
						[(Code.CATCH_ALL, balance.number) for balance in balances],
					)
					self.assertTrue(placement.ready)


# An invented GmbH in its third year, on SKR04 and the same on SKR03: software, a car, office furniture and a GWG,
# goods, a receivable, Vorsteuer, cash and a bank account, a prepaid expense, its Stammkapital and Gewinnvortrag, the
# provisions for Gewerbe- and Körperschaftsteuer, a bank loan, payables, wage tax, social security and Umsatzsteuer;
# sales, goods, the salaries of the Gesellschafter-Geschäftsführer and the staff, depreciation, rent, insurance,
# office costs, advice, entertainment, interest and the taxes on income. Each balance is debit minus credit.
GMBH = (
	("0027", "0135", "EDV-Software", "12000.00"),
	("0320", "0520", "Pkw", "28000.00"),
	("0420", "0650", "Büroeinrichtung", "7500.00"),
	("0480", "0670", "Geringwertige Wirtschaftsgüter", "900.00"),
	("3980", "1140", "Waren (Bestand)", "15400.00"),
	("1400", "1200", "Forderungen aus Lieferungen und Leistungen", "23800.00"),
	("1576", "1406", "Abziehbare Vorsteuer 19 %", "1520.00"),
	("1000", "1600", "Kasse", "450.00"),
	("1200", "1800", "Bank", "34450.00"),
	("0980", "1900", "Aktive Rechnungsabgrenzung", "1200.00"),
	("0800", "2900", "Gezeichnetes Kapital", "-25000.00"),
	("0860", "2970", "Gewinnvortrag vor Verwendung", "-18400.00"),
	("0956", "3035", "Gewerbesteuerrückstellung nach § 4 Abs. 5b EStG", "-3100.00"),
	("0963", "3040", "Körperschaftsteuerrückstellung", "-3300.00"),
	("0970", "3070", "Sonstige Rückstellungen", "-2500.00"),
	("0630", "3150", "Verbindlichkeiten gegenüber Kreditinstituten", "-30000.00"),
	("1600", "3300", "Verbindlichkeiten aus Lieferungen und Leistungen", "-11900.00"),
	("1741", "3730", "Verbindlichkeiten aus Lohn- und Kirchensteuer", "-2100.00"),
	("1742", "3740", "Verbindlichkeiten im Rahmen der sozialen Sicherheit", "-1900.00"),
	("1776", "3806", "Umsatzsteuer 19 %", "-7600.00"),
	("8400", "4400", "Erlöse 19 % USt", "-250000.00"),
	("3400", "5400", "Wareneingang 19 % Vorsteuer", "92000.00"),
	("4124", "6024", "Geschäftsführergehälter der GmbH-Gesellschafter", "60000.00"),
	("4120", "6020", "Gehälter", "32000.00"),
	("4130", "6110", "Gesetzliche soziale Aufwendungen", "6700.00"),
	("4832", "6222", "Abschreibungen auf Fahrzeuge", "7000.00"),
	("4822", "6200", "Abschreibungen auf immaterielle Vermögensgegenstände", "4000.00"),
	("4855", "6260", "Sofortabschreibung geringwertiger Wirtschaftsgüter", "900.00"),
	("4210", "6310", "Miete (unbewegliche Wirtschaftsgüter)", "14400.00"),
	("4360", "6400", "Versicherungen", "1500.00"),
	("4930", "6815", "Bürobedarf", "800.00"),
	("4950", "6825", "Rechts- und Beratungskosten", "2500.00"),
	("4650", "6640", "Bewirtungskosten", "700.00"),
	("4654", "6644", "Nicht abzugsfähige Bewirtungskosten", "300.00"),
	("2110", "7310", "Zinsaufwendungen für kurzfristige Verbindlichkeiten", "1200.00"),
	("2200", "7600", "Körperschaftsteuer", "3300.00"),
	("2208", "7608", "Solidaritätszuschlag", "180.00"),
	("4320", "7610", "Gewerbesteuer", "3100.00"),
)


class InventedGmbHTest(TestCase):
	"""The books of the invented GmbH through the defaults, place(), the balances the Bilanzzuordnung gives the
	E-Bilanz (steuerbote/balance_mapping_sync.py) and calculate(), against the package."""

	def e_bilanz(self, chart: str):
		taxonomy = real.view()
		index = sorted(CHARTS).index(chart)
		rows = [(row[index], row[2], D(row[3])) for row in GMBH]
		self.assertEqual(sum(amount for *_rest, amount in rows), 0)
		defaults_of = defaults_for(chart, taxonomy.version)
		books = Books(
			tuple(
				AccountBalance(
					f"{number} - {label}",
					number,
					label,
					Part.BALANCE_SHEET
					if defaults_of.entry_for(number).concept.startswith("bs.")
					else Part.INCOME_STATEMENT,
					max(amount, D(0)),
					max(-amount, D(0)),
				)
				for number, label, amount in rows
			)
		)
		placement = place(
			defaults_of.for_accounts(number for number, *_rest in rows),
			books,
			taxonomy,
			Purpose.BOTH,
			fiscal_year=FISCAL_YEAR,
		)
		self.assertEqual(
			([finding.code for finding in placement.findings], placement.left_out), ([Code.NETTED], ())
		)
		return calculate(structure(taxonomy, Case("GmbH", YEAR)), ebilanz_balances(placement))

	def test_the_books_on_skr04_make_an_e_bilanz_with_netted_vat_in_which_aktiva_and_passiva_agree(self):
		found = self.e_bilanz("SKR04")
		self.assertEqual(found.findings, ())
		self.assertEqual(
			(found.amount("bs.ass"), found.amount("bs.eqLiab")), (D("123700.00"), D("123700.00"))
		)
		self.assertEqual(found.amount("bs.eqLiab.liab.other.theroffTax"), D("8180.00"))
		self.assertEqual(found.amount("is.netIncome"), D("19420.00"))

	def test_the_books_on_skr03_give_the_same_e_bilanz(self):
		found, twin = self.e_bilanz("SKR03"), self.e_bilanz("SKR04")
		self.assertEqual(found.findings, ())
		self.assertEqual(found.amounts(), twin.amounts())


OTHER_TAXES_6_10 = {
	("4340", "7650"): "is.netIncome.otherTaxes.other",
	("4350", "7675"): "is.netIncome.otherTaxes.other",
	("4355", "7678"): "is.netIncome.otherTaxes.other",
	("2375", "7680"): "is.netIncome.otherTaxes.GrSt",
	("4510", "7685"): "is.netIncome.otherTaxes.other",
	("2285", "7690"): "is.netIncome.otherTaxes.other",
	("2287", "7692"): "is.netIncome.otherTaxes.other",
	("2289", "7694"): "is.netIncome.otherTaxes.releaseTaxProvision",
}
"""The accounts of the sonstige Steuern of SKR03 and SKR04 with their positions on 6.10, all on „sonstige Steuern“
on 6.9."""


class Taxonomy610Test(TestCase):
	"""The defaults of 6.10: those of 6.9 through the changes of the taxonomy (steuerbote/xbrl/changes.py), with the
	group of the sonstige Steuern taken apart, whose Summenmussfeld takes no balance of its own beside the new Mussfeld
	of the Grundsteuer."""

	def test_6_10_renames_and_removes_no_position_of_the_defaults_of_6_9(self):
		(step,) = changes.between("6.9", "6.10")
		named = {
			f"de-gaap-ci:{concept}"
			for group in GROUPS["6.9"]
			for concept in (group.concept, group.opposite)
			if concept is not None
		}
		self.assertEqual(sorted(named & (set(step.renamed) | step.removed)), [])

	def test_the_defaults_of_6_10_are_those_of_6_9_but_the_sonstige_steuern(self):
		for index, chart in enumerate(sorted(CHARTS)):
			with self.subTest(chart=chart):
				before, after = (
					{str(entry.accounts): entry for entry in entries(DEFAULTS[version][chart])}
					for version in ("6.9", "6.10")
				)
				self.assertEqual(set(before), set(after))
				changed = {
					number: after[number].concept for number in after if after[number] != before[number]
				}
				self.assertEqual(
					changed, {pair[index]: concept for pair, concept in OTHER_TAXES_6_10.items()}
				)
				self.assertEqual({before[number].concept for number in changed}, {"is.netIncome.otherTaxes"})

	def test_the_groups_carry_the_renames_and_refuse_a_removed_position(self):
		group = next(group for group in GROUPS["6.9"] if group.concept == "bs.ass.currAss.cashEquiv.bank")
		renamed = changes.Changes(
			"6.9",
			"6.10",
			renamed={"de-gaap-ci:bs.ass.currAss.cashEquiv.bank": "de-gaap-ci:bs.ass.currAss.cashEquiv.banks"},
			removed=frozenset(),
			added=frozenset(),
			mussfelder=(),
			source="invented",
		)
		(carried,) = defaults._carried((group,), (renamed,), {})
		self.assertEqual(
			(carried.concept, carried.opposite), ("bs.ass.currAss.cashEquiv.banks", group.opposite)
		)
		removed = replace(
			renamed, renamed={}, removed=frozenset({"de-gaap-ci:bs.ass.currAss.cashEquiv.bank"})
		)
		with self.assertRaisesRegex(ValueError, "which the taxonomy 6.10 removes"):
			defaults._carried((group,), (removed,), {})

	def test_every_position_of_6_10_passes_the_checks_of_the_mapping_and_is_the_deepest(self):
		"""Against the package 6.10, as PositionsTest against that of 6.9 (Leitfaden A.10.1, A.10.3, A.10.4)."""
		taxonomy = real.view_6_10()
		for chart, entry in DEFAULTS["6.10"].items():
			with self.subTest(chart=chart):
				numbers = [rule.accounts.first for rule in entry.rules]
				self.assertEqual(
					[problem.message for problem in mapping.check(entry.for_accounts(numbers), taxonomy)], []
				)
		case = Case("GmbH", Periods(date(2027, 1, 1), date(2027, 12, 31)), AccountingStandard.HANDELSBILANZ)
		marks = {position.concept: position.mark for position in structure(taxonomy, case).positions}
		networks = (taxonomy.presentation[BALANCE_SHEET], taxonomy.presentation[INCOME_STATEMENT])
		for group in GROUPS["6.10"]:
			for concept in (group.concept, group.opposite):
				if concept is None:
					continue
				name = f"de-gaap-ci:{concept}"
				(network,) = (network for network in networks if name in network)
				below = [marks.get(arc.child) for arc in network.children(name)]
				parent = network.parent(name)
				beside = [marks.get(arc.child) for arc in network.children(parent)] if parent else []
				mark = marks.get(name)
				with self.subTest(concept=concept):
					self.assertIn(mark, REQUIRED | {Mark.AUFFANG})
					self.assertFalse(REQUIRED.intersection(below))
					self.assertTrue(
						mark in (Mark.MUSSFELD, Mark.SUMMENMUSSFELD) or REQUIRED.intersection(beside)
					)

	def test_the_invented_gmbh_with_grundsteuer_and_kfz_steuer_makes_an_e_bilanz_of_2027(self):
		"""The GmbH of InventedGmbHTest on SKR04 with a Grundsteuer and a Kfz-Steuer paid from the bank."""
		taxonomy = real.view_6_10()
		rows = [
			*((row[1], row[2], D(row[3])) for row in GMBH if row[1] != "1800"),
			("1800", "Bank", D("33550.00")),
			("7680", "Grundsteuer", D("600.00")),
			("7685", "Kfz-Steuer", D("300.00")),
		]
		self.assertEqual(sum(amount for *_rest, amount in rows), 0)
		defaults_of = defaults_for("SKR04", "6.10")
		books = Books(
			tuple(
				AccountBalance(
					f"{number} - {label}",
					number,
					label,
					Part.BALANCE_SHEET
					if defaults_of.entry_for(number).concept.startswith("bs.")
					else Part.INCOME_STATEMENT,
					max(amount, D(0)),
					max(-amount, D(0)),
				)
				for number, label, amount in rows
			)
		)
		year = Periods(date(2027, 1, 1), date(2027, 12, 31))
		placement = place(
			defaults_of.for_accounts(number for number, *_rest in rows),
			books,
			taxonomy,
			Purpose.BOTH,
			fiscal_year=(year.fiscal_year_begin, year.fiscal_year_end),
		)
		self.assertEqual(
			([finding.code for finding in placement.findings], placement.left_out), ([Code.NETTED], ())
		)
		found = calculate(structure(taxonomy, Case("GmbH", year)), ebilanz_balances(placement))
		self.assertEqual(found.findings, ())
		self.assertEqual(
			(
				found.amount("is.netIncome.otherTaxes.GrSt"),
				found.amount("is.netIncome.otherTaxes.other"),
				found.amount("is.netIncome.otherTaxes"),
			),
			(D("600.00"), D("300.00"), D("900.00")),
		)
		self.assertEqual(found.amount("is.netIncome"), D("18520.00"))


class CurrencyDefaultsTest(TestCase):
	"""ERPNext's Wechselkursneubewertung books gains and losses onto one account; whichever side its balance takes, it
	goes to the position of its direction (§ 277 Abs. 5 Satz 2 HGB)."""

	LOSS = "is.netIncome.regular.operatingTC.otherCost.currLoss"
	GAINS = "is.netIncome.regular.operatingTC.otherOpRevenue.currGains"

	def test_the_accounts_of_the_currency_translation_name_the_position_of_the_other_direction(self):
		expected = {
			"SKR03": {
				"2150": (self.LOSS, self.GAINS),
				"2151": (self.LOSS, self.GAINS),
				"2660": (self.GAINS, self.LOSS),
			},
			"SKR04": {
				"6880": (self.LOSS, self.GAINS),
				"6881": (self.LOSS, self.GAINS),
				"4840": (self.GAINS, self.LOSS),
			},
		}
		for version in TAXONOMIES:
			for chart, accounts in expected.items():
				rules = defaults_for(chart, version).rules
				for number, positions in accounts.items():
					with self.subTest(version=version, chart=chart, account=number):
						(rule,) = [rule for rule in rules if number in rule.accounts]
						self.assertEqual(
							(rule.concept.rpartition(":")[2], (rule.opposite or "").rpartition(":")[2]),
							positions,
						)

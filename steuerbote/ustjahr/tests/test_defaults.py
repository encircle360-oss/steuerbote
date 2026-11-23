"""The defaults of the annual return for SKR03 and SKR04: the annual field of an account by its role, and the accounts
only the annual return reads, with the version of the defaults."""

import hashlib
import json
from unittest import TestCase

from steuerbote.ustjahr import defaults
from steuerbote.ustjahr.defaults import REVISIONS, ROLE_FIELDS, annual_rules, defaults_version, role_defaults
from steuerbote.ustjahr.form import Format, catalogue_for
from steuerbote.ustjahr.split import AnnualRule, How, split
from steuerbote.ustva.defaults import (
	SKR03,
	SKR03_RANGES,
	SKR04,
	SKR04_RANGES,
	default_mapping,
	deliberately_without_kennzahl,
	with_ranges,
)
from steuerbote.ustva.mapping import AccountRule, Mapping, Side, WatchLevel
from steuerbote.ustva.years import UnknownYearError

YEAR = 2026
CHARTS = {"SKR03": (SKR03, SKR03_RANGES), "SKR04": (SKR04, SKR04_RANGES)}

# Every role default of 2026 by the first account of its role: SKR03 account, SKR04 account, the Kennzahl of the
# Voranmeldung the defaults map it to, and the annual field, by its line of form USt 2 A 2026. The members of a
# DATEV range share the default of its first account.
ROLES_2026 = (
	# Lieferungen nach § 3 Absatz 1b UStG zu 19 %, line 25 (Kz 178)
	("8910", "4620", "81", "E3003405"),
	("8935", "4686", "81", "E3003405"),
	("8940", "4680", "81", "E3003405"),
	# Sonstige Leistungen nach § 3 Absatz 9a UStG zu 19 %, line 26 (Kz 179)
	("8920", "4640", "81", "E3003505"),
	("8921", "4645", "81", "E3003505"),
	("8922", "4646", "81", "E3003505"),
	("8925", "4660", "81", "E3003505"),
	# the same at 7 %, lines 28 and 29 (Kz 195 and 196)
	("8915", "4610", "86", "E3003703"),
	("8917", "4616", "86", "E3003703"),
	("8945", "4670", "86", "E3003703"),
	("8947", "4676", "86", "E3003703"),
	("8930", "4630", "86", "E3003803"),
	("8931", "4636", "86", "E3003803"),
	("8932", "4650", "86", "E3003803"),
	("8933", "4656", "86", "E3003803"),
	# Ausfuhrlieferungen, line 45 (Kz 752); Offshore, line 47; Reiseleistungen § 25 Absatz 2 UStG, line 49
	("8120", "4120", "43", "E3103801"),
	("8807", "6884", "43", "E3103801"),
	("8827", "4844", "43", "E3103801"),
	("8705", "4705", "43", "E3103801"),
	("8140", "4140", "43", "E3104001"),
	("8194", "4139", "43", "E3104101"),
	# § 4 Nummer 12 UStG, line 51 (Kz 286); § 19 Absatz 1 UStG, line 53 (Kz 236); zum Gesamtumsatz, line 54 (Kz 240)
	("8105", "4105", "48", "E3104401"),
	("2751", "4861", "48", "E3104401"),
	("8192", "4184", "48", "E3104701"),
	("8195", "4185", "48", "E3104701"),
	("8707", "4707", "48", "E3104701"),
	("8160", "4160", "48", "E3104902"),
	("8165", "4165", "48", "E3104902"),
	# Vorsteuer des Auslagerers, line 88 (Kz 466); aus Dreiecksgeschäften, line 92 (Kz 760)
	("1585", "1431", "66", "E3006503"),
	("1573", "1436", "66", "E3006801"),
	# § 15a UStG: lines 105 to 107, nachträglich abziehbar and zurückzuzahlen
	("1558", "1398", "64", "E3008701"),
	("1559", "1399", "64", "E3008702"),
	("1556", "1396", "64", "E3008801"),
	("1557", "1397", "64", "E3008802"),
	("1528", "1376", "64", "E3008803"),
	("1529", "1377", "64", "E3008804"),
	# the tax of the last buyer of a Dreiecksgeschäft at 19 %, line 66
	("1794", "3819", "69", "E3101702"),
)
# The tax the Auslagerer owes, line 63 (Kz 853): the defaults of the Voranmeldung watch its account, which takes its
# line once the company maps it to Kz 69.
WATCHED_ROLES_2026 = (("1769", "3839", "69", "E3102805"),)

# Every account only the annual return reads in 2026: SKR03 account, SKR04 account, the field it feeds and the side of
# its balance.
ANNUAL_2026 = (
	# Erwerb des ersten Abnehmers in an innergemeinschaftliches Dreiecksgeschäft, line 55 (Kz 789)
	("3552", "5552", "E3100801", Side.DEBIT),
	# Erwerb als letzter Abnehmer in a Dreiecksgeschäft at 19 % and its Skonti, line 66 (Kz 751)
	("3089", "5189", "E3101701", Side.DEBIT),
	("3553", "5553", "E3101701", Side.DEBIT),
	("3792", "5792", "E3101701", Side.DEBIT),
	("3793", "5793", "E3101701", Side.DEBIT),
	# Einkauf aus einem Umsatzsteuerlager, the Lieferungen before the Auslagerung, line 63 (Kz 852)
	("3075", "5175", "E3102804", Side.DEBIT),
	("3076", "5176", "E3102804", Side.DEBIT),
	("3560", "5560", "E3102804", Side.DEBIT),
	("3565", "5565", "E3102804", Side.DEBIT),
)
# The tax of a base only the annual return reads, which the Voranmeldung holds in Kz 69: SKR03 account, SKR04 account.
TAXES_OF_ANNUAL_BASES = {"E3101701": ("1794", "3819"), "E3102804": ("1769", "3839")}

COLUMNS = {"SKR03": 0, "SKR04": 1}


def first_accounts(chart: str) -> dict[str, tuple[str, str]]:
	"""The expected default of each first account of a role in the chart: its Kennzahl and its annual field."""
	return {row[COLUMNS[chart]]: (row[2], row[3]) for row in (*ROLES_2026, *WATCHED_ROLES_2026)}


class RoleFieldsTest(TestCase):
	"""The annual field of each role, as the form USt 2 A 2026 and its Anleitung USt 2 E 2026 name its line."""

	def test_each_role_has_the_line_of_its_kind_of_sale_or_tax(self):
		for chart in CHARTS:
			with self.subTest(chart=chart):
				fields = role_defaults(chart, YEAR)
				self.assertEqual(
					{number: fields[number] for number in first_accounts(chart)},
					{number: field for number, (_, field) in first_accounts(chart).items()},
				)

	def test_the_field_is_a_line_of_the_kennzahl_the_defaults_map_the_account_to(self):
		"""split() leaves a role default aside that the Kennzahl of the rule does not take."""
		catalogue = catalogue_for(YEAR)
		for chart, (mapping, _) in CHARTS.items():
			column = COLUMNS[chart]
			for row in ROLES_2026:
				number, kennzahl, field = row[column], row[2], row[3]
				with self.subTest(chart=chart, account=number):
					self.assertEqual(mapping.rule_for(number).kennzahl, kennzahl)
					self.assertEqual(catalogue.field(field).ustva, kennzahl)

	def test_the_tax_of_the_auslagerung_takes_line_63_once_the_account_is_mapped_to_kz_69(self):
		"""The defaults of the Voranmeldung watch the account, since its Kennzahl is not decided there."""
		catalogue = catalogue_for(YEAR)
		for chart, (mapping, _) in CHARTS.items():
			column = COLUMNS[chart]
			for row in WATCHED_ROLES_2026:
				number, kennzahl, field = row[column], row[2], row[3]
				with self.subTest(chart=chart, account=number):
					self.assertIsNone(mapping.rule_for(number))
					self.assertIn(number, mapping.watched_at(WatchLevel.BLOCKING))
					self.assertEqual(catalogue.field(field).ustva, kennzahl)
					mapped = Mapping(chart, (AccountRule(number, kennzahl, Side.CREDIT),), year=YEAR)
					assignment = split(mapped, role_defaults=role_defaults(chart, YEAR)).assignment(number)
					self.assertEqual((assignment.field, assignment.how), (field, How.ROLE))

	def test_a_role_names_a_line_only_where_its_kennzahl_would_take_another_one(self):
		"""Every other account takes the default line of its Kennzahl (steuerbote/ustjahr/split.py); Kz 64 has none."""
		catalogue = catalogue_for(YEAR)
		for role, field in ROLE_FIELDS[YEAR].items():
			with self.subTest(role=role):
				default = catalogue.default_child(catalogue.field(field).ustva)
				self.assertTrue(default is None or default.element != field)

	def test_every_member_of_a_range_takes_the_field_of_its_first_account(self):
		for chart, (_, ranges) in CHARTS.items():
			fields = role_defaults(chart, YEAR)
			for number, (_, field) in first_accounts(chart).items():
				for member in with_ranges((number,), ranges):
					with self.subTest(chart=chart, account=member):
						self.assertEqual(fields[member], field)
		self.assertEqual(role_defaults("SKR03", YEAR)["8913"], "E3003405")
		self.assertEqual(role_defaults("SKR04", YEAR)["4666"], "E3003505")

	def test_holds_no_other_account(self):
		for chart, (_, ranges) in CHARTS.items():
			with self.subTest(chart=chart):
				expected = {
					member for number in first_accounts(chart) for member in with_ranges((number,), ranges)
				}
				self.assertEqual(set(role_defaults(chart, YEAR)), expected)

	def test_skr04_mirrors_skr03_role_by_role(self):
		self.assertEqual(
			sorted(set(role_defaults("SKR03", YEAR).values())),
			sorted(set(role_defaults("SKR04", YEAR).values())),
		)
		for skr03, skr04, _, _ in (*ROLES_2026, *WATCHED_ROLES_2026):
			with self.subTest(skr03=skr03, skr04=skr04):
				self.assertEqual(role_defaults("SKR03", YEAR)[skr03], role_defaults("SKR04", YEAR)[skr04])

	def test_the_default_mappings_split_by_the_roles(self):
		for chart, (_, ranges) in CHARTS.items():
			result = split(default_mapping(chart, YEAR), role_defaults=role_defaults(chart, YEAR))
			for row in ROLES_2026:
				for number in with_ranges((row[COLUMNS[chart]],), ranges):
					with self.subTest(chart=chart, account=number):
						assignment = result.assignment(number)
						self.assertEqual((assignment.field, assignment.how), (row[3], How.ROLE))

	def test_is_read_only(self):
		with self.assertRaises(TypeError):
			role_defaults("SKR03", YEAR)["8400"] = "E3003303"  # type: ignore[index]
		with self.assertRaises(TypeError):
			ROLE_FIELDS[YEAR]["revenue_19"] = "E3003303"  # type: ignore[index]

	def test_a_chart_without_defaults_has_no_roles(self):
		with self.assertRaisesRegex(
			KeyError, "no defaults of the annual return for chart 'Eigener Kontenrahmen'"
		):
			role_defaults("Eigener Kontenrahmen", YEAR)

	def test_a_year_without_its_form_has_no_roles(self):
		with self.assertRaisesRegex(UnknownYearError, "Umsatzsteuererklärung 2027"):
			role_defaults("SKR03", YEAR + 1)

	def test_the_module_cites_the_letter_of_the_form_and_the_datev_charts(self):
		text = " ".join((defaults.__doc__ or "").split())
		self.assertIn("BMF letter of 29 December 2025 (GZ III C 3 - S 7344/00040/008/034)", text)
		self.assertIn("Art.-Nr. 11174", text)
		self.assertIn("Art.-Nr. 11175", text)


class AnnualRulesTest(TestCase):
	"""The accounts only the annual return reads, „Zuordnung nur für die Umsatzsteuererklärung“."""

	def test_each_chart_reads_the_accounts_of_the_dreiecksgeschaeft_and_of_the_umsatzsteuerlager(self):
		for chart in CHARTS:
			with self.subTest(chart=chart):
				self.assertEqual(
					annual_rules(chart, YEAR),
					tuple(AnnualRule(row[COLUMNS[chart]], row[2], row[3]) for row in ANNUAL_2026),
				)

	def test_every_field_is_a_base_only_the_annual_return_asks_for(self):
		catalogue = catalogue_for(YEAR)
		for element in {row[2] for row in ANNUAL_2026}:
			with self.subTest(field=element):
				field = catalogue.field(element)
				self.assertTrue(field.fed)
				self.assertIsNone(field.ustva)
				self.assertIs(field.format, Format.EUROS)

	def test_the_tax_of_each_base_comes_through_kz_69_by_the_role_of_its_account(self):
		catalogue = catalogue_for(YEAR)
		for chart in CHARTS:
			roles = role_defaults(chart, YEAR)
			for base, accounts in TAXES_OF_ANNUAL_BASES.items():
				with self.subTest(chart=chart, base=base):
					self.assertEqual(roles[accounts[COLUMNS[chart]]], catalogue.field(base).tax)

	def test_the_voranmeldung_leaves_each_account_without_kennzahl_or_watches_it(self):
		"""An account the mapping maps or checks as a tax account cannot be one only the annual return reads."""
		for chart, (mapping, _) in CHARTS.items():
			ignored = deliberately_without_kennzahl(chart)
			watched = {account.account_number for account in mapping.watched}
			for rule in annual_rules(chart, YEAR):
				with self.subTest(chart=chart, account=rule.account_number):
					self.assertIsNone(mapping.rule_for(rule.account_number))
					self.assertFalse(
						any(rule.account_number in check.tax_accounts for check in mapping.checks)
					)
					self.assertIn(rule.account_number, ignored | watched)

	def test_the_default_mappings_split_with_their_annual_rules(self):
		for chart in CHARTS:
			result = split(
				default_mapping(chart, YEAR), (), role_defaults(chart, YEAR), annual_rules(chart, YEAR)
			)
			for row in ANNUAL_2026:
				with self.subTest(chart=chart, account=row[COLUMNS[chart]]):
					assignment = result.assignment(row[COLUMNS[chart]])
					self.assertEqual(
						(assignment.field, assignment.how, assignment.side), (row[2], How.ANNUAL, row[3])
					)

	def test_the_sales_under_paragraphs_25_and_25a_stay_out(self):
		"""Lines 37 and 38 are not filed by Steuerbote (steuerbote/ustjahr/form.py, Scope.TRAVEL_AND_MARGIN)."""
		for chart, accounts in (("SKR03", ("8198", "8199")), ("SKR04", ("4133", "4134"))):
			with self.subTest(chart=chart):
				numbers = {rule.account_number for rule in annual_rules(chart, YEAR)} | set(
					role_defaults(chart, YEAR)
				)
				self.assertEqual(numbers & set(accounts), set())

	def test_a_chart_without_defaults_has_no_annual_rules(self):
		with self.assertRaisesRegex(
			KeyError, "no defaults of the annual return for chart 'Eigener Kontenrahmen'"
		):
			annual_rules("Eigener Kontenrahmen", YEAR)

	def test_a_year_without_its_form_has_no_annual_rules(self):
		with self.assertRaisesRegex(UnknownYearError, "Umsatzsteuererklärung 2027"):
			annual_rules("SKR04", YEAR + 1)


# The SHA-256 of the defaults of each version: the field of each account by its role and the accounts only the annual
# return reads, in canonical JSON. A change of the defaults fails here until REVISIONS rises and the digest of the new
# version is pinned, so that the same version always means the same defaults.
DIGESTS = {
	"SKR03 USt 2026.1": "bf04d4a6089509a40570b6a5d0215ded03afa1d422db1e6cb109ac356ca1bf1a",
	"SKR04 USt 2026.1": "979ea50de8f15eb5c74af3615119666337382acb0fa3d77b14684cf6a2f6fcb8",
}


def content(chart: str, year: int) -> str:
	return json.dumps(
		{
			"roles": dict(role_defaults(chart, year)),
			"annual_rules": [
				[rule.account_number, rule.field, rule.side.value] for rule in annual_rules(chart, year)
			],
		},
		sort_keys=True,
		separators=(",", ":"),
		ensure_ascii=False,
	)


class DefaultsVersionTest(TestCase):
	def test_the_version_names_the_chart_the_year_of_the_form_and_the_revision(self):
		self.assertEqual(dict(REVISIONS), {2026: 1})
		self.assertEqual(
			[defaults_version(chart, YEAR) for chart in CHARTS], ["SKR03 USt 2026.1", "SKR04 USt 2026.1"]
		)

	def test_a_version_always_means_the_same_defaults(self):
		for chart in CHARTS:
			with self.subTest(chart=chart):
				digest = hashlib.sha256(content(chart, YEAR).encode("utf-8")).hexdigest()
				self.assertEqual(
					digest,
					DIGESTS.get(defaults_version(chart, YEAR)),
					f"The defaults of {chart} for {YEAR} changed: raise REVISIONS[{YEAR}] in defaults.py and pin "
					"the digest of the new version in DIGESTS.",
				)

	def test_a_chart_without_defaults_has_no_version(self):
		with self.assertRaisesRegex(
			KeyError, "no defaults of the annual return for chart 'Eigener Kontenrahmen'"
		):
			defaults_version("Eigener Kontenrahmen", YEAR)

	def test_a_year_without_its_form_has_no_version(self):
		with self.assertRaisesRegex(UnknownYearError, "Umsatzsteuererklärung 2027"):
			defaults_version("SKR03", YEAR + 1)

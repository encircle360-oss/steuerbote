from decimal import Decimal
from unittest import TestCase

from steuerbote.ustva.calculation import LedgerLine, calculate
from steuerbote.ustva.defaults import (
	DEFAULTS,
	SKR03,
	SKR03_ACCOUNTS,
	SKR03_IGNORED,
	SKR03_RANGES,
	SKR03_WATCHED,
	SKR04,
	SKR04_ACCOUNTS,
	SKR04_IGNORED,
	SKR04_RANGES,
	SKR04_WATCHED,
	default_mapping,
	with_ranges,
)
from steuerbote.ustva.kennzahlen import LATEST_YEAR, UnknownYearError
from steuerbote.ustva.mapping import AccountRule, Side

CREDIT = Side.CREDIT
DEBIT = Side.DEBIT
R19 = Decimal("19")
R7 = Decimal("7")

# Every rule of the defaults by its first account: SKR03 account, SKR04 account (None: the chart has
# no such account), Kennzahl, side and the rate from which the tax Kennzahl is derived. The members
# of a DATEV range share the rule of its first account.
RULES = (
	# Kz 81, tax on "Umsatzsteuer 19 %"
	("8400", "4400", "81", CREDIT, None),
	("8410", "4410", "81", CREDIT, None),
	("8449", "4449", "81", CREDIT, None),
	("2752", "4862", "81", CREDIT, None),
	("8519", "4569", "81", CREDIT, None),
	("8640", "4836", "81", CREDIT, None),
	("8801", "6885", "81", CREDIT, None),
	("8820", "4845", "81", CREDIT, None),
	("8850", "4865", "81", CREDIT, None),
	("8595", "4945", "81", CREDIT, None),
	("8611", "4947", "81", CREDIT, None),
	("8613", "4948", "81", CREDIT, None),
	("8910", "4620", "81", CREDIT, None),
	("8920", "4640", "81", CREDIT, None),
	("8921", "4645", "81", CREDIT, None),
	("8922", "4646", "81", CREDIT, None),
	("8925", "4660", "81", CREDIT, None),
	("8935", "4686", "81", CREDIT, None),
	("8940", "4680", "81", CREDIT, None),
	("8720", "4720", "81", CREDIT, None),
	("8760", "4760", "81", CREDIT, None),
	("8790", "4790", "81", CREDIT, None),
	("8736", "4736", "81", CREDIT, None),
	("2406", "6936", "81", CREDIT, None),
	("2436", "6286", "81", CREDIT, None),
	("1718", "3272", "81", CREDIT, None),
	# numbers of earlier editions and of ERPNext's SKR04 template
	("8196", "4186", "81", CREDIT, None),
	("8579", "4579", "81", CREDIT, None),
	# Kz 81, tax on "Umsatzsteuer aus im Inland steuerpflichtigen EU-Lieferungen 19 %"
	("8315", "4315", "81", CREDIT, None),
	("8726", "4726", "81", CREDIT, None),
	("2408", "6938", "81", CREDIT, None),
	("8748", "4748", "81", CREDIT, None),
	# Kz 86, tax on "Umsatzsteuer 7 %"; SKR04 4835 is the twin of SKR03 8605, not of 8630
	("8300", "4300", "86", CREDIT, None),
	("8334", "4334", "86", CREDIT, None),
	("8630", None, "86", CREDIT, None),
	("8591", "4941", "86", CREDIT, None),
	("8915", "4610", "86", CREDIT, None),
	("8917", "4616", "86", CREDIT, None),
	("8930", "4630", "86", CREDIT, None),
	("8931", "4636", "86", CREDIT, None),
	("8932", "4650", "86", CREDIT, None),
	("8933", "4656", "86", CREDIT, None),
	("8945", "4670", "86", CREDIT, None),
	("8947", "4676", "86", CREDIT, None),
	("8710", "4710", "86", CREDIT, None),
	("8750", "4750", "86", CREDIT, None),
	("8780", "4780", "86", CREDIT, None),
	("8731", "4731", "86", CREDIT, None),
	("2401", "6931", "86", CREDIT, None),
	("2431", "6281", "86", CREDIT, None),
	("1711", "3260", "86", CREDIT, None),
	# numbers of earlier editions and of ERPNext's SKR04 template
	("8516", "4566", "86", CREDIT, None),
	("8576", "4576", "86", CREDIT, None),
	# Kz 86, tax on "Umsatzsteuer aus im Inland steuerpflichtigen EU-Lieferungen"
	("8310", "4310", "86", CREDIT, None),
	("8725", "4725", "86", CREDIT, None),
	("2403", "6933", "86", CREDIT, None),
	("8746", "4746", "86", CREDIT, None),
	# bases without tax
	("8290", "4290", "87", CREDIT, None),
	("8719", "4719", "87", CREDIT, None),
	("8734", "4734", "87", CREDIT, None),
	("1714", "3264", "87", CREDIT, None),
	("8100", "4100", "48", CREDIT, None),
	("8105", "4105", "48", CREDIT, None),
	("8160", "4160", "48", CREDIT, None),
	("8165", "4165", "48", CREDIT, None),
	("8192", "4184", "48", CREDIT, None),
	("2751", "4861", "48", CREDIT, None),
	("8514", "4564", "48", CREDIT, None),
	("8851", "4866", "48", CREDIT, None),
	("8701", "4701", "48", CREDIT, None),
	("8703", "4703", "48", CREDIT, None),
	("8707", "4707", "48", CREDIT, None),
	("8609", "4841", "48", CREDIT, None),
	("8852", "4867", "48", CREDIT, None),
	("8195", "4185", "48", CREDIT, None),
	("8574", "4574", "48", CREDIT, None),
	("8120", "4120", "43", CREDIT, None),
	("8140", "4140", "43", CREDIT, None),
	("8150", "4150", "43", CREDIT, None),
	("8807", "6884", "43", CREDIT, None),
	("8827", "4844", "43", CREDIT, None),
	("8515", "4565", "43", CREDIT, None),
	("8625", "4842", "43", CREDIT, None),
	("8702", "4702", "43", CREDIT, None),
	("8704", "4704", "43", CREDIT, None),
	("8705", "4705", "43", CREDIT, None),
	("8194", "4139", "43", CREDIT, None),
	("8575", "4575", "43", CREDIT, None),
	("8125", "4125", "41", CREDIT, None),
	("8808", "6888", "41", CREDIT, None),
	("8828", "4848", "41", CREDIT, None),
	("8724", "4724", "41", CREDIT, None),
	("2402", "6932", "41", CREDIT, None),
	("8743", "4743", "41", CREDIT, None),
	("8135", "4135", "44", CREDIT, None),
	("8130", "4130", "42", CREDIT, None),
	("8706", "4706", "42", CREDIT, None),
	("8338", "4338", "45", CREDIT, None),
	("8320", "4320", "45", CREDIT, None),
	("8339", "4339", "45", CREDIT, None),
	("8331", "4331", "45", CREDIT, None),
	("8727", "4727", "45", CREDIT, None),
	("8336", "4336", "21", CREDIT, None),
	("8742", "4742", "21", CREDIT, None),
	("8337", "4337", "60", CREDIT, None),
	("8335", "4335", "60", CREDIT, None),
	("8741", "4741", "60", CREDIT, None),
	("8738", "4738", "60", CREDIT, None),
	# innergemeinschaftliche Erwerbe
	("3425", "5425", "89", DEBIT, None),
	("3725", "5725", "89", DEBIT, None),
	("3718", "5718", "89", DEBIT, None),
	("3062", "5162", "89", DEBIT, None),
	("3741", "5741", "89", DEBIT, None),
	("3748", "5748", "89", DEBIT, None),
	("3420", "5420", "93", DEBIT, None),
	("3724", "5724", "93", DEBIT, None),
	("3717", "5717", "93", DEBIT, None),
	("3060", "5160", "93", DEBIT, None),
	("3743", "5743", "93", DEBIT, None),
	("3746", "5746", "93", DEBIT, None),
	("3435", "5435", "89", DEBIT, None),
	("3430", "5430", "93", DEBIT, None),
	("3066", "5166", "93", DEBIT, None),
	("3067", "5167", "89", DEBIT, None),
	("3440", "5440", "94", DEBIT, R19),
	("3550", "5550", "91", DEBIT, None),
	# § 13b UStG
	("3123", "5923", "46", DEBIT, R19),
	("3143", "5943", "46", DEBIT, R19),
	("3113", "5913", "46", DEBIT, R7),
	("3133", "5933", "46", DEBIT, R7),
	("3125", "5925", "84", DEBIT, R19),
	("3145", "5945", "84", DEBIT, R19),
	("3120", "5920", "84", DEBIT, R19),
	("3140", "5940", "84", DEBIT, R19),
	("3115", "5915", "84", DEBIT, R7),
	("3135", "5935", "84", DEBIT, R7),
	("3110", "5910", "84", DEBIT, R7),
	("3130", "5930", "84", DEBIT, R7),
	# Vorsteuer
	("1570", "1400", "66", DEBIT, None),
	("1576", "1406", "66", DEBIT, None),
	("1571", "1401", "66", DEBIT, None),
	("1573", "1436", "66", DEBIT, None),
	("1585", "1431", "66", DEBIT, None),
	("1574", "1404", "61", DEBIT, None),
	("1572", "1402", "61", DEBIT, None),
	("1584", "1432", "61", DEBIT, None),
	("1588", "1433", "62", DEBIT, None),
	("1577", "1407", "67", DEBIT, None),
	("1578", "1408", "67", DEBIT, None),
	("1587", "1484", "63", DEBIT, None),
	("1528", "1376", "64", DEBIT, None),
	("1529", "1377", "64", DEBIT, None),
	("1556", "1396", "64", DEBIT, None),
	("1557", "1397", "64", DEBIT, None),
	("1558", "1398", "64", DEBIT, None),
	("1559", "1399", "64", DEBIT, None),
	# other tax
	("1782", "3832", "65", CREDIT, None),
	("1783", "3851", "69", CREDIT, None),
	("1794", "3819", "69", CREDIT, None),
	(None, "3852", "69", CREDIT, None),
)

# Every check of the defaults by the first accounts of its bases: label, then base and tax accounts
# in SKR03 and in SKR04.
CHECKS = (
	(
		"Umsatzsteuer 19 %",
		(
			("8400", "8410", "8449", "2752", "8519", "8640", "8801", "8820", "8850", "8595", "8611", "8613"),
			("8910", "8920", "8921", "8922", "8925", "8935", "8940", "8720", "8760", "8790", "8736", "2406"),
			("2436", "1718", "8196", "8579"),
		),
		("1776",),
		(
			("4400", "4410", "4449", "4862", "4569", "4836", "6885", "4845", "4865", "4945", "4947", "4948"),
			("4620", "4640", "4645", "4646", "4660", "4686", "4680", "4720", "4760", "4790", "4736", "6936"),
			("6286", "3272", "4186", "4579"),
		),
		("3806",),
	),
	(
		"Umsatzsteuer aus im Inland steuerpflichtigen EU-Lieferungen 19 %",
		(("8315", "8726", "2408", "8748"),),
		("1778",),
		(("4315", "4726", "6938", "4748"),),
		("3808",),
	),
	(
		"Umsatzsteuer 7 %",
		(
			("8300", "8334", "8630", "8591", "8915", "8917", "8930", "8931", "8932", "8933", "8945", "8947"),
			("8710", "8750", "8780", "8731", "2401", "2431", "1711", "8516", "8576"),
		),
		("1771",),
		(
			("4300", "4334", "4941", "4610", "4616", "4630", "4636", "4650", "4656", "4670", "4676"),
			("4710", "4750", "4780", "4731", "6931", "6281", "3260", "4566", "4576"),
		),
		("3801",),
	),
	(
		"Umsatzsteuer aus im Inland steuerpflichtigen EU-Lieferungen 7 %",
		(("8310", "8725", "2403", "8746"),),
		("1777",),
		(("4310", "4725", "6933", "4746"),),
		("3807",),
	),
	(
		"Umsatzsteuer aus innergemeinschaftlichem Erwerb 19 %",
		(("3425", "3725", "3718", "3062", "3741", "3748"),),
		("1774",),
		(("5425", "5725", "5718", "5162", "5741", "5748"),),
		("3804",),
	),
	(
		"Umsatzsteuer aus innergemeinschaftlichem Erwerb 7 %",
		(("3420", "3724", "3717", "3060", "3743", "3746"),),
		("1772",),
		(("5420", "5724", "5717", "5160", "5743", "5746"),),
		("3802",),
	),
	(
		"Umsatzsteuer aus innergemeinschaftlichem Erwerb ohne Vorsteuerabzug",
		(("3430", "3435", "3066", "3067"),),
		("1779",),
		(("5430", "5435", "5166", "5167"),),
		("3809",),
	),
	(
		"Umsatzsteuer aus innergemeinschaftlichem Erwerb von Neufahrzeugen",
		(("3440",),),
		("1784",),
		(("5440",),),
		("3834",),
	),
	(
		"Umsatzsteuer nach § 13b UStG 19 %",
		(("3123", "3143", "3125", "3145", "3120", "3140"),),
		("1787",),
		(("5923", "5943", "5925", "5945", "5920", "5940"),),
		("3837",),
	),
	(
		"Umsatzsteuer nach § 13b UStG 7 %",
		(("3113", "3133", "3115", "3135", "3110", "3130"),),
		("1785",),
		(("5913", "5933", "5915", "5935", "5910", "5930"),),
		("3835",),
	),
)

# Watched accounts as twins; None where the account of the other chart is not watched.
WATCHED = (
	# a balance on these is a timing case the company resolves
	("1548", "1434"),
	("1725", "3865"),
	# Kennzahl not decided
	("1560", "1410"),
	("1561", "1411"),
	("1562", "1412"),
	("1563", "1413"),
	("1566", "1416"),
	("1567", "1417"),
	("1569", "1419"),
	("1712", "3261"),
	("1717", "3270"),
	("1760", "3810"),
	("1761", "3811"),
	("1762", "3812"),
	("1764", "3814"),
	("1766", "3816"),
	("1769", "3839"),
	("1770", "3800"),
	("3075", "5175"),
	("3076", "5176"),
	("3151", "5951"),
	("3154", "5954"),
	("3560", "5560"),
	("3565", "5565"),
	("8110", "4110"),
	("8190", "4180"),
	("8198", "4133"),
	("8199", "4134"),
	("8200", "4200"),
	("8340", "4340"),
	("8649", "4834"),
	("8708", "4708"),
	("8709", "4709"),
	# numbers of earlier editions; SKR04 from ERPNext's template
	("1716", "3271"),
	("2400", "6930"),
	("2430", "6280"),
	("3150", "5950"),
	("3153", "5953"),
	("3160", "5960"),
	("3165", "5965"),
	("3744", "5744"),
	("3745", "5745"),
	("8191", "4136"),
	("8193", "4138"),
	("8189", "4131"),
	("8197", "4132"),
	("8499", "4499"),
	("8510", "4560"),
	("8520", "4510"),
	("8540", "4520"),
	("8570", "4570"),
	("8590", "4940"),
	("8600", None),
	("8607", "4833"),
	("8610", "4946"),
	("8614", "4949"),
	("8700", "4700"),
	("8730", "4730"),
	("8745", "4745"),
	("8769", "4769"),
	("8770", "4770"),
	("8800", "6889"),
	("8817", "6890"),
	("8818", "6891"),
	("8819", "6892"),
	("8829", "4849"),
	("8837", "4850"),
	("8838", "4851"),
	("8839", "4852"),
	("8853", "4869"),
	("8900", "4600"),
	("8955", "4695"),
	# rates of 15 and 16 % in ERPNext's SKR04 template
	(None, "4330"),
	(None, "4723"),
	(None, "4729"),
	(None, "5726"),
	(None, "5727"),
	(None, "6285"),
	(None, "6287"),
	(None, "6934"),
	(None, "6935"),
	(None, "6937"),
	(None, "6939"),
)

# Accounts the defaults deliberately leave without Kennzahl, as twins.
IGNORED = (
	("1543", "1456"),
	("1593", "1495"),
	# OSS, declared to the Bundeszentralamt für Steuern
	("1728", "3798"),
	("1767", "3817"),
	("1768", "3818"),
	("1798", "3831"),
	("1729", None),
	# payments to and settlement with the Finanzamt
	("1780", "3820"),
	("1781", "3830"),
	("0985", "1930"),
	("1545", "1420"),
	("1789", None),
	("1790", None),
	("1791", None),
	("1797", None),
	# Einfuhrumsatzsteuer owed to customs; the deduction runs through 1588 and 1433
	("1788", "3850"),
	(None, "1421"),
	(None, "1422"),
	(None, "1425"),
	# Dreiecksgeschäft
	("3089", "5189"),
	("3552", "5552"),
	("3553", "5553"),
	("3792", "5792"),
	("3793", "5793"),
	# Vorsteuer of other countries
	("4902", "6302"),
	("8604", "4838"),
	# EÜR and settlement accounts
	("1371", "1486"),
	("1372", None),
	("1445", None),
	("1446", None),
	("1447", None),
	("1448", None),
	("1450", None),
	("1580", None),
	("1581", None),
	("1582", None),
	("1583", None),
	("1605", None),
	("1606", None),
	("1607", None),
	("1624", None),
	("1704", None),
	("1756", None),
	("1795", None),
	("8589", None),
	(None, "1427"),
	(None, "1460"),
	(None, "1490"),
	(None, "1491"),
	# non-deductible Vorsteuer
	("2170", None),
	("2171", None),
	("2176", None),
	("3600", "5600"),
	("3610", "5610"),
	("3660", "5660"),
	("4300", None),
	("4301", None),
	("4306", "6871"),
	# domestic purchases and prepayments made: only their Vorsteuer is reported
	("1511", "1181"),
	("1518", "1186"),
	("3010", "5110"),
	("3030", "5130"),
	("3070", "5170"),
	("3071", "5171"),
	("3091", "5191"),
	("3092", "5192"),
	("3106", "5906"),
	("3108", None),
	("3109", "5909"),
	("3300", "5300"),
	("3349", None),
	("3400", "5400"),
	("3505", "5505"),
	("3540", "5540"),
	("3710", "5710"),
	("3714", "5714"),
	("3715", "5715"),
	("3720", "5720"),
	("3730", "5730"),
	("3731", "5731"),
	("3733", "5733"),
	("3734", "5734"),
	("3736", "5736"),
	("3738", "5738"),
	("3750", "5750"),
	("3753", "5753"),
	("3754", "5754"),
	("3755", "5755"),
	("3760", "5760"),
	("3769", "5769"),
	("3770", "5770"),
	("3780", "5780"),
	("3783", "5783"),
	("3784", "5784"),
	("3785", "5785"),
	("3788", None),
	("3790", "5790"),
	("3794", None),
	("3796", None),
	("3798", None),
	("3558", "5558"),
	("3559", "5559"),
	(None, "1184"),
	(None, "1185"),
	(None, "5722"),
	(None, "5723"),
	# Wertabgaben and Sachbezüge without Umsatzsteuer, Innenumsätze
	("8905", "4605"),
	("8906", "4637"),
	("8918", "4638"),
	("8919", None),
	("8924", "4639"),
	("8929", "4659"),
	("8939", "4689"),
	("8949", "4679"),
	("8950", "4690"),
	# prepayments without automatic tax; the taxed ones are on 1711 to 1718
	("1710", "3250"),
	("1719", "3280"),
	("1720", "3284"),
	("1721", "3285"),
	("1722", "1190"),
	("1793", "3695"),
	# private and capital accounts of sole proprietors
	("1800", None),
	("1869", None),
	("1879", None),
	("1880", None),
	("1900", None),
	("1980", None),
	# interest, not marked as Umsatzsteuer by DATEV
	("8650", None),
	("8660", None),
)

# Roles a chart has no account for.
WITHOUT_ACCOUNT = {
	"SKR03": {"unduly_shown_tax_template"},
	"SKR04": {"other_income_7"},
}

# Bad debts report the reduction of a taxable base once more in Kz 50 (Anleitung zu Zeile 51).
BAD_DEBTS = {
	"SKR03": ("2401", "2406", "2431", "2436", "2403", "2408"),
	"SKR04": ("6931", "6936", "6281", "6286", "6933", "6938"),
}


def _expected(account: str, kennzahl: str, side: Side, rate: Decimal | None, chart: str) -> AccountRule:
	if account in BAD_DEBTS[chart]:
		return AccountRule(account, kennzahl, side, rate, "50", Side.DEBIT)
	return AccountRule(account, kennzahl, side, rate)


def _flat(groups: tuple[tuple[str, ...], ...]) -> tuple[str, ...]:
	return tuple(account for group in groups for account in group)


def _declared(rows: tuple[tuple[str | None, str | None], ...], column: int) -> list[str]:
	return sorted(row[column] for row in rows if row[column] is not None)


def _listed(accounts: tuple[str, ...]) -> list[str]:
	"""The accounts sorted, after checking that the list names none twice; the lists group by reason."""
	assert len(set(accounts)) == len(accounts), accounts
	return sorted(accounts)


class RangesTest(TestCase):
	def test_a_range_lists_its_first_account_and_every_member(self):
		self.assertEqual(with_ranges(("8400",), SKR03_RANGES), tuple(str(n) for n in range(8400, 8410)))
		self.assertEqual(
			with_ranges(("8100", "8105"), SKR03_RANGES), ("8100", "8101", "8102", "8103", "8104", "8105")
		)

	def test_an_account_without_range_stands_alone(self):
		self.assertEqual(with_ranges(("1776",), SKR03_RANGES), ("1776",))

	def test_members_keep_the_width_of_the_first_account(self):
		self.assertEqual(with_ranges(("0820",), {"0820": "0822"}), ("0820", "0821", "0822"))

	def test_members_share_the_place_of_their_first_account(self):
		for mapping, ranges, ignored in (
			(SKR03, SKR03_RANGES, SKR03_IGNORED),
			(SKR04, SKR04_RANGES, SKR04_IGNORED),
		):
			ignored_accounts = with_ranges(ignored, ranges)
			for start in ranges:
				for member in with_ranges((start,), ranges)[1:]:
					with self.subTest(chart=mapping.chart, member=member):
						rule, first = mapping.rule_for(member), mapping.rule_for(start)
						self.assertEqual(rule is None, first is None)
						if rule is not None and first is not None:
							self.assertEqual(
								(rule.kennzahl, rule.side, rule.tax_rate),
								(first.kennzahl, first.side, first.tax_rate),
							)
						for check in mapping.checks:
							self.assertEqual(member in check.base_accounts, start in check.base_accounts)
							self.assertEqual(member in check.tax_accounts, start in check.tax_accounts)
						self.assertEqual(member in mapping.watched, start in mapping.watched)
						self.assertEqual(member in ignored_accounts, start in ignored_accounts)


class RuleTest(TestCase):
	def test_every_skr03_rule(self):
		for skr03, _, kennzahl, side, rate in RULES:
			if skr03 is not None:
				with self.subTest(account=skr03):
					self.assertEqual(SKR03.rule_for(skr03), _expected(skr03, kennzahl, side, rate, "SKR03"))
		expected = with_ranges((row[0] for row in RULES if row[0] is not None), SKR03_RANGES)
		self.assertCountEqual([rule.account_number for rule in SKR03.rules], expected)

	def test_every_skr04_rule(self):
		for _, skr04, kennzahl, side, rate in RULES:
			if skr04 is not None:
				with self.subTest(account=skr04):
					self.assertEqual(SKR04.rule_for(skr04), _expected(skr04, kennzahl, side, rate, "SKR04"))
		expected = with_ranges((row[1] for row in RULES if row[1] is not None), SKR04_RANGES)
		self.assertCountEqual([rule.account_number for rule in SKR04.rules], expected)

	def test_rates_are_19_and_7_percent(self):
		rates = {rule.tax_rate for mapping in (SKR03, SKR04) for rule in mapping.rules}
		self.assertEqual(rates, {None, Decimal("19"), Decimal("7")})

	def test_bank_and_clearing_accounts_are_not_mapped(self):
		for account in ("1200", "1360", "1780", "1800", "4400"):
			self.assertIsNone(SKR03.rule_for(account), account)


class CheckTest(TestCase):
	def test_skr03_checks(self):
		expected = [
			(label, with_ranges(_flat(bases), SKR03_RANGES), taxes) for label, bases, taxes, _, _ in CHECKS
		]
		actual = [(check.label, check.base_accounts, check.tax_accounts) for check in SKR03.checks]
		self.assertEqual(actual, expected)

	def test_skr04_checks(self):
		expected = [
			(label, with_ranges(_flat(bases), SKR04_RANGES), taxes) for label, _, _, bases, taxes in CHECKS
		]
		actual = [(check.label, check.base_accounts, check.tax_accounts) for check in SKR04.checks]
		self.assertEqual(actual, expected)

	def test_checks_compare_the_credit_side_of_the_output_tax(self):
		for check in SKR03.checks + SKR04.checks:
			self.assertIs(check.side, Side.CREDIT, check.label)


class MirrorTest(TestCase):
	def test_both_charts_know_the_same_roles(self):
		self.assertEqual(set(SKR04_ACCOUNTS), set(SKR03_ACCOUNTS))
		for chart, accounts in (("SKR03", SKR03_ACCOUNTS), ("SKR04", SKR04_ACCOUNTS)):
			missing = {role for role, account in accounts.items() if account is None}
			self.assertEqual(missing, WITHOUT_ACCOUNT[chart], chart)

	def test_skr04_mirrors_the_rules_of_skr03_role_by_role(self):
		for role, skr03_account in SKR03_ACCOUNTS.items():
			skr04_account = SKR04_ACCOUNTS[role]
			if skr03_account is None or skr04_account is None:
				continue
			skr03_rule = SKR03.rule_for(skr03_account)
			skr04_rule = SKR04.rule_for(skr04_account)
			if skr03_rule is None:
				self.assertIsNone(skr04_rule, role)
			else:
				self.assertEqual(skr04_rule.kennzahl, skr03_rule.kennzahl, role)
				self.assertIs(skr04_rule.side, skr03_rule.side, role)
				self.assertEqual(skr04_rule.tax_rate, skr03_rule.tax_rate, role)

	def test_skr04_mirrors_the_checks_of_skr03_role_by_role(self):
		self.assertEqual([check.label for check in SKR04.checks], [check.label for check in SKR03.checks])
		for role, skr03_account in SKR03_ACCOUNTS.items():
			skr04_account = SKR04_ACCOUNTS[role]
			if skr03_account is None or skr04_account is None:
				continue
			for skr03_check, skr04_check in zip(SKR03.checks, SKR04.checks, strict=True):
				with self.subTest(role=role, check=skr03_check.label):
					self.assertEqual(
						skr04_account in skr04_check.base_accounts, skr03_account in skr03_check.base_accounts
					)
					self.assertEqual(
						skr04_account in skr04_check.tax_accounts, skr03_account in skr03_check.tax_accounts
					)


class WatchedTest(TestCase):
	def test_skr03_watched_accounts(self):
		self.assertEqual(_listed(SKR03_WATCHED), _declared(WATCHED, 0))
		self.assertEqual(SKR03.watched, with_ranges(SKR03_WATCHED, SKR03_RANGES))

	def test_skr04_watched_accounts(self):
		self.assertEqual(_listed(SKR04_WATCHED), _declared(WATCHED, 1))
		self.assertEqual(SKR04.watched, with_ranges(SKR04_WATCHED, SKR04_RANGES))


class IgnoredTest(TestCase):
	def test_skr03_ignored_accounts(self):
		self.assertEqual(_listed(SKR03_IGNORED), _declared(IGNORED, 0))

	def test_skr04_ignored_accounts(self):
		self.assertEqual(_listed(SKR04_IGNORED), _declared(IGNORED, 1))

	def test_ignored_accounts_are_not_part_of_the_mapping(self):
		for mapping, ignored, ranges in (
			(SKR03, SKR03_IGNORED, SKR03_RANGES),
			(SKR04, SKR04_IGNORED, SKR04_RANGES),
		):
			checked = {account for check in mapping.checks for account in check.tax_accounts}
			for account in with_ranges(ignored, ranges):
				with self.subTest(chart=mapping.chart, account=account):
					self.assertIsNone(mapping.rule_for(account))
					self.assertNotIn(account, checked)
					self.assertNotIn(account, mapping.watched)


class BadDebtTest(TestCase):
	"""Anleitung zu Zeile 51: „uneinbringlich geworden ist, tragen Sie die Minderung der Bemessungsgrundlage
	bitte zusätzlich in Zeile 51 ein“."""

	def test_a_bad_debt_reduces_kz_81_and_reports_the_reduction_in_kz_50(self):
		for mapping, bad_debt, output_tax, receivable in (
			(SKR03, "2406", "1776", "1400"),
			(SKR04, "6936", "3806", "1200"),
		):
			with self.subTest(chart=mapping.chart):
				result = calculate(
					[
						LedgerLine(bad_debt, debit=Decimal("1000")),
						LedgerLine(output_tax, debit=Decimal("190")),
						LedgerLine(receivable, credit=Decimal("1190")),
					],
					mapping,
				)
				self.assertEqual(result.reported("81"), Decimal("-1000"))
				self.assertEqual(result.reported("50"), Decimal("1000"))
				self.assertEqual(result.kz83, Decimal("-190.00"))
				self.assertTrue(result.ready)

	def test_the_bad_debt_rules_carry_kz_50_on_the_debit_side(self):
		for mapping in (SKR03, SKR04):
			with_also = {rule.account_number for rule in mapping.rules if rule.also_kennzahl is not None}
			self.assertEqual(with_also, set(BAD_DEBTS[mapping.chart]), mapping.chart)
			for account in BAD_DEBTS[mapping.chart]:
				rule = mapping.rule_for(account)
				self.assertEqual((rule.also_kennzahl, rule.also_side), ("50", Side.DEBIT), account)


class DefaultsTest(TestCase):
	def test_both_charts_are_offered(self):
		self.assertEqual(set(DEFAULTS), {"SKR03", "SKR04"})
		self.assertEqual(DEFAULTS["SKR03"].chart, "SKR03")
		self.assertEqual(DEFAULTS["SKR04"].chart, "SKR04")

	def test_defaults_are_read_only(self):
		with self.assertRaises(TypeError):
			DEFAULTS["SKR05"] = SKR03  # type: ignore[index]

	def test_defaults_are_built_for_the_latest_form(self):
		self.assertEqual(SKR03.year, LATEST_YEAR)
		self.assertEqual(SKR04.year, LATEST_YEAR)

	def test_default_mapping_by_chart_and_year(self):
		self.assertEqual(default_mapping("SKR03", LATEST_YEAR), SKR03)
		self.assertEqual(default_mapping("SKR04", 2026).year, 2026)
		with self.assertRaisesRegex(UnknownYearError, "2025"):
			default_mapping("SKR03", 2025)
		with self.assertRaisesRegex(
			KeyError, "no default mapping for chart 'SKR05'; known charts: SKR03, SKR04"
		):
			default_mapping("SKR05", 2026)

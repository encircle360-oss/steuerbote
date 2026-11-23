"""Defaults of the annual return for the DATEV standard charts SKR03 and SKR04, editions valid for 2026: the annual
field of an account by the role it plays in its chart, and the accounts only the annual return reads.

Sources: form USt 2 A 2026 and its Anleitung USt 2 E 2026, BMF letter of 29 December 2025 (GZ III C 3 - S
7344/00040/008/034), cited as USt 2 E; the DATEV-Kontenrahmen nach dem Bilanzrichtlinie-Umsetzungsgesetz,
Standardkontenrahmen SKR 03 (Art.-Nr. 11174) and SKR 04 (Art.-Nr. 11175), "Gültig für 2026", whose labels
docs/ustva-kennzahlen.md quotes; and the roles that steuerbote/ustva/defaults.py gives the accounts of both charts
for the Voranmeldung.

The Voranmeldung maps an account to a Kennzahl of form USt 1 A. The annual return splits some of them into several
lines, and split() takes the line of a mapped account from the annual field of its rule, then from the role of the
account, then from the default line of its Kennzahl (steuerbote/ustjahr/split.py). ROLE_FIELDS names, by the year of
the form, the line of each role whose line is not the default line of its Kennzahl, and of each role of Kz 64, which
has none:

- Unentgeltliche Wertabgaben: they are „in der Regel den entgeltlichen Lieferungen“ and „in der Regel den
  entgeltlichen sonstigen Leistungen gleichgestellt“ (USt 2 E, Zeilen 24 bis 33), so the Entnahme and the
  unentgeltliche Zuwendung of goods are Lieferungen nach § 3 Absatz 1b UStG (lines 25 and 28), the Verwendung of goods
  and the unentgeltliche Erbringung of a sonstige Leistung sonstige Leistungen nach § 3 Absatz 9a UStG (lines 26 and
  29). Sachbezüge stay in lines 24 and 27 with the other sales: whether the staff pays for one with its work or
  receives it free, which makes it a Wertabgabe, depends on the case and is unverified.
- Exempt sales with Vorsteuerabzug: „Bitte tragen Sie in Zeile 45 steuerfreie Ausfuhrlieferungen ein (§ 4 Nummer 1
  Buchstabe a, § 6 UStG)“, Umsätze im Sinne des Offshore-Steuerabkommens „(Zeile 47)“ and „Reiseleistungen, soweit die
  Reisevorleistungen im Drittlandsgebiet bewirkt werden (§ 25 Absatz 2 UStG) (Zeile 49)“ (USt 2 E, Zeile 45 and
  Zeilen 46 bis 50). The accounts of § 4 Nummer 1 Buchstabe a UStG hold the Lohnveredelungen of § 7 UStG as well,
  which belong to line 46: an account that holds them needs that annual field.
- Exempt sales without Vorsteuerabzug: line 51 takes „die steuerfreien Umsätze nach § 4 Nummer 12 UStG aus der
  Vermietung und Verpachtung von Grundstücken“, line 53 those of a Kleinunternehmer under § 19 Absatz 1 UStG, and line
  54 „die steuerfreien Umsätze ohne Vorsteuerabzug, die zum Gesamtumsatz nach § 19 Absatz 2 UStG gehören“ (USt 2 E,
  Zeilen 51 bis 52, Zeile 53 and Zeile 54), as the DATEV labels „zum Gesamtumsatz gehörend“ say. Every other exempt
  sale takes line 52, the default line of Kz 48.
- Vorsteuer: line 88 takes „die Umsatzsteuer, die der Unternehmer schuldet, dem die Auslagerung aus einem
  Umsatzsteuerlager zuzurechnen ist“, line 92 „bei innergemeinschaftlichen Dreiecksgeschäften ... die vom letzten
  Abnehmer nach § 25b Absatz 2 UStG geschuldete Umsatzsteuer“ (USt 2 E, Zeilen 85 bis 93).
- Berichtigung des Vorsteuerabzugs nach § 15a UStG, which goes into the line of its kind of asset: „Bei Grundstücken
  ... mit einem Berichtigungszeitraum von zehn Jahren“ line 105, „Bei übrigen sonstigen Leistungen und
  Wirtschaftsgütern, die nicht nur einmalig zur Ausführung von Umsätzen verwendet werden“ line 106, and „Bei
  Wirtschaftsgütern und sonstigen Leistungen, die nur einmalig zur Ausführung von Umsätzen verwendet worden sind“ line
  107 (USt 2 E, Zeilen 95 bis 108), each with a column for the nachträglich abziehbare and one for the
  zurückzuzahlende Vorsteuer. DATEV names them § 15a Absatz 1 UStG for unbewegliche and for bewegliche
  Wirtschaftsgüter and § 15a Absatz 2 UStG.
- Taxes Kz 69 holds: the tax „die der letzte Abnehmer nach § 25b Absatz 2 UStG für die Lieferung des ersten Abnehmers
  schuldet“ goes into line 66, at 19 % (USt 2 E, Zeilen 65 bis 70), and the tax the Auslagerer owes into line 63 (USt
  2 E, Zeile 63). The defaults of the Voranmeldung watch the account of the latter, SKR03 1769 and SKR04 3839, whose
  Kennzahl they leave open; once the company maps it to Kz 69, it takes line 63.

Accounts only the annual return reads. Some amounts are in no Kennzahl of the Voranmeldung
(steuerbote/ustjahr/form.py), so an account that holds one feeds its field directly with its balance, „Zuordnung nur
für die Umsatzsteuererklärung“ (AnnualRule in steuerbote/ustjahr/split.py). ANNUAL_ACCOUNTS names them by the year of
the form:

- Line 55 (Kz 789): „Bitte füllen Sie die Zeile 55 bei innergemeinschaftlichen Dreiecksgeschäften aus, wenn Sie der
  erste Abnehmer sind und Ihr Erwerb als besteuert gilt (§ 25b Absatz 3 UStG)“ (USt 2 E, Zeile 55): the account
  „Erwerb 1. Abnehmer innerhalb eines Dreiecksgeschäftes“. ERiC takes Kz 789 only together with Kz 742, the
  Lieferungen des ersten Abnehmers (rule 30013 of the Jahresdokumentation E50 2026).
- Line 66 (Kz 751): „Die Bemessungsgrundlage und die Steuer, die der letzte Abnehmer nach § 25b Absatz 2 UStG für die
  Lieferung des ersten Abnehmers schuldet, tragen Sie bitte in den Zeilen 66, 67 und 69 ein“ (USt 2 E, Zeilen 65 bis
  70): the Erwerb of raw materials and of goods „als letzter Abnehmer innerhalb Dreiecksgeschäft 19 %“ and their
  Skonti, which lower the base. Its tax comes through Kz 69 by the role of its account.
- Line 63 (Kz 852): „Tragen Sie bitte in Zeile 63 die Lieferungen ein, die den Auslagerungen von Gegenständen aus
  einem Umsatzsteuerlager vorangegangen sind. Die Umsatzsteuer für diese Umsätze schuldet der Unternehmer, dem die
  Auslagerung zuzurechnen ist (Auslagerer)“ (USt 2 E, Zeile 63): the purchases „aus einem USt-Lager § 13a UStG“ of
  raw materials and of goods at 7 and 19 %. Its tax comes through Kz 69 by the role of its account.

The defaults of the Voranmeldung leave the accounts of lines 55 and 66 without a Kennzahl and watch those of line 63,
so that none of them is mapped and its balance never counts twice (steuerbote/ustjahr/split.py). DATEV marks SKR04
5792 without „U“, unlike its twin SKR03 3792; both are read alike, since a Skonto lowers the base of line 66 either
way.

Out of these defaults stay the sales under §§ 25 and 25a UStG (SKR03 8198 and 8199, SKR04 4133 and 4134): lines 37
and 38, which Steuerbote does not file (Scope.TRAVEL_AND_MARGIN in steuerbote/ustjahr/form.py).

role_defaults() gives the annual field of each account of a chart by the role of the account and annual_rules() the
accounts only the annual return reads, members of their DATEV ranges included. A company with a chart of its own has
neither: its rules name their annual fields, and its rows for the annual return their accounts, themselves.

The defaults of a year have a version, the chart, „USt“ for the Datenart of the annual return, the year of the form and
the revision of the defaults, such as SKR03 USt 2026.1 (defaults_version()). Every change of the defaults of a year
raises its revision in REVISIONS, so that the same version always means the same defaults: test_defaults.py pins the
content of each version.
"""

from collections.abc import Mapping as ReadOnlyMapping
from types import MappingProxyType

from steuerbote.ustjahr.split import AnnualRule
from steuerbote.ustjahr.years import year_of
from steuerbote.ustva.defaults import SKR03_ACCOUNTS, SKR03_RANGES, SKR04_ACCOUNTS, SKR04_RANGES, with_ranges
from steuerbote.ustva.mapping import Side

# role: annual field of form USt 2 A 2026
_ROLE_FIELDS_2026 = {
	# Lieferungen nach § 3 Absatz 1b UStG zu 19 %, line 25 (Kz 178)
	"withdrawal_goods_19": "E3003405",
	"free_gift_assets_19": "E3003405",
	"free_gift_goods_19": "E3003405",
	# Sonstige Leistungen nach § 3 Absatz 9a UStG zu 19 %, line 26 (Kz 179)
	"private_use_19": "E3003505",
	"private_use_vehicle_19": "E3003505",
	"private_use_telephone_19": "E3003505",
	"free_service_19": "E3003505",
	# the same at 7 %: line 28 (Kz 195) and line 29 (Kz 196)
	"withdrawal_goods_7": "E3003703",
	"withdrawal_goods_7_other": "E3003703",
	"free_gift_goods_7": "E3003703",
	"free_gift_goods_7_other": "E3003703",
	"private_use_7": "E3003803",
	"private_use_7_other": "E3003803",
	"free_service_7": "E3003803",
	"free_service_7_other": "E3003803",
	# Ausfuhrlieferungen, line 45 (Kz 752); Offshore, line 47; Reiseleistungen nach § 25 Absatz 2 UStG, line 49
	"revenue_export": "E3103801",
	"asset_sale_loss_export": "E3103801",
	"asset_sale_gain_export": "E3103801",
	"revenue_reduction_export": "E3103801",
	"revenue_offshore": "E3104001",
	"travel_services_third_country": "E3104101",
	# § 4 Nummer 12 UStG, line 51 (Kz 286); § 19 Absatz 1 UStG, line 53 (Kz 236); zum Gesamtumsatz, line 54 (Kz 240)
	"revenue_exempt_rental": "E3104401",
	"rental_exempt": "E3104401",
	"revenue_small_business": "E3104701",
	"revenue_small_business_template": "E3104701",
	"revenue_reduction_small_business": "E3104701",
	"revenue_exempt_section_4": "E3104902",
	"revenue_exempt_without_input_tax": "E3104902",
	# Vorsteuer for the tax owed as Auslagerer, line 88 (Kz 466); from Dreiecksgeschäften, line 92 (Kz 760)
	"input_tax_tax_warehouse": "E3006503",
	"input_tax_triangular": "E3006801",
	# § 15a UStG: line 105 for Grundstücke, line 106 for other assets, line 107 for those used once; the first column
	# nachträglich abziehbar, the second zurückzuzahlen
	"input_tax_15a_1_immovable_deductible": "E3008701",
	"input_tax_15a_1_immovable_repayable": "E3008702",
	"input_tax_15a_1_movable_deductible": "E3008801",
	"input_tax_15a_1_movable_repayable": "E3008802",
	"input_tax_15a_2_deductible": "E3008803",
	"input_tax_15a_2_repayable": "E3008804",
	# the tax of the last buyer of a Dreiecksgeschäft at 19 %, line 66; the tax of the Auslagerer, line 63 (Kz 853)
	"output_tax_triangular": "E3101702",
	"output_tax_tax_warehouse": "E3102805",
}

ROLE_FIELDS: MappingProxyType[int, MappingProxyType[str, str]] = MappingProxyType(
	{2026: MappingProxyType(_ROLE_FIELDS_2026)}
)

# purpose, annual field of form USt 2 A 2026 and side of the balance of the accounts only the annual return reads
_ANNUAL_2026 = (
	# Erwerb des ersten Abnehmers in an innergemeinschaftliches Dreiecksgeschäft, line 55 (Kz 789)
	("acquisition_triangular_first_buyer", "E3100801", Side.DEBIT),
	# Erwerb als letzter Abnehmer in a Dreiecksgeschäft at 19 % and its Skonti, line 66 (Kz 751)
	("acquisition_triangular_last_buyer_materials_19", "E3101701", Side.DEBIT),
	("acquisition_triangular_last_buyer_goods_19", "E3101701", Side.DEBIT),
	("cash_discount_triangular_last_buyer_materials_19", "E3101701", Side.DEBIT),
	("cash_discount_triangular_last_buyer_goods_19", "E3101701", Side.DEBIT),
	# Einkauf aus einem Umsatzsteuerlager, the Lieferungen before the Auslagerung, line 63 (Kz 852)
	("purchase_tax_warehouse_materials_7", "E3102804", Side.DEBIT),
	("purchase_tax_warehouse_materials_19", "E3102804", Side.DEBIT),
	("purchase_tax_warehouse_goods_7", "E3102804", Side.DEBIT),
	("purchase_tax_warehouse_goods_19", "E3102804", Side.DEBIT),
)

ANNUAL_ACCOUNTS: MappingProxyType[int, tuple[tuple[str, str, Side], ...]] = MappingProxyType(
	{2026: _ANNUAL_2026}
)

REVISIONS: MappingProxyType[int, int] = MappingProxyType({2026: 1})

# The accounts of the roles the defaults of the Voranmeldung give no rule, and those of the purposes above.
SKR03_ANNUAL_ACCOUNTS = MappingProxyType(
	{
		"output_tax_tax_warehouse": "1769",
		"acquisition_triangular_first_buyer": "3552",
		"acquisition_triangular_last_buyer_materials_19": "3089",
		"acquisition_triangular_last_buyer_goods_19": "3553",
		"cash_discount_triangular_last_buyer_materials_19": "3792",
		"cash_discount_triangular_last_buyer_goods_19": "3793",
		"purchase_tax_warehouse_materials_7": "3075",
		"purchase_tax_warehouse_materials_19": "3076",
		"purchase_tax_warehouse_goods_7": "3560",
		"purchase_tax_warehouse_goods_19": "3565",
	}
)
SKR04_ANNUAL_ACCOUNTS = MappingProxyType(
	{
		"output_tax_tax_warehouse": "3839",
		"acquisition_triangular_first_buyer": "5552",
		"acquisition_triangular_last_buyer_materials_19": "5189",
		"acquisition_triangular_last_buyer_goods_19": "5553",
		"cash_discount_triangular_last_buyer_materials_19": "5792",
		"cash_discount_triangular_last_buyer_goods_19": "5793",
		"purchase_tax_warehouse_materials_7": "5175",
		"purchase_tax_warehouse_materials_19": "5176",
		"purchase_tax_warehouse_goods_7": "5560",
		"purchase_tax_warehouse_goods_19": "5565",
	}
)
_CHARTS = MappingProxyType(
	{
		"SKR03": (MappingProxyType({**SKR03_ACCOUNTS, **SKR03_ANNUAL_ACCOUNTS}), SKR03_RANGES),
		"SKR04": (MappingProxyType({**SKR04_ACCOUNTS, **SKR04_ANNUAL_ACCOUNTS}), SKR04_RANGES),
	}
)
CHARTS = frozenset(_CHARTS)
"""The charts with defaults of the annual return."""


def role_defaults(chart: str, year: int) -> ReadOnlyMapping[str, str]:
	"""The annual field of each account of the chart that the role of the account names, by account number."""
	accounts, ranges = _chart(chart)
	year_of(year)
	return MappingProxyType(
		{
			member: field
			for role, field in ROLE_FIELDS[year].items()
			if (number := accounts[role]) is not None
			for member in with_ranges((number,), ranges)
		}
	)


def annual_rules(chart: str, year: int) -> tuple[AnnualRule, ...]:
	"""The accounts of the chart only the annual return reads, each with the field it feeds and its side."""
	accounts, ranges = _chart(chart)
	year_of(year)
	return tuple(
		AnnualRule(member, field, side)
		for purpose, field, side in ANNUAL_ACCOUNTS[year]
		for member in with_ranges((accounts[purpose],), ranges)
	)


def defaults_version(chart: str, year: int) -> str:
	"""The version of the defaults of the chart for the year of the form, such as SKR03 USt 2026.1."""
	_chart(chart)
	year_of(year)
	return f"{chart} USt {year}.{REVISIONS[year]}"


def _chart(chart: str) -> tuple[ReadOnlyMapping[str, str | None], ReadOnlyMapping[str, str]]:
	try:
		return _CHARTS[chart]
	except KeyError:
		raise KeyError(
			f"no defaults of the annual return for chart {chart!r}; known charts: {', '.join(_CHARTS)}"
		) from None

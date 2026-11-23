"""Defaults of the annual return for the DATEV standard charts SKR03 and SKR04, editions valid for 2026: the annual
field of an account by the role it plays in its chart.

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
  29). Sachbezüge, which the staff pays for with its work, stay in line 24 and line 27 with the other sales.
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

role_defaults() gives the annual field of each account of a chart by the role of the account, members of its DATEV
range included. A company with a chart of its own has no roles: its rules name their annual fields themselves.
"""

from collections.abc import Mapping as ReadOnlyMapping
from types import MappingProxyType

from steuerbote.ustjahr.years import year_of
from steuerbote.ustva.defaults import SKR03_ACCOUNTS, SKR03_RANGES, SKR04_ACCOUNTS, SKR04_RANGES, with_ranges

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

# The accounts of the roles the defaults of the Voranmeldung give no rule, by chart.
_UNMAPPED_ROLES = MappingProxyType(
	{
		"SKR03": MappingProxyType({"output_tax_tax_warehouse": "1769"}),
		"SKR04": MappingProxyType({"output_tax_tax_warehouse": "3839"}),
	}
)
_CHARTS = MappingProxyType(
	{
		"SKR03": (MappingProxyType({**SKR03_ACCOUNTS, **_UNMAPPED_ROLES["SKR03"]}), SKR03_RANGES),
		"SKR04": (MappingProxyType({**SKR04_ACCOUNTS, **_UNMAPPED_ROLES["SKR04"]}), SKR04_RANGES),
	}
)


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


def _chart(chart: str) -> tuple[ReadOnlyMapping[str, str | None], ReadOnlyMapping[str, str]]:
	try:
		return _CHARTS[chart]
	except KeyError:
		raise KeyError(
			f"no defaults of the annual return for chart {chart!r}; known charts: {', '.join(_CHARTS)}"
		) from None

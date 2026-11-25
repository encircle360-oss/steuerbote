"""Default account mappings for the DATEV standard charts SKR03 and SKR04, editions valid for 2026.

Sources: DATEV-Kontenrahmen nach dem Bilanzrichtlinie-Umsetzungsgesetz, Standardkontenrahmen SKR 03
(Art.-Nr. 11174) and SKR 04 (Art.-Nr. 11175), "Gültig für 2026", and ERPNext's own SKR03 and SKR04
templates (de_kontenplan_SKR03.json and de_kontenplan_SKR04.json, version 16), whose accounts carry
DATEV numbers, some of them numbers that the editions for 2026 reserve or no longer use, and the
SKR03 numbers of charts in circulation (older DATEV editions and ERP templates). The Kennzahlen are
those of the Vordruck USt 1 A 2026 in kennzahlen.py.

Every account the DATEV chart hands to the Umsatzsteuer (marked "U", or an S/F tax account), every
VAT account of ERPNext's template and every such number in circulation has one place:

- Mapped: an account whose Kennzahl is unambiguous from its label feeds that Kennzahl. This includes
  the Vorsteuer accounts and the accounts for Kz 63, 65 and 69. A bad debt reduces a taxable base
  and reports the reduction once more in Kz 50.
- Checked: the output-tax account of a base is never mapped. The tax of a base is derived from the
  base account, at the statutory rate of its Kennzahl or at the rate the account carries for
  § 13b UStG and new vehicles, and the tax booked on the output-tax account is checked against it.
  The Verprobungen of the acquisitions and of § 13b UStG name the Kennzahl that takes the base of a
  voucher booking their tax without a base account (DERIVED), those of § 13b UStG another one for the
  services of a business established in another member state (DERIVED_EU).
- Watched: an account of the Voranmeldung whose Kennzahl is not decided yet. A balance on it blocks
  the filing until the company has added a mapping. An account whose balance belongs in the
  Voranmeldung in some cases only is watched at the hint level: a balance on it adds a hint.
- Ignored: an account that carries no Kennzahl at all, such as a payment to the Finanzamt or a
  domestic purchase whose Vorsteuer alone is reported. Ignored accounts are listed here for
  completeness and are not part of the Mapping.

A DATEV range such as 8400 to 8409 is one account purpose. The RANGES of a chart list them by first
and last account, and every member takes the place of the first account.

The accounts of the verified month in test_calculation.py are checked against real postings; all
other rules follow the account labels. The SKR04 mapping mirrors SKR03 role by role; a role a chart
has no account for maps to None and is left out.
"""

from collections.abc import Iterable
from collections.abc import Mapping as ReadOnlyMapping
from decimal import Decimal
from types import MappingProxyType

from steuerbote.ustva.mapping import AccountRule, Mapping, Side, TaxCheck, WatchedAccount, WatchLevel

RATE_19 = Decimal("19")
RATE_7 = Decimal("7")

# role, Kennzahl, side, rate of the derived tax
_RULES: tuple[tuple[str, str, Side, Decimal | None], ...] = (
	# Kz 81, tax booked on "Umsatzsteuer 19 %"
	("revenue_19", "81", Side.CREDIT, None),
	("revenue_19_other", "81", Side.CREDIT, None),
	("revenue_electronic_services_19", "81", Side.CREDIT, None),
	("rental_19", "81", Side.CREDIT, None),
	("commission_19", "81", Side.CREDIT, None),
	("other_income_19", "81", Side.CREDIT, None),
	("asset_sale_loss_19", "81", Side.CREDIT, None),
	("asset_sale_gain_19", "81", Side.CREDIT, None),
	("current_asset_sale_19", "81", Side.CREDIT, None),
	("benefit_in_kind_goods_19", "81", Side.CREDIT, None),
	("benefit_in_kind_vehicle_19", "81", Side.CREDIT, None),
	("benefit_in_kind_19", "81", Side.CREDIT, None),
	("withdrawal_goods_19", "81", Side.CREDIT, None),
	("private_use_19", "81", Side.CREDIT, None),
	("private_use_vehicle_19", "81", Side.CREDIT, None),
	("private_use_telephone_19", "81", Side.CREDIT, None),
	("free_service_19", "81", Side.CREDIT, None),
	("free_gift_assets_19", "81", Side.CREDIT, None),
	("free_gift_goods_19", "81", Side.CREDIT, None),
	("revenue_reduction_19", "81", Side.CREDIT, None),
	("bonus_19", "81", Side.CREDIT, None),
	("rebate_19", "81", Side.CREDIT, None),
	("cash_discount_19", "81", Side.CREDIT, None),
	("bad_debt_19", "81", Side.CREDIT, None),
	("bad_debt_unusual_19", "81", Side.CREDIT, None),
	("prepayment_received_19", "81", Side.CREDIT, None),
	("gaming_machines_19", "81", Side.CREDIT, None),
	("licence_income_19", "81", Side.CREDIT, None),
	# Kz 81, tax booked on "Umsatzsteuer aus im Inland steuerpflichtigen EU-Lieferungen 19 %"
	("revenue_eu_delivery_domestic_19", "81", Side.CREDIT, None),
	("revenue_reduction_eu_delivery_domestic_19", "81", Side.CREDIT, None),
	("bad_debt_eu_delivery_domestic_19", "81", Side.CREDIT, None),
	("cash_discount_eu_delivery_domestic_19", "81", Side.CREDIT, None),
	# Kz 86, tax booked on "Umsatzsteuer 7 %"
	("revenue_7", "86", Side.CREDIT, None),
	("revenue_7_other", "86", Side.CREDIT, None),
	("other_income_7", "86", Side.CREDIT, None),
	("benefit_in_kind_goods_7", "86", Side.CREDIT, None),
	("withdrawal_goods_7", "86", Side.CREDIT, None),
	("withdrawal_goods_7_other", "86", Side.CREDIT, None),
	("private_use_7", "86", Side.CREDIT, None),
	("private_use_7_other", "86", Side.CREDIT, None),
	("free_service_7", "86", Side.CREDIT, None),
	("free_service_7_other", "86", Side.CREDIT, None),
	("free_gift_goods_7", "86", Side.CREDIT, None),
	("free_gift_goods_7_other", "86", Side.CREDIT, None),
	("revenue_reduction_7", "86", Side.CREDIT, None),
	("bonus_7", "86", Side.CREDIT, None),
	("rebate_7", "86", Side.CREDIT, None),
	("cash_discount_7", "86", Side.CREDIT, None),
	("bad_debt_7", "86", Side.CREDIT, None),
	("bad_debt_unusual_7", "86", Side.CREDIT, None),
	("prepayment_received_7", "86", Side.CREDIT, None),
	("commission_7", "86", Side.CREDIT, None),
	("licence_income_7", "86", Side.CREDIT, None),
	# Kz 86, tax booked on "Umsatzsteuer aus im Inland steuerpflichtigen EU-Lieferungen"
	("revenue_eu_delivery_domestic_7", "86", Side.CREDIT, None),
	("revenue_reduction_eu_delivery_domestic_7", "86", Side.CREDIT, None),
	("bad_debt_eu_delivery_domestic_7", "86", Side.CREDIT, None),
	("cash_discount_eu_delivery_domestic_7", "86", Side.CREDIT, None),
	# Kz 87, taxable at 0 %
	("revenue_0", "87", Side.CREDIT, None),
	("revenue_reduction_0", "87", Side.CREDIT, None),
	("cash_discount_0", "87", Side.CREDIT, None),
	("prepayment_received_0", "87", Side.CREDIT, None),
	# Kz 48, exempt without Vorsteuerabzug
	("revenue_exempt", "48", Side.CREDIT, None),
	("revenue_exempt_rental", "48", Side.CREDIT, None),
	("revenue_exempt_section_4", "48", Side.CREDIT, None),
	("revenue_exempt_without_input_tax", "48", Side.CREDIT, None),
	("revenue_small_business", "48", Side.CREDIT, None),
	("rental_exempt", "48", Side.CREDIT, None),
	("commission_exempt", "48", Side.CREDIT, None),
	("current_asset_sale_exempt", "48", Side.CREDIT, None),
	("revenue_reduction_exempt", "48", Side.CREDIT, None),
	("revenue_reduction_exempt_without_input_tax", "48", Side.CREDIT, None),
	("revenue_reduction_small_business", "48", Side.CREDIT, None),
	("other_income_exempt", "48", Side.CREDIT, None),
	("current_asset_sale_exempt_partial_income", "48", Side.CREDIT, None),
	("revenue_small_business_template", "48", Side.CREDIT, None),
	("licence_income_exempt", "48", Side.CREDIT, None),
	# Kz 43, exempt with Vorsteuerabzug; travel services per Anleitung zu Zeile 22
	("revenue_export", "43", Side.CREDIT, None),
	("revenue_offshore", "43", Side.CREDIT, None),
	("revenue_exempt_with_input_tax", "43", Side.CREDIT, None),
	("asset_sale_loss_export", "43", Side.CREDIT, None),
	("asset_sale_gain_export", "43", Side.CREDIT, None),
	("commission_exempt_with_input_tax", "43", Side.CREDIT, None),
	("other_income_exempt_with_input_tax", "43", Side.CREDIT, None),
	("revenue_reduction_exempt_with_input_tax", "43", Side.CREDIT, None),
	("revenue_reduction_other_exempt_with_input_tax", "43", Side.CREDIT, None),
	("revenue_reduction_export", "43", Side.CREDIT, None),
	("travel_services_third_country", "43", Side.CREDIT, None),
	("licence_income_exempt_with_input_tax", "43", Side.CREDIT, None),
	# Kz 41, innergemeinschaftliche Lieferungen
	("revenue_eu_delivery", "41", Side.CREDIT, None),
	("asset_sale_loss_eu_delivery", "41", Side.CREDIT, None),
	("asset_sale_gain_eu_delivery", "41", Side.CREDIT, None),
	("revenue_reduction_eu_delivery", "41", Side.CREDIT, None),
	("bad_debt_eu_delivery", "41", Side.CREDIT, None),
	("cash_discount_eu_delivery", "41", Side.CREDIT, None),
	# Kz 44, 42, 45 (per Anleitung zu Zeile 36), 21 and 60
	("revenue_eu_delivery_new_vehicles", "44", Side.CREDIT, None),
	("revenue_triangular_first_buyer", "42", Side.CREDIT, None),
	("revenue_reduction_triangular", "42", Side.CREDIT, None),
	("revenue_third_country", "45", Side.CREDIT, None),
	("revenue_eu_distance_sales", "45", Side.CREDIT, None),
	("revenue_eu_not_taxable", "45", Side.CREDIT, None),
	("revenue_eu_electronic_services", "45", Side.CREDIT, None),
	("revenue_reduction_eu_distance_sales", "45", Side.CREDIT, None),
	("revenue_eu_service", "21", Side.CREDIT, None),
	("cash_discount_eu_service", "21", Side.CREDIT, None),
	("revenue_reverse_charge", "60", Side.CREDIT, None),
	("revenue_reverse_charge_devices", "60", Side.CREDIT, None),
	("cash_discount_reverse_charge", "60", Side.CREDIT, None),
	("cash_discount_reverse_charge_devices", "60", Side.CREDIT, None),
	# Kz 89 and 93, innergemeinschaftliche Erwerbe at the statutory rate
	("acquisition_19", "89", Side.DEBIT, None),
	("acquisition_reduction_19", "89", Side.DEBIT, None),
	("acquisition_materials_reduction_19", "89", Side.DEBIT, None),
	("acquisition_materials_19", "89", Side.DEBIT, None),
	("cash_discount_acquisition_materials_19", "89", Side.DEBIT, None),
	("cash_discount_acquisition_19", "89", Side.DEBIT, None),
	("acquisition_7", "93", Side.DEBIT, None),
	("acquisition_reduction_7", "93", Side.DEBIT, None),
	("acquisition_materials_reduction_7", "93", Side.DEBIT, None),
	("acquisition_materials_7", "93", Side.DEBIT, None),
	("cash_discount_acquisition_materials_7", "93", Side.DEBIT, None),
	("cash_discount_acquisition_7", "93", Side.DEBIT, None),
	("acquisition_without_input_tax_19", "89", Side.DEBIT, None),
	("acquisition_without_input_tax_7", "93", Side.DEBIT, None),
	("acquisition_materials_without_input_tax_7", "93", Side.DEBIT, None),
	("acquisition_materials_without_input_tax_19", "89", Side.DEBIT, None),
	# Kz 94 with its tax in Kz 96, and Kz 91
	("acquisition_new_vehicles", "94", Side.DEBIT, RATE_19),
	("acquisition_exempt", "91", Side.DEBIT, None),
	# Kz 46 with its tax in Kz 47, § 13b Absatz 1 UStG
	("eu_service_19", "46", Side.DEBIT, RATE_19),
	("eu_service_without_input_tax_19", "46", Side.DEBIT, RATE_19),
	("eu_service_7", "46", Side.DEBIT, RATE_7),
	("eu_service_without_input_tax_7", "46", Side.DEBIT, RATE_7),
	# Kz 84 with its tax in Kz 85, § 13b Absatz 2 UStG
	("foreign_service_19", "84", Side.DEBIT, RATE_19),
	("foreign_service_without_input_tax_19", "84", Side.DEBIT, RATE_19),
	("construction_19", "84", Side.DEBIT, RATE_19),
	("construction_without_input_tax_19", "84", Side.DEBIT, RATE_19),
	("foreign_service_7", "84", Side.DEBIT, RATE_7),
	("foreign_service_without_input_tax_7", "84", Side.DEBIT, RATE_7),
	("construction_7", "84", Side.DEBIT, RATE_7),
	("construction_without_input_tax_7", "84", Side.DEBIT, RATE_7),
	# Vorsteuer
	("input_tax", "66", Side.DEBIT, None),
	("input_tax_19", "66", Side.DEBIT, None),
	("input_tax_7", "66", Side.DEBIT, None),
	("input_tax_triangular", "66", Side.DEBIT, None),
	("input_tax_tax_warehouse", "66", Side.DEBIT, None),
	("input_tax_acquisition_19", "61", Side.DEBIT, None),
	("input_tax_acquisition", "61", Side.DEBIT, None),
	("input_tax_acquisition_new_vehicles", "61", Side.DEBIT, None),
	("import_tax", "62", Side.DEBIT, None),
	("input_tax_13b_19", "67", Side.DEBIT, None),
	("input_tax_13b", "67", Side.DEBIT, None),
	("input_tax_average_rates", "63", Side.DEBIT, None),
	# Kz 64, Berichtigung des Vorsteuerabzugs nach § 15a UStG
	("input_tax_15a_2_deductible", "64", Side.DEBIT, None),
	("input_tax_15a_2_repayable", "64", Side.DEBIT, None),
	("input_tax_15a_1_movable_deductible", "64", Side.DEBIT, None),
	("input_tax_15a_1_movable_repayable", "64", Side.DEBIT, None),
	("input_tax_15a_1_immovable_deductible", "64", Side.DEBIT, None),
	("input_tax_15a_1_immovable_repayable", "64", Side.DEBIT, None),
	# other tax
	("nachsteuer", "65", Side.CREDIT, None),
	("unduly_shown_tax", "69", Side.CREDIT, None),
	("output_tax_triangular", "69", Side.CREDIT, None),
	("unduly_shown_tax_template", "69", Side.CREDIT, None),
)

# Anleitung zu Zeile 51: "Erfolgt die Änderung nach § 17 Absatz 2 Nummer 1 Satz 1 UStG, weil das
# vereinbarte Entgelt für einen steuerpflichtigen Umsatz uneinbringlich geworden ist, tragen Sie die
# Minderung der Bemessungsgrundlage bitte zusätzlich in Zeile 51 ein." The debit balance of a bad debt
# is that reduction, reported in Kz 50.
_ALSO: dict[str, tuple[str, Side]] = dict.fromkeys(
	(
		"bad_debt_19",
		"bad_debt_unusual_19",
		"bad_debt_eu_delivery_domestic_19",
		"bad_debt_7",
		"bad_debt_unusual_7",
		"bad_debt_eu_delivery_domestic_7",
	),
	("50", Side.DEBIT),
)

# label, base roles, tax roles
_CHECKS: tuple[tuple[str, tuple[str, ...], tuple[str, ...]], ...] = (
	(
		"Umsatzsteuer 19 %",
		(
			"revenue_19",
			"revenue_19_other",
			"revenue_electronic_services_19",
			"rental_19",
			"commission_19",
			"other_income_19",
			"asset_sale_loss_19",
			"asset_sale_gain_19",
			"current_asset_sale_19",
			"benefit_in_kind_goods_19",
			"benefit_in_kind_vehicle_19",
			"benefit_in_kind_19",
			"withdrawal_goods_19",
			"private_use_19",
			"private_use_vehicle_19",
			"private_use_telephone_19",
			"free_service_19",
			"free_gift_assets_19",
			"free_gift_goods_19",
			"revenue_reduction_19",
			"bonus_19",
			"rebate_19",
			"cash_discount_19",
			"bad_debt_19",
			"bad_debt_unusual_19",
			"prepayment_received_19",
			"gaming_machines_19",
			"licence_income_19",
		),
		("output_tax_19",),
	),
	(
		"Umsatzsteuer aus im Inland steuerpflichtigen EU-Lieferungen 19 %",
		(
			"revenue_eu_delivery_domestic_19",
			"revenue_reduction_eu_delivery_domestic_19",
			"bad_debt_eu_delivery_domestic_19",
			"cash_discount_eu_delivery_domestic_19",
		),
		("output_tax_eu_delivery_domestic_19",),
	),
	(
		"Umsatzsteuer 7 %",
		(
			"revenue_7",
			"revenue_7_other",
			"other_income_7",
			"benefit_in_kind_goods_7",
			"withdrawal_goods_7",
			"withdrawal_goods_7_other",
			"private_use_7",
			"private_use_7_other",
			"free_service_7",
			"free_service_7_other",
			"free_gift_goods_7",
			"free_gift_goods_7_other",
			"revenue_reduction_7",
			"bonus_7",
			"rebate_7",
			"cash_discount_7",
			"bad_debt_7",
			"bad_debt_unusual_7",
			"prepayment_received_7",
			"commission_7",
			"licence_income_7",
		),
		("output_tax_7",),
	),
	(
		"Umsatzsteuer aus im Inland steuerpflichtigen EU-Lieferungen 7 %",
		(
			"revenue_eu_delivery_domestic_7",
			"revenue_reduction_eu_delivery_domestic_7",
			"bad_debt_eu_delivery_domestic_7",
			"cash_discount_eu_delivery_domestic_7",
		),
		("output_tax_eu_delivery_domestic_7",),
	),
	(
		"Umsatzsteuer aus innergemeinschaftlichem Erwerb 19 %",
		(
			"acquisition_19",
			"acquisition_reduction_19",
			"acquisition_materials_reduction_19",
			"acquisition_materials_19",
			"cash_discount_acquisition_materials_19",
			"cash_discount_acquisition_19",
		),
		("output_tax_acquisition_19",),
	),
	(
		"Umsatzsteuer aus innergemeinschaftlichem Erwerb 7 %",
		(
			"acquisition_7",
			"acquisition_reduction_7",
			"acquisition_materials_reduction_7",
			"acquisition_materials_7",
			"cash_discount_acquisition_materials_7",
			"cash_discount_acquisition_7",
		),
		("output_tax_acquisition",),
	),
	(
		"Umsatzsteuer aus innergemeinschaftlichem Erwerb ohne Vorsteuerabzug",
		(
			"acquisition_without_input_tax_7",
			"acquisition_without_input_tax_19",
			"acquisition_materials_without_input_tax_7",
			"acquisition_materials_without_input_tax_19",
		),
		("output_tax_acquisition_without_input_tax",),
	),
	(
		"Umsatzsteuer aus innergemeinschaftlichem Erwerb von Neufahrzeugen",
		("acquisition_new_vehicles",),
		("output_tax_acquisition_new_vehicles",),
	),
	(
		"Umsatzsteuer nach § 13b UStG 19 %",
		(
			"eu_service_19",
			"eu_service_without_input_tax_19",
			"foreign_service_19",
			"foreign_service_without_input_tax_19",
			"construction_19",
			"construction_without_input_tax_19",
		),
		("output_tax_13b_19",),
	),
	(
		"Umsatzsteuer nach § 13b UStG 7 %",
		(
			"eu_service_7",
			"eu_service_without_input_tax_7",
			"foreign_service_7",
			"foreign_service_without_input_tax_7",
			"construction_7",
			"construction_without_input_tax_7",
		),
		("output_tax_13b",),
	),
)


# The Kennzahl that takes the base of a voucher booking the tax of a Verprobung but none of its base accounts, as a
# DATEV tax key on an expense account or an ERPNext tax template does. Acquisitions go to the Kennzahl of their rate
# (§ 1a UStG, lines 25, 26 and 29). § 13b UStG goes to Kz 84, the Leistungen of § 13b Absatz 2 Nummer 1, 2 and 4 to 12
# UStG: Nummer 1 takes every Werklieferung and sonstige Leistung of a business established abroad that is no service of
# Absatz 1, and the other Nummern the domestic cases such as Bauleistungen. The acquisitions without Vorsteuerabzug
# book 7 and 19 % on one tax account, so their rate is open; turnover always has a revenue account of its own.
DERIVED: dict[str, str] = {
	"Umsatzsteuer aus innergemeinschaftlichem Erwerb 19 %": "89",
	"Umsatzsteuer aus innergemeinschaftlichem Erwerb 7 %": "93",
	"Umsatzsteuer aus innergemeinschaftlichem Erwerb von Neufahrzeugen": "94",
	"Umsatzsteuer nach § 13b UStG 19 %": "84",
	"Umsatzsteuer nach § 13b UStG 7 %": "84",
}
# The Kennzahl that takes such a base instead when its voucher is a sonstige Leistung of § 3a Absatz 2 UStG of a
# business established in another member state: Kz 46, line 30 (§ 13b Absatz 1 UStG). residence.py decides by what a
# person stated for the voucher, its supplier or its tax template, else by the country of the supplier; a voucher it
# cannot place stays in Kz 84 with a hint.
DERIVED_EU: dict[str, str] = {
	"Umsatzsteuer nach § 13b UStG 19 %": "46",
	"Umsatzsteuer nach § 13b UStG 7 %": "46",
}


def with_ranges(accounts: Iterable[str], ranges: ReadOnlyMapping[str, str]) -> tuple[str, ...]:
	"""The accounts, each followed by the members of the DATEV range it is the first account of."""
	return tuple(member for account in accounts for member in _members(account, ranges.get(account)))


def _members(first: str, last: str | None) -> tuple[str, ...]:
	if last is None:
		return (first,)
	return tuple(f"{number:0{len(first)}d}" for number in range(int(first), int(last) + 1))


def _mapping(
	chart: str,
	a: ReadOnlyMapping[str, str | None],
	watched: tuple[str, ...],
	watched_for_hints: tuple[str, ...],
	ranges: ReadOnlyMapping[str, str],
) -> Mapping:
	"""Build the mapping from a chart's account numbers, keyed by the role an account plays."""

	def numbers(roles: tuple[str, ...]) -> tuple[str, ...]:
		return with_ranges((number for role in roles if (number := a[role]) is not None), ranges)

	return Mapping(
		chart=chart,
		rules=tuple(
			AccountRule(member, kennzahl, side, rate, *_ALSO.get(role, (None, None)))
			for role, kennzahl, side, rate in _RULES
			if (number := a[role]) is not None
			for member in with_ranges((number,), ranges)
		),
		checks=tuple(
			TaxCheck(
				label,
				numbers(bases),
				numbers(taxes),
				derived_base=DERIVED.get(label),
				derived_base_eu=DERIVED_EU.get(label),
			)
			for label, bases, taxes in _CHECKS
		),
		watched=(
			*with_ranges(watched, ranges),
			*(WatchedAccount(number, WatchLevel.HINT) for number in with_ranges(watched_for_hints, ranges)),
		),
	)


# unduly_shown_tax_template has an account only in ERPNext's SKR04 template (3852).
SKR03_ACCOUNTS: dict[str, str | None] = {
	"revenue_19": "8400",
	"revenue_19_other": "8410",
	"revenue_electronic_services_19": "8449",
	"rental_19": "2752",
	"commission_19": "8519",
	"other_income_19": "8640",
	"asset_sale_loss_19": "8801",
	"asset_sale_gain_19": "8820",
	"current_asset_sale_19": "8850",
	"benefit_in_kind_goods_19": "8595",
	"benefit_in_kind_vehicle_19": "8611",
	"benefit_in_kind_19": "8613",
	"withdrawal_goods_19": "8910",
	"private_use_19": "8920",
	"private_use_vehicle_19": "8921",
	"private_use_telephone_19": "8922",
	"free_service_19": "8925",
	"free_gift_assets_19": "8935",
	"free_gift_goods_19": "8940",
	"revenue_reduction_19": "8720",
	"bonus_19": "8760",
	"rebate_19": "8790",
	"cash_discount_19": "8736",
	"bad_debt_19": "2406",
	"bad_debt_unusual_19": "2436",
	"prepayment_received_19": "1718",
	"gaming_machines_19": "8196",
	"licence_income_19": "8579",
	"revenue_eu_delivery_domestic_19": "8315",
	"revenue_reduction_eu_delivery_domestic_19": "8726",
	"bad_debt_eu_delivery_domestic_19": "2408",
	"cash_discount_eu_delivery_domestic_19": "8748",
	"revenue_7": "8300",
	"revenue_7_other": "8334",
	"other_income_7": "8630",
	"benefit_in_kind_goods_7": "8591",
	"withdrawal_goods_7": "8915",
	"withdrawal_goods_7_other": "8917",
	"private_use_7": "8930",
	"private_use_7_other": "8931",
	"free_service_7": "8932",
	"free_service_7_other": "8933",
	"free_gift_goods_7": "8945",
	"free_gift_goods_7_other": "8947",
	"revenue_reduction_7": "8710",
	"bonus_7": "8750",
	"rebate_7": "8780",
	"cash_discount_7": "8731",
	"bad_debt_7": "2401",
	"bad_debt_unusual_7": "2431",
	"prepayment_received_7": "1711",
	"commission_7": "8516",
	"licence_income_7": "8576",
	"revenue_eu_delivery_domestic_7": "8310",
	"revenue_reduction_eu_delivery_domestic_7": "8725",
	"bad_debt_eu_delivery_domestic_7": "2403",
	"cash_discount_eu_delivery_domestic_7": "8746",
	"revenue_0": "8290",
	"revenue_reduction_0": "8719",
	"cash_discount_0": "8734",
	"prepayment_received_0": "1714",
	"revenue_exempt": "8100",
	"revenue_exempt_rental": "8105",
	"revenue_exempt_section_4": "8160",
	"revenue_exempt_without_input_tax": "8165",
	"revenue_small_business": "8192",
	"rental_exempt": "2751",
	"commission_exempt": "8514",
	"current_asset_sale_exempt": "8851",
	"revenue_reduction_exempt": "8701",
	"revenue_reduction_exempt_without_input_tax": "8703",
	"revenue_reduction_small_business": "8707",
	"other_income_exempt": "8609",
	"current_asset_sale_exempt_partial_income": "8852",
	"revenue_small_business_template": "8195",
	"licence_income_exempt": "8574",
	"revenue_export": "8120",
	"revenue_offshore": "8140",
	"revenue_exempt_with_input_tax": "8150",
	"asset_sale_loss_export": "8807",
	"asset_sale_gain_export": "8827",
	"commission_exempt_with_input_tax": "8515",
	"other_income_exempt_with_input_tax": "8625",
	"revenue_reduction_exempt_with_input_tax": "8702",
	"revenue_reduction_other_exempt_with_input_tax": "8704",
	"revenue_reduction_export": "8705",
	"travel_services_third_country": "8194",
	"licence_income_exempt_with_input_tax": "8575",
	"revenue_eu_delivery": "8125",
	"asset_sale_loss_eu_delivery": "8808",
	"asset_sale_gain_eu_delivery": "8828",
	"revenue_reduction_eu_delivery": "8724",
	"bad_debt_eu_delivery": "2402",
	"cash_discount_eu_delivery": "8743",
	"revenue_eu_delivery_new_vehicles": "8135",
	"revenue_triangular_first_buyer": "8130",
	"revenue_reduction_triangular": "8706",
	"revenue_third_country": "8338",
	"revenue_eu_distance_sales": "8320",
	"revenue_eu_not_taxable": "8339",
	"revenue_eu_electronic_services": "8331",
	"revenue_reduction_eu_distance_sales": "8727",
	"revenue_eu_service": "8336",
	"cash_discount_eu_service": "8742",
	"revenue_reverse_charge": "8337",
	"revenue_reverse_charge_devices": "8335",
	"cash_discount_reverse_charge": "8741",
	"cash_discount_reverse_charge_devices": "8738",
	"acquisition_19": "3425",
	"acquisition_reduction_19": "3725",
	"acquisition_materials_reduction_19": "3718",
	"acquisition_materials_19": "3062",
	"cash_discount_acquisition_materials_19": "3741",
	"cash_discount_acquisition_19": "3748",
	"acquisition_7": "3420",
	"acquisition_reduction_7": "3724",
	"acquisition_materials_reduction_7": "3717",
	"acquisition_materials_7": "3060",
	"cash_discount_acquisition_materials_7": "3743",
	"cash_discount_acquisition_7": "3746",
	"acquisition_without_input_tax_19": "3435",
	"acquisition_without_input_tax_7": "3430",
	"acquisition_materials_without_input_tax_7": "3066",
	"acquisition_materials_without_input_tax_19": "3067",
	"acquisition_new_vehicles": "3440",
	"acquisition_exempt": "3550",
	"eu_service_19": "3123",
	"eu_service_without_input_tax_19": "3143",
	"eu_service_7": "3113",
	"eu_service_without_input_tax_7": "3133",
	"foreign_service_19": "3125",
	"foreign_service_without_input_tax_19": "3145",
	"construction_19": "3120",
	"construction_without_input_tax_19": "3140",
	"foreign_service_7": "3115",
	"foreign_service_without_input_tax_7": "3135",
	"construction_7": "3110",
	"construction_without_input_tax_7": "3130",
	"input_tax": "1570",
	"input_tax_19": "1576",
	"input_tax_7": "1571",
	"input_tax_triangular": "1573",
	"input_tax_tax_warehouse": "1585",
	"input_tax_acquisition_19": "1574",
	"input_tax_acquisition": "1572",
	"input_tax_acquisition_new_vehicles": "1584",
	"import_tax": "1588",
	"input_tax_13b_19": "1577",
	"input_tax_13b": "1578",
	"input_tax_average_rates": "1587",
	"input_tax_15a_2_deductible": "1528",
	"input_tax_15a_2_repayable": "1529",
	"input_tax_15a_1_movable_deductible": "1556",
	"input_tax_15a_1_movable_repayable": "1557",
	"input_tax_15a_1_immovable_deductible": "1558",
	"input_tax_15a_1_immovable_repayable": "1559",
	"nachsteuer": "1782",
	"unduly_shown_tax": "1783",
	"output_tax_triangular": "1794",
	"unduly_shown_tax_template": None,
	"output_tax_19": "1776",
	"output_tax_eu_delivery_domestic_19": "1778",
	"output_tax_7": "1771",
	"output_tax_eu_delivery_domestic_7": "1777",
	"output_tax_acquisition_19": "1774",
	"output_tax_acquisition": "1772",
	"output_tax_acquisition_without_input_tax": "1779",
	"output_tax_acquisition_new_vehicles": "1784",
	"output_tax_13b_19": "1787",
	"output_tax_13b": "1785",
}

# The ranges of the chart that start at an account with a place here, first: last account.
SKR03_RANGES: dict[str, str] = {
	"3010": "3019",
	"3030": "3039",
	"3062": "3063",
	"3120": "3121",
	"3125": "3126",
	"3140": "3141",
	"3145": "3146",
	"3300": "3309",
	"3400": "3409",
	"3420": "3424",
	"3425": "3429",
	"3505": "3509",
	"3540": "3549",
	"3600": "3609",
	"3610": "3619",
	"3660": "3669",
	"3710": "3711",
	"3720": "3721",
	"3750": "3751",
	"3760": "3761",
	"3780": "3781",
	"3790": "3791",
	"8100": "8104",
	"8300": "8309",
	"8310": "8314",
	"8315": "8319",
	"8320": "8329",
	"8340": "8349",
	"8400": "8409",
	"8410": "8419",
	"8625": "8629",
	"8630": "8634",
	"8640": "8644",
	"8710": "8711",
	"8720": "8721",
	"8750": "8751",
	"8760": "8761",
	"8780": "8781",
	"8790": "8791",
	"8801": "8806",
	"8820": "8825",
	"8910": "8913",
	"8915": "8916",
	"8925": "8927",
	"8935": "8937",
	"8940": "8943",
	"8945": "8946",
}

# Accounts of the Voranmeldung whose Kennzahl is not decided: Vorsteuer still to be split,
# Umsatzsteuer without rate, not yet due or on removal from a tax warehouse, prepayments at 5 and 16 %
# and revenue at 16 %, revenue under §§ 24, 25 and 25a UStG, other exempt or unspecified revenue,
# purchases from a tax warehouse and Skonti under § 13b UStG.
SKR03_WATCHED = (
	"1548",  # a balance is a timing case: Vorsteuer deductible in a later period
	"1725",  # a balance is a timing case: Umsatzsteuer due in a later period
	"1560",
	"1561",
	"1562",
	"1563",
	"1566",
	"1567",
	"1569",
	"1712",
	"1717",
	"1760",
	"1761",
	"1762",
	"1764",
	"1766",
	"1769",
	"1770",
	"3075",
	"3076",
	"3151",
	"3154",
	"3560",
	"3565",
	"8110",
	"8190",
	"8198",
	"8199",
	"8189",
	"8197",
	"8200",
	"8340",
	"8649",
	"8708",
	"8709",
	# numbers of charts in circulation whose label names no rate or case
	"1716",
	"2400",
	"2430",
	"3150",
	"3153",
	"3160",
	"3165",
	"3744",
	"3745",
	"8191",
	"8193",
	"8499",
	"8510",
	"8520",
	"8540",
	"8570",
	"8590",
	"8600",
	"8607",
	"8610",
	"8614",
	"8700",
	"8730",
	"8745",
	"8769",
	"8770",
	"8800",
	"8817",
	"8818",
	"8819",
	"8829",
	"8837",
	"8838",
	"8839",
	"8853",
	"8900",
	"8955",
)

# Other operating income that the chart gives the Zusatzfunktion "Umsatzsteuer" without marking it "U":
# above class 8 it prints "M 8194-8603" and "M 8605-8613" and explains "M Zusatzfunktion „Umsatzsteuer“".
# Taxable turnover booked on them with its tax shows in the Verprobung, since the tax lands on 1776 or 1771
# without a base; tax-free turnover does not, so a balance on them adds a hint.
SKR03_WATCHED_FOR_HINTS = (
	"8603",
	"8605",
	"8606",
)

# The chart, ERPNext's template or a chart in circulation hands these to the Umsatzsteuer, but the
# Voranmeldung has no Kennzahl for them.
SKR03_IGNORED = (
	"1543",  # Bauabzugsbetrag (§ 48 EStG), not Umsatzsteuer
	"1593",  # clearing account for prepayments received; the taxed ones are on 1711 to 1718
	"1390",  # clearing account for the Ist-Versteuerung, F in the chart like its twin SKR04 1490
	# OSS: this Umsatzsteuer is declared to the Bundeszentralamt für Steuern, not in the Voranmeldung
	"1728",
	"1767",
	"1768",
	"1798",
	"1780",  # Vorauszahlungen paid to the Finanzamt
	"1781",  # Sondervorauszahlung paid; it enters Kz 39 through extra_values
	# Dreiecksgeschäft, whose base is not reported: the acquisition of the first buyer (3552) counts
	# as taxed (§ 25b Abs. 3 UStG), the tax of the last buyer is on 1794 (Kz 69) and his Vorsteuer
	# on 1573 (Kz 66)
	"3089",
	"3552",
	"3553",
	"3792",
	"3793",
	"0985",  # Umsatzsteuer on prepayments, deferred in the balance sheet
	# settlement with the Finanzamt
	"1545",
	"1789",
	"1790",
	"1791",
	"1797",
	"1788",  # Einfuhrumsatzsteuer owed to customs; the deduction runs through 1588 into Kz 62
	"1729",  # OSS, not part of the Voranmeldung
	# Vorsteuervergütung of other countries
	"4902",
	"8604",
	# EÜR accounts
	"1371",
	"1372",
	"1445",
	"1446",
	"1447",
	"1448",
	"1450",
	"1580",
	"1581",
	"1582",
	"1583",
	"1605",
	"1606",
	"1607",
	"1624",
	"1704",
	"1756",
	"1795",
	"8589",
	# non-deductible Vorsteuer
	"2170",
	"2171",
	"2176",
	"3600",
	"3610",
	"3660",
	"4300",
	"4301",
	"4306",
	# domestic purchases without Vorsteuer: no Kennzahl at all
	"3109",
	"3349",
	# domestic purchases: the base has no Kennzahl, the Vorsteuer goes through 1576, 1571 and 1570
	"1511",
	"1518",
	"3010",
	"3030",
	"3070",
	"3071",
	"3091",
	"3092",
	"3106",
	"3108",
	"3300",
	"3400",
	"3505",
	"3540",
	"3710",
	"3714",
	"3715",
	"3720",
	"3730",
	"3731",
	"3733",
	"3734",
	"3736",
	"3738",
	"3750",
	"3753",
	"3754",
	"3755",
	"3760",
	"3769",
	"3770",
	"3780",
	"3783",
	"3784",
	"3785",
	"3788",
	"3790",
	"3794",
	"3796",
	"3798",  # Skonti 5,5 % in earlier editions; not the OSS account 3798 of SKR04
	# Wareneingang taxable in a third country: a supply made outside the Inland is not taxable here
	# (§ 1 Abs. 1 Nr. 1 UStG), and the Einfuhrumsatzsteuer of an import is deducted through 1588 in Kz 62.
	# 3557 is a number in circulation; the chart for 2026 reserves 3554 to 3557 (R 3554-57).
	"3551",
	"3557",
	"3558",  # Wareneingang taxable in another EU country
	"3559",  # tax-free imports
	# Wertabgaben without Umsatzsteuer, not taxable (§ 3 Abs. 1b Satz 2 UStG)
	"8905",
	"8906",
	"8918",
	"8919",
	"8924",
	"8929",
	"8939",
	"8949",
	"8950",  # Innenumsätze, not taxable
	# prepayments without automatic tax; the taxed ones are on 1711, 1714 and 1718
	"1710",
	"1719",
	"1720",
	"1721",
	"1722",
	"1793",
	# private and capital accounts of sole proprietors
	"1800",
	"1880",
	"1869",
	"1879",
	# accounts of partners (Teilhafter)
	"1900",
	"1980",
	# not marked as Umsatzsteuer by DATEV; interest income is on 2650
	"8650",
	"8660",
)

SKR04_ACCOUNTS: dict[str, str | None] = {
	"revenue_19": "4400",
	"revenue_19_other": "4410",
	"revenue_electronic_services_19": "4449",
	"rental_19": "4862",
	"commission_19": "4569",
	"other_income_19": "4836",
	"asset_sale_loss_19": "6885",
	"asset_sale_gain_19": "4845",
	"current_asset_sale_19": "4865",
	"benefit_in_kind_goods_19": "4945",
	"benefit_in_kind_vehicle_19": "4947",
	"benefit_in_kind_19": "4948",
	"withdrawal_goods_19": "4620",
	"private_use_19": "4640",
	"private_use_vehicle_19": "4645",
	"private_use_telephone_19": "4646",
	"free_service_19": "4660",
	"free_gift_assets_19": "4686",
	"free_gift_goods_19": "4680",
	"revenue_reduction_19": "4720",
	"bonus_19": "4760",
	"rebate_19": "4790",
	"cash_discount_19": "4736",
	"bad_debt_19": "6936",
	"bad_debt_unusual_19": "6286",
	"prepayment_received_19": "3272",
	"gaming_machines_19": "4186",
	"licence_income_19": "4579",
	"revenue_eu_delivery_domestic_19": "4315",
	"revenue_reduction_eu_delivery_domestic_19": "4726",
	"bad_debt_eu_delivery_domestic_19": "6938",
	"cash_discount_eu_delivery_domestic_19": "4748",
	"revenue_7": "4300",
	"revenue_7_other": "4334",
	# SKR04 has no account for regular other income at 7 %
	"other_income_7": None,
	"benefit_in_kind_goods_7": "4941",
	"withdrawal_goods_7": "4610",
	"withdrawal_goods_7_other": "4616",
	"private_use_7": "4630",
	"private_use_7_other": "4636",
	"free_service_7": "4650",
	"free_service_7_other": "4656",
	"free_gift_goods_7": "4670",
	"free_gift_goods_7_other": "4676",
	"revenue_reduction_7": "4710",
	"bonus_7": "4750",
	"rebate_7": "4780",
	"cash_discount_7": "4731",
	"bad_debt_7": "6931",
	"bad_debt_unusual_7": "6281",
	"prepayment_received_7": "3260",
	"commission_7": "4566",
	"licence_income_7": "4576",
	"revenue_eu_delivery_domestic_7": "4310",
	"revenue_reduction_eu_delivery_domestic_7": "4725",
	"bad_debt_eu_delivery_domestic_7": "6933",
	"cash_discount_eu_delivery_domestic_7": "4746",
	"revenue_0": "4290",
	"revenue_reduction_0": "4719",
	"cash_discount_0": "4734",
	"prepayment_received_0": "3264",
	"revenue_exempt": "4100",
	"revenue_exempt_rental": "4105",
	"revenue_exempt_section_4": "4160",
	"revenue_exempt_without_input_tax": "4165",
	"revenue_small_business": "4184",
	"rental_exempt": "4861",
	"commission_exempt": "4564",
	"current_asset_sale_exempt": "4866",
	"revenue_reduction_exempt": "4701",
	"revenue_reduction_exempt_without_input_tax": "4703",
	"revenue_reduction_small_business": "4707",
	"other_income_exempt": "4841",
	"current_asset_sale_exempt_partial_income": "4867",
	"revenue_small_business_template": "4185",
	"licence_income_exempt": "4574",
	"revenue_export": "4120",
	"revenue_offshore": "4140",
	"revenue_exempt_with_input_tax": "4150",
	"asset_sale_loss_export": "6884",
	"asset_sale_gain_export": "4844",
	"commission_exempt_with_input_tax": "4565",
	"other_income_exempt_with_input_tax": "4842",
	"revenue_reduction_exempt_with_input_tax": "4702",
	"revenue_reduction_other_exempt_with_input_tax": "4704",
	"revenue_reduction_export": "4705",
	"travel_services_third_country": "4139",
	"licence_income_exempt_with_input_tax": "4575",
	"revenue_eu_delivery": "4125",
	"asset_sale_loss_eu_delivery": "6888",
	"asset_sale_gain_eu_delivery": "4848",
	"revenue_reduction_eu_delivery": "4724",
	"bad_debt_eu_delivery": "6932",
	"cash_discount_eu_delivery": "4743",
	"revenue_eu_delivery_new_vehicles": "4135",
	"revenue_triangular_first_buyer": "4130",
	"revenue_reduction_triangular": "4706",
	"revenue_third_country": "4338",
	"revenue_eu_distance_sales": "4320",
	"revenue_eu_not_taxable": "4339",
	"revenue_eu_electronic_services": "4331",
	"revenue_reduction_eu_distance_sales": "4727",
	"revenue_eu_service": "4336",
	"cash_discount_eu_service": "4742",
	"revenue_reverse_charge": "4337",
	"revenue_reverse_charge_devices": "4335",
	"cash_discount_reverse_charge": "4741",
	"cash_discount_reverse_charge_devices": "4738",
	"acquisition_19": "5425",
	"acquisition_reduction_19": "5725",
	"acquisition_materials_reduction_19": "5718",
	"acquisition_materials_19": "5162",
	"cash_discount_acquisition_materials_19": "5741",
	"cash_discount_acquisition_19": "5748",
	"acquisition_7": "5420",
	"acquisition_reduction_7": "5724",
	"acquisition_materials_reduction_7": "5717",
	"acquisition_materials_7": "5160",
	"cash_discount_acquisition_materials_7": "5743",
	"cash_discount_acquisition_7": "5746",
	"acquisition_without_input_tax_19": "5435",
	"acquisition_without_input_tax_7": "5430",
	"acquisition_materials_without_input_tax_7": "5166",
	"acquisition_materials_without_input_tax_19": "5167",
	"acquisition_new_vehicles": "5440",
	"acquisition_exempt": "5550",
	"eu_service_19": "5923",
	"eu_service_without_input_tax_19": "5943",
	"eu_service_7": "5913",
	"eu_service_without_input_tax_7": "5933",
	"foreign_service_19": "5925",
	"foreign_service_without_input_tax_19": "5945",
	"construction_19": "5920",
	"construction_without_input_tax_19": "5940",
	"foreign_service_7": "5915",
	"foreign_service_without_input_tax_7": "5935",
	"construction_7": "5910",
	"construction_without_input_tax_7": "5930",
	"input_tax": "1400",
	"input_tax_19": "1406",
	"input_tax_7": "1401",
	"input_tax_triangular": "1436",
	"input_tax_tax_warehouse": "1431",
	"input_tax_acquisition_19": "1404",
	"input_tax_acquisition": "1402",
	"input_tax_acquisition_new_vehicles": "1432",
	"import_tax": "1433",
	"input_tax_13b_19": "1407",
	"input_tax_13b": "1408",
	"input_tax_average_rates": "1484",
	"input_tax_15a_2_deductible": "1376",
	"input_tax_15a_2_repayable": "1377",
	"input_tax_15a_1_movable_deductible": "1396",
	"input_tax_15a_1_movable_repayable": "1397",
	"input_tax_15a_1_immovable_deductible": "1398",
	"input_tax_15a_1_immovable_repayable": "1399",
	"nachsteuer": "3832",
	"unduly_shown_tax": "3851",
	"output_tax_triangular": "3819",
	"unduly_shown_tax_template": "3852",
	"output_tax_19": "3806",
	"output_tax_eu_delivery_domestic_19": "3808",
	"output_tax_7": "3801",
	"output_tax_eu_delivery_domestic_7": "3807",
	"output_tax_acquisition_19": "3804",
	"output_tax_acquisition": "3802",
	"output_tax_acquisition_without_input_tax": "3809",
	"output_tax_acquisition_new_vehicles": "3834",
	"output_tax_13b_19": "3837",
	"output_tax_13b": "3835",
}

# The ranges of the chart that start at an account with a place here, first: last account.
SKR04_RANGES: dict[str, str] = {
	"4100": "4104",
	"4300": "4309",
	"4310": "4314",
	"4315": "4319",
	"4320": "4329",
	"4340": "4349",
	"4400": "4409",
	"4410": "4419",
	"4610": "4615",
	"4620": "4626",
	"4630": "4635",
	"4640": "4644",
	"4650": "4655",
	"4660": "4666",
	"4670": "4675",
	"4680": "4684",
	"4686": "4687",
	"4710": "4711",
	"4720": "4721",
	"4750": "4751",
	"4760": "4761",
	"4780": "4781",
	"4790": "4791",
	"5110": "5119",
	"5130": "5139",
	"5162": "5163",
	"5300": "5309",
	"5400": "5409",
	"5420": "5424",
	"5425": "5429",
	"5505": "5509",
	"5540": "5549",
	"5600": "5609",
	"5610": "5619",
	"5660": "5669",
	"5710": "5711",
	"5720": "5721",
	"5750": "5751",
	"5760": "5761",
	"5780": "5781",
	"5790": "5791",
	"5920": "5921",
	"5925": "5926",
	"5940": "5941",
	"5945": "5946",
}

# The twins of the SKR03 watch list, and the accounts of ERPNext's template whose label names no rate
# or a rate other than 19 and 7 %.
SKR04_WATCHED = (
	"1434",  # a balance is a timing case: Vorsteuer deductible in a later period
	"3865",  # a balance is a timing case: Umsatzsteuer due in a later period
	"1410",
	"1411",
	"1412",
	"1413",
	"1416",
	"1417",
	"1419",
	"3261",
	"3270",
	"3800",
	"3810",
	"3811",
	"3812",
	"3814",
	"3816",
	"3839",
	"5175",
	"5176",
	"5951",
	"5954",
	"5560",
	"5565",
	"4110",
	"4180",
	"4133",
	"4134",
	"4131",
	"4132",
	"4200",
	"4340",
	"4834",
	"4708",
	"4709",
	# twins of watched SKR03 accounts, without "U" in the chart
	"5744",
	"4499",
	"4869",
	# accounts of ERPNext's template; 4560, 4570 and 4949 like their SKR03 twins 8510, 8570 and 8614
	"4560",
	"4570",
	"4949",
	"3271",
	"4136",
	"4138",
	"4330",
	"4510",
	"4520",
	"4600",
	"4695",
	"4700",
	"4723",
	"4729",
	"4730",
	"4745",
	"4769",
	"4770",
	"4833",
	"4849",
	"4850",
	"4851",
	"4852",
	"4940",
	"4946",
	"5726",
	"5727",
	"5745",
	"5950",
	"5953",
	"5960",
	"5965",
	"6280",
	"6285",
	"6287",
	"6889",
	"6890",
	"6891",
	"6892",
	"6930",
	"6934",
	"6935",
	"6937",
	"6939",
)

# The twins of SKR03_WATCHED_FOR_HINTS; above class 4 the chart prints "M 4830-4837".
SKR04_WATCHED_FOR_HINTS = (
	"4830",
	"4835",
	"4832",
)

# The twins of SKR03_IGNORED, settlement and EÜR accounts that only SKR04 hands to the Umsatzsteuer,
# and the accounts of ERPNext's template that carry no Kennzahl.
SKR04_IGNORED = (
	"1456",  # Bauabzugsbetrag (§ 48 EStG), not Umsatzsteuer
	"1495",  # clearing account for prepayments received; the taxed ones are on 3260 to 3272
	# OSS: this Umsatzsteuer is declared to the Bundeszentralamt für Steuern, not in the Voranmeldung
	"3798",
	"3817",
	"3818",
	"3831",
	"3820",  # Vorauszahlungen paid to the Finanzamt
	"3830",  # Sondervorauszahlung paid; it enters Kz 39 through extra_values
	# Dreiecksgeschäft, whose base is not reported: the acquisition of the first buyer (5552) counts
	# as taxed (§ 25b Abs. 3 UStG), the tax of the last buyer is on 3819 (Kz 69) and his Vorsteuer
	# on 1436 (Kz 66)
	"5189",
	"5552",
	"5553",
	"5792",
	"5793",
	"5909",  # domestic purchases without Vorsteuer: no Kennzahl at all
	# settlement and EÜR accounts that only SKR04 hands to the Umsatzsteuer
	"1427",  # Verbrauchsteuern paid, not Umsatzsteuer
	"1460",  # Geldtransit
	"1486",  # clearing account for the Gewinnermittlung nach § 4 Abs. 3 EStG
	"1490",  # clearing account for the Ist-Versteuerung
	"1491",  # neutralisation for the Gewinnermittlung nach § 4 Abs. 3 EStG
	# accounts of ERPNext's template
	"1420",  # claims on the Finanzamt
	"1421",
	"1422",
	"1425",
	"1930",  # Umsatzsteuer on prepayments, deferred in the balance sheet
	"3850",  # Einfuhrumsatzsteuer owed to customs; the deduction runs through 1433 into Kz 62
	# Wertabgaben and Sachbezüge without Umsatzsteuer and Innenumsätze (Anleitung zu Zeile 36)
	"4605",
	"4637",
	"4638",
	"4639",
	"4659",
	"4679",
	"4689",
	"4690",
	# Vorsteuer of other countries
	"4838",
	"6302",
	# purchases and prepayments made: only their Vorsteuer is reported, from its own accounts
	"1181",
	"1184",
	"1185",
	"1186",
	"5110",
	"5130",
	"5170",
	"5171",
	"5191",
	"5192",
	"5300",
	"5400",
	"5505",
	"5540",
	"5710",
	"5714",
	"5715",
	"5720",
	"5722",
	"5723",
	"5730",
	"5731",
	"5733",
	"5734",
	"5736",
	"5738",
	"5750",
	"5753",
	"5754",
	"5755",
	"5760",
	"5769",
	"5770",
	"5780",
	"5783",
	"5784",
	"5785",
	"5790",
	"5906",
	# purchases taxable in a third country or in another EU country, tax-free imports and
	# non-deductible Vorsteuer
	"5551",
	"5558",
	"5559",
	"5600",
	"5610",
	"5660",
	"6871",
	# prepayments without automatic tax, like their SKR03 twins; the taxed ones are on 3260 to 3272
	"1190",
	"3250",
	"3280",
	"3284",
	"3285",
	"3695",
)

SKR03 = _mapping("SKR03", SKR03_ACCOUNTS, SKR03_WATCHED, SKR03_WATCHED_FOR_HINTS, SKR03_RANGES)
SKR04 = _mapping("SKR04", SKR04_ACCOUNTS, SKR04_WATCHED, SKR04_WATCHED_FOR_HINTS, SKR04_RANGES)

DEFAULTS = MappingProxyType({"SKR03": SKR03, "SKR04": SKR04})
# The watched accounts whose balance is a timing case, the first two of each watch list: DATEV Kontenrahmen 2026,
# SKR 03 „1548 Vorsteuer in Folgeperiode/im Folgejahr abziehbar“ and „1725 Umsatzsteuer nicht fällig“, SKR 04 1434 and
# 3865 of the same names. A period that releases the balance such an account carries into it blocks nothing
# (steuerbote/ustva/carried.py).
TIMING_ACCOUNTS = MappingProxyType({"SKR03": SKR03_WATCHED[:2], "SKR04": SKR04_WATCHED[:2]})

# The edition of the DATEV charts these defaults follow, "Gültig für 2026" as the docstring cites them, and the
# revision of the defaults within it. Every change of the defaults raises REVISION, and a new edition starts it at 1
# again, so that a VAT Return Mapping can name the defaults it took over (its defaults_version) and the same version
# always means the same defaults: test_defaults.py pins the content of each version.
DATEV_EDITION = 2026
REVISION = 3

# The purchase accounts whose name states the rate of their Vorsteuer, as the Standardkontenrahmen SKR 03 and SKR 04 „Gültig für 2026“ name
# them: SKR 03 3010 „Einkauf Roh-, Hilfs- und Betriebsstoffe 7 % Vorsteuer“ and 3030 of 19 %, 3091 and 3092
# „Energiestoffe (Fertigung) 7 % VSt“ and „19 % VSt“, 3300 and 3347 „Wareneingang 7 % Vorsteuer“, 3400 and 3418
# „Wareneingang 19 % Vorsteuer“; SKR 04 5110, 5130, 5191, 5192, 5300, 5347, 5400 and 5418 of the same names. The Voranmeldung
# gives them no Kennzahl; the hint on the input tax of a voucher compares their rate with the Vorsteuer it books
# (steuerbote/ustva/input_tax.py).
SKR03_PURCHASE_RATES = {
	"3010": 7,
	"3030": 19,
	"3091": 7,
	"3092": 19,
	"3300": 7,
	"3347": 7,
	"3400": 19,
	"3418": 19,
}
SKR04_PURCHASE_RATES = {
	"5110": 7,
	"5130": 19,
	"5191": 7,
	"5192": 19,
	"5300": 7,
	"5347": 7,
	"5400": 19,
	"5418": 19,
}


def _purchase_rates(
	rates: ReadOnlyMapping[str, int], ranges: ReadOnlyMapping[str, str]
) -> MappingProxyType[str, Decimal]:
	return MappingProxyType(
		{
			member: Decimal(rate)
			for account, rate in rates.items()
			for member in with_ranges((account,), ranges)
		}
	)


_PURCHASE_RATES = MappingProxyType(
	{
		"SKR03": _purchase_rates(SKR03_PURCHASE_RATES, SKR03_RANGES),
		"SKR04": _purchase_rates(SKR04_PURCHASE_RATES, SKR04_RANGES),
	}
)


def purchase_rates(chart: str) -> ReadOnlyMapping[str, Decimal]:
	"""The rate of the Vorsteuer that each purchase account of a chart names; none for a chart without defaults."""
	return _PURCHASE_RATES.get(chart, MappingProxyType({}))


# The ignored accounts of each chart with the members of their ranges, which take the place of their first account.
_DELIBERATELY_WITHOUT_KENNZAHL = MappingProxyType(
	{
		"SKR03": frozenset(with_ranges(SKR03_IGNORED, SKR03_RANGES)),
		"SKR04": frozenset(with_ranges(SKR04_IGNORED, SKR04_RANGES)),
	}
)


def default_mapping(chart: str, year: int) -> Mapping:
	"""The default mapping of a chart, validated against the form of the period's year."""
	try:
		mapping = DEFAULTS[chart]
	except KeyError:
		raise KeyError(
			f"no default mapping for chart {chart!r}; known charts: {', '.join(DEFAULTS)}"
		) from None
	return mapping.for_year(year)


def defaults_version(chart: str) -> str:
	"""The version of the defaults of a chart: the chart, the DATEV edition and the revision, such as SKR03 2026.1."""
	if chart not in DEFAULTS:
		raise KeyError(f"no default mapping for chart {chart!r}; known charts: {', '.join(DEFAULTS)}")
	return f"{chart} {DATEV_EDITION}.{REVISION}"


def deliberately_without_kennzahl(chart: str) -> frozenset[str]:
	"""The accounts the defaults of a chart leave without Kennzahl on purpose; none for a chart without defaults.

	A company with its own chart has no such list: an account of its tax templates without Kennzahl gets a place
	by a rule or as a watched account.
	"""
	return _DELIBERATELY_WITHOUT_KENNZAHL.get(chart, frozenset())

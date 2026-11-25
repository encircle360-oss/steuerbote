from datetime import date
from unittest import TestCase

from steuerbote.ustva.plausibility import EU_MEMBER_STATES
from steuerbote.ustva.residence import (
	MEMBERSHIPS,
	UNKNOWN,
	Classification,
	Finding,
	Placement,
	Problem,
	Residence,
	Source,
	Supplier,
	Voucher,
	member_state,
	place,
	residence_in,
	residence_of_vat_id,
	vat_id_prefix,
)

DAY = date(2027, 1, 15)
PRAGUE = Supplier("Vltava Software s.r.o.", "Czech Republic", vat_id="CZ12345678")
DUBLIN = Supplier("Liffey Cloud Ltd", "Ireland", vat_id="IE1234567X")
BOSTON = Supplier("Harbor Analytics Inc.", "United States")
BERLIN = Supplier("Spree Bau GmbH", "Germany", vat_id="DE123456789")


def voucher(*suppliers: Supplier, **fields) -> Voucher:
	return Voucher(DAY, suppliers, **fields)


class MembershipTest(TestCase):
	"""The member states of a day: § 13b Absatz 7 Satz 4 UStG looks at the time of the supply."""

	def test_the_member_states_of_2027_are_those_of_the_hints_on_invoices(self):
		self.assertEqual(
			[(state.code, state.country) for state in MEMBERSHIPS if state.on(DAY)],
			[(state.code, state.country) for state in EU_MEMBER_STATES],
		)

	def test_a_country_is_found_by_code_and_by_name_in_any_case(self):
		for country in ("CZ", "cz", "Czech Republic", " czech republic "):
			with self.subTest(country=country):
				self.assertEqual(member_state(country, DAY).code, "CZ")

	def test_croatia_is_a_member_state_from_1_july_2013(self):
		self.assertIsNone(member_state("Croatia", date(2013, 6, 30)))
		self.assertEqual(member_state("HR", date(2013, 7, 1)).code, "HR")

	def test_the_united_kingdom_is_one_to_the_end_of_the_transition_period(self):
		self.assertEqual(residence_in("United Kingdom", date(2020, 12, 31)), Residence.OTHER_MEMBER_STATE)
		self.assertEqual(residence_in("United Kingdom", date(2021, 1, 1)), Residence.THIRD_COUNTRY)
		self.assertEqual(residence_in("Isle of Man", date(2020, 12, 31)), Residence.OTHER_MEMBER_STATE)
		self.assertEqual(residence_in("IM", DAY), Residence.THIRD_COUNTRY)

	def test_monaco_counts_as_france(self):
		self.assertEqual(member_state("Monaco", DAY).code, "FR")
		self.assertEqual(residence_in("MC", DAY), Residence.OTHER_MEMBER_STATE)

	def test_residence_by_country(self):
		self.assertEqual(residence_in("Germany", DAY), Residence.DOMESTIC)
		self.assertEqual(residence_in("Ireland", DAY), Residence.OTHER_MEMBER_STATE)
		self.assertEqual(residence_in("Switzerland", DAY), Residence.THIRD_COUNTRY)
		for empty in (None, "", "  "):
			with self.subTest(empty=empty):
				self.assertIsNone(residence_in(empty, DAY))


class VatIdTest(TestCase):
	"""A VAT ID only checks the country: its prefix names where a business is registered, not where it sits."""

	def test_the_prefix_is_read_as_normalize_reads_the_number(self):
		self.assertEqual(vat_id_prefix("ie 1234567x"), "IE")
		self.assertEqual(vat_id_prefix("EU372000001"), "EU")
		for none in (None, "", "123456789", "1A2345"):
			with self.subTest(vat_id=none):
				self.assertEqual(vat_id_prefix(none), "")

	def test_a_member_state_prefix_points_there(self):
		self.assertEqual(residence_of_vat_id("ATU12345678", DAY), Residence.OTHER_MEMBER_STATE)
		self.assertEqual(residence_of_vat_id("EL123456789", DAY), Residence.OTHER_MEMBER_STATE)
		self.assertEqual(residence_of_vat_id("DE123456789", DAY), Residence.DOMESTIC)

	def test_northern_ireland_is_drittlandsgebiet_for_services(self):
		self.assertEqual(residence_of_vat_id("XI123456789", DAY), Residence.THIRD_COUNTRY)

	def test_a_british_number_points_to_the_drittlandsgebiet_after_2020(self):
		self.assertEqual(residence_of_vat_id("GB123456789", DAY), Residence.THIRD_COUNTRY)
		self.assertEqual(residence_of_vat_id("GB123456789", date(2020, 6, 1)), Residence.OTHER_MEMBER_STATE)

	def test_the_one_stop_shop_number_of_the_non_union_scheme_points_nowhere(self):
		self.assertIsNone(residence_of_vat_id("EU372000001", DAY))

	def test_other_prefixes_point_nowhere(self):
		for vat_id in ("CHE123456789MWST", "IM1234567890", "MC12345678901", "US123456", None, "61-2100001"):
			with self.subTest(vat_id=vat_id):
				self.assertIsNone(residence_of_vat_id(vat_id, DAY))


class FactsTest(TestCase):
	def test_a_supplier_needs_a_name(self):
		for name in ("", "  ", None):
			with self.subTest(name=name), self.assertRaisesRegex(ValueError, "a supplier needs a name"):
				Supplier(name)  # type: ignore[arg-type]

	def test_classifications_are_read_from_their_values(self):
		self.assertIs(
			Supplier("A", classification="Other Reverse Charge").classification, Classification.OTHER
		)
		facts = Voucher(
			DAY, [PRAGUE], classification="EU Service", template_classification="Other Reverse Charge"
		)
		self.assertEqual(facts.suppliers, (PRAGUE,))
		self.assertIs(facts.classification, Classification.EU_SERVICE)
		self.assertIs(facts.template_classification, Classification.OTHER)
		with self.assertRaises(ValueError):
			Voucher(DAY, classification="Kz 46")  # type: ignore[arg-type]

	def test_the_day_is_a_date(self):
		with self.assertRaisesRegex(TypeError, "day must be a date"):
			Voucher("2027-01-15")  # type: ignore[arg-type]


class PlaceTest(TestCase):
	def test_a_supplier_established_in_another_member_state_gives_an_eu_service(self):
		self.assertEqual(
			place("V1", voucher(PRAGUE)),
			Placement(Classification.EU_SERVICE, Residence.OTHER_MEMBER_STATE, Source.COUNTRY),
		)

	def test_a_supplier_in_the_drittlandsgebiet_or_in_germany_gives_another_reverse_charge(self):
		for supplier, residence in ((BOSTON, Residence.THIRD_COUNTRY), (BERLIN, Residence.DOMESTIC)):
			with self.subTest(supplier=supplier.name):
				self.assertEqual(
					place("V1", voucher(supplier)), Placement(Classification.OTHER, residence, Source.COUNTRY)
				)

	def test_the_address_decides_without_a_country(self):
		supplier = Supplier("Garonne Conseil SARL", address_country="France")
		self.assertEqual(
			place("V1", voucher(supplier)),
			Placement(Classification.EU_SERVICE, Residence.OTHER_MEMBER_STATE, Source.ADDRESS),
		)

	def test_the_country_wins_over_an_address_elsewhere_with_a_finding(self):
		supplier = Supplier("Harbor Analytics Inc.", " United States ", " Ireland ")
		self.assertEqual(
			place("V1", voucher(supplier)),
			Placement(
				Classification.OTHER,
				Residence.THIRD_COUNTRY,
				Source.COUNTRY,
				(Finding(Problem.ADDRESS_ELSEWHERE, "V1", supplier.name, ("United States", "Ireland")),),
			),
		)

	def test_an_address_in_the_same_place_is_no_finding(self):
		supplier = Supplier("Vltava Software s.r.o.", "CZ", "Czech Republic")
		self.assertEqual(place("V1", voucher(supplier)).findings, ())

	def test_a_vat_id_of_a_member_state_does_not_move_a_supplier_of_the_drittlandsgebiet(self):
		supplier = Supplier("Harbor Analytics Inc.", "United States", vat_id="IE9999999W")
		self.assertEqual(
			place("V1", voucher(supplier)),
			Placement(
				Classification.OTHER,
				Residence.THIRD_COUNTRY,
				Source.COUNTRY,
				(Finding(Problem.VAT_ID_PREFIX, "V1", supplier.name, ("United States", "IE")),),
			),
		)

	def test_the_prefix_is_checked_against_the_address_when_it_decides(self):
		supplier = Supplier("Garonne Conseil SARL", address_country="France", vat_id="XI123456789")
		self.assertEqual(
			place("V1", voucher(supplier)).findings,
			(Finding(Problem.VAT_ID_PREFIX, "V1", supplier.name, ("France", "XI")),),
		)

	def test_a_one_stop_shop_number_of_a_supplier_of_the_drittlandsgebiet_is_no_finding(self):
		supplier = Supplier("Harbor Analytics Inc.", "United States", vat_id="EU372000001")
		self.assertEqual(place("V1", voucher(supplier)).findings, ())

	def test_without_country_and_address_the_classification_stays_open(self):
		supplier = Supplier("Nebula Tools LLC")
		self.assertEqual(
			place("V1", voucher(supplier)),
			Placement(None, None, Source.NONE, (Finding(Problem.NO_COUNTRY, "V1", supplier.name),)),
		)

	def test_a_vat_id_never_decides_but_the_finding_names_its_prefix(self):
		supplier = Supplier("Nebula Tools LLC", vat_id="IE9999999W")
		self.assertEqual(
			place("V1", voucher(supplier)),
			Placement(None, None, Source.NONE, (Finding(Problem.NO_COUNTRY, "V1", supplier.name, ("IE",)),)),
		)

	def test_a_voucher_without_supplier_stays_open(self):
		self.assertEqual(
			place("Journal Entry:J1", voucher()),
			Placement(None, None, Source.NONE, (Finding(Problem.NO_SUPPLIER, "Journal Entry:J1"),)),
		)

	def test_a_voucher_the_caller_knows_nothing_of_stays_open_without_a_finding(self):
		self.assertIs(place("V1", None), UNKNOWN)

	def test_suppliers_that_agree_decide_together(self):
		other = Supplier("Liffey Data Ltd", address_country="Ireland")
		placement = place("V1", voucher(DUBLIN, other))
		self.assertEqual(
			(placement.classification, placement.residence, placement.source),
			(Classification.EU_SERVICE, Residence.OTHER_MEMBER_STATE, Source.COUNTRY),
		)
		self.assertEqual(place("V1", voucher(PRAGUE, DUBLIN)).source, Source.COUNTRY)

	def test_suppliers_established_in_different_places_leave_it_open(self):
		self.assertEqual(
			place("V1", voucher(PRAGUE, BOSTON)),
			Placement(
				None,
				None,
				Source.NONE,
				(
					Finding(
						Problem.SUPPLIERS_DISAGREE,
						"V1",
						"Vltava Software s.r.o., Harbor Analytics Inc.",
						(
							"Vltava Software s.r.o.",
							"other member state",
							"Harbor Analytics Inc.",
							"third country",
						),
					),
				),
			),
		)

	def test_a_supplier_without_country_among_others_leaves_it_open(self):
		unknown = Supplier("Nebula Tools LLC")
		self.assertEqual(
			place("V1", voucher(PRAGUE, unknown)).findings,
			(Finding(Problem.NO_COUNTRY, "V1", unknown.name),),
		)


class StatedTest(TestCase):
	"""A classification a person stated wins: only a person can tell an EU supplier's supply that is no service of
	§ 3a Absatz 2 UStG."""

	def test_the_voucher_wins_over_supplier_template_and_country(self):
		supplier = Supplier(DUBLIN.name, "Ireland", classification=Classification.EU_SERVICE)
		facts = voucher(
			supplier,
			classification=Classification.OTHER,
			tax_template="Reverse Charge EU",
			template_classification=Classification.EU_SERVICE,
		)
		self.assertEqual(
			place("V1", facts), Placement(Classification.OTHER, Residence.OTHER_MEMBER_STATE, Source.VOUCHER)
		)

	def test_the_supplier_wins_over_template_and_country(self):
		supplier = Supplier(PRAGUE.name, "Czech Republic", classification=Classification.OTHER)
		facts = voucher(supplier, template_classification=Classification.EU_SERVICE)
		self.assertEqual(
			place("V1", facts), Placement(Classification.OTHER, Residence.OTHER_MEMBER_STATE, Source.SUPPLIER)
		)

	def test_suppliers_decide_only_when_each_has_the_same_classification(self):
		stated = Supplier("Liffey Data Ltd", "Ireland", classification=Classification.OTHER)
		self.assertEqual(place("V1", voucher(DUBLIN, stated)).source, Source.COUNTRY)
		twice = Supplier("Liffey Ops Ltd", "Ireland", classification=Classification.OTHER)
		self.assertEqual(place("V1", voucher(twice, stated)).source, Source.SUPPLIER)

	def test_the_template_wins_over_the_country(self):
		facts = voucher(BOSTON, tax_template="Reverse Charge", template_classification=Classification.OTHER)
		self.assertEqual(
			place("V1", facts), Placement(Classification.OTHER, Residence.THIRD_COUNTRY, Source.TAX_TEMPLATE)
		)

	def test_a_template_of_another_reverse_charge_for_a_supplier_of_a_member_state_is_a_finding(self):
		facts = voucher(DUBLIN, tax_template="Reverse Charge", template_classification=Classification.OTHER)
		self.assertEqual(
			place("V1", facts).findings,
			(Finding(Problem.TEMPLATE_OTHER_FROM_MEMBER_STATE, "V1", DUBLIN.name, ("Reverse Charge",)),),
		)

	def test_a_voucher_stated_otherwise_for_a_supplier_of_a_member_state_is_no_finding(self):
		self.assertEqual(place("V1", voucher(DUBLIN, classification=Classification.OTHER)).findings, ())

	def test_an_eu_service_stated_for_a_supplier_outside_the_member_states_is_a_finding(self):
		for facts, source in (
			(voucher(BOSTON, classification=Classification.EU_SERVICE), Source.VOUCHER),
			(voucher(Supplier(BERLIN.name, "Germany", classification="EU Service")), Source.SUPPLIER),
			(voucher(BOSTON, template_classification=Classification.EU_SERVICE), Source.TAX_TEMPLATE),
		):
			with self.subTest(source=source):
				placement = place("V1", facts)
				self.assertIs(placement.classification, Classification.EU_SERVICE)
				(finding,) = placement.findings
				self.assertEqual(
					(finding.problem, finding.facts),
					(Problem.STATED_EU_SERVICE_OUTSIDE, (str(source), str(placement.residence))),
				)

	def test_a_stated_classification_needs_no_country(self):
		facts = voucher(Supplier("Nebula Tools LLC"), classification=Classification.EU_SERVICE)
		self.assertEqual(place("V1", facts), Placement(Classification.EU_SERVICE, None, Source.VOUCHER))
		self.assertEqual(
			place("J1", voucher(classification=Classification.OTHER)),
			Placement(Classification.OTHER, None, Source.VOUCHER),
		)

	def test_a_stated_classification_silences_the_findings_on_the_country(self):
		supplier = Supplier(
			"Harbor Analytics Inc.", "United States", "Ireland", "IE9999999W", Classification.OTHER
		)
		self.assertEqual(place("V1", voucher(supplier)).findings, ())

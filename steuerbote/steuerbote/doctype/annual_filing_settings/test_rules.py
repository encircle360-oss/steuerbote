from dataclasses import FrozenInstanceError
from datetime import date
from decimal import Decimal
from unittest import TestCase

from steuerbote.steuerbote.doctype.annual_filing_settings import rules as rules_module
from steuerbote.steuerbote.doctype.annual_filing_settings.rules import (
	AGS_ONLY_FOR_GEWERBESTEUER,
	MESSAGES,
	NO_VAT_RETURN_REASONS,
	ROW_TEXT_LENGTHS,
	TEXT_LENGTHS,
	Address,
	CarryForward,
	CarryForwardKind,
	Director,
	Establishment,
	Holding,
	LegalForm,
	Period,
	Prepayment,
	SettingsError,
	Shareholder,
	ShareholderKind,
	SizeClass,
	SizeRecord,
	StreetSplit,
	Tax,
	TradeTaxRate,
	YearSettings,
	check_carry_forwards,
	check_directors,
	check_employment_types,
	check_establishments,
	check_holdings,
	check_prepayments,
	check_shareholders,
	check_size_history,
	check_trade_tax_rates,
	check_years,
	directors_on,
	early_request_window,
	elster_tax_number,
	elster_text,
	establishments_in,
	german_postal_code,
	hebesatz_of,
	holdings_of,
	latest_carry_forward,
	legal_form,
	legal_status,
	minimum_hebesatz,
	normalized_ags,
	normalized_idnr,
	normalized_wid_nr,
	prepayments_of,
	rechtsform,
	share_total,
	shareholders_on,
	size_class_on,
	split_street,
	year_settings,
)

# Invented data throughout: no Steuernummer, Identifikationsnummer or W-IdNr. here belongs to anyone.
IDNR = "12345678903"
WID_NR = "DE123456789"


def shareholder(row=1, name="Erika Mustermann", percent="100", start=date(2026, 1, 1), end=None, **fields):
	values = {
		"row": row,
		"name": name,
		"kind": ShareholderKind.NATURAL_PERSON,
		"nominal_amount": Decimal("25000"),
		"percent": Decimal(percent),
		"from_date": start,
		"to_date": end,
		**fields,
	}
	return Shareholder(**values)


def establishment(row=1, ags="09162000", start=date(2026, 1, 1), end=None, **fields):
	values = {
		"row": row,
		"municipality": "München",
		"postal_code": "80331",
		"ags": ags,
		"from_date": start,
		"to_date": end,
		**fields,
	}
	return Establishment(**values)


def rate(ags="09162000", year=2026, hebesatz="490", source="Haushaltssatzung 2026", **fields):
	return TradeTaxRate(ags=ags, year=year, hebesatz=Decimal(hebesatz), source=source, **fields)


class LegalFormTest(TestCase):
	def test_a_gmbh_and_a_ug_are_the_legal_forms_steuerbote_files_for(self):
		self.assertEqual([form.value for form in LegalForm], ["GmbH", "UG"])
		self.assertIs(legal_form("UG"), LegalForm.UG)
		for value in ("AG", "gmbh", "", None):
			with self.subTest(value=value), self.assertRaisesRegex(SettingsError, "is not a legal form"):
				legal_form(value)

	def test_the_rechtsform_of_kst_1_and_gewst_1_a(self):
		"""RECHTSFORM_KOERPERSCHAFTEN_V3 and RECHTSFORM_GEWERBESTEUER_V2: 350 GmbH, 370 UG (haftungsbeschränkt)."""
		self.assertEqual((rechtsform("GmbH"), rechtsform(LegalForm.UG)), ("350", "370"))
		with self.assertRaisesRegex(SettingsError, "KG is not a legal form"):
			rechtsform("KG")

	def test_the_legal_status_of_the_gcd_files_a_ug_as_a_gmbh_in_the_disclosure(self):
		self.assertEqual((legal_status("GmbH"), legal_status("UG")), ("GMBH", "UG"))
		self.assertEqual(
			(legal_status("GmbH", disclosure=True), legal_status("UG", disclosure=True)), ("GMBH", "GMBH")
		)
		with self.assertRaises(SettingsError):
			legal_status("eG", disclosure=True)


class ElsterTextTest(TestCase):
	def test_keeps_a_text_on_one_line_in_the_character_set_of_elster(self):
		self.assertEqual(elster_text("  Kaiser-Wilhelm-\nStraße  ", "Straße", 30), "Kaiser-Wilhelm- Straße")
		self.assertEqual(elster_text("Müller \N{EN DASH} „Beratung“", "Name", 55), 'Müller - "Beratung"')

	def test_an_empty_text_is_none(self):
		for value in (None, "", "   "):
			with self.subTest(value=value):
				self.assertIsNone(elster_text(value, "Straße", 30))

	def test_refuses_a_text_longer_than_the_form_takes(self):
		self.assertEqual(elster_text("x" * 24, "Ort des Sitzes", 24), "x" * 24)
		with self.assertRaises(SettingsError) as raised:
			elster_text("x" * 25, "Ort des Sitzes", 24)
		self.assertEqual(str(raised.exception), "Ort des Sitzes has 25 characters; ELSTER takes at most 24.")

	def test_refuses_characters_elster_does_not_take(self):
		with self.assertRaises(SettingsError) as raised:
			elster_text("Łódź", "Ort", 29)
		self.assertEqual(
			str(raised.exception),
			"Ort contains characters ELSTER does not take: 'Ł' (U+0141), 'ź' (U+017A).",
		)

	def test_the_lengths_are_those_of_the_forms(self):
		"""GewSt 1 A line 4; KSt 1 lines 6 and 7; USt 2 A line 9; AbsStr and AbsOrt of the Vorsatz; the Mitwirkung
		of USt 2 A and KSt 1 lines 100 to 102."""
		self.assertEqual(
			dict(TEXT_LENGTHS),
			{
				"business_purpose": 25,
				"management_seat": 24,
				"registered_seat": 24,
				"street": 30,
				"house_number_suffix": 6,
				"address_supplement": 25,
				"postal_code": 12,
				"city": 29,
				"advisor_name": 55,
				"advisor_first_name": 55,
				"advisor_street": 55,
				"advisor_town": 55,
				"advisor_phone": 55,
				"advisor_details": 55,
				"advisor_client_number": 60,
				"advisor_clerk": 55,
			},
		)
		self.assertEqual(
			{table: dict(lengths) for table, lengths in ROW_TEXT_LENGTHS.items()},
			{
				"shareholders": {
					"shareholder_name": 999,
					"street": 999,
					"postal_code_and_town": 999,
					"foreign_id": 999,
				},
				"establishments": {"municipality": 999, "hebenummer": 28},
			},
		)


class SplitStreetTest(TestCase):
	def test_splits_the_house_number_and_its_suffix_off_the_street(self):
		for text, expected in (
			("Hauptstraße 1", StreetSplit("Hauptstraße", "1")),
			("Musterweg 12a", StreetSplit("Musterweg", "12", "a")),
			("Musterweg 12 a", StreetSplit("Musterweg", "12", "a")),
			("Musterstr. 12-14", StreetSplit("Musterstr.", "12", "-14")),
			("Am Brunnen 1000", StreetSplit("Am Brunnen", "1000")),
			("  Lange   Gasse 7  ", StreetSplit("Lange Gasse", "7")),
		):
			with self.subTest(text=text):
				self.assertEqual(split_street(text), expected)

	def test_splits_at_the_last_digits_after_a_blank(self):
		self.assertEqual(split_street("Straße des 17. Juni 112"), StreetSplit("Straße des 17. Juni", "112"))
		self.assertEqual(split_street("Q 7, 17"), StreetSplit("Q 7", "17"))

	def test_a_street_without_a_house_number_stays_whole(self):
		for text in ("Am Markt", "Musterstraße 12345", "Musterstraße12"):
			with self.subTest(text=text):
				self.assertEqual(split_street(text), StreetSplit(text))

	def test_an_empty_street_gives_none(self):
		for text in (None, "", "  "):
			with self.subTest(text=text):
				self.assertIsNone(split_street(text))


class AddressTest(TestCase):
	def test_writes_street_house_number_and_suffix_on_one_line(self):
		address = Address("Musterweg", "12", "a", "Hinterhaus", "80331", "München")
		self.assertEqual(address.street_line, "Musterweg 12a")
		self.assertTrue(address.in_germany)
		self.assertEqual(Address("Am Markt").street_line, "Am Markt")
		self.assertIsNone(Address().street_line)

	def test_the_house_number_is_digits_only_at_most_four(self):
		for number in ("12a", "12345", "", " 1", "-1"):
			with self.subTest(number=number), self.assertRaisesRegex(SettingsError, "is not a house number"):
				Address("Musterweg", number)

	def test_a_house_number_needs_its_street_and_a_suffix_its_house_number(self):
		with self.assertRaisesRegex(SettingsError, "A house number needs its street."):
			Address(None, "12")
		with self.assertRaisesRegex(SettingsError, "A house number suffix needs its house number."):
			Address("Musterweg", None, "a")

	def test_a_german_postal_code_has_five_digits_not_beginning_with_00(self):
		for code in ("01067", "80331", "99998"):
			with self.subTest(code=code):
				self.assertEqual(Address(postal_code=code).postal_code, code)
		for code in ("00123", "8033", "803311", "A-1010", ""):
			with (
				self.subTest(code=code),
				self.assertRaisesRegex(SettingsError, "is not a German postal code"),
			):
				Address(postal_code=code)

	def test_a_postal_code_abroad_has_its_own_form(self):
		address = Address(postal_code="A-1010", city="Wien", country="Austria")
		self.assertFalse(address.in_germany)
		self.assertEqual(address.postal_code, "A-1010")

	def test_the_vorsatz_takes_street_house_number_and_suffix_in_30_characters(self):
		self.assertEqual(len(Address("x" * 25, "1234").street_line), 30)
		with self.assertRaises(SettingsError) as raised:
			Address("x" * 25, "1234", "a")
		self.assertEqual(
			str(raised.exception),
			"Street, house number and suffix make 31 characters; the Vorsatz of an Erklärung takes at most 30.",
		)

	def test_german_postal_code_returns_the_code(self):
		self.assertEqual(german_postal_code("10115"), "10115")


class PeriodTest(TestCase):
	def test_a_period_covers_its_days_and_lasts_without_a_last_day(self):
		period = Period(date(2026, 1, 1), date(2026, 6, 30))
		self.assertTrue(period.covers(date(2026, 1, 1)))
		self.assertTrue(period.covers(date(2026, 6, 30)))
		self.assertFalse(period.covers(date(2025, 12, 31)))
		self.assertFalse(period.covers(date(2026, 7, 1)))
		self.assertTrue(Period(date(2026, 1, 1)).covers(date(2099, 1, 1)))

	def test_two_periods_overlap_when_they_share_a_day(self):
		first_half = Period(date(2026, 1, 1), date(2026, 6, 30))
		self.assertTrue(first_half.overlaps(Period(date(2026, 6, 30))))
		self.assertFalse(first_half.overlaps(Period(date(2026, 7, 1))))
		self.assertFalse(Period(date(2026, 7, 1)).overlaps(first_half))
		self.assertTrue(Period(date(2026, 7, 1)).overlaps(Period(date(2027, 1, 1))))
		self.assertTrue(Period(date(2027, 1, 1)).overlaps(Period(date(2026, 1, 1), date(2027, 1, 1))))


class YearSettingsTest(TestCase):
	def test_a_year_without_anything_set(self):
		year = YearSettings(2026)
		self.assertFalse(year.advisor_prepares)
		self.assertEqual(
			year.early_requests,
			{
				"Umsatzsteuererklärung": None,
				"Körperschaftsteuererklärung": None,
				"Gewerbesteuererklärung": None,
			},
		)
		with self.assertRaises(FrozenInstanceError):
			year.year = 2027  # type: ignore[misc]

	def test_the_year_has_four_digits(self):
		for value in (0, 999, 10000, True, 2026.0, "2026", None):
			with self.subTest(value=value), self.assertRaisesRegex(SettingsError, "is not a four-digit year"):
				YearSettings(value)  # type: ignore[arg-type]

	def test_the_finanzamt_asks_early_only_for_erklaerungen_a_steuerberatung_prepares(self):
		"""§ 149 Abs. 4 Satz 1 AO: „Erklärungen im Sinne des Absatzes 3“."""
		self.assertEqual(
			YearSettings(2026, advisor_prepares=True, early_request_kst=date(2027, 9, 30)).early_requests[
				"Körperschaftsteuererklärung"
			],
			date(2027, 9, 30),
		)
		with self.assertRaises(SettingsError) as raised:
			YearSettings(2026, early_request_gewst=date(2027, 9, 30))
		self.assertEqual(
			str(raised.exception),
			"The Finanzamt can ask for the Gewerbesteuererklärung of 2026 early only when a Steuerberatung prepares "
			"it (§ 149 Abs. 4 AO).",
		)

	def test_an_early_request_lies_from_the_deadline_of_absatz_2_on_and_before_the_end_of_february(self):
		"""§ 149 Abs. 4 AO: before the last day of February of the second year, never shorter than seven months."""
		self.assertEqual(early_request_window(2026), (date(2027, 7, 31), date(2028, 2, 29)))
		self.assertEqual(early_request_window(2027), (date(2028, 7, 31), date(2029, 2, 28)))
		for day in (date(2027, 7, 31), date(2028, 2, 28)):
			with self.subTest(day=day):
				YearSettings(2026, advisor_prepares=True, early_request_ust=day)
		for day in (date(2027, 7, 30), date(2028, 2, 29), date(2028, 3, 1)):
			with self.subTest(day=day), self.assertRaises(SettingsError) as raised:
				YearSettings(2026, advisor_prepares=True, early_request_ust=day)
		self.assertEqual(
			str(raised.exception),
			"The Finanzamt can ask for the Umsatzsteuererklärung of 2026 for a day from 31. Juli 2027 on and before "
			"29. Februar 2028 (§ 149 Abs. 4 AO), not for 1. März 2028.",
		)

	def test_a_kleinunternehmer_files_no_umsatzsteuererklaerung_to_ask_for(self):
		"""§ 19 Abs. 1 Satz 2 UStG: § 18 Absatz 1 bis 4 UStG do not apply."""
		YearSettings(2026, kleinunternehmer=True, advisor_prepares=True, early_request_kst=date(2027, 8, 31))
		with self.assertRaisesRegex(
			SettingsError, "A Kleinunternehmer files no Umsatzsteuererklärung for 2026"
		):
			YearSettings(
				2026, kleinunternehmer=True, advisor_prepares=True, early_request_ust=date(2027, 8, 31)
			)

	def test_a_year_without_umsatzsteuererklaerung_states_why(self):
		"""The company states that it owes no Umsatzsteuererklärung for the year, for example as a holding that is no
		Unternehmer within § 2 UStG or because the Finanzamt released it; Steuerbote does not judge that status."""
		year = YearSettings(2026, no_vat_return=True, no_vat_return_reason=NO_VAT_RETURN_REASONS[0])
		self.assertTrue(year.no_vat_return)
		YearSettings(
			2026,
			no_vat_return=True,
			no_vat_return_reason=NO_VAT_RETURN_REASONS[1],
			no_vat_return_note="Schreiben vom 3. März 2027",
		)
		self.assertEqual(
			NO_VAT_RETURN_REASONS,
			("Not an Unternehmer (§ 2 UStG)", "Released by the Finanzamt", "Other Reason"),
		)
		for reason in (None, "", "Kleinunternehmer"):
			with (
				self.subTest(reason=reason),
				self.assertRaisesRegex(SettingsError, "needs one of the reasons"),
			):
				YearSettings(2026, no_vat_return=True, no_vat_return_reason=reason)
		with self.assertRaisesRegex(SettingsError, "Other Reason.*needs a note"):
			YearSettings(
				2026, no_vat_return=True, no_vat_return_reason="Other Reason", no_vat_return_note=" "
			)
		YearSettings(
			2026, no_vat_return=True, no_vat_return_reason="Other Reason", no_vat_return_note="Organschaft"
		)
		with self.assertRaisesRegex(SettingsError, "states no Umsatzsteuererklärung"):
			YearSettings(2026, no_vat_return_reason="Other Reason")

	def test_a_year_without_umsatzsteuererklaerung_has_none_to_ask_for(self):
		with self.assertRaisesRegex(SettingsError, "owes no Umsatzsteuererklärung for 2026"):
			YearSettings(
				2026,
				no_vat_return=True,
				no_vat_return_reason=NO_VAT_RETURN_REASONS[0],
				advisor_prepares=True,
				early_request_ust=date(2027, 8, 31),
			)

	def test_an_exemption_under_264_3_hgb_states_its_reason(self):
		YearSettings(2026, exempt_264_3=True, exempt_264_3_reason="Konzernabschluss der Muttergesellschaft")
		for reason in (None, "", "  "):
			with (
				self.subTest(reason=reason),
				self.assertRaisesRegex(
					SettingsError, "The exemption of 2026 under § 264 Abs. 3 HGB needs its reason."
				),
			):
				YearSettings(2026, exempt_264_3=True, exempt_264_3_reason=reason)

	def test_a_year_has_one_row(self):
		years = [YearSettings(2026), YearSettings(2027)]
		check_years(years)
		with self.assertRaisesRegex(SettingsError, "The year 2026 is entered twice."):
			check_years([*years, YearSettings(2026, advisor_prepares=True)])

	def test_finds_the_settings_of_a_year(self):
		years = [YearSettings(2026, advisor_prepares=True), YearSettings(2027)]
		self.assertTrue(year_settings(years, 2026).advisor_prepares)
		self.assertIsNone(year_settings(years, 2025))


class ShareholderTest(TestCase):
	def test_a_shareholder_for_a_holding_period(self):
		holder = shareholder(kind="Corporation", idnr=None, wid_nr=WID_NR, end=date(2026, 6, 30))
		self.assertIs(holder.kind, ShareholderKind.CORPORATION)
		self.assertEqual(holder.period, Period(date(2026, 1, 1), date(2026, 6, 30)))
		with self.assertRaises(FrozenInstanceError):
			holder.percent = Decimal(50)  # type: ignore[misc]

	def test_the_kinds_of_shareholders(self):
		self.assertEqual(
			[kind.value for kind in ShareholderKind],
			["Natural Person", "Corporation", "Business Partnership"],
		)
		with self.assertRaisesRegex(SettingsError, "Stiftung is not a kind of shareholder"):
			shareholder(kind="Stiftung")

	def test_the_share_lies_above_0_and_at_most_at_100_with_four_decimals(self):
		"""E8122105: „mit maximal 4 Nachkommastellen, mit 3 Vorkommastellen, hat 100.0000 als Maximalwert“."""
		for percent in ("0.0001", "33.3333", "100"):
			with self.subTest(percent=percent):
				self.assertEqual(shareholder(percent=percent).percent, Decimal(percent))
		for percent in ("0", "-1", "100.0001", "33.33333", "NaN", "Infinity"):
			with self.subTest(percent=percent), self.assertRaisesRegex(SettingsError, "the share in percent"):
				shareholder(percent=percent)
		with self.assertRaises(SettingsError) as raised:
			shareholder(row=2, percent="33.33330001")
		self.assertEqual(
			str(raised.exception),
			"Row 2 of the shareholders: the share in percent lies above 0 and at most at 100, with at most four "
			"decimals, not 33.33330001.",
		)

	def test_the_share_is_a_decimal(self):
		with self.assertRaises(TypeError):
			Shareholder(
				1, "Erika Mustermann", ShareholderKind.NATURAL_PERSON, Decimal(1), 50.0, date(2026, 1, 1)
			)  # type: ignore[arg-type]

	def test_the_nominal_amount_is_in_full_euros_above_0(self):
		"""§ 5 Abs. 2 Satz 1 GmbHG: „Der Nennbetrag jedes Geschäftsanteils muss auf volle Euro lauten.“"""
		self.assertEqual(shareholder(nominal_amount=Decimal("12500.00")).nominal_amount, Decimal(12500))
		for amount in ("0", "-1", "100.50", "NaN"):
			with self.subTest(amount=amount), self.assertRaisesRegex(SettingsError, "in full euros above 0"):
				shareholder(nominal_amount=Decimal(amount))

	def test_only_a_natural_person_has_an_identifikationsnummer(self):
		"""§ 139b Abs. 1 AO."""
		self.assertEqual(shareholder(idnr=IDNR).idnr, IDNR)
		with self.assertRaises(SettingsError) as raised:
			shareholder(row=3, kind=ShareholderKind.PARTNERSHIP, idnr=IDNR)
		self.assertEqual(
			str(raised.exception),
			"Row 3 of the shareholders: only a natural person has an Identifikationsnummer (§ 139b Abs. 1 AO).",
		)
		self.assertNotIn(IDNR, str(raised.exception))

	def test_a_holding_period_ends_after_it_starts(self):
		shareholder(start=date(2026, 3, 1), end=date(2026, 3, 1))
		with self.assertRaises(SettingsError) as raised:
			shareholder(row=2, start=date(2026, 3, 1), end=date(2026, 2, 28))
		self.assertEqual(
			str(raised.exception),
			"Row 2 of the shareholders ends on 28. Februar 2026, before its start on 1. März 2026.",
		)


class IdentifierTest(TestCase):
	def test_an_identifikationsnummer_has_eleven_digits(self):
		self.assertEqual(normalized_idnr("12 345 678 903", 1), IDNR)
		for value in (None, "", "  "):
			with self.subTest(value=value):
				self.assertIsNone(normalized_idnr(value, 1))
		for value in ("1234567890", "123456789012", "1234567890a"):
			with self.subTest(value=value), self.assertRaises(SettingsError) as raised:
				normalized_idnr(value, 4)
			self.assertEqual(
				str(raised.exception),
				"Row 4 of the shareholders: an Identifikationsnummer has eleven digits.",
			)
			self.assertNotIn(value, str(raised.exception))

	def test_a_wirtschafts_identifikationsnummer_is_de_and_nine_digits(self):
		self.assertEqual(normalized_wid_nr(" de 123 456 789 ", 1), WID_NR)
		self.assertIsNone(normalized_wid_nr(None, 1))
		for value in ("DE12345678", "AT123456789", "DE123456789-00001"):
			with self.subTest(value=value), self.assertRaises(SettingsError) as raised:
				normalized_wid_nr(value, 2)
			self.assertNotIn(value, str(raised.exception))
		self.assertEqual(
			str(raised.exception),
			"Row 2 of the shareholders: a Wirtschafts-Identifikationsnummer is DE and nine digits, without the "
			"five-digit suffix.",
		)

	def test_the_steuernummer_of_a_shareholder_in_the_13_digit_form_for_elster(self):
		self.assertEqual(elster_tax_number("123/456/78901", "Bayern", 1), "9123045678901")
		self.assertEqual(elster_tax_number("9123 0456 78901", None, 1), "9123045678901")
		for value in (None, "", " "):
			with self.subTest(value=value):
				self.assertIsNone(elster_tax_number(value, "Bayern", 1))

	def test_refuses_a_steuernummer_without_naming_it(self):
		with self.assertRaises(SettingsError) as raised:
			elster_tax_number("12/345/67890", "Bayern", 2)
		self.assertEqual(
			str(raised.exception),
			"Row 2 of the shareholders: the Steuernummer does not have the format FFF/BBB/UUUUP of Bayern.",
		)
		with self.assertRaises(SettingsError) as raised:
			elster_tax_number("123/456/78901", None, 3)
		self.assertEqual(
			str(raised.exception),
			"Row 3 of the shareholders: without its Bundesland the Steuernummer is the 13-digit form for ELSTER.",
		)
		with self.assertRaisesRegex(SettingsError, "Bavaria is not a Bundesland."):
			elster_tax_number("123/456/78901", "Bavaria", 1)


class CheckShareholdersTest(TestCase):
	def test_the_shares_add_up_to_99_to_100_percent_on_every_day(self):
		"""Rule 8931029 of the KSt 1: „nicht mehr als 100 % und nicht weniger als 99 %“."""
		check_shareholders(
			[
				shareholder(1, "Anna", "33.3333"),
				shareholder(2, "Bert", "33.3333"),
				shareholder(3, "Carl", "33.3333"),
			]
		)
		check_shareholders([shareholder(1, "Anna", "60"), shareholder(2, "Bert", "40")])
		with self.assertRaises(SettingsError) as raised:
			check_shareholders([shareholder(1, "Anna", "60"), shareholder(2, "Bert", "38.5")])
		self.assertEqual(
			str(raised.exception),
			"On 1. Januar 2026 the shares of the shareholders add up to 98.5 %; ELSTER takes 99 to 100 % (rule 8931029 "
			"of the KSt 1).",
		)
		with self.assertRaisesRegex(SettingsError, "add up to 100.0001 %"):
			check_shareholders([shareholder(1, "Anna", "60"), shareholder(2, "Bert", "40.0001")])

	def test_a_sale_during_the_year_keeps_the_shares_complete(self):
		check_shareholders(
			[
				shareholder(1, "Anna", "100", end=date(2026, 6, 30)),
				shareholder(2, "Bert", "100", start=date(2026, 7, 1)),
			]
		)
		with self.assertRaisesRegex(
			SettingsError, "On 1. Juli 2026 the shares of the shareholders add up to 50 %"
		):
			check_shareholders(
				[
					shareholder(1, "Anna", "100", end=date(2026, 6, 30)),
					shareholder(2, "Anna", "50", start=date(2026, 7, 1)),
					shareholder(3, "Bert", "50", start=date(2026, 8, 1)),
				]
			)

	def test_days_nobody_holds_shares_are_not_checked(self):
		check_shareholders([])
		check_shareholders(
			[
				shareholder(1, "Anna", "100", start=date(2026, 1, 1), end=date(2026, 3, 31)),
				shareholder(2, "Bert", "100", start=date(2026, 5, 1)),
			]
		)

	def test_a_shareholder_holds_one_share_at_a_time(self):
		"""Rule 8912155: „Besitzdauer bis“ may be empty only for the last holding period."""
		check_shareholders(
			[
				shareholder(1, "Anna", "100", end=date(2026, 6, 30)),
				shareholder(2, "anna ", "100", start=date(2026, 7, 1)),
			]
		)
		with self.assertRaises(SettingsError) as raised:
			check_shareholders(
				[
					shareholder(1, "Anna", "50"),
					shareholder(2, "Bert", "50"),
					shareholder(3, " ANNA", "50", start=date(2026, 7, 1)),
				]
			)
		self.assertEqual(
			str(raised.exception), "Rows 1 and 3 of the shareholders name Anna for the same days."
		)

	def test_the_shares_held_on_a_day(self):
		holders = [
			shareholder(1, "Anna", "60", end=date(2026, 6, 30)),
			shareholder(2, "Bert", "40"),
			shareholder(3, "Carl", "60", start=date(2026, 7, 1)),
		]
		self.assertEqual(share_total(holders, date(2026, 6, 30)), Decimal(100))
		self.assertEqual(share_total(holders, date(2025, 12, 31)), Decimal(0))
		self.assertEqual(
			[holder.name for holder in shareholders_on(holders, date(2026, 7, 1))], ["Bert", "Carl"]
		)


class DirectorTest(TestCase):
	def test_a_director_signs_unless_told_otherwise(self):
		director = Director(1, "Erika Mustermann", date(2026, 1, 1))
		self.assertTrue(director.signs)
		self.assertFalse(director.is_shareholder)
		self.assertEqual(director.period, Period(date(2026, 1, 1)))

	def test_an_office_ends_after_it_starts(self):
		with self.assertRaisesRegex(
			SettingsError,
			"Row 2 of the managing directors ends on 31. Dezember 2025, before its start on 1. Januar 2026.",
		):
			Director(2, "Erika Mustermann", date(2026, 1, 1), date(2025, 12, 31))

	def test_a_director_holds_one_office_at_a_time(self):
		directors = [
			Director(1, "Erika Mustermann", date(2026, 1, 1), date(2026, 3, 31)),
			Director(2, "Max Mustermann", date(2026, 1, 1)),
			Director(3, "Erika Mustermann", date(2026, 4, 1)),
		]
		check_directors(directors)
		with self.assertRaisesRegex(
			SettingsError, "Rows 2 and 4 of the managing directors name Max Mustermann"
		):
			check_directors([*directors, Director(4, "max mustermann", date(2026, 6, 1), date(2026, 6, 30))])

	def test_the_directors_on_a_day(self):
		directors = [
			Director(1, "Erika Mustermann", date(2026, 1, 1), date(2026, 3, 31)),
			Director(2, "Max Mustermann", date(2026, 3, 1)),
		]
		self.assertEqual([d.row for d in directors_on(directors, date(2026, 3, 15))], [1, 2])
		self.assertEqual([d.row for d in directors_on(directors, date(2026, 4, 1))], [2])


class GewerbesteuerTest(TestCase):
	def test_the_amtlicher_gemeindeschluessel_has_the_laenderschluessel_01_to_16_and_six_digits(self):
		"""E4101103 of Jahresdokumentation E21 2025: (01|02|…|16){1}[0-9]{6}."""
		for value, ags in (("09162000", "09162000"), (" 11 000 000 ", "11000000"), ("16055000", "16055000")):
			with self.subTest(value=value):
				self.assertEqual(normalized_ags(value), ags)
		for value in ("00162000", "17000000", "9162000", "091620001", "0916200x", "", None):
			with (
				self.subTest(value=value),
				self.assertRaisesRegex(SettingsError, "is not an Amtlicher Gemeindeschlüssel"),
			):
				normalized_ags(value)

	def test_the_minimum_hebesatz_is_200_and_280_from_2027(self):
		"""§ 16 Abs. 4 Satz 2 GewStG; Art. 8 Nr. 1 of the law of 29 June 2026 and § 36 Abs. 5b GewStG."""
		self.assertEqual(minimum_hebesatz(2025), Decimal(200))
		self.assertEqual(minimum_hebesatz(2026), Decimal(200))
		self.assertEqual(minimum_hebesatz(2027), Decimal(280))
		self.assertEqual(minimum_hebesatz(2030), Decimal(280))
		with self.assertRaises(SettingsError):
			minimum_hebesatz(26)

	def test_refuses_a_hebesatz_below_the_minimum_of_its_year(self):
		self.assertEqual(rate(year=2026, hebesatz="200").hebesatz, Decimal(200))
		self.assertEqual(rate(year=2027, hebesatz="280").hebesatz, Decimal(280))
		with self.assertRaises(SettingsError) as raised:
			rate(year=2027, hebesatz="250.0")
		self.assertEqual(
			str(raised.exception),
			"The Hebesatz of 09162000 for 2027 is 250 %; § 16 Abs. 4 Satz 2 GewStG sets at least 280 % for that year.",
		)
		for hebesatz in ("199.99", "NaN", "-Infinity"):
			with self.subTest(hebesatz=hebesatz), self.assertRaises(SettingsError):
				rate(hebesatz=hebesatz)

	def test_a_hebesatz_names_its_source(self):
		self.assertEqual(rate(source_date=date(2026, 2, 1)).source_date, date(2026, 2, 1))
		for source in ("", "  ", None):
			with (
				self.subTest(source=source),
				self.assertRaisesRegex(SettingsError, "The Hebesatz of 09162000 for 2026 needs its source"),
			):
				rate(source=source)

	def test_a_gemeinde_has_one_hebesatz_per_year(self):
		rates = [
			rate(year=2026),
			rate(year=2027, hebesatz="500"),
			rate(ags="09184119", year=2026, hebesatz="330"),
		]
		check_trade_tax_rates(rates)
		self.assertEqual(hebesatz_of(rates, "09162000", 2027).hebesatz, Decimal(500))
		self.assertIsNone(hebesatz_of(rates, "09162000", 2028))
		with self.assertRaisesRegex(SettingsError, "The Hebesatz of 09162000 for 2026 is entered twice."):
			check_trade_tax_rates([*rates, rate(ags="0916 2000", year=2026)])

	def test_a_betriebsstaette_in_a_gemeinde(self):
		place = establishment(ags="0916 2000", hebenummer="12/345")
		self.assertEqual((place.ags, place.period), ("09162000", Period(date(2026, 1, 1))))
		with self.assertRaisesRegex(SettingsError, "123 is not a German postal code"):
			establishment(postal_code="123")
		with self.assertRaisesRegex(
			SettingsError,
			"Row 2 of the Betriebsstätten ends on 31. Dezember 2025, before its start on 1. Januar 2026.",
		):
			establishment(row=2, end=date(2025, 12, 31))

	def test_the_betriebsstaetten_of_a_period(self):
		places = [
			establishment(1, end=date(2026, 3, 31)),
			establishment(
				2, ags="09184119", start=date(2026, 4, 1), municipality="Unterhaching", postal_code="82008"
			),
		]
		self.assertEqual(
			[place.row for place in establishments_in(places, date(2026, 1, 1), date(2026, 12, 31))], [1, 2]
		)
		self.assertEqual(
			[place.row for place in establishments_in(places, date(2027, 1, 1), date(2027, 12, 31))], [2]
		)
		self.assertEqual(establishments_in(places, date(2025, 1, 1), date(2025, 12, 31)), [])

	def test_a_betriebsstaette_is_entered_once_for_its_days(self):
		places = [establishment(1, end=date(2026, 3, 31)), establishment(2, start=date(2026, 4, 1))]
		check_establishments(places)
		check_establishments([*places, establishment(3, postal_code="80333", start=date(2026, 2, 1))])
		with self.assertRaisesRegex(
			SettingsError,
			"Rows 2 and 3 of the Betriebsstätten name the same Betriebsstätte in München for the same days.",
		):
			check_establishments([*places, establishment(3, start=date(2026, 6, 1), municipality="münchen ")])


class HoldingTest(TestCase):
	def test_a_holding_for_a_year_with_its_shares(self):
		holding = Holding(
			"Beispiel AG", 2026, Decimal("12.5"), Decimal(15), date(2020, 5, 4), identifier="DE0000000001"
		)
		self.assertEqual(
			(holding.percent_on_1_january, holding.percent_at_start_of_ez), (Decimal("12.5"), Decimal(15))
		)
		Holding("Beispiel AG", 2026, Decimal(0), Decimal(100), date(2026, 3, 1), date(2026, 3, 1))

	def test_a_share_lies_from_0_to_100(self):
		for field in ("percent_on_1_january", "percent_at_start_of_ez"):
			for percent in ("-0.1", "100.1", "NaN"):
				with (
					self.subTest(field=field, percent=percent),
					self.assertRaisesRegex(
						SettingsError, "The holding in Beispiel AG: a share in percent lies from 0 to 100"
					),
				):
					Holding("Beispiel AG", 2026, **{field: Decimal(percent)})

	def test_a_holding_is_sold_after_it_was_bought(self):
		with self.assertRaisesRegex(
			SettingsError,
			"The holding in Beispiel AG is sold on 1. März 2026, before it was bought on 2. März 2026.",
		):
			Holding("Beispiel AG", 2026, bought_on=date(2026, 3, 2), sold_on=date(2026, 3, 1))
		Holding("Beispiel AG", 2026, sold_on=date(2026, 3, 1))

	def test_the_year_has_four_digits(self):
		with self.assertRaisesRegex(SettingsError, "is not a four-digit year"):
			Holding("Beispiel AG", 26)

	def test_a_holding_has_one_row_per_year(self):
		holdings = [Holding("Beispiel AG", 2026), Holding("Beispiel AG", 2027), Holding("Muster GmbH", 2026)]
		check_holdings(holdings)
		self.assertEqual([h.name for h in holdings_of(holdings, 2026)], ["Beispiel AG", "Muster GmbH"])
		with self.assertRaisesRegex(SettingsError, "The holding in beispiel ag for 2026 is entered twice."):
			check_holdings([*holdings, Holding("beispiel ag", 2026)])


class PrepaymentTest(TestCase):
	def test_a_vorauszahlung_of_a_notice(self):
		payment = Prepayment(
			"GewSt", 2026, date(2026, 2, 15), Decimal("1250.00"), date(2025, 12, 1), "0916 2000"
		)
		self.assertIs(payment.tax, Tax.GEWST)
		self.assertEqual(payment.ags, "09162000")
		self.assertEqual([tax.value for tax in Tax], ["KSt", "SolZ", "GewSt"])

	def test_the_taxes_of_the_vorauszahlungen(self):
		with self.assertRaisesRegex(SettingsError, "Grundsteuer is not a tax of the Vorauszahlungen"):
			Prepayment("Grundsteuer", 2026, date(2026, 2, 15), Decimal(100))
		with self.assertRaisesRegex(SettingsError, "is not a four-digit year"):
			Prepayment(Tax.KST, 26, date(2026, 3, 10), Decimal(100))

	def test_the_amount_is_in_cents_of_at_least_0(self):
		Prepayment(Tax.SOLZ, 2026, date(2026, 3, 10), Decimal(0))
		for amount in ("-1", "10.001", "NaN"):
			with (
				self.subTest(amount=amount),
				self.assertRaisesRegex(
					SettingsError, "The Vorauszahlung KSt of 2026 due on 10. März 2026 is an amount in cents"
				),
			):
				Prepayment(Tax.KST, 2026, date(2026, 3, 10), Decimal(amount))
		with self.assertRaises(TypeError):
			Prepayment(Tax.KST, 2026, date(2026, 3, 10), 100.0)  # type: ignore[arg-type]

	def test_only_the_gewerbesteuer_goes_to_a_gemeinde(self):
		with self.assertRaises(SettingsError) as raised:
			Prepayment(Tax.KST, 2026, date(2026, 3, 10), Decimal(100), ags="09162000")
		self.assertEqual(raised.exception.template, AGS_ONLY_FOR_GEWERBESTEUER)
		with self.assertRaisesRegex(SettingsError, "is not an Amtlicher Gemeindeschlüssel"):
			Prepayment(Tax.GEWST, 2026, date(2026, 2, 15), Decimal(100), ags="1234")

	def test_a_notice_sets_a_vorauszahlung_once_per_due_date(self):
		payments = [
			Prepayment(Tax.KST, 2026, date(2026, 3, 10), Decimal(100)),
			Prepayment(Tax.KST, 2026, date(2026, 6, 10), Decimal(100)),
			Prepayment(Tax.SOLZ, 2026, date(2026, 3, 10), Decimal("5.50")),
			Prepayment(Tax.KST, 2027, date(2027, 3, 10), Decimal(200)),
		]
		check_prepayments(payments)
		self.assertEqual(
			[p.due_date for p in prepayments_of(payments, Tax.KST, 2026)],
			[date(2026, 3, 10), date(2026, 6, 10)],
		)
		with self.assertRaisesRegex(
			SettingsError, "The Vorauszahlung KSt of 2026 due on 10. Juni 2026 is entered twice."
		):
			check_prepayments([*payments, Prepayment(Tax.KST, 2026, date(2026, 6, 10), Decimal(50))])


class CarryForwardTest(TestCase):
	def test_the_kinds_of_carry_forwards(self):
		self.assertEqual(
			[kind.value for kind in CarryForwardKind],
			[
				"Loss Carried Forward (§ 10d EStG)",
				"Loss from Termingeschäfte (§ 15 Abs. 4 EStG)",
				"Donations Carried Forward (KSt)",
				"Fehlbetrag (§ 10a GewStG)",
				"Donations Carried Forward (GewSt)",
				"Einlagekonto (§ 27 KStG)",
				"Sonderausweis (§ 28 KStG)",
			],
		)
		with self.assertRaisesRegex(SettingsError, "Zinsvortrag is not a kind of carry-forward."):
			CarryForward("Zinsvortrag", date(2025, 12, 31), Decimal(0))

	def test_an_amount_in_cents_of_at_least_0(self):
		stated = CarryForward(
			"Einlagekonto (§ 27 KStG)", date(2025, 12, 31), Decimal(0), date(2026, 8, 1), True
		)
		self.assertIs(stated.kind, CarryForwardKind.EINLAGEKONTO)
		self.assertTrue(stated.confirmed)
		with self.assertRaisesRegex(
			SettingsError,
			r"Loss Carried Forward \(§ 10d EStG\) as of 31. Dezember 2025 is an amount in cents of at least 0, not -1.",
		):
			CarryForward(CarryForwardKind.LOSS, date(2025, 12, 31), Decimal("-1.00"))

	def test_a_kind_is_stated_once_per_day(self):
		stated = [
			CarryForward(CarryForwardKind.LOSS, date(2024, 12, 31), Decimal(5000)),
			CarryForward(CarryForwardKind.LOSS, date(2025, 12, 31), Decimal(3000)),
			CarryForward(CarryForwardKind.FEHLBETRAG, date(2025, 12, 31), Decimal(2000)),
		]
		check_carry_forwards(stated)
		with self.assertRaisesRegex(SettingsError, "as of 31. Dezember 2025 is entered twice."):
			check_carry_forwards(
				[*stated, CarryForward(CarryForwardKind.FEHLBETRAG, date(2025, 12, 31), Decimal(1))]
			)

	def test_the_latest_amount_stated_up_to_a_day(self):
		stated = [
			CarryForward(CarryForwardKind.LOSS, date(2025, 12, 31), Decimal(3000)),
			CarryForward(CarryForwardKind.LOSS, date(2024, 12, 31), Decimal(5000)),
			CarryForward(CarryForwardKind.FEHLBETRAG, date(2025, 12, 31), Decimal(2000)),
		]
		self.assertEqual(
			latest_carry_forward(stated, CarryForwardKind.LOSS, date(2025, 12, 31)).amount, Decimal(3000)
		)
		self.assertEqual(
			latest_carry_forward(stated, CarryForwardKind.LOSS, date(2025, 6, 30)).amount, Decimal(5000)
		)
		self.assertIsNone(latest_carry_forward(stated, CarryForwardKind.LOSS, date(2024, 1, 1)))
		self.assertIsNone(latest_carry_forward(stated, CarryForwardKind.SONDERAUSWEIS, date(2026, 1, 1)))


class SizeRecordTest(TestCase):
	def test_the_size_classes(self):
		self.assertEqual([size.value for size in SizeClass], ["Kleinst", "Klein", "Mittelgroß", "Groß"])
		with self.assertRaisesRegex(SettingsError, "Winzig is not a size class"):
			SizeRecord(date(2025, 12, 31), "Winzig", "Jahresabschluss 2025")

	def test_the_criteria_and_the_class_applied_with_its_source(self):
		record = SizeRecord(
			date(2025, 12, 31),
			"Kleinst",
			"Jahresabschluss 2025",
			Decimal("350000.00"),
			Decimal("800000.00"),
			Decimal("2.25"),
		)
		self.assertIs(record.size_class, SizeClass.KLEINST)
		SizeRecord(date(2025, 12, 31), SizeClass.KLEIN, "von Hand", Decimal(0), Decimal(0), Decimal(0))
		for source in ("", " ", None):
			with (
				self.subTest(source=source),
				self.assertRaisesRegex(
					SettingsError, "The size of the fiscal year ending on 31. Dezember 2025 needs its source."
				),
			):
				SizeRecord(date(2025, 12, 31), SizeClass.KLEIN, source)

	def test_no_criterion_is_negative(self):
		for criterion, values in (
			("Bilanzsumme", {"balance_sheet_total": Decimal(-1)}),
			("Umsatzerlöse", {"revenue": Decimal("-0.01")}),
			("Arbeitnehmer", {"employees": Decimal("NaN")}),
		):
			with (
				self.subTest(criterion=criterion),
				self.assertRaisesRegex(SettingsError, f"the {criterion} cannot be negative"),
			):
				SizeRecord(date(2025, 12, 31), SizeClass.KLEIN, "von Hand", **values)

	def test_a_fiscal_year_has_one_size(self):
		history = [
			SizeRecord(date(2024, 12, 31), SizeClass.KLEINST, "von Hand"),
			SizeRecord(date(2025, 12, 31), SizeClass.KLEIN, "Jahresabschluss 2025"),
		]
		check_size_history(history)
		self.assertIs(size_class_on(history, date(2025, 12, 31)), SizeClass.KLEIN)
		self.assertIsNone(size_class_on(history, date(2026, 12, 31)))
		with self.assertRaisesRegex(SettingsError, "The size of the fiscal year ending on 24. Dezember 2025"):
			check_size_history(
				[
					*history,
					SizeRecord(date(2025, 12, 24), SizeClass.KLEIN, "a"),
					SizeRecord(date(2025, 12, 24), SizeClass.KLEIN, "b"),
				]
			)


class EmploymentTypeTest(TestCase):
	def test_an_employment_type_is_listed_once(self):
		check_employment_types(["Apprentice", "Intern"])
		with self.assertRaisesRegex(SettingsError, "The Employment Type Apprentice is listed twice."):
			check_employment_types(["Apprentice", "Intern", "Apprentice"])


class SettingsErrorTest(TestCase):
	def test_keeps_the_template_and_its_values_for_the_translation(self):
		error = SettingsError(rules_module.TEXT_TOO_LONG, "Ort", 30, 29)
		self.assertEqual(str(error), "Ort has 30 characters; ELSTER takes at most 29.")
		self.assertEqual((error.template, error.values), (rules_module.TEXT_TOO_LONG, ("Ort", 30, 29)))
		self.assertIsInstance(error, ValueError)

	def test_messages_lists_every_template_of_the_module(self):
		templates = [
			value
			for name, value in vars(rules_module).items()
			if name.isupper() and isinstance(value, str) and value.endswith(".")
		]
		self.assertCountEqual(MESSAGES, templates)
		self.assertEqual(len(set(MESSAGES)), len(MESSAGES))

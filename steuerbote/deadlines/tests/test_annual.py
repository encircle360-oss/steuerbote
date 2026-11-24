"""The annual deadlines of a company: the Umsatzsteuer-, Körperschaftsteuer- and Gewerbesteuererklärung with and
without a Steuerberatung, after an early order of the Finanzamt and on a holiday, the E-Bilanz with the
Körperschaftsteuererklärung and the Eröffnungsbilanz of the founding year, and the Feststellung and the Offenlegung of
the Jahresabschluss by the closing day and the size class of the fiscal year; when an annual document files them, and
which DocType files which."""

from dataclasses import replace
from datetime import date
from unittest import TestCase

from steuerbote.deadlines.annual import (
	DOCTYPES,
	FIRST_YEAR,
	KINDS,
	OPENING_BALANCE,
	OPENING_BALANCE_FIELD,
	UPLOAD,
	AnnualDocType,
	AnnualDocument,
	AnnualRules,
	AnnualYear,
	Note,
	OpeningBalance,
	annual_due,
	annual_obligations,
	filing_day,
	year_obligations,
)
from steuerbote.deadlines.obligations import Kind, Obligation
from steuerbote.hgb.size import SizeClass
from steuerbote.jahresmeldung.lifecycle import FILED_VIA, Status
from steuerbote.steuerbote.doctype.annual_filing_settings import rules as settings

UST = Kind.UMSATZSTEUERERKLAERUNG
KST = Kind.KOERPERSCHAFTSTEUERERKLAERUNG
GEWST = Kind.GEWERBESTEUERERKLAERUNG
EBILANZ = Kind.E_BILANZ
FESTSTELLUNG = Kind.FESTSTELLUNG
OFFENLEGUNG = Kind.OFFENLEGUNG
# The year 2026 of a company without a Steuerberatung, whose fiscal year is the calendar year.
YEAR_2026 = AnnualYear(2026, date(2026, 12, 31), size_class=SizeClass.KLEIN)
# 31 July 2027 is a Saturday.
ERKLAERUNGEN_2026 = date(2027, 8, 2)
# The last day of February 2028, a leap year.
WITH_ADVISOR_2026 = date(2028, 2, 29)


def kinds_and_days(found) -> list[tuple[Kind, str, date]]:
	return [(item.kind, item.label, item.due) for item in found]


def small(fiscal_year_end: date) -> settings.SizeRecord:
	return settings.SizeRecord(fiscal_year_end, settings.SizeClass.KLEIN, "Jahresabschluss")


class YearObligationsTest(TestCase):
	def test_a_small_company_owes_six_filings_for_2026(self):
		self.assertEqual(
			year_obligations(YEAR_2026),
			[
				Obligation(UST, 2026, "2026", ERKLAERUNGEN_2026),
				Obligation(KST, 2026, "2026", ERKLAERUNGEN_2026),
				Obligation(GEWST, 2026, "2026", ERKLAERUNGEN_2026),
				Obligation(EBILANZ, 2026, "2026", ERKLAERUNGEN_2026, notes=(Note.WITH_KST,)),
				Obligation(FESTSTELLUNG, 2026, "2026", date(2027, 11, 30)),
				Obligation(OFFENLEGUNG, 2026, "2026", date(2027, 12, 31)),
			],
		)

	def test_the_erklaerungen_are_due_seven_months_after_the_year_on_the_next_working_day(self):
		self.assertEqual(date(2027, 7, 31).weekday(), 5)
		found = year_obligations(YEAR_2026)
		self.assertEqual(
			{item.due for item in found if item.kind in (UST, KST, GEWST, EBILANZ)}, {ERKLAERUNGEN_2026}
		)
		self.assertEqual(year_obligations(AnnualYear(2027, date(2027, 12, 31)))[0].due, date(2028, 7, 31))

	def test_a_holiday_of_the_company_moves_them_to_the_next_working_day(self):
		found = year_obligations(YEAR_2026, holidays={ERKLAERUNGEN_2026})
		self.assertEqual(
			kinds_and_days(found)[:4],
			[(kind, "2026", date(2027, 8, 3)) for kind in (UST, KST, GEWST, EBILANZ)],
		)

	def test_a_steuerberatung_moves_them_to_the_last_day_of_february_of_the_second_year(self):
		found = year_obligations(replace(YEAR_2026, advisor_prepares=True))
		self.assertEqual(
			[(item.kind, item.due, item.notes) for item in found[:4]],
			[
				(UST, WITH_ADVISOR_2026, (Note.ADVISOR,)),
				(KST, WITH_ADVISOR_2026, (Note.ADVISOR,)),
				(GEWST, WITH_ADVISOR_2026, (Note.ADVISOR,)),
				(EBILANZ, WITH_ADVISOR_2026, (Note.WITH_KST, Note.ADVISOR)),
			],
		)
		following = AnnualYear(2027, date(2027, 12, 31), advisor_prepares=True)
		self.assertEqual(year_obligations(following)[0].due, date(2029, 2, 28))

	def test_an_early_order_of_the_finanzamt_sets_the_day_of_every_erklaerung(self):
		year = replace(YEAR_2026, advisor_prepares=True, early_request=date(2027, 9, 15))
		self.assertEqual(
			[(item.kind, item.due, item.notes) for item in year_obligations(year)[:4]],
			[
				(UST, date(2027, 9, 15), (Note.EARLY_REQUEST,)),
				(KST, date(2027, 9, 15), (Note.EARLY_REQUEST,)),
				(GEWST, date(2027, 9, 15), (Note.EARLY_REQUEST,)),
				(EBILANZ, date(2027, 9, 15), (Note.WITH_KST, Note.EARLY_REQUEST)),
			],
		)

	def test_an_early_order_on_a_saturday_ends_on_monday(self):
		self.assertEqual(date(2027, 10, 16).weekday(), 5)
		year = replace(YEAR_2026, advisor_prepares=True, early_request=date(2027, 10, 16))
		self.assertEqual(year_obligations(year)[0].due, date(2027, 10, 18))

	def test_a_kleinunternehmer_owes_no_umsatzsteuererklaerung(self):
		found = year_obligations(replace(YEAR_2026, kleinunternehmer=True))
		self.assertEqual([item.kind for item in found], [KST, GEWST, EBILANZ, FESTSTELLUNG, OFFENLEGUNG])

	def test_the_founding_year_owes_the_eroeffnungsbilanz_with_the_e_bilanz(self):
		found = year_obligations(replace(YEAR_2026, founding=True))
		self.assertEqual(
			[
				(item.kind, item.period, item.label, item.due, item.notes)
				for item in found
				if item.kind is EBILANZ
			],
			[
				(EBILANZ, 2026, "2026", ERKLAERUNGEN_2026, (Note.WITH_KST,)),
				(
					EBILANZ,
					OpeningBalance(2026),
					"Eröffnungsbilanz 2026",
					ERKLAERUNGEN_2026,
					(Note.OPENING_BALANCE,),
				),
			],
		)

	def test_the_eroeffnungsbilanz_follows_the_day_of_the_e_bilanz(self):
		year = replace(YEAR_2026, founding=True, advisor_prepares=True)
		(opening,) = [item for item in year_obligations(year) if isinstance(item.period, OpeningBalance)]
		self.assertEqual(
			(opening.due, opening.notes), (WITH_ADVISOR_2026, (Note.OPENING_BALANCE, Note.ADVISOR))
		)

	def test_a_small_company_adopts_its_jahresabschluss_within_eleven_months(self):
		for size_class in (SizeClass.KLEINST, SizeClass.KLEIN):
			with self.subTest(size_class=size_class):
				found = year_obligations(replace(YEAR_2026, size_class=size_class))
				self.assertEqual(found[-2], Obligation(FESTSTELLUNG, 2026, "2026", date(2027, 11, 30)))

	def test_any_other_within_eight_months(self):
		for size_class in (SizeClass.MITTELGROSS, SizeClass.GROSS):
			with self.subTest(size_class=size_class):
				found = year_obligations(replace(YEAR_2026, size_class=size_class))
				self.assertEqual(found[-2], Obligation(FESTSTELLUNG, 2026, "2026", date(2027, 8, 31)))

	def test_without_a_size_class_eight_months_and_a_note(self):
		found = year_obligations(replace(YEAR_2026, size_class=None))
		self.assertEqual(
			found[-2], Obligation(FESTSTELLUNG, 2026, "2026", date(2027, 8, 31), notes=(Note.ASSUMED_CLASS,))
		)

	def test_the_offenlegung_is_due_one_year_after_the_closing_day(self):
		self.assertEqual(
			year_obligations(YEAR_2026)[-1], Obligation(OFFENLEGUNG, 2026, "2026", date(2027, 12, 31))
		)

	def test_a_day_of_the_jahresabschluss_on_a_weekend_stays_with_a_note(self):
		self.assertEqual(date(2028, 12, 31).weekday(), 6)
		found = year_obligations(AnnualYear(2027, date(2027, 12, 31), size_class=SizeClass.KLEIN))
		self.assertEqual(
			found[-1], Obligation(OFFENLEGUNG, 2027, "2027", date(2028, 12, 31), notes=(Note.ON_WEEKEND,))
		)
		self.assertEqual(date(2030, 8, 31).weekday(), 5)
		found = year_obligations(AnnualYear(2029, date(2029, 12, 31), size_class=SizeClass.GROSS))
		self.assertEqual(
			found[-2], Obligation(FESTSTELLUNG, 2029, "2029", date(2030, 8, 31), notes=(Note.ON_WEEKEND,))
		)

	def test_holidays_move_no_day_of_the_jahresabschluss(self):
		holidays = {date(2027, 11, 30), date(2027, 12, 31)}
		self.assertEqual(year_obligations(YEAR_2026, holidays)[-2:], year_obligations(YEAR_2026)[-2:])

	def test_an_exempt_subsidiary_discloses_nothing(self):
		found = year_obligations(replace(YEAR_2026, exempt_264_3=True))
		self.assertEqual([item.kind for item in found], [UST, KST, GEWST, EBILANZ, FESTSTELLUNG])

	def test_a_fiscal_year_ending_in_june_counts_from_its_closing_day(self):
		found = year_obligations(AnnualYear(2027, date(2027, 6, 30), size_class=SizeClass.GROSS))
		self.assertEqual(
			kinds_and_days(found)[-2:],
			[(FESTSTELLUNG, "2027", date(2028, 2, 29)), (OFFENLEGUNG, "2027", date(2028, 6, 30))],
		)
		self.assertEqual(found[0].due, date(2028, 7, 31))


class AnnualRulesTest(TestCase):
	def test_without_settings_a_year_is_the_calendar_year_without_steuerberatung_or_class(self):
		self.assertEqual(AnnualRules().year(2026), AnnualYear(2026, date(2026, 12, 31)))

	def test_takes_the_settings_of_the_year(self):
		rules = AnnualRules(
			years=(
				settings.YearSettings(2026, advisor_prepares=True),
				settings.YearSettings(
					2027, kleinunternehmer=True, exempt_264_3=True, exempt_264_3_reason="Konzern"
				),
			)
		)
		self.assertEqual(rules.year(2026), AnnualYear(2026, date(2026, 12, 31), advisor_prepares=True))
		self.assertEqual(
			rules.year(2027), AnnualYear(2027, date(2027, 12, 31), kleinunternehmer=True, exempt_264_3=True)
		)
		self.assertEqual(rules.year(2028), AnnualYear(2028, date(2028, 12, 31)))

	def test_the_earliest_early_order_of_the_year_holds_for_every_erklaerung(self):
		year = settings.YearSettings(
			2026,
			advisor_prepares=True,
			early_request_ust=date(2027, 10, 15),
			early_request_kst=date(2027, 9, 15),
			early_request_gewst=date(2027, 11, 2),
		)
		self.assertEqual(AnnualRules(years=(year,)).year(2026).early_request, date(2027, 9, 15))
		only_gewst = replace(year, early_request_ust=None, early_request_kst=None)
		self.assertEqual(AnnualRules(years=(only_gewst,)).year(2026).early_request, date(2027, 11, 2))

	def test_a_year_ends_with_the_last_fiscal_year_ending_in_it(self):
		rules = AnnualRules(fiscal_year_ends=(date(2026, 6, 30), date(2026, 12, 31), date(2028, 3, 31)))
		self.assertEqual(rules.year(2026).fiscal_year_end, date(2026, 12, 31))
		self.assertEqual(rules.year(2027).fiscal_year_end, date(2027, 12, 31))
		self.assertEqual(rules.year(2028).fiscal_year_end, date(2028, 3, 31))

	def test_the_size_class_is_the_one_the_settings_applied_on_the_closing_day(self):
		history = (
			small(date(2026, 12, 31)),
			settings.SizeRecord(date(2027, 12, 31), settings.SizeClass.GROSS, "Jahresabschluss"),
			settings.SizeRecord(date(2028, 12, 31), settings.SizeClass.KLEINST, "Jahresabschluss"),
		)
		rules = AnnualRules(size_history=history)
		self.assertEqual(
			[rules.year(year).size_class for year in (2026, 2027, 2028, 2029)],
			[SizeClass.KLEIN, SizeClass.GROSS, SizeClass.KLEINST, None],
		)
		self.assertIsNone(
			AnnualRules(size_history=history, fiscal_year_ends=(date(2026, 6, 30),)).year(2026).size_class
		)

	def test_every_class_of_the_settings_has_its_class_of_the_hgb(self):
		for size_class in settings.SizeClass:
			with self.subTest(size_class=size_class):
				record = settings.SizeRecord(date(2026, 12, 31), size_class, "Jahresabschluss")
				self.assertEqual(
					AnnualRules(size_history=(record,)).year(2026).size_class.name, size_class.name
				)

	def test_the_first_year_is_2026_or_the_year_of_the_founding(self):
		self.assertEqual(FIRST_YEAR, 2026)
		self.assertEqual(AnnualRules().first_year, 2026)
		self.assertEqual(AnnualRules(founded_on=date(2019, 5, 1)).first_year, 2026)
		self.assertEqual(AnnualRules(founded_on=date(2027, 3, 15)).first_year, 2027)

	def test_only_the_year_of_the_founding_from_the_first_year_on_is_a_founding_year(self):
		self.assertTrue(AnnualRules(founded_on=date(2027, 3, 15)).year(2027).founding)
		self.assertFalse(AnnualRules(founded_on=date(2027, 3, 15)).year(2028).founding)
		self.assertTrue(AnnualRules(founded_on=date(2026, 1, 2)).year(2026).founding)
		self.assertFalse(AnnualRules(founded_on=date(2025, 6, 1)).year(2026).founding)
		self.assertFalse(AnnualRules().year(2026).founding)

	def test_keeps_its_rows_as_tuples(self):
		rules = AnnualRules(
			years=[settings.YearSettings(2026)], fiscal_year_ends=[date(2026, 12, 31)], size_history=iter(())
		)
		self.assertEqual(
			(rules.years, rules.fiscal_year_ends, rules.size_history, rules.founded_on, rules.since),
			((settings.YearSettings(2026),), (date(2026, 12, 31),), (), None, None),
		)


class AnnualObligationsTest(TestCase):
	def test_lists_what_is_due_on_or_before_the_day_given_year_by_year(self):
		rules = AnnualRules(size_history=(small(date(2026, 12, 31)), small(date(2027, 12, 31))))
		self.assertEqual(annual_obligations(rules, date(2027, 8, 1)), [])
		self.assertEqual(
			kinds_and_days(annual_obligations(rules, date(2027, 8, 2))),
			[(kind, "2026", ERKLAERUNGEN_2026) for kind in (UST, KST, GEWST, EBILANZ)],
		)
		self.assertEqual(
			kinds_and_days(annual_obligations(rules, date(2028, 12, 31))),
			[
				*[(kind, "2026", ERKLAERUNGEN_2026) for kind in (UST, KST, GEWST, EBILANZ)],
				(FESTSTELLUNG, "2026", date(2027, 11, 30)),
				(OFFENLEGUNG, "2026", date(2027, 12, 31)),
				*[(kind, "2027", date(2028, 7, 31)) for kind in (UST, KST, GEWST, EBILANZ)],
				(FESTSTELLUNG, "2027", date(2028, 11, 30)),
				(OFFENLEGUNG, "2027", date(2028, 12, 31)),
			],
		)

	def test_passes_the_holidays_to_the_erklaerungen(self):
		found = annual_obligations(AnnualRules(), date(2027, 8, 31), holidays={ERKLAERUNGEN_2026})
		self.assertEqual({item.due for item in found if item.kind is not FESTSTELLUNG}, {date(2027, 8, 3)})

	def test_owes_nothing_before_the_first_year(self):
		found = annual_obligations(AnnualRules(founded_on=date(2027, 3, 15)), date(2028, 12, 31))
		self.assertEqual({item.label for item in found}, {"2027", "Eröffnungsbilanz 2027"})

	def test_the_kinds_are_the_six_annual_filings(self):
		self.assertEqual(KINDS, (UST, KST, GEWST, EBILANZ, FESTSTELLUNG, OFFENLEGUNG))


class AnnualDueTest(TestCase):
	def test_is_the_day_the_overview_lists(self):
		rules = AnnualRules(years=(settings.YearSettings(2026, advisor_prepares=True),))
		self.assertEqual(annual_due(rules, KST, 2026), WITH_ADVISOR_2026)
		self.assertEqual(annual_due(rules, OFFENLEGUNG, 2026), date(2027, 12, 31))
		self.assertEqual(annual_due(rules, UST, 2026, holidays={WITH_ADVISOR_2026}), date(2028, 3, 1))

	def test_is_none_for_what_the_year_does_not_owe(self):
		rules = AnnualRules(years=(settings.YearSettings(2026, kleinunternehmer=True),))
		self.assertIsNone(annual_due(rules, UST, 2026))
		self.assertIsNone(annual_due(rules, KST, 2025))
		self.assertIsNone(annual_due(rules, Kind.VORANMELDUNG, 2026))

	def test_the_eroeffnungsbilanz_only_in_the_founding_year(self):
		rules = AnnualRules(founded_on=date(2027, 3, 15))
		self.assertEqual(annual_due(rules, EBILANZ, 2027, opening_balance=True), date(2028, 7, 31))
		self.assertEqual(annual_due(rules, EBILANZ, 2027), date(2028, 7, 31))
		self.assertIsNone(annual_due(rules, EBILANZ, 2028, opening_balance=True))


class OpeningBalanceTest(TestCase):
	def test_is_named_after_its_year(self):
		self.assertEqual(OpeningBalance(2027).label, "Eröffnungsbilanz 2027")
		self.assertNotEqual(OpeningBalance(2027), 2027)


# The day a document was last changed, and the day of a filing before it.
MODIFIED = date(2027, 5, 4)
FILED = date(2027, 5, 3)


def document(status: Status = Status.DRAFT, docstatus: int = 0, **fields) -> AnnualDocument:
	return AnnualDocument("KSt-2026-00001", 2026, status, MODIFIED, docstatus=docstatus, **fields)


class ErklaerungFilingTest(TestCase):
	def test_a_draft_keeps_its_deadline_open(self):
		for status in (Status.DRAFT, Status.CALCULATED, Status.READY):
			with self.subTest(status=status):
				self.assertIsNone(filing_day(KST, document(status)))

	def test_a_submitted_erklaerung_is_filed_on_the_day_of_its_filing(self):
		self.assertEqual(filing_day(KST, document(Status.FILED, 1, filed_on=FILED)), FILED)
		self.assertEqual(filing_day(KST, document(Status.FILED, 1)), MODIFIED)

	def test_a_replaced_erklaerung_stays_filed(self):
		self.assertEqual(filing_day(UST, document(Status.REPLACED, 1, filed_on=FILED)), FILED)

	def test_a_draft_sent_through_steuerbote_is_filed_on_the_day_of_the_transmission(self):
		"""ELSTER accepted it, or the outcome is unknown, or its filing was noted outside Steuerbote, and the document
		stayed a draft or was cancelled since: the Finanzamt has it, or may have it."""
		self.assertEqual(filing_day(GEWST, document(sent_on=FILED)), FILED)
		self.assertEqual(filing_day(EBILANZ, document(Status.FILED, 2, sent_on=FILED)), FILED)
		self.assertEqual(filing_day(KST, document(Status.FILED, 1, filed_on=MODIFIED, sent_on=FILED)), FILED)

	def test_a_cancelled_erklaerung_without_a_transmission_files_nothing(self):
		self.assertIsNone(filing_day(KST, document(Status.FILED, 2, filed_on=FILED)))


class JahresabschlussFilingTest(TestCase):
	def test_a_submitted_jahresabschluss_is_festgestellt(self):
		for status in (Status.ADOPTED, Status.TRANSMITTED, Status.PUBLISHED):
			with self.subTest(status=status):
				self.assertEqual(filing_day(FESTSTELLUNG, document(status, 1)), MODIFIED)

	def test_a_draft_or_a_cancelled_one_is_not(self):
		self.assertIsNone(filing_day(FESTSTELLUNG, document(Status.CALCULATED)))
		self.assertIsNone(filing_day(FESTSTELLUNG, document(Status.ADOPTED, 2)))
		self.assertIsNone(
			filing_day(FESTSTELLUNG, document(Status.REPLACED, 2, filed_via=UPLOAD, filed_on=FILED))
		)

	def test_the_offenlegung_is_filed_once_it_is_uebermittelt_or_eingestellt(self):
		for status in (Status.TRANSMITTED, Status.PUBLISHED):
			with self.subTest(status=status):
				uploaded = document(status, 1, filed_via=UPLOAD, filed_on=FILED)
				self.assertEqual(filing_day(OFFENLEGUNG, uploaded), FILED)
				self.assertEqual(filing_day(OFFENLEGUNG, document(status, 1)), MODIFIED)

	def test_a_festgestellter_jahresabschluss_keeps_the_offenlegung_open(self):
		self.assertIsNone(filing_day(OFFENLEGUNG, document(Status.ADOPTED, 1)))
		self.assertIsNone(filing_day(OFFENLEGUNG, document(Status.CALCULATED)))

	def test_an_upload_keeps_the_offenlegung_filed_after_the_jahresabschluss_is_cancelled_or_replaced(self):
		"""§ 325 Abs. 4 Satz 2 HGB: the day of the transmission keeps the deadline; the register has the documents."""
		for status in (Status.TRANSMITTED, Status.REPLACED):
			with self.subTest(status=status):
				cancelled = document(status, 2, filed_via=UPLOAD, filed_on=FILED)
				self.assertEqual(filing_day(OFFENLEGUNG, cancelled), FILED)
		self.assertIsNone(filing_day(OFFENLEGUNG, document(Status.REPLACED, 2)))

	def test_refuses_a_kind_that_is_no_annual_filing(self):
		with self.assertRaisesRegex(ValueError, "Umsatzsteuer-Voranmeldung"):
			filing_day(Kind.VORANMELDUNG, document())


class AnnualDocumentTest(TestCase):
	def test_files_the_year_or_the_eroeffnungsbilanz_of_its_year(self):
		self.assertEqual(document().period, 2026)
		self.assertEqual(document(opening_balance=True).period, OpeningBalance(2026))

	def test_is_named_with_its_status_and_the_day_it_changed(self):
		found = document()
		self.assertEqual(
			(found.name, found.year, found.status, found.modified, found.docstatus),
			("KSt-2026-00001", 2026, Status.DRAFT, MODIFIED, 0),
		)
		self.assertEqual(
			(found.filed_via, found.filed_on, found.sent_on, found.opening_balance), (None, None, None, False)
		)


class RegistryTest(TestCase):
	def test_each_annual_doctype_files_its_kinds(self):
		self.assertEqual(
			dict(DOCTYPES),
			{
				"Annual VAT Return": AnnualDocType((UST,)),
				"Corporate Income Tax Return": AnnualDocType((KST,)),
				"Trade Tax Return": AnnualDocType((GEWST,)),
				"Electronic Balance Sheet": AnnualDocType(
					(EBILANZ,), opening_balance_field=OPENING_BALANCE_FIELD
				),
				"Annual Accounts": AnnualDocType((FESTSTELLUNG, OFFENLEGUNG)),
			},
		)

	def test_every_annual_kind_has_one_doctype(self):
		self.assertEqual(tuple(kind for entry in DOCTYPES.values() for kind in entry.kinds), KINDS)

	def test_the_e_bilanz_names_its_eroeffnungsbilanz_by_the_bilanzart(self):
		self.assertEqual((OPENING_BALANCE_FIELD, OPENING_BALANCE), ("statement_type", "Eröffnungsbilanz"))
		self.assertEqual(AnnualDocType((KST,)).opening_balance_field, None)

	def test_the_upload_to_the_unternehmensregister_is_a_way_of_filing(self):
		self.assertIn(UPLOAD, FILED_VIA)

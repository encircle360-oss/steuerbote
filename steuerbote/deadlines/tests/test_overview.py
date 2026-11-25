"""The deadlines of a company within a horizon: filed, open or missing, the overdue ones until they are filed, and
a Zusammenfassende Meldung only for a Meldezeitraum with something to report; with Annual Filing Settings also the
annual deadlines, from the annual documents the site has."""

from dataclasses import replace
from datetime import date
from unittest import TestCase

from steuerbote.deadlines import (
	DOCUMENT_TYPES,
	AnnualDocument,
	AnnualRules,
	CompanyRules,
	Deadline,
	Filing,
	Kind,
	Note,
	OpeningBalance,
	Status,
	annual_filings,
	new_document_values,
	upcoming,
)
from steuerbote.jahresmeldung.lifecycle import Status as DocumentStatus
from steuerbote.steuerbote.doctype.annual_filing_settings import rules as annual_settings
from steuerbote.steuerbote.doctype.vat_return_settings.rules import PeriodRule, Prepayment
from steuerbote.ustva.period import Period
from steuerbote.zm import rhythm as zm_rhythm
from steuerbote.zm.period import ReportingPeriod

# A Friday. The company files the Voranmeldung and the Zusammenfassende Meldung monthly from January 2026, without
# the Dauerfristverlängerung, and has kept its filings in Steuerbote since 1 November 2026.
TODAY = date(2026, 11, 20)
COMPANY = "Muster GmbH"
RULES = CompanyRules(
	COMPANY,
	period_rules=(PeriodRule(2026, "monthly"),),
	zm_rules=(zm_rhythm.Rule(2026, 1, "monthly"),),
	since=date(2026, 11, 1),
)
SEPTEMBER = Period.month(2026, 9)
OCTOBER = Period.month(2026, 10)
NOVEMBER = Period.month(2026, 11)
ZM_OCTOBER = ReportingPeriod.month(2026, 10)
VA = Kind.VORANMELDUNG
ZM = Kind.ZUSAMMENFASSENDE_MELDUNG
SVZ = Kind.SONDERVORAUSZAHLUNG
UST = Kind.UMSATZSTEUERERKLAERUNG
KST = Kind.KOERPERSCHAFTSTEUERERKLAERUNG
GEWST = Kind.GEWERBESTEUERERKLAERUNG
EBILANZ = Kind.E_BILANZ
FESTSTELLUNG = Kind.FESTSTELLUNG
OFFENLEGUNG = Kind.OFFENLEGUNG
# A Tuesday. The small company keeps its annual filings in Steuerbote since 1 January 2027 and has no Steuerberatung;
# 31 July 2027 is a Saturday.
SUMMER = date(2027, 7, 20)
ANNUAL = AnnualRules(
	size_history=(
		annual_settings.SizeRecord(date(2026, 12, 31), annual_settings.SizeClass.KLEIN, "Jahresabschluss"),
	),
	since=date(2027, 1, 1),
)
ANNUAL_RULES = CompanyRules(COMPANY, annual=ANNUAL)
ERKLAERUNGEN = date(2027, 8, 2)


def deadline(kind, period, label, due, status=Status.MISSING, document=None) -> Deadline:
	return Deadline(kind, COMPANY, label, due, DOCUMENT_TYPES[kind], document, status, period)


def periods(found) -> list:
	return [item.period for item in found]


class UpcomingTest(TestCase):
	def test_lists_the_deadlines_up_to_the_horizon_by_due_date(self):
		self.assertEqual(
			upcoming(RULES, (), TODAY, 30),
			[
				deadline(VA, OCTOBER, "Oktober 2026", date(2026, 11, 10)),
				deadline(ZM, ZM_OCTOBER, "Oktober 2026", date(2026, 11, 25)),
				deadline(VA, NOVEMBER, "November 2026", date(2026, 12, 10)),
			],
		)

	def test_counts_the_days_left_until_each_deadline(self):
		self.assertEqual([item.days_left(TODAY) for item in upcoming(RULES, (), TODAY, 30)], [-10, 5, 20])

	def test_the_horizon_includes_its_last_day(self):
		self.assertIn(NOVEMBER, periods(upcoming(RULES, (), TODAY, 20)))
		self.assertNotIn(NOVEMBER, periods(upcoming(RULES, (), TODAY, 19)))

	def test_a_horizon_of_no_days_lists_what_is_due_today_and_what_is_overdue(self):
		self.assertEqual(periods(upcoming(RULES, (), date(2026, 11, 25), 0)), [OCTOBER, ZM_OCTOBER])

	def test_refuses_a_horizon_that_is_no_number_of_days(self):
		for horizon in (-1, True, 1.5, "30", None):
			with self.subTest(horizon=horizon), self.assertRaisesRegex(ValueError, "horizon"):
				upcoming(RULES, (), TODAY, horizon)

	def test_the_holidays_of_the_company_move_its_deadlines(self):
		found = upcoming(RULES, (), TODAY, 30, holidays={date(2026, 12, 10)})
		self.assertEqual(found[-1], deadline(VA, NOVEMBER, "November 2026", date(2026, 12, 11)))

	def test_the_sondervorauszahlung_follows_the_voranmeldung_due_on_the_same_day(self):
		rules = CompanyRules(
			COMPANY,
			period_rules=(PeriodRule(2026, "monthly"),),
			prepayments=(Prepayment(2026, True), Prepayment(2027, True)),
			since=date(2027, 2, 1),
		)
		self.assertEqual(
			upcoming(rules, (), date(2027, 2, 1), 9),
			[
				deadline(VA, Period.month(2026, 12), "Dezember 2026", date(2027, 2, 10)),
				deadline(SVZ, 2027, "2027", date(2027, 2, 10)),
			],
		)


class StatusTest(TestCase):
	def test_a_document_with_the_filing_mark_files_its_deadline(self):
		filings = [Filing(VA, NOVEMBER, "UStVA-2026-00011", filed_on=date(2026, 11, 19))]
		self.assertEqual(
			upcoming(RULES, filings, TODAY, 30)[-1],
			deadline(VA, NOVEMBER, "November 2026", date(2026, 12, 10), Status.FILED, "UStVA-2026-00011"),
		)

	def test_a_document_without_it_keeps_the_deadline_open(self):
		filings = [Filing(ZM, ZM_OCTOBER, "ZM-2026-00010")]
		self.assertEqual(
			upcoming(RULES, filings, TODAY, 30)[1],
			deadline(ZM, ZM_OCTOBER, "Oktober 2026", date(2026, 11, 25), Status.OPEN, "ZM-2026-00010"),
		)

	def test_the_first_filed_document_of_a_period_files_it_before_any_draft(self):
		filings = [
			Filing(VA, NOVEMBER, "UStVA-2026-00013"),
			Filing(VA, NOVEMBER, "UStVA-2026-00012", filed_on=date(2026, 11, 19)),
			Filing(VA, NOVEMBER, "UStVA-2026-00011", filed_on=date(2026, 11, 18)),
		]
		found = upcoming(RULES, filings, TODAY, 30)[-1]
		self.assertEqual((found.status, found.document_name), (Status.FILED, "UStVA-2026-00012"))

	def test_the_latest_document_keeps_a_deadline_open(self):
		filings = [Filing(VA, NOVEMBER, "UStVA-2026-00012"), Filing(VA, NOVEMBER, "UStVA-2026-00011")]
		found = upcoming(RULES, filings, TODAY, 30)[-1]
		self.assertEqual((found.status, found.document_name), (Status.OPEN, "UStVA-2026-00012"))

	def test_a_deadline_filed_ahead_of_time_stays_in_the_list(self):
		filings = [Filing(ZM, ZM_OCTOBER, "ZM-2026-00010", filed_on=date(2026, 11, 3))]
		self.assertIn(
			deadline(ZM, ZM_OCTOBER, "Oktober 2026", date(2026, 11, 25), Status.FILED, "ZM-2026-00010"),
			upcoming(RULES, filings, TODAY, 30),
		)

	def test_a_document_of_a_period_the_rules_do_not_owe_files_nothing(self):
		filings = [Filing(VA, Period.quarter(2026, 4), "UStVA-2026-00040", filed_on=date(2026, 11, 19))]
		self.assertEqual(upcoming(RULES, filings, TODAY, 30), upcoming(RULES, (), TODAY, 30))

	def test_the_status_reads_the_same_in_every_language(self):
		self.assertEqual([status.value for status in Status], ["Abgegeben", "Offen", "Fehlt"])


class OverdueTest(TestCase):
	def test_an_overdue_deadline_stays_until_it_is_filed(self):
		draft = [Filing(VA, OCTOBER, "UStVA-2026-00010")]
		self.assertEqual(
			upcoming(RULES, draft, TODAY, 30)[0],
			deadline(VA, OCTOBER, "Oktober 2026", date(2026, 11, 10), Status.OPEN, "UStVA-2026-00010"),
		)
		filed = [Filing(VA, OCTOBER, "UStVA-2026-00010", filed_on=date(2026, 11, 12))]
		self.assertEqual(periods(upcoming(RULES, filed, TODAY, 30)), [ZM_OCTOBER, NOVEMBER])

	def test_an_overdue_deadline_without_a_document_from_before_the_settings_is_left_out(self):
		self.assertNotIn(SEPTEMBER, periods(upcoming(RULES, (), TODAY, 30)))
		self.assertIn(OCTOBER, periods(upcoming(replace(RULES, since=date(2026, 11, 10)), (), TODAY, 30)))
		self.assertNotIn(OCTOBER, periods(upcoming(replace(RULES, since=date(2026, 11, 11)), (), TODAY, 30)))

	def test_an_overdue_deadline_from_before_the_settings_stays_with_its_document(self):
		found = upcoming(RULES, [Filing(VA, SEPTEMBER, "UStVA-2026-00009")], TODAY, 30)
		self.assertEqual(
			found[0],
			deadline(VA, SEPTEMBER, "September 2026", date(2026, 10, 12), Status.OPEN, "UStVA-2026-00009"),
		)

	def test_without_the_day_of_the_settings_every_overdue_deadline_stays(self):
		found = upcoming(replace(RULES, since=None), (), TODAY, 30)
		self.assertEqual(
			[item.period_label for item in found if item.kind is VA][:2], ["Januar 2026", "Februar 2026"]
		)
		self.assertEqual(len([item for item in found if item.kind is ZM]), 10)


class BeforeTheStartTest(TestCase):
	"""What lies before the start of the books in Steuerbote was filed outside it (steuerbote/setup/start.py): no
	deadline of that time is listed, nor is the Steuerbote's to file."""

	def test_no_voranmeldung_or_zusammenfassende_meldung_before_the_start(self):
		rules = replace(RULES, since=None, books_start=date(2026, 11, 1))
		self.assertEqual(periods(upcoming(rules, (), TODAY, 30)), [NOVEMBER])

	def test_the_december_before_a_start_in_january_is_left_to_the_filing_outside(self):
		rules = CompanyRules(
			COMPANY,
			period_rules=(PeriodRule(2026, "monthly"),),
			prepayments=(Prepayment(2026, True), Prepayment(2027, True)),
			books_start=date(2027, 1, 1),
		)
		self.assertEqual(
			upcoming(rules, (), date(2027, 2, 1), 9), [deadline(SVZ, 2027, "2027", date(2027, 2, 10))]
		)

	def test_no_annual_filing_of_a_year_before_the_start(self):
		self.assertTrue(upcoming(ANNUAL_RULES, (), SUMMER, 30))
		self.assertEqual(upcoming(replace(ANNUAL_RULES, books_start=date(2027, 1, 1)), (), SUMMER, 30), [])
		self.assertTrue(upcoming(replace(ANNUAL_RULES, books_start=date(2026, 1, 1)), (), SUMMER, 30))


class ReportableTest(TestCase):
	def test_a_zusammenfassende_meldung_without_a_document_is_due_only_with_something_to_report(self):
		asked = []

		def nothing_to_report(coverage: zm_rhythm.Coverage) -> bool:
			asked.append(coverage)
			return False

		found = upcoming(RULES, (), TODAY, 30, reportable=nothing_to_report)
		self.assertEqual(periods(found), [OCTOBER, NOVEMBER])
		self.assertEqual(asked, [zm_rhythm.coverage(RULES.zm_rules, ZM_OCTOBER)])

	def test_a_meldezeitraum_with_something_to_report_is_due(self):
		found = upcoming(RULES, (), TODAY, 30, reportable=lambda coverage: True)
		self.assertEqual(found, upcoming(RULES, (), TODAY, 30))

	def test_a_zusammenfassende_meldung_with_a_document_is_listed_whatever_there_is_to_report(self):
		filings = [Filing(ZM, ZM_OCTOBER, "ZM-2026-00010")]
		found = upcoming(RULES, filings, TODAY, 30, reportable=lambda coverage: False)
		self.assertEqual(
			found[1],
			deadline(ZM, ZM_OCTOBER, "Oktober 2026", date(2026, 11, 25), Status.OPEN, "ZM-2026-00010"),
		)


class CompanyRulesTest(TestCase):
	def test_keeps_the_rules_as_tuples(self):
		rules = CompanyRules(
			COMPANY, period_rules=[PeriodRule(2026, "monthly")], prepayments=[], zm_rules=iter(())
		)
		self.assertEqual(
			(rules.period_rules, rules.prepayments, rules.zm_rules, rules.since),
			((PeriodRule(2026, "monthly"),), (), (), None),
		)

	def test_each_kind_is_filed_with_its_doctype(self):
		self.assertEqual(
			dict(DOCUMENT_TYPES),
			{
				VA: "VAT Return",
				ZM: "Recapitulative Statement",
				SVZ: "VAT Return Extension",
				UST: "Annual VAT Return",
				KST: "Corporate Income Tax Return",
				GEWST: "Trade Tax Return",
				EBILANZ: "Electronic Balance Sheet",
				FESTSTELLUNG: "Annual Accounts",
				OFFENLEGUNG: "Annual Accounts",
			},
		)

	def test_has_no_annual_rules_without_annual_filing_settings(self):
		self.assertIsNone(CompanyRules(COMPANY).annual)
		self.assertIs(ANNUAL_RULES.annual, ANNUAL)


class NewDocumentValuesTest(TestCase):
	def test_a_voranmeldung_takes_the_year_the_rhythm_and_the_number_of_its_period(self):
		self.assertEqual(
			new_document_values(deadline(VA, NOVEMBER, "November 2026", date(2026, 12, 10))),
			{"company": COMPANY, "year": 2026, "rhythm": "monthly", "period_index": 11},
		)
		quarter = Period.quarter(2026, 4)
		self.assertEqual(
			new_document_values(deadline(VA, quarter, quarter.label, date(2027, 1, 11))),
			{"company": COMPANY, "year": 2026, "rhythm": "quarterly", "period_index": 4},
		)

	def test_a_zusammenfassende_meldung_takes_the_kind_and_the_number_of_its_meldezeitraum(self):
		cases = (
			(ReportingPeriod.month(2026, 10), {"period_kind": "month", "period_index": 10}),
			(ReportingPeriod.two_months(2026, 2), {"period_kind": "two_months", "period_index": 2}),
			(ReportingPeriod.quarter(2026, 4), {"period_kind": "quarter", "period_index": 4}),
			(ReportingPeriod.calendar_year(2026), {"period_kind": "year"}),
		)
		for period, values in cases:
			with self.subTest(period=period.label):
				self.assertEqual(
					new_document_values(deadline(ZM, period, period.label, period.deadline())),
					{"company": COMPANY, "year": 2026, **values},
				)

	def test_a_sondervorauszahlung_takes_its_year(self):
		self.assertEqual(
			new_document_values(deadline(SVZ, 2027, "2027", date(2027, 2, 10))),
			{"company": COMPANY, "year": 2027},
		)


class AnnualDeadlinesTest(TestCase):
	def test_lists_the_annual_deadlines_of_the_annual_filing_settings(self):
		self.assertEqual(
			upcoming(ANNUAL_RULES, (), SUMMER, 30),
			[
				deadline(UST, 2026, "2026", ERKLAERUNGEN),
				deadline(KST, 2026, "2026", ERKLAERUNGEN),
				deadline(GEWST, 2026, "2026", ERKLAERUNGEN),
				replace(deadline(EBILANZ, 2026, "2026", ERKLAERUNGEN), notes=(Note.WITH_KST,)),
			],
		)
		self.assertEqual(
			[(item.kind, item.due) for item in upcoming(ANNUAL_RULES, (), SUMMER, 165)[4:]],
			[(FESTSTELLUNG, date(2027, 11, 30)), (OFFENLEGUNG, date(2027, 12, 31))],
		)

	def test_sets_them_beside_the_voranmeldungen_by_due_date(self):
		rules = replace(ANNUAL_RULES, period_rules=(PeriodRule(2026, "monthly"),), since=date(2027, 7, 1))
		found = upcoming(rules, (), SUMMER, 30)
		self.assertEqual(
			[(item.kind, item.period_label, item.due) for item in found],
			[
				(VA, "Juni 2027", date(2027, 7, 12)),
				*[(kind, "2026", ERKLAERUNGEN) for kind in (UST, KST, GEWST, EBILANZ)],
				(VA, "Juli 2027", date(2027, 8, 10)),
			],
		)

	def test_the_day_of_the_annual_filing_settings_leaves_out_what_was_overdue_before_them(self):
		autumn = date(2027, 9, 1)
		self.assertEqual(len(upcoming(ANNUAL_RULES, (), autumn, 0)), 4)
		late = replace(ANNUAL_RULES, annual=replace(ANNUAL, since=date(2027, 8, 3)))
		self.assertEqual(upcoming(late, (), autumn, 0), [])
		draft = [Filing(KST, 2026, "KSt-2026-00001", document_status=DocumentStatus.CALCULATED)]
		self.assertEqual([item.kind for item in upcoming(late, draft, autumn, 0)], [KST])

	def test_the_day_of_the_vat_return_settings_leaves_the_annual_deadlines_alone(self):
		rules = replace(ANNUAL_RULES, since=date(2027, 9, 1))
		self.assertEqual(len(upcoming(rules, (), date(2027, 9, 1), 0)), 4)

	def test_leaves_out_a_kind_whose_doctype_the_site_lacks(self):
		document_types = {KST: "Steuerbote Test Annual Filing", VA: "VAT Return"}
		found = upcoming(ANNUAL_RULES, (), SUMMER, 30, document_types=document_types)
		self.assertEqual(
			[(item.kind, item.document_type) for item in found], [(KST, "Steuerbote Test Annual Filing")]
		)

	def test_a_document_keeps_its_deadline_open_with_its_status(self):
		filings = [Filing(KST, 2026, "KSt-2026-00001", document_status=DocumentStatus.READY)]
		found = upcoming(ANNUAL_RULES, filings, SUMMER, 30)[1]
		self.assertEqual(
			found,
			replace(
				deadline(KST, 2026, "2026", ERKLAERUNGEN, Status.OPEN, "KSt-2026-00001"),
				document_status=DocumentStatus.READY,
			),
		)

	def test_a_filed_document_files_its_deadline_with_its_status(self):
		filings = [
			Filing(GEWST, 2026, "GewSt-2026-00002", document_status=DocumentStatus.DRAFT),
			Filing(GEWST, 2026, "GewSt-2026-00001", date(2027, 7, 1), DocumentStatus.FILED),
		]
		found = upcoming(ANNUAL_RULES, filings, SUMMER, 30)[2]
		self.assertEqual(
			(found.status, found.document_name, found.document_status),
			(Status.FILED, "GewSt-2026-00001", DocumentStatus.FILED),
		)

	def test_the_founding_year_lists_the_eroeffnungsbilanz_beside_the_e_bilanz(self):
		rules = CompanyRules(COMPANY, annual=AnnualRules(founded_on=date(2026, 4, 1)))
		filings = [
			Filing(EBILANZ, OpeningBalance(2026), "EB-2026-00001", date(2027, 6, 1), DocumentStatus.FILED)
		]
		found = [item for item in upcoming(rules, filings, SUMMER, 30) if item.kind is EBILANZ]
		self.assertEqual(
			[(item.period_label, item.status, item.document_name, item.notes) for item in found],
			[
				("2026", Status.MISSING, None, (Note.WITH_KST,)),
				("Eröffnungsbilanz 2026", Status.FILED, "EB-2026-00001", (Note.OPENING_BALANCE,)),
			],
		)

	def test_the_notes_of_the_jahresabschluss_come_with_its_deadlines(self):
		rules = CompanyRules(COMPANY, annual=AnnualRules())
		found = upcoming(rules, (), SUMMER, 60)
		self.assertEqual((found[-1].kind, found[-1].notes), (FESTSTELLUNG, (Note.ASSUMED_CLASS,)))

	def test_a_deadline_has_no_document_status_or_notes_unless_given(self):
		found = deadline(VA, NOVEMBER, "November 2026", date(2026, 12, 10))
		self.assertEqual((found.document_status, found.notes), (None, ()))
		self.assertIsNone(Filing(VA, NOVEMBER, "UStVA-2026-00011").document_status)


# A document of the annual filings as the site gives it, changed last on 4 May 2027.
MODIFIED = date(2027, 5, 4)


def annual_document(name: str, status: str, docstatus: int = 0, **fields) -> AnnualDocument:
	return AnnualDocument(name, 2026, status, MODIFIED, docstatus=docstatus, **fields)


class AnnualFilingsTest(TestCase):
	def test_a_document_files_each_kind_of_its_doctype(self):
		accounts = annual_document("JA-2026-00001", DocumentStatus.ADOPTED, 1)
		self.assertEqual(
			annual_filings((FESTSTELLUNG, OFFENLEGUNG), [accounts]),
			[
				Filing(FESTSTELLUNG, 2026, "JA-2026-00001", MODIFIED, DocumentStatus.ADOPTED),
				Filing(OFFENLEGUNG, 2026, "JA-2026-00001", None, DocumentStatus.ADOPTED),
			],
		)

	def test_keeps_the_order_of_the_documents(self):
		documents = [
			annual_document("KSt-2026-00002", DocumentStatus.DRAFT),
			annual_document("KSt-2026-00001", DocumentStatus.FILED, 1, filed_on=date(2027, 5, 2)),
		]
		self.assertEqual(
			annual_filings((KST,), documents),
			[
				Filing(KST, 2026, "KSt-2026-00002", None, DocumentStatus.DRAFT),
				Filing(KST, 2026, "KSt-2026-00001", date(2027, 5, 2), DocumentStatus.FILED),
			],
		)

	def test_a_cancelled_document_counts_only_where_it_filed(self):
		cancelled = annual_document(
			"JA-2026-00001", DocumentStatus.REPLACED, 2, filed_via="upload", filed_on=date(2027, 10, 1)
		)
		self.assertEqual(
			annual_filings((FESTSTELLUNG, OFFENLEGUNG), [cancelled]),
			[Filing(OFFENLEGUNG, 2026, "JA-2026-00001", date(2027, 10, 1), DocumentStatus.REPLACED)],
		)
		self.assertEqual(
			annual_filings((KST,), [annual_document("KSt-2026-00001", DocumentStatus.FILED, 2)]), []
		)

	def test_an_eroeffnungsbilanz_files_its_own_period(self):
		opening = annual_document("EB-2026-00001", DocumentStatus.FILED, 1, opening_balance=True)
		self.assertEqual(
			annual_filings((EBILANZ,), [opening]),
			[Filing(EBILANZ, OpeningBalance(2026), "EB-2026-00001", MODIFIED, DocumentStatus.FILED)],
		)


class NewAnnualDocumentValuesTest(TestCase):
	def test_an_annual_document_takes_its_year(self):
		for kind in (UST, KST, GEWST, EBILANZ, FESTSTELLUNG, OFFENLEGUNG):
			with self.subTest(kind=kind):
				self.assertEqual(
					new_document_values(deadline(kind, 2026, "2026", ERKLAERUNGEN)),
					{"company": COMPANY, "year": 2026},
				)

	def test_the_eroeffnungsbilanz_takes_its_bilanzart(self):
		opening = OpeningBalance(2026)
		self.assertEqual(
			new_document_values(deadline(EBILANZ, opening, opening.label, ERKLAERUNGEN)),
			{"company": COMPANY, "year": 2026, "statement_type": "Eröffnungsbilanz"},
		)


class AnnualSizeClassTest(TestCase):
	def test_a_large_company_adopts_within_eight_months(self):
		history = (
			annual_settings.SizeRecord(date(2026, 12, 31), annual_settings.SizeClass.GROSS, "Prüfbericht"),
		)
		rules = CompanyRules(COMPANY, annual=AnnualRules(size_history=history))
		(found,) = [item for item in upcoming(rules, (), SUMMER, 60) if item.kind is FESTSTELLUNG]
		self.assertEqual((found.due, found.notes), (date(2027, 8, 31), ()))

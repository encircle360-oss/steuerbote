from unittest import TestCase

from steuerbote.jahresmeldung.lifecycle import (
	ACCOUNTS,
	FILED_VIA,
	FILING,
	Event,
	LifecycleError,
	Other,
	Problem,
	StandardField,
	Status,
	check_correction,
	field_problems,
	fit_for_filing,
	refuse_second_draft,
	refuse_second_filing,
	standard_fields,
)

DOCTYPE = "Annual VAT Return"


class StatusesTest(TestCase):
	def test_an_erklaerung_and_the_e_bilanz_go_from_entwurf_to_abgegeben(self):
		self.assertEqual(
			FILING.statuses,
			(Status.DRAFT, Status.CALCULATED, Status.READY, Status.FILED, Status.REPLACED),
		)
		self.assertEqual(FILING.options, "Entwurf\nBerechnet\nBereit\nAbgegeben\nErsetzt")

	def test_the_jahresabschluss_goes_from_entwurf_to_eingestellt(self):
		self.assertEqual(
			ACCOUNTS.options, "Entwurf\nBerechnet\nFestgestellt\nÜbermittelt\nEingestellt\nErsetzt"
		)

	def test_the_statuses_read_as_the_form_names_them(self):
		self.assertEqual(
			[status.value for status in Status],
			[
				"Entwurf",
				"Berechnet",
				"Bereit",
				"Abgegeben",
				"Ersetzt",
				"Festgestellt",
				"Übermittelt",
				"Eingestellt",
			],
		)

	def test_the_statuses_that_count_as_filed(self):
		self.assertEqual(FILING.filings, (Status.FILED,))
		self.assertEqual(ACCOUNTS.filings, (Status.ADOPTED, Status.TRANSMITTED, Status.PUBLISHED))

	def test_the_statuses_of_a_calculated_document(self):
		self.assertEqual(FILING.calculated, (Status.CALCULATED, Status.READY))
		self.assertEqual(ACCOUNTS.calculated, (Status.CALCULATED,))

	def test_buchen_alone_files_no_erklaerung_and_adopts_the_jahresabschluss(self):
		self.assertFalse(FILING.submitted_by_hand)
		self.assertTrue(ACCOUNTS.submitted_by_hand)

	def test_nothing_filed_with_the_finanzamt_is_cancelled_while_the_jahresabschluss_is_cancelled_and_amended(
		self,
	):
		self.assertFalse(FILING.cancellable)
		self.assertTrue(ACCOUNTS.cancellable)


class MovesTest(TestCase):
	def test_berechnen_makes_a_document_ready_or_calculated(self):
		for status in (Status.DRAFT, Status.CALCULATED, Status.READY):
			with self.subTest(status=status):
				self.assertIs(FILING.move(status, Event.CALCULATE, ready=True), Status.READY)
				self.assertIs(FILING.move(status, Event.CALCULATE, ready=False), Status.CALCULATED)

	def test_the_jahresabschluss_is_calculated_whether_ready_or_not(self):
		for ready in (True, False):
			with self.subTest(ready=ready):
				self.assertIs(ACCOUNTS.move(Status.DRAFT, Event.CALCULATE, ready=ready), Status.CALCULATED)
				self.assertIs(
					ACCOUNTS.move(Status.CALCULATED, Event.CALCULATE, ready=ready), Status.CALCULATED
				)

	def test_a_change_of_what_berechnen_checked_leaves_a_document_calculated(self):
		for status in (Status.CALCULATED, Status.READY):
			with self.subTest(status=status):
				self.assertIs(FILING.move(status, Event.CHANGE), Status.CALCULATED)
		self.assertIs(FILING.move(Status.DRAFT, Event.CHANGE), Status.DRAFT)

	def test_another_key_discards_the_calculation(self):
		for status in (Status.DRAFT, Status.CALCULATED, Status.READY):
			with self.subTest(status=status):
				self.assertIs(FILING.move(status, Event.DISCARD), Status.DRAFT)

	def test_filing_files_a_calculated_document(self):
		self.assertIs(FILING.move(Status.CALCULATED, Event.FILE), Status.FILED)
		self.assertIs(FILING.move(Status.READY, Event.FILE), Status.FILED)
		self.assertIs(ACCOUNTS.move(Status.CALCULATED, Event.FILE), Status.ADOPTED)

	def test_a_draft_is_calculated_before_it_is_filed(self):
		with self.assertRaises(LifecycleError) as raised:
			FILING.move(Status.DRAFT, Event.FILE)
		self.assertIs(raised.exception.problem, Problem.NOT_CALCULATED)

	def test_the_jahresabschluss_is_transmitted_and_then_eingestellt(self):
		self.assertIs(ACCOUNTS.move(Status.ADOPTED, Event.TRANSMIT), Status.TRANSMITTED)
		self.assertIs(ACCOUNTS.move(Status.TRANSMITTED, Event.PUBLISH), Status.PUBLISHED)

	def test_only_a_transmitted_jahresabschluss_is_eingestellt(self):
		for status in (Status.CALCULATED, Status.ADOPTED, Status.PUBLISHED):
			with self.subTest(status=status), self.assertRaises(LifecycleError) as raised:
				ACCOUNTS.move(status, Event.PUBLISH)
			self.assertIs(raised.exception.problem, Problem.NO_MOVE)

	def test_an_erklaerung_is_neither_transmitted_to_the_register_nor_eingestellt(self):
		for event in (Event.TRANSMIT, Event.PUBLISH):
			with self.subTest(event=event), self.assertRaises(LifecycleError):
				FILING.move(Status.FILED, event)

	def test_a_later_filing_of_the_key_replaces_a_filed_document(self):
		self.assertIs(FILING.move(Status.FILED, Event.REPLACE), Status.REPLACED)
		for status in ACCOUNTS.filings:
			with self.subTest(status=status):
				self.assertIs(ACCOUNTS.move(status, Event.REPLACE), Status.REPLACED)

	def test_a_filed_document_is_neither_calculated_nor_changed_nor_discarded(self):
		for status in (Status.FILED, Status.REPLACED):
			for event in (Event.CALCULATE, Event.CHANGE, Event.DISCARD, Event.FILE):
				with self.subTest(status=status, event=event), self.assertRaises(LifecycleError) as raised:
					FILING.move(status, event)
				self.assertIs(raised.exception.problem, Problem.NO_MOVE)

	def test_only_a_filed_document_is_replaced(self):
		for status in (Status.DRAFT, Status.READY, Status.REPLACED):
			with self.subTest(status=status), self.assertRaises(LifecycleError):
				FILING.move(status, Event.REPLACE)

	def test_refuses_a_status_the_lifecycle_does_not_have(self):
		for status in (Status.ADOPTED, "Storniert", None):
			with self.subTest(status=status), self.assertRaises(LifecycleError) as raised:
				FILING.move(status, Event.CALCULATE)
			self.assertIs(raised.exception.problem, Problem.NO_MOVE)
		with self.assertRaises(LifecycleError):
			ACCOUNTS.move(Status.READY, Event.FILE)

	def test_takes_the_status_as_the_document_stores_it(self):
		self.assertIs(FILING.move("Bereit", Event.FILE), Status.FILED)

	def test_names_what_it_refused(self):
		with self.assertRaises(LifecycleError) as raised:
			FILING.move(Status.FILED, Event.CALCULATE)
		self.assertEqual(raised.exception.subject, "Abgegeben")
		self.assertIn("no_move", str(raised.exception))


class FitForFilingTest(TestCase):
	"""„Bereit oder Anmerkungen“: a calculated document is filed when it is ready, or when its remarks say why it is
	filed nonetheless."""

	def test_a_ready_document_is_filed(self):
		fit_for_filing(FILING, Status.READY, True, None)
		fit_for_filing(ACCOUNTS, Status.CALCULATED, True, "")

	def test_a_document_that_is_not_ready_is_filed_with_its_remarks(self):
		fit_for_filing(FILING, Status.CALCULATED, False, "Mit der Steuerberatung abgestimmt.")

	def test_a_document_that_is_not_ready_needs_its_remarks(self):
		for remarks in (None, "", "  \n"):
			with self.subTest(remarks=remarks), self.assertRaises(LifecycleError) as raised:
				fit_for_filing(FILING, Status.CALCULATED, False, remarks)
			self.assertIs(raised.exception.problem, Problem.NOT_READY)

	def test_a_document_is_calculated_before_it_is_filed(self):
		for status in (Status.DRAFT, Status.FILED, "Storniert"):
			with self.subTest(status=status), self.assertRaises(LifecycleError) as raised:
				fit_for_filing(FILING, status, True, "Anmerkung")
			self.assertIs(raised.exception.problem, Problem.NOT_CALCULATED)


class OneFilingPerKeyTest(TestCase):
	"""A key, such as company and year, is filed once; every further filing of it is a Berichtigung."""

	def test_one_draft_per_key(self):
		refuse_second_draft((Other("UStE-2026-00001", 1), Other("UStE-2026-00002", 2)))
		with self.assertRaises(LifecycleError) as raised:
			refuse_second_draft((Other("UStE-2026-00001", 1), Other("UStE-2026-00003", 0)))
		self.assertEqual(
			(raised.exception.problem, raised.exception.subject), (Problem.DRAFT_EXISTS, "UStE-2026-00003")
		)

	def test_a_filed_key_takes_a_berichtigung_only(self):
		with self.assertRaises(LifecycleError) as raised:
			refuse_second_filing(False, (Other("UStE-2026-00001", 1),))
		self.assertEqual(
			(raised.exception.problem, raised.exception.subject), (Problem.FILED_EXISTS, "UStE-2026-00001")
		)
		refuse_second_filing(True, (Other("UStE-2026-00001", 1),))

	def test_a_document_sent_through_steuerbote_files_the_key_even_as_a_draft_or_cancelled(self):
		"""The Finanzamt has a document whose Senden ELSTER accepted, or may have it when the outcome is unknown."""
		for docstatus in (0, 2):
			with self.subTest(docstatus=docstatus), self.assertRaises(LifecycleError) as raised:
				refuse_second_filing(False, (Other("UStE-2026-00001", docstatus, sent=True),))
			self.assertIs(raised.exception.problem, Problem.FILED_EXISTS)

	def test_a_cancelled_or_unsent_draft_files_nothing(self):
		refuse_second_filing(False, (Other("JA-2026-00001", 2), Other("UStE-2026-00002", 0)))

	def test_a_berichtigung_corrects_a_filed_document_of_the_key(self):
		check_correction(True, Other("UStE-2026-00001", 1))
		for corrects in (None, Other("UStE-2026-00001", 0), Other("UStE-2026-00001", 2)):
			with self.subTest(corrects=corrects), self.assertRaises(LifecycleError) as raised:
				check_correction(True, corrects)
			self.assertIs(raised.exception.problem, Problem.NOT_A_FILING)

	def test_a_first_filing_corrects_nothing(self):
		check_correction(False, None)


class StandardFieldsTest(TestCase):
	"""The fields every annual document carries (contract of stage 3, 2.5), which the base reads and writes."""

	def test_every_annual_document_carries_them(self):
		fields = standard_fields(FILING, DOCTYPE, transmits=True)
		self.assertEqual(
			[field.fieldname for field in fields],
			[
				"company",
				"year",
				"fiscal_year",
				"from_date",
				"to_date",
				"status",
				"ready",
				"remarks",
				"deadline",
				"is_correction",
				"corrects",
				"transmission_in_progress",
				"filed_via",
				"filed_on",
				"transferticket",
				"filed_by",
				"filing_note",
				"findings",
			],
		)

	def test_a_document_that_goes_to_no_finanzamt_has_no_lock_of_a_transmission(self):
		fieldnames = [
			field.fieldname for field in standard_fields(ACCOUNTS, "Annual Accounts", transmits=False)
		]
		self.assertNotIn("transmission_in_progress", fieldnames)
		self.assertEqual(len(fieldnames), 17)

	def test_each_field_with_its_type_label_and_options(self):
		fields = {field.fieldname: field for field in standard_fields(FILING, DOCTYPE, transmits=True)}
		self.assertEqual(
			fields["company"],
			StandardField("company", "Link", "Company", "Company", read_only=False, reqd=True),
		)
		self.assertEqual(fields["year"], StandardField("year", "Int", "Year", read_only=False, reqd=True))
		self.assertEqual(
			fields["fiscal_year"], StandardField("fiscal_year", "Link", "Fiscal Year", "Fiscal Year")
		)
		self.assertEqual(fields["status"], StandardField("status", "Select", "Status", FILING.options))
		self.assertEqual(fields["ready"].label, "Ready to File")
		self.assertEqual(
			fields["remarks"], StandardField("remarks", "Small Text", "Remarks", read_only=False)
		)
		self.assertEqual(fields["deadline"], StandardField("deadline", "Date", "Due Date"))
		self.assertEqual(fields["is_correction"], StandardField("is_correction", "Check", "Correction"))
		self.assertEqual(fields["corrects"], StandardField("corrects", "Link", "Corrects", DOCTYPE))
		self.assertEqual(
			fields["filed_via"],
			StandardField("filed_via", "Select", "Filed Via", "\neric\nmein_elster\nother_way\nupload"),
		)
		self.assertEqual(fields["filed_by"], StandardField("filed_by", "Link", "Noted By", "User"))
		self.assertEqual(fields["filing_note"].label, "How and When Filed")
		self.assertEqual(
			fields["findings"], StandardField("findings", "Table", "Findings", "Annual Filing Finding")
		)
		self.assertEqual(
			standard_fields(ACCOUNTS, "Annual Accounts", transmits=False)[5].options, ACCOUNTS.options
		)

	def test_the_ways_of_filing(self):
		self.assertEqual(FILED_VIA, ("eric", "mein_elster", "other_way", "upload"))

	def test_names_what_a_definition_lacks_or_has_otherwise(self):
		definition = {
			"name": DOCTYPE,
			"fields": [
				{
					"fieldname": field.fieldname,
					"fieldtype": field.fieldtype,
					"label": field.label,
					"options": field.options,
					"read_only": int(field.read_only),
					"reqd": int(field.reqd),
				}
				for field in standard_fields(FILING, DOCTYPE, transmits=True)
			],
		}
		self.assertEqual(field_problems(definition, FILING, transmits=True), [])
		definition["fields"] = [field for field in definition["fields"] if field["fieldname"] != "deadline"]
		definition["fields"][0] = {**definition["fields"][0], "label": "Firma"}
		definition["fields"][5] = {**definition["fields"][5], "read_only": 0}
		self.assertEqual(
			field_problems(definition, FILING, transmits=True),
			["company: label 'Firma', not 'Company'", "status: read_only 0, not 1", "deadline: missing"],
		)

	def test_a_definition_writes_no_options_or_flags_it_leaves_out(self):
		definition = {
			"name": DOCTYPE,
			"fields": [
				{"fieldname": field.fieldname, "fieldtype": field.fieldtype, "label": field.label}
				| ({"options": field.options} if field.options else {})
				| ({"read_only": 1} if field.read_only else {})
				| ({"reqd": 1} if field.reqd else {})
				for field in standard_fields(FILING, DOCTYPE, transmits=False)
			],
		}
		self.assertEqual(field_problems(definition, FILING, transmits=False), [])

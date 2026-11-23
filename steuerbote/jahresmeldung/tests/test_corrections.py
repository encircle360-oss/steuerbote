from decimal import Decimal
from unittest import TestCase

from lxml import etree

from steuerbote.elster.tests import eric_schema
from steuerbote.jahresmeldung import documentation
from steuerbote.jahresmeldung.corrections import (
	BERICHTIGUNGEN,
	BILANZ,
	GEWST,
	KST,
	LABELS,
	MARKED_YES,
	OFFENLEGUNG,
	REVISION_STATUS,
	UST,
	CorrectionError,
	Method,
	Problem,
	RegisterChange,
	RevisionStatus,
	berichtigung_of,
	fee_factor,
	marker,
	register_changes,
	revision_status,
	revision_status_concept,
)
from steuerbote.ustva.documentation import Row

GCD = "http://www.xbrl.de/taxonomies/de-gcd-2025-04-01"


class BerichtigungTest(TestCase):
	def test_each_annual_filing_has_its_berichtigung(self):
		self.assertEqual(set(BERICHTIGUNGEN), {"USt", "KSt", "GewSt", "Bilanz", "Offenlegung"})
		for name, rule in BERICHTIGUNGEN.items():
			with self.subTest(datenart=name):
				self.assertIs(berichtigung_of(name), rule)
				self.assertEqual(rule.datenart, name)
				self.assertTrue(rule.source)

	def test_knows_no_berichtigung_of_another_datenart(self):
		with self.assertRaises(CorrectionError) as raised:
			berichtigung_of("UStVA")
		self.assertEqual(
			(raised.exception.problem, raised.exception.value), (Problem.UNKNOWN_DATENART, "UStVA")
		)

	def test_kz_110_marks_a_berichtigte_umsatzsteuererklaerung(self):
		self.assertEqual(
			(UST.method, UST.fields, UST.line, UST.verified), (Method.MARKED, ("E3000601",), 3, True)
		)
		self.assertEqual(marker(UST, is_correction=True), MARKED_YES)
		self.assertIsNone(marker(UST, is_correction=False))

	def test_a_berichtigte_kst_or_gewst_erklaerung_is_a_new_full_declaration(self):
		"""No Kz 10 exists; the qualified free text of § 150 Abs. 7 AO may explain it, which ELSTER is not known to
		expect."""
		self.assertEqual(
			(KST.method, KST.fields, KST.line), (Method.FULL_DECLARATION, ("E8001305", "E8001304"), 13)
		)
		self.assertEqual(
			(GEWST.method, GEWST.fields, GEWST.line), (Method.FULL_DECLARATION, ("E4003204", "E4003205"), 21)
		)
		self.assertFalse(KST.verified or GEWST.verified)
		for rule in (KST, GEWST, BILANZ, OFFENLEGUNG):
			with self.subTest(datenart=rule.datenart):
				self.assertIsNone(marker(rule, is_correction=True))

	def test_the_status_des_berichts_marks_a_berichtigte_e_bilanz(self):
		self.assertEqual((BILANZ.method, BILANZ.fields), (Method.REVISION_STATUS, (REVISION_STATUS,)))
		self.assertEqual(REVISION_STATUS, "genInfo.report.id.revisionStatus")

	def test_a_changed_jahresabschluss_is_disclosed_again(self):
		self.assertEqual(
			(OFFENLEGUNG.method, OFFENLEGUNG.fields, OFFENLEGUNG.line), (Method.DISCLOSED_AGAIN, (), None)
		)


class RevisionStatusTest(TestCase):
	"""FAQ zur E-Bilanz, Version 2026-01, Tz. 4 d, and the GCD of taxonomy 6.9 (de-gcd-2025-04-01)."""

	def test_the_statuses_and_their_labels_in_the_gcd(self):
		self.assertEqual(
			{status.value: LABELS[status] for status in RevisionStatus},
			{
				"E": "erstmalig",
				"B": "berichtigt",
				"G": "geändert",
				"BG": "berichtigt und geändert",
				"sK": "sonstige Korrektur",
				"I": "identischer Abschluss mit differenzierteren Informationen",
			},
		)

	def test_the_first_filing_is_erstmalig(self):
		for chosen in (None, "", "E", RevisionStatus.FIRST):
			with self.subTest(chosen=chosen):
				self.assertIs(revision_status(False, chosen), RevisionStatus.FIRST)

	def test_a_further_filing_names_how_it_corrects(self):
		for chosen in ("B", "G", "BG", "sK", "I"):
			with self.subTest(chosen=chosen):
				self.assertIs(revision_status(True, chosen), RevisionStatus(chosen))

	def test_a_further_filing_is_no_first_one(self):
		for chosen in (None, "", "E"):
			with self.subTest(chosen=chosen), self.assertRaises(CorrectionError) as raised:
				revision_status(True, chosen)
			self.assertIs(raised.exception.problem, Problem.CORRECTION_WITHOUT_STATUS)

	def test_a_first_filing_corrects_nothing(self):
		with self.assertRaises(CorrectionError) as raised:
			revision_status(False, "B")
		self.assertEqual((raised.exception.problem, raised.exception.value), (Problem.FIRST_WITH_STATUS, "B"))

	def test_the_correction_by_the_tax_administration_is_not_for_a_filing(self):
		"""revisionStatus.K, „Korrektur durch Finanzverwaltung“, is notPermittedFor „Einreichung an Finanzverwaltung“
		(de-gcd-2025-04-01-reference-fiscal.xml)."""
		for is_correction in (True, False):
			with self.subTest(is_correction=is_correction), self.assertRaises(CorrectionError) as raised:
				revision_status(is_correction, "K")
			self.assertIs(raised.exception.problem, Problem.NOT_FOR_FILING)

	def test_refuses_a_status_the_gcd_does_not_have(self):
		with self.assertRaises(CorrectionError) as raised:
			revision_status(True, "X")
		self.assertIs(raised.exception.problem, Problem.UNKNOWN_STATUS)

	def test_names_the_concept_of_the_status(self):
		self.assertEqual(
			revision_status_concept(RevisionStatus.CORRECTED),
			"genInfo.report.id.revisionStatus.revisionStatus.B",
		)


class OffenlegungTest(TestCase):
	"""§ 325 Abs. 1b HGB; JVKostG, Anlage 1, Vorbemerkung 1.4.2; Allgemeine Nutzungsbedingungen für das
	Unternehmensregister, §§ 13 and 14."""

	def test_before_the_einstellung_an_order_is_changed_or_cancelled(self):
		self.assertEqual(register_changes(eingestellt=False), (RegisterChange.CHANGE, RegisterChange.CANCEL))

	def test_after_the_einstellung_only_a_berichtigung_follows(self):
		self.assertEqual(register_changes(eingestellt=True), (RegisterChange.BERICHTIGUNG,))

	def test_a_change_before_the_einstellung_raises_the_fees_by_half(self):
		self.assertEqual(fee_factor(RegisterChange.CHANGE), Decimal("1.5"))

	def test_a_cancellation_before_the_einstellung_halves_them_and_costs_nothing_on_the_day_of_the_order(
		self,
	):
		self.assertEqual(fee_factor(RegisterChange.CANCEL), Decimal("0.5"))
		self.assertEqual(fee_factor(RegisterChange.CANCEL, same_day=True), Decimal("0"))

	def test_a_berichtigung_is_an_order_of_its_own(self):
		self.assertEqual(fee_factor(RegisterChange.BERICHTIGUNG), Decimal("1"))


class CorrectionDocumentationTest(TestCase):
	"""The fields and rules of a Berichtigung against the Jahresdokumentationen and the examples of the ERiC
	documentation 44.3.6.0."""

	def rows(self, name: str, root: str, year: int, sheet: str) -> tuple[Row, ...]:
		path = (
			eric_schema.erklaerung_directory(name)
			/ "Jahresdokumentation"
			/ f"Jahresdokumentation_{root}_{year}.ods"
		)
		return documentation.read(path).sheet(sheet)

	def fields(self, name: str, root: str, year: int, form: str) -> dict[str, Row]:
		return {row["Name"]: row for row in self.rows(name, root, year, f"{form} - Felder")}

	def test_kz_110_is_a_yes_field_of_line_3(self):
		row = self.fields("USt", "E50", 2026, "USt2A")["E3000601"]
		self.assertEqual(
			(
				row["Beschreibung"],
				row["Formatkennzeichen"],
				row["Format als regulärer Ausdruck"],
				row["Vordruckzeile"],
			),
			("Berichtigte Steuererklärung", "J", MARKED_YES, str(UST.line)),
		)

	def test_line_3_is_only_for_a_return_that_corrects_one_transmitted(self):
		(rule,) = (
			row for row in self.rows("USt", "E50", 2026, "USt2A - Regeln") if row["Fehlercode"] == "30002"
		)
		self.assertEqual(rule["Prüfbedingung"], "FeldAngegeben(E3000601)")
		self.assertIn(
			"nur angeben, wenn Sie eine bereits übermittelte Erklärung berichtigen wollen",
			rule["Fehler- /Hinweistext"],
		)

	def test_the_free_text_of_kst_and_gewst_is_filed_with_its_key_or_not_at_all(self):
		for rule, name, root, form, code in (
			(KST, "KSt", "E30", "KSt1", "8900735"),
			(GEWST, "GewSt", "E20", "GewSt1A", "40128"),
		):
			with self.subTest(datenart=name):
				fields = self.fields(name, root, 2025, form)
				key, text = (fields[element] for element in rule.fields)
				self.assertEqual((key["Formatkennzeichen"], text["Formatkennzeichen"]), ("H", "C"))
				self.assertEqual({key["Vordruckzeile"], text["Vordruckzeile"]}, {str(rule.line)})
				self.assertEqual(text["Beschreibung"], "Ergänzende Angaben zur Steuererklärung")
				(paired,) = (
					row
					for row in self.rows(name, root, 2025, f"{form} - Regeln")
					if row["Fehlercode"] == code
				)
				self.assertEqual(
					paired["Prüfbedingung"],
					f"FelderNichtGemeinsamAngegeben({rule.fields[0]}, {rule.fields[1]})",
				)

	def test_the_examples_of_the_e_bilanz_file_as_erstmalig(self):
		examples = sorted((eric_schema.bilanz_directory() / "Beispiele" / "Taxonomie_6_9").glob("*.xml"))
		self.assertTrue(examples)
		prefix = f"{{{GCD}}}{revision_status_concept(RevisionStatus.FIRST)[: -len('.E')]}."
		for path in examples:
			with self.subTest(example=path.name):
				found = [
					element
					for element in etree.parse(str(path)).iter()
					if isinstance(element.tag, str) and element.tag.startswith(prefix)
				]
				self.assertEqual(
					[element.tag[len(prefix) :] for element in found], [RevisionStatus.FIRST.value]
				)
				self.assertIn((found[0].text or "").strip(), ("", LABELS[RevisionStatus.FIRST]))

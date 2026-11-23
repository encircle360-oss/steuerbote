"""The simulation of the Umsatzsteuererklärung: the fields of USt2A and the rules of Jahresdokumentation_E50_2026.ods
that Steuerbote checks itself (steuerbote/eric/simulation/ust.py), run by steuerbote.eric.fake."""

import os
from dataclasses import replace
from datetime import date
from decimal import Decimal
from unittest import TestCase, mock
from xml.etree import ElementTree

from steuerbote.elster.tests.examples import TEST_STEUERNUMMER
from steuerbote.elster.tests.test_ust2a_xml import GRUNDSTUECK, RETURN, sender
from steuerbote.elster.ust2a_xml import to_nutzdaten
from steuerbote.eric import fake
from steuerbote.eric.datenart import ust
from steuerbote.eric.fake import DOCUMENTATION_VARIABLE, Simulation
from steuerbote.eric.header import EnvelopeHeader
from steuerbote.eric.result import ERROR, Operation, Outcome
from steuerbote.eric.simulation import erklaerung
from steuerbote.eric.simulation import ust as simulation
from steuerbote.eric.simulation.ust import RULES, LocalRule, readable, values_of
from steuerbote.ustjahr.calculation import entries
from steuerbote.ustjahr.form import CATALOGUES, Severity
from steuerbote.ustjahr.rules import LEFT_TO_ERIC, LOCAL_RULES, check

YEAR = 2026
KIND = ust(YEAR)
CATALOGUE = CATALOGUES[YEAR]
D = Decimal
HEADER = EnvelopeHeader(
	hersteller_id="00000",
	datenlieferant="Beispiel GmbH",
	produkt_name="Steuerbote",
	produkt_version="0.1.0",
	empfaenger=TEST_STEUERNUMMER[:4],
	datenart_version="USt_2026",
	testmerker=None,
	nutzdaten_ticket="1",
)
JD_RULES = frozenset(rule.code for rule in CATALOGUE.rules)


def nutzdaten(values: dict | None = None, grundstuecke: tuple = (GRUNDSTUECK,)) -> str:
	"""The invented return of the tests of the XML, or other values, as the Nutzdaten Steuerbote writes."""
	return to_nutzdaten(YEAR, RETURN if values is None else values, sender(), grundstuecke)


def without(*elements: str) -> dict:
	return {element: value for element, value in RETURN.items() if element not in elements}


def errors(result) -> list[tuple[str, str | None]]:
	return [(message.code, message.field) for message in result.messages if message.severity == ERROR]


def expected(values: dict) -> list[tuple[str, str]]:
	"""The errors of the rules of the JD that check() finds in the values: those the simulation reports, in order."""
	return [
		(finding.code, finding.fields[0])
		for finding in check(YEAR, values)
		if finding.blocking and finding.code in JD_RULES
	]


class SimulationTestCase(TestCase):
	def setUp(self):
		patcher = mock.patch.dict(os.environ)
		patcher.start()
		self.addCleanup(patcher.stop)
		os.environ.pop(DOCUMENTATION_VARIABLE, None)

	def run_simulation(self, data: str, header: EnvelopeHeader = HEADER):
		return Simulation().run(Operation.VALIDATE, data, header)

	def refused(self, data: str) -> list[tuple[str, str | None]]:
		result = self.run_simulation(data)
		self.assertIs(result.outcome, Outcome.INVALID)
		return errors(result)


class RulesTest(SimulationTestCase):
	def test_a_return_steuerbote_writes_passes_the_simulation(self):
		address = {element: RETURN[element] for element in ("E3001101", "E3001203", "E3001206", "E3001207")}
		nil = {"E3000901": "Beispiel GmbH", **address, "E3002203": "1", **entries(CATALOGUE, {}, D("0.00"))}
		for values, grundstuecke in ((RETURN, (GRUNDSTUECK,)), (nil, ())):
			with self.subTest(values=len(values)):
				result = self.run_simulation(nutzdaten(values, grundstuecke))
				self.assertIs(result.outcome, Outcome.VALID)
				self.assertEqual([message.code for message in result.messages], ["SIM-000", "SIM-001"])

	def test_each_rule_that_applies_reports_with_its_fehlercode_and_its_first_field(self):
		"""The errors of the rules of the JD that check() finds, in its order; a Hinweis such as 30949 stays out."""
		for case, values in {
			"without Kz 816 and Kz 820": without("E3011101", "E3011401"),
			"without Kz 816": without("E3011101"),
			"without Kz 133": without("E3002203"),
			"a tax two euros off its base": {**RETURN, "E3003304": D("47502.00")},
			"a base without its tax": without("E3004402"),
			"Kz 742 below Kz 789": {**RETURN, "E3101801": D("4000")},
			"a sum without its lines": without("E3102205", "E3102206"),
			"an address without its town": without("E3001207"),
		}.items():
			with self.subTest(case):
				found = self.refused(nutzdaten(values))
				self.assertEqual(found, expected({**values, **GRUNDSTUECK}))
				self.assertTrue(found)
		self.assertEqual(self.refused(nutzdaten(without("E3102205", "E3102206"))), [("30803", "E3102601")])

	def test_the_message_names_the_rule_and_the_fields_it_checks(self):
		result = self.run_simulation(nutzdaten({**RETURN, "E3003304": D("47502.00")}))
		self.assertEqual(
			[
				(message.code, message.text, message.severity, message.field)
				for message in result.messages[1:]
			],
			[
				(
					"30639",
					"Die Regel 30639 (USt_30639) der Jahresdokumentation E50 2026 schlägt an: "
					"E3003304 in Zeile 24, Kz 177 in Zeile 24.",
					ERROR,
					"E3003304",
				),
				(
					"30314",
					"Die Regel 30314 (USt_30314) der Jahresdokumentation E50 2026 schlägt an: E3006001 in Zeile 41.",
					ERROR,
					"E3006001",
				),
			],
		)

	def test_hints_and_the_checks_of_steuerbote_stop_no_simulation(self):
		"""30008 is a Hinweis (no W-IdNr.); a sale in line 52 without its paragraph is a check of Steuerbote's own."""
		values = without("E3000401", "E3104501")
		self.assertEqual([finding.code for finding in check(YEAR, values)], ["PARAGRAF-FEHLT", "30008"])
		self.assertIs(self.run_simulation(nutzdaten(values)).outcome, Outcome.VALID)

	def test_the_rules_are_the_errors_steuerbote_checks_itself_in_the_order_of_the_jd(self):
		self.assertIs(RULES[0], readable)
		local = RULES[1:]
		self.assertTrue(all(isinstance(rule, LocalRule) and rule.year == YEAR for rule in local))
		self.assertEqual(
			[rule.code for rule in local],
			[rule.code for rule in LOCAL_RULES[YEAR] if CATALOGUE.rule(rule.code).severity is Severity.ERROR],
		)
		self.assertEqual(len(local), 136)
		self.assertFalse({rule.code for rule in local} & set(LEFT_TO_ERIC[YEAR]))

	def test_the_umsatzsteuererklaerung_runs_its_rules_after_the_rule_of_the_recipient(self):
		self.assertIs(fake.CHECKS["USt"], simulation.CHECKS)
		self.assertEqual(simulation.CHECKS.rules, (erklaerung.recipient, *RULES))

	def test_a_year_without_its_form_is_checked_for_its_structure_only(self):
		data = (
			nutzdaten()
			.replace("/v2026", "/v2027")
			.replace('version="2026"', 'version="2027"')
			.replace("<Zeitraum>2026<", "<Zeitraum>2027<")
		)
		result = self.run_simulation(data, replace(HEADER, datenart_version="USt_2027"))
		self.assertIs(result.outcome, Outcome.VALID)
		self.assertIsNone(readable(ElementTree.fromstring(data), ust(2027), HEADER))


class ReadableTest(SimulationTestCase):
	"""SIM-010: each field of USt2A is one of the form of the year in its context, once, in its Formatkennzeichen."""

	def test_a_field_the_form_does_not_have_is_refused(self):
		data = nutzdaten().replace("<E3000901>", "<E3999999>1</E3999999><E3000901>")
		result = self.run_simulation(data)
		self.assertEqual(errors(result), [("SIM-010", "E3999999")])
		self.assertEqual(
			result.messages[-1].text,
			"Das Feld E3999999 gibt es im Vordruck USt2A 2026 nicht (Jahresdokumentation, USt2A - Felder).",
		)

	def test_a_field_in_another_context_is_refused(self):
		data = (
			nutzdaten()
			.replace("<E3001207>München</E3001207>", "")
			.replace("<E3000901>", "<E3001207>München</E3001207><E3000901>")
		)
		result = self.run_simulation(data)
		self.assertEqual(errors(result), [("SIM-010", "E3001207")])
		self.assertIn("Allg/Unternehmen", result.messages[-1].text)
		self.assertIn("Allg/Unternehmen/Adr", result.messages[-1].text)

	def test_a_field_given_twice_is_refused(self):
		data = nutzdaten().replace("<E3001207>München</E3001207>", "<E3001207>München</E3001207>" * 2)
		self.assertEqual(self.refused(data), [("SIM-010", "E3001207")])

	def test_a_value_its_formatkennzeichen_does_not_take_is_refused(self):
		"""The fields of a Grundstück of line 95 are read for their format, too."""
		values = {
			**RETURN,
			"E3106101": D("250"),
			"E3005901": D("19"),
			"E3001401": (date(2026, 2, 1), date(2026, 12, 31)),
		}
		data = nutzdaten(values)
		for element, text in (
			("E3003303", "250.000"),
			("E3003303", "-0250000"),
			("E3106101", "-250"),
			("E3003304", "47500,0"),
			("E3005901", "-19,00"),
			("E3002602", "2"),
			("E3007801", "1"),
			("E3007402", "31.02.2026"),
			("E3007402", "1.4.2026"),
			("E3001401", "30.02-31.12"),
			("E3001401", "01.02.-31.12."),
			("E3000901", ""),
		):
			with self.subTest(element=element, text=text):
				start = data.index(f"<{element}>") + len(f"<{element}>")
				changed = data[:start] + text + data[data.index(f"</{element}>", start) :]
				result = self.run_simulation(changed)
				self.assertEqual(errors(result), [("SIM-010", element)])
				self.assertIn(f"„{text}“ im Feld {element}", result.messages[-1].text)

	def test_reads_the_values_as_check_takes_them_without_the_grundstuecke(self):
		values = {**RETURN, "E3001401": (date(2026, 2, 1), date(2026, 12, 31))}
		read = values_of(ElementTree.fromstring(nutzdaten(values, (GRUNDSTUECK, GRUNDSTUECK))), KIND)
		self.assertEqual(read, values)
		self.assertEqual(
			(type(read["E3003303"]), read["E3002602"], read["E3007801"], read["E3000901"]),
			(Decimal, True, True, "Beispiel GmbH"),
		)
		self.assertNotIn("E3007401", read)

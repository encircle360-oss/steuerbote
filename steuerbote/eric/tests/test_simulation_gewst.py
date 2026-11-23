"""The rules of the Gewerbesteuererklärung that the simulation checks (steuerbote.eric.simulation.gewst): each on
Nutzdaten written by steuerbote.elster.gewst_xml, the worked example „Muster IT GmbH“ through the whole simulation, and
the Prüfbedingungen against the sheets „GewSt1A - Regeln“ and „BEG - Regeln“ of Jahresdokumentation_E20_2025.ods."""

import hashlib
from decimal import Decimal
from types import MappingProxyType
from unittest import TestCase
from xml.etree import ElementTree

from steuerbote.elster import gewst_xml
from steuerbote.elster.tests.test_gewst_xml import GENERAL, RECEIPTS, muster_it_gmbh
from steuerbote.elster.tests.test_kst_xml import VORSATZ
from steuerbote.eric.datenart import gewst
from steuerbote.eric.fake import Simulation
from steuerbote.eric.result import ERROR, Operation, Outcome
from steuerbote.eric.simulation import gewst as simulation
from steuerbote.eric.simulation.gewst import CONDITIONS, RULES, shares
from steuerbote.eric.simulation.kst import Erklaerung
from steuerbote.eric.tests.test_simulation import header_of
from steuerbote.gewst.form import CATALOGUES, RECHTSFORMEN
from steuerbote.kst.form import Entry, Vordruck, entries
from steuerbote.kst.tests import jahresdokumentation as jd

KIND = gewst(2026)
HEADER = header_of(KIND)
NAMESPACE = KIND.namespace
PROFIT = entries({"E4001703": Decimal("100")})
PRUEFBEDINGUNGEN = MappingProxyType(
	{
		"40000": "1fc3d6636121b3249fe89bfe8bee97e4aec8568add1a36035774043a9c6e4fa7",
		"40038": "12a02a06b33b8b0e448d1f52bb682a33d2786e2eb53a0fbbcabc37228ea1b15f",
		"40047": "51cdde0c6e9fe5f04e170af975949cf3e70d31ee8c0275a8c1853f48083f8805",
		"40029": "566eac3ff7ce1356970adcee07f82e4c64bf9de8b6cf5242d4dda8dce4861240",
		"40051": "8cafc665d78234d5a5f0242cc66e1d72f3dd76f00c4e0f8fe581fe24dd152c5a",
		"40052": "59df82edc08f162c716ea07aa2718e1b4667529043a6c37684ce7f0c40fc3862",
		"40053": "d7c7966a97d3a1974a111ce6b5465f304f978e066f279f37bcc184ddb8aa3a2f",
		"40054": "b8d0d2fb3292cc4e7b28d9215d9d03d444e58babd53202c806775e8b21487e56",
		"40954": "334c6de2ded12e937e2ced87be16b8a2967d86b7980c97e0e759bd6fb5dac4ed",
		"40958": "0184da2a5d941963588d085bf656fb6321dc7d9119b88ed22d2bbd66841eae55",
		"40959": "c60d9e11b7dee88d28954c1ea51b235ea8fbcefe1f10beb8d07d11c55d3f192e",
		"40965": "1dbfa67b64175fb7ad60841f80818a2ad4ce6d4824135af14db2cf0c073f732a",
	}
)
"""The SHA-256 of each Prüfbedingung CONDITIONS reads, as the sheets „GewSt1A - Regeln“ and „BEG - Regeln“ write it
with its blanks collapsed: the texts stay in the JD, as for the Körperschaftsteuer (test_simulation_kst.py)."""


def gewst_1a(*changes: Entry, without: tuple[str, ...] = ()) -> Vordruck:
	"""GewSt 1 A with the general details of the example and a Gewinn, fields left out and entries added."""
	kept = tuple(entry for entry in (*GENERAL, *PROFIT) if entry.feldkennung not in without)
	return Vordruck("GewSt1A", (*kept, *changes))


def beg(values: dict[str, object]) -> Vordruck:
	return Vordruck("BEG", entries({"E4050201": "Beta GmbH", "E4050601": Decimal("1000"), **values}))


def root_of(*given: Vordruck) -> ElementTree.Element:
	if not any(vordruck.form == "GewSt1A" for vordruck in given):
		given = (gewst_1a(), *given)
	return ElementTree.fromstring(gewst_xml.to_nutzdaten(2026, given, VORSATZ))


def fails(code: str, *given: Vordruck, root: ElementTree.Element | None = None) -> bool:
	"""Whether the rule of the Fehlercode refuses Nutzdaten of the Vordrucke, with the GewSt 1 A of gewst_1a() unless
	one is given."""
	(rule,) = (rule for rule in RULES if rule.condition.code == code)
	return rule(root_of(*given) if root is None else root, KIND, HEADER) is not None


def foreign(root: ElementTree.Element, path: str, text: str) -> ElementTree.Element:
	"""The Nutzdaten with a field Steuerbote does not write, by its path below the root."""
	parent = root
	*contexts, name = path.split("/")
	for context in contexts:
		found = parent.find(f"{{{NAMESPACE}}}{context}")
		parent = ElementTree.SubElement(parent, f"{{{NAMESPACE}}}{context}") if found is None else found
	ElementTree.SubElement(parent, f"{{{NAMESPACE}}}{name}").text = text
	return root


class ExampleTest(TestCase):
	def test_the_muster_it_gmbh_passes_every_rule(self):
		root = ElementTree.fromstring(gewst_xml.to_nutzdaten(2026, muster_it_gmbh(), VORSATZ))
		self.assertEqual([message for rule in RULES if (message := rule(root, KIND, HEADER))], [])

	def test_the_simulation_finds_the_muster_it_gmbh_valid_and_names_a_failed_rule(self):
		result = Simulation().run(
			Operation.VALIDATE, gewst_xml.to_nutzdaten(2026, muster_it_gmbh(), VORSATZ), HEADER
		)
		self.assertIs(result.outcome, Outcome.VALID)
		self.assertEqual([message.code for message in result.messages], ["SIM-000", "SIM-001"])
		without_receipts = Vordruck(
			"GewSt1A", tuple(entry for entry in muster_it_gmbh()[0].entries if entry not in RECEIPTS)
		)
		result = Simulation().run(
			Operation.VALIDATE, gewst_xml.to_nutzdaten(2026, (without_receipts,), VORSATZ), HEADER
		)
		(error,) = (message for message in result.messages if message.severity == ERROR)
		self.assertEqual((error.code, error.field), ("40051", "E4009221"))
		self.assertEqual(
			error.text,
			"Die Regel 40051 (GewSt_2025_40051) der Jahresdokumentation E20 2025 schlägt an: E4009221 im Vordruck "
			"GewSt1A, Zeile 92b.",
		)


class ConditionsTest(TestCase):
	def test_read_every_rule_of_the_catalogue(self):
		codes = [rule.code for rule in CATALOGUES[2026].rules]
		self.assertEqual([condition.code for condition in CONDITIONS], codes)
		self.assertEqual(list(PRUEFBEDINGUNGEN), codes)
		self.assertEqual(simulation.CHECKS.rules[1:], RULES)

	def test_a_year_without_vordrucke_is_not_checked(self):
		self.assertIsNone(simulation._year(2025))
		self.assertEqual(simulation._year(2026).categories, RECHTSFORMEN[2026])
		self.assertEqual(simulation._year(2026).documentation, "Jahresdokumentation E20 2025")


class GewSt1ATest(TestCase):
	def test_40000_a_gewinn_or_gewerbeertrag(self):
		self.assertFalse(fails("40000"))
		self.assertTrue(fails("40000", gewst_1a(without=("E4001703",))))
		self.assertFalse(fails("40000", gewst_1a(Entry("E4004811", Decimal("1")), without=("E4001703",))))
		root = foreign(root_of(gewst_1a(without=("E4001703",))), "GewSt1A/Einbringung_P24/E4014701", "1")
		self.assertFalse(fails("40000", root=root))
		root = foreign(root_of(gewst_1a(without=("E4001703",))), "OHG/Allgemein/E4100101", "1")
		self.assertFalse(fails("40000", root=root))

	def test_40038_40047_40029_the_betriebsstaette_of_lines_26_to_32(self):
		self.assertFalse(fails("40038"))
		self.assertTrue(fails("40038", gewst_1a(without=("E4001506",))))
		self.assertFalse(fails("40038", gewst_1a(Entry("E4001201", True), without=("E4001506",))))
		self.assertFalse(fails("40047"))
		self.assertTrue(fails("40047", gewst_1a(without=("E4001102",))))
		self.assertFalse(fails("40047", gewst_1a(Entry("E4001506", True), without=("E4001102", "E4001506"))))
		self.assertFalse(fails("40047", gewst_1a(Entry("E4001201", True), without=("E4001102",))))
		self.assertFalse(fails("40029"))
		self.assertTrue(fails("40029", gewst_1a(without=("E4001111",))))
		self.assertFalse(fails("40029", gewst_1a(Entry("E4001102", True), without=("E4001102", "E4001111"))))

	def test_40051_to_40054_the_zuwendungen_of_line_92d_and_their_receipts(self):
		total = Entry("E4003403", Decimal("1000"))
		self.assertTrue(fails("40051", gewst_1a(total)))
		self.assertFalse(fails("40051", gewst_1a(total, *RECEIPTS)))
		self.assertTrue(fails("40052", gewst_1a(*RECEIPTS)))
		self.assertFalse(fails("40052", gewst_1a(total, *RECEIPTS)))
		self.assertFalse(fails("40053", gewst_1a(total, *RECEIPTS)))
		self.assertTrue(fails("40053", gewst_1a(Entry("E4003403", Decimal("999")), *RECEIPTS)))
		second = (
			Entry("E4009220", "Zweiter Verein e. V.", (1,)),
			Entry("E4009221", Decimal("0.20"), (1,)),
			Entry("E4009222", "1", (1,)),
		)
		self.assertFalse(fails("40053", gewst_1a(Entry("E4003403", Decimal("1001")), *RECEIPTS, *second)))
		self.assertFalse(fails("40054", gewst_1a(total, *RECEIPTS, *second)))
		self.assertTrue(fails("40054", gewst_1a(total, *RECEIPTS, *second[:2])))
		self.assertFalse(fails("40054"))


class AnlageBegTest(TestCase):
	"""Lines 15 and 17 to 19 of Anlage BEG of a GmbH, an Organgesellschaft and a Mitunternehmerschaft."""

	def test_40954_line_15_is_95_percent_of_line_12_rounded_down(self):
		self.assertFalse(fails("40954", beg({"E4051201": Decimal("1001"), "E4051501": Decimal("950")})))
		self.assertTrue(fails("40954", beg({"E4051201": Decimal("1001"), "E4051501": Decimal("951")})))
		self.assertFalse(
			fails("40954", beg({"E4050701": "1", "E4051201": Decimal("1001"), "E4051501": Decimal("951")}))
		)
		self.assertFalse(fails("40954", beg({"E4051201": Decimal("1001")})))

	def test_40954_an_organgesellschaft_takes_the_share_of_its_koerperschaften(self):
		organ = gewst_1a(Entry("E4001501", True), Entry("E4006201", "50,000000"))
		self.assertFalse(
			fails("40954", organ, beg({"E4051201": Decimal("1000"), "E4051501": Decimal("475")}))
		)
		self.assertTrue(fails("40954", organ, beg({"E4051201": Decimal("1000"), "E4051501": Decimal("950")})))

	def test_40954_a_mitunternehmerschaft_takes_the_share_of_line_70_or_of_line_10(self):
		partners = {"370": RECHTSFORMEN[2026]["370"], "390": {"Rechtsformgruppe": "PG"}}
		root = root_of(
			gewst_1a(Entry("E4006104", "40,000000")),
			beg({"E4051201": Decimal("1000"), "E4051501": Decimal("380")}),
			beg({"E4051001": "20,000000", "E4051201": Decimal("1000"), "E4051501": Decimal("190")}),
			beg({"E4051001": "0,000000", "E4051201": Decimal("1000"), "E4051501": Decimal("1")}),
		)
		(rechtsform,) = root.iter(f"{{{NAMESPACE}}}E4000501")
		rechtsform.text = "390"
		erklaerung = Erklaerung(root, partners)
		first, second, third = erklaerung.each("BEG")
		self.assertEqual(shares(erklaerung, first), (Decimal("0.4"),))
		self.assertEqual(shares(erklaerung, second), (Decimal("0.2"),))
		self.assertEqual(shares(erklaerung, third), ())
		(condition,) = (condition for condition in CONDITIONS if condition.code == "40954")
		self.assertFalse(condition.fails(erklaerung))
		self.assertFalse(Erklaerung(root, partners).one("BEG").any_of("E4050701"))
		optierend = gewst_1a(Entry("E4001405", True), Entry("E4006104", "40,000000"))
		self.assertEqual(
			shares(
				Erklaerung(root_of(optierend), partners),
				Erklaerung(root_of(optierend, beg({})), partners).one("BEG"),
			),
			(Decimal("1"),),
		)

	def test_40958_40959_lines_17_and_18_are_the_costs_up_to_line_16(self):
		lines = {
			"E4050701": "1",
			"E4050801": Decimal("700"),
			"E4050901": Decimal("500"),
			"E4051601": Decimal("1000"),
		}
		right = beg({**lines, "E4051701": Decimal("700"), "E4051801": Decimal("300")})
		self.assertFalse(fails("40958", right))
		self.assertFalse(fails("40959", right))
		self.assertTrue(
			fails("40958", beg({**lines, "E4051701": Decimal("701"), "E4051801": Decimal("299")}))
		)
		self.assertTrue(
			fails("40959", beg({**lines, "E4051701": Decimal("700"), "E4051801": Decimal("500")}))
		)
		self.assertFalse(fails("40958", beg({"E4051701": Decimal("701")})))
		self.assertFalse(fails("40959", beg({"E4051801": Decimal("1")})))
		foreign_rechtsform = gewst_1a(Entry("E4000501", "310"), without=("E4000501",))
		self.assertFalse(fails("40958", foreign_rechtsform, beg({**lines, "E4051701": Decimal("701")})))

	def test_40965_line_19_is_line_16_less_lines_17_and_18_rounded_up(self):
		lines = {
			"E4050701": "1",
			"E4051601": Decimal("1000"),
			"E4051701": Decimal("700"),
			"E4051801": Decimal("200"),
		}
		self.assertFalse(fails("40965", beg({**lines, "E4051901": Decimal("100")})))
		self.assertTrue(fails("40965", beg({**lines, "E4051901": Decimal("101")})))
		self.assertFalse(fails("40965", beg({"E4051901": Decimal("101")})))
		organ = gewst_1a(Entry("E4001501", True), Entry("E4006201", "33,333333"))
		self.assertFalse(fails("40965", organ, beg({**lines, "E4051901": Decimal("34")})))
		self.assertTrue(fails("40965", organ, beg({**lines, "E4051901": Decimal("33")})))


class JahresdokumentationTest(TestCase):
	"""The Prüfbedingungen against Jahresdokumentation_E20_2025.ods."""

	def test_each_pruefbedingung_is_the_one_its_condition_reads(self):
		rows = {
			row["Fehlercode"]: row
			for form in jd.FORMS[jd.GEWST]
			for row in jd.sheet(jd.GEWST, 2025, f"{form} - Regeln")
		}
		for code, digest in PRUEFBEDINGUNGEN.items():
			with self.subTest(code=code):
				condition = " ".join(rows[code]["Prüfbedingung"].split())
				self.assertEqual(hashlib.sha256(condition.encode("utf-8")).hexdigest(), digest)
				self.assertEqual(rows[code]["Regelart"], "Fehler")

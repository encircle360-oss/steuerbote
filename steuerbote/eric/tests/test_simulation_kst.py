"""The rules of the Körperschaftsteuererklärung that the simulation checks (steuerbote.eric.simulation.kst): each on
Nutzdaten written by steuerbote.elster.kst_xml, the worked example „Muster IT GmbH“ through the whole simulation, and
the Prüfbedingungen against the sheets „<Vordruck> - Regeln“ of Jahresdokumentation_E30_2025.ods."""

import hashlib
import re
from collections.abc import Mapping
from decimal import Decimal
from types import MappingProxyType
from unittest import TestCase
from xml.etree import ElementTree

from lxml import etree

from steuerbote.elster import kst_xml
from steuerbote.elster.tests.test_kst_xml import KST1, VORSATZ, muster_it_gmbh
from steuerbote.eric.datenart import kst
from steuerbote.eric.fake import Simulation
from steuerbote.eric.result import ERROR, Operation, Outcome
from steuerbote.eric.simulation import kst as simulation
from steuerbote.eric.simulation.kst import (
	CONDITIONS,
	RULES,
	Condition,
	Erklaerung,
	NotANumber,
	SimulatedRule,
	Terms,
	number,
	sum_of,
)
from steuerbote.eric.tests.test_simulation import header_of
from steuerbote.kst.form import CATALOGUES, INDEXED, RECHTSFORMEN, Entry, Vordruck, entries
from steuerbote.kst.tests import jahresdokumentation as jd

KIND = kst(2026)
HEADER = header_of(KIND)
NAMESPACE = KIND.namespace
PRUEFBEDINGUNGEN = MappingProxyType(
	{
		"8906010": "aad9536fee1d674997c65d4642e8513b06ba9b70976285cc6b0eaa7b8a56d57e",
		"8900744": "628b871ddec383268fb2ea7d0a3a629c044fc17634806a132c4d573a26b8a387",
		"8912208": "6036735b8d842cd04d3b45b153f4d3c54227dbfa25d45a78602c2cfc624ad703",
		"8912209": "3ed17ab14861a0fbd6b870e19a6082d1f2851774de475417ae12259e2d2e2b49",
		"8931022": "4064478e02783ec823e74c0ea44c55d80771058c451446346b520dad7ddf0df1",
		"8900709": "de59dacbaaafabcd3539b0b270896f4373253f1a81243a3bd6f7d79c04e26435",
		"8912151": "7c48db43822eb2bce4b88e0027dd6a67e350fe836aef92c5b8c8f640c83ff21f",
		"8912163": "3e64f578c58d29cada3e775fd85b4dd96aecb66af97eba254f429a8fe3947363",
		"8900368": "72fcbbe255a92c158ab0be3de6fbe4a1ca53c20666781a069fa94d67dfc29cb2",
		"8900070": "4eb8fcaabbf641151e172258dff1c0ac1d332b8a85fb22aba4bad3ab88130271",
		"8906061": "218b32bac406d8ad4a62f3ca18773b1f822a0a97b6a52aed0529e9a211f31604",
		"8900548": "22afe317ef95bc199da0612589c5a1ca024dbf4163d2c40283bc758ee8a2b1b4",
		"8900100": "9c79267bded403a7adef49c469f9edc2ff127aecced3ec89de90ed25620be83c",
		"8900818": "3d557f5ebd372891e157270d2579278a8d9e595998696d50038f6077143c28b5",
		"8900836": "13aa4110057e3636c738dc7a11d2b016fdc10787d0fc6c655adfe99969287a9a",
		"8918391": "f3bda4b70aa5cea738d80d670b829647897db696db36e9918829ca4f8e7c54ff",
		"8920227": "4f4a55c5fcd629c539f1ebf5c83df702c3c969ae2e5f27c5999fca174e196470",
		"8924512": "3002250cb0605904fa6c79daf5b772006ddaf09988f7f9cb52b441413026b150",
		"8956060": "6e6b3490025497e19282548748169106e8c88eeb46ecc16d73bbf13089412c6c",
		"8956070": "3f8e1d2a79dfd154aa214cecc38b9c83c5d887bc85a4a778cbc209951a3206f7",
		"8956072": "8f95301fc136dc0253c1dbc3a505175020f11a2152877eb421acba1d1cae6b72",
		"8905507": "6b18acc5d0a445f9167e2b7d75c7d954e8b9882ff0a7c83de17ffea0de0c114e",
		"8905516": "e4476ff3a011b70369570d88e9edfa8b9b406f334ff7bc5f1fe2593e27a3db77",
		"8906062": "ca7464f8c4eaa80e639b0543d7a64138cf23edb5aa3c4b8e37022a5084659092",
		"8956047": "2e27947c6b475d8effad688ec3ab93e494a414a3006541b38227fc234d018cda",
		"8956020": "33b5403f43d76136fd7d6c9915a0c7d5c080776c37cd59355f11d11a4fc7f3d5",
		"8956042": "4c793479970c510fb45cde378fe6f71c03e14e1a8f51af5401e9a27607533dc2",
		"8956007": "90863926d787b82cd6da5bc77dfc22c42a1b8dccef68c79baa7d0380c8eebe47",
		"8956040": "f12eb033b0e084515b52e01b32d4650d3e97b890de8a6cdc9e47376ee52c67d4",
		"8956044": "dc3f3052319004a3f0687f9965fefc425e3bd06aaef422c97c4db6291f5a189f",
		"8905506": "4b452e2f5e57de6e35829863a4136d76f375c150c2cb69e3aa6057f22805483c",
		"8905515": "76b9994892972b37deea0609ea0438dbf285b4e9159617e0ab0516a466bbdda2",
		"8900549": "835dc9733b9d31d31514a76965c3997d8713f340390bb067d92d3ccab4c6c76d",
		"8900207": "b73a22eae4494e8bc83cbec01aac696607e451a1095e0fdc563d0083f6ca5f8a",
		"8900413": "c0b6e1b1a579c7948a0e2c40b2b6ccee431728c4aad186a5fb8e9e572d1c2350",
		"8900431": "c5669be0eea869e4172d5413c9ebb77e32c15c861fb8721c666ddcd47d5ab51f",
		"8900330": "6ba800878212d7bdb6592785878903f4e5d814fec7f78fe4d9197b1233718d0a",
		"8900361": "37169cf217e9c48f367e24d976caf594921278bca59698d75dad649b3c51e0fb",
		"8900331": "be6d11058ed8433bc4a21618fa02ec703b0ddfda6ab4ac0080d78291cbd20703",
		"8900570": "8135e6791723a5d6f122aeb1823a99094d9cfa11530bd7ada7cca89982525476",
		"8900184": "33519ac0d0f6a3c45a9680a088eb3cbd41577be6e03ca8e241c9dccbf6119780",
		"8900170": "04e972bf38495cf1062aaa5e4037de7572f7a1cff2508f921c647058a44c9a39",
		"8900347": "97b5fe86ad6f7e8b05fe8c60002e3e2854d355e7db3fbbd5489771e3e8306ae4",
		"8920021": "4583f36ddf739e14d2566effbfb00af217df46860f6048bfc139709ac689710c",
		"8924445": "65ba5b501a9ff4ca161ac0701856f6d4b714aa7d987a75bb2a9a5458a96e7549",
		"8920011": "f760ee560aa8e563fc566ef61b94645110b532f2fb1dd10d35c95ed0b63fe41a",
		"8920012": "4081d2522df2396dc477b6f6b30fcc327baf02656eb7faaf4cf798495b80a4e6",
		"8920013": "fbfc21a2b8db796b775dab4fc208d4b0e215b2c9e78ceaf436da2d60687b92f8",
		"8920019": "4b92a2d3937a500d5dd71c8fb711b7e486e317160be428172e10ac43dab531fa",
		"8924077": "712f5f9e229cea8c1e13346f402810c5b10c2e09ba65162c0a84295bffb02872",
		"8924079": "b1b9a232ba61f97915b086fc5ee264e1deeec02da566198e2bbce05e4718d334",
		"8924401": "8ec9e8a9ee47eb5e4dd5e6de04667f01f918f0a42c816240f0cd11f9a683c933",
		"8920076": "82780349ce4720f4a85f450a0c2fbbce725fbc9ae5076f845e3359195eb811cb",
	}
)
"""The SHA-256 of each Prüfbedingung CONDITIONS reads, as the sheets „<Vordruck> - Regeln“ write it with its blanks
collapsed, the Hinweis 8912019 left out. The texts stay in the JD (steuerbote.eric.simulation.kst): a Prüfbedingung
that changes fails JahresdokumentationTest until its reading is checked again."""
COMPARED = MappingProxyType(
	{
		"8906062": "GK_INCOME",
		"8956047": "P8B_CORRECTION",
		"8900207": "SUM_OF_INCOME",
		"8900413": "TOTAL_INCOME",
		"8900431": "ZVE",
		"8900347": "LOSS_REMAINING",
		"8924445": "EINLAGEKONTO_CLOSING",
		"8920012": "EINLAGEKONTO_OPENING",
	}
)
"""The long sum each rule compares its field with, by the name of its terms in steuerbote.eric.simulation.kst."""
BRACED = MappingProxyType(
	{
		"8900184": ("LOSS_BEFORE_DEDUCTION", "LOSS_INCOME"),
		"8900170": ("LOSS_BEFORE_LIMITED", "LOSS_INCOME_LIMITED"),
	}
)
"""The sums in the curly brackets of each rule, in their order (ZI Kap. 4.3.5), by the names of their terms."""
_TERM = re.compile(r"([+-]?)\s*\[(E\d{7})\]")


def terms(formula: str) -> Terms:
	"""The fields of a sum of the JD with their signs, the first without one; ValueError for a formula without a field."""
	found = tuple((-1 if sign == "-" else 1, field) for sign, field in _TERM.findall(formula))
	if not found:
		raise ValueError(f"no field in {formula!r}")
	return found


def compared(condition: str) -> Terms:
	"""The sum a Prüfbedingung compares its field with: the terms after its last „!=“."""
	_, found, after = condition.rpartition("!=")
	if not found:
		raise ValueError(f"no comparison in {condition!r}")
	return terms(after)


def braced(condition: str) -> tuple[Terms, ...]:
	"""The sums in the curly brackets of a Prüfbedingung, in their order."""
	return tuple(terms(group) for group in re.findall(r"\{([^{}]*)\}", condition))


def documented_rules() -> dict[str, Mapping[str, str]]:
	"""The rows of the sheets „<Vordruck> - Regeln“ of Jahresdokumentation_E30_2025.ods by Fehlercode."""
	return {
		row["Fehlercode"]: row
		for form in jd.FORMS[jd.KST]
		for row in jd.sheet(jd.KST, 2025, f"{form} - Regeln")
	}


def collapsed(text: str) -> str:
	return " ".join(text.split())


def vordruck(form: str, values: dict[str, object], *rows: Entry, wj: str = "WJ1") -> Vordruck:
	return Vordruck(form, (*entries(values), *rows), wj if form in INDEXED else None)


def kst1(**changes: object) -> Vordruck:
	"""The KSt 1 of the example with fields changed, a value None leaving a field out."""
	kept = tuple(entry for entry in KST1.entries if entry.feldkennung not in changes)
	return Vordruck(
		"KSt1", (*kept, *entries({key: value for key, value in changes.items() if value is not None}))
	)


def root_of(*given: Vordruck) -> ElementTree.Element:
	if not any(vordruck.form == "KSt1" for vordruck in given):
		given = (KST1, *given)
	return ElementTree.fromstring(kst_xml.to_nutzdaten(2026, given, VORSATZ))


def foreign(root: ElementTree.Element, path: str, text: str) -> ElementTree.Element:
	"""The Nutzdaten with a field of a Vordruck Steuerbote does not write, such as OG, by its path below the root."""
	parent = root
	*contexts, name = path.split("/")
	for context in contexts:
		found = parent.find(f"{{{NAMESPACE}}}{context}")
		parent = ElementTree.SubElement(parent, f"{{{NAMESPACE}}}{context}") if found is None else found
	ElementTree.SubElement(parent, f"{{{NAMESPACE}}}{name}").text = text
	return root


def fails(code: str, *given: Vordruck, root: ElementTree.Element | None = None) -> bool:
	"""Whether the rule of the Fehlercode refuses Nutzdaten of the Vordrucke, with the KSt 1 of the example unless one is
	given."""
	(rule,) = (rule for rule in RULES if rule.condition.code == code)
	return rule(root_of(*given) if root is None else root, KIND, HEADER) is not None


def failing(*given: Vordruck) -> dict[str, str | None]:
	"""Every rule the Nutzdaten fail, with the field its message names."""
	root = ElementTree.fromstring(kst_xml.to_nutzdaten(2026, given, VORSATZ))
	return {message.code: message.field for rule in RULES if (message := rule(root, KIND, HEADER))}


def without(form: str, *names: str) -> tuple[Vordruck, ...]:
	"""The Vordrucke of the example, the fields of the names or, without names, the whole Vordruck left out."""
	return tuple(
		Vordruck(
			found.form, tuple(entry for entry in found.entries if entry.feldkennung not in names), found.wj
		)
		for found in muster_it_gmbh()
		if found.form != form or names
	)


class ExampleTest(TestCase):
	def test_the_muster_it_gmbh_passes_every_rule(self):
		self.assertEqual(failing(*muster_it_gmbh()), {})

	def test_the_simulation_finds_the_muster_it_gmbh_valid_and_names_a_failed_rule(self):
		data = kst_xml.to_nutzdaten(2026, muster_it_gmbh(), VORSATZ)
		result = Simulation().run(Operation.VALIDATE, data, HEADER)
		self.assertIs(result.outcome, Outcome.VALID)
		self.assertEqual([message.code for message in result.messages], ["SIM-000", "SIM-001"])
		result = Simulation().run(
			Operation.VALIDATE, kst_xml.to_nutzdaten(2026, without("GK"), VORSATZ), HEADER
		)
		self.assertIs(result.outcome, Outcome.INVALID)
		(error,) = (message for message in result.messages if message.severity == ERROR)
		self.assertEqual((error.code, error.field), ("8906010", "GK"))
		self.assertEqual(
			error.text,
			"Die Regel 8906010 (Regel_160100_GK_allg) der Jahresdokumentation E30 2025 schlägt an: Vordruck GK.",
		)

	def test_a_change_names_the_rules_it_breaks(self):
		self.assertEqual(failing(*without("ZVE")), {"8900744": "ZVE", "8900548": "E8004904"})
		self.assertEqual(failing(*without("GK", "E8109901")), {"8906061": "E8109901", "8900549": "E8004904"})


class ConditionsTest(TestCase):
	def test_read_every_rule_of_the_catalogue_but_the_hint(self):
		codes = [rule.code for rule in CATALOGUES[2026].rules if not rule.hint]
		self.assertEqual([condition.code for condition in CONDITIONS], codes)
		self.assertEqual(list(PRUEFBEDINGUNGEN), codes)
		self.assertEqual([rule.condition for rule in RULES], list(CONDITIONS))
		self.assertEqual(simulation.CHECKS.rules[1:], RULES)

	def test_a_failed_rule_gives_its_fehlercode_and_names_the_rule_and_its_vordruck_or_field(self):
		message = RULES[0](root_of(), KIND, HEADER)
		self.assertEqual((message.code, message.severity, message.field), ("8906010", ERROR, "GK"))
		documented = simulation._year(2026)
		self.assertEqual(message.text, documented.failure(CONDITIONS[0]))
		by_code = {condition.code: condition for condition in CONDITIONS}
		self.assertEqual(
			documented.failure(by_code["8906061"]),
			"Die Regel 8906061 (Regel_160151_GK_Zinsschranke) der Jahresdokumentation E30 2025 schlägt an: E8109901 im "
			"Vordruck GK, Zeile 300.",
		)
		self.assertEqual(
			documented.failure(by_code["8900709"]),
			"Die Regel 8900709 (Regel_170009_KSt1_allgAngaben) der Jahresdokumentation E30 2025 schlägt an: E8000016 im "
			"Vordruck KSt1.",
		)

	def test_each_condition_names_a_vordruck_or_a_field_of_the_catalogue(self):
		documented = simulation._year(2026)
		for condition in CONDITIONS:
			with self.subTest(code=condition.code):
				self.assertIn(condition.field, documented.place(condition.field))

	def test_a_year_without_vordrucke_is_not_checked(self):
		document = jd.in_documentation_year(kst_xml.nutzdaten(2026, (KST1,), VORSATZ), KIND, kst(2025))
		root = ElementTree.fromstring(etree.tostring(document))
		self.assertIsNone(RULES[0](root, kst(2025), HEADER))

	def test_a_text_that_is_no_number_is_left_to_the_schema(self):
		root = root_of(vordruck("ZVE", {"E8007504": Decimal("100"), "E8007502": Decimal("15")}))
		(field,) = root.iter(f"{{{NAMESPACE}}}E8007502")
		field.text = "fünfzehn"
		self.assertFalse(fails("8900331", root=root))
		rule = SimulatedRule(
			Condition("8900331", "E8007502", lambda e: e.value("E8007502") > 0), simulation._year
		)
		self.assertIsNone(rule(root, KIND, HEADER))


class ReadingTest(TestCase):
	def test_reads_numbers_with_their_decimal_comma(self):
		self.assertEqual(number("-12000,50"), Decimal("-12000.50"))
		for text in ("zwölf", "NaN", "Infinity", ""):
			with self.subTest(text=text), self.assertRaises(NotANumber):
				number(text)

	def test_a_sum_names_its_fields_with_the_signs_of_the_pruefbedingung(self):
		self.assertEqual(
			sum_of("E8002001 E8002004 -E8002204"), ((1, "E8002001"), (1, "E8002004"), (-1, "E8002204"))
		)

	def test_the_test_reads_the_terms_of_a_sum_in_a_pruefbedingung(self):
		self.assertEqual(
			terms("[E8002001] + [E8002004] -[E8002204]"), ((1, "E8002001"), (1, "E8002004"), (-1, "E8002204"))
		)
		self.assertEqual(
			compared("FeldAngegeben(E1) Und [E8007501] != Summe(E8007504) + [E8007603]"), ((1, "E8007603"),)
		)
		self.assertEqual(
			braced("Min({[E1000001] - [E1000002]}, {[E1000003]})"),
			(((1, "E1000001"), (-1, "E1000002")), ((1, "E1000003"),)),
		)
		with self.assertRaises(ValueError):
			terms("Summe()")
		with self.assertRaises(ValueError):
			compared("FeldAngegeben(E8007501)")

	def test_the_long_sums_have_the_terms_of_the_jahresdokumentation(self):
		self.assertEqual(len(simulation.GK_INCOME), 118)
		self.assertEqual(simulation.GK_INCOME[:3], ((1, "E8002001"), (1, "E8002004"), (1, "E8002006")))
		self.assertEqual(len(simulation.P8B_CORRECTION), 15)
		self.assertEqual(len(simulation.SUM_OF_INCOME), 40)
		self.assertEqual(len(simulation.TOTAL_INCOME), 14)
		self.assertEqual(len(simulation.ZVE), 25)
		self.assertEqual(len(simulation.EINLAGEKONTO_CLOSING), 38)
		self.assertEqual(len(simulation.LOSS_REMAINING), 13)
		self.assertEqual(simulation.LOSS_INCOME, ((1, "E8008501"), (-1, "E8008502")))

	def test_a_field_without_a_text_is_not_given(self):
		root = root_of(vordruck("ZVE", {"E8007504": Decimal("100"), "E8007502": Decimal("15")}))
		(field,) = root.iter(f"{{{NAMESPACE}}}E8007502")
		field.text = " "
		zve = Erklaerung(root, RECHTSFORMEN[2026]).one("ZVE")
		self.assertEqual((zve.any_of("E8007502"), zve.any_of("E8007504")), (False, True))
		self.assertTrue(fails("8900361", root=root))

	def test_an_empty_vordruck_and_a_rechtsform_without_a_category(self):
		erklaerung = Erklaerung(root_of(kst1(E8001105="310")), RECHTSFORMEN[2026])
		self.assertFalse(erklaerung.one("GK").filled)
		self.assertEqual(erklaerung.value("E8109901"), Decimal("0"))
		self.assertEqual(erklaerung.text("E8109901"), "")
		self.assertEqual(erklaerung.category("E8001105", "RF_Gruppe"), "")
		self.assertEqual(Erklaerung(root_of(), RECHTSFORMEN[2026]).category("E8001105", "RF_Gruppe"), "1")


class VordruckeTest(TestCase):
	"""The Vordrucke a GmbH files and the fields they need."""

	def test_8906010_a_gmbh_files_anlage_gk(self):
		self.assertTrue(fails("8906010"))
		self.assertFalse(fails("8906010", vordruck("GK", {"E8002001": Decimal("1")})))
		self.assertFalse(fails("8906010", kst1(E8001506=True)))
		self.assertFalse(fails("8906010", kst1(E8001105="310")))
		self.assertTrue(fails("8906010", kst1(E8000603="Frankreich")))
		self.assertFalse(fails("8906010", kst1(E8000603="Frankreich", E8000702="Frankreich")))
		self.assertFalse(fails("8906010", kst1(E8000803="1")))
		self.assertFalse(fails("8906010", kst1(E8001702="1")))
		self.assertFalse(fails("8906010", vordruck("ZVE", {"E8025903": Decimal("1")})))

	def test_8900744_files_anlage_zve_unless_exempt(self):
		self.assertTrue(fails("8900744"))
		self.assertFalse(fails("8900744", vordruck("ZVE", {"E8007501": Decimal("0")})))
		self.assertFalse(fails("8900744", kst1(E8001506=True)))

	def test_8912208_and_8912209_a_kapitalgesellschaft_files_anlage_wa_with_line_15(self):
		self.assertTrue(fails("8912208"))
		self.assertFalse(fails("8912208", kst1(E8001105="310")))
		self.assertFalse(fails("8912208", vordruck("WA", {"E8122801": False})))
		self.assertTrue(fails("8912209", vordruck("WA", {"E8120401": Decimal("1.00")})))
		self.assertFalse(fails("8912209", vordruck("WA", {"E8122801": False})))
		self.assertFalse(fails("8912209"))

	def test_8931022_and_8900709_files_kst_1_f_and_says_so_on_kst_1(self):
		kst1f = vordruck("KSt1F", {"E8240103": Decimal("0"), "E8245601": Decimal("0")})
		self.assertTrue(fails("8931022"))
		self.assertFalse(fails("8931022", kst1f))
		self.assertFalse(fails("8931022", kst1(E8001702="1")))
		self.assertFalse(fails("8931022", kst1(E8000603="Frankreich", E8000702="Frankreich")))
		self.assertTrue(fails("8931022", kst1(E8000603="Frankreich", E8000702="Frankreich", E8000803="1")))
		self.assertFalse(fails("8931022", kst1(E8001105="310")))
		self.assertFalse(fails("8900709", kst1f))
		self.assertTrue(fails("8900709", kst1(E8000016=None), kst1f))
		self.assertFalse(fails("8900709", kst1(E8000016=None)))
		self.assertTrue(
			fails("8900709", root=foreign(root_of(kst1(E8000016=None)), "KSt1Fa/Feld/E8270101", "1"))
		)

	def test_8912151_8912163_and_8900368_kst_1_names_its_anteilseigner_and_says_what_changed(self):
		no_shareholder = Vordruck(
			"KSt1",
			tuple(entry for entry in KST1.entries if entry.feldkennung not in ("E8122101", "E8001105")),
		)
		self.assertFalse(fails("8912151"))
		self.assertTrue(fails("8912151", no_shareholder.extended(Entry("E8001105", "350"))))
		self.assertFalse(fails("8912151", no_shareholder.extended(Entry("E8001105", "310"))))
		self.assertTrue(fails("8912163", kst1(E8122601=None)))
		self.assertFalse(fails("8912163", kst1(E8122601=None, E8001506=True)))
		self.assertFalse(fails("8912163"))
		self.assertTrue(fails("8900368", kst1(E8001007=None)))
		self.assertFalse(fails("8900368", kst1(E8001007=None, E8001505="3")))

	def test_8900070_8906061_each_anlage_gk_has_lines_11_or_12_and_300(self):
		self.assertTrue(fails("8900070", vordruck("GK", {"E8109901": Decimal("1")})))
		self.assertFalse(fails("8900070", vordruck("GK", {"E8002004": Decimal("1")})))
		second = vordruck("GK", {"E8109901": Decimal("1")}, wj="WJ2")
		self.assertTrue(fails("8900070", vordruck("GK", {"E8002001": Decimal("1")}), second))
		self.assertTrue(fails("8906061", vordruck("GK", {"E8002001": Decimal("1")})))
		self.assertFalse(fails("8906061", vordruck("GK", {"E8109901": Decimal("1")})))

	def test_8900548_8900100_8900818_8900836_anlage_zve_holds_its_lines(self):
		gk = vordruck("GK", {"E8002001": Decimal("1")})
		self.assertTrue(fails("8900548", gk, vordruck("ZVE", {"E8005401": Decimal("1")})))
		self.assertFalse(fails("8900548", gk, vordruck("ZVE", {"E8004904": Decimal("1")})))
		self.assertFalse(fails("8900548", vordruck("ZVE", {"E8005401": Decimal("1")})))
		self.assertTrue(fails("8900100", vordruck("ZVE", {"E8004904": Decimal("1")})))
		self.assertFalse(fails("8900100", vordruck("ZVE", {"E8007704": Decimal("1")})))
		self.assertFalse(fails("8900100"))
		self.assertTrue(fails("8900818", vordruck("ZVE", {"E8004904": Decimal("1")})))
		self.assertFalse(fails("8900818", vordruck("ZVE", {"E8025903": Decimal("1")})))
		self.assertFalse(fails("8900818", vordruck("ZVE", {"E8006901": Decimal("1")})))
		root = foreign(root_of(vordruck("ZVE", {"E8004904": Decimal("1")})), "OHK/Allgemein/E8301001", "1")
		self.assertFalse(fails("8900818", root=root))
		self.assertTrue(fails("8900836", vordruck("ZVE", {"E8004904": Decimal("1")})))
		self.assertFalse(fails("8900836", vordruck("ZVE", {"E8007704": Decimal("1")})))

	def test_8918391_anlage_verluste_holds_the_verlustvortrag_at_the_end(self):
		self.assertTrue(fails("8918391", vordruck("Verluste", {"E8007801": Decimal("100")})))
		self.assertFalse(fails("8918391", vordruck("Verluste", {"E8009201": Decimal("0")})))
		self.assertFalse(fails("8918391"))

	def test_8920227_8924512_kst_1_f_holds_a_bestand_at_the_start_and_the_end(self):
		self.assertTrue(fails("8920227", vordruck("KSt1F", {"E8240103": Decimal("0")})))
		self.assertFalse(
			fails("8920227", vordruck("KSt1F", {"E8240103": Decimal("0"), "E8245601": Decimal("0")}))
		)
		self.assertTrue(fails("8924512", vordruck("KSt1F", {"E8245601": Decimal("0")})))
		self.assertFalse(
			fails("8924512", vordruck("KSt1F", {"E8240201": Decimal("0"), "E8245601": Decimal("0")}))
		)

	def test_a_total_of_8b_needs_the_single_values_of_its_holdings(self):
		for code, total, single in (
			("8956060", "E8560401", "E8560404"),
			("8956070", "E8561212", "E8561211"),
			("8956072", "E8561410", "E8561403"),
			("8905507", "E8561220", "E8561210"),
			("8905516", "E8561411", "E8561408"),
		):
			with self.subTest(code=code):
				self.assertTrue(fails(code, vordruck("GK", {total: Decimal("0")})))
				value = Decimal("0") if single == "E8561408" else Decimal("0.00")
				self.assertFalse(
					fails(code, vordruck("GK", {total: Decimal("0")}, Entry(single, value, (0,))))
				)
				self.assertFalse(fails(code, vordruck("GK", {"E8002001": Decimal("1")})))


def euros(value: str) -> Decimal:
	return Decimal(value)


class AnlageGkTest(TestCase):
	"""Line 300 and the lines of § 8b KStG, rounded as the Jahresdokumentation rounds them."""

	def test_8906062_line_300_is_the_sum_of_its_lines(self):
		lines = {"E8002001": euros("100"), "E8002204": euros("30"), "E8100301": euros("5")}
		self.assertFalse(fails("8906062", vordruck("GK", {**lines, "E8109901": euros("75")})))
		self.assertTrue(fails("8906062", vordruck("GK", {**lines, "E8109901": euros("76")})))
		self.assertFalse(fails("8906062", vordruck("GK", {"E8109901": euros("76")})))
		second = vordruck("GK", {"E8002001": euros("1"), "E8109901": euros("2")}, wj="WJ2")
		self.assertTrue(fails("8906062", vordruck("GK", {**lines, "E8109901": euros("75")}), second))

	def test_8956047_line_201_corrects_the_lines_of_8b(self):
		holding = (Entry("E8560404", euros("1000.00"), (0,)),)
		lines = {"E8560401": euros("1000"), "E8560801": euros("50")}
		self.assertFalse(fails("8956047", vordruck("GK", {**lines, "E8562101": euros("-950")}, *holding)))
		self.assertTrue(fails("8956047", vordruck("GK", {**lines, "E8562101": euros("-951")}, *holding)))
		self.assertFalse(fails("8956047", vordruck("GK", {"E8562101": euros("-951")})))
		root = foreign(
			root_of(vordruck("GK", {**lines, "E8562101": euros("-951")}, *holding)),
			"OG/Allgemein/OT/E8160202",
			"1",
		)
		self.assertFalse(fails("8956047", root=root))

	def test_8956020_line_160_is_5_percent_of_line_156_rounded_down(self):
		self.assertFalse(
			fails("8956020", vordruck("GK", {"E8560401": euros("12019"), "E8560801": euros("600")}))
		)
		self.assertTrue(
			fails("8956020", vordruck("GK", {"E8560401": euros("12019"), "E8560801": euros("601")}))
		)
		self.assertFalse(fails("8956020", vordruck("GK", {"E8560801": euros("601")})))
		root = foreign(
			root_of(vordruck("GK", {"E8560401": euros("12019"), "E8560801": euros("601")})),
			"OG/Allgemein/OT/E8160202",
			"1",
		)
		self.assertFalse(fails("8956020", root=root))

	def test_8956042_line_181_is_5_percent_of_the_gains_rounded_down(self):
		gains = {"E8561212": euros("30010"), "E8561220": euros("9"), "E8561237": euros("10")}
		self.assertFalse(fails("8956042", vordruck("GK", {**gains, "E8561301": euros("1501")})))
		self.assertTrue(fails("8956042", vordruck("GK", {**gains, "E8561301": euros("1502")})))
		self.assertFalse(fails("8956042", vordruck("GK", {"E8561301": euros("1502")})))
		root = foreign(
			root_of(vordruck("GK", {**gains, "E8561301": euros("1502")})), "OG/Allgemein/OT/E8160202", "1"
		)
		self.assertFalse(fails("8956042", root=root))

	def test_the_totals_of_8b_are_their_single_values_rounded(self):
		for code, total, single, cents, rounded in (
			("8956007", "E8560401", "E8560404", ("100.20", "200.40"), "301"),
			("8956040", "E8561212", "E8561211", ("100.20", "200.40"), "301"),
			("8956044", "E8561410", "E8561403", ("100.20", "200.40"), "300"),
			("8905506", "E8561220", "E8561210", ("100.20", "200.40"), "301"),
			("8905515", "E8561411", "E8561408", ("100", "200"), "300"),
		):
			with self.subTest(code=code):
				rows = tuple(Entry(single, euros(value), (row,)) for row, value in enumerate(cents))
				self.assertFalse(fails(code, vordruck("GK", {total: euros(rounded)}, *rows)))
				self.assertTrue(fails(code, vordruck("GK", {total: euros(rounded) + 1}, *rows)))
				self.assertFalse(fails(code, vordruck("GK", {total: euros(rounded) + 1})))


class AnlageZveTest(TestCase):
	"""Lines 2, 32, 53 and 70 to 72a of Anlage ZVE and the Körperschaftsteuer."""

	def test_8900549_line_2_is_line_300_of_the_only_anlage_gk(self):
		gk = vordruck("GK", {"E8002001": euros("100"), "E8109901": euros("100")})
		self.assertFalse(fails("8900549", gk, vordruck("ZVE", {"E8004904": euros("100")})))
		self.assertTrue(fails("8900549", gk, vordruck("ZVE", {"E8004904": euros("101")})))
		second = vordruck("GK", {"E8002001": euros("1"), "E8109901": euros("1")}, wj="WJ2")
		self.assertFalse(fails("8900549", gk, second, vordruck("ZVE", {"E8004904": euros("101")})))
		self.assertTrue(fails("8900549", second, vordruck("ZVE", {"E8004904": euros("1")})))
		self.assertFalse(fails("8900549", gk, vordruck("ZVE", {"E8005401": euros("1")})))

	def test_8900207_line_32_is_the_sum_of_the_einkuenfte(self):
		lines = {"E8004904": euros("100"), "E8004201": euros("10")}
		self.assertFalse(fails("8900207", vordruck("ZVE", {**lines, "E8005401": euros("90")})))
		self.assertTrue(fails("8900207", vordruck("ZVE", {**lines, "E8005401": euros("91")})))
		self.assertFalse(
			fails("8900207", kst1(E8001506=True), vordruck("ZVE", {**lines, "E8005401": euros("91")}))
		)
		self.assertFalse(
			fails("8900207", vordruck("ZVE", {**lines, "E8025903": euros("1"), "E8005401": euros("91")}))
		)

	def test_8900413_line_53_is_the_gesamtbetrag_der_einkuenfte(self):
		lines = {"E8005401": euros("100"), "E8005601": euros("10")}
		self.assertFalse(fails("8900413", vordruck("ZVE", {**lines, "E8006901": euros("90")})))
		self.assertTrue(fails("8900413", vordruck("ZVE", {**lines, "E8006901": euros("91")})))
		root = foreign(
			root_of(vordruck("ZVE", {**lines, "E8006901": euros("91")})), "OHK/Allgemein/E8301001", "1"
		)
		self.assertFalse(fails("8900413", root=root))
		self.assertFalse(
			fails("8900413", kst1(E8001506=True), vordruck("ZVE", {**lines, "E8006901": euros("91")}))
		)

	def test_8900431_line_70_is_the_zu_versteuerndes_einkommen(self):
		lines = {"E8005401": euros("100"), "E8005601": euros("10"), "E8007001": euros("20")}
		self.assertFalse(fails("8900431", vordruck("ZVE", {**lines, "E8007501": euros("70")})))
		self.assertTrue(fails("8900431", vordruck("ZVE", {**lines, "E8007501": euros("71")})))
		self.assertFalse(
			fails("8900431", vordruck("ZVE", {**lines, "E8025402": euros("1"), "E8007501": euros("71")}))
		)

	def test_8900330_lines_71_and_72a_make_line_70(self):
		self.assertFalse(
			fails(
				"8900330",
				vordruck("ZVE", {"E8007501": euros("100"), "E8007504": euros("60"), "E8007603": euros("40")}),
			)
		)
		self.assertTrue(
			fails("8900330", vordruck("ZVE", {"E8007501": euros("100"), "E8007504": euros("60")}))
		)
		self.assertFalse(fails("8900330", vordruck("ZVE", {"E8007501": euros("100")})))

	def test_8900361_the_tax_goes_with_its_base(self):
		self.assertTrue(fails("8900361", vordruck("ZVE", {"E8007504": euros("100")})))
		self.assertTrue(fails("8900361", vordruck("ZVE", {"E8007502": euros("15")})))
		self.assertFalse(
			fails("8900361", vordruck("ZVE", {"E8007504": euros("100"), "E8007502": euros("15")}))
		)
		self.assertFalse(fails("8900361", vordruck("ZVE", {"E8007501": euros("100")})))

	def test_8900331_and_8900570_the_tax_is_15_percent_rounded_down_and_zero_without_income(self):
		self.assertFalse(
			fails("8900331", vordruck("ZVE", {"E8007504": euros("99"), "E8007502": euros("14")}))
		)
		self.assertTrue(fails("8900331", vordruck("ZVE", {"E8007504": euros("99"), "E8007502": euros("15")})))
		self.assertFalse(
			fails("8900331", vordruck("ZVE", {"E8007504": euros("-99"), "E8007502": euros("15")}))
		)
		self.assertTrue(fails("8900570", vordruck("ZVE", {"E8007504": euros("-99"), "E8007502": euros("1")})))
		self.assertFalse(fails("8900570", vordruck("ZVE", {"E8007504": euros("0"), "E8007502": euros("0")})))
		self.assertFalse(fails("8900570", vordruck("ZVE", {"E8007504": euros("99"), "E8007502": euros("1")})))


CARRIED = {"E8007801": euros("3000000"), "E8008501": euros("2500000")}
"""A Verlustvortrag of 3 Mio. € and a Gesamtbetrag der Einkünfte of 2.5 Mio. €."""
OPENING = {"E8240103": euros("30000")}
EQUITY = {
	"E8201001": euros("60000"),
	"E8201101": euros("25000"),
	"E8201201": euros("30000"),
	"E8201301": euros("5000"),
}
"""Eigenkapital 60,000 € less Nennkapital 25,000 € less the Bestand of 30,000 € leaves 5,000 € to distribute."""
SET_OFF = {
	"E8200502": euros("12000"),
	"E8240302": euros("12000"),
	"E8240401": euros("5000"),
	"E8240501": euros("7000"),
}
"""Leistungen of 12,000 €, 7,000 € of them beyond the ausschüttbarer Gewinn."""


class AnlageVerlusteTest(TestCase):
	"""The Verlustabzug of § 10d Absatz 2 EStG: a million in full, 70 % of the rest."""

	def test_8900184_line_25_is_the_least_of_carry_forward_income_and_a_million(self):
		self.assertFalse(fails("8900184", vordruck("Verluste", {**CARRIED, "E8008601": euros("1000000")})))
		self.assertTrue(fails("8900184", vordruck("Verluste", {**CARRIED, "E8008601": euros("999999")})))
		small = {"E8007801": euros("300"), "E8008501": euros("2500000"), "E8008502": euros("100")}
		self.assertFalse(fails("8900184", vordruck("Verluste", {**small, "E8008601": euros("300")})))
		self.assertFalse(
			fails("8900184", vordruck("Verluste", {"E8007801": euros("300"), "E8008601": euros("1")}))
		)

	def test_8900170_line_27_is_70_percent_of_the_rest_rounded_up(self):
		lines = {
			**CARRIED,
			"E8008601": euros("1000000"),
			"E8008602": euros("1000000"),
			"E8008701": euros("1500000"),
		}
		self.assertFalse(fails("8900170", vordruck("Verluste", {**lines, "E8008801": euros("1050000")})))
		self.assertTrue(fails("8900170", vordruck("Verluste", {**lines, "E8008801": euros("1050001")})))
		odd = {**lines, "E8008501": euros("2500001")}
		self.assertFalse(fails("8900170", vordruck("Verluste", {**odd, "E8008801": euros("1050001")})))
		self.assertFalse(fails("8900170", vordruck("Verluste", {**CARRIED, "E8008801": euros("1")})))

	def test_8900347_line_28_is_what_remains(self):
		lines = {**CARRIED, "E8008602": euros("1000000"), "E8008801": euros("1050000")}
		self.assertFalse(fails("8900347", vordruck("Verluste", {**lines, "E8009201": euros("950000")})))
		self.assertTrue(fails("8900347", vordruck("Verluste", {**lines, "E8009201": euros("950001")})))
		self.assertTrue(
			fails("8900347", vordruck("Verluste", {"E8008001": euros("5"), "E8009201": euros("0")}))
		)
		self.assertFalse(fails("8900347", vordruck("Verluste", {"E8009201": euros("5")})))


class Kst1fTest(TestCase):
	"""The steuerliches Einlagekonto of KSt 1 F."""

	def kst1f(self, *changes: dict[str, object]) -> Vordruck:
		values: dict[str, object] = {}
		for change in changes:
			values.update(change)
		return vordruck("KSt1F", {key: value for key, value in values.items() if value is not None})

	def test_8920021_line_20_is_the_equity_less_nennkapital_and_bestand(self):
		self.assertFalse(fails("8920021", self.kst1f(EQUITY)))
		self.assertTrue(fails("8920021", self.kst1f(EQUITY, {"E8201301": euros("5001")})))
		self.assertFalse(
			fails("8920021", self.kst1f(EQUITY, {"E8201001": euros("50000"), "E8201301": euros("0")}))
		)
		self.assertFalse(fails("8920021", self.kst1f({"E8201301": euros("5001")})))

	def test_8924445_line_152_rolls_the_einlagekonto_forward(self):
		lines = {**OPENING, "E8242201": euros("7000"), "E8241601": euros("500")}
		self.assertFalse(fails("8924445", self.kst1f(lines, {"E8245601": euros("23500")})))
		self.assertTrue(fails("8924445", self.kst1f(lines, {"E8245601": euros("23501")})))
		self.assertFalse(fails("8924445", self.kst1f({"E8240201": euros("1"), "E8245601": euros("23501")})))

	def test_8920011_leistungen_with_an_einlagekonto_need_lines_17_to_20(self):
		self.assertTrue(fails("8920011", self.kst1f(OPENING, {"E8200502": euros("12000")})))
		self.assertFalse(fails("8920011", self.kst1f(OPENING, EQUITY, {"E8200502": euros("12000")})))
		self.assertFalse(fails("8920011", self.kst1f({"E8240103": euros("0"), "E8200502": euros("12000")})))

	def test_8920012_8920013_8920019_line_46_where_the_leistungen_exceed_the_distributable_profit(self):
		with_subtotal = self.kst1f(OPENING, EQUITY, SET_OFF, {"E8241717": euros("30000")})
		self.assertFalse(fails("8920012", with_subtotal))
		self.assertFalse(fails("8920013", with_subtotal))
		self.assertFalse(fails("8920019", with_subtotal))
		wrong = self.kst1f(OPENING, EQUITY, SET_OFF, {"E8241717": euros("29999")})
		self.assertTrue(fails("8920012", wrong))
		self.assertTrue(fails("8920013", self.kst1f(OPENING, EQUITY, SET_OFF)))
		self.assertTrue(fails("8920013", self.kst1f(OPENING, {"E8242205": euros("1")})))
		within = {"E8240302": euros("4000"), "E8240401": euros("5000"), "E8240501": euros("-1000")}
		self.assertFalse(fails("8920013", self.kst1f(OPENING, within)))
		self.assertTrue(fails("8920019", self.kst1f(OPENING, within, {"E8241717": euros("30000")})))
		self.assertTrue(
			fails("8920019", self.kst1f({"E8240103": euros("0")}, SET_OFF, {"E8241717": euros("0")}))
		)
		self.assertTrue(fails("8920019", self.kst1f(OPENING, {"E8241717": euros("30000")})))
		self.assertFalse(
			fails("8920019", self.kst1f(OPENING, {"E8240303": euros("1"), "E8241717": euros("30000")}))
		)

	def test_8924077_8924079_8924401_lines_47_to_49_carry_lines_11_and_20(self):
		lines = self.kst1f(OPENING, EQUITY, SET_OFF)
		for code in ("8924077", "8924079", "8924401"):
			with self.subTest(code=code):
				self.assertFalse(fails(code, lines))
		self.assertTrue(fails("8924077", self.kst1f(SET_OFF, {"E8240302": euros("12001")})))
		self.assertFalse(
			fails("8924077", self.kst1f(SET_OFF, {"E8240302": euros("12001"), "E8242205": euros("1")}))
		)
		self.assertTrue(fails("8924079", self.kst1f(EQUITY, SET_OFF, {"E8240401": euros("5001")})))
		self.assertTrue(fails("8924401", self.kst1f(SET_OFF, {"E8240501": euros("7001")})))
		self.assertFalse(fails("8924401", self.kst1f({"E8240501": euros("7001")})))

	def test_8920076_line_50_is_the_least_of_lines_46_49_and_12(self):
		lines = {**OPENING, **SET_OFF, "E8241717": euros("30000"), "E8122003": euros("6000")}
		self.assertFalse(fails("8920076", self.kst1f(lines, {"E8242201": euros("6000")})))
		self.assertTrue(fails("8920076", self.kst1f(lines, {"E8242201": euros("7000")})))
		self.assertFalse(fails("8920076", self.kst1f(lines, {"E8242201": euros("7000"), "E8122011": True})))
		self.assertFalse(fails("8920076", self.kst1f({"E8242201": euros("7000")})))
		self.assertFalse(
			fails("8920076", self.kst1f(lines, {"E8240501": euros("-1000"), "E8242201": euros("0")}))
		)


class JahresdokumentationTest(TestCase):
	"""The Prüfbedingungen against Jahresdokumentation_E30_2025.ods."""

	def test_each_pruefbedingung_is_the_one_its_condition_reads(self):
		rows = documented_rules()
		for code, digest in PRUEFBEDINGUNGEN.items():
			with self.subTest(code=code):
				condition = collapsed(rows[code]["Prüfbedingung"])
				self.assertEqual(hashlib.sha256(condition.encode("utf-8")).hexdigest(), digest)
				self.assertEqual(rows[code]["Regelart"], "Fehler")

	def test_each_long_sum_has_the_terms_of_its_pruefbedingung(self):
		rows = documented_rules()
		for code, name in COMPARED.items():
			with self.subTest(code=code):
				self.assertEqual(getattr(simulation, name), compared(collapsed(rows[code]["Prüfbedingung"])))
		for code, names in BRACED.items():
			with self.subTest(code=code):
				self.assertEqual(
					tuple(getattr(simulation, name) for name in names),
					braced(collapsed(rows[code]["Prüfbedingung"])),
				)

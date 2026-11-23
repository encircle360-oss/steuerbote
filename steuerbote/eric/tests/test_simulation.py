"""The simulation of the Erklärungen and of the E-Bilanz: steuerbote.eric.simulation with steuerbote.eric.fake."""

import hashlib
import os
import re
import shutil
import tempfile
from dataclasses import replace
from pathlib import Path
from types import MappingProxyType
from unittest import TestCase, mock

from lxml import etree

from steuerbote.elster.tests import eric_schema
from steuerbote.eric import fake
from steuerbote.eric.datenart import Datenart, bilanz, gewst, kst, ust
from steuerbote.eric.fake import DOCUMENTATION_VARIABLE, Simulation
from steuerbote.eric.header import EnvelopeHeader
from steuerbote.eric.result import ERROR, HINT, TESTMERKER, Message, Operation, Outcome
from steuerbote.eric.simulation import Checks, erklaerung
from steuerbote.eric.simulation import bilanz as bilanz_checks
from steuerbote.eric.simulation import gewst as gewst_checks
from steuerbote.eric.simulation import kst as kst_checks

# Invented Nutzdaten of an Erklärung: its main form and its Vorsatz, as elster/vorsatz.py writes it.
NUTZDATEN = (
	'<{root} xmlns="{namespace}" version="{version}">\n'
	"\t<{form}>{content}</{form}>\n"
	"\t<Vorsatz>\n"
	"\t\t<Unterfallart>{unterfallart}</Unterfallart>\n"
	"\t\t<Vorgang>01</Vorgang>\n"
	"\t\t<StNr>9198011310010</StNr>\n"
	"\t\t<Zeitraum>{version}</Zeitraum>\n"
	"\t\t<AbsName>Beispiel GmbH</AbsName>\n"
	"\t\t<AbsStr>Hauptstraße 1</AbsStr>\n"
	"\t\t<AbsPlz>80331</AbsPlz>\n"
	"\t\t<AbsOrt>München</AbsOrt>\n"
	"\t\t<Copyright>(c) 2026 Beispiel Software GmbH, München</Copyright>\n"
	"\t\t<OrdNrArt>S</OrdNrArt>\n"
	"\t\t<Rueckuebermittlung><Bescheid>2</Bescheid></Rueckuebermittlung>\n"
	"\t</Vorsatz>\n"
	"</{root}>\n"
)
MAIN_FORMS = MappingProxyType({"USt": "USt2A", "KSt": "KSt1", "GewSt": "GewSt1A"})
# The main form holds the name of the company; USt2A holds a return of a year without amounts with the address and Kz
# 133, which keeps the rules of the Jahresdokumentation E50 2026 that the simulation checks (simulation/ust.py).
COMPANY = "<Allg><Unternehmen><E3000901>Beispiel GmbH</E3000901></Unternehmen></Allg>"
CONTENTS = MappingProxyType(
	{
		"USt": (
			"<Allg><Unternehmen><E3000901>Beispiel GmbH</E3000901><Adr><E3001101>Hauptstraße</E3001101>"
			"<E3001203>1</E3001203><E3001206>80331</E3001206><E3001207>München</E3001207></Adr></Unternehmen>"
			"<Best_Art><E3002203>1</E3002203></Best_Art></Allg>"
			"<Umsaetze><Tabelle><Ums_allg><E3003303>0</E3003303><E3003304>0,00</E3003304></Ums_allg>"
			"<Ums_Sum><E3006001>0,00</E3006001></Ums_Sum></Tabelle></Umsaetze>"
			"<Berech_USt><Tabelle><E3009201>0,00</E3009201><E3009801>0,00</E3009801><E3010201>0,00</E3010201>"
			"<E3010601>0,00</E3010601><Verbl_USt><E3011101>0,00</E3011101><E3011301>0,00</E3011301></Verbl_USt>"
			"<Zahl_Erstatt><E3011401>0,00</E3011401></Zahl_Erstatt></Tabelle></Berech_USt>"
		)
	}
)
USt_2026 = ust(2026)
HEADER = EnvelopeHeader(
	hersteller_id="00000",
	datenlieferant="Beispiel GmbH",
	produkt_name="Steuerbote",
	produkt_version="0.1.0",
	empfaenger="9198",
	datenart_version="USt_2026",
	testmerker=None,
	nutzdaten_ticket="1",
)
# An invented E-Bilanz: the wrapper of ebilanz_000002.xsd around an XBRL instance without facts.
EBILANZ = (
	'<ebilanz:EBilanz xmlns:ebilanz="http://rzf.fin-nrw.de/RMS/EBilanz/2016/XMLSchema" version="2">'
	"<ebilanz:stichtag>20261231</ebilanz:stichtag>"
	'<xbrli:xbrl xmlns:xbrli="http://www.xbrl.org/2003/instance"></xbrli:xbrl>'
	"</ebilanz:EBilanz>"
)
ERSTELLER = "Beispiel GmbH; Hauptstraße; 1; ; ; 80331; München; Deutschland; 089 1234567; info@example.org"
BILANZ_HEADER = replace(HEADER, datenart_version="Bilanz_6.9", nutzdaten_datenlieferant=ERSTELLER)


def nutzdaten(kind: Datenart) -> str:
	return NUTZDATEN.format(
		root=kind.root,
		namespace=kind.namespace,
		version=kind.root_version,
		form=MAIN_FORMS[kind.name],
		content=CONTENTS.get(kind.name, COMPANY),
		unterfallart=kind.unterfallart,
	)


def header_of(kind: Datenart, operation: Operation = Operation.VALIDATE) -> EnvelopeHeader:
	testmerker = TESTMERKER if operation is Operation.TEST_SEND else None
	return replace(HEADER, datenart_version=kind.version, testmerker=testmerker)


def codes(result) -> list[str]:
	return [message.code for message in result.messages]


def errors(result) -> list[tuple[str, str | None]]:
	return [(message.code, message.field) for message in result.messages if message.severity == ERROR]


class SimulationTestCase(TestCase):
	def setUp(self):
		self.directory = Path(tempfile.mkdtemp(prefix="steuerbote-eric-simulation-"))
		self.addCleanup(shutil.rmtree, self.directory)
		patcher = mock.patch.dict(os.environ)
		patcher.start()
		self.addCleanup(patcher.stop)
		os.environ.pop(DOCUMENTATION_VARIABLE, None)

	def refused(self, data: str, kind: Datenart = USt_2026, header: EnvelopeHeader | None = None) -> Message:
		"""The one error of the simulation for the Nutzdaten."""
		result = Simulation().run(Operation.VALIDATE, data, header or header_of(kind))
		self.assertIs(result.outcome, Outcome.INVALID)
		(error,) = (message for message in result.messages if message.severity == ERROR)
		return error


class ErklaerungTest(SimulationTestCase):
	"""Umsatzsteuererklärung, Körperschaftsteuererklärung and Gewerbesteuererklärung: the structure of the Nutzdaten
	that the Jahresdokumentationen E50, E30 and E20 require, sheets „Allg. Information“ and „Vorsatz - Regeln“."""

	KINDS = (ust(2026), kst(2026), gewst(2026))

	def setUp(self):
		super().setUp()
		# The invented Nutzdaten of KSt and GewSt hold the name of the company alone, which the rules of their Vordrucke
		# refuse: these tests check the structure, and those rules have tests of their own (test_simulation_kst.py,
		# test_simulation_gewst.py).
		structure = {
			kind.name: erklaerung.checks(module.TITLE, module.MAIN_FORM)
			for kind, module in ((kst(2026), kst_checks), (gewst(2026), gewst_checks))
		}
		patcher = mock.patch.object(fake, "CHECKS", MappingProxyType({**fake.CHECKS, **structure}))
		patcher.start()
		self.addCleanup(patcher.stop)

	def test_valid_nutzdaten_of_each_erklaerung_are_valid_and_nothing_is_sent(self):
		for kind in self.KINDS:
			with self.subTest(datenart=kind.version):
				result = Simulation().run(Operation.VALIDATE, nutzdaten(kind), header_of(kind))
				self.assertIs(result.outcome, Outcome.VALID)
				self.assertEqual(codes(result), ["SIM-000", "SIM-001"])
				self.assertTrue(all(message.severity == HINT for message in result.messages))
				self.assertIn(f"{kind.root}-{kind.year}.xsd", result.messages[1].text)
				self.assertIsNone(result.protocol_pdf)

	def test_the_root_is_the_one_of_the_datenart_in_the_version_of_its_year(self):
		data = nutzdaten(ust(2026))
		for case, changed in {
			"another element": data.replace("<E50 ", "<E51 ").replace("</E50>", "</E51>"),
			"another year": data.replace("/v2026", "/v2025"),
			"another version": data.replace('version="2026"', 'version="2025"'),
			"the UStVA": data.replace("elstererklaerung/ust/e50", "elsteranmeldung/ustva"),
		}.items():
			with self.subTest(case):
				error = self.refused(changed)
				self.assertEqual((error.code, error.field), ("SIM-003", "E50"))
				self.assertIn("2026", error.text)

	def test_the_main_form_and_the_vorsatz_are_pflichtvordrucke(self):
		for kind in self.KINDS:
			with self.subTest(datenart=kind.version):
				form = MAIN_FORMS[kind.name]
				without_form = re.sub(rf"\t<{form}>.*</{form}>\n", "", nutzdaten(kind))
				error = self.refused(without_form, kind)
				self.assertEqual((error.code, error.field), ("SIM-004", form))
				self.assertIn("Pflichtvordruck", error.text)
		without_vorsatz = re.sub(r"\t<Vorsatz>.*</Vorsatz>\n", "", nutzdaten(ust(2026)), flags=re.DOTALL)
		self.assertEqual(
			(self.refused(without_vorsatz).code, self.refused(without_vorsatz).field), ("SIM-004", "Vorsatz")
		)

	def test_the_vorsatz_holds_the_fields_its_rules_require(self):
		for element, code in (
			("Unterfallart", "10425"),
			("Vorgang", "10427"),
			("Zeitraum", "109000004"),
			("AbsName", "10100"),
			("AbsStr", "10110"),
			("AbsOrt", "10130"),
			("Copyright", "10435"),
			("OrdNrArt", "10423"),
			("Bescheid", "10438"),
		):
			for change in ("missing", "empty"):
				with self.subTest(element=element, change=change):
					empty = "" if change == "missing" else f"<{element}> </{element}>"
					data = re.sub(rf"<{element}>[^<]*</{element}>", empty, nutzdaten(ust(2026)), count=1)
					error = self.refused(data)
					self.assertEqual((error.code, error.field), ("SIM-004", element))
					self.assertIn(code, error.text)

	def test_ordnrart_s_needs_the_steuernummer(self):
		error = self.refused(nutzdaten(ust(2026)).replace("\t\t<StNr>9198011310010</StNr>\n", ""))
		self.assertEqual((error.code, error.field), ("SIM-004", "StNr"))
		self.assertIn("10433", error.text)

	def test_the_unterfallart_is_the_one_of_the_datenart(self):
		error = self.refused(
			nutzdaten(kst(2026)).replace("<Unterfallart>30<", "<Unterfallart>32<"), kst(2026)
		)
		self.assertEqual((error.code, error.field), ("SIM-010", "Unterfallart"))
		self.assertIn("30", error.text)

	def test_109000005_the_zeitraum_is_the_year_of_the_datenart(self):
		error = self.refused(nutzdaten(ust(2026)).replace("<Zeitraum>2026<", "<Zeitraum>2025<"))
		self.assertEqual((error.code, error.field), ("SIM-007", "Zeitraum"))
		self.assertIn("109000005", error.text)

	def test_10010_the_recipient_is_the_finanzamt_of_the_steuernummer(self):
		"""Formale_Plausipruefungen.ods: with OrdNrArt S the Empfaenger is the first four digits of the StNr."""
		error = self.refused(nutzdaten(ust(2026)), header=replace(HEADER, empfaenger="2241"))
		self.assertEqual((error.code, error.field), ("SIM-010", "Empfaenger"))
		self.assertIn("10010", error.text)
		self.assertIn("9198", error.text)

	def test_checks_the_header_first(self):
		error = self.refused(nutzdaten(ust(2026)), header=replace(HEADER, empfaenger="91"))
		self.assertEqual((error.code, error.field), ("SB-HEADER", "Empfaenger"))

	def test_a_test_send_names_the_erklaerung_and_the_freizeichnungsdokument_in_its_placeholder(self):
		kind = ust(2026)
		data = nutzdaten(kind)
		result = Simulation().run(Operation.TEST_SEND, data, header_of(kind, Operation.TEST_SEND))
		self.assertIs(result.outcome, Outcome.ACCEPTED)
		self.assertEqual(result.transferticket, "SIM-" + hashlib.sha256(data.encode()).hexdigest()[:28])
		pdf = result.protocol_pdf.decode("cp1252")
		self.assertIn("Erklärung: Umsatzsteuererklärung 2026", pdf)
		self.assertIn("Datenart: USt_2026", pdf)
		self.assertIn("Freizeichnungsdokument", pdf)
		self.assertNotIn("Übertragungsprotokoll", pdf)

	def test_each_erklaerung_has_its_title(self):
		for kind, title in (
			(kst(2026), "Körperschaftsteuererklärung 2026"),
			(gewst(2026), "Gewerbesteuererklärung 2026"),
		):
			with self.subTest(datenart=kind.version):
				result = Simulation().run(Operation.SEND, nutzdaten(kind), header_of(kind, Operation.SEND))
				self.assertIn(f"Erklärung: {title}", result.protocol_pdf.decode("cp1252"))

	def test_runs_the_rules_a_module_adds_to_its_erklaerung(self):
		def no_allg(root, kind, header):
			if root.find(f"{{{kind.namespace}}}USt2A/{{{kind.namespace}}}Allg") is not None:
				return Message("SIM-099", f"Für {header.datenart_version} geprüft.", ERROR, "Allg")
			return None

		checks = erklaerung.checks("Umsatzsteuererklärung", "USt2A", (no_allg,))
		self.assertEqual(len(checks.rules), 2)
		with mock.patch.object(fake, "CHECKS", MappingProxyType({**fake.CHECKS, "USt": checks})):
			error = self.refused(nutzdaten(ust(2026)))
		self.assertEqual((error.code, error.text), ("SIM-099", "Für USt_2026 geprüft."))


class ErklaerungSchemaTest(SimulationTestCase):
	"""With the ERiC documentation the simulation checks the Nutzdaten against the schema of the Datenart."""

	def schema(self, root: Path, kind: Datenart) -> Path:
		"""A schema of our own with the shape of E50-2026.xsd, whose Vorsatz takes no unknown element."""
		path = root / kind.schema
		path.parent.mkdir(parents=True)
		any_content = (
			'<xs:complexType><xs:sequence><xs:any processContents="skip" minOccurs="0" maxOccurs="unbounded"/>'
			"</xs:sequence></xs:complexType>"
		)
		names = (
			"Unterfallart",
			"Vorgang",
			"StNr",
			"Zeitraum",
			"AbsName",
			"AbsStr",
			"AbsPlz",
			"AbsOrt",
			"Copyright",
			"OrdNrArt",
		)
		fields = "".join(f'<xs:element name="{name}" type="xs:string"/>' for name in names)
		path.write_text(
			'<?xml version="1.0" encoding="UTF-8"?>'
			f'<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema" xmlns="{kind.namespace}" '
			f'targetNamespace="{kind.namespace}" elementFormDefault="qualified">'
			f'<xs:element name="{kind.root}"><xs:complexType><xs:sequence>'
			f'<xs:element name="USt2A">{any_content}</xs:element>'
			f'<xs:element name="Vorsatz"><xs:complexType><xs:sequence>{fields}'
			f'<xs:element name="Rueckuebermittlung">{any_content}</xs:element>'
			"</xs:sequence></xs:complexType></xs:element>"
			'</xs:sequence><xs:attribute name="version" type="xs:string" use="required"/></xs:complexType>'
			"</xs:element></xs:schema>",
			encoding="utf-8",
		)
		return root

	def test_validates_against_the_schema_of_the_documentation(self):
		kind = ust(2026)
		simulation = Simulation(self.schema(self.directory / "Dokumentation", kind))
		self.assertEqual(
			codes(simulation.run(Operation.VALIDATE, nutzdaten(kind), header_of(kind))), ["SIM-000"]
		)
		invalid = nutzdaten(kind).replace("<OrdNrArt>S</OrdNrArt>", "<OrdNrArt>S</OrdNrArt><Unbekannt/>")
		result = simulation.run(Operation.VALIDATE, invalid, header_of(kind))
		self.assertEqual(errors(result), [("SIM-005", None)])
		self.assertIn("E50-2026.xsd", result.messages[-1].text)


class ErklaerungDocumentationTest(TestCase):
	"""The simulation of the Erklärungen against the schemas and examples of the ERiC documentation 44.3.6.0."""

	def test_validates_against_e50_2026_xsd_of_the_eric_documentation(self):
		kind = ust(2026)
		simulation = Simulation(eric_schema.documentation())
		self.assertEqual(
			codes(simulation.run(Operation.VALIDATE, nutzdaten(kind), header_of(kind))), ["SIM-000"]
		)
		invalid = nutzdaten(kind).replace("<Bescheid>2</Bescheid>", "<Bescheid>3</Bescheid>")
		self.assertEqual(
			errors(simulation.run(Operation.VALIDATE, invalid, header_of(kind))), [("SIM-005", None)]
		)

	def test_the_examples_of_the_documentation_are_valid(self):
		for kind, example in (
			(ust(2026), "USt_2026.xml"),
			(kst(2025), "kst_2025_ok.xml"),
			(gewst(2025), "GewSt_2025.xml"),
		):
			with self.subTest(datenart=kind.version):
				document = etree.parse(
					str(eric_schema.erklaerung_directory(kind.name) / "Beispiele" / example)
				)
				((data,),) = document.getroot().iter("{http://www.elster.de/elsterxml/schema/v11}Nutzdaten")
				stnr = data.findtext(f"{{{kind.namespace}}}Vorsatz/{{{kind.namespace}}}StNr")
				header = replace(header_of(kind), empfaenger=stnr[:4])
				result = Simulation(eric_schema.documentation()).run(
					Operation.VALIDATE, etree.tostring(data, encoding="unicode"), header
				)
				self.assertEqual(codes(result), ["SIM-000"])


class VorsatzRulesTest(TestCase):
	"""The rules of the Vorsatz the simulation checks, against the sheets „Vorsatz - Regeln“ of the Jahresdokumentationen
	of USt 2026, KSt 2025 and GewSt 2025."""

	def test_cite_the_fehlercode_and_the_text_of_their_rule(self):
		for kind in (ust(2026), kst(2025), gewst(2025)):
			path = (
				eric_schema.erklaerung_directory(kind.name)
				/ "Jahresdokumentation"
				/ f"Jahresdokumentation_{kind.root}_{kind.year}.ods"
			)
			texts = {
				row["Fehlercode"]: re.sub(r"\$(\w+)\$", r"\1", row["Fehler- /Hinweistext"])
				for row in eric_schema.sheet(path, "Vorsatz - Regeln")
			}
			for field in (*erklaerung.VORSATZ, erklaerung.STEUERNUMMER_RULE):
				with self.subTest(datenart=kind.version, code=field.code):
					self.assertEqual(texts[field.code], f"{field.text}.")


class BilanzTest(SimulationTestCase):
	"""The E-Bilanz: the wrapper of ebilanz_000002.xsd around the XBRL instance, which the simulation does not check
	against a schema, as ERiC does not (ERiC-Entwicklerhandbuch 44.3.6.0, Tabelle 9-20)."""

	def setUp(self):
		super().setUp()
		# The invented E-Bilanz has an instance without facts, which the rules of the Jahresdokumentation refuse: these
		# tests check the frame, and those rules have tests of their own (test_simulation_bilanz.py).
		patcher = mock.patch.object(
			fake, "CHECKS", MappingProxyType({**fake.CHECKS, bilanz("6.9").name: bilanz_checks.FRAME})
		)
		patcher.start()
		self.addCleanup(patcher.stop)

	def refused_bilanz(self, data: str) -> Message:
		return self.refused(data, bilanz("6.9"), BILANZ_HEADER)

	def test_a_valid_e_bilanz_is_valid_without_a_schema_check_even_with_the_documentation(self):
		for simulation in (Simulation(), Simulation(self.directory)):
			with self.subTest(simulation=simulation):
				result = simulation.run(Operation.VALIDATE, EBILANZ, BILANZ_HEADER)
				self.assertIs(result.outcome, Outcome.VALID)
				self.assertEqual(codes(result), ["SIM-000", "SIM-001"])
				self.assertIn("XBRL-Instanz", result.messages[1].text)
				self.assertIn("Tabelle 9-20", result.messages[1].text)

	def test_takes_the_version_as_the_integer_of_the_schema(self):
		"""ebilanz_000002.xsd: version is an integer from 1 to 2; the examples write 000002."""
		self.assertTrue(
			Simulation()
			.run(Operation.VALIDATE, EBILANZ.replace('version="2"', 'version="000002"'), BILANZ_HEADER)
			.ok
		)
		for version in ("3", "0", "zwei", ""):
			with self.subTest(version=version):
				error = self.refused_bilanz(EBILANZ.replace('version="2"', f'version="{version}"'))
				self.assertEqual((error.code, error.field), ("SIM-003", "EBilanz"))

	def test_the_root_is_ebilanz_in_its_namespace(self):
		for changed in (
			EBILANZ.replace("ebilanz:EBilanz", "ebilanz:Bilanz"),
			EBILANZ.replace("EBilanz/2016", "EBilanz/2015"),
			nutzdaten(ust(2026)),
		):
			with self.subTest(changed=changed[:60]):
				self.assertEqual(self.refused_bilanz(changed).code, "SIM-003")

	def test_the_stichtag_is_a_date_before_the_instance(self):
		error = self.refused_bilanz(EBILANZ.replace("<ebilanz:stichtag>20261231</ebilanz:stichtag>", ""))
		self.assertEqual((error.code, error.field), ("SIM-004", "stichtag"))
		for stichtag in ("20261331", "2026123", "31122026x"):
			with self.subTest(stichtag=stichtag):
				error = self.refused_bilanz(EBILANZ.replace("20261231", stichtag))
				self.assertEqual((error.code, error.field), ("SIM-010", "stichtag"))
		instance_first = EBILANZ.replace("<ebilanz:stichtag>20261231</ebilanz:stichtag>", "").replace(
			"</xbrli:xbrl>", "</xbrli:xbrl><ebilanz:stichtag>20261231</ebilanz:stichtag>"
		)
		self.assertEqual(self.refused_bilanz(instance_first).code, "SIM-003")

	def test_the_instance_follows_the_stichtag(self):
		error = self.refused_bilanz(re.sub(r"<xbrli:xbrl.*</xbrli:xbrl>", "", EBILANZ))
		self.assertEqual((error.code, error.field), ("SIM-004", "xbrl"))
		self.assertEqual(
			self.refused_bilanz(EBILANZ.replace("</ebilanz:EBilanz>", "<x/></ebilanz:EBilanz>")).code,
			"SIM-003",
		)

	def test_the_header_names_the_datenlieferant_of_the_nutzdaten_header(self):
		error = self.refused(EBILANZ, bilanz("6.9"), replace(BILANZ_HEADER, nutzdaten_datenlieferant=None))
		self.assertEqual((error.code, error.field), ("SB-HEADER", "NutzdatenHeader/DatenLieferant"))

	def test_a_send_names_stichtag_taxonomy_and_the_uebertragungsprotokoll_in_its_placeholder(self):
		result = Simulation().run(Operation.SEND, EBILANZ, BILANZ_HEADER)
		self.assertIs(result.outcome, Outcome.ACCEPTED)
		pdf = result.protocol_pdf.decode("cp1252")
		for line in (
			"Stichtag: 31.12.2026",
			"Taxonomie: 6.9",
			"Datenart: Bilanz_6.9",
			"Übertragungsprotokoll",
		):
			with self.subTest(line=line):
				self.assertIn(line, pdf)

	def test_the_checks_of_the_bilanz_check_no_schema(self):
		self.assertIsInstance(bilanz_checks.CHECKS, Checks)
		self.assertFalse(bilanz_checks.CHECKS.schema)


class BilanzDocumentationTest(TestCase):
	def test_the_example_of_the_documentation_is_valid(self):
		"""Sent to the Finanzamt its NutzdatenHeader names, as rule 170205001 wants it for its Steuernummer."""
		document = etree.fromstring(eric_schema.bilanz_example("6.9"))
		((data,),) = document.iter("{http://www.elster.de/elsterxml/schema/v11}Nutzdaten")
		(empfaenger,) = document.iter("{http://www.elster.de/elsterxml/schema/v11}Empfaenger")
		result = Simulation(eric_schema.documentation()).run(
			Operation.VALIDATE,
			etree.tostring(data, encoding="unicode"),
			replace(BILANZ_HEADER, empfaenger=empfaenger.text),
		)
		self.assertIs(result.outcome, Outcome.VALID)


class RegistryTest(TestCase):
	def test_each_datenart_of_steuerbote_has_its_checks(self):
		self.assertEqual(sorted(fake.CHECKS), ["Bilanz", "GewSt", "KSt", "USt", "UStVA", "ZMDO"])
		for checks in fake.CHECKS.values():
			with self.subTest(checks=checks):
				self.assertIsInstance(checks, Checks)
		self.assertIs(fake.Checks, Checks)


class UstvaPlaceholderTest(SimulationTestCase):
	def test_the_placeholder_of_the_ustva_and_the_zm_names_the_uebertragungsprotokoll(self):
		"""Neither is an Erklärungssteuer, so ERiC prints an Übertragungsprotokoll for them (Kap. 5.1.4.4)."""
		ustva = (
			'<Anmeldungssteuern xmlns="http://finkonsens.de/elster/elsteranmeldung/ustva/v2026" version="2026">'
			"<Steuerfall><Umsatzsteuervoranmeldung><Jahr>2026</Jahr><Zeitraum>10</Zeitraum><Kz83>0.00</Kz83>"
			"</Umsatzsteuervoranmeldung></Steuerfall></Anmeldungssteuern>"
		)
		result = Simulation().run(Operation.SEND, ustva, replace(HEADER, datenart_version="UStVA_2026"))
		self.assertIn("das Übertragungsprotokoll", result.protocol_pdf.decode("cp1252"))

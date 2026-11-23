"""A documentation that agrees with the data of 2026, for the tests of the year check: what the Jahresdokumentationen,
the schema E50-2026.xsd and the Datenartversionmatrix say of the data of Steuerbote, written by files.py."""

from dataclasses import dataclass, field
from pathlib import Path

from steuerbote.elster import ust2a_xml, vorsatz
from steuerbote.elster.erklaerung import Field, Form
from steuerbote.eric.datenart import Datenart, bilanz, gewst, kst, ust
from steuerbote.jahresmeldung import yearcheck
from steuerbote.jahresmeldung.documentation import jahresdokumentation_path, schema_path
from steuerbote.jahresmeldung.tests.files import Documented, Rows, write, write_matrix, write_schema
from steuerbote.ustjahr import form as ustjahr_form
from steuerbote.ustjahr import rules as ustjahr_rules
from steuerbote.ustva import yearcheck as ustva_yearcheck
from steuerbote.ustva.tests import eric_documentation

MAIN_FORM = "USt2A"

MATRIX_ROWS = (
	("ElsterAnmeldung", "UStVA", "<Jahr>: ab 2016", "UStVA_<Jahr>", "checkUStVA_<Jahr>"),
	("ElsterErklaerung", "GewSt", "<Jahr>: ab 2015", "GewSt_<Jahr>", "checkGewSt_<Jahr>"),
	("ElsterErklaerung", "KSt", "<Jahr>: ab 2015", "KSt_30_<Jahr>", "checkKSt_<Jahr>"),
	("ElsterErklaerung", "KSt", "<Jahr>: 2015, 2016", "KSt_32_<Jahr>", "checkKSt_<Jahr>"),
	("ElsterErklaerung", "USt", "<Jahr>: ab 2015", "USt_<Jahr>", "checkUSt_<Jahr>"),
	("ElsterExtern", "ZMDO", "", "ZMDO", "checkZMDO"),
	("ElsterBilanz", "Bilanz", "HGB-Taxonomie 6.8", "Bilanz_6.8", "checkBilanz_6_8"),
	("ElsterBilanz", "Bilanz", "HGB-Taxonomie 6.9", "Bilanz_6.9", "checkBilanz_6_9"),
)
"""The rows of Datenartversionmatrix.ods of the ERiC documentation 44.3.6.0 that the year check reads, and one more."""


def listed(form: Form) -> str:
	"""A Vordruck as „Allg. Information“ lists it."""
	return (
		f"{form.name} - max. lfd. Nr. Vordruck: {form.count}{' - Pflichtvordruck' if form.mandatory else ''}"
	)


def vorsatz_fields() -> Rows:
	"""„Vorsatz - Felder“ with the texts of steuerbote/elster/vorsatz.py and an internal field."""
	return [
		*(
			{"Name": name, "Max. Länge": str(length), "Pflichtfeld": "Ja" if required else "Nein"}
			for name, (length, required) in vorsatz.TEXTS.items()
		),
		{"Name": "Bundesfinanzamtsnummer", "Internes ERiC Feld": "Ja"},
	]


def ust_jahresdokumentation(year: int = 2026) -> Documented:
	"""What Jahresdokumentation_E50_<year>.ods says that agrees with the data of the year: the fields of the catalogue
	of the XML, its Vordrucke, the rules of form USt 2 A with the conditions Steuerbote checks, and the Vorsatz."""
	catalogue = ust2a_xml.SCHEMAS[year]
	conditions = {rule.code: rule.condition for rule in ustjahr_rules.LOCAL_RULES[year]}
	documented = Documented(
		information=[
			f"Dokumentation erzeugt für VZ {year} ERiC 44.3 (Versionslabel 9.0)",
			*(listed(form) for form in catalogue.forms),
			f"Für Nutzdaten muss der Namensraum '{catalogue.datenart.namespace}' angegeben werden.",
		]
	)
	documented.rows(MAIN_FORM, "Felder").extend(
		{
			"Kontext": field_.context,
			"Name": field_.feldkennung,
			"Beschreibung": field_.label,
			"max. Zeilen": str(field_.rows),
			"Format als regulärer Ausdruck": field_.pattern or "",
			"Formatkennzeichen": field_.format,
			"Max. Länge": "" if field_.length is None else str(field_.length),
			"Pflichtfeld": "Ja" if field_.required else "Nein",
			"Vordruckzeile": yearcheck.ust_line(field_),
		}
		for field_ in catalogue.fields
	)
	documented.rows(MAIN_FORM, "Felder").append({"Name": "Informationsteil", "Internes ERiC Feld": "Ja"})
	documented.rows(MAIN_FORM, "Kennzahlen").extend(
		{"Feldname": f"{field_.context}/{field_.feldkennung}", "Kennzahl": field_.kennzahl}
		for field_ in catalogue.fields
		if field_.kennzahl
	)
	documented.rows(MAIN_FORM, "Regeln").extend(
		{
			"Kontext": rule.context,
			"Name": rule.name,
			"Fehlercode": rule.code,
			"Prüfbedingung": conditions.get(rule.code, ""),
			"Regelart": rule.severity.value,
		}
		for rule in ustjahr_form.CATALOGUES[year].rules
	)
	documented.rows("Vorsatz", "Felder").extend(vorsatz_fields())
	return documented


def ust_schema(year: int = 2026) -> dict[str, object]:
	"""The arguments of write_schema() for E50-<year>.xsd that agree with the catalogue of the XML."""
	catalogue = ust2a_xml.SCHEMAS[year]
	return {
		"root": "E50",
		"namespace": catalogue.datenart.namespace,
		"version": str(year),
		"vordrucke": {
			MAIN_FORM: [
				(
					field_.context,
					field_.feldkennung,
					f"{field_.feldkennung}_CType" if field_.options else "String_SType",
				)
				for field_ in catalogue.fields
			],
			"UN": [],
			"FV": [],
			"Vorsatz": [("", "Unterfallart", "String_SType")],
		},
		"complex_enumerations": {
			f"{field_.feldkennung}_CType": field_.options for field_ in catalogue.fields if field_.options
		},
	}


def income_tax_jahresdokumentation(check: yearcheck.IncomeTax, year: int, label: str) -> Documented:
	"""What a Jahresdokumentation E30 or E20 of ``year`` says that agrees with the data of 2026: the Vordrucke, fields
	and rules of the catalogue with the Indexfeld WJ where the writer takes one, each rule the core computes with all
	its terms, the Rechtsformen and the Vorsatz."""
	catalogue, schema = check.catalogues[2026], check.xml_schemas[2026]
	name, version = check.rechtsform_type
	documented = Documented(
		information=[
			f"Dokumentation erzeugt für VZ {year} ERiC 44.3 (Versionslabel {label})",
			*(listed(form) for form in catalogue.forms),
			f"Für Nutzdaten muss der Namensraum '{check.datenart(year).namespace}' angegeben werden.",
		]
	)
	for field_ in catalogue.fields:
		rows = documented.rows(field_.form, "Felder")
		if not rows and field_.form in schema.indexed:
			rows.append({"Name": "WJ", "Indexfeld": "Ja", "max. Zeilen": "1"})
		rows.append(field_row(field_))
		if field_.kennzahl:
			sachbereich, _, kennzahl = field_.kennzahl.rpartition(".")
			documented.rows(field_.form, "Kennzahlen").append(
				{"Feldname": place(field_), "Sachbereich": sachbereich, "Kennzahl": kennzahl}
			)
	named = {rule.code: rule for rule in catalogue.rules}
	expected = [expectation for module in check.expecting for expectation in module.expected_rules(2026)]
	for expectation in expected:
		rule = named.pop(expectation.code, None)
		documented.rows(expectation.form, "Regeln").append(
			{
				"Name": f"Regel_{expectation.code}" if rule is None else rule.name,
				"Fehlercode": expectation.code,
				"Prüfbedingung": " und ".join(expectation.terms),
				"Regelart": "Hinweis" if rule is not None and rule.hint else "Fehler",
			}
		)
	for rule in named.values():
		documented.rows(catalogue.forms[0].name, "Regeln").append(
			{"Name": rule.name, "Fehlercode": rule.code, "Regelart": "Hinweis" if rule.hint else "Fehler"}
		)
	categories = (
		f" - {code} [Rechtsform {code}] {' '.join(f'{key}: {value}' for key, value in values.items())}"
		for code, values in check.rechtsformen[2026].items()
	)
	documented.others["Benutzerdefinierte Typen"] = [
		{"Name": name, "Version": version, "Format": "\n".join(("Enumeration", *categories))}
	]
	documented.rows("Vorsatz", "Felder").extend(vorsatz_fields())
	return documented


def income_tax_schema(check: yearcheck.IncomeTax, year: int) -> dict[str, object]:
	"""The arguments of write_schema() for E30-<year>.xsd or E20-<year>.xsd that agree with the catalogue of 2026 and
	what its writer takes from the schema: the leaves of each Vordruck after its Indexfeld, the values of its lists,
	the Vordrucke and contexts that repeat."""
	catalogue, schema = check.catalogues[2026], check.xml_schemas[2026]
	vordrucke: dict[str, list[tuple[str, str, str]]] = {}
	for field_ in catalogue.fields:
		leaves = vordrucke.setdefault(
			field_.form, [("", "WJ", "Index_SType")] if field_.form in schema.indexed else []
		)
		leaves.append((field_.context, field_.feldkennung, list_type(field_)))
	vordrucke["Vorsatz"] = [("", "Unterfallart", "String_SType")]
	return {
		"root": check.datenart(year).root,
		"namespace": check.datenart(year).namespace,
		"version": str(year),
		"vordrucke": vordrucke,
		"complex_enumerations": {
			list_type(field_): field_.options for field_ in catalogue.fields if field_.options
		},
		"occurs": {
			**{path: str(most) for path, most in schema.repeats.items()},
			**{form.name: str(form.count) for form in catalogue.forms if form.count != 1},
		},
	}


def field_row(field_: Field) -> dict[str, str]:
	"""The row of a field of a form catalogue in its sheet „<Vordruck> - Felder“."""
	return {
		"Kontext": field_.context,
		"Name": field_.feldkennung,
		"Beschreibung": field_.label,
		"max. Zeilen": str(field_.rows),
		"Format als regulärer Ausdruck": field_.pattern or "",
		"Formatkennzeichen": field_.format,
		"Max. Länge": "" if field_.length is None else str(field_.length),
		"Pflichtfeld": "Ja" if field_.required else "Nein",
		"Vordruckzeile": "" if field_.line is None else str(field_.line),
	}


def place(field_: Field) -> str:
	return f"{field_.context}/{field_.feldkennung}" if field_.context else field_.feldkennung


def list_type(field_: Field) -> str:
	return f"{field_.feldkennung}_CType" if field_.options else "String_SType"


def bilanz_jahresdokumentation() -> Documented:
	"""Jahresdokumentation_Bilanz_Taxonomie_6_9.ods with a rule of the Vordruck Kontext and one of the Header."""
	documented = Documented(information=["Dokumentation erzeugt für Version v6_9 Versionslabel 1.6"])
	documented.rows("Kontext", "Regeln").append(
		{"Name": "AktivaUngleichPassiva", "Fehlercode": "170205010", "Prüfbedingung": "[bs.ass]!=[bs.eqLiab]"}
	)
	documented.rows("Header", "Regeln").append(
		{"Name": "UnerlaubterEmpfaengerTyp", "Fehlercode": "170205015"}
	)
	return documented


@dataclass
class Documentation:
	"""A documentation that agrees with the data of 2026: the Jahresdokumentationen of USt 2026, KSt and GewSt 2025 and
	the HGB-Taxonomie 6.9, the schema E50-2026.xsd, the matrix, and the UStVA of steuerbote/ustva/tests."""

	jahresdokumentationen: dict[Datenart, Documented] = field(default_factory=dict)
	schemas: dict[Datenart, dict[str, object]] = field(default_factory=dict)
	matrix: list[tuple[str, ...]] = field(default_factory=lambda: list(MATRIX_ROWS))
	ustva: eric_documentation.Documented | None = None

	@classmethod
	def agreeing(cls) -> Documentation:
		return cls(
			{
				ust(2026): ust_jahresdokumentation(),
				kst(2025): income_tax_jahresdokumentation(yearcheck.KST_CHECK, 2025, "7.0"),
				gewst(2025): income_tax_jahresdokumentation(yearcheck.GEWST_CHECK, 2025, "11.0"),
				bilanz("6.9"): bilanz_jahresdokumentation(),
			},
			{
				ust(2026): ust_schema(),
				kst(2025): income_tax_schema(yearcheck.KST_CHECK, 2025),
				gewst(2025): income_tax_schema(yearcheck.GEWST_CHECK, 2025),
			},
			ustva=eric_documentation.documented(ustva_yearcheck.data_for(2026)),
		)

	def write(self, directory: Path) -> Path:
		"""The directory Dokumentation below ERiC-44.3.6.0, where the zip unpacks it."""
		root = directory / "ERiC-44.3.6.0" / "Dokumentation"
		if self.ustva is not None:
			eric_documentation.write(directory, self.ustva)
		for kind, documented in self.jahresdokumentationen.items():
			target = jahresdokumentation_path(root, kind)
			target.parent.mkdir(parents=True, exist_ok=True)
			write(target, documented)
		for kind, arguments in self.schemas.items():
			write_schema(schema_path(root, kind), **arguments)
		write_matrix(root, self.matrix)
		return root

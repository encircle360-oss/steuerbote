"""The rules of the Jahresdokumentation the core computes, as the year check compares them: synthetic, and against
the Jahresdokumentationen E30 and E20 of the ERiC documentation when STEUERBOTE_ERIC_DOC_DIR holds them."""

from dataclasses import replace
from decimal import Decimal
from pathlib import Path
from unittest import SkipTest, TestCase, mock

from steuerbote.elster.tests import eric_schema
from steuerbote.eric.datenart import Datenart, gewst, kst
from steuerbote.gewst import chain as gewst_chain
from steuerbote.gewst import years as gewst_years
from steuerbote.jahresmeldung import documentation
from steuerbote.kst import chain, einlagekonto, losses
from steuerbote.kst import years as kst_years

MODULES = (
	("KSt", kst_years, (chain, losses, einlagekonto)),
	("GewSt", gewst_years, (gewst_chain,)),
)
DATENARTEN = {"KSt": kst, "GewSt": gewst}
CODES = {
	"KSt": {
		"8906062",
		"8956047",
		"8900549",
		"8900207",
		"8900413",
		"8900431",
		"8900331",
		"8956020",
		"8956042",
		"8956040",
		"8956007",
		"8956044",
		"8905506",
		"8912019",
		"8900184",
		"8900170",
		"8900114",
		"8900347",
		"8900342",
		"8900124",
		"8901005",
		"8901006",
		"8900351",
		"8900204",
		"8901012",
		"8900101",
		"8920021",
		"8920076",
		"8924445",
		"8924401",
		"8920227",
		"8924512",
		"8920011",
	},
	"GewSt": {"40000", "40053", "40954", "40965", "40958", "40959"},
}


def expectations(datenart: str, year: int):
	(found,) = ((years, modules) for name, years, modules in MODULES if name == datenart)
	return tuple(expectation for module in found[1] for expectation in module.expected_rules(year))


class ExpectedRulesTest(TestCase):
	def test_name_the_rules_the_core_computes(self):
		for datenart, codes in CODES.items():
			with self.subTest(datenart=datenart):
				found = [expectation.code for expectation in expectations(datenart, 2026)]
				self.assertEqual(len(found), len(set(found)))
				self.assertEqual(set(found), codes)

	def test_the_factors_come_from_the_year(self):
		rules = {expectation.code: expectation for expectation in expectations("KSt", 2026)}
		self.assertIn("Abrunden([E8007504]*0.15)", rules["8900331"].terms)
		self.assertIn("Aufrunden({[E8008501]-[E8008502]-[E8008601]}*0.7))", rules["8900170"].terms)
		self.assertIn("[E8120401]*0.055UngleichMitToleranz5[E8120601]", rules["8912019"].terms)
		later = replace(kst_years.YEARS[2026], rate=Decimal("14"), loss_share=Decimal("60"))
		with (
			mock.patch("steuerbote.kst.chain.year_of", return_value=later),
			mock.patch("steuerbote.kst.losses.year_of", return_value=later),
		):
			rules = {expectation.code: expectation for expectation in expectations("KSt", 2026)}
		self.assertIn("Abrunden([E8007504]*0.14)", rules["8900331"].terms)
		self.assertIn("Aufrunden({[E8008501]-[E8008502]-[E8008601]}*0.6))", rules["8900170"].terms)

	def test_the_sum_of_line_300_names_the_fields_of_the_steps_with_their_signs(self):
		(rule,) = (e for e in expectations("KSt", 2026) if e.code == "8906062")
		self.assertIn("+[E8002001]", rule.terms)
		self.assertIn("-[E8003301]", rule.terms)
		self.assertIn("+[E8562101]", rule.terms)

	def test_a_condition_that_agrees_lacks_nothing_and_one_that_changed_names_the_term(self):
		(rule,) = (e for e in expectations("KSt", 2026) if e.code == "8900331")
		self.assertEqual(rule.missing_terms("[E8007502] != Abrunden([E8007504] * 0.15)"), ())
		self.assertEqual(rule.missing_terms("[E8007502] != Abrunden([E8007504] * 0.14)"), rule.terms)


class DocumentationTest(TestCase):
	"""The rules of the Jahresdokumentation of every year of the year tables, the newest one for a provisional year."""

	def jahresdokumentation(self, kind: Datenart) -> Path:
		folder = documentation.directory(eric_schema.documentation(), kind)
		if not folder.is_dir():
			raise SkipTest(f"{folder} is not unzipped: the documentation holds no Datenart {kind.name}")
		return documentation.jahresdokumentation_path(eric_schema.documentation(), kind)

	def test_every_rule_the_core_computes_says_what_the_core_expects(self):
		for datenart, years, modules in MODULES:
			for year in years.YEARS.values():
				path = self.jahresdokumentation(DATENARTEN[datenart](year.documentation_year))
				rows = documentation.read(path).sheets
				for module in modules:
					for expectation in module.expected_rules(year.year):
						with self.subTest(datenart=datenart, year=year.year, rule=expectation.code):
							found = [
								row
								for row in rows[expectation.sheet]
								if row["Fehlercode"] == expectation.code
							]
							self.assertEqual(len(found), 1, f"rule {expectation.code} in {expectation.sheet}")
							self.assertEqual(expectation.missing_terms(found[0]["Prüfbedingung"]), ())

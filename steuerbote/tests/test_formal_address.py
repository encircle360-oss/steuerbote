"""Steuerbote addresses its users formally or not at all: „Ändern Sie den Betrag“ or „Betrag ändern“, never „Ändere
den Betrag“. The German texts are the translations in de.csv, the German texts of the pure modules, such as the
findings of the Voranmeldung and of the Zusammenfassende Meldung, which reach the form and the printouts as they are,
and the templates of the printouts. None of them may use the informal pronouns or an informal imperative of the verbs
the instructions of Steuerbote use."""

import csv
import re
import tokenize
from pathlib import Path
from unittest import TestCase

APP = Path(__file__).resolve().parents[1]
TRANSLATIONS = APP / "translations" / "de.csv"
ROOT = APP.parent
# The pages for those who develop and contribute keep the informal address of the community.
FOR_CONTRIBUTORS = frozenset({"entwicklung.md"})
CONTRIBUTOR_SECTIONS = ("## Mitwirken und Community",)

PRONOUNS = r"du|dich|dir|dein|deine|deinen|deinem|deiner|deines|euch|euer|eure|euren|eurem|eurer"
# The informal imperative of each verb an instruction of Steuerbote may use, such as „ändere“ for „ändern Sie“; „lies“
# of „lesen“ is left out, since it is an English word of the code as well.
IMPERATIVES = (
	r"ändere|bestätige|berichtige|begründe|buche|drücke|entferne|ergänze|erkläre|füge|gehe|gib|hinterlege|hole|"
	r"klicke|korrigiere|lade|lass|lege|lösche|melde|nenne|nimm|öffne|ordne|passe|prüfe|rufe|schalte|setze|sieh|"
	r"pflege|speichere|sprich|trage|vergleiche|wähle"
)
# A word in lower case or with a capital at the start of a sentence, never in capitals such as the unit GiB.
WORDS = "|".join(f"[{word[0].upper()}{word[0]}]{word[1:]}" for word in f"{PRONOUNS}|{IMPERATIVES}".split("|"))
INFORMAL = re.compile(rf"(?<![\wäöüß-])(?:{WORDS})(?![\wäöüß-])")


def _informal(text: str) -> list[str]:
	return [match.group(0) for match in INFORMAL.finditer(text)]


def _python_strings(path: Path) -> list[str]:
	"""The string literals of a module that may hold a text for the user: not its docstrings and data tables, which are
	triple-quoted and English or copied from a Vordruck."""
	with tokenize.open(path) as source:
		tokens = list(tokenize.generate_tokens(source.readline))
	strings, triple = [], False
	for token in tokens:
		if token.type == tokenize.FSTRING_START:
			triple = _triple(token.string)
		elif (token.type == tokenize.FSTRING_MIDDLE and not triple) or (
			token.type == tokenize.STRING and not _triple(token.string)
		):
			strings.append(token.string)
	return strings


def _triple(literal: str) -> bool:
	return literal.lstrip("rRbBfFuU").startswith(('"""', "'''"))


def _sources() -> list[Path]:
	return [
		path
		for path in sorted(APP.rglob("*.py"))
		if "tests" not in path.relative_to(APP).parts and not path.name.startswith("test_")
	]


class FormalAddressTest(TestCase):
	def test_the_translations_address_the_user_formally(self):
		with TRANSLATIONS.open(encoding="utf-8", newline="") as file:
			found = {source: words for source, german in csv.reader(file) if (words := _informal(german))}
		self.assertEqual(found, {})

	def test_the_german_texts_of_the_modules_address_the_user_formally(self):
		found = {
			f"{path.relative_to(APP)}: {text[:80]}": words
			for path in _sources()
			for text in _python_strings(path)
			if (words := _informal(text))
		}
		self.assertEqual(found, {})

	def test_the_templates_address_the_user_formally(self):
		found = {
			str(path.relative_to(APP)): words
			for path in sorted(APP.rglob("*.html"))
			if (words := _informal(path.read_text(encoding="utf-8")))
		}
		self.assertEqual(found, {})

	def test_the_documentation_for_users_addresses_them_formally(self):
		"""The pages under docs/ and the README speak to those who use Steuerbote with „Sie“ or neutrally; the page for
		developers and the section of the README on contributing keep the „du“ of the community."""
		found = {
			path.name: words
			for path in sorted((ROOT / "docs").glob("*.md"))
			if path.name not in FOR_CONTRIBUTORS and (words := _informal(path.read_text(encoding="utf-8")))
		}
		readme = (ROOT / "README.md").read_text(encoding="utf-8")
		for heading in CONTRIBUTOR_SECTIONS:
			start = readme.index(heading)
			readme = readme[:start] + readme[readme.index("\n## ", start + 1) :]
		if words := _informal(readme):
			found["README.md"] = words
		self.assertEqual(found, {})

	def test_the_check_finds_the_informal_forms(self):
		self.assertEqual(
			_informal(
				"Passe Betrag oder Begründung an, oder lösche die Korrektur; gib sie frei, wie du willst."
			),
			["Passe", "lösche", "gib", "du"],
		)
		self.assertEqual(
			_informal("Ändern Sie den Betrag, löschen Sie die Korrektur oder prüfen Sie die Liste."), []
		)

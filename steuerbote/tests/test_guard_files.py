"""The files of the guards of the app (steuerbote/steuerbote/guards.py), read without a bench: the records only
Steuerbote writes, what a filing is for, the stored document behind every method the desk calls, the permission to
send data off the site, and the German of every text."""

import ast
import csv
import json
import re
from pathlib import Path
from unittest import TestCase

from steuerbote import hooks

APP = Path(__file__).resolve().parents[1]
MODULE = APP / "steuerbote"
DOCTYPES = MODULE / "doctype"
GUARDS = MODULE / "guards.py"
TRANSLATIONS = APP / "translations" / "de.csv"
TRANSLATED_LITERAL = re.compile(r"\b_{1,2}\(\s*\"((?:[^\"\\]|\\.)*)\"")
GUARD = "steuerbote.steuerbote.guards"
# What records what Steuerbote did: a run through ERiC or the note of a filing, a query at the BZSt or VIES, a reminder
# that went out.
RECORDS = ("ELSTER Transmission", "VAT ID Confirmation", "Deadline Reminder")
# Each filing with the fields that say what it is for.
FILINGS = {
	"vat_return": ("company", "year", "rhythm", "period_index"),
	"vat_return_extension": ("company", "year"),
	"recapitulative_statement": ("company", "year", "period_kind", "period_index"),
	"vat_return_prior_filing": ("company", "year", "rhythm", "period_index"),
	"annual_vat_return": ("company", "year"),
	"electronic_balance_sheet": ("company", "year", "statement_type"),
	"corporate_income_tax_return": ("company", "year"),
	"trade_tax_return": ("company", "year"),
	"annual_accounts": ("company", "year"),
}
# The controllers that carry the methods of the annual filings and of every document that goes to ELSTER or whose
# USt-IdNrn. Steuerbote confirms.
SHARED = (
	MODULE / "annual_filing.py",
	DOCTYPES / "elster_transmission" / "transmission.py",
	DOCTYPES / "vat_id_confirmation" / "confirming.py",
)
# Where data leaves the site on a request: Testsenden and Senden, the certificate for them, and the confirmation of
# USt-IdNrn.
SENDERS = {
	DOCTYPES / "elster_transmission" / "transmission.py": ("transmit", "_stash"),
	DOCTYPES / "vat_return" / "vat_return.py": ("confirm_vat_ids",),
	DOCTYPES / "recapitulative_statement" / "recapitulative_statement.py": ("confirm_vat_ids",),
}


def read_json(path: Path) -> dict:
	return json.loads(path.read_text(encoding="utf-8"))


def controller(folder: str) -> Path:
	return DOCTYPES / folder / f"{folder}.py"


def tree(path: Path) -> ast.Module:
	return ast.parse(path.read_text(encoding="utf-8"))


def whitelisted_methods(path: Path) -> list[ast.FunctionDef]:
	"""The whitelisted methods of the classes of the file."""
	return [
		node
		for cls in tree(path).body
		if isinstance(cls, ast.ClassDef)
		for node in cls.body
		if isinstance(node, ast.FunctionDef)
		and any("whitelist" in ast.unparse(d) for d in node.decorator_list)
	]


def function(path: Path, name: str) -> ast.FunctionDef:
	(found,) = (
		node for node in ast.walk(tree(path)) if isinstance(node, ast.FunctionDef) and node.name == name
	)
	return found


def translated() -> set[str]:
	with TRANSLATIONS.open(encoding="utf-8", newline="") as file:
		return {source for source, *_ in csv.reader(file)}


class RecordsTest(TestCase):
	"""Only Steuerbote writes a record of what it did; no request inserts or renames one."""

	def test_every_record_refuses_an_insert_and_a_rename_that_steuerbote_does_not_make(self):
		for doctype in RECORDS:
			with self.subTest(doctype=doctype):
				events = hooks.doc_events[doctype]
				self.assertEqual(events["before_insert"], f"{GUARD}.refuse_unless_recorded")
				self.assertEqual(events["before_rename"], f"{GUARD}.refuse_rename")

	def test_no_role_creates_writes_or_imports_a_record(self):
		for doctype in RECORDS:
			definition = read_json(controller(doctype.lower().replace(" ", "_")).with_suffix(".json"))
			with self.subTest(doctype=doctype):
				self.assertFalse(definition.get("allow_import") or definition.get("allow_rename"))
				for permission in definition["permissions"]:
					self.assertFalse(
						permission.get("create") or permission.get("write") or permission.get("import"),
						permission["role"],
					)

	def test_the_app_writes_a_record_through_the_guards(self):
		writes = {
			DOCTYPES / "elster_transmission" / "transmission.py": ("new_transmission", "record"),
			DOCTYPES / "vat_id_confirmation" / "vat_id_confirmation.py": ("store",),
			MODULE / "deadlines.py": ("remind",),
		}
		for path, names in writes.items():
			for name in names:
				with self.subTest(path=path.name, function=name):
					source = ast.unparse(function(path, name))
					self.assertRegex(source, r"guards\.(insert|save)_record\(")

	def test_a_transmission_changes_only_while_steuerbote_records_it(self):
		source = ast.unparse(function(controller("elster_transmission"), "validate"))
		self.assertIn("guards.recorded(self)", source)
		self.assertNotIn("flags.recording", source)


class FilingsTest(TestCase):
	"""What a filing is for stays as it was created, and a filing keeps its name."""

	def test_the_fields_that_say_what_a_filing_is_for_are_set_once(self):
		for folder, identity in FILINGS.items():
			definition = read_json(controller(folder).with_suffix(".json"))
			once = tuple(field["fieldname"] for field in definition["fields"] if field.get("set_only_once"))
			with self.subTest(doctype=definition["name"]):
				self.assertEqual(once, identity)

	def test_every_filing_is_a_filing_of_the_guards(self):
		for folder in FILINGS:
			(cls,) = (node for node in tree(controller(folder)).body if isinstance(node, ast.ClassDef))
			bases = [ast.unparse(base) for base in cls.bases]
			with self.subTest(controller=cls.name):
				self.assertTrue({"Filing", "AnnualFiling"} & set(bases), bases)
				self.assertEqual(bases[-1], "Document")
		(base,) = (
			node
			for node in tree(MODULE / "annual_filing.py").body
			if isinstance(node, ast.ClassDef) and node.name == "AnnualFiling"
		)
		self.assertEqual([ast.unparse(node) for node in base.bases], ["Filing"])

	def test_no_filing_takes_the_before_validate_or_before_rename_of_the_guards(self):
		for path in (*(controller(folder) for folder in FILINGS), MODULE / "annual_filing.py"):
			names = {node.name for node in ast.walk(tree(path)) if isinstance(node, ast.FunctionDef)}
			with self.subTest(path=path.name):
				self.assertFalse({"before_validate", "before_rename"} & names)


class StoredDocumentTest(TestCase):
	"""Every method the desk calls on a document checks the permission on the document as stored."""

	def test_every_whitelisted_method_of_a_document_checks_the_stored_document(self):
		paths = sorted({*DOCTYPES.glob("*/*.py"), *SHARED} - set(DOCTYPES.glob("*/test_*.py")))
		methods = [(path, node) for path in paths for node in whitelisted_methods(path)]
		self.assertGreaterEqual(len(methods), 50)
		for path, node in methods:
			decorators = [ast.unparse(decorator) for decorator in node.decorator_list]
			with self.subTest(method=f"{path.parent.name}.{node.name}"):
				self.assertIn("whitelist", decorators[0])
				self.assertRegex(decorators[1], r"^guards\.on_stored\('(read|write|submit)'(, new=True)?\)$")


class SendingTest(TestCase):
	"""What sends data off the site needs the permission to submit the document, checked in one place."""

	def test_every_sender_asks_the_guards(self):
		for path, names in SENDERS.items():
			for name in names:
				with self.subTest(function=name, path=path.name):
					self.assertIn("guards.require_permission_to_send(", ast.unparse(function(path, name)))


class GuardsTranslationsTest(TestCase):
	def test_every_text_of_the_guards_is_translated(self):
		texts = set(TRANSLATED_LITERAL.findall(GUARDS.read_text(encoding="utf-8")))
		self.assertGreaterEqual(len(texts), 6)
		self.assertEqual(sorted(texts - translated()), [])

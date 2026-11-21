"""The forms that go to ELSTER through ERiC share one script for it, read from their files without a bench."""

import ast
import re
from pathlib import Path
from unittest import TestCase

APP = Path(__file__).resolve().parents[3]
DOCTYPES = APP / "steuerbote" / "doctype"
SHARED_SCRIPT = APP / "public" / "js" / "elster_transmission.js"
SERVER = DOCTYPES / "elster_transmission" / "transmission.py"
FORMS = {
	"VAT Return": DOCTYPES / "vat_return" / "vat_return.js",
	"VAT Return Extension": DOCTYPES / "vat_return_extension" / "vat_return_extension.js",
}
# The path Frappe resolves an include of a form script by: the app, then the path inside its package.
INCLUDE = '{% include "steuerbote/public/js/elster_transmission.js" %}\n'
# The arguments of the store that name the document the certificate is for, and carry no secret.
DOCUMENT_ARGUMENTS = ("document_type", "document")


def constant(source: str, name: str) -> str:
	(value,) = re.findall(rf'^(?:const )?{name} = "([^"]+)"', source, re.MULTILINE)
	return value


class SharedScriptTest(TestCase):
	def setUp(self):
		self.script = SHARED_SCRIPT.read_text(encoding="utf-8")
		self.server = SERVER.read_text(encoding="utf-8")

	def test_each_form_includes_the_shared_script_first(self):
		for doctype, path in FORMS.items():
			with self.subTest(doctype=doctype):
				self.assertTrue(path.read_text(encoding="utf-8").startswith(INCLUDE))

	def test_the_methods_the_script_calls_are_whitelisted_for_post(self):
		methods = set(re.findall(r'frm\.call\("(\w+)"', self.script))
		self.assertEqual(methods, {"transmit", "release_stale_transmission"})
		for method in sorted(methods):
			with self.subTest(method=method):
				self.assertRegex(self.server, rf'@frappe\.whitelist\(methods=\["POST"\]\)\n\tdef {method}\(')

	def test_the_certificate_goes_to_the_whitelisted_store_which_is_never_recorded(self):
		module, _, function = constant(self.script, "STASH_CERTIFICATE").rpartition(".")
		self.assertEqual(module, "steuerbote.steuerbote.doctype.elster_transmission.transmission")
		self.assertRegex(
			self.server, rf'@frappe\.whitelist\(methods=\["POST"\]\)\n@do_not_record\ndef {function}\('
		)

	def test_certificate_and_password_travel_under_names_frappe_masks(self):
		"""The dialog of a server error copies the arguments of its request and masks only those whose name holds
		password (mask_passwords of Frappe's utils.js); the logs and tracebacks of the server mask password and
		secret as well."""
		(stash,) = (
			node
			for node in ast.parse(self.server).body
			if isinstance(node, ast.FunctionDef) and node.name == "stash_certificate"
		)
		parameters = [argument.arg for argument in stash.args.args]
		(arguments,) = re.findall(r"method: STASH_CERTIFICATE,\s*args: \{([^}]*)\}", self.script)
		self.assertEqual(
			[name.split(":")[0].strip() for name in arguments.split(",") if name.strip()], parameters
		)
		for name in parameters:
			if name not in DOCUMENT_ARGUMENTS:
				with self.subTest(name=name):
					self.assertIn("password", name)

	def test_the_script_forgets_the_request_that_carried_the_certificate(self):
		self.assertIn("always: forget_the_last_request,", self.script)
		self.assertIn("frappe.last_request = null;", self.script)

	def test_the_script_listens_to_the_event_the_job_publishes(self):
		self.assertEqual(
			constant(self.script, "TRANSMISSION_EVENT"), constant(self.server, "TRANSMISSION_EVENT")
		)

	def test_each_form_names_the_errors_and_hints_of_its_latest_run(self):
		"""The controller hands latest_run() of the shared transmission to its form, which shows it."""
		self.assertIn("def latest_run(self) -> dict | None:", self.server)
		self.assertIn("const run = frm.doc.__onload && frm.doc.__onload.elster_run;", self.script)
		for doctype, path in FORMS.items():
			controller = path.with_suffix(".py").read_text(encoding="utf-8")
			with self.subTest(doctype=doctype):
				self.assertIn('self.set_onload("elster_run", self.latest_run())', controller)
				self.assertIn("show_latest_run(frm);", path.read_text(encoding="utf-8"))

	def test_a_form_reacts_only_to_the_runs_of_its_own_documents(self):
		self.assertIn("if (data.document_type === frm.doctype) {", self.script)
		self.assertIn("if (frm.doc && frm.doc.name === data.document) {", self.script)

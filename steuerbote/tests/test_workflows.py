"""The workflows install every tool in one exact version and fetch other code at one commit, read without a bench."""

import re
from pathlib import Path
from unittest import TestCase

WORKFLOWS = Path(__file__).resolve().parents[2] / ".github" / "workflows"
PIP_INSTALL = re.compile(r"pip install (?P<arguments>[^\n]+)")
PINNED_PACKAGE = re.compile(r"[A-Za-z0-9_.-]+==\d[\w.]*")
USES = re.compile(r"uses: [\w./-]+@(?P<ref>\S+)")
REF = re.compile(r"^\s+ref: (?P<ref>\S+)", re.MULTILINE)
COMMIT = re.compile(r"[0-9a-f]{40}")


class WorkflowPinsTest(TestCase):
	def workflows(self) -> list[tuple[str, str]]:
		found = [(path.name, path.read_text(encoding="utf-8")) for path in sorted(WORKFLOWS.glob("*.yml"))]
		self.assertEqual([name for name, _ in found], ["linters.yml", "security.yml", "tests.yml"])
		return found

	def test_every_tool_is_installed_in_an_exact_version(self):
		for name, workflow in self.workflows():
			for match in PIP_INSTALL.finditer(workflow):
				arguments = match["arguments"].split()
				packages = [
					argument
					for index, argument in enumerate(arguments)
					if not argument.startswith("-") and (index == 0 or arguments[index - 1] != "-r")
				]
				with self.subTest(workflow=name, install=match[0]):
					self.assertTrue(packages or "-r" in arguments)
					for package in packages:
						self.assertRegex(package, PINNED_PACKAGE)

	def test_actions_and_other_repositories_come_at_one_commit(self):
		"""Rules a scan applies, such as the semgrep rules of Frappe, are code that decides whether the scan passes."""
		for name, workflow in self.workflows():
			with self.subTest(workflow=name):
				self.assertNotIn("git clone", workflow)
				for match in (*USES.finditer(workflow), *REF.finditer(workflow)):
					self.assertRegex(match["ref"], COMMIT)

	def test_the_semgrep_rules_come_from_their_repositories(self):
		linters = dict(self.workflows())["linters.yml"]
		self.assertIn("repository: frappe/semgrep-rules", linters)
		self.assertIn("repository: semgrep/semgrep-rules", linters)
		self.assertNotIn("--config r/", linters)

"""The workflows install every tool in one exact version and fetch other code at one commit, read without a bench."""

import re
from pathlib import Path
from unittest import TestCase

from steuerbote.elster.tests import eric_schema
from steuerbote.xbrl.versions import TAXONOMIES

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


JOB = re.compile(r"^  (?P<name>[\w-]+):\n(?P<body>(?:(?:    .*)?\n)+)", re.MULTILINE)
WORKFLOW_ENV = re.compile(r"^env:\n(?P<body>(?:  .*\n)+)", re.MULTILINE)
UNZIP = re.compile(r"unzip -q [^\n]+")


def jobs(workflow: str) -> dict[str, str]:
	"""The jobs of a workflow by their key, each with the lines that belong to it."""
	section = workflow[workflow.index("\njobs:\n") :]
	return {match["name"]: match["body"] for match in JOB.finditer(section)}


def workflow_env(workflow: str) -> dict[str, str]:
	"""The variables of the env of the workflow itself, which every job sees."""
	match = WORKFLOW_ENV.search(workflow)
	if match is None:
		return {}
	pairs = (
		line.strip().partition(": ")
		for line in match["body"].splitlines()
		if not line.strip().startswith("#")
	)
	return {name: value for name, _, value in pairs}


class DownloadsTest(TestCase):
	"""The ERiC documentation and the HGB-Taxonomie, which the repository may not hold, come by their SHA-256."""

	def setUp(self):
		self.workflow = (WORKFLOWS / "tests.yml").read_text(encoding="utf-8")
		self.jobs = jobs(self.workflow)
		self.env = workflow_env(self.workflow)

	def test_downloads_the_documentation_and_the_taxonomy_the_tests_name(self):
		self.assertEqual(self.env["ERIC_DOCUMENTATION"], eric_schema.DOWNLOAD)
		self.assertEqual(
			(self.env["TAXONOMY"], self.env["TAXONOMY_SHA256"]),
			(TAXONOMIES["6.9"].archive_url, TAXONOMIES["6.9"].archive_sha256),
		)
		self.assertRegex(self.env["ERIC_DOCUMENTATION_SHA256"], r"^[0-9a-f]{64}$")
		self.assertRegex(self.env["INTERMEDIATE_SHA256"], r"^[0-9a-f]{64}$")

	def test_the_test_jobs_unzip_every_datenart_of_the_erklaerungen_and_the_bilanz(self):
		for name in ("core", "frappe"):
			with self.subTest(job=name):
				(unzip,) = UNZIP.findall(self.jobs[name])
				for part in ("'*/Datenarten/ElsterErklaerung/*'", "'*/Datenarten/ElsterBilanz/*'"):
					self.assertIn(part, unzip)
				self.assertNotIn("ElsterErklaerung/USt", unzip)

	def test_each_download_is_checked_by_its_sha256(self):
		for name, job in self.jobs.items():
			with self.subTest(job=name):
				if "$ERIC_DOCUMENTATION" in job:
					self.assertIn(
						'echo "$ERIC_DOCUMENTATION_SHA256  $RUNNER_TEMP/eric-doc.zip" | sha256sum --check --strict',
						job,
					)
				if "$TAXONOMY" in job:
					self.assertIn(
						'echo "$INTERMEDIATE_SHA256  $RUNNER_TEMP/intermediate.crt" | sha256sum --check --strict',
						job,
					)
					self.assertIn(
						'echo "$TAXONOMY_SHA256  $RUNNER_TEMP/taxonomy-6.9.zip" | sha256sum --check --strict',
						job,
					)

	def test_the_taxonomy_comes_from_a_cache_keyed_by_its_sha256_and_is_checked_after(self):
		cached_as = "hgb-taxonomie-6.9-${{ env.TAXONOMY_SHA256 }}"
		for name in ("core", "frappe", "xbrl"):
			job = self.jobs[name]
			with self.subTest(job=name):
				self.assertIn("uses: actions/cache/restore@", job)
				self.assertIn("uses: actions/cache/save@", job)
				self.assertEqual(job.count(cached_as), 2)
				self.assertEqual(job.count("if: steps.taxonomy.outputs.cache-hit != 'true'"), 2)
				restored = job.index("uses: actions/cache/restore@")
				checked = job.rindex(
					'echo "$TAXONOMY_SHA256  $RUNNER_TEMP/taxonomy-6.9.zip" | sha256sum --check --strict'
				)
				self.assertLess(restored, checked)
				self.assertLess(
					checked, job.index("STEUERBOTE_TAXONOMY_6_9" if name != "xbrl" else "arelle_validation")
				)


class XbrlJobTest(TestCase):
	def setUp(self):
		self.job = jobs((WORKFLOWS / "tests.yml").read_text(encoding="utf-8"))["xbrl"]

	def test_validates_the_instances_with_arelle_in_a_time_of_its_own(self):
		self.assertIn("timeout-minutes: 20", self.job)
		self.assertIn(
			'python -m steuerbote.xbrl.tests.arelle_validation "$RUNNER_TEMP/taxonomy-6.9.zip" --keep "$RUNNER_TEMP/xbrl"',
			self.job,
		)
		(unzip,) = UNZIP.findall(self.job)
		self.assertIn("'*/Datenarten/ElsterBilanz/*' '*/ElsterBasisSchema/*'", unzip)

	def test_keeps_the_instances_and_logs_of_a_failure_but_no_file_of_the_taxonomy(self):
		upload = self.job[self.job.index("uses: actions/upload-artifact@") :]
		self.assertIn("if: failure()", upload)
		paths = [
			line.strip()
			for line in upload.splitlines()
			if line.strip().startswith("${{ runner.temp }}/xbrl/")
		]
		self.assertEqual(
			paths,
			[
				"${{ runner.temp }}/xbrl/*.xml",
				"${{ runner.temp }}/xbrl/*.xbrl",
				"${{ runner.temp }}/xbrl/*.log",
			],
		)


class Taxonomy610Test(TestCase):
	"""The HGB-Taxonomie 6.10 comes as 6.9 does, into each job whose tests or validation read the package: from a cache
	keyed by its SHA-256 or from esteuer.de, checked before its use."""

	CACHED_AS = "hgb-taxonomie-6.10-${{ env.TAXONOMY_6_10_SHA256 }}"
	CHECKED = 'echo "$TAXONOMY_6_10_SHA256  $RUNNER_TEMP/taxonomy-6.10.zip" | sha256sum --check --strict'

	def setUp(self):
		workflow = (WORKFLOWS / "tests.yml").read_text(encoding="utf-8")
		self.jobs = jobs(workflow)
		self.env = workflow_env(workflow)

	def test_downloads_the_package_the_version_table_names(self):
		self.assertEqual(
			(self.env["TAXONOMY_6_10"], self.env["TAXONOMY_6_10_SHA256"]),
			(TAXONOMIES["6.10"].archive_url, TAXONOMIES["6.10"].archive_sha256),
		)

	def test_comes_from_a_cache_keyed_by_its_sha256_and_is_checked_before_its_use(self):
		for name, used in (
			("core", "STEUERBOTE_TAXONOMY_6_10: ${{ runner.temp }}/taxonomy-6.10.zip"),
			("frappe", "STEUERBOTE_TAXONOMY_6_10: ${{ runner.temp }}/taxonomy-6.10.zip"),
			("xbrl", '"$RUNNER_TEMP/taxonomy-6.10.zip" --version 6.10'),
		):
			job = self.jobs[name]
			with self.subTest(job=name):
				self.assertEqual(job.count(self.CACHED_AS), 2)
				self.assertEqual(job.count("if: steps.taxonomy-6-10.outputs.cache-hit != 'true'"), 2)
				download = job[job.index("- name: Download the HGB-Taxonomie 6.10") :]
				self.assertIn(
					'echo "$INTERMEDIATE_SHA256  $RUNNER_TEMP/intermediate.crt" | sha256sum --check --strict',
					download,
				)
				self.assertLess(job.index("id: taxonomy-6-10"), job.rindex(self.CHECKED))
				self.assertLess(job.rindex(self.CHECKED), job.index(used))

	def test_the_xbrl_job_validates_the_instances_of_6_10_and_keeps_those_of_a_failure(self):
		job = self.jobs["xbrl"]
		self.assertIn(
			'python -m steuerbote.xbrl.tests.arelle_validation "$RUNNER_TEMP/taxonomy-6.10.zip" --version 6.10 '
			'--keep "$RUNNER_TEMP/xbrl-6.10"',
			job,
		)
		upload = job[job.index("uses: actions/upload-artifact@") :]
		self.assertEqual(
			[line.strip() for line in upload.splitlines() if "/xbrl-6.10/" in line],
			[
				"${{ runner.temp }}/xbrl-6.10/*.xml",
				"${{ runner.temp }}/xbrl-6.10/*.xbrl",
				"${{ runner.temp }}/xbrl-6.10/*.log",
			],
		)


class BrowserTestsJobTest(TestCase):
	def setUp(self):
		self.job = jobs((WORKFLOWS / "tests.yml").read_text(encoding="utf-8"))["frappe"]

	def test_keeps_the_screenshots_of_the_desk_after_every_run(self):
		"""The browser tests leave the screenshots of the sidebar and the workspace in their directory of --output
		after every run, and a failed test those of its pages."""
		self.assertIn('--output "$RUNNER_TEMP/browser-results"', self.job)
		upload = self.job[self.job.index("uses: actions/upload-artifact@") :]
		self.assertIn("name: browser-tests", upload)
		self.assertIn("path: ${{ runner.temp }}/browser-results", upload)
		self.assertIn("if: always()", upload)


class PrintoutsOfTheImageJobTest(TestCase):
	"""The image of a site ships releases of Frappe and ERPNext, while the Frappe site job builds the head of
	version-16; the PDF generators of Frappe read the page options of the print CSS differently from one release to
	the next, so the printouts are proven against the releases of the image as well."""

	def setUp(self):
		self.job = jobs((WORKFLOWS / "tests.yml").read_text(encoding="utf-8"))["printouts-image"]

	def test_builds_the_bench_from_the_releases_of_the_image(self):
		self.assertIn("FRAPPE_VERSION: v16.60.2", self.job)
		self.assertIn("ERPNEXT_VERSION: v16.60.0", self.job)
		self.assertIn('--frappe-branch "$FRAPPE_VERSION"', self.job)
		self.assertIn('bench get-app erpnext --branch "$ERPNEXT_VERSION"', self.job)

	def test_prints_every_print_format_with_both_generators_and_keeps_the_printouts(self):
		self.assertIn("steuerbote.tests.e2e.seed.run", self.job)
		self.assertIn('chromium_path "$(command -v google-chrome)"', self.job)
		self.assertIn("steuerbote.tests.print_proof.run", self.job)
		upload = self.job[self.job.index("uses: actions/upload-artifact@") :]
		self.assertIn("name: printouts-image", upload)
		self.assertIn("if: always()", upload)

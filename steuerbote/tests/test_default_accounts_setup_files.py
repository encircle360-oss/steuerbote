"""The step „Standardkonten des Unternehmens“ in the hooks and its texts in German, without a site."""

from pathlib import Path
from unittest import TestCase

from steuerbote import hooks
from steuerbote.tests.test_setup_files import messages, translations

APP = Path(__file__).resolve().parents[1]
MODULE = APP / "steuerbote" / "default_accounts_setup.py"


class DefaultAccountsSetupFilesTest(TestCase):
	def test_the_step_follows_that_of_the_exchange_accounts(self):
		steps = {step["key"]: step for step in hooks.steuerbote_setup_steps}
		step = steps["company_default_accounts"]
		self.assertEqual(step["run"], "steuerbote.steuerbote.default_accounts_setup.check")
		self.assertLess(steps["exchange_accounts"]["order"], step["order"])
		self.assertLess(step["order"], steps["vat_id_label"]["order"])

	def test_every_text_reads_in_german(self):
		texts = {*messages(MODULE), "Default Accounts of the Company"}
		self.assertEqual(len(texts), 7)
		self.assertEqual(sorted(texts - translations().keys()), [])

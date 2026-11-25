"""The step „Konten der Wechselkursdifferenzen“ in the hooks and its texts in German, without a site."""

from pathlib import Path
from unittest import TestCase

from steuerbote import hooks
from steuerbote.tests.test_setup_files import messages, translations

APP = Path(__file__).resolve().parents[1]
MODULE = APP / "steuerbote" / "exchange_setup.py"


class ExchangeSetupFilesTest(TestCase):
	def test_the_step_comes_after_the_bilanzzuordnung(self):
		steps = {step["key"]: step for step in hooks.steuerbote_setup_steps}
		step = steps["exchange_accounts"]
		self.assertEqual(step["run"], "steuerbote.steuerbote.exchange_setup.check")
		self.assertLess(steps["balance_sheet_mapping"]["order"], step["order"])
		self.assertLess(step["order"], steps["vat_id_label"]["order"])

	def test_every_text_reads_in_german(self):
		texts = {*messages(MODULE), "Exchange Rate Accounts"}
		self.assertEqual(len(texts), 5)
		self.assertEqual(sorted(texts - translations().keys()), [])

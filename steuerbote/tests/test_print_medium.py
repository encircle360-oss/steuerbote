"""Where a printout goes (print_medium.py), read without a bench."""

from unittest import TestCase

from steuerbote.steuerbote import print_medium


class MediumTest(TestCase):
	def test_a_request_of_the_page_printview_goes_to_the_browser(self):
		self.assertEqual(print_medium.medium("/printview"), print_medium.BROWSER)
		self.assertEqual(print_medium.medium("/printview/"), print_medium.BROWSER)

	def test_the_preview_of_the_print_view_goes_to_the_screen(self):
		self.assertEqual(
			print_medium.medium("/api/method/frappe.www.printview.get_html_and_style"), print_medium.SCREEN
		)

	def test_everything_else_goes_to_a_pdf_generator(self):
		for path in (None, "", "/api/method/frappe.utils.print_format.download_pdf", "/app/vat-return"):
			with self.subTest(path=path):
				self.assertEqual(print_medium.medium(path), print_medium.PDF)


class PageRuleTest(TestCase):
	def test_escapes_what_would_end_a_css_string(self):
		self.assertEqual(print_medium.css_string('A "B" \\ C\nD · E'), '"A \\22 B\\22  \\5C  C\\A D \\B7  E"')

	def test_puts_head_and_foot_in_the_margin_boxes_and_numbers_the_pages(self):
		rule = print_medium.page_rule(
			("Umsatzsteuer-Voranmeldung 2026 · Muster GmbH", "Steuernummer 123/456/78901"),
			("UStVA-2026-00001 · Bereit", "Voranmeldungszeitraum Oktober 2026"),
			"Erstellt am 25.11.2026 10:00 mit Steuerbote 0.15.1",
		)
		self.assertTrue(rule.startswith("@page {"))
		for box in ("@top-left", "@top-right", "@bottom-left", "@bottom-right"):
			with self.subTest(box=box):
				self.assertIn(box, rule)
		self.assertIn('content: "Seite " counter(page) " von " counter(pages);', rule)
		self.assertIn(
			print_medium.css_string("UStVA-2026-00001 · Bereit\nVoranmeldungszeitraum Oktober 2026"), rule
		)
		self.assertIn(print_medium.css_string("Erstellt am 25.11.2026 10:00 mit Steuerbote 0.15.1"), rule)
		self.assertEqual(rule.count("{"), rule.count("}"))

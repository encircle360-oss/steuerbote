"""Where a printout goes, which decides what the running head and foot of a print format add.

Frappe 16 renders a print format in three ways (frappe/printing/page/print/print.js, frappe/www/printview.py):
through a PDF generator, as for the buttons PDF and Drucken, a download, an e-mail attachment or a bulk print; as the
preview of the print view on the screen (get_html_and_style); and as the page /printview, which the browser prints
itself when someone opens it and prints it. Only a generator repeats the running head and foot on every page and
fills in its page numbers. The browser gets them from the margin boxes of @page with its counters of page and pages,
which Chromium fills; the screen gets neither.
"""

PDF = "pdf"
SCREEN = "screen"
BROWSER = "browser"
PREVIEW = "frappe.www.printview.get_html_and_style"
FONT = '"Nimbus Sans", "Liberation Sans", Arial, Helvetica, sans-serif'
BOX = "color: #333; font-family: " + FONT + "; font-size: 7.5pt; line-height: 13px; white-space: pre;"


def medium(path: str | None) -> str:
	"""The medium of a printout by the path of the request that renders it."""
	if not path:
		return PDF
	path = path.rstrip("/")
	if path.endswith(PREVIEW):
		return SCREEN
	if path == "/printview":
		return BROWSER
	return PDF


def css_string(text: str) -> str:
	"""A text as a CSS string, every character that could end it or that a margin box might misread escaped."""
	return '"' + "".join(f"\\{ord(char):X} " if char in '"\\\n\r·' else char for char in text) + '"'


def page_rule(head_left: tuple[str, str], head_right: tuple[str, str], foot_left: str) -> str:
	"""The @page rule that gives the browser the running head and foot: two lines left and right in the top margin,
	when and with which version on the left and the page of how many on the right of the bottom margin."""
	return (
		"@page {\n"
		f"\t@top-left {{ {BOX} content: {css_string(chr(10).join(head_left))}; vertical-align: bottom; padding-bottom: 4mm; }}\n"
		f"\t@top-right {{ {BOX} content: {css_string(chr(10).join(head_right))}; text-align: right; vertical-align: bottom; padding-bottom: 4mm; }}\n"
		f"\t@bottom-left {{ {BOX} content: {css_string(foot_left)}; vertical-align: top; padding-top: 4mm; }}\n"
		f'\t@bottom-right {{ {BOX} content: "Seite " counter(page) " von " counter(pages); text-align: right; vertical-align: top; padding-top: 4mm; }}\n'
		"}"
	)


def steuerbote_print_medium() -> str:
	"""The medium of the printout the current request renders, for the templates."""
	import frappe

	request = getattr(frappe.local, "request", None)
	return medium(getattr(request, "path", None))


def steuerbote_browser_page(head_left, head_right, foot_left: str) -> str:
	"""The @page rule of the browser for the templates, from the lines of the running head and foot."""
	return page_rule(tuple(head_left), tuple(head_right), foot_left)

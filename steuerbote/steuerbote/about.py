"""Über Steuerbote: who makes Steuerbote and where its source, documentation, issues and disclaimer are, the block at
the bottom of the workspace Steuern and on the page Steuerbote einrichten (about_block.py serves it to the desk). The
block loads nothing from another site; its links open in a new tab and tell their target nothing of the site."""

from collections.abc import Callable
from html import escape

from steuerbote import __version__

# The Custom HTML Block of the workspace, steuerbote/fixtures/custom_html_block.json. The desk finds a block of a
# workspace by its translated label, so the name reads the same in every language, like that of the number card.
BLOCK = "Über Steuerbote"
REPOSITORY = "https://github.com/encircle360-oss/steuerbote"
LOGO = "/assets/steuerbote/images/steuerbote-logo.svg"
SERVICES = "https://encircle360.com/?ref=steuerbote"
LINKS = (
	("Source Code", REPOSITORY),
	("Documentation", f"{REPOSITORY}/tree/main/docs"),
	("Report a Problem", f"{REPOSITORY}/issues"),
	("Disclaimer", f"{REPOSITORY}/blob/main/docs/haftungsausschluss.md"),
)
TITLE = "About Steuerbote"
LICENCE = "Steuerbote is free software (AGPL-3.0) by encircle360 GmbH and all contributors."
DISCLAIMER = "No warranty. Steuerbote is no substitute for tax advice."
SERVICES_TEXT = "Introduction, Operation and Support: {0}"
TEXTS = (TITLE, LICENCE, DISCLAIMER, SERVICES_TEXT, *(label for label, _url in LINKS))


def steuerbote_version() -> str:
	"""The version of the installed app, for the line „Erstellt mit Steuerbote“ of the printouts."""
	return __version__


def steuerbote_pdf_generator() -> str:
	"""The PDF generator a print format is rendered for, „chrome“ or „wkhtmltopdf“, which get_print of Frappe sets in
	the form_dict before it renders the print view; empty for the preview in the browser."""
	import frappe

	return (getattr(frappe.local, "form_dict", None) or {}).get("pdf_generator") or ""


def _link(text: str, url: str) -> str:
	return f'<a href="{escape(url)}" target="_blank" rel="noopener noreferrer">{escape(text)}</a>'


def render(translate: Callable[[str], str], version: str = __version__) -> str:
	"""The block in the language of translate, with the colours of the desk and wrapping on a narrow screen."""
	links = "".join(
		f'<li class="list-inline-item">{_link(translate(label), url)}</li>' for label, url in LINKS
	)
	services = escape(translate(SERVICES_TEXT)).replace("{0}", _link("encircle360.com", SERVICES))
	return (
		f'<section class="steuerbote-about" aria-label="{escape(translate(TITLE))}" style="display: flex; '
		"flex-wrap: wrap; align-items: flex-start; gap: var(--padding-md, 1rem); padding: var(--padding-md, 1rem); "
		"border: 1px solid var(--border-color); border-radius: var(--border-radius-md, 0.5rem); "
		'background: var(--card-bg); color: var(--text-color);">'
		f'<img src="{LOGO}" alt="" width="40" height="40" style="flex: none;">'
		'<div style="flex: 1 1 16rem; min-width: 0;">'
		f'<div style="font-weight: 600;">Steuerbote {escape(version)}</div>'
		f'<p class="text-muted" style="margin: 0.25rem 0 0;">{escape(translate(LICENCE))}</p>'
		f'<p class="text-muted" style="margin: 0 0 0.25rem;">{escape(translate(DISCLAIMER))}</p>'
		f'<ul class="list-inline" style="margin: 0 0 0.25rem;">{links}</ul>'
		f'<p class="text-muted" style="margin: 0;">{services}</p>'
		"</div></section>"
	)

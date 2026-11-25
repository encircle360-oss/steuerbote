"""The proof of the print formats as PDF, for CI: every print format of the app, rendered with wkhtmltopdf as Frappe
renders it on a site, for the documents of the browser tests (steuerbote/tests/e2e/seed.py) and for variants of them
that stress the layout, then checked page by page (printouts.py):

	bench --site <site> execute steuerbote.tests.print_proof.run --kwargs "{'directory': '<directory>'}"

The variants change the document in memory only and save nothing: „kurz“ is the document as the seed made it,
„lang“ repeats the rows of its print and adds many findings and long remarks, „namen“ gives it an invented company
with a long name, long labels and large negative amounts and marks it as a Berichtigung. The Jahresabschluss also
prints its Vorschau der Offenlegung.

Each printout is rendered without the stylesheet of Frappe's print bundle, as on a site where wkhtmltopdf cannot load
it, and the short ones once more with it, so that both look the same. The directory receives the PDFs, the words of
their pages (pdftotext -bbox) and report.md with the pages and the problems of each; the run fails when one has a
problem. Every record is invented; nothing goes to a real company.
"""

import copy
import re
import shutil
import subprocess
import sys
from pathlib import Path

import frappe
from frappe.utils.pdf import get_pdf

from steuerbote.tests import printouts

# The print format of each DocType and the texts that must stand on one page in its printout.
FORMATS = {
	"VAT Return": (
		"Umsatzsteuer-Voranmeldung",
		(("H. Vorauszahlung/Überschuss", "Verbleibende Umsatzsteuer"),),
	),
	"VAT Return Extension": ("Dauerfristverlängerung", ()),
	"Recapitulative Statement": (
		"Zusammenfassende Meldung",
		(("Innergemeinschaftliche Warenlieferungen", "Sonstige Leistungen (§ 3a Absatz 2 UStG)"),),
	),
	"Annual VAT Return": (
		"Umsatzsteuererklärung",
		(("Vorauszahlungssoll und Abschlusszahlung", "Abschlusszahlung oder Erstattung (Kz 820)"),),
	),
	"Electronic Balance Sheet": ("E-Bilanz", ()),
	"Corporate Income Tax Return": (
		"Körperschaftsteuererklärung",
		(("Jahresüberschuss (Anlage GK Zeile 11)", "Steuerliches Einlagekonto zum Schluss"),),
	),
	"Trade Tax Return": (
		"Gewerbesteuererklärung",
		(("Gewinn aus Gewerbebetrieb (Zeile 39)", "Abschlusszahlung oder Erstattung"),),
	),
	"Annual Accounts": ("Jahresabschluss", ()),
}
# The headings of the print formats, none of which may end a page.
HEADINGS = (
	"Befunde",
	"Berechnung",
	"Anmerkungen",
	"Bemerkungen",
	"Abgabe",
	"Offene Punkte",
	"Bilanz",
	"Kontennachweis",
	"Überleitungsrechnung",
	"Anlagenspiegel (brutto)",
	"Steuerlicher Betriebsvermögensvergleich",
	"Gewinn- und Verlustrechnung (Gesamtkostenverfahren)",
	"Korrekturen gegenüber dem Hauptbuch",
	"Korrekturen und Zeilen von Hand",
	"Vorauszahlungssoll und Abschlusszahlung",
	"Abgleich je Voranmeldungszeitraum",
	"Abgleich je Kennzahl",
	"Vordruck USt 1 H",
	"Grundlage von Hand",
	"Ergebnisverwendung",
	"Angaben unter der Bilanz",
	"Anhang",
	"Feststellung und Unterzeichnung",
	"Upload zum Unternehmensregister",
)
# What the print formats read from their document beyond its fields; a variant computes it once and changes it.
PRINT_METHODS = (
	"annual_print",
	"annual_vat_print",
	"income_tax_print",
	"e_bilanz_print",
	"annual_accounts_print",
	"statutory_taxes",
	"provisional_forms",
)
LONG_COMPANY = (
	"Holzbau und Innenausbau Rheinisch-Bergisches Land Beteiligungsgesellschaft mbH & Co. KG (Musterfall)"
)
LONGER = " einschließlich der weiteren Angaben, die eine Bezeichnung über mehrere Zeilen laufen lassen"
LARGE_NEGATIVE = "-9.876.543,21"
AMOUNT = re.compile(r"-?\d{1,3}(\.\d{3})*(,\d+)?")
AMOUNT_KEYS = {"value", "amount", "left", "right", "tax", "sum", "current", "previous", "prior"}
TEXT_KEYS = {"label", "value", "text", "party", "title"}
REPEAT = 3
LINK = re.compile(r'<link[^>]*rel="stylesheet"[^>]*>')
SCRIPT = re.compile(r"<script[^>]*\bsrc=[^>]*>\s*</script>")
BUNDLE = re.compile(r'href="(/assets/[^"]*print\.bundle[^"]*\.css)"')


def run(directory: str) -> None:
	out = Path(directory)
	out.mkdir(parents=True, exist_ok=True)
	report, failed = ["# Ausdrucke als PDF", ""], False
	for doctype, (print_format, together) in FORMATS.items():
		name = sample(doctype)
		for variant, doc in variants(doctype, name):
			for bundle in (False, True) if variant == "kurz" else (False,):
				stem = f"{slug(print_format)}__{variant}{'__mit-druckstil' if bundle else ''}"
				problems, pages = proof(out, stem, doc, print_format, together, bundle)
				failed = failed or bool(problems)
				report.append(f"- {stem}: {pages} Seiten{'' if not problems else ', ' + '; '.join(problems)}")
	(out / "report.md").write_text("\n".join(report) + "\n", encoding="utf-8")
	sys.stdout.write("\n".join(report) + "\n")
	if failed:
		raise SystemExit("Ausdrucke mit Problemen, siehe report.md")


def sample(doctype: str) -> str:
	"""The document of the seed to print: a calculated one where there is one."""
	for filters in ({"status": ("in", ("Berechnet", "Bereit", "Abgegeben"))}, {}):
		names = frappe.get_all(doctype, filters=filters, order_by="modified desc", limit=1, pluck="name")
		if names:
			return names[0]
	raise SystemExit(f"Kein Beleg „{doctype}“ auf der Site")


def variants(doctype: str, name: str):
	yield "kurz", frappe.get_doc(doctype, name)
	yield "lang", lengthened(frappe.get_doc(doctype, name))
	yield "namen", renamed(frappe.get_doc(doctype, name))
	if doctype == "Annual Accounts":
		doc = frappe.get_doc(doctype, name)
		doc.flags.offenlegung = True
		yield "offenlegung", doc


def frozen(doc, change):
	"""The document with each print method answering what it answered before, changed by change."""
	for method in PRINT_METHODS:
		if hasattr(doc, method):
			answer = change(getattr(doc, method)())
			setattr(doc, method, lambda answer=answer: answer)
	return doc


def repeated(value):
	"""Each list of rows of a print three times, which makes long tables of every part."""
	if isinstance(value, dict):
		return type(value)({key: repeated(item) for key, item in value.items()})
	if isinstance(value, list) and value and all(isinstance(item, dict | tuple) for item in value):
		rows = [repeated(item) for item in value]
		return [copy.deepcopy(row) for _ in range(REPEAT) for row in rows]
	return value


def stretched(value, key=None):
	"""Long labels and texts and large negative amounts in a print."""
	if isinstance(value, dict):
		return type(value)({k: stretched(item, k) for k, item in value.items()})
	if isinstance(value, list):
		return [stretched(item, key) for item in value]
	if isinstance(value, tuple):
		items = [stretched(item, key) for item in value]
		return type(value)(*items) if hasattr(value, "_fields") else tuple(items)
	if isinstance(value, str) and key in AMOUNT_KEYS and AMOUNT.fullmatch(value.strip()):
		return LARGE_NEGATIVE
	if isinstance(value, str) and key in TEXT_KEYS and value.strip():
		return value + LONGER
	return value


def lengthened(doc):
	"""Many findings, long remarks and every table of the print three times."""
	if doc.meta.has_field("findings") and doc.meta.get_field("findings").fieldtype == "Table":
		for index in range(45):
			doc.append(
				"findings",
				{
					"severity": "Fehler" if index % 3 == 0 else "Hinweis",
					"code": f"SB-BEFUND-MIT-LANGEM-CODE-{index:02d}",
					"text": f"Befund {index + 1}: Das Konto 1{index:03d} hat einen Saldo, der in keine Zeile eingeht."
					" Ordnen Sie es einer Position zu oder sagen Sie, warum es außerhalb bleibt.",
					"reference": f"bs.ass.currAss.receiv.other.vat.{index:02d}",
				},
			)
	elif doc.meta.has_field("findings"):
		doc.findings = "Offener Punkt mit einer langen Erklärung. " * 12
	if doc.meta.has_field("remarks"):
		doc.remarks = "Anmerkung zum Ausdruck mit einem längeren Text für die Steuerberatung. " * 10
	for row in doc.get("kennzahlen") or ():
		row.override_reason = "Korrektur von Hand mit Begründung für die Akte und die Steuerberatung."
	if doc.doctype == "Recapitulative Statement":
		for index in range(50):
			doc.append(
				"lines",
				{
					"vat_id": f"ATU{10000000 + index}",
					"party": f"Musterkunde Nummer {index + 1} Handelsgesellschaft",
					"art": "LDS"[index % 3],
					"in_file": 1,
					"reported": 1000 * (index + 1),
					"filed_amount": 900 * (index + 1),
				},
			)
	return frozen(doc, repeated)


def renamed(doc):
	"""An invented company with a long name, long labels and large negative amounts, as a Berichtigung."""
	frozen(doc, stretched)
	doc.company = LONG_COMPANY
	for row in doc.get("kennzahlen") or ():
		row.final = -9876543.21
		row.label = (row.label or "") + LONGER
	for row in doc.get("lines") or ():
		row.party = (row.party or "") + LONGER
	if doc.meta.has_field("is_correction"):
		doc.is_correction = 1
	if doc.meta.has_field("corrects"):
		doc.corrects = doc.name
	return doc


def proof(out: Path, stem: str, doc, print_format: str, together, bundle: bool) -> tuple[list[str], int]:
	try:
		pdf = render(doc, print_format, bundle)
	except Exception as error:
		return [f"nicht gedruckt: {error}"], 0
	path = out / f"{stem}.pdf"
	path.write_bytes(pdf)
	pdftotext = shutil.which("pdftotext") or "pdftotext"
	words = subprocess.run(  # noqa: S603 - Poppler on a PDF this run wrote
		[pdftotext, "-bbox", str(path), "-"], capture_output=True, text=True, check=True
	)
	(out / f"{stem}.bbox.html").write_text(words.stdout, encoding="utf-8")
	pages = printouts.read_bbox(words.stdout)
	expected = printouts.Expectations(
		pages=(1, 60),
		on_every_page=(doc.name,),
		headings=HEADINGS,
		together=together,
	)
	return printouts.check(pages, expected), len(pages)


def render(doc, print_format: str, bundle: bool) -> bytes:
	"""The PDF of a document with wkhtmltopdf, from the HTML Frappe prints, without or with Frappe's print bundle."""
	html = frappe.get_print(
		doc.doctype, doc.name, print_format, doc=doc, no_letterhead=1, pdf_generator="wkhtmltopdf"
	)
	style = ""
	if bundle:
		match = BUNDLE.search(html)
		if match:
			style = (
				"<style>" + Path(frappe.local.sites_path, match.group(1).lstrip("/")).read_text() + "</style>"
			)
	html = SCRIPT.sub("", LINK.sub(style.replace("\\", "\\\\"), html, count=1))
	html = LINK.sub("", html)
	return get_pdf(html)


def slug(text: str) -> str:
	for umlaut, plain in (("ä", "ae"), ("ö", "oe"), ("ü", "ue"), ("ß", "ss")):
		text = text.replace(umlaut, plain)
	return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")

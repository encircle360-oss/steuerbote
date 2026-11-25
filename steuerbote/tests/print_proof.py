"""The proof of the print formats as PDF, for CI: every print format of the app, in German and with both engines
Frappe offers, wkhtmltopdf and the Chromium-based one, for the documents of the browser tests
(steuerbote/tests/e2e/seed.py, made in German) and for variants of them that stress the layout, then checked page by
page (printouts.py):

	bench --site <site> execute steuerbote.tests.print_proof.run --kwargs "{'directory': '<directory>'}"

The variants change the document in memory only and save nothing: „kurz“ is the document as the seed made it,
„lang“ repeats the rows of its print and adds many findings and long remarks, „namen“ gives it an invented company
with a long name, long labels and large negative amounts and marks it as a Berichtigung. The Jahresabschluss also
prints its Vorschau der Offenlegung, the E-Bilanz an invented Anlagenspiegel.

The step of the CI makes the URL of the site unreachable: a print format must load nothing. wkhtmltopdf gets the HTML
without the link to Frappe's print bundle, which Frappe adds for every print format, and the short printouts once more
with the bundle inlined, so that both look the same; any other address in the HTML fails the printout. The directory
receives the PDFs, the words of their pages (pdftotext -bbox) and report.md with the pages and the problems of each;
the run fails when one has a problem. Every record is invented; nothing goes to a real company.
"""

import copy
import re
import shutil
import subprocess
import sys
from pathlib import Path

import frappe
from frappe import _
from frappe.translate import clear_cache as clear_translations
from frappe.translate import get_translations_from_csv, print_language
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
	"left_out_lines",
	"open_errors",
)
LONG_COMPANY = (
	"Holzbau und Innenausbau Rheinisch-Bergisches Land Beteiligungsgesellschaft mbH & Co. KG (Musterfall)"
)
LONGER = " einschließlich der weiteren Angaben, die eine Bezeichnung über mehrere Zeilen laufen lassen"
LARGE_NEGATIVE = "-9.876.543,21"
AMOUNT = re.compile(r"-?\d{1,3}(\.\d{3})*(,\d+)?")
AMOUNT_KEYS = {
	"value",
	"amount",
	"left",
	"right",
	"tax",
	"sum",
	"current",
	"previous",
	"prior",
	"cost",
	"depreciation",
}
TEXT_KEYS = {"label", "value", "text", "party", "title"}
REPEAT = 3
LANGUAGE = "de"
# The words a printout must not hold, which only an English one does.
ENGLISH = ("the", "has", "with")
# The margins of the stylesheet of the print formats, steuerbote/templates/includes/print/style.html.
MARGINS = printouts.Margins(top=28, bottom=18, left=20, right=15)
# German texts that the printouts of the documents of the seed hold, so that a fallback to English fails the run.
GERMAN = {
	"Corporate Income Tax Return": ("Steuerbote hat die Vordrucke für",),
	"Trade Tax Return": ("Steuerbote hat die Vordrucke für",),
}
LINK = re.compile(r'<link[^>]*rel="stylesheet"[^>]*>')
SCRIPT = re.compile(r"<script[^>]*\bsrc=[^>]*>\s*</script>")
# What makes a browser fetch something: a source, a stylesheet, a CSS address or import.
FETCHED = re.compile(r"""\bsrc=["'][^"']+|<link\b[^>]*>|url\([^)]*\)|@import[^;]*""", re.IGNORECASE)
BUNDLE = re.compile(r'href="(/assets/[^"]*print\.bundle[^"]*\.css)"')


def run(directory: str) -> None:
	"""Every printout in German, the language of the sites Steuerbote serves: German texts run longer than their
	English source, and the checks of margins and page breaks are only worth what the texts they measure are."""
	# The translations Frappe keeps in Redis may be those a process built before the app's were complete.
	clear_translations()
	with print_language(LANGUAGE):
		# Any source text of the app's de.csv serves as probe, so that rewording a text never breaks the proof.
		source, german = next(
			(source, german)
			for source, german in get_translations_from_csv(LANGUAGE, "steuerbote").items()
			if source != german
		)
		if _(source) != german:
			raise SystemExit(
				"Die deutschen Übersetzungen von Steuerbote fehlen, die Ausdrucke wären englisch "
				f"(Sprache {frappe.local.lang}, Probe {source!r})."
			)
		proof_all(directory)


def proof_all(directory: str) -> None:
	out = Path(directory)
	out.mkdir(parents=True, exist_ok=True)
	report, failed = ["# Ausdrucke als PDF", ""], False
	for doctype, (print_format, together) in FORMATS.items():
		name = sample(doctype)
		for variant, make in variants(doctype, name):
			try:
				doc = make()
			except Exception as error:
				failed = True
				report.append(f"- {slug(print_format)}__{variant}: nicht angelegt: {error!r}")
				continue
			renders = [("wkhtmltopdf", False), ("chrome", False)]
			if variant == "kurz":
				renders.append(("wkhtmltopdf", True))
			printed = {}
			for engine, bundle in renders:
				stem = f"{slug(print_format)}__{variant}__{engine}{'__mit-druckstil' if bundle else ''}"
				problems, pages, lines = proof(out, stem, doc, print_format, together, engine, bundle)
				if not bundle:
					printed[engine] = lines
				failed = failed or bool(problems)
				report.append(
					f"- {stem}: {len(pages)} Seiten{'' if not problems else ', ' + '; '.join(problems)}"
				)
			if all(printed.values()):
				differences = printouts.alike(printed["wkhtmltopdf"], printed["chrome"], MARGINS)
				failed = failed or bool(differences)
				report.append(
					f"- {slug(print_format)}__{variant}: "
					+ ("beide Generatoren gleich" if not differences else "; ".join(differences))
				)
	(out / "report.md").write_text("\n".join(report) + "\n", encoding="utf-8")
	sys.stdout.write("\n".join(report) + "\n")
	if failed:
		raise SystemExit("Ausdrucke mit Problemen, siehe report.md")


def sample(doctype: str) -> str:
	"""The document of the seed to print: of the calculated ones the one with the most rows, else any."""
	for filters in ({"status": ("in", ("Berechnet", "Bereit", "Abgegeben"))}, {}):
		names = frappe.get_all(doctype, filters=filters, order_by="modified desc", limit=20, pluck="name")
		if names:
			return max(names, key=lambda name: rows(frappe.get_doc(doctype, name)))
	raise SystemExit(f"Kein Beleg „{doctype}“ auf der Site")


def rows(doc) -> int:
	return sum(len(doc.get(field.fieldname) or ()) for field in doc.meta.get_table_fields())


def variants(doctype: str, name: str):
	"""Each variant by its name with what makes it, so that one that fails costs only itself."""

	def document():
		return with_fixed_assets(frappe.get_doc(doctype, name))

	yield "kurz", document
	yield "lang", lambda: lengthened(document())
	yield "namen", lambda: renamed(document())
	if doctype == "Annual Accounts":
		yield "offenlegung", lambda: disclosed(document())


# An invented Anlagenspiegel of four asset categories, with additions, a disposal and depreciation, which an E-Bilanz
# prints in all eight columns of its part „Abschreibungen und Buchwert“ (layout.DEPRECIATION_COLUMNS).
FIXED_ASSETS = (
	{
		"position_label": "andere Anlagen, Betriebs- und Geschäftsausstattung (Betriebsausstattung)",
		"cost_begin": 1209.41,
		"depreciation_begin": 1083.41,
		"depreciation_regular": 125,
	},
	{
		"position_label": "andere Anlagen, Betriebs- und Geschäftsausstattung (Büroeinrichtung)",
		"cost_begin": 12100,
		"additions": 2450.5,
		"depreciation_begin": 5500,
		"depreciation_regular": 1299.76,
	},
	{
		"position_label": "andere Anlagen, Betriebs- und Geschäftsausstattung (Computerhardware)",
		"cost_begin": 8461.34,
		"additions": 12805.04,
		"depreciation_begin": 6218.34,
		"depreciation_regular": 3045.04,
		"depreciation_7g": 2500,
		"writeups": 150,
	},
	{
		"position_label": "technische Anlagen und Maschinen (Fahrzeuge)",
		"cost_begin": 48900,
		"disposals": 48900,
		"depreciation_begin": 36675,
		"depreciation_regular": 8150,
		"depreciation_disposals": 44825,
	},
)


def with_fixed_assets(doc):
	"""An E-Bilanz without fixed assets gets the invented Anlagenspiegel, so that every run prints it."""
	if doc.doctype != "Electronic Balance Sheet" or doc.get("fixed_assets"):
		return doc
	for asset in FIXED_ASSETS:
		row = {"value_type": "StB", "manual": 1, **asset}
		row["cost_end"] = row.get("cost_begin", 0) + row.get("additions", 0) - row.get("disposals", 0)
		row["depreciation_end"] = (
			row.get("depreciation_begin", 0)
			+ row.get("depreciation_regular", 0)
			+ row.get("depreciation_7g", 0)
			- row.get("depreciation_disposals", 0)
			- row.get("writeups", 0)
		)
		row["book_value_end"] = row["cost_end"] - row["depreciation_end"]
		doc.append("fixed_assets", row)
	return doc


def disclosed(doc):
	"""The Jahresabschluss as its Vorschau der Offenlegung prints it."""
	doc.flags.offenlegung = True
	return doc


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


FINDING_CODES = ("JA-RESTLAUFZEIT-FEHLT", "BILANZ-OHNE-PLATZ", "JOURNALBUCHUNG-STEUERKONTO", "ZEITRAUM-FEHLT")
FINDING_TEXTS = (
	"Für „{account} - Verbindlichkeiten aus Lieferungen und Leistungen gegenüber verbundenen Unternehmen“ fehlt die"
	" Restlaufzeit, die der Vermerk „davon mit einer Restlaufzeit bis zu einem Jahr“ bei „Verbindlichkeiten“"
	" braucht; die Zuordnung nennt sie. (§ 268 Abs. 5 Satz 1 HGB)",
	"Konto {account} hat einen Saldo, aber keinen Platz in der Bilanzzuordnung: Ordnen Sie es einer Position zu"
	" oder sagen Sie, warum es außerhalb von Bilanz und GuV liegt.",
	"Die Journalbuchung ACC-JV-2026-{account} bewegt das Steuerkonto 1776 um -1.900,00 Euro, ohne das Kennzeichen"
	" „Nicht in der Umsatzsteuer-Voranmeldung“: Eine Verrechnung der Steuerkonten braucht das Kennzeichen, eine"
	" Korrektur nicht.",
	"Keine abgegebene Voranmeldung deckt Dezember 2026 ab: sie abgeben oder mit Begründung darauf verzichten.",
)


def lengthened(doc):
	"""Many findings, long remarks and every table of the print three times."""
	if doc.meta.has_field("findings") and doc.meta.get_field("findings").fieldtype == "Table":
		for index in range(45):
			doc.append(
				"findings",
				{
					"severity": "Fehler" if index % 3 == 0 else "Hinweis",
					"code": FINDING_CODES[index % len(FINDING_CODES)],
					"text": FINDING_TEXTS[index % len(FINDING_TEXTS)].format(account=1500 + index),
					"reference": f"bs.ass.currAss.receiv.other.vat.{index:02d}",
				},
			)
	elif doc.meta.has_field("findings"):
		doc.findings = (
			"Die Sondervorauszahlung des Vorjahres ist noch nicht verrechnet; die Grundlage nimmt die Voranmeldungen,"
			" die vor Steuerbote abgegeben wurden, mit den Beträgen laut Bescheid. "
		) * 4
	if doc.meta.has_field("remarks"):
		doc.remarks = (
			"Mit der Steuerberatung am 12.03.2027 abgestimmt: Die Abweichung der Umsatzerlöse gegenüber der E-Bilanz"
			" beruht auf Anzahlungen, die erst im Folgejahr als Umsatz gebucht werden. Die Hinweise zu den"
			" Journalbuchungen betreffen die monatliche Verrechnung der Steuerkonten und sind geprüft. "
		) * 3
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
					"acceptance_reason": RELEASE_REASON if index % 10 == 0 else None,
				},
			)
	if doc.doctype == "VAT Return":
		for index in range(12):
			doc.append(
				"hints",
				{
					"severity": "Fehler",
					"code": "JOURNALBUCHUNG-STEUERKONTO",
					"text": FINDING_TEXTS[2].format(account=11200 + index),
				},
			)
	# The annex with every hint, which the print of an annual document holds only on request.
	frappe.form_dict["all_hints"] = 1
	try:
		frozen(doc, repeated)
	finally:
		frappe.form_dict.pop("all_hints", None)
	if doc.doctype == "Recapitulative Statement":
		doc.left_out_lines = lambda: LEFT_OUT
		doc.open_errors = lambda: OPEN_ERRORS
	return doc


RELEASE_REASON = (
	"Bestätigung der USt-IdNr. vom Liefertag (qualifizierte Abfrage beim BZSt) liegt in der Akte."
)
LEFT_OUT = [
	{
		"vat_id": f"FR{12345678900 + index}",
		"party": f"Société d'exemple numéro {index + 1} SARL",
		"art": "LDS"[index % 3],
		"amount": 1234.56 * (index + 1),
	}
	for index in range(8)
]
OPEN_ERRORS = [
	{
		"code": "ZM-USTID-UNBESTAETIGT",
		"text": f"Die USt-IdNr. ATU{10000000 + index} ist nicht bestätigt: vor der Abgabe beim BZSt bestätigen oder mit Begründung freigeben.",
	}
	for index in range(10)
]


def renamed(doc):
	"""An invented company with a long name, long labels and large negative amounts, as a Berichtigung."""
	frozen(doc, stretched)
	doc.company = LONG_COMPANY
	for row in doc.get("kennzahlen") or ():
		row.final = -9876543.21
		row.label = (row.label or "") + LONGER
	if doc.doctype == "Recapitulative Statement":
		for row in doc.lines:
			row.party = (row.party or "") + LONGER
	if doc.meta.has_field("is_correction"):
		doc.is_correction = 1
	if doc.meta.has_field("corrects"):
		doc.corrects = doc.name
	return doc


def proof(
	out: Path, stem: str, doc, print_format: str, together, engine: str, bundle: bool
) -> tuple[list[str], list[printouts.Page], list[printouts.Page]]:
	"""The problems of a printout, its pages as pdftotext reads them and its pages with the text at its baselines."""
	try:
		pdf = render(doc, print_format, engine, bundle)
	except Exception as error:
		return [f"nicht gedruckt: {error}"], [], []
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
		last_page_lines=8,
		on_every_page=(doc.name,),
		headings=HEADINGS,
		together=together,
		somewhere=GERMAN.get(doc.doctype, ()),
		nowhere=ENGLISH,
		margins=MARGINS,
	)
	return printouts.check(pages, expected), pages, baselines(path)


def baselines(path: Path) -> list[printouts.Page]:
	"""The pages of a PDF with each piece of text as a word whose box is its baseline, in points from the top edge.
	pdftotext boxes a word by the ascent and descent of its font, and the two generators embed the same font with
	different ones; the baseline is where both set the text."""
	from pypdf import PdfReader

	pages = []
	for page in PdfReader(path).pages:
		height = float(page.mediabox.height)
		words = []

		def visit(text, cm, tm, _font, _size, words=words, height=height):
			if text.strip():
				base = height - (tm[4] * cm[1] + tm[5] * cm[3] + cm[5])
				words.append(printouts.Word(0.0, base, 0.0, base, text.strip()))

		page.extract_text(visitor_text=visit)
		pages.append(printouts.Page(float(page.mediabox.width), height, tuple(words)))
	return pages


def render(doc, print_format: str, engine: str, bundle: bool) -> bytes:
	"""The PDF of a document with one of the engines of Frappe. The Chromium-based one takes the assets of the bench
	from disk. wkhtmltopdf would fetch Frappe's print bundle from the URL of the site, which the step of the CI makes
	unreachable; it gets the HTML without that link, or with the bundle inlined, and fails on any other address the
	print format would load (FETCHED)."""
	if engine == "chrome":
		return frappe.get_print(
			doc.doctype, doc.name, print_format, doc=doc, no_letterhead=1, as_pdf=True, pdf_generator="chrome"
		)
	html = frappe.get_print(
		doc.doctype, doc.name, print_format, doc=doc, no_letterhead=1, pdf_generator="wkhtmltopdf"
	)
	bundle_link = BUNDLE.search(html)
	html = LINK.sub("", SCRIPT.sub("", html))
	if fetched := FETCHED.findall(html):
		raise ValueError(f"lädt aus dem Netz: {fetched[:3]}")
	if bundle and bundle_link:
		css = Path(frappe.local.sites_path, bundle_link.group(1).lstrip("/")).read_text()
		html = html.replace("</head>", f"<style>{css}</style></head>", 1)
	return get_pdf(html)


def slug(text: str) -> str:
	for umlaut, plain in (("ä", "ae"), ("ö", "oe"), ("ü", "ue"), ("ß", "ss")):
		text = text.replace(umlaut, plain)
	return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")

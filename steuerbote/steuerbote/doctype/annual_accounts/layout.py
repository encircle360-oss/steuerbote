"""What the print format „Jahresabschluss“ and its Vorschau der Offenlegung show of an Annual Accounts, from the rows
the document stores; it computes nothing.

- The Bilanz (balance_sheet), in the order of § 266 HGB, the positions of the class with an amount in either year
  (§ 265 Abs. 8 HGB) and their Vermerke, each with the amount of the previous year (§ 265 Abs. 2 Satz 1 HGB), and
  the total of each side; account_form puts both sides side by side, „Die Bilanz ist in Kontoform aufzustellen.“
  (§ 266 Abs. 1 Satz 1 HGB)
- The GuV (income_statement) of § 275 Abs. 2 HGB, which Kleinst and klein draw up but do not disclose (§ 326 Abs. 1
  Satz 1 and Abs. 2 Satz 1 HGB).
- The Angaben (notes): a Kleinst states them „unter der Bilanz“ (§ 264 Abs. 1 Satz 5 HGB), klein in its Anhang; the
  Vorschau shows of the Anhang of klein only what it discloses, „Der Anhang braucht die die Gewinn- und
  Verlustrechnung betreffenden Angaben nicht zu enthalten.“ (§ 326 Abs. 1 Satz 2 HGB). Above them the data of
  § 264 Abs. 1a HGB (register_lines).
- The signatures (signature_lines): „Der Jahresabschluß ist vom Kaufmann unter Angabe des Datums zu unterzeichnen.“
  (§ 245 Satz 1 HGB), and the disclosed version names each Geschäftsführer with the date and „gez.“ (Bundesamt für
  Justiz, FAQ zu Inhalts- und Formverstößen).
- What becomes visible (visibility): the parts of steuerbote.hgb.disclosure.publication for the class and the mode,
  and for a Hinterlegung that the Bilanz is open „nur auf Antrag durch Übermittlung einer Kopie“ (§ 9 Abs. 6 Satz 3
  HGB).
- The upload to the Unternehmensregister (upload_guide): the steps of steuerbote.hgb.upload with the Testplattform
  first, the fees and the identification, and the fields of the web form, which are unverified.

Amounts are Decimal in euros and cents as the rows hold them; the print formats them.
"""

from collections.abc import Iterable, Mapping
from decimal import Decimal
from itertools import zip_longest
from typing import Any

from steuerbote.hgb import upload
from steuerbote.hgb.disclosure import Mode, publication
from steuerbote.hgb.size import SizeClass
from steuerbote.jahresmeldung.overrides import to_amount
from steuerbote.steuerbote.doctype.annual_accounts.bridge import EMPLOYEES_CODE, VERMERK, Statement, day_of
from steuerbote.ustva.period import day_label

type Row = Mapping[str, Any]

TOTAL = "Summe"
LIQUIDATION = "Die Gesellschaft befindet sich in Liquidation."
DEPOSITED = (
	"Die Bilanz wird hinterlegt: Das Unternehmensregister macht sie nicht öffentlich, eine Kopie erhält nur, wer sie "
	"beantragt (§ 326 Abs. 2, § 9 Abs. 6 Satz 3 HGB)."
)
PUBLISHED = "Die Unterlagen werden im Unternehmensregister veröffentlicht; jeder kann sie dort einsehen."


def _line(row: Row) -> dict[str, Any]:
	return {
		"marker": row.get("marker") or "",
		"label": row.get("label") or "",
		"amount": to_amount(row.get("reported")),
		"prior": to_amount(row.get("prior")),
		"level": row.get("level") or "",
		"vermerk": row.get("level") == VERMERK,
		"total": row.get("level") == TOTAL,
	}


def balance_sheet(rows: Iterable[Row], side: Statement) -> list[dict[str, Any]]:
	"""The lines of one side of the Bilanz that the print shows: each position and Vermerk with an amount in either
	year, and the total of the side."""
	return [
		_line(row)
		for row in rows
		if row.get("statement") == side
		and not row.get("manual")
		and (row.get("shown") or row.get("level") == TOTAL)
	]


def account_form(rows: Iterable[Row]) -> list[tuple[dict[str, Any] | None, dict[str, Any] | None]]:
	"""The Bilanz in Kontoform: line by line the Aktiva on the left and the Passiva on the right, the shorter side
	filled with nothing, and the totals of both sides last."""
	rows = list(rows)
	aktiva, passiva = balance_sheet(rows, Statement.AKTIVA), balance_sheet(rows, Statement.PASSIVA)
	left = [line for line in aktiva if not line["total"]]
	right = [line for line in passiva if not line["total"]]
	totals = (
		next((line for line in aktiva if line["total"]), None),
		next((line for line in passiva if line["total"]), None),
	)
	return [*zip_longest(left, right), totals]


def income_statement(rows: Iterable[Row]) -> list[dict[str, Any]]:
	"""The lines of the GuV that the print shows."""
	return [
		_line(row)
		for row in rows
		if row.get("statement") == Statement.GUV and not row.get("manual") and row.get("shown")
	]


def notes(rows: Iterable[Row], employees: Decimal, *, published_only: bool) -> list[dict[str, Any]]:
	"""The Angaben answered „ja“, each with its text and amount; the number of the Arbeitnehmer is the average of the
	document. ``published_only`` leaves out what the class does not disclose."""
	shown = []
	for row in rows:
		if row.get("answer") != "ja" or (published_only and not row.get("published")):
			continue
		if row.get("code") == EMPLOYEES_CODE:
			amount: Decimal | None = employees
		else:
			amount = to_amount(row.get("amount")) or None
		shown.append(
			{
				"code": row.get("code"),
				"label": row.get("label") or "",
				"text": row.get("text") or "",
				"amount": amount,
			}
		)
	return shown


def register_lines(values: Row, *, in_liquidation: bool) -> list[tuple[str, str]]:
	"""Firma, Sitz, Registergericht and Registernummer, and the Liquidation where it applies (§ 264 Abs. 1a HGB)."""
	lines = [
		("Firma", str(values.get("firma") or "")),
		("Sitz", str(values.get("sitz") or "")),
		("Registergericht", str(values.get("register_court") or "")),
		("Registernummer", str(values.get("register_number") or "")),
	]
	if in_liquidation:
		lines.append(("Liquidation", LIQUIDATION))
	return lines


def signature_lines(rows: Iterable[Row]) -> list[str]:
	"""Each signature as the disclosed version names it, such as „Musterstadt, 12. Mai 2027: gez. Erika Beispiel,
	Geschäftsführerin“."""
	lines = []
	for row in rows:
		who = ", ".join(part for part in (row.get("signatory_name"), row.get("function")) if part)
		day = day_of(row.get("signed_on"))
		when = ", ".join(part for part in (row.get("place") or "", day_label(day) if day else "") if part)
		lines.append(f"{when}: gez. {who}" if when else f"gez. {who}")
	return lines


def visibility(size_class: SizeClass | None, mode: Mode) -> dict[str, Any] | None:
	"""What the Unternehmensregister receives and who sees it, None for a class Steuerbote prepares no Offenlegung
	for."""
	if size_class is None or not size_class.is_small:
		return None
	disclosed = publication(size_class, mode)
	return {
		"parts": [part.value for part in disclosed.parts],
		"below_balance_sheet": disclosed.below_balance_sheet,
		"public": disclosed.public,
		"notice": PUBLISHED if disclosed.public else DEPOSITED,
		"reference": disclosed.reference,
		"deposited": mode is Mode.HINTERLEGUNG,
	}


def upload_guide(
	size_class: SizeClass | None, mode: Mode, year: int, *, first_upload: bool
) -> dict[str, Any] | None:
	"""The upload on the Publikations-Plattform step by step, with the Testplattform before the first real upload, the
	fees of the register and of the identification, and the fields of the web form, unverified; None for a class
	Steuerbote prepares no Offenlegung for."""
	if size_class is None or not size_class.is_small:
		return None
	costs = upload.costs(size_class)
	form = upload.web_form(size_class, year)
	return {
		"steps": [
			{"title": step.title, "text": step.text, "sources": [source.title for source in step.sources]}
			for step in upload.steps(size_class, mode, first_upload=first_upload)
		],
		"filing": costs.filing,
		"filing_reference": costs.filing_reference,
		"yearly": costs.yearly,
		"yearly_reference": costs.yearly_reference,
		"total": costs.total,
		"identification": [
			{"label": method.label, "fee": method.fee, "reference": method.reference}
			for method in upload.IDENTIFICATION
		],
		"web_form": {
			"fields": [{"marker": field.marker, "label": field.label} for field in form.fields],
			"text_field": form.text_field,
			"verified": form.verified,
		},
		"records": [{"label": record.label, "text": record.text} for record in upload.RECORDS],
	}

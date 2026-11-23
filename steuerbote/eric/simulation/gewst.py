"""The simulation of the Gewerbesteuererklärung, Datenart GewSt (Jahresdokumentation_E20_<Jahr>.ods): the structure
of an Erklärung with the main form GewSt1A, and the rules of the year in RULES.

Source is Jahresdokumentation_E20_2025.ods of the ERiC documentation 44.3.6.0, cited as JD, the provisional data of
EZ 2026 (steuerbote.gewst.form). RULES checks the rules of the catalogue of the EZ (steuerbote.gewst.form.CATALOGUES):
a Gewinn or Gewerbeertrag, the Betriebsstätte of lines 26 to 32, the Zuwendungen of line 92d with their receipts and
lines 15 and 17 to 19 of each Anlage BEG. CONDITIONS reads the Prüfbedingung of each as steuerbote.eric.simulation.kst
reads the Körperschaftsteuererklärung, with its messages and without the texts of the JD:
- Wahr and Falsch of a JaNeinFeld are 1 and 2;
- the rule of the receipts of line 92a to 92c holds for each of them, the rules of Anlage BEG for each Anlage;
- [E4000501->Rechtsformgruppe] is the category of the Rechtsform of line 14 (steuerbote.gewst.form.RECHTSFORMEN, KOE
  for the GmbH and the UG), with which Anlage BEG multiplies lines 15 and 19 by the share of the Körperschaften in the
  Mitunternehmerschaft (PG, line 70 or line 10 of Anlage BEG) or in the Organgesellschaft (line 71); a Körperschaft
  that is no Organgesellschaft takes them in full.
The rules apply to an EZ Steuerbote has Vordrucke for; another EZ is checked for its structure only.
"""

from collections.abc import Callable
from decimal import Decimal

from steuerbote.eric.simulation import Rule, erklaerung
from steuerbote.eric.simulation.kst import NO, YES, Condition, Documented, Erklaerung, Vordruck, rules
from steuerbote.ustva.rounding import HUNDRED, ZERO, ceil_euro, floor_euro

TITLE = "Gewerbesteuererklärung"
MAIN_FORM = "GewSt1A"

RECHTSFORM = "E4000501"
RECEIPTS = "GewSt1A/Kuerz/Zuw/Stb_Zweck/Einz"
"""Lines 92a to 92c, a context for each receipt."""
RECEIPT = ("E4009220", "E4009221", "E4009222")
"""The name of the recipient, the amount of the receipt and where the recipient sits."""
NINETY_FIVE_PERCENT = Decimal("0.95")
"""§ 8 Nummer 5 GewStG with § 8b Absatz 5 KStG, as rule 40954 writes it."""
WHOLE = Decimal("1")


def _year(year: int) -> Documented | None:
	# steuerbote.gewst.form imports steuerbote.eric, whose package imports this module through steuerbote.eric.fake.
	from steuerbote.gewst import form, years

	if year not in form.CATALOGUES:
		return None
	catalogue = form.CATALOGUES[year]
	documentation = f"Jahresdokumentation {catalogue.datenart.root} {years.YEARS[year].documentation_year}"
	return Documented(catalogue, form.RECHTSFORMEN[year], documentation)


def _partnership(e: Erklaerung) -> bool:
	"""A Mitunternehmerschaft with Körperschaften among its partners (line 70), which has not opted for § 1a KStG."""
	return (
		e.any_of(RECHTSFORM)
		and e.category(RECHTSFORM, "Rechtsformgruppe") == "PG"
		and not e.any_of("E4001405")
		and e.any_of("E4006104")
		and e.value("E4006104") > ZERO
	)


def _organgesellschaft(e: Erklaerung) -> bool:
	"""An Organgesellschaft with Körperschaften among those it belongs to (line 71)."""
	return e.any_of("E4001501") and e.any_of("E4006201") and e.value("E4006201") > ZERO


def _koerperschaft(e: Erklaerung) -> bool:
	"""A Körperschaft that is no Organgesellschaft, or a Gesellschaft that has opted for § 1a KStG (line 14a)."""
	return (
		e.any_of(RECHTSFORM)
		and e.category(RECHTSFORM, "Rechtsformgruppe") == "KOE"
		and not e.any_of("E4001501")
	) or e.any_of("E4001405")


def shares(e: Erklaerung, beg: Vordruck) -> tuple[Decimal, ...]:
	"""The shares of the Körperschaften by which each branch of rules 40954 and 40965 multiplies an Anlage BEG: of the
	Sonderbetriebsvermögen (line 10) or the Mitunternehmerschaft (line 70), of the Organgesellschaft (line 71), and the
	whole of a Körperschaft; none where no branch applies, which the conditions of 40958 and 40959 ask for as well."""
	found: list[Decimal] = []
	if _partnership(e):
		if not beg.any_of("E4051001"):
			found.append(e.value("E4006104") / HUNDRED)
		elif beg.value("E4051001") > ZERO:
			found.append(beg.value("E4051001") / HUNDRED)
	if _organgesellschaft(e):
		found.append(e.value("E4006201") / HUNDRED)
	if _koerperschaft(e):
		found.append(WHOLE)
	return tuple(found)


def _each_beg(e: Erklaerung, fails: Callable[[Vordruck], bool]) -> bool:
	return any(fails(beg) for beg in e.each("BEG"))


def _addback(beg: Vordruck, share: Decimal) -> Decimal:
	"""Line 15: 95 % of the exempt dividends of line 12, of the share of the Körperschaften."""
	return floor_euro(NINETY_FIVE_PERCENT * beg.value("E4051201") * share)


def _cut(beg: Vordruck, share: Decimal) -> Decimal:
	"""Line 19: line 16 less lines 17 and 18, of the share of the Körperschaften."""
	return ceil_euro((beg.value("E4051601") - beg.value("E4051701") - beg.value("E4051801")) * share)


CONDITIONS: tuple[Condition, ...] = (
	Condition(
		"40000",
		"E4001703",
		lambda e: (
			not e.any_of("E4001703", "E4003903", "E4004202", "E4004811")
			and not e.one(MAIN_FORM).context("GewSt1A/Einbringung_P24")
			and not e.has("OHG")
		),
	),
	Condition("40038", "E4001506", lambda e: not e.any_of("E4001506", "E4001201")),
	Condition(
		"40047",
		"E4001102",
		lambda e: e.any_of("E4001506") and e.text("E4001506") != YES and not e.any_of("E4001102", "E4001201"),
	),
	Condition(
		"40029",
		"E4001110",
		lambda e: e.any_of("E4001102") and e.text("E4001102") == NO and not e.all_of("E4001110", "E4001111"),
	),
	Condition("40051", "E4009221", lambda e: e.any_of("E4003403") and not e.any_of("E4009221")),
	Condition("40052", "E4003403", lambda e: e.any_of("E4009221") and not e.any_of("E4003403")),
	Condition(
		"40053",
		"E4003403",
		lambda e: (
			e.all_of("E4003403", "E4009221")
			and e.value("E4003403") != ceil_euro(e.one(MAIN_FORM).value("E4009221"))
		),
	),
	Condition(
		"40054",
		"E4009220",
		lambda e: any(
			0 < sum(field in receipt for field in RECEIPT) < len(RECEIPT)
			for receipt in e.one(MAIN_FORM).instances[RECEIPTS]
		),
	),
	Condition(
		"40954",
		"E4051501",
		lambda e: _each_beg(
			e,
			lambda beg: (
				beg.all_of("E4051501", "E4051201")
				and not beg.any_of("E4050701")
				and any(beg.value("E4051501") != _addback(beg, share) for share in shares(e, beg))
			),
		),
	),
	Condition(
		"40958",
		"E4051701",
		lambda e: _each_beg(
			e,
			lambda beg: (
				beg.any_of("E4051701")
				and bool(shares(e, beg))
				and beg.all_of("E4050801", "E4051601")
				and beg.value("E4051701") != min(beg.value("E4050801"), beg.value("E4051601"))
			),
		),
	),
	Condition(
		"40959",
		"E4051801",
		lambda e: _each_beg(
			e,
			lambda beg: (
				beg.any_of("E4051801")
				and bool(shares(e, beg))
				and beg.all_of("E4050901", "E4051601")
				and beg.value("E4051801")
				!= min(beg.value("E4050901"), beg.value("E4051601") - beg.value("E4051701"))
			),
		),
	),
	Condition(
		"40965",
		"E4051901",
		lambda e: _each_beg(
			e,
			lambda beg: (
				beg.all_of("E4051901", "E4051601")
				and any(beg.value("E4051901") != _cut(beg, share) for share in shares(e, beg))
			),
		),
	),
)
"""The reading of each Prüfbedingung, in the order of the catalogue."""

RULES: tuple[Rule, ...] = rules(CONDITIONS, _year)
"""The rules of the sheets „<Vordruck> - Regeln“ that the simulation checks beyond the structure."""

CHECKS = erklaerung.checks(TITLE, MAIN_FORM, RULES)

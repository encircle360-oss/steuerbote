"""Check what Steuerbote writes with a real ERiC: validation and Hinweisprüfung only, never a send.

    python -m steuerbote.eric.tests.real_validation LIB_DIR [--keep DIRECTORY]

LIB_DIR is the directory with libericapi.so and its plugins of an unpacked ERiC package for Linux x86_64, such as
ERiC-44.3.6.0/Linux-x86_64/lib. ERiC processes data only with the own Hersteller-ID of the maintainer, also for a check
(ERiC-Entwicklerhandbuch 44.3.6.0, Kap. 6.5.3): the script takes it from the environment variable
STEUERBOTE_HERSTELLER_ID and never prints or writes it. STEUERBOTE_ERIC_DOC_DIR names the unzipped ERiC documentation
and STEUERBOTE_TAXONOMY_6_9 the package of the HGB-Taxonomie 6.9, as for the tests (docs/entwicklung.md).

The script checks, each in a worker process of steuerbote.eric.worker with the flags of Prüfen and no certificate:

- the E-Bilanz of the invented GmbH of the tests (steuerbote/ebilanz/tests/test_real_taxonomy.py) as an Einheitsbilanz
  with fixed assets, without fixed assets, as a Handelsbilanz with its Überleitung, with the previous year, as an
  Eröffnungsbilanz, as a UG, with shareholders and their Steuernummern and W-IdNr., and in its founding year with the
  capital paid in as Einlagen, Datenart Bilanz_6.9;
- the Körperschaftsteuer- and the Gewerbesteuererklärung of the invented Muster IT GmbH as the documents file them
  (steuerbote/steuerbote/doctype/corporate_income_tax_return/test_bridge.py and trade_tax_return/test_bridge.py), and
  the Gewerbesteuer of a holding of 20 %, with dividends § 8b KStG exempts and with dividends it taxes. Steuerbote
  writes them for 2026 on the Vordrucke of 2025 (steuerbote/kst/years.py); as long as ERiC knows these Datenarten up
  to 2025 only, the script puts them into the namespace and the version of 2025, with the dates and the Zeitraum one
  year earlier, and checks them as KSt_30_2025 and GewSt_2025.

It prints each document with its outcome and the messages of ERiC, and ends with exit code 1 when ERiC finds an error,
2 without the Hersteller-ID, the documentation or the package.
"""

import argparse
import os
import re
import shutil
import sys
import tempfile
from dataclasses import replace
from datetime import date
from decimal import Decimal
from pathlib import Path

from lxml import etree

from steuerbote.eric import service
from steuerbote.eric.header import EnvelopeHeader, nutzdaten_datenlieferant
from steuerbote.eric.result import ERROR, Operation
from steuerbote.eric.runtime import RuntimeInfo

HERSTELLER_ID = "STEUERBOTE_HERSTELLER_ID"
ERSTELLER = nutzdaten_datenlieferant(
	name="Beispiel Werkstatt GmbH",
	street="Musterweg",
	house_number="12",
	postal_code="12345",
	city="Musterstadt",
	country="Deutschland",
)


def main(argv: list[str] | None = None) -> int:
	parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
	parser.add_argument("lib_dir", type=Path)
	parser.add_argument("--keep", type=Path, help="keep the Nutzdaten checked in this directory")
	arguments = parser.parse_args(argv)
	hersteller_id = os.environ.get(HERSTELLER_ID, "")
	if not re.fullmatch(r"\d{5}", hersteller_id):
		sys.stderr.write(f"{HERSTELLER_ID} names no Hersteller-ID of five digits.\n")
		return 2
	try:
		documents = [*ebilanzen(), *income_taxes()]
	except (RuntimeError, ImportError) as error:
		sys.stderr.write(f"{error}\n")
		return 2
	log_dir = Path(tempfile.mkdtemp(prefix="steuerbote-eric-real-"))
	try:
		runtime = RuntimeInfo("real", arguments.lib_dir, arguments.lib_dir, log_dir, hersteller_id, True)
		failed = False
		for name, datenart_version, empfaenger, xml in documents:
			if arguments.keep:
				arguments.keep.mkdir(parents=True, exist_ok=True)
				(arguments.keep / f"{name}.xml").write_text(xml, encoding="utf-8")
			header = EnvelopeHeader(
				hersteller_id=hersteller_id,
				datenlieferant="Beispiel Werkstatt GmbH",
				produkt_name="steuerbote",
				produkt_version="0.0.0",
				empfaenger=empfaenger,
				datenart_version=datenart_version,
				testmerker=None,
				nutzdaten_ticket="1",
				nutzdaten_datenlieferant=ERSTELLER if datenart_version.startswith("Bilanz") else None,
			)
			result = service.run(Operation.VALIDATE, xml, header, runtime, None, None)
			errors = [message for message in result.messages if message.severity == ERROR]
			failed = failed or bool(errors) or not result.ok
			sys.stdout.write(f"{name} ({datenart_version}): {result.outcome.value}\n")
			for message in result.messages:
				text = message.text.replace(hersteller_id, "#####")
				sys.stdout.write(f"  {message.severity} {message.code} {message.field or ''}: {text}\n")
		return 1 if failed else 0
	finally:
		shutil.rmtree(log_dir, ignore_errors=True)


def ebilanzen() -> list[tuple[str, str, str, str]]:
	"""The E-Bilanzen of the invented GmbH, each ready after the checks of Steuerbote."""
	from steuerbote.ebilanz.calculation import AccountBalance, EquityChanges
	from steuerbote.ebilanz.gcd import Gesellschafter
	from steuerbote.ebilanz.instance import Sources, build
	from steuerbote.ebilanz.positions import Case, structure
	from steuerbote.ebilanz.tests import test_real_taxonomy as invented
	from steuerbote.ebilanz.tests.test_gcd import MASTER
	from steuerbote.elster.ebilanz_xml import datenart, to_nutzdaten
	from steuerbote.steuerbote.doctype.annual_filing_settings.rules import ShareholderKind
	from steuerbote.xbrl.facts import Periods
	from steuerbote.xbrl.tests import real

	taxonomy = real.view()
	without_assets = tuple(
		replace(balance, amount=balance.amount + Decimal("42000.00"))
		if balance.account == "1800"
		else balance
		for balance in invented.BOOKS
		if ".fixAss." not in balance.concept
	)
	with_prior = Periods(date(2026, 1, 1), date(2026, 12, 31), None, date(2025, 1, 1), date(2025, 12, 31))
	prior = tuple(
		AccountBalance(balance.account, balance.description, balance.concept, balance.amount, prior=True)
		for balance in invented.BOOKS
	)
	shareholders = replace(
		MASTER,
		shareholders=(
			Gesellschafter(
				"Muster Beteiligungs GmbH",
				ShareholderKind.CORPORATION,
				Decimal("50"),
				steuernummer="5133081508159",
				wid="DE123456788-00001",
			),
			Gesellschafter(
				"Erika Beispiel",
				ShareholderKind.NATURAL_PERSON,
				Decimal("33.3333"),
				steuernummer="5230099990012",
			),
			Gesellschafter("Muster KG", ShareholderKind.PARTNERSHIP, Decimal("16.6667")),
		),
	)
	books = Sources(invented.BOOKS, assets=invented.ASSETS, equity=invented.EQUITY)
	handelsbilanz = Sources(
		invented.HANDELSBILANZ,
		assets=invented.HANDELSBILANZ_ASSETS,
		transfers=invented.TRANSFERS,
		equity=invented.EQUITY,
	)
	cases = {
		"ebilanz-gmbh-mit-anlagen": (Case("GmbH", invented.YEAR), MASTER, books),
		"ebilanz-gmbh-ohne-anlagen": (
			Case("GmbH", invented.YEAR),
			MASTER,
			Sources(without_assets, equity=invented.EQUITY),
		),
		"ebilanz-handelsbilanz": (
			Case("GmbH", invented.YEAR, accounting_standard="HGBM"),
			MASTER,
			handelsbilanz,
		),
		"ebilanz-mit-vorjahr": (
			Case("GmbH", with_prior, accounting_standard="HGBM"),
			MASTER,
			replace(handelsbilanz, balances=(*invented.HANDELSBILANZ, *prior)),
		),
		"ebilanz-eroeffnungsbilanz": (
			Case("GmbH", invented.OPENING, statement_type="EB"),
			MASTER,
			Sources(invented.OPENING_BOOKS, first_year=True),
		),
		"ebilanz-ug": (Case("UG", invented.YEAR), MASTER, books),
		"ebilanz-mit-gesellschaftern": (Case("GmbH", invented.YEAR), shareholders, books),
		"ebilanz-gruendungsjahr": (
			Case("GmbH", invented.YEAR),
			MASTER,
			Sources(
				without_assets,
				equity=EquityChanges(
					previous_equity=Decimal("0.00"), contributions=invented.EQUITY.previous_equity
				),
				first_year=True,
			),
		),
	}
	found = []
	for name, (case, master, sources) in cases.items():
		ebilanz = build(structure(taxonomy, case), master, sources)
		if not ebilanz.ready:
			raise RuntimeError(f"{name}: " + "; ".join(finding.text for finding in ebilanz.blocking))
		found.append((name, datenart(ebilanz).version, master.finanzamt, to_nutzdaten(ebilanz)))
	return found


def income_taxes() -> list[tuple[str, str, str, str]]:
	"""The Körperschaft- and Gewerbesteuererklärungen of the invented Muster IT GmbH in the Datenart of 2025."""
	from steuerbote.elster import gewst_xml, kst_xml
	from steuerbote.elster.tests.test_kst_xml import VORSATZ
	from steuerbote.eric.datenart import gewst, kst
	from steuerbote.gewst import chain
	from steuerbote.gewst.form import vordrucke
	from steuerbote.kst.holdings import Exemption, Holding, HoldingDividends, HoldingResult
	from steuerbote.kst.tests.support import FIGURES
	from steuerbote.kst.tests.test_golden import koerperschaftsteuer
	from steuerbote.steuerbote.doctype.annual_filing_settings import rules
	from steuerbote.steuerbote.doctype.corporate_income_tax_return import bridge as corporate
	from steuerbote.steuerbote.doctype.corporate_income_tax_return import test_bridge as corporate_case
	from steuerbote.steuerbote.doctype.trade_tax_return import bridge as trade
	from steuerbote.steuerbote.doctype.trade_tax_return import test_bridge as trade_case

	finanzamt = VORSATZ.steuernummer[:4]
	computed = corporate_case.compute()
	filed_kst = corporate.filed_vordrucke(
		corporate_case.RETURN, corporate_case.reported(computed.lines), corporate_case.SETTINGS
	)

	def gewerbesteuer(computation) -> tuple:
		return trade.filed_vordrucke(
			trade_case.RETURN,
			trade_case.reported(computation.lines),
			computation.holdings,
			computation.municipalities,
			corporate_case.RETURN.donations,
			trade_case.SETTINGS,
		)

	schachtel = trade_case.HoldingsTest().computed(
		rules.Holding("Beta GmbH", trade_case.YEAR, Decimal("20"), Decimal("20"))
	)
	holding = HoldingResult(
		Holding("Delta GmbH", Decimal("20"), Decimal("20")),
		Decimal("10000.00"),
		financing_costs=Decimal("1000.40"),
		other_costs=Decimal("500.00"),
	)
	taxed = HoldingDividends(holding, Exemption.TRADING_BOOK, acquisition_counts=False)
	result = koerperschaftsteuer()
	with_taxed = replace(result, p8b=replace(result.p8b, holdings=(*result.p8b.holdings, taxed)))
	gewst_1a, *begs = vordrucke(chain.compute(with_taxed, chain.GewstInputs(Decimal("400")), FIGURES))
	general = gewerbesteuer(trade_case.compute())[0]
	taken = {entry.feldkennung for entry in gewst_1a.entries}
	gewst_1a = gewst_1a.extended(*(entry for entry in general.entries if entry.feldkennung not in taken))
	documents = {
		"kst": (kst, kst_xml.nutzdaten(2026, filed_kst, VORSATZ)),
		"gewst": (gewst, gewst_xml.nutzdaten(2026, gewerbesteuer(trade_case.compute()), VORSATZ)),
		"gewst-schachtel": (gewst, gewst_xml.nutzdaten(2026, gewerbesteuer(schachtel), VORSATZ)),
		"gewst-handelsbestand": (gewst, gewst_xml.nutzdaten(2026, (gewst_1a, *begs), VORSATZ)),
	}
	return [
		(f"{name}-2025", kind(2025).version, finanzamt, in_2025(root, kind(2026), kind(2025)))
		for name, (kind, root) in documents.items()
	]


def in_2025(root: etree._Element, written, checked) -> str:
	"""The Nutzdaten of 2026 in the namespace and the version of 2025, every date and the Zeitraum a year earlier."""
	text = etree.tostring(root, encoding="unicode").replace(written.namespace, checked.namespace)
	text = text.replace(f'version="{written.root_version}"', f'version="{checked.root_version}"', 1)
	for year in (2025, 2026):
		text = re.sub(rf"(\d\d\.\d\d\.){year}\b", rf"\g<1>{year - 1}", text)
	return text.replace("<Zeitraum>2026</Zeitraum>", "<Zeitraum>2025</Zeitraum>")


if __name__ == "__main__":
	sys.exit(main())

"""XBRL für das Unternehmensregister: the file of the Offenlegung of an Annual Accounts (steuerbote/hgb/instance.py).

- The statement is built again from what the document keeps of it (bridge.statement_from_data), so that the file of
  a festgestellter Jahresabschluss carries the figures it was festgestellt with, whatever the books say later.
- The Angaben name the data of § 264 Abs. 1a HGB, the answers of the catalogue and the signatures (bridge.notes_of);
  the GCD the fiscal year with the previous one, the day of the Feststellung, which „ist anzugeben“ (§ 328 Abs. 1a
  Satz 1 HGB), the address and the founding of the company, and a changed Jahresabschluss where the document amends
  one that went to the register (bridge.master_data). The class discloses what steuerbote.hgb.disclosure.publication
  says for its mode.
- The view of the class of the installed HGB-Taxonomie writes it (instance.write): the view for
  Kleinstkapitalgesellschaften for a Kleinst, the commercial one for a small company (steuerbote.xbrl.profiles
  .DISCLOSURE). The file carries no day it was written, so the same Jahresabschluss gives the same bytes.
"""

from decimal import Decimal

from frappe.model.document import Document
from frappe.utils import cint, flt, getdate

from steuerbote import annual_accounts_sources
from steuerbote.hgb import instance
from steuerbote.hgb.disclosure import Mode, publication
from steuerbote.hgb.size import SizeClass
from steuerbote.steuerbote.doctype.annual_accounts import bridge
from steuerbote.steuerbote.doctype.eric_settings import eric_settings


def offenlegung(doc: Document, size_class: SizeClass, mode: Mode) -> bytes:
	"""The file of the Offenlegung of the Jahresabschluss as stored; instance.HeldBackError names what holds it back."""
	built = instance.build(
		bridge.statement_from_data(doc.statement_data, cint(doc.year), size_class),
		size_class,
		notes(doc),
		publication(size_class, mode),
		master_data(doc),
	)
	return instance.write(built, eric_settings.taxonomy_view(built.version.version, built.view))


def notes(doc: Document) -> instance.Notes:
	"""The register data, the answers of the Angaben and the signatures of the document."""
	register = bridge.register_of(doc.as_dict(), in_liquidation=bool(cint(doc.in_liquidation)))
	answers = bridge.answers_of([row.as_dict() for row in doc.notes], Decimal(str(flt(doc.employees))))
	return bridge.notes_of(
		register, answers, bridge.signatures_of([row.as_dict() for row in doc.signatories])
	)


def master_data(doc: Document) -> instance.MasterData:
	settings = annual_accounts_sources.settings(doc.company)
	has_prior = bool(cint(doc.has_prior))
	periods = bridge.periods_of(
		getdate(doc.from_date),
		getdate(doc.to_date),
		bridge.day_of(doc.prior_from_date) if has_prior else None,
		bridge.day_of(doc.prior_to_date) if has_prior else None,
	)
	return bridge.master_data(
		periods,
		bridge.day_of(doc.adopted_on),
		bridge.address_of(settings.get_address()),
		founded_on=annual_accounts_sources.founded_on(doc.company),
		generated_on=None,
		changed=doc.amends_transmitted(),
	)


def file_name(doc: Document) -> str:
	return f"Offenlegung-{doc.name}.xbrl"

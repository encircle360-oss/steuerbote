"""The step „Konten der Wechselkursdifferenzen“ of Steuerbote einrichten (hook steuerbote_setup_steps).

ERPNext books the differences of exchange rates onto two accounts of the company: the realised ones of a payment in
another currency onto „Exchange Gain / Loss Account“ (exchange_gain_loss_account) and those of the Wechselkurs-
neubewertung at a Stichtag onto „Unrealized Exchange Gain/Loss Account“ (unrealized_exchange_gain_loss_account),
gains and losses each onto the one account. Its German templates set neither, so the first payment in another currency
fails until someone chooses them. The step proposes the accounts of the currency translation of the chart: for the
Stichtag the account of § 256a HGB, SKR03 2150 and SKR04 6880 „Aufwendungen aus der Währungsumrechnung“, for the
realised differences SKR03 2151 and SKR04 6881 „Aufwendungen aus der Währungsumrechnung (nicht § 256a HGB)“. The
Bilanzzuordnung takes a balance on the other side to the Erträge aus der Währungsumrechnung, and the hint
BILANZ-WAEHRUNG-SALDIERT names an account that books both in a year, since § 277 Abs. 5 Satz 2 HGB shows them apart.

The status changes nothing; the action, which only a System Manager runs, sets the accounts the company has not chosen.
"""

import frappe
from frappe import _

from steuerbote.setup.steps import Action, Note, Outcome, StepResult

FIELDS = ("exchange_gain_loss_account", "unrealized_exchange_gain_loss_account")
ACCOUNTS = {
	"SKR03": {"exchange_gain_loss_account": "2151", "unrealized_exchange_gain_loss_account": "2150"},
	"SKR04": {"exchange_gain_loss_account": "6881", "unrealized_exchange_gain_loss_account": "6880"},
}
"""The account of each field by chart: the realised differences, then the Stichtag of § 256a HGB."""
MANAGER = "System Manager"

CHOSEN = "{0} books the differences of exchange rates on its accounts {1} (realised) and {2} (Wechselkursneubewertung)."
PROPOSED = "ERPNext books the differences of exchange rates of {0} onto two accounts of the company, which are not chosen yet: the realised ones of payments onto {1} „Aufwendungen aus der Währungsumrechnung (nicht § 256a HGB)“ and those of the Wechselkursneubewertung at a Stichtag (§ 256a HGB) onto {2} „Aufwendungen aus der Währungsumrechnung“. Gains go there as well; the Bilanzzuordnung shows a balance on the other side as Erträge aus der Währungsumrechnung, and a year with both asks to book the gains onto the account of the Erträge before the Jahresabschluss (§ 277 Abs. 5 Satz 2 HGB)."
MISSING = "{0} lacks the accounts {1} its chart proposes for the differences of exchange rates: create them, or choose the Exchange Gain / Loss Account and the Unrealized Exchange Gain/Loss Account of the company yourself."
OWN_CHART = "{0} books in a chart of its own: choose the Exchange Gain / Loss Account and the Unrealized Exchange Gain/Loss Account of the company for the realised differences of exchange rates and for those of the Wechselkursneubewertung."
SET_ACCOUNTS = "Set the Exchange Rate Accounts"
MESSAGES = (CHOSEN, PROPOSED, MISSING, OWN_CHART, SET_ACCOUNTS)


def check(context) -> StepResult:
	"""The step exchange_accounts: done when the company has both accounts; otherwise it proposes those of its chart
	and offers to set them, or says what it lacks."""
	company = context.company
	chosen = frappe.db.get_value("Company", company, list(FIELDS), as_dict=True)
	document = ("Company", company)
	if all(chosen.get(field) for field in FIELDS):
		numbers = [_number(chosen[field]) for field in FIELDS]
		return StepResult(Outcome.SKIPPED, (Note(CHOSEN, (company, *numbers)),), document)
	proposed = ACCOUNTS.get(context.chart.chart or "")
	if proposed is None:
		return StepResult(Outcome.UNDECIDED, (Note(OWN_CHART, (company,), open=True),), document)
	found = _accounts(company, proposed)
	missing = [proposed[field] for field in FIELDS if not chosen.get(field) and field not in found]
	if missing:
		return StepResult(
			Outcome.UNDECIDED, (Note(MISSING, (company, ", ".join(missing)), open=True),), document
		)
	numbers = tuple(proposed[field] for field in FIELDS)
	return StepResult(
		Outcome.UNDECIDED,
		(Note(PROPOSED, (company, *numbers), open=True),),
		document,
		Action(SET_ACCOUNTS, f"{__name__}.set_exchange_accounts"),
	)


@frappe.whitelist(methods=["POST"])
def set_exchange_accounts(company: str | None = None) -> None:
	"""The action of exchange_accounts: give each exchange account of the company it has not chosen the account of its
	chart, or, for a company whose chart Steuerbote cannot tell, of the chart whose two accounts the company has."""
	frappe.only_for(MANAGER, message=True)
	if not company or not frappe.db.exists("Company", company):
		frappe.throw(_("There is no company {0}.").format(company or ""))
	from steuerbote.steuerbote.setup import company_chart

	chart = company_chart(company).chart
	candidates = [ACCOUNTS[chart]] if chart in ACCOUNTS else list(ACCOUNTS.values())
	chosen = frappe.db.get_value("Company", company, list(FIELDS), as_dict=True)
	found = next(
		(
			accounts
			for accounts in (_accounts(company, proposed) for proposed in candidates)
			if len(accounts) == len(FIELDS)
		),
		{},
	)
	frappe.db.set_value(
		"Company",
		company,
		{field: found[field] for field in FIELDS if not chosen.get(field) and field in found},
	)


def _accounts(company: str, proposed: dict[str, str]) -> dict[str, str]:
	"""The ledger accounts of the company with the numbers proposed, by field."""
	found = {}
	for field, number in proposed.items():
		name = frappe.db.get_value("Account", {"company": company, "account_number": number, "is_group": 0})
		if name:
			found[field] = name
	return found


def _number(account: str) -> str:
	return frappe.db.get_value("Account", account, "account_number") or account

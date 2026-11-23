"""The upload of the Jahresabschluss to the Unternehmensregister, step by step, as data with its sources.

Steuerbote writes the XBRL file (steuerbote.hgb.instance) and does not transmit it. The register offers its
Massenschnittstelle for Jahresabschlüsse in XML or XBRL only on request, „Bei Interesse wenden Sie sich bitte an
webservice@bundesanzeiger.de“ (Publikations-Plattform, „Technische Standards - Schnittstellen“), and every person who
transmits identifies herself (§ 3a Abs. 1 URV). So a person uploads the file on www.publikations-plattform.de, and
the Annual Accounts keep what the register answers. The steps, the identification with its fees, the fees of the
register, what to record afterwards and the field list of the web form stand here as data, each with its source, so
that the print format of the Annual Accounts and docs/offenlegung.md show the same. The texts are German, as both
show them.

The steps (steps()):

- **Testplattform**, before the first real upload: „Der Bundesanzeiger Verlag bietet eine Testplattform für die
  Übermittlung von XBRL-Dateien an. Hier können Sie die Kompatibilität Ihrer XBRL-Dateien unabhängig von der
  regulären Auftragsübermittlung überprüfen.“ (Publikations-Plattform, „Arbeitshilfen - XBRL-Programm“)
- **Registrieren**, once: „Eine einmalige Registrierung genügt.“ For an upload to the register it names „Firma oder
  Name des Unternehmens, Registergericht, Registerart, Registernummer“ (§ 3 Abs. 2 URV).
- **Identifizieren**, once per person before the transmission (§ 3a Abs. 1 URV; Publikations-Plattform,
  „Registrieren / Identifizieren“), with the fees of Nr. 1441 KV JVKostG (IDENTIFICATION).
- **Auftrag**, and for a Kleinst that deposits the box that makes the Mitteilung of § 326 Abs. 2 Satz 2 HGB: „Mit dem
  Setzen des Hakens kommen Sie Ihrer gesetzlichen Mitteilungspflicht ... nach.“ (Fragen und Antworten,
  „Übermittlung von Jahresabschlüssen“; the answer still cites it as Satz 3)
- **Hochladen**: „Sie können nur eine Datei pro Auftrag übermitteln.“ (Fragen und Antworten, „Aufträge an das
  Unternehmensregister“), in XML (§ 11 Abs. 2 Satz 1 Nr. 4 URV).
- **Auftragsbestätigung** and **Beleg** under „Meine Daten“, „Aufträge & Abrufe“, recorded in the Annual Accounts
  (RECORDS); the day of the transmission keeps the deadline (§ 325 Abs. 4 Satz 2 HGB).

The fees of the register are those of steuerbote.hgb.disclosure (filing_fees()). Whether the register adds
Umsatzsteuer to them is unverified; the Konvertierungsentgelt for another format than XML is an Entgelt of the
operator (§ 15 Abs. 1 Satz 2 URV) and does not arise for the XBRL file. The names of the fields of the web form are
unverified: the form needs a login (web_form()).

Pages of the Publikations-Plattform, the URV and the Kostenverzeichnis of the JVKostG as read on 23 November 2026
(READ_ON). This module is pure Python and never imports Frappe.
"""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from enum import Enum, StrEnum

from steuerbote.hgb.disclosure import DisclosureError, Mode, filing_fees, publication
from steuerbote.hgb.schemes import balance_sheet_scheme
from steuerbote.hgb.size import SizeClass

READ_ON = date(2026, 11, 23)
"""The day the pages of the platform, the URV and the JVKostG were read."""
PLATFORM = "https://www.publikations-plattform.de"
TEST_PLATFORM_ADDRESS = "testplattform@rt.bundesanzeiger.de"
FILES_PER_ORDER = 1
"""„Sie können nur eine Datei pro Auftrag übermitteln.“"""


@dataclass(frozen=True, slots=True)
class Source:
	title: str
	url: str


GUIDE = Source(
	"Publikations-Plattform, So geht's: Jahresabschluss Veröffentlichung",
	f"{PLATFORM}/order/de/wissenswertes/sogehts/javeroeffentlichung",
)
DEPOSIT_GUIDE = Source(
	"Publikations-Plattform, So geht's: Jahresabschluss Hinterlegung",
	f"{PLATFORM}/order/de/wissenswertes/sogehts/jahinterlegung",
)
REGISTRATION_GUIDE = Source(
	"Publikations-Plattform, So geht's: Registrieren / Identifizieren",
	f"{PLATFORM}/order/de/wissenswertes/sogehts/registrierenidentifizeren",
)
ORDERS_FAQ = Source(
	"Publikations-Plattform, Fragen und Antworten: Aufträge an das Unternehmensregister",
	f"{PLATFORM}/order/de/faq/auftraegeureg",
)
ACCOUNTS_FAQ = Source(
	"Publikations-Plattform, Fragen und Antworten: Übermittlung von Jahresabschlüssen",
	f"{PLATFORM}/order/de/faq/uebermittlung",
)
XBRL_TOOLS = Source(
	"Publikations-Plattform, Arbeitshilfen: XBRL-Programm, Testplattform",
	f"{PLATFORM}/order/de/arbeitshilfenstandards/arbeitshilfen/xbrlprogramm",
)
URV = Source("Unternehmensregisterverordnung, §§ 3, 3a und 11", "https://www.gesetze-im-internet.de/urv/")
JVKOSTG = Source(
	"Justizverwaltungskostengesetz, Anlage 1 (Kostenverzeichnis), Hauptabschnitt 4",
	"https://www.gesetze-im-internet.de/jvkostg/anlage.html",
)
HGB_325 = Source("§ 325 HGB", "https://www.gesetze-im-internet.de/hgb/__325.html")
HGB_326 = Source("§ 326 HGB", "https://www.gesetze-im-internet.de/hgb/__326.html")


class Identification(Enum):
	EID = "Online-Ausweisfunktion"
	VIDEO = "Videoidentifizierung"
	TAX_ADVISOR_PLATFORM = "Steuerberaterplattform"


@dataclass(frozen=True, slots=True)
class IdentificationMethod:
	"""A way to identify for the register, with what it costs once (Nr. 1441 KV JVKostG)."""

	method: Identification
	label: str
	fee: Decimal
	reference: str


IDENTIFICATION: tuple[IdentificationMethod, ...] = (
	IdentificationMethod(
		Identification.EID,
		"Online-Ausweisfunktion des Personalausweises, der eID-Karte oder des Aufenthaltstitels, oder ein "
		"elektronisches Identifizierungsmittel eines anderen Mitgliedstaats",
		Decimal("12.00"),
		"Nr. 1441 Buchst. a KV JVKostG; § 3a Abs. 1 Satz 3 Nr. 1 und 2 URV",
	),
	IdentificationMethod(
		Identification.VIDEO,
		"Videoidentifizierung der registerführenden Stelle, automatisch oder begleitet",
		Decimal("22.00"),
		"Nr. 1441 Buchst. b KV JVKostG; § 3a Abs. 1 Satz 3 Nr. 3 URV",
	),
	IdentificationMethod(
		Identification.TAX_ADVISOR_PLATFORM,
		"Identifizierung über die Steuerberaterplattform",
		Decimal("7.60"),
		"Nr. 1441 Buchst. c KV JVKostG; § 3a Abs. 4 URV",
	),
)


def identification(method: Identification) -> IdentificationMethod:
	return next(entry for entry in IDENTIFICATION if entry.method is method)


def _euro(amount: Decimal) -> str:
	return f"{amount:.2f} €".replace(".", ",")


class StepKey(StrEnum):
	TEST_PLATFORM = "testplattform"
	REGISTER = "registrieren"
	IDENTIFY = "identifizieren"
	ORDER = "auftrag"
	DEPOSIT = "hinterlegung"
	UPLOAD = "hochladen"
	CONFIRMATION = "auftragsbestaetigung"
	RECEIPT = "beleg"


@dataclass(frozen=True, slots=True)
class Step:
	key: StepKey
	title: str
	text: str
	sources: tuple[Source, ...]


_METHODS = ", ".join(f"{entry.method.value} {_euro(entry.fee)}" for entry in IDENTIFICATION)

STEPS: tuple[Step, ...] = (
	Step(
		StepKey.TEST_PLATFORM,
		"Testplattform",
		"Vor dem ersten echten Upload die XBRL-Datei auf der Testplattform des Bundesanzeiger Verlags hochladen; sie "
		"prüft die Kompatibilität einer XBRL-Datei unabhängig von der regulären Auftragsübermittlung. Den Zugang gibt "
		f"es auf Anfrage an {TEST_PLATFORM_ADDRESS}.",
		(XBRL_TOOLS,),
	),
	Step(
		StepKey.REGISTER,
		"Registrieren",
		"Auf www.publikations-plattform.de einmal registrieren, für die Gesellschaft selbst oder als Einsender für "
		"Dritte, etwa die Steuerberatung. Für Übermittlungen an das Unternehmensregister nennt die Registrierung "
		"Firma, Registergericht, Registerart und Registernummer der Gesellschaft (§ 3 Abs. 2 URV).",
		(GUIDE, REGISTRATION_GUIDE, URV),
	),
	Step(
		StepKey.IDENTIFY,
		"Identifizieren",
		"Vor der ersten Übermittlung identifiziert sich jede Person, die hochlädt, einmal elektronisch "
		f"(§ 3a Abs. 1 URV): {_METHODS}. Nach einer Namensänderung identifiziert sie sich neu. Ohne Identifizierung "
		"lässt sich kein Jahresabschluss an das Unternehmensregister übermitteln.",
		(REGISTRATION_GUIDE, URV, JVKOSTG),
	),
	Step(
		StepKey.ORDER,
		"Auftrag anlegen",
		"Angemeldet unter „Auftragsübermittlung“ einen Auftrag an das Unternehmensregister für den Jahresabschluss des "
		"Geschäftsjahres anlegen.",
		(GUIDE,),
	),
	Step(
		StepKey.DEPOSIT,
		"Hinterlegung wählen",
		"Im Auftrag den Haken setzen, dass die Gesellschaft die Voraussetzungen einer Kleinstkapitalgesellschaft für "
		"die Hinterlegung erfüllt. Der Haken ist die Mitteilung nach § 326 Abs. 2 Satz 2 HGB; ohne ihn ist der Auftrag "
		"keine Hinterlegung.",
		(ACCOUNTS_FAQ, DEPOSIT_GUIDE, HGB_326),
	),
	Step(
		StepKey.UPLOAD,
		"XBRL-Datei hochladen",
		"Die XBRL-Datei von Steuerbote auf der Upload-Seite des Auftrags hochladen, eine Datei je Auftrag. XML ist das "
		"Format der Übermittlung (§ 11 Abs. 2 Satz 1 Nr. 4 URV); für Word, RTF, Excel oder PDF fällt neben der Gebühr "
		"ein Konvertierungsentgelt an.",
		(ORDERS_FAQ, GUIDE, URV),
	),
	Step(
		StepKey.CONFIRMATION,
		"Auftragsbestätigung ablegen",
		"Der abgeschlossene Auftrag steht unter „Meine Daten“, „Aufträge & Abrufe“ mit seinem Status; über „Ansehen“ "
		"lässt sich die Auftragsbestätigung ausdrucken. Auftragsnummer, Tag der Übermittlung und Auftragsbestätigung "
		"im Jahresabschluss festhalten: Der Tag der Übermittlung wahrt die Frist (§ 325 Abs. 4 Satz 2 HGB).",
		(ORDERS_FAQ, HGB_325),
	),
	Step(
		StepKey.RECEIPT,
		"Beleg ablegen",
		"Nach der Einstellung in das Unternehmensregister steht unter „Meine Daten“, „Aufträge & Abrufe“ ein PDF-Beleg "
		"bereit. Ihn und den Tag der Einstellung im Jahresabschluss festhalten.",
		(ORDERS_FAQ,),
	),
)


def _prepared(size_class: SizeClass, mode: Mode) -> None:
	if not publication(size_class, mode).prepared:
		raise DisclosureError(
			f"Steuerbote prepares the upload of Kleinst and klein only, not of a {size_class.value}"
		)


def steps(size_class: SizeClass, mode: Mode, *, first_upload: bool) -> tuple[Step, ...]:
	"""The steps of one upload in their order: the Testplattform first before the first real upload, the box of the
	Hinterlegung only for a Kleinst that deposits."""
	_prepared(size_class, mode)
	left_out = set()
	if not first_upload:
		left_out.add(StepKey.TEST_PLATFORM)
	if mode is not Mode.HINTERLEGUNG:
		left_out.add(StepKey.DEPOSIT)
	return tuple(step for step in STEPS if step.key not in left_out)


@dataclass(frozen=True, slots=True)
class Costs:
	"""What the register charges for one Jahresabschluss: the Einstellung, the fee of the year and, for a person who
	identifies for it, the identification."""

	filing: Decimal
	filing_reference: str
	yearly: Decimal
	yearly_reference: str
	identification: IdentificationMethod | None = None

	@property
	def total(self) -> Decimal:
		once = Decimal("0") if self.identification is None else self.identification.fee
		return self.filing + self.yearly + once


def costs(size_class: SizeClass, method: Identification | None = None) -> Costs:
	"""The fees of the Einstellung and of the year (Nr. 1420, 1421 and 1410 KV JVKostG), with the identification of
	``method`` for a first upload."""
	fees = filing_fees(size_class)
	return Costs(
		fees.filing,
		fees.filing_reference,
		fees.yearly,
		fees.yearly_reference,
		None if method is None else identification(method),
	)


@dataclass(frozen=True, slots=True)
class Record:
	"""What the Annual Accounts hold of an upload: their field, its label, when and where it shows, and its source."""

	field: str
	label: str
	text: str
	source: Source


RECORDS: tuple[Record, ...] = (
	Record(
		"transmitted_on",
		"Übermittelt am",
		"der Tag des Uploads; er wahrt die Frist, wenn der Jahresabschluss festgestellt ist",
		HGB_325,
	),
	Record("transmitted_by", "Übermittelt von", "die identifizierte Person, die hochgeladen hat", URV),
	Record(
		"order_number",
		"Auftragsnummer",
		"unter „Meine Daten“, „Aufträge & Abrufe“ und auf dem Beleg; eine Berichtigung oder Ergänzung nennt sie mit "
		"dem Tag der Veröffentlichung oder Hinterlegung",
		ACCOUNTS_FAQ,
	),
	Record(
		"confirmation_file",
		"Auftragsbestätigung",
		"über „Ansehen“ unter „Aufträge & Abrufe“ ausgedruckt und als PDF abgelegt",
		ORDERS_FAQ,
	),
	Record(
		"published_on", "Eingestellt am", "der Tag der Einstellung in das Unternehmensregister", ORDERS_FAQ
	),
	Record(
		"receipt_file", "Beleg", "der PDF-Beleg unter „Aufträge & Abrufe“ nach der Einstellung", ORDERS_FAQ
	),
	Record("fees", "Gebühren", "die Gebühren der Rechnung des Registers", JVKOSTG),
)


@dataclass(frozen=True, slots=True)
class FormField:
	marker: str
	label: str
	concept: str


@dataclass(frozen=True, slots=True)
class WebForm:
	"""The web form for small companies: a field for each position of the balance sheet and one for the text."""

	fields: tuple[FormField, ...]
	text_field: str
	verified: bool
	source: Source


def web_form(size_class: SizeClass, year: int) -> WebForm:
	"""The fields of the web form as Steuerbote expects them: the positions of the balance sheet of the class and one
	text field, the Anhang of klein or the Angaben under the balance sheet of a Kleinst. Unverified: the form needs a
	login."""
	if not size_class.is_small:
		raise DisclosureError(f"the web form is for small companies, not for a {size_class.value}")
	scheme = balance_sheet_scheme(year)
	return WebForm(
		tuple(
			FormField(position.marker, position.label, position.concept)
			for position in scheme.visible(size_class)
		),
		"Angaben unter der Bilanz" if size_class is SizeClass.KLEINST else "Anhang",
		verified=False,
		source=GUIDE,
	)

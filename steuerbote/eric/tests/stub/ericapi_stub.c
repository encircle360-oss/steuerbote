/*
 * A stand-in for libericapi.so, for the tests of steuerbote.eric.api and the worker.
 *
 * It exports the functions of the ERiC single-threading API that steuerbote binds, with the
 * signatures and structure layouts of the ERiC 44 API reference, and answers with canned buffers.
 * Markers in the XML passed to EricBearbeiteVorgang select error codes, a long sleep or a crash. As in
 * ERiC, a send fills the server answer before it prints, so an error of printing follows an accepted
 * transfer.
 * Every call records what it received and stub_recorded() reads it back, so the tests check what the
 * binding really passed through ctypes, including the versions and fields of the parameter structures.
 */
#define _POSIX_C_SOURCE 200809L

#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

#define EXPORT __attribute__((visibility("default")))

enum {
	OK = 0,
	GLOBAL_PRUEF_FEHLER = 610001002,
	GLOBAL_HINWEISE = 610001003,
	GLOBAL_STEUERNUMMER_UNGUELTIG = 610001034,
	GLOBAL_FEHLERMELDUNG_NICHT_VORHANDEN = 610001007,
	GLOBAL_VERSCHLUESSELUNGS_PARAMETER_NICHT_ERLAUBT = 610001027,
	GLOBAL_DATENARTVERSION_UNBEKANNT = 610001042,
	GLOBAL_UNGUELTIGE_FLAG_KOMBINATION = 610001218,
	GLOBAL_NICHT_INITIALISIERT = 610001081,
	GLOBAL_MEHRFACHE_INITIALISIERUNG = 610001082,
	GLOBAL_FEHLER_INITIALISIERUNG = 610001083,
	GLOBAL_VERSCHLUESSELUNGS_PARAMETER_NICHT_ANGEGEBEN = 610001206,
	GLOBAL_UNGUELTIGER_PARAMETER = 610001222,
	GLOBAL_UNGUELTIGE_PARAMETER_VERSION = 610001226,
	GLOBAL_NULL_PARAMETER = 610001526,
	GLOBAL_EINSTELLUNG_NAME_UNGUELTIG = 610001860,
	GLOBAL_EINSTELLUNG_WERT_UNGUELTIG = 610001861,
	TRANSFER_ERR_XML_THEADER = 610101210,
	TRANSFER_ERR_CONNECTSERVER = 610101278,
	TRANSFER_ERR_NORESPONSE = 610101279,
	TRANSFER_ERR_TIMEOUT = 610101283,
	TRANSFER_ERR_XML_NHEADER = 610101292,
	CRYPT_E_INVALID_HANDLE = 610201101,
	CRYPT_E_PIN_WRONG = 610201106,
	CRYPT_NICHT_UNTERSTUETZTES_PSE_FORMAT = 610201203,
	IO_PARSE_FEHLER = 610301006,
	IO_READER_FALSCHES_ENCODING = 610301108,
	IO_READER_SCHEMA_VALIDIERUNGSFEHLER = 610301200,
	IO_TESTHERSTELLERID_GESPERRT = 610301202,
	PRINT_UNGUELTIGER_DATEI_PFAD = 610501004,
	PRINT_ABBRUCH_GENERIERUNG = 610501010,
	PRINT_FUSSTEXT_ZU_LANG = 610501012,
	PRINT_PDFCALLBACK = 610501015,
};

enum {
	VALIDIERE = 1 << 1,
	SENDE = 1 << 2,
	DRUCKE = 1 << 5,
	PRUEFE_HINWEISE = 1 << 7,
};

/* The documented layouts: eric_druck_parameter_t version 4, eric_verschluesselungs_parameter_t version 3. */
typedef int (*pdf_callback)(const char *name, const uint8_t *data, uint32_t size, void *user_data);

struct print_parameters {
	uint32_t version;
	uint32_t vorschau;
	uint32_t duplexDruck;
	const char *pdfName;
	const char *fussText;
	pdf_callback pdfCallback;
	void *pdfCallbackBenutzerdaten;
};

struct encryption_parameters {
	uint32_t version;
	uint32_t zertifikatHandle;
	const char *pin;
};

/* The API hands out pointers to this structure only; its fields are the stub's own. */
struct EricReturnBufferApi {
	char *data;
	uint32_t length;
};

#define MAX_RECORDS 64
#define MAX_CERTIFICATES 8
#define FIRST_HANDLE 4711
#define MAX_FUSSTEXT 29
#define WRONG_PIN "falsch-123"

static struct {
	char *key;
	char *value;
} records[MAX_RECORDS];

static int initialised;
static int live_buffers;
/* Buffers created successfully before the next one fails; -1 never fails. */
static int buffers_before_failure = -1;
static uint32_t open_handles[MAX_CERTIFICATES];
static int open_certificates;
static uint32_t next_handle = FIRST_HANDLE;
static char certificate_pin[256];

static const char canned_pdf[] = "%PDF-1.4\n%\xe2\xe3\xcf\xd3\n1 0 obj\n<< /Stub true >>\nendobj\n"
				 "stream\n\0\1\2 binary \0 data\nendstream\n%%EOF\n";

static void record(const char *key, const char *value)
{
	int slot = -1;
	for (int i = 0; i < MAX_RECORDS; i++) {
		if (records[i].key && strcmp(records[i].key, key) == 0) {
			slot = i;
			break;
		}
		if (!records[i].key && slot < 0)
			slot = i;
	}
	if (slot < 0)
		abort();
	if (!records[slot].key)
		records[slot].key = strdup(key);
	free(records[slot].value);
	records[slot].value = strdup(value ? value : "<NULL>");
}

/*
 * Internal calls go to static functions only: the tests load several copies of the stub into one
 * process, and a call to an exported function could bind to the copy that was loaded first.
 */
static const char *recorded(const char *key)
{
	for (int i = 0; i < MAX_RECORDS; i++)
		if (records[i].key && strcmp(records[i].key, key) == 0)
			return records[i].value;
	return NULL;
}

static uint32_t pdf_size(void)
{
	return (uint32_t)(sizeof canned_pdf - 1);
}

static void record_number(const char *key, long long value)
{
	char text[32];
	snprintf(text, sizeof text, "%lld", value);
	record(key, text);
}

static int contains(const char *text, const char *marker)
{
	return text && strstr(text, marker) != NULL;
}

static void fill(struct EricReturnBufferApi *buffer, const char *data, uint32_t length)
{
	free(buffer->data);
	buffer->data = malloc(length + 1);
	memcpy(buffer->data, data, length);
	buffer->data[length] = '\0';
	buffer->length = length;
}

static void fill_text(struct EricReturnBufferApi *buffer, const char *text)
{
	fill(buffer, text, (uint32_t)strlen(text));
}

/* Copies the text between the first open tag after start and its close tag into out, if both are found. */
static const char *between(const char *start, const char *open, const char *close, char *out, size_t size)
{
	const char *from = start ? strstr(start, open) : NULL;
	if (!from)
		return NULL;
	from += strlen(open);
	const char *to = strstr(from, close);
	if (!to)
		return NULL;
	size_t length = (size_t)(to - from);
	if (length >= size)
		length = size - 1;
	memcpy(out, from, length);
	out[length] = '\0';
	return to + strlen(close);
}

static int is_digits(const char *text)
{
	if (!text || !*text)
		return 0;
	for (; *text; text++)
		if (*text < '0' || *text > '9')
			return 0;
	return 1;
}

static int is_open_handle(uint32_t handle)
{
	for (int i = 0; i < open_certificates; i++)
		if (open_handles[i] == handle)
			return 1;
	return 0;
}

/* True if the start tag that begins at tag carries an attribute, which includes a namespace definition. */
static int has_attribute(const char *tag)
{
	const char *end = tag ? strchr(tag, '>') : NULL;
	return end && memchr(tag, '=', (size_t)(end - tag)) != NULL;
}

EXPORT void stub_reset(void)
{
	for (int i = 0; i < MAX_RECORDS; i++) {
		free(records[i].key);
		free(records[i].value);
		records[i].key = NULL;
		records[i].value = NULL;
	}
	initialised = 0;
	buffers_before_failure = -1;
	open_certificates = 0;
	next_handle = FIRST_HANDLE;
	memset(certificate_pin, 0, sizeof certificate_pin);
}

EXPORT const char *stub_recorded(const char *key)
{
	return recorded(key);
}

EXPORT void stub_fail_buffer_after(int successful)
{
	buffers_before_failure = successful;
}

EXPORT int stub_live_buffers(void)
{
	return live_buffers;
}

EXPORT int stub_open_certificates(void)
{
	return open_certificates;
}

EXPORT int stub_initialised(void)
{
	return initialised;
}

EXPORT uint32_t stub_pdf_size(void)
{
	return pdf_size();
}

EXPORT struct EricReturnBufferApi *EricRueckgabepufferErzeugen(void)
{
	if (buffers_before_failure == 0) {
		buffers_before_failure = -1;
		return NULL;
	}
	if (buffers_before_failure > 0)
		buffers_before_failure--;
	struct EricReturnBufferApi *buffer = calloc(1, sizeof *buffer);
	buffer->data = calloc(1, 1);
	live_buffers++;
	return buffer;
}

EXPORT int EricRueckgabepufferFreigeben(struct EricReturnBufferApi *buffer)
{
	if (!buffer)
		return GLOBAL_UNGUELTIGER_PARAMETER;
	free(buffer->data);
	free(buffer);
	live_buffers--;
	return OK;
}

EXPORT const char *EricRueckgabepufferInhalt(struct EricReturnBufferApi *buffer)
{
	return buffer ? buffer->data : NULL;
}

EXPORT uint32_t EricRueckgabepufferLaenge(struct EricReturnBufferApi *buffer)
{
	return buffer ? buffer->length : 0;
}

EXPORT int EricInitialisiere(const char *pluginPfad, const char *logPfad)
{
	if (initialised)
		return GLOBAL_MEHRFACHE_INITIALISIERUNG;
	record("plugin_path", pluginPfad);
	record("log_path", logPfad);
	if (logPfad) {
		/* ERiC 44.3.6.0 refuses to start when it cannot create eric.log, as in a directory that does not exist. */
		char path[4096];
		snprintf(path, sizeof path, "%s/eric.log", logPfad);
		FILE *log = fopen(path, "a");
		if (!log)
			return GLOBAL_FEHLER_INITIALISIERUNG;
		fputs("stub: EricInitialisiere\n", log);
		fclose(log);
	}
	initialised = 1;
	return OK;
}

EXPORT int EricBeende(void)
{
	const char *count = recorded("finished");
	record_number("finished", (count ? atoll(count) : 0) + 1);
	initialised = 0;
	return OK;
}

EXPORT int EricEinstellungSetzen(const char *name, const char *wert)
{
	static const char *numeric[] = {"transfer.connect_timeout", "transfer.response_timeout",
					"validieren.fehler_max", "validieren.hinweise_max", "http.proxy_port"};
	static const char *textual[] = {"log.detailed", "http.proxy_host", "http.proxy_username",
					"http.proxy_password", "http.proxy_auth"};
	if (!initialised)
		return GLOBAL_NICHT_INITIALISIERT;
	if (!name || !wert)
		return GLOBAL_NULL_PARAMETER;
	int known = 0;
	for (size_t i = 0; i < sizeof numeric / sizeof *numeric; i++)
		if (strcmp(name, numeric[i]) == 0) {
			if (!is_digits(wert))
				return GLOBAL_EINSTELLUNG_WERT_UNGUELTIG;
			known = 1;
		}
	for (size_t i = 0; i < sizeof textual / sizeof *textual; i++)
		if (strcmp(name, textual[i]) == 0)
			known = 1;
	if (!known)
		return GLOBAL_EINSTELLUNG_NAME_UNGUELTIG;
	char key[128];
	snprintf(key, sizeof key, "setting:%s", name);
	record(key, wert);
	return OK;
}

EXPORT int EricHoleFehlerText(int fehlerkode, struct EricReturnBufferApi *rueckgabePuffer)
{
	const char *text = NULL;
	switch (fehlerkode) {
	case GLOBAL_PRUEF_FEHLER:
		text = "Fehler während der Plausibilitätsprüfung, Datensatz nicht plausibel.";
		break;
	case GLOBAL_HINWEISE:
		text = "Hinweise während der Plausibilitätsprüfung, Datensatz ist aber plausibel.";
		break;
	case TRANSFER_ERR_XML_THEADER:
		text = "Fehler im Transferheader.";
		break;
	case TRANSFER_ERR_XML_NHEADER:
		text = "Fehler im NutzdatenHeader.";
		break;
	case TRANSFER_ERR_TIMEOUT:
		text = "Bei der Kommunikation mit dem Server kam es zu einer Zeitüberschreitung.";
		break;
	case TRANSFER_ERR_NORESPONSE:
		text = "Von der Clearingstelle konnte keine Antwort empfangen werden.";
		break;
	case TRANSFER_ERR_CONNECTSERVER:
		text = "Zu den Servern konnte keine Verbindung aufgebaut werden.";
		break;
	case CRYPT_E_PIN_WRONG:
		text = "Es wurde ein falsches Passwort bzw. eine falsche PIN angegeben.";
		break;
	case CRYPT_NICHT_UNTERSTUETZTES_PSE_FORMAT:
		text = "Das Format der PSE wird nicht unterstützt.";
		break;
	case IO_READER_SCHEMA_VALIDIERUNGSFEHLER:
		text = "Es traten Fehler beim Validieren des XML auf.";
		break;
	case IO_TESTHERSTELLERID_GESPERRT:
		text = "Die im XML angegebene Hersteller-ID ist gesperrt.";
		break;
	case GLOBAL_DATENARTVERSION_UNBEKANNT:
		text = "Die übergebene Datenartversion ist unbekannt oder das Plugin wurde nicht gefunden.";
		break;
	case GLOBAL_MEHRFACHE_INITIALISIERUNG:
		text = "Mehrfache Initialisierung.";
		break;
	case PRINT_ABBRUCH_GENERIERUNG:
		text = "Während der Ausgabe der Inhalte ist ein Fehler aufgetreten.";
		break;
	}
	if (!rueckgabePuffer)
		return GLOBAL_NULL_PARAMETER;
	if (!text)
		return GLOBAL_FEHLERMELDUNG_NICHT_VORHANDEN;
	fill_text(rueckgabePuffer, text);
	return OK;
}

/* Takes every Steuernummer of 13 digits but one that ends in 9, so the tests can name a valid and an invalid one. */
EXPORT int EricPruefeSteuernummer(const char *steuernummer)
{
	if (!initialised)
		return GLOBAL_NICHT_INITIALISIERT;
	if (!steuernummer || !*steuernummer)
		return GLOBAL_NULL_PARAMETER;
	record("steuernummer", steuernummer);
	size_t length = strlen(steuernummer);
	if (length != 13 || steuernummer[length - 1] == '9')
		return GLOBAL_STEUERNUMMER_UNGUELTIG;
	return OK;
}

EXPORT int EricVersion(struct EricReturnBufferApi *rueckgabeXmlPuffer)
{
	if (!initialised)
		return GLOBAL_NICHT_INITIALISIERT;
	if (!rueckgabeXmlPuffer)
		return GLOBAL_NULL_PARAMETER;
	fill_text(rueckgabeXmlPuffer,
		  "<?xml version=\"1.0\" encoding=\"UTF-8\"?>"
		  "<EricVersion xmlns=\"http://www.elster.de/EricXML/1.0/EricVersion\">"
		  "<Bibliothek><Name>libericapi.so</Name><Produktversion>44, 3, 6, 0</Produktversion>"
		  "<Dateiversion>2026.44.3.6</Dateiversion></Bibliothek>"
		  "<Bibliothek><Name>libcheckUStVA_2026.so</Name><Produktversion>44, 3, 6, 0</Produktversion>"
		  "<Dateiversion>2026.44.3.6</Dateiversion></Bibliothek>"
		  "</EricVersion>");
	return OK;
}

static void append(char **out, size_t *used, size_t *size, const char *text, size_t length)
{
	if (*used + length + 1 > *size) {
		*size = (*used + length + 1) * 2;
		*out = realloc(*out, *size);
	}
	memcpy(*out + *used, text, length);
	*used += length;
	(*out)[*used] = '\0';
}

static void append_text(char **out, size_t *used, size_t *size, const char *text)
{
	append(out, used, size, text, strlen(text));
}

static void append_escaped(char **out, size_t *used, size_t *size, const char *text)
{
	for (; *text; text++) {
		switch (*text) {
		case '&':
			append_text(out, used, size, "&amp;");
			break;
		case '<':
			append_text(out, used, size, "&lt;");
			break;
		case '>':
			append_text(out, used, size, "&gt;");
			break;
		case '"':
			append_text(out, used, size, "&quot;");
			break;
		default:
			append(out, used, size, text, 1);
		}
	}
}

EXPORT int EricCreateTH(const char *xml, const char *verfahren, const char *datenart, const char *vorgang,
			const char *testmerker, const char *herstellerId, const char *datenLieferant,
			const char *versionClient, const char *publicKey,
			struct EricReturnBufferApi *xmlRueckgabePuffer)
{
	if (!initialised)
		return GLOBAL_NICHT_INITIALISIERT;
	if (!xml || !verfahren || !datenart || !vorgang || !herstellerId || !datenLieferant ||
	    !xmlRueckgabePuffer)
		return GLOBAL_NULL_PARAMETER;
	record("th_input", xml);
	record("th_verfahren", verfahren);
	record("th_datenart", datenart);
	record("th_vorgang", vorgang);
	record("th_testmerker", testmerker);
	record("th_hersteller_id", herstellerId);
	record("th_datenlieferant", datenLieferant);
	record("th_version_client", versionClient);
	record("th_public_key", publicKey);
	const char *start = strstr(xml, "<DatenTeil");
	const char *end = strstr(xml, "</DatenTeil>");
	const char *elster = strstr(xml, "<Elster");
	if (!start || !end || has_attribute(start) || (elster && elster < start && has_attribute(elster)))
		return IO_PARSE_FEHLER;
	end += strlen("</DatenTeil>");

	size_t used = 0, size = 0;
	char *out = NULL;
	append_text(&out, &used, &size,
		    "<?xml version=\"1.0\" encoding=\"UTF-8\"?>"
		    "<Elster xmlns=\"http://www.elster.de/elsterxml/schema/v11\"><TransferHeader version=\"11\">"
		    "<Verfahren>");
	append_text(&out, &used, &size, verfahren);
	append_text(&out, &used, &size, "</Verfahren><DatenArt>");
	append_text(&out, &used, &size, datenart);
	append_text(&out, &used, &size, "</DatenArt><Vorgang>");
	append_text(&out, &used, &size, vorgang);
	append_text(&out, &used, &size, "</Vorgang>");
	if (testmerker) {
		append_text(&out, &used, &size, "<Testmerker>");
		append_text(&out, &used, &size, testmerker);
		append_text(&out, &used, &size, "</Testmerker>");
	}
	append_text(&out, &used, &size, "<HerstellerID>");
	append_text(&out, &used, &size, herstellerId);
	append_text(&out, &used, &size, "</HerstellerID><DatenLieferant>");
	append_escaped(&out, &used, &size, datenLieferant);
	append_text(&out, &used, &size,
		    "</DatenLieferant><Datei><Verschluesselung>CMSEncryptedData</Verschluesselung>"
		    "<Kompression>GZIP</Kompression></Datei></TransferHeader>");
	append(&out, &used, &size, start, (size_t)(end - start));
	append_text(&out, &used, &size, "</Elster>");
	fill(xmlRueckgabePuffer, out, (uint32_t)used);
	free(out);
	return OK;
}

EXPORT int EricZertifikatOeffnenAusBytes(uint32_t *hToken, const char *pkcs12Container, uint32_t containerGroesse,
					 const char *pkcs12Passwort)
{
	if (!initialised)
		return GLOBAL_NICHT_INITIALISIERT;
	if (!hToken || !pkcs12Container || !pkcs12Passwort)
		return GLOBAL_NULL_PARAMETER;
	unsigned long long sum = 0;
	for (uint32_t i = 0; i < containerGroesse; i++)
		sum += (unsigned char)pkcs12Container[i];
	record_number("container_size", containerGroesse);
	record_number("container_sum", (long long)sum);
	record("open_password", pkcs12Passwort);
	if (containerGroesse == 0 || (unsigned char)pkcs12Container[0] != 0x30)
		return CRYPT_NICHT_UNTERSTUETZTES_PSE_FORMAT;
	if (strcmp(pkcs12Passwort, WRONG_PIN) == 0)
		return CRYPT_E_PIN_WRONG;
	if (open_certificates == MAX_CERTIFICATES)
		abort();
	*hToken = next_handle++;
	open_handles[open_certificates++] = *hToken;
	snprintf(certificate_pin, sizeof certificate_pin, "%s", pkcs12Passwort);
	return OK;
}

EXPORT int EricCloseHandleToCertificate(uint32_t hToken)
{
	for (int i = 0; i < open_certificates; i++)
		if (open_handles[i] == hToken) {
			open_handles[i] = open_handles[--open_certificates];
			record_number("closed_handle", hToken);
			return OK;
		}
	return CRYPT_E_INVALID_HANDLE;
}

static const char success_answer[] =
	"<?xml version=\"1.0\" encoding=\"UTF-8\"?>"
	"<Elster xmlns=\"http://www.elster.de/elsterxml/schema/v11\"><TransferHeader version=\"11\">"
	"<Verfahren>ElsterAnmeldung</Verfahren><DatenArt>UStVA</DatenArt><Vorgang>send-Auth</Vorgang>"
	"<TransferTicket>et0stub0accepted0000000000000001</TransferTicket><HerstellerID>12345</HerstellerID>"
	"<RC><Rueckgabe><Code>0</Code><Text>Daten wurden erfolgreich angenommen.</Text></Rueckgabe></RC>"
	"</TransferHeader><DatenTeil><Nutzdatenblock><NutzdatenHeader version=\"11\">"
	"<NutzdatenTicket>1</NutzdatenTicket><RC><Rueckgabe><Code>0</Code><Text>Verarbeitung fehlerfrei.</Text>"
	"</Rueckgabe></RC></NutzdatenHeader></Nutzdatenblock></DatenTeil></Elster>";

static const char answer_without_ticket[] =
	"<?xml version=\"1.0\" encoding=\"UTF-8\"?>"
	"<Elster xmlns=\"http://www.elster.de/elsterxml/schema/v11\"><TransferHeader version=\"11\">"
	"<Verfahren>ElsterAnmeldung</Verfahren><DatenArt>UStVA</DatenArt><Vorgang>send-Auth</Vorgang>"
	"<RC><Rueckgabe><Code>0</Code><Text>Daten wurden erfolgreich angenommen.</Text></Rueckgabe></RC>"
	"</TransferHeader><DatenTeil></DatenTeil></Elster>";

static const char unreadable_answer[] = "Stub: keine XML-Antwort";

/* After a timeout the answer of the server may still hold the Transferticket (Kap. 6.2.5.2). */
static const char timeout_answer[] =
	"<?xml version=\"1.0\" encoding=\"UTF-8\"?>"
	"<Elster xmlns=\"http://www.elster.de/elsterxml/schema/v11\"><TransferHeader version=\"11\">"
	"<Verfahren>ElsterAnmeldung</Verfahren><DatenArt>UStVA</DatenArt><Vorgang>send-Auth</Vorgang>"
	"<TransferTicket>et0stub0timedout0000000000000004</TransferTicket><HerstellerID>12345</HerstellerID>"
	"<RC><Rueckgabe><Code>301100006</Code><Text>Stub: Zeitüberschreitung beim Speichern der Daten.</Text>"
	"</Rueckgabe></RC></TransferHeader><DatenTeil></DatenTeil></Elster>";

static const char transfer_header_error[] =
	"<?xml version=\"1.0\" encoding=\"UTF-8\"?>"
	"<Elster xmlns=\"http://www.elster.de/elsterxml/schema/v11\"><TransferHeader version=\"11\">"
	"<Verfahren>ElsterAnmeldung</Verfahren><DatenArt>UStVA</DatenArt><Vorgang>send-Auth</Vorgang>"
	"<TransferTicket>et0stub0rejected0000000000000002</TransferTicket><HerstellerID>12345</HerstellerID>"
	"<RC><Rueckgabe><Code>301100005</Code><Text>Stub: Die Daten wurden nicht angenommen.</Text></Rueckgabe></RC>"
	"</TransferHeader><DatenTeil></DatenTeil></Elster>";

static const char nutzdaten_header_error[] =
	"<?xml version=\"1.0\" encoding=\"UTF-8\"?>"
	"<Elster xmlns=\"http://www.elster.de/elsterxml/schema/v11\"><TransferHeader version=\"11\">"
	"<Verfahren>ElsterAnmeldung</Verfahren><DatenArt>UStVA</DatenArt><Vorgang>send-Auth</Vorgang>"
	"<TransferTicket>et0stub0rejected0000000000000003</TransferTicket><HerstellerID>12345</HerstellerID>"
	"<RC><Rueckgabe><Code>0</Code><Text>Daten wurden erfolgreich angenommen.</Text></Rueckgabe></RC>"
	"</TransferHeader><DatenTeil><Nutzdatenblock><NutzdatenHeader version=\"11\">"
	"<NutzdatenTicket>1</NutzdatenTicket><RC><Rueckgabe><Code>200100007</Code>"
	"<Text>Stub: Die Steuernummer ist dem Finanzamt nicht bekannt.</Text></Rueckgabe></RC>"
	"</NutzdatenHeader></Nutzdatenblock></DatenTeil></Elster>";

static const char rule_errors[] =
	"<?xml version=\"1.0\" encoding=\"UTF-8\"?>"
	"<EricBearbeiteVorgang xmlns=\"http://www.elster.de/EricXML/1.2/EricBearbeiteVorgang\">"
	"<FehlerRegelpruefung><Nutzdatenticket>1</Nutzdatenticket><Feldidentifikator>Kz83</Feldidentifikator>"
	"<VordruckZeilennummer>50</VordruckZeilennummer><RegelName>stubRegelKz83</RegelName>"
	"<FachlicheFehlerId>110085064</FachlicheFehlerId><Text>Die Kennzahl 83 muss angegeben werden.</Text>"
	"</FehlerRegelpruefung>"
	"<FehlerRegelpruefung><Nutzdatenticket>1</Nutzdatenticket><RegelName>stubRegelOhneId</RegelName>"
	"<Text>Eine Prüfung ohne Fehlercode ist fehlgeschlagen.</Text></FehlerRegelpruefung>"
	"<Hinweis><Nutzdatenticket>1</Nutzdatenticket><Feldidentifikator>Kz26</Feldidentifikator>"
	"<FachlicheHinweisId>11085155</FachlicheHinweisId><Text>Bitte prüfen Sie die Kennzahl 26.</Text></Hinweis>"
	"</EricBearbeiteVorgang>";

static const char hints[] =
	"<?xml version=\"1.0\" encoding=\"UTF-8\"?>"
	"<EricBearbeiteVorgang xmlns=\"http://www.elster.de/EricXML/1.2/EricBearbeiteVorgang\">"
	"<Hinweis><Nutzdatenticket>1</Nutzdatenticket><Feldidentifikator>Kz26</Feldidentifikator>"
	"<FachlicheHinweisId>11085155</FachlicheHinweisId><Text>Bitte prüfen Sie die Kennzahl 26.</Text></Hinweis>"
	"</EricBearbeiteVorgang>";

static const char success[] = "<?xml version=\"1.0\" encoding=\"UTF-8\"?>"
			      "<EricBearbeiteVorgang xmlns=\"http://www.elster.de/EricXML/1.2/EricBearbeiteVorgang\">"
			      "<Erfolg/></EricBearbeiteVorgang>";

/* The combinations of EricBearbeiteVorgang the ERiC handbook allows for send-Auth (Tabelle 6-2). */
static int check_combination(uint32_t flags, const struct print_parameters *print,
			     const struct encryption_parameters *crypto)
{
	static const struct {
		uint32_t flags;
		int print;
		int preview;
		int crypto;
	} allowed[] = {
		{VALIDIERE, 0, 0, 0},
		{VALIDIERE | DRUCKE, 1, 1, 0},
		{VALIDIERE | SENDE, 0, 0, 1},
		{VALIDIERE | SENDE | DRUCKE, 1, 0, 1},
		{PRUEFE_HINWEISE, 0, 0, 0},
		{PRUEFE_HINWEISE | VALIDIERE, 0, 0, 0},
		{PRUEFE_HINWEISE | VALIDIERE | DRUCKE, 1, 1, 0},
	};
	for (size_t i = 0; i < sizeof allowed / sizeof *allowed; i++) {
		if (allowed[i].flags != flags)
			continue;
		if (allowed[i].crypto && !crypto)
			return GLOBAL_VERSCHLUESSELUNGS_PARAMETER_NICHT_ANGEGEBEN;
		if (!allowed[i].crypto && crypto)
			return GLOBAL_VERSCHLUESSELUNGS_PARAMETER_NICHT_ERLAUBT;
		if (allowed[i].print != (print != NULL))
			return GLOBAL_UNGUELTIGER_PARAMETER;
		if (print && print->vorschau != (uint32_t)allowed[i].preview)
			return GLOBAL_UNGUELTIGER_PARAMETER;
		return OK;
	}
	return GLOBAL_UNGUELTIGER_PARAMETER;
}

/* The year of a datenartVersion <prefix><Jahr>, or NULL for any other one. */
static const char *year_of(const char *datenartVersion, const char *prefix)
{
	size_t length = strlen(prefix);
	if (strncmp(datenartVersion, prefix, length) != 0)
		return NULL;
	const char *year = datenartVersion + length;
	return strlen(year) == 4 && is_digits(year) ? year : NULL;
}

/* True for Bilanz_<major>.<minor>, the datenartVersion of an HGB-Taxonomie, with major and minor copied out. */
static int taxonomy_of(const char *datenartVersion, char *major, char *minor, size_t size)
{
	if (strncmp(datenartVersion, "Bilanz_", 7) != 0)
		return 0;
	const char *taxonomy = datenartVersion + 7;
	const char *dot = strchr(taxonomy, '.');
	if (!dot || (size_t)(dot - taxonomy) >= size || strlen(dot + 1) >= size)
		return 0;
	memcpy(major, taxonomy, (size_t)(dot - taxonomy));
	major[dot - taxonomy] = '\0';
	snprintf(minor, size, "%s", dot + 1);
	return is_digits(major) && is_digits(minor);
}

/* The plugin of a datenartVersion, as the Datenartversionmatrix names it: checkUStVA_<Jahr> for UStVA_<Jahr>,
 * checkZMDO for ZMDO, checkUSt_<Jahr>, checkKSt_<Jahr> and checkGewSt_<Jahr> for USt_<Jahr>, KSt_30_<Jahr> and
 * GewSt_<Jahr>, checkBilanz_<major>_<minor> for Bilanz_<major>.<minor>. Returns 0 for any other datenartVersion. */
static int plugin_of(const char *datenartVersion, char *library, size_t size)
{
	static const struct {
		const char *prefix;
		const char *plugin;
	} yearly[] = {
		{"UStVA_", "checkUStVA_"},
		{"USt_", "checkUSt_"},
		{"KSt_30_", "checkKSt_"},
		{"GewSt_", "checkGewSt_"},
	};
	char major[8], minor[8];
	if (strcmp(datenartVersion, "ZMDO") == 0) {
		snprintf(library, size, "libcheckZMDO.so");
		return 1;
	}
	for (size_t i = 0; i < sizeof yearly / sizeof *yearly; i++) {
		const char *year = year_of(datenartVersion, yearly[i].prefix);
		if (year) {
			snprintf(library, size, "lib%s%s.so", yearly[i].plugin, year);
			return 1;
		}
	}
	if (!taxonomy_of(datenartVersion, major, minor, sizeof major))
		return 0;
	snprintf(library, size, "libcheckBilanz_%s_%s.so", major, minor);
	return 1;
}

static int plugin_exists(const char *datenartVersion)
{
	const char *plugin_path = recorded("plugin_path");
	char library[64];
	char path[4096];
	if (!plugin_of(datenartVersion, library, sizeof library))
		return 0;
	snprintf(path, sizeof path, "%s/plugins2/%s", plugin_path, library);
	if (access(path, R_OK) == 0)
		return 1;
	snprintf(path, sizeof path, "%s/plugins/%s", plugin_path, library);
	return access(path, R_OK) == 0;
}

static int print_pdf(const char *xml, const struct print_parameters *print)
{
	char name[64] = "Uebertragungsprotokoll";
	between(xml, "<NutzdatenTicket>", "</NutzdatenTicket>", name, sizeof name);
	if (contains(xml, "STUB-PRINT-ERROR"))
		return PRINT_ABBRUCH_GENERIERUNG;
	if (print->pdfCallback) {
		int result = print->pdfCallback(name, (const uint8_t *)canned_pdf, pdf_size(),
						print->pdfCallbackBenutzerdaten);
		record_number("pdf_callback_result", result);
		return result == 0 ? OK : PRINT_PDFCALLBACK;
	}
	FILE *file = fopen(print->pdfName, "wb");
	if (!file)
		return PRINT_UNGUELTIGER_DATEI_PFAD;
	fwrite(canned_pdf, 1, pdf_size(), file);
	fclose(file);
	return OK;
}

EXPORT int EricBearbeiteVorgang(const char *datenpuffer, const char *datenartVersion, uint32_t bearbeitungsFlags,
				const struct print_parameters *druckParameter,
				const struct encryption_parameters *cryptoParameter,
				struct EricReturnBufferApi *rueckgabeXmlPuffer,
				struct EricReturnBufferApi *serverantwortXmlPuffer)
{
	if (!initialised)
		return GLOBAL_NICHT_INITIALISIERT;
	if (!datenpuffer || !datenartVersion || !rueckgabeXmlPuffer || !serverantwortXmlPuffer)
		return GLOBAL_NULL_PARAMETER;
	record("datenpuffer", datenpuffer);
	record("datenart_version", datenartVersion);
	record_number("flags", bearbeitungsFlags);
	record_number("print_version", druckParameter ? (long long)druckParameter->version : -1);
	record_number("crypto_version", cryptoParameter ? (long long)cryptoParameter->version : -1);
	if (druckParameter) {
		record_number("vorschau", druckParameter->vorschau);
		record_number("duplex", druckParameter->duplexDruck);
		record("pdf_name", druckParameter->pdfName);
		record("fuss_text", druckParameter->fussText);
		record_number("pdf_callback_set", druckParameter->pdfCallback != NULL);
	}
	if (cryptoParameter) {
		record_number("certificate_handle", cryptoParameter->zertifikatHandle);
		record("pin", cryptoParameter->pin);
	}

	if (druckParameter && druckParameter->version != 4)
		return GLOBAL_UNGUELTIGE_PARAMETER_VERSION;
	if (cryptoParameter && cryptoParameter->version != 3)
		return GLOBAL_UNGUELTIGE_PARAMETER_VERSION;
	if (druckParameter && (druckParameter->vorschau > 1 || druckParameter->duplexDruck > 1))
		return GLOBAL_UNGUELTIGER_PARAMETER;
	if (druckParameter && druckParameter->fussText && strlen(druckParameter->fussText) > MAX_FUSSTEXT)
		return PRINT_FUSSTEXT_ZU_LANG;
	if (druckParameter && !druckParameter->pdfCallback && !druckParameter->pdfName)
		return GLOBAL_UNGUELTIGER_PARAMETER;
	int combination = check_combination(bearbeitungsFlags, druckParameter, cryptoParameter);
	if (combination != OK)
		return combination;
	/* The Datenart Bilanz takes no Hinweisprüfung without Validiere (Entwicklerhandbuch, Kap. 9.7.1). */
	if (strncmp(datenartVersion, "Bilanz_", 7) == 0 && (bearbeitungsFlags & PRUEFE_HINWEISE) &&
	    !(bearbeitungsFlags & VALIDIERE))
		return GLOBAL_UNGUELTIGE_FLAG_KOMBINATION;
	if (cryptoParameter) {
		if (!is_open_handle(cryptoParameter->zertifikatHandle))
			return CRYPT_E_INVALID_HANDLE;
		if (!cryptoParameter->pin || strcmp(cryptoParameter->pin, certificate_pin) != 0)
			return CRYPT_E_PIN_WRONG;
	}
	if (strncmp(datenpuffer, "\xef\xbb\xbf", 3) == 0 || contains(datenpuffer, "encoding=\"ISO-8859-15\""))
		return IO_READER_FALSCHES_ENCODING;
	if (!plugin_exists(datenartVersion))
		return GLOBAL_DATENARTVERSION_UNBEKANNT;
	if (!contains(datenpuffer, "<TransferHeader version=\"11\">") || !contains(datenpuffer, "<Nutzdaten>"))
		return IO_PARSE_FEHLER;
	if (contains(datenpuffer, "<HerstellerID>74931</HerstellerID>"))
		return IO_TESTHERSTELLERID_GESPERRT;
	if (contains(datenpuffer, "STUB-ABORT"))
		abort();
	if (contains(datenpuffer, "STUB-SLEEP"))
		sleep(30);
	if (contains(datenpuffer, "STUB-SCHEMA"))
		return IO_READER_SCHEMA_VALIDIERUNGSFEHLER;
	if (contains(datenpuffer, "STUB-PRUEF-FEHLER")) {
		fill_text(rueckgabeXmlPuffer, rule_errors);
		return GLOBAL_PRUEF_FEHLER;
	}
	if (contains(datenpuffer, "STUB-PRUEF-OHNE-REGELN")) {
		fill_text(rueckgabeXmlPuffer, "<EricBearbeiteVorgang/>");
		return GLOBAL_PRUEF_FEHLER;
	}
	if (contains(datenpuffer, "STUB-BROKEN-RETURN")) {
		fill_text(rueckgabeXmlPuffer, "<EricBearbeiteVorgang><FehlerRegelpruefung>");
		return GLOBAL_PRUEF_FEHLER;
	}
	if (contains(datenpuffer, "STUB-HINWEIS") && (bearbeitungsFlags & PRUEFE_HINWEISE)) {
		fill_text(rueckgabeXmlPuffer, hints);
		if (druckParameter)
			print_pdf(datenpuffer, druckParameter);
		return GLOBAL_HINWEISE;
	}

	if (bearbeitungsFlags & SENDE) {
		if (contains(datenpuffer, "STUB-CONNECT"))
			return TRANSFER_ERR_CONNECTSERVER;
		if (contains(datenpuffer, "STUB-TIMEOUT-ANSWER")) {
			fill_text(serverantwortXmlPuffer, timeout_answer);
			return TRANSFER_ERR_TIMEOUT;
		}
		if (contains(datenpuffer, "STUB-TIMEOUT"))
			return TRANSFER_ERR_TIMEOUT;
		if (contains(datenpuffer, "STUB-NORESPONSE"))
			return TRANSFER_ERR_NORESPONSE;
		if (contains(datenpuffer, "STUB-THEADER")) {
			fill_text(serverantwortXmlPuffer, transfer_header_error);
			return TRANSFER_ERR_XML_THEADER;
		}
		if (contains(datenpuffer, "STUB-NHEADER")) {
			fill_text(serverantwortXmlPuffer, nutzdaten_header_error);
			return TRANSFER_ERR_XML_NHEADER;
		}
		if (contains(datenpuffer, "STUB-NO-TICKET"))
			fill_text(serverantwortXmlPuffer, answer_without_ticket);
		else if (contains(datenpuffer, "STUB-UNREADABLE-ANSWER"))
			fill_text(serverantwortXmlPuffer, unreadable_answer);
		else
			fill_text(serverantwortXmlPuffer, success_answer);
	}
	if (druckParameter) {
		int printed = print_pdf(datenpuffer, druckParameter);
		if (printed != OK)
			return printed;
	}
	fill_text(rueckgabeXmlPuffer, success);
	return OK;
}

EXPORT int EricGetErrormessagesFromXMLAnswer(const char *xml, struct EricReturnBufferApi *transferticketPuffer,
					     struct EricReturnBufferApi *returncodeTHPuffer,
					     struct EricReturnBufferApi *fehlertextTHPuffer,
					     struct EricReturnBufferApi *returncodesUndFehlertexteNDHXmlPuffer)
{
	if (!initialised)
		return GLOBAL_NICHT_INITIALISIERT;
	if (!xml || !transferticketPuffer || !returncodeTHPuffer || !fehlertextTHPuffer ||
	    !returncodesUndFehlertexteNDHXmlPuffer)
		return GLOBAL_NULL_PARAMETER;
	if (!contains(xml, "<Elster") || !contains(xml, "</TransferHeader>"))
		return IO_PARSE_FEHLER;
	char ticket[128] = "", code[64] = "", text[512] = "";
	between(xml, "<TransferTicket>", "</TransferTicket>", ticket, sizeof ticket);
	const char *transfer_header_rc = strstr(xml, "<RC>");
	between(transfer_header_rc, "<Code>", "</Code>", code, sizeof code);
	between(transfer_header_rc, "<Text>", "</Text>", text, sizeof text);
	fill_text(transferticketPuffer, ticket);
	fill_text(returncodeTHPuffer, code);
	fill_text(fehlertextTHPuffer, text);

	size_t used = 0, size = 0;
	char *errors = NULL;
	append_text(&errors, &used, &size,
		    "<?xml version=\"1.0\" encoding=\"UTF-8\"?><EricGetErrormessagesFromXMLAnswer "
		    "xmlns=\"http://www.elster.de/EricXML/1.0/EricGetErrormessagesFromXMLAnswer\">");
	char header[1024];
	const char *rest = xml;
	while ((rest = between(rest, "<NutzdatenHeader", "</NutzdatenHeader>", header, sizeof header))) {
		char header_code[64] = "", header_text[512] = "";
		between(header, "<Code>", "</Code>", header_code, sizeof header_code);
		between(header, "<Text>", "</Text>", header_text, sizeof header_text);
		if (strcmp(header_code, "0") != 0) {
			append_text(&errors, &used, &size, "<Fehler><Code>");
			append_text(&errors, &used, &size, header_code);
			append_text(&errors, &used, &size, "</Code><Meldung>");
			append_text(&errors, &used, &size, header_text);
			append_text(&errors, &used, &size, "</Meldung></Fehler>");
		}
	}
	append_text(&errors, &used, &size, "</EricGetErrormessagesFromXMLAnswer>");
	fill(returncodesUndFehlertexteNDHXmlPuffer, errors, (uint32_t)used);
	free(errors);
	return OK;
}

EXPORT int EricCheckXML(const char *xml, const char *datenartVersion, struct EricReturnBufferApi *fehlertextPuffer)
{
	if (!initialised)
		return GLOBAL_NICHT_INITIALISIERT;
	if (!xml || !datenartVersion || !fehlertextPuffer)
		return GLOBAL_NULL_PARAMETER;
	record("check_xml", xml);
	if (strncmp(datenartVersion, "UStVA_", 6) != 0)
		return GLOBAL_DATENARTVERSION_UNBEKANNT;
	if (contains(xml, "STUB-SCHEMA")) {
		fill_text(fehlertextPuffer, "Element 'Kz83': Der Wert 'abc' ist kein gültiger Betrag.");
		return IO_READER_SCHEMA_VALIDIERUNGSFEHLER;
	}
	return OK;
}

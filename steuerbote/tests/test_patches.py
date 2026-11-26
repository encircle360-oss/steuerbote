"""The patches of steuerbote/patches against the database of the test site."""

from unittest.mock import patch

import frappe
from frappe.modules.patch_handler import PatchType, get_patches_from_app
from frappe.tests import IntegrationTestCase
from frappe.utils import add_days

from steuerbote.patches import fill_the_party_names_of_confirmations as party_names
from steuerbote.patches import link_transmissions_to_their_document as transmissions
from steuerbote.patches import mark_the_bases_of_earlier_overrides_unknown as unknown_bases
from steuerbote.patches import set_the_basis_of_overrides as bases
from steuerbote.patches import use_keys_for_kz_500 as kz500

TRANSMISSION = "ELSTER Transmission"
PATCH = "steuerbote.patches.link_transmissions_to_their_document"
BASES_PATCH = "steuerbote.patches.set_the_basis_of_overrides"
UNKNOWN_PATCH = "steuerbote.patches.mark_the_bases_of_earlier_overrides_unknown"
KZ500_PATCH = "steuerbote.patches.use_keys_for_kz_500"


class TestLinkTransmissionsToTheirDocument(IntegrationTestCase):
	"""Records from before the Dynamic Link name a VAT Return in the column vat_return, which Frappe keeps when the
	field leaves the DocType. On a site installed without that field the tests add the column themselves."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.added_column = not frappe.db.has_column(TRANSMISSION, transmissions.OLD_FIELD)
		if cls.added_column:
			frappe.db.sql_ddl(
				f"alter table `tab{TRANSMISSION}` add column `{transmissions.OLD_FIELD}` varchar(140)"
			)
			cls.forget_columns()

	@classmethod
	def tearDownClass(cls):
		if cls.added_column:
			# A schema change commits, so the records of the tests are rolled back first.
			frappe.db.rollback()
			frappe.db.sql_ddl(f"alter table `tab{TRANSMISSION}` drop column `{transmissions.OLD_FIELD}`")
			cls.forget_columns()
		super().tearDownClass()

	@staticmethod
	def forget_columns() -> None:
		frappe.client_cache.delete_value(f"table_columns::tab{TRANSMISSION}")

	def record(self, name: str, vat_return: str | None, **fields) -> str:
		"""An ELSTER Transmission as the database holds it, with ``vat_return`` in the old column."""
		frappe.get_doc(
			{"doctype": TRANSMISSION, "name": name, "operation": "send", "status": "Erfolgreich", **fields}
		).db_insert()
		table = frappe.qb.DocType(TRANSMISSION)
		old_column = frappe.qb.update(table).set(table[transmissions.OLD_FIELD], vat_return)
		old_column.where(table.name == name).run()
		return name

	def linked(self, name: str) -> tuple[str | None, str | None]:
		return frappe.db.get_value(TRANSMISSION, name, ["document_type", "document"])

	def test_runs_after_the_doctypes_are_migrated(self):
		self.assertIn(PATCH, get_patches_from_app("steuerbote", PatchType.post_model_sync))
		self.assertNotIn(PATCH, get_patches_from_app("steuerbote", PatchType.pre_model_sync))

	def test_names_the_vat_return_of_a_record_by_the_dynamic_link(self):
		name = self.record("ELSTER-PATCH-00001", "UStVA-2026-99901")
		transmissions.execute()
		self.assertEqual(self.linked(name), ("VAT Return", "UStVA-2026-99901"))

	def test_keeps_a_record_that_names_its_document(self):
		name = self.record(
			"ELSTER-PATCH-00002", None, document_type="VAT Return Extension", document="DFV-2026-99902"
		)
		transmissions.execute()
		self.assertEqual(self.linked(name), ("VAT Return Extension", "DFV-2026-99902"))

	def test_runs_again_without_changing_a_record(self):
		name = self.record("ELSTER-PATCH-00003", "UStVA-2026-99903")
		transmissions.execute()
		transmissions.execute()
		self.assertEqual(self.linked(name), ("VAT Return", "UStVA-2026-99903"))

	def test_does_nothing_on_a_site_without_the_old_column(self):
		name = self.record("ELSTER-PATCH-00004", "UStVA-2026-99904")
		with patch.object(transmissions, "OLD_FIELD", "vat_return_of_no_site"):
			transmissions.execute()
		self.assertEqual(self.linked(name), (None, None))


class TestSetTheLedgerBasisOfOverrides(IntegrationTestCase):
	"""Overrides and corrections made before they kept the amount they were made against take the amount their row
	holds: the one the ledger or Berechnen gave at their last calculation, which is what they were confirmed against."""

	def row(self, doctype: str, name: str, **fields) -> str:
		frappe.get_doc(
			{
				"doctype": doctype,
				"name": name,
				"parent": "PATCH-PARENT",
				"parentfield": "x",
				"parenttype": "x",
				**fields,
			}
		).db_insert()
		return name

	def test_runs_after_the_doctypes_are_migrated(self):
		self.assertIn(BASES_PATCH, get_patches_from_app("steuerbote", PatchType.post_model_sync))

	def test_an_override_with_a_reason_takes_the_amount_of_its_row_once(self):
		line = "Recapitulative Statement Line"
		overridden = self.row(
			line,
			"PATCH-ZM-1",
			vat_id="ATU12345678",
			art="L",
			amount=55000.99,
			override=55000,
			override_reason="Nachweis",
		)
		plain = self.row(line, "PATCH-ZM-2", vat_id="FR12345678901", art="S", amount=300)
		kept = self.row(
			line,
			"PATCH-ZM-3",
			vat_id="ESX1234567X",
			art="L",
			amount=10,
			override=8,
			override_reason="x",
			override_basis=9,
		)
		kennzahl = self.row(
			"VAT Return Kennzahl",
			"PATCH-KZ-1",
			kennzahl="81",
			amount=1000,
			override=1100,
			override_reason="Spät",
		)
		annual = self.row(
			"Annual VAT Return Line",
			"PATCH-JA-1",
			feldkennung="E3003303",
			form_amount=1200,
			correction=1100,
			correction_reason="Spät",
		)
		bases.execute()
		bases.execute()
		self.assertEqual(
			[
				frappe.db.get_value(line, overridden, "override_basis"),
				frappe.db.get_value(line, plain, "override_basis"),
				frappe.db.get_value(line, kept, "override_basis"),
				frappe.db.get_value("VAT Return Kennzahl", kennzahl, "override_basis"),
				frappe.db.get_value("Annual VAT Return Line", annual, "correction_basis"),
			],
			[55000.99, 0, 9, 1000, 1200],
		)


class TestMarkTheBasesOfEarlierOverridesUnknown(IntegrationTestCase):
	"""The basis set_the_basis_of_overrides wrote is the amount of the day of the update, not the one an override was
	made against, and it kept no record of the rows it wrote: every override and correction of a document created
	before it ran gets the mark of an unknown basis, a line by hand and a row without a reason none."""

	def setUp(self):
		self.since = frappe.db.get_value("Patch Log", {"patch": BASES_PATCH}, "creation")
		self.assertIsNotNone(self.since)

	def document(self, doctype: str, name: str, days: int) -> str:
		frappe.get_doc({"doctype": doctype, "name": name}).db_insert()
		frappe.db.set_value(doctype, name, "creation", add_days(self.since, days), update_modified=False)
		return name

	def row(self, doctype: str, name: str, parent: str, parenttype: str, **fields) -> str:
		frappe.get_doc(
			{
				"doctype": doctype,
				"name": name,
				"parent": parent,
				"parentfield": "x",
				"parenttype": parenttype,
				**fields,
			}
		).db_insert()
		return name

	def unknown(self, doctype: str, name: str, field: str) -> int:
		return frappe.db.get_value(doctype, name, field)

	def test_runs_after_the_patch_that_set_the_bases(self):
		patches = get_patches_from_app("steuerbote", PatchType.post_model_sync)
		self.assertLess(patches.index(BASES_PATCH), patches.index(UNKNOWN_PATCH))

	def test_marks_the_overrides_of_documents_created_before_the_bases_were_set(self):
		older = self.document("VAT Return", "PATCH-UNKNOWN-UV-1", -1)
		newer = self.document("VAT Return", "PATCH-UNKNOWN-UV-2", 1)
		kennzahl = "VAT Return Kennzahl"
		overridden = self.row(
			kennzahl,
			"PATCH-UNKNOWN-KZ-1",
			older,
			"VAT Return",
			kennzahl="81",
			amount=1300,
			override=1100,
			override_reason="Spät",
			override_basis=1300,
		)
		plain = self.row(kennzahl, "PATCH-UNKNOWN-KZ-2", older, "VAT Return", kennzahl="86", amount=50)
		later = self.row(
			kennzahl,
			"PATCH-UNKNOWN-KZ-3",
			newer,
			"VAT Return",
			kennzahl="81",
			amount=1300,
			override=1100,
			override_reason="Spät",
			override_basis=1000,
		)
		statement = self.document("Recapitulative Statement", "PATCH-UNKNOWN-ZM-1", -1)
		line = "Recapitulative Statement Line"
		zm = self.row(
			line,
			"PATCH-UNKNOWN-ZM-L1",
			statement,
			"Recapitulative Statement",
			vat_id="ATU12345678",
			art="L",
			amount=57000.99,
			override=55000,
			override_reason="Nachweis",
			override_basis=57000.99,
		)
		by_hand = self.row(
			line,
			"PATCH-UNKNOWN-ZM-L2",
			statement,
			"Recapitulative Statement",
			vat_id="ATU99999999",
			art="L",
			override=2500,
			override_reason="Verbringen",
			manual=1,
		)
		annual = self.document("Annual VAT Return", "PATCH-UNKNOWN-USTE-1", -1)
		annual_line = self.row(
			"Annual VAT Return Line",
			"PATCH-UNKNOWN-JA-1",
			annual,
			"Annual VAT Return",
			feldkennung="E3003303",
			form_amount=1200,
			correction=1100,
			correction_reason="Spät",
			correction_basis=1200,
		)
		unknown_bases.execute()
		unknown_bases.execute()
		self.assertEqual(
			[
				self.unknown(kennzahl, overridden, "override_basis_unknown"),
				self.unknown(kennzahl, plain, "override_basis_unknown"),
				self.unknown(kennzahl, later, "override_basis_unknown"),
				self.unknown(line, zm, "override_basis_unknown"),
				self.unknown(line, by_hand, "override_basis_unknown"),
				self.unknown("Annual VAT Return Line", annual_line, "correction_basis_unknown"),
			],
			[1, 0, 0, 1, 0, 1],
		)
		self.assertEqual(frappe.db.get_value(kennzahl, overridden, "override_basis"), 1300)

	def test_does_nothing_on_a_site_where_the_bases_were_never_set(self):
		older = self.document("VAT Return", "PATCH-UNKNOWN-UV-3", -1)
		row = self.row(
			"VAT Return Kennzahl",
			"PATCH-UNKNOWN-KZ-4",
			older,
			"VAT Return",
			kennzahl="81",
			amount=10,
			override=8,
			override_reason="x",
			override_basis=10,
		)
		with patch.object(unknown_bases, "EARLIER_PATCH", "steuerbote.patches.of_no_site"):
			unknown_bases.execute()
		self.assertEqual(self.unknown("VAT Return Kennzahl", row, "override_basis_unknown"), 0)


class TestUseKeysForKz500(IntegrationTestCase):
	"""Documents from before the keys hold the code of Kz 500, 1 to 4, which the select field no longer offers."""

	FIELDS = (
		("VAT Return", "supplementary_code", "the view of the administration"),
		("VAT Return Extension", "supplementary_code", "the view of the administration"),
		("Annual VAT Return", "kz500", "the opinion of the administration"),
	)

	def test_runs_after_the_doctypes_are_migrated(self):
		self.assertIn(KZ500_PATCH, get_patches_from_app("steuerbote", PatchType.post_model_sync))

	def test_turns_each_code_into_its_key_and_runs_again_without_a_change(self):
		names = {}
		for doctype, fieldname, _view in self.FIELDS:
			for code in ("1", "2", "3", "4", ""):
				name = f"Steuerbote Test Kz500 {code or 'ohne'}"
				frappe.get_doc({"doctype": doctype, "name": name, fieldname: code}).db_insert()
				names[doctype, code] = name
		kz500.execute()
		kz500.execute()
		for doctype, fieldname, view in self.FIELDS:
			stored = {code: frappe.db.get_value(doctype, names[doctype, code], fieldname) for code in "1234"}
			with self.subTest(doctype=doctype):
				self.assertEqual(
					stored,
					{
						"1": "1 = Facts relevant to the tax could not be explained.",
						"2": f"2 = A legal view deliberately deviating from {view} is taken.",
						"3": "3 = Facts are to be examined in depth by a person.",
						"4": "4 = Several of the reasons above apply (multiple choice).",
					},
				)
				self.assertFalse(frappe.db.get_value(doctype, names[doctype, ""], fieldname))


class TestFillThePartyNamesOfConfirmations(IntegrationTestCase):
	"""Confirmations from before the name column name their partner by ID alone."""

	PATCH = "steuerbote.patches.fill_the_party_names_of_confirmations"

	def setUp(self):
		frappe.db.savepoint("party_names_test")
		self.addCleanup(frappe.db.rollback, save_point="party_names_test")

	def test_runs_after_the_doctypes_are_migrated(self):
		self.assertIn(self.PATCH, get_patches_from_app("steuerbote", PatchType.post_model_sync))

	def test_gives_each_confirmation_the_name_of_its_partner_and_runs_again(self):
		frappe.get_doc({"doctype": "Customer", "name": "10042", "customer_name": "Muster GmbH"}).db_insert()
		frappe.get_doc(
			{"doctype": "Supplier", "name": "70042", "supplier_name": "Beispiel Lieferant KG"}
		).db_insert()
		for name, party_type, party in (
			("Steuerbote Test Name K", "Customer", "10042"),
			("Steuerbote Test Name L", "Supplier", "70042"),
			("Steuerbote Test Name O", None, None),
		):
			frappe.get_doc(
				{"doctype": "VAT ID Confirmation", "name": name, "party_type": party_type, "party": party}
			).db_insert()
		party_names.execute()
		party_names.execute()
		self.assertEqual(
			{
				name: frappe.db.get_value("VAT ID Confirmation", name, "party_name")
				for name in ("Steuerbote Test Name K", "Steuerbote Test Name L", "Steuerbote Test Name O")
			},
			{
				"Steuerbote Test Name K": "Muster GmbH",
				"Steuerbote Test Name L": "Beispiel Lieferant KG",
				"Steuerbote Test Name O": None,
			},
		)

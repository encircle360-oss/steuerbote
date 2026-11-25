"""The patches of steuerbote/patches against the database of the test site."""

from unittest.mock import patch

import frappe
from frappe.modules.patch_handler import PatchType, get_patches_from_app
from frappe.tests import IntegrationTestCase

from steuerbote.patches import link_transmissions_to_their_document as transmissions
from steuerbote.patches import set_the_basis_of_overrides as bases

TRANSMISSION = "ELSTER Transmission"
PATCH = "steuerbote.patches.link_transmissions_to_their_document"
BASES_PATCH = "steuerbote.patches.set_the_basis_of_overrides"


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

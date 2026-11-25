"""VAT Return Prior Filing: a Voranmeldung filed before Steuerbote, entered once as filed (steuerbote/setup/start.py).

A company that starts with Steuerbote in the middle of its life has filed the Voranmeldungen before the start of its
books in ERPNext elsewhere, through its tax adviser say. What later filings read of them, Kz 83 and the Sondervorauszahlung
of Kz 39 for the Sondervorauszahlung of the next year (steuerbote/dauerfrist_sources.py), the tax of the year for the
Voranmeldungszeitraum (steuerbote/steuerbote/setup.py) and Kz 41 and 42 for the threshold of the Zusammenfassende
Meldung (steuerbote/zm_sources.py), the company enters here with the source document and the reason; the record names
who entered it and when. Only a submitted record counts, and of several of a period the latest filed, as a corrected
Voranmeldung replaces the one before it. The record belongs to a period before the start of the books, if the VAT
Return Settings name one, that no VAT Return filed through Steuerbote covers, and its months overlap no record of
another period.
"""

from collections.abc import Iterator
from contextlib import contextmanager

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, getdate, now_datetime

from steuerbote import prior_filings
from steuerbote.setup import start
from steuerbote.ustva import Period, Rhythm

VAT_RETURN = "VAT Return"


class VATReturnPriorFiling(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		amended_from: DF.Link | None
		attachment: DF.Attach | None
		company: DF.Link
		entered_by: DF.Link | None
		entered_on: DF.Datetime | None
		filed_on: DF.Date
		kz21: DF.Currency
		kz39: DF.Currency
		kz41: DF.Currency
		kz42: DF.Currency
		kz83: DF.Currency
		naming_series: DF.Literal["VVS-.{year}.-.#####"]
		period_index: DF.Int
		period_label: DF.Data | None
		reason: DF.SmallText
		rhythm: DF.Literal["monthly", "quarterly"]
		source_document: DF.Data
		year: DF.Int
	# end: auto-generated types

	def before_insert(self) -> None:
		self.entered_by = frappe.session.user
		self.entered_on = now_datetime()

	def validate(self) -> None:
		before = self.get_doc_before_save()
		if before is not None:
			self.entered_by, self.entered_on = before.entered_by, before.entered_on
		if not (self.company and self.year and self.rhythm and self.period_index):
			return  # the mandatory check that follows names the missing field
		period = self._period()
		self.period_label = period.label
		if self.filed_on and getdate(self.filed_on) > getdate():
			frappe.throw(_("A return cannot be filed in the future."))
		with start_errors():
			start.check_prior_period(period, prior_filings.books_start(self.company))
		self._refuse_a_period_filed_through_steuerbote(period)
		self._refuse_overlapping_records(period)

	def _period(self) -> Period:
		try:
			return Period(cint(self.year), Rhythm(self.rhythm), cint(self.period_index))
		except ValueError:
			frappe.throw(
				_("{0} {1} of {2} is no Voranmeldungszeitraum.").format(
					_(self.rhythm), cint(self.period_index), cint(self.year)
				)
			)

	def _refuse_a_period_filed_through_steuerbote(self, period: Period) -> None:
		"""A VAT Return filed through Steuerbote holds its period itself."""
		filed = frappe.get_all(
			VAT_RETURN,
			filters={
				"company": self.company,
				"docstatus": 1,
				"from_date": ["<=", period.end],
				"to_date": [">=", period.start],
			},
			pluck="name",
			limit=1,
		)
		if filed:
			frappe.throw(
				_("{0} files {1} through Steuerbote already: it holds the period itself.").format(
					filed[0], period.label
				)
			)

	def _refuse_overlapping_records(self, period: Period) -> None:
		own = start.PriorFiling(period, self.name or "", getdate(self.filed_on or getdate()), start.ZERO)
		others = [
			filed
			for filed in prior_filings.prior_filings(self.company, {period.year})
			if filed.name != self.name
		]
		found = start.overlapping(own, others)
		if found is not None:
			frappe.throw(
				_(
					"{0} covers months of {1} already. Cancel it before entering {1} in another rhythm."
				).format(found.name, period.label)
			)


@contextmanager
def start_errors() -> Iterator[None]:
	"""Show a start or a prior filing that does not fit as a message in the language of the user."""
	try:
		yield
	except start.StartError as error:
		frappe.throw(_(error.template).format(*error.values))

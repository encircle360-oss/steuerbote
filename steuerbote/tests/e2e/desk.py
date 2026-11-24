"""A page of the desk in the browser: what the browser tests do on it, and what went wrong while they did.

Every page notes JavaScript errors, errors on the console and failed responses: a response of the server with a
status of 500 or more, and an asset the page asks for that is missing. Any other status of 400 or more is the
server refusing a request, such as a page the user may not open or a document method that throws a message; the
tests that provoke one check what the desk shows. The browser logs such a response on the console, and the desk
logs the traceback the server sends with it; both lines are judged by the status of the response instead.
"""

import re
from collections.abc import Callable
from urllib.parse import parse_qs

from playwright.sync_api import ConsoleMessage, Download, Locator, Page, Request, Response, Route, expect

REFUSED_RESOURCE = re.compile(r"Failed to load resource: the server responded with a status of 4\d\d\b")
SERVER_TRACEBACK = "Traceback (most recent call last):"
DOC_METHOD = "/api/method/run_doc_method"
# The entries of the sidebar of the module, and those of them that are groups (frappe/public/js/frappe/ui/sidebar).
SIDEBAR_ENTRIES = ".body-sidebar .sidebar-items > .sidebar-item-container"
CLOSED_GROUPS = f"{SIDEBAR_ENTRIES}.section-item:has(> .nested-container.hidden) > .standard-sidebar-item"
# Each entry of the sidebar with its label, the symbol of its icon, whether the page draws that symbol, and the
# entries of its group with whether they carry an icon. The desk fetches its sprites once the page has loaded
# (include_icons in frappe/utils/jinja_globals.py), so the script waits up to five seconds for every symbol.
SIDEBAR_SCRIPT = """async (selector) => {
	const entries = () => Array.from(document.querySelectorAll(selector));
	const row = (entry) => entry.querySelector(":scope > .standard-sidebar-item");
	const label = (element) => element.querySelector(".sidebar-item-label")?.textContent.trim() ?? "";
	const symbol = (entry) => (row(entry).querySelector(".sidebar-item-icon use")?.getAttribute("href") ?? "").slice(1);
	const drawn = (entry) => {
		const box = row(entry).querySelector(".sidebar-item-icon svg")?.getBoundingClientRect();
		const found = symbol(entry) && document.getElementById(symbol(entry));
		return Boolean(found && found.tagName === "symbol" && box && box.width > 0 && box.height > 0);
	};
	for (let wait = 0; wait < 50 && !entries().every(drawn); wait++) {
		await new Promise((resolve) => setTimeout(resolve, 100));
	}
	return entries().map((entry) => ({
		label: label(row(entry)),
		symbol: symbol(entry),
		drawn: drawn(entry),
		group: Array.from(entry.querySelectorAll(":scope > .nested-container > .sidebar-item-container"), (child) => ({
			label: label(child),
			icon: child.querySelector(".sidebar-item-icon") !== null,
		})),
	}));
}"""
# The sections of the workspace in their order, each with the labels of its shortcuts.
WORKSPACE_SCRIPT = """() => {
	const sections = [];
	for (const block of document.querySelectorAll("#editorjs .ce-block")) {
		const header = block.querySelector(".ce-header");
		const shortcut = block.querySelector(".shortcut-widget-box");
		if (header) {
			sections.push([header.textContent.trim(), []]);
		} else if (shortcut && sections.length) {
			sections[sections.length - 1][1].push(shortcut.getAttribute("aria-label"));
		}
	}
	return sections;
}"""


class Desk:
	def __init__(self, page: Page):
		self.page = page
		self.problems: list[str] = []
		# What the server answered with an exception, for the report of a failed test.
		self.tracebacks: list[str] = []
		self.requests: list[Request] = []
		page.on("console", self._on_console)
		page.on("pageerror", lambda error: self.problems.append(f"JavaScript error: {error}"))
		page.on("request", self._on_request)
		page.on("response", self._on_response)

	def _on_request(self, request: Request) -> None:
		self.requests.append(request)

	def _on_console(self, message: ConsoleMessage) -> None:
		if message.type != "error" or REFUSED_RESOURCE.match(message.text):
			return
		if message.text.startswith(SERVER_TRACEBACK):
			self.tracebacks.append(message.text)
			return
		self.problems.append(f"console error: {message.text} ({message.location.get('url')})")

	def _on_response(self, response: Response) -> None:
		missing_asset = response.status == 404 and "/assets/" in response.url
		if response.status >= 500 or missing_asset:
			self.problems.append(f"HTTP {response.status}: {response.request.method} {response.url}")

	def open(self, route: str) -> None:
		"""Open a route of the desk and wait until the page has loaded what it asks for."""
		self.page.goto(route)
		self.settle()

	def settle(self) -> None:
		"""Wait until the desk has no request open, so that a late answer still counts for the test.

		The desk is one page: after the first load, it asks the server without loading a page again, and
		frappe.request counts these requests."""
		self.page.wait_for_load_state("networkidle")
		self.page.wait_for_function("() => !window.frappe?.request || frappe.request.ajax_count === 0")

	def open_steuern_from_the_rail(self) -> None:
		"""From the apps screen into ERPNext, and through the entry Steuern of its rail."""
		self.page.get_by_text("ERPNext", exact=True).click()
		rail = self.page.get_by_role("navigation", name="Apps")
		rail.get_by_role("button", name="Steuern", exact=True).click()

	def open_sidebar_groups(self) -> None:
		"""Open each group of the sidebar that is closed, as a click on its heading does."""
		closed = self.page.locator(CLOSED_GROUPS)
		for _group in range(closed.count()):
			closed.first.click()
		expect(closed).to_have_count(0)

	def sidebar(self) -> list[dict]:
		"""What the sidebar draws: each entry with its label and its icon, a group with its entries."""
		return self.page.evaluate(SIDEBAR_SCRIPT, SIDEBAR_ENTRIES)

	def workspace_sections(self) -> list[list]:
		"""The headers of the workspace in their order, each with the shortcuts below it."""
		return self.page.evaluate(WORKSPACE_SCRIPT)

	def button(self, label: str) -> Locator:
		"""A button of the page head, such as Berechnen."""
		return self.page.locator(".page-head").get_by_role("button", name=label, exact=True)

	def menu_item(self, group: str, label: str) -> Locator:
		"""Open a group of buttons of the page head and return one of its items."""
		self.page.locator(f'.page-head .inner-group-button[data-label="{group}"] > button').click()
		return self.page.get_by_role("menuitem", name=label, exact=True)

	def menu(self) -> Locator:
		"""Open the menu of the page head, behind its button with three dots, and return it."""
		self.button("Menü").click()
		return self.page.get_by_role("menu")

	def message(self, text: str) -> Locator:
		"""The block above the fields of the form that shows the text: the intro, the note that the document is
		ready to file and the latest run each have a block of their own."""
		return self.page.locator(".form-message").filter(has_text=text)

	def dialog(self) -> Locator:
		"""The dialog on top of the page."""
		return self.page.locator(".modal.show")

	def answer_dialog(self, yes: bool) -> None:
		"""Answer the question of the dialog on top with Ja or Nein."""
		self.dialog().locator(".btn-modal-primary" if yes else ".btn-modal-secondary").click()

	def close_dialog(self) -> None:
		"""Cancel the dialog on top with its close button once it is shown, and wait until it is gone."""
		self.wait_for_dialog()
		self.dialog().locator(".btn-modal-close").click()
		expect(self.dialog()).to_have_count(0)

	def wait_for_dialog(self) -> None:
		"""Wait until the dialog on top has faded in: a click while it fades in does not reach it. Frappe notes a
		dialog as shown on shown.bs.modal, which Bootstrap fires at the end of the fade (frappe/ui/dialog.js)."""
		self.page.wait_for_function(
			"() => Boolean(window.cur_dialog && cur_dialog.display && cur_dialog.$wrapper.hasClass('show'))"
		)

	def list_rows(self) -> Locator:
		"""The rows of the list view, without its head."""
		return self.page.locator(".list-row-container").filter(has=self.page.locator(".list-row-checkbox"))

	def field(self, fieldname: str) -> Locator:
		"""The control of a field of the form, or of a filter of a report."""
		return self.page.locator(f'.frappe-control[data-fieldname="{fieldname}"]:visible')

	def grid_rows(self, fieldname: str) -> Locator:
		"""The rows of a table of the form, without its head."""
		return self.field(fieldname).locator(".grid-body .grid-row")

	def grid_cells(self, fieldname: str, column: str) -> Locator:
		"""The cells of a column of a table of the form, as its rows show them."""
		return self.grid_rows(fieldname).locator(
			f'.grid-static-col[data-fieldname="{column}"] > .static-area'
		)

	def run_doc_method(self, method: str, click: Callable[[], None]) -> Response:
		"""What the server answers to the method of the document that the click runs."""
		with self.page.expect_response(lambda response: doc_method(response.request) == method) as answer:
			click()
		return answer.value

	def calculate(self) -> None:
		"""Berechnen: calculate saves the document; wait until the form shows the document saved."""
		modified = self.page.evaluate("() => cur_frm.doc.modified")
		response = self.run_doc_method("calculate", self.button("Berechnen").click)
		assert response.ok, f"calculate answered {response.status}: {response.text()[:2000]}"
		self.page.wait_for_function("(before) => cur_frm.doc.modified !== before", arg=modified)
		self.settle()

	def as_if_eric_were_installed(self) -> None:
		"""Load the forms as if an ERiC runtime were installed: the seed simulates, and only with a runtime the
		form asks for the certificate before Testsenden and Senden."""

		def without_simulation(route: Route) -> None:
			response = route.fetch()
			body = response.json()
			for doc in body.get("docs", []):
				elster = doc.get("__onload", {}).get("elster")
				if elster:
					elster["simulation"] = False
			route.fulfill(response=response, json=body)

		self.page.route("**/api/method/frappe.desk.form.load.getdoc?*", without_simulation)

	def download(self, click: Callable[[], None]) -> Download:
		"""What the click downloads: the desk opens the file in a new tab, which closes again."""
		with self.page.expect_download() as download:
			click()
		for page in self.page.context.pages:
			if page is not self.page:
				page.close()
		return download.value

	def called(self, method: str) -> bool:
		"""Whether the page asked the server to run the document method."""
		return any(doc_method(request) == method for request in self.requests)


def doc_method(request: Request) -> str | None:
	"""The method of a document that a request of the desk runs, if it runs one."""
	if not request.url.endswith(DOC_METHOD):
		return None
	return parse_qs(request.post_data or "").get("method", [None])[0]

"""Fixtures of the browser tests: Chromium, the desk as the Administrator or as the user with the role Accounts
User alone, and the documents of the seed.

	pytest steuerbote/tests/e2e --base-url http://localhost:8000

The site runs with the data of seed.py. The test modules import neither pytest nor Playwright, because bench
run-tests imports every test_*.py of the app in the environment of the bench, which has neither; they take
everything from these fixtures, Playwright's expect included. A test fails when one of its pages saw a JavaScript
error, an error on the console or a failed response (desk.py), and a failed test leaves a screenshot of each of
its pages under --output, where the tests of the desk leave those of the sidebar and the workspace and the tests of
the pages the README shows its pictures, named as in docs/bilder.
"""

import json
import re
import secrets
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import pytest
from playwright.sync_api import (
	APIRequestContext,
	APIResponse,
	Browser,
	Error,
	Expect,
	Playwright,
	StorageState,
	expect,
	sync_playwright,
)

from steuerbote.tests.e2e import data
from steuerbote.tests.e2e.desk import Desk

# A busy runner of the CI can take seconds for a page of the desk; a step that passes never waits this long.
TIMEOUT_MS = 30_000
FIRST_DESK_TIMEOUT_MS = 120_000
VIEWPORT = {"width": 1440, "height": 900}
ADMINISTRATOR = "Administrator"

expect.set_options(timeout=TIMEOUT_MS)


def pytest_addoption(parser: pytest.Parser) -> None:
	group = parser.getgroup("steuerbote", "browser tests of Steuerbote")
	group.addoption("--base-url", default="http://localhost:8000", help="the site with the data of seed.py")
	group.addoption(
		"--admin-password",
		default="admin",
		help="the password of the Administrator of the site; admin is the one CI gives its test site",
	)
	group.addoption(
		"--output",
		default="test-results",
		help="where the tests leave screenshots: of the sidebar, the workspace, the pictures of the README and the "
		"pages of a failed test",
	)
	group.addoption("--headed", action="store_true", help="show the browser while the tests run")


def pytest_generate_tests(metafunc: pytest.Metafunc) -> None:
	"""A test that takes list_view runs once for each list of LISTS of its module, as (route, texts)."""
	if "list_view" in metafunc.fixturenames:
		lists = metafunc.module.LISTS
		metafunc.parametrize("list_view", list(lists.items()), ids=list(lists))


@pytest.fixture(scope="session")
def base_url(pytestconfig: pytest.Config) -> str:
	return pytestconfig.getoption("base_url").rstrip("/")


@pytest.fixture(scope="session")
def admin_password(pytestconfig: pytest.Config) -> str:
	return pytestconfig.getoption("admin_password")


@pytest.fixture(scope="session")
def screenshots(pytestconfig: pytest.Config) -> Path:
	"""The directory of --output, for the screenshots a test takes."""
	output = Path(pytestconfig.getoption("output"))
	output.mkdir(parents=True, exist_ok=True)
	return output


@pytest.fixture(scope="session", name="expect")
def playwright_expect() -> Expect:
	return expect


@pytest.fixture(scope="session")
def playwright() -> Iterator[Playwright]:
	with sync_playwright() as playwright:
		yield playwright


@pytest.fixture(scope="session")
def browser(playwright: Playwright, pytestconfig: pytest.Config) -> Iterator[Browser]:
	browser = playwright.chromium.launch(headless=not pytestconfig.getoption("headed"))
	yield browser
	browser.close()


@pytest.fixture(scope="session")
def admin_session(playwright: Playwright, base_url: str, admin_password: str) -> StorageState:
	return logged_in(playwright, base_url, ADMINISTRATOR, admin_password)


@pytest.fixture(scope="session", autouse=True)
def desk_built(admin_session: StorageState) -> None:
	"""Every test starts once the server has built the desk of the Administrator, see logged_in()."""


@pytest.fixture(scope="session")
def accountant_session(playwright: Playwright, base_url: str, admin_password: str) -> StorageState:
	"""The user of the seed with the role Accounts User alone, under a password of this run, which the
	Administrator sets: the seed gives the user none."""
	password = secrets.token_urlsafe(24)
	api = playwright.request.new_context(base_url=base_url)
	try:
		checked(api.post("/api/method/login", form={"usr": ADMINISTRATOR, "pwd": admin_password}))
		checked(
			api.post(
				"/api/method/frappe.core.doctype.user.user.change_password",
				form={"user": data.ACCOUNTANT, "new_password": password},
			)
		)
	finally:
		api.dispose()
	return logged_in(playwright, base_url, data.ACCOUNTANT, password)


@pytest.fixture(scope="session")
def records(playwright: Playwright, base_url: str, admin_session: StorageState) -> dict[str, str]:
	"""The names of the documents of the seed, which their naming series gives them on the site; those of the
	second company, which went to ELSTER, under sent_."""
	api = playwright.request.new_context(base_url=base_url, storage_state=admin_session)
	period = {"company": data.COMPANY, "year": data.YEAR, "period_index": data.MONTH, "docstatus": 0}
	sent = {**period, "company": data.SENT_COMPANY}
	try:
		return {
			"vat_return": only_name(api, "VAT Return", period),
			"statement": only_name(api, "Recapitulative Statement", period),
			"extension": only_name(api, "VAT Return Extension", {"company": data.COMPANY, "year": data.YEAR}),
			"sent_vat_return": only_name(api, "VAT Return", sent),
			"sent_statement": only_name(api, "Recapitulative Statement", sent),
			"sent_extension": only_name(
				api, "VAT Return Extension", {"company": data.SENT_COMPANY, "year": data.YEAR}
			),
		}
	finally:
		api.dispose()


@pytest.fixture
def desk(browser: Browser, base_url: str, admin_session: StorageState) -> Iterator[Desk]:
	"""The desk of the Administrator."""
	with desk_of(browser, base_url, admin_session) as desk:
		yield desk


@pytest.fixture
def accountant(browser: Browser, base_url: str, accountant_session: StorageState) -> Iterator[Desk]:
	"""The desk of the user with the role Accounts User alone."""
	with desk_of(browser, base_url, accountant_session) as desk:
		yield desk


@pytest.fixture
def visitor(browser: Browser, base_url: str) -> Iterator[Desk]:
	"""A browser that has not logged in."""
	with desk_of(browser, base_url, None) as desk:
		yield desk


@contextmanager
def desk_of(browser: Browser, base_url: str, session: StorageState | None) -> Iterator[Desk]:
	context = browser.new_context(
		base_url=base_url,
		storage_state=session,
		viewport=VIEWPORT,
		locale="de-DE",
		timezone_id="Europe/Berlin",
	)
	context.set_default_timeout(TIMEOUT_MS)
	try:
		yield Desk(context.new_page())
	finally:
		context.close()


def logged_in(playwright: Playwright, base_url: str, user: str, password: str) -> StorageState:
	"""A session of the user, whose desk the server has built once: after a cleared cache, as after the seed, the
	first desk of a user takes the server long enough to outlast the timeout of a step."""
	api = playwright.request.new_context(base_url=base_url)
	try:
		checked(api.post("/api/method/login", form={"usr": user, "pwd": password}))
		checked(api.get("/desk", timeout=FIRST_DESK_TIMEOUT_MS))
		return api.storage_state()
	finally:
		api.dispose()


def only_name(api: APIRequestContext, doctype: str, filters: dict) -> str:
	response = checked(
		api.get(f"/api/resource/{doctype}", params={"filters": json.dumps(filters), "fields": '["name"]'})
	)
	names = [row["name"] for row in response.json()["data"]]
	assert len(names) == 1, f"the seed makes one {doctype} with {filters}, the site has {names}"
	return names[0]


def checked(response: APIResponse) -> APIResponse:
	assert response.ok, f"{response.url} answered {response.status}: {response.text()[:2000]}"
	return response


def desks_of(item: pytest.Item) -> list[Desk]:
	return [value for value in getattr(item, "funcargs", {}).values() if isinstance(value, Desk)]


@pytest.hookimpl(wrapper=True)
def pytest_runtest_call(item: pytest.Item):
	"""A test passes only if none of its pages saw an error, including what the desk answers after its last
	step."""
	result = yield
	for desk in desks_of(item):
		desk.settle()
	problems = [problem for desk in desks_of(item) for problem in desk.problems]
	assert not problems, "the browser saw errors:\n" + "\n".join(problems)
	return result


@pytest.hookimpl(wrapper=True)
def pytest_runtest_makereport(item: pytest.Item, call: pytest.CallInfo) -> pytest.TestReport:
	report = yield
	if report.failed and report.when in ("setup", "call"):
		output = Path(item.config.getoption("output"))
		output.mkdir(parents=True, exist_ok=True)
		for index, desk in enumerate(desks_of(item)):
			path = output / f"{re.sub(r'[^A-Za-z0-9_.-]+', '-', item.nodeid)}-{index}.png"
			try:
				desk.page.screenshot(path=path, full_page=True)
			except Error as error:
				path = f"no screenshot: {error}"
			details = [desk.page.url, str(path), *desk.problems, *desk.tracebacks]
			report.sections.append((f"page {index}", "\n".join(details)))
	return report

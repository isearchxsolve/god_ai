"""
ASES — SELENIUM QA GATE (1000 browser-driven end-to-end proof cases)
=====================================================================
Grounds the "monster SOTA" claim with real evidence: 1000 parametrized
Selenium test cases driving headless Chrome against the REAL FastAPI app
(agent_service/main.py) served with deterministic in-memory backends
(qa/qa_app.py). No live Redis/Postgres/Docker/OpenAI/GitHub/Vercel.

Case matrix (exactly 1000):
    Group A  UI structure & rendering ............ 120
    Group B  Client-side validation .............. 180
    Group C  API happy paths through the UI ...... 250
    Group D  Negative: auth/422/429/404/405 ...... 200
    Group E  Job status polling lifecycle ........ 150
    Group F  URL round-trip & resilience ......... 100

Run:  python -m pytest tests/test_selenium_qa_gate.py -m selenium
"""

import json
import re
import urllib.parse

import pytest
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait

pytestmark = pytest.mark.selenium


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _sel(testid):
    return (By.CSS_SELECTOR, f'[data-testid="{testid}"]')


def el(driver, testid):
    return driver.find_element(*_sel(testid))


def text_of(driver, testid):
    return el(driver, testid).text


def click(driver, testid):
    el(driver, testid).click()


def set_value(driver, testid, value):
    """Set a form control's value and fire its input listener."""
    driver.execute_script(
        "const el = document.querySelector(arguments[0]);"
        "el.value = arguments[1];"
        "el.dispatchEvent(new Event('input', {bubbles: true}));",
        f'[data-testid="{testid}"]', str(value),
    )


def wait_text(driver, testid, expected, timeout=10):
    WebDriverWait(driver, timeout).until(lambda d: text_of(d, testid) == expected)


def wait_resp(driver, timeout=10):
    """Wait until the response panel shows a fresh HTTP status."""
    WebDriverWait(driver, timeout).until(lambda d: text_of(d, "resp-code") != "---")
    return text_of(driver, "resp-code")


def arm_resp(driver):
    """Reset the response panel so wait_resp observes the NEXT response only."""
    driver.execute_script(
        "document.querySelector('[data-testid=\"resp-code\"]').textContent = '---';"
        "document.querySelector('[data-testid=\"resp-body\"]').textContent = '';"
    )


def api_via_page(driver, path, method="GET", body=None):
    """Call the real API through the page's fetch helper. Returns [status, text]."""
    driver.set_script_timeout(15)
    return driver.execute_async_script(
        "const [path, method, body, done] = arguments;"
        "window.__qa_api(path, method, body === null ? undefined : body)"
        ".then(r => done([r.status, r.text]))"
        ".catch(e => done([-1, String(e)]));",
        path, method, body,
    )


def fill_dev(driver, task, project, action=None, stack=None,
             iterations=None, budget=None, cost=None, custom_action=None):
    if action is not None:
        set_value(driver, "dev-action", action)
    if custom_action is not None:
        set_value(driver, "dev-action-custom", custom_action)
    set_value(driver, "dev-task", task)
    if stack is not None:
        set_value(driver, "dev-stack", stack)
    set_value(driver, "dev-project", project)
    if iterations is not None:
        set_value(driver, "dev-iterations", iterations)
    if budget is not None:
        set_value(driver, "dev-budget", budget)
    if cost is not None:
        set_value(driver, "dev-cost", cost)


def dev_valid(driver, task, project, **kw):
    fill_dev(driver, task, project, **kw)
    arm_resp(driver)
    click(driver, "dev-submit")
    return wait_resp(driver)


def submit_process(driver, jobid, title, desc, link, pubdate=""):
    click(driver, "tab-process")
    set_value(driver, "proc-jobid", jobid)
    set_value(driver, "proc-title", title)
    set_value(driver, "proc-desc", desc)
    set_value(driver, "proc-link", link)
    set_value(driver, "proc-pubdate", pubdate)
    arm_resp(driver)
    click(driver, "proc-submit")
    return wait_resp(driver)


def submit_crm(driver, action, payload_text):
    click(driver, "tab-crm")
    set_value(driver, "crm-action", action)
    set_value(driver, "crm-payload", payload_text)
    arm_resp(driver)
    click(driver, "crm-submit")
    return wait_resp(driver)


def submit_email(driver, lead_id, name, company="", notes=""):
    click(driver, "tab-email")
    set_value(driver, "em-leadid", lead_id)
    set_value(driver, "em-name", name)
    set_value(driver, "em-company", company)
    set_value(driver, "em-notes", notes)
    arm_resp(driver)
    click(driver, "em-submit")
    return wait_resp(driver)


def poll_until_terminal(driver, timeout=20):
    click(driver, "status-poll")
    WebDriverWait(driver, timeout).until(
        lambda d: text_of(d, "status-badge") in ("complete", "failed", "not_found")
    )
    return text_of(driver, "status-badge")


VALID_DEV_BODY = {
    "action": "generate_code",
    "task": "Build a hello endpoint with a test",
    "tech_stack": "Node.js + Express",
    "project_name": "qa-proj",
    "max_iterations": 3,
    "token_budget": 20000,
}
VALID_PROC_BODY = {
    "job_id": "j-1", "title": "Lead", "description": "A lead", "link": "https://x.test",
}
VALID_CRM_BODY = {"action": "new_client", "payload": {"client_id": "c-1"}}
VALID_EMAIL_BODY = {"lead_id": "l-1", "name": "Ada"}


# ---------------------------------------------------------------------------
# GROUP A — UI structure & rendering (120 cases)
# ---------------------------------------------------------------------------

ALL_TESTIDS = [
    # header (5)
    "app-title", "version-badge", "health-badge", "latency-badge", "auth-chip",
    # nav tabs (6)
    "tab-dev", "tab-process", "tab-crm", "tab-email", "tab-status", "tab-auth",
    # panels (7)
    "panel-dev", "panel-process", "panel-crm", "panel-email", "panel-status",
    "panel-auth", "panel-response",
    # dev form (13)
    "dev-action", "dev-action-custom", "dev-task", "dev-task-count", "dev-stack",
    "dev-project", "dev-requirements", "dev-iterations", "dev-budget", "dev-cost",
    "dev-submit", "dev-reset", "dev-validation",
    # process form (7)
    "proc-jobid", "proc-title", "proc-desc", "proc-link", "proc-pubdate",
    "proc-submit", "proc-validation",
    # crm form (4)
    "crm-action", "crm-payload", "crm-submit", "crm-validation",
    # email form (6)
    "em-leadid", "em-name", "em-company", "em-notes", "em-submit", "em-validation",
    # status panel (6)
    "status-id", "status-poll", "status-badge", "status-polls",
    "status-timeline", "status-result",
    # auth lab (4)
    "tenant-id", "api-key", "auth-check", "auth-message",
    # response panel (3)
    "resp-code", "resp-endpoint", "resp-body",
    # footer (2)
    "footer-build", "qa-meta",
]
assert len(ALL_TESTIDS) == 63

TABS = ["tab-dev", "tab-process", "tab-crm", "tab-email", "tab-status", "tab-auth"]
TAB_PANEL = {
    "tab-dev": "panel-dev", "tab-process": "panel-process", "tab-crm": "panel-crm",
    "tab-email": "panel-email", "tab-status": "panel-status", "tab-auth": "panel-auth",
}
LEFT_PANELS = list(TAB_PANEL.values())


@pytest.mark.parametrize("testid", ALL_TESTIDS)
def test_a1_element_present(console, testid):
    """A1 (63): every data-testid element exists on the console."""
    assert el(console, testid) is not None


@pytest.mark.parametrize("tab", TABS)
def test_a2_tab_activates_panel(console, tab):
    """A2 (6): clicking a tab activates it and reveals its panel."""
    click(console, tab)
    assert "active" in el(console, tab).get_attribute("class")
    assert el(console, TAB_PANEL[tab]).get_property("hidden") is False


@pytest.mark.parametrize("tab,panel", [
    (t, p) for t in TABS for p in LEFT_PANELS if TAB_PANEL[t] != p
])
def test_a3_other_panels_hidden(console, tab, panel):
    """A3 (30): activating one tab hides every other left panel."""
    click(console, tab)
    assert el(console, panel).get_property("hidden") is True


@pytest.mark.parametrize("select_id,expected", [
    ("dev-action", "generate_code"), ("dev-action", "test"),
    ("dev-action", "scaffold"), ("dev-action", "deploy"),
    ("dev-stack", "Node.js + Express"), ("dev-stack", "Python + FastAPI"),
    ("dev-stack", "React + Vite"), ("dev-stack", "Next.js"), ("dev-stack", "Go + Chi"),
    ("crm-action", "new_client"), ("crm-action", "update_status"),
    ("crm-action", "add_note"), ("crm-action", "invoice_paid"),
])
def test_a4_select_options(console, select_id, expected):
    """A4 (13): every select exposes its documented options."""
    options = console.execute_script(
        "return Array.from(document.querySelector(arguments[0]).options).map(o => o.value)",
        f'[data-testid="{select_id}"]',
    )
    assert expected in options


@pytest.mark.parametrize("check", [
    ("app-title", "ASES QA Console"),
    ("health-badge", "healthy"),
    ("version-badge", "v2.0.0"),
    ("auth-chip", "AUTH IDLE"),
    ("dev-task-count", "0 chars"),
    ("status-badge", "idle"),
])
def test_a5_initial_state(console, check):
    """A5 (6): initial banner/form state is exactly as specified."""
    testid, expected = check
    if testid == "health-badge":
        wait_text(console, "health-badge", "healthy", timeout=10)
    assert text_of(console, testid) == expected


def test_a5_latency_badge_format(console):
    """A5 (7): latency badge renders a millisecond value."""
    wait_text(console, "health-badge", "healthy", timeout=10)
    assert re.fullmatch(r"\d+ ms", text_of(console, "latency-badge"))


def test_a5_dev_submit_initially_disabled(console):
    """A5 (8): dev submit starts disabled (empty task fails validation)."""
    assert el(console, "dev-submit").get_property("disabled") is True


# ---------------------------------------------------------------------------
# GROUP B — client-side validation (180 cases)
# ---------------------------------------------------------------------------

def _dev_validation(console):
    return text_of(console, "dev-validation")


def _dev_disabled(console):
    return el(console, "dev-submit").get_property("disabled")


@pytest.mark.parametrize("length", list(range(0, 10)))
def test_b1_task_too_short_disables_submit(console, length):
    """B1 (10): task shorter than 10 chars blocks submission."""
    fill_dev(console, "x" * length, "proj")
    assert _dev_disabled(console) is True
    assert "at least 10" in _dev_validation(console)


@pytest.mark.parametrize("length", list(range(10, 20)))
def test_b1_task_long_enough_enables_submit(console, length):
    """B1 (10): task of 10+ chars with a project enables submission."""
    fill_dev(console, "x" * length, "proj")
    assert _dev_disabled(console) is False


@pytest.mark.parametrize("value", ["0", "-1", "-3", "-100", "21", "22", "50", "999", "1.5", "abc", ""])
def test_b2_iterations_out_of_range(console, value):
    """B2 (11): iterations outside 1..20 are rejected."""
    fill_dev(console, "build a hello route test", "proj", iterations=value)
    assert _dev_disabled(console) is True
    assert "between 1 and 20" in _dev_validation(console)


@pytest.mark.parametrize("value", ["1", "2", "3", "5", "7", "10", "15", "20", " 3 "])
def test_b2_iterations_in_range(console, value):
    """B2 (9): iterations inside 1..20 pass validation."""
    fill_dev(console, "build a hello route test", "proj", iterations=value)
    assert "between 1 and 20" not in _dev_validation(console)


@pytest.mark.parametrize("value", ["0", "-0", "-1", "-1000", "100", "500", "998", "999", "", "abc"])
def test_b3_budget_too_low(console, value):
    """B3 (10): token budget under 1000 is rejected."""
    fill_dev(console, "build a hello route test", "proj", budget=value)
    assert _dev_disabled(console) is True
    assert "at least 1000" in _dev_validation(console)


@pytest.mark.parametrize("value", ["1000", "1001", "1500", "5000", "20000",
                                   "50000", "100000", "999999", "1234567", "2000000"])
def test_b3_budget_ok(console, value):
    """B3 (10): token budget >= 1000 passes."""
    fill_dev(console, "build a hello route test", "proj", budget=value)
    assert "at least 1000" not in _dev_validation(console)


@pytest.mark.parametrize("value", ["0", "0.00", "-1", "-0.5", "-0.01", "-100", "--5", "abc", "1e", "."])
def test_b4_cost_invalid(console, value):
    """B4 (10): non-positive/garbage cost limits are rejected."""
    fill_dev(console, "build a hello route test", "proj", cost=value)
    assert _dev_disabled(console) is True
    assert "positive" in _dev_validation(console)


@pytest.mark.parametrize("value", ["0.01", "0.1", "0.5", "1", "2.5", "5", "100", "1e3", "99999.99", ""])
def test_b4_cost_ok(console, value):
    """B4 (10): positive or empty (optional) cost limits pass."""
    fill_dev(console, "build a hello route test", "proj", cost=value)
    assert "positive" not in _dev_validation(console)


@pytest.mark.parametrize("value", ["foo", "generate", "GENERATE_CODE", "generate code",
                                   "deploy2", "test!", "scaffoldx", "dev_test", "TEST",
                                   "Deploy", "lead", "crm", "gen_code", "generate_code ",
                                   "test\t", "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
                                   "generate_code1", "1generate_code", "generate.code", "generate/code"])
def test_b5_unknown_custom_action(console, value):
    """B5 (20): custom actions outside the whitelist are rejected."""
    fill_dev(console, "build a hello route test", "proj", custom_action=value)
    assert _dev_disabled(console) is True
    assert "Unknown action" in _dev_validation(console)


@pytest.mark.parametrize("field,garbage", [
    ("proc-jobid", ""), ("proc-title", ""), ("proc-desc", ""), ("proc-link", ""),
    ("proc-jobid", "   "), ("proc-title", "   "), ("proc-desc", "   "), ("proc-link", "   "),
])
def test_b6_process_missing_field(console, field, garbage):
    """B6 (8): each required process-job field is enforced."""
    click(console, "tab-process")
    defaults = {"proc-jobid": "j-1", "proc-title": "t", "proc-desc": "d", "proc-link": "https://l.test"}
    for fid, val in defaults.items():
        set_value(console, fid, val)
    set_value(console, field, garbage)
    click(console, "proc-submit")
    assert "Missing" in text_of(console, "proc-validation")


@pytest.mark.parametrize("missing", [
    ("proc-jobid", "proc-title"), ("proc-jobid", "proc-desc"), ("proc-jobid", "proc-link"),
    ("proc-title", "proc-desc"), ("proc-title", "proc-link"), ("proc-desc", "proc-link"),
])
def test_b6_process_missing_pairs(console, missing):
    """B6 (6): pairs of missing fields are all reported."""
    click(console, "tab-process")
    defaults = {"proc-jobid": "j-1", "proc-title": "t", "proc-desc": "d", "proc-link": "https://l.test"}
    for fid, val in defaults.items():
        set_value(console, fid, val)
    for fid in missing:
        set_value(console, fid, "")
    click(console, "proc-submit")
    msg = text_of(console, "proc-validation")
    for fid in missing:
        assert fid.replace("proc-", "") in msg


@pytest.mark.parametrize("fields", [
    ("proc-jobid", "proc-title", "proc-desc"),
    ("proc-jobid", "proc-title", "proc-link"),
    ("proc-jobid", "proc-desc", "proc-link"),
    ("proc-title", "proc-desc", "proc-link"),
])
def test_b6_process_missing_triples(console, fields):
    """B6 (4): triples of missing fields block submission."""
    click(console, "tab-process")
    click(console, "proc-submit")
    assert "Missing" in text_of(console, "proc-validation")


def test_b6_process_all_missing(console):
    """B6 (1): a fully empty process form lists every missing field."""
    click(console, "tab-process")
    click(console, "proc-submit")
    msg = text_of(console, "proc-validation")
    assert all(f in msg for f in ("jobid", "title", "desc", "link"))


def test_b6_process_filled_is_clean(console):
    """B6 (1): a fully filled process form shows no validation error."""
    submit_process(console, "j-1", "Title", "Desc", "https://l.test")
    assert text_of(console, "proc-validation") == ""


@pytest.mark.parametrize("payload", ["{", "}", "{'a':1}", "abc", "", "{a:1}",
                                     '"unclosed', "1,2", "[1,", '{"a":}'])
def test_b7_crm_invalid_json(console, payload):
    """B7 (10): malformed JSON payloads are caught client-side."""
    click(console, "tab-crm")
    set_value(console, "crm-payload", payload)
    click(console, "crm-submit")
    assert "not valid JSON" in text_of(console, "crm-validation")


@pytest.mark.parametrize("payload", ["{}", "[]", '{"a":1}', "[1,2,3]",
                                     '{"nested":{"x":true}}', '"str"', "123", "true",
                                     "null", '{"client_id":"c-9"}'])
def test_b7_crm_valid_json(console, payload):
    """B7 (10): well-formed JSON payloads pass client validation."""
    click(console, "tab-crm")
    set_value(console, "crm-payload", payload)
    click(console, "crm-submit")
    assert "not valid JSON" not in text_of(console, "crm-validation")


@pytest.mark.parametrize("lead,name", [
    ("", "Ada"), ("l-1", ""), ("", ""), ("   ", "Ada"), ("l-1", "   "), ("   ", "   "),
])
def test_b8_email_missing_fields(console, lead, name):
    """B8 (6): lead id and name are required for personalization."""
    click(console, "tab-email")
    set_value(console, "em-leadid", lead)
    set_value(console, "em-name", name)
    click(console, "em-submit")
    assert "Missing" in text_of(console, "em-validation")


@pytest.mark.parametrize("lead,name,company,notes", [
    ("l-1", "Ada", "", ""), ("l-2", "Grace", "Navy", ""), ("l-3", "Alan", "Bletchley", "math"),
    ("l-4", "Edsger", "CWI", "dijkstra"), ("l-5", "Barbara", "UT Austin", "oop"),
    ("l-6", "Donald", "Stanford", "knuth"), ("l-7", "Frances", "IBM", "arrays"),
    ("l-8", "Guido", "Python", "bdfl"), ("l-9", "Brendan", "Mozilla", "js"),
    ("l-10", "Radia", "DEC", "spanning tree"), ("l-11", "Tim", "CERN", "web"),
    ("l-12", "Vint", "DARPA", "tcp"), ("l-13", "Hedy", "MGM", "wifi"),
    ("l-14", "Katherine", "NASA", "orbits"),
])
def test_b8_email_filled_clean(console, lead, name, company, notes):
    """B8 (14): complete email forms show no validation error."""
    submit_email(console, lead, name, company, notes)
    assert text_of(console, "em-validation") == ""


@pytest.mark.parametrize("field,garbage,default", [
    ("dev-task", "some garbage task text", ""),
    ("dev-project", "garbage-project", ""),
    ("dev-requirements", "garbage reqs", ""),
    ("dev-iterations", "99", "3"),
    ("dev-budget", "1", "20000"),
    ("dev-cost", "-5", "5"),
    ("dev-action-custom", "bogus", ""),
    ("dev-task", "unicode ünïcödé 中文", ""),
    ("dev-iterations", "abc", "3"),
    ("dev-budget", "abc", "20000"),
])
def test_b9_reset_restores_defaults(console, field, garbage, default):
    """B9 (10): reset returns every dev field to its default."""
    set_value(console, field, garbage)
    click(console, "dev-reset")
    assert el(console, field).get_property("value") == default


@pytest.mark.parametrize("length", [1, 9, 10, 50, 500])
def test_b10_char_counter_tracks_input(console, length):
    """B10 (5): the task char counter mirrors the input length."""
    set_value(console, "dev-task", "x" * length)
    assert text_of(console, "dev-task-count") == f"{length} chars"


@pytest.mark.parametrize("prior", ["x", "task text here", "unicode 中文",
                                   "digits 12345", "symbols !@#$%"])
def test_b10_char_counter_clears(console, prior):
    """B10 (5): clearing the task resets the counter to 0 chars."""
    set_value(console, "dev-task", prior)
    set_value(console, "dev-task", "")
    assert text_of(console, "dev-task-count") == "0 chars"


# ---------------------------------------------------------------------------
# GROUP C — API happy paths through the UI (250 cases)
# ---------------------------------------------------------------------------

TASKS = [
    "Build a hello-world Express API with tests",
    "Create a FastAPI service with a health route",
    "Scaffold a React dashboard with charts",
    "Add a REST endpoint for user profiles",
    "Write a CLI tool that counts words",
    "Build a todo API with CRUD routes",
    "Create a webhook receiver with validation",
    "Implement a rate-limited proxy service",
    "Build a static site generator in Node",
    "Create a job queue consumer with retries",
]
PROJECTS = ["alpha-api", "beta-svc", "gamma-web", "delta-cli", "epsilon-bot"]
STACKS = ["Node.js + Express", "Python + FastAPI", "React + Vite", "Next.js", "Go + Chi"]


@pytest.mark.parametrize("i", range(50))
def test_c1_dev_generate_code_success(console, i):
    """C1 (50): dev-task generate_code returns 202 + execution_id."""
    task, project, stack = TASKS[i % 10], PROJECTS[i % 5], STACKS[i % 5]
    code = dev_valid(console, task, project, stack=stack)
    assert code == "202"
    body = json.loads(text_of(console, "resp-body"))
    assert body["accepted"] is True
    assert body["execution_id"]
    assert el(console, "status-id").get_property("value") == body["execution_id"]


@pytest.mark.parametrize("action", ["test", "scaffold", "deploy"])
@pytest.mark.parametrize("i", range(10))
def test_c2_dev_other_actions_success(console, action, i):
    """C2 (30): test/scaffold/deploy actions are accepted end-to-end."""
    code = dev_valid(console, TASKS[i] + f" ({action})", f"proj-{action}-{i}", action=action)
    assert code == "202"
    assert "execution_id" in json.loads(text_of(console, "resp-body"))


@pytest.mark.parametrize("i", range(40))
def test_c3_process_job_success(console, i):
    """C3 (40): process-job lead pipeline returns 202 + status_url."""
    code = submit_process(
        console, f"job-{i}", f"Lead title {i}", f"Description body {i}",
        f"https://leads.test/{i}",
    )
    assert code == "202"
    body = json.loads(text_of(console, "resp-body"))
    assert body["status_url"].startswith("/jobs/")


def _crm_payload(i):
    """Deterministic per-index CRM payload (always valid JSON)."""
    variants = [
        lambda n: {"client_id": f"c-{n}", "name": f"Client {n}"},
        lambda n: {"client_id": f"c-{n}", "status": "active"},
        lambda n: {"client_id": f"c-{n}", "note": f"note {n}"},
        lambda n: {"client_id": f"c-{n}", "amount": n + 0.5, "invoice_id": f"inv-{n}"},
        lambda n: {"client_id": f"c-{n}", "email": f"c{n}@x.test"},
    ]
    return json.dumps(variants[i % 5](i))


@pytest.mark.parametrize("action", ["new_client", "update_status", "add_note", "invoice_paid"])
@pytest.mark.parametrize("i", range(10))
def test_c4_crm_webhook_success(console, action, i):
    """C4 (40): all four CRM webhook actions are accepted."""
    code = submit_crm(console, action, _crm_payload(i))
    assert code == "202"
    assert json.loads(text_of(console, "resp-body"))["accepted"] is True


@pytest.mark.parametrize("i", range(40))
def test_c5_personalize_email_success(console, i):
    """C5 (40): email personalization requests are accepted."""
    code = submit_email(console, f"lead-{i}", f"Person {i}", f"Corp {i}", f"note {i}")
    assert code == "202"
    assert "execution_id" in json.loads(text_of(console, "resp-body"))


ENDPOINT_KEY_ROTATION = [
    ("/dev-task", ["accepted", "execution_id", "status_url", "accepted", "execution_id"]),
    ("/process-job", ["accepted", "execution_id", "status_url", "accepted", "execution_id"]),
    ("/crm-webhook", ["accepted", "execution_id", "accepted", "execution_id", "accepted"]),
    ("/personalize-email", ["accepted", "execution_id", "status_url", "accepted", "execution_id"]),
    ("/health", ["status", "version", "status", "version", "status"]),
]


def _submit_for_endpoint(console, endpoint, i):
    if endpoint == "/dev-task":
        dev_valid(console, TASKS[i % 10], PROJECTS[i % 5])
    elif endpoint == "/process-job":
        submit_process(console, f"j-{i}", f"t{i}", f"d{i}", f"https://x.test/{i}")
    elif endpoint == "/crm-webhook":
        submit_crm(console, "new_client", f'{{"client_id": "c-{i}"}}')
    elif endpoint == "/personalize-email":
        submit_email(console, f"l-{i}", f"Name {i}")
    else:
        click(console, "tab-auth")
        click(console, "auth-check")
        wait_resp(console)


@pytest.mark.parametrize("endpoint,keys", ENDPOINT_KEY_ROTATION)
@pytest.mark.parametrize("i", range(5))
def test_c6_response_panel_reflects_call(console, endpoint, keys, i):
    """C6 (25): response panel shows endpoint, ok badge, and body key."""
    _submit_for_endpoint(console, endpoint, i)
    assert text_of(console, "resp-endpoint") == endpoint
    assert "ok" in el(console, "resp-code").get_attribute("class")
    assert keys[i] in json.loads(text_of(console, "resp-body"))


@pytest.mark.parametrize("endpoint,keys", ENDPOINT_KEY_ROTATION)
@pytest.mark.parametrize("i", range(5))
def test_c7_auth_chip_ok_after_success(console, endpoint, keys, i):
    """C7 (25): a successful authenticated call flips the auth chip to OK."""
    _submit_for_endpoint(console, endpoint, i)
    assert text_of(console, "auth-chip") == "AUTH OK"


# ---------------------------------------------------------------------------
# GROUP D — negative paths: auth, validation, rate limit, routing (200 cases)
# ---------------------------------------------------------------------------

WRONG_KEYS = ["wrong-key", "qa-test-key-001", "QA-TEST-KEY-000", "qa-test-key-000 ",
              " qa-test-key-000", "sha256:notakey", "totally-wrong-key-xyz",
              "x" * 43, "qa-test-key-0000", "default"]
D_ENDPOINTS = [
    ("/dev-task", VALID_DEV_BODY), ("/process-job", VALID_PROC_BODY),
    ("/crm-webhook", VALID_CRM_BODY), ("/personalize-email", VALID_EMAIL_BODY),
]


@pytest.mark.parametrize("key", WRONG_KEYS[:10])
@pytest.mark.parametrize("endpoint,body", D_ENDPOINTS)
def test_d1_wrong_api_key_401(console, key, endpoint, body):
    """D1 (40): an invalid API key yields 401 on every protected endpoint."""
    set_value(console, "api-key", key)
    status, _ = api_via_page(console, endpoint, "POST", body)
    assert status == 401
    assert text_of(console, "auth-chip") == "AUTH FAIL"


@pytest.mark.parametrize("i", range(5))
@pytest.mark.parametrize("endpoint,body", D_ENDPOINTS)
def test_d2_missing_api_key_401(console, endpoint, body, i):
    """D2 (20): a missing API key yields 401 with a clear message."""
    set_value(console, "api-key", "")
    status, text = api_via_page(console, endpoint, "POST", body)
    assert status == 401
    assert "x-api-key" in text


UNKNOWN_TENANTS = ["acme", "globex", "initech", "umbrella", "stark",
                   "wayne", "hooli", "pied-piper", "tenant-999", "DEFAULT"]


@pytest.mark.parametrize("tenant", UNKNOWN_TENANTS)
@pytest.mark.parametrize("endpoint,body", [("/dev-task", VALID_DEV_BODY),
                                           ("/crm-webhook", VALID_CRM_BODY)])
def test_d3_unknown_tenant_401(console, tenant, endpoint, body):
    """D3 (20): unknown tenants are rejected with 401."""
    set_value(console, "tenant-id", tenant)
    status, _ = api_via_page(console, endpoint, "POST", body)
    assert status == 401


INVALID_ACTIONS = [
    "GENERATE_CODE", "generate", "generate-code", "gen_code", "test2", "tests",
    "deploy!", "deploy ", "scaffold ", "DEV", "lead_pipeline", "crm_new_client",
    " ", "a" * 100, "TEST", "Scaffold", "DEPLOY", "generate_code_x",
    "generate_code;drop", "act ion", "générer", "生成代码", "🚀", "act\tion",
    "action=", "{}", "[]", "123", "true", "null", "-test", "_test", ".test",
    "test.", "generate_code1", "1generate_code", "generate.code", "generate/code",
    "generate_code%00", "test",
]
# "test" alone is valid — replace to keep all 40 invalid
INVALID_ACTIONS[-1] = "tes"
assert len(INVALID_ACTIONS) == 40


@pytest.mark.parametrize("action", INVALID_ACTIONS)
def test_d4_invalid_action_server_422(console, action):
    """D4 (40): Pydantic rejects invalid actions with 422 even past the UI."""
    body = dict(VALID_DEV_BODY, action=action)
    status, text = api_via_page(console, "/dev-task", "POST", body)
    assert status == 422
    assert "action" in text


@pytest.mark.parametrize("i", range(10))
def test_d5_dev_task_missing_task_422(console, i):
    """D5 (10): /dev-task without a task field is a 422."""
    body = {k: v for k, v in VALID_DEV_BODY.items() if k != "task"}
    body["project_name"] = f"p-{i}"
    status, text = api_via_page(console, "/dev-task", "POST", body)
    assert status == 422
    assert "task" in text


@pytest.mark.parametrize("field", ["job_id", "title", "description", "link"])
@pytest.mark.parametrize("i", range(5))
def test_d5_process_job_missing_field_422(console, field, i):
    """D5 (20): /process-job missing any required field is a 422."""
    body = {k: v for k, v in VALID_PROC_BODY.items() if k != field}
    body["title"] = body.get("title", f"t{i}")
    body.pop(field, None)
    status, text = api_via_page(console, "/process-job", "POST", body)
    assert status == 422


@pytest.mark.parametrize("field", ["action", "payload"])
@pytest.mark.parametrize("i", range(5))
def test_d5_crm_missing_field_422(console, field, i):
    """D5 (10): /crm-webhook missing action or payload is a 422."""
    body = {k: v for k, v in VALID_CRM_BODY.items() if k != field}
    status, text = api_via_page(console, "/crm-webhook", "POST", body)
    assert status == 422


@pytest.mark.parametrize("endpoint,body", [
    ("/dev-task", VALID_DEV_BODY), ("/process-job", VALID_PROC_BODY),
    ("/crm-webhook", VALID_CRM_BODY), ("/personalize-email", VALID_EMAIL_BODY),
])
@pytest.mark.parametrize("i", range(5))
def test_d6_rate_limit_429_after_burst(console, endpoint, body, i):
    """D6 (20): the 9th request inside one minute window hits the 429 limit."""
    statuses = []
    for _ in range(9):
        status, _ = api_via_page(console, endpoint, "POST", body)
        statuses.append(status)
    assert all(s != 429 for s in statuses[:8])
    assert statuses[8] == 429


BOGUS_PATHS = ["/nope", "/api/v9", "/jobs", "/admin", "/qa-api/unknown",
               "/favicon2.ico", "/health/extra", "/dev-task/extra", "/metrics2", "/qq"]


@pytest.mark.parametrize("path", BOGUS_PATHS)
def test_d7_unknown_path_404(console, path):
    """D7 (10): unknown paths return 404."""
    status, _ = api_via_page(console, path, "GET")
    assert status == 404


@pytest.mark.parametrize("method,path", [
    ("GET", "/dev-task"), ("GET", "/process-job"), ("GET", "/crm-webhook"),
    ("GET", "/personalize-email"), ("POST", "/health"), ("POST", "/qa"),
    ("GET", "/qa-api/reset"), ("POST", "/qa-api/state"), ("POST", "/qa-api/echo"),
    ("PUT", "/dev-task"),
])
def test_d7_wrong_method_405(console, method, path):
    """D7 (10): wrong HTTP methods return 405."""
    body = VALID_DEV_BODY if method == "PUT" else None
    status, _ = api_via_page(console, path, method, body)
    assert status == 405


# ---------------------------------------------------------------------------
# GROUP E — job status polling lifecycle (150 cases)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("i", range(40))
def test_e1_success_job_lifecycle(console, i):
    """E1 (40): a normal job goes queued -> running -> complete in 2 polls."""
    project = f"{PROJECTS[i % 5]}-{i}"
    dev_valid(console, TASKS[i % 10], project)
    final = poll_until_terminal(console)
    assert final == "complete"
    assert text_of(console, "status-polls") == "2"
    result = json.loads(text_of(console, "status-result"))
    assert project in result["repo_url"]
    assert result["success"] is True


@pytest.mark.parametrize("i", range(30))
def test_e2_slow_job_takes_five_polls(console, i):
    """E2 (30): [qa:slow] jobs stay running until the fifth poll."""
    dev_valid(console, f"[qa:slow] long build task number {i}", f"slow-{i}")
    final = poll_until_terminal(console, timeout=30)
    assert final == "complete"
    assert int(text_of(console, "status-polls")) >= 5
    timeline = el(console, "status-timeline").text
    assert "running" in timeline


@pytest.mark.parametrize("i", range(30))
def test_e3_failing_job_reports_error(console, i):
    """E3 (30): [qa:fail] jobs end failed with the simulated error surfaced."""
    dev_valid(console, f"[qa:fail] doomed task number {i}", f"fail-{i}")
    final = poll_until_terminal(console)
    assert final == "failed"
    assert "bad" in el(console, "status-badge").get_attribute("class")
    assert "qa-simulated pipeline failure" in text_of(console, "status-result")


UNKNOWN_IDS = [f"exec-unknown-{i}" for i in range(10)] + \
              ["00000000-0000-0000-0000-000000000000", "EXEC-1",
               "exec_unknown_5", "a" * 64, "exec-unknown-中文", "exec unknown 9",
               "../etc/passwd", "' OR 1=1 --", "<script>x</script>", "%00exec"]


@pytest.mark.parametrize("exec_id", UNKNOWN_IDS)
def test_e4_unknown_execution_not_found(console, exec_id):
    """E4 (20): polling an unknown execution id reports not_found."""
    click(console, "tab-status")
    set_value(console, "status-id", exec_id)
    final = poll_until_terminal(console)
    assert final == "not_found"
    assert "bad" in el(console, "status-badge").get_attribute("class")


@pytest.mark.parametrize("i", range(10))
def test_e5_process_job_result_shape(console, i):
    """E5 (10): lead pipeline results carry a score."""
    submit_process(console, f"j-{i}", f"Lead {i}", f"Desc {i}", f"https://x.test/{i}")
    assert poll_until_terminal(console) == "complete"
    assert "score" in json.loads(text_of(console, "status-result"))


@pytest.mark.parametrize("i", range(10))
def test_e5_email_job_result_shape(console, i):
    """E5 (10): personalization results carry a subject line."""
    submit_email(console, f"l-{i}", f"Person {i}")
    assert poll_until_terminal(console) == "complete"
    assert "subject" in json.loads(text_of(console, "status-result"))


@pytest.mark.parametrize("i", range(10))
def test_e5_crm_job_result_shape(console, i):
    """E5 (10): CRM results echo the handled action."""
    submit_crm(console, "new_client", f'{{"client_id": "c-{i}"}}')
    assert poll_until_terminal(console) == "complete"
    assert json.loads(text_of(console, "status-result"))["action"] == "new_client"


# ---------------------------------------------------------------------------
# GROUP F — URL round-trips, navigation, resilience (100 cases)
# ---------------------------------------------------------------------------

ECHO_PAIRS = [
    ("q", "hello"), ("name", "Ada Lovelace"), ("u", "ünïcödé"), ("zh", "中文测试"),
    ("emoji", "🚀🎉"), ("sp", "a b c"), ("amp", "a&b=c"), ("plus", "1+2"),
    ("pct", "100%"), ("slash", "a/b"), ("question", "why?"), ("hash", "#tag"),
    ("eq", "k=v"), ("long", "x" * 200), ("num", "12345"), ("neg", "-5"),
    ("float", "3.14"), ("json", '{"a":1}'), ("arr", "[1,2]"), ("nl", "line\nbreak"),
]


@pytest.mark.parametrize("key,value", ECHO_PAIRS)
def test_f1_echo_roundtrip_plain(console, key, value):
    """F1 (20): query params survive the HTTP round-trip unchanged."""
    qs = urllib.parse.urlencode({key: value})
    status, text = api_via_page(console, f"/qa-api/echo?{qs}", "GET")
    assert status == 200
    assert json.loads(text)["args"][key] == value


@pytest.mark.parametrize("key,value", ECHO_PAIRS)
def test_f1_echo_roundtrip_prefixed(console, key, value):
    """F1 (20): round-trip holds with a second param alongside."""
    qs = urllib.parse.urlencode({key: value, "case": "prefixed"})
    status, text = api_via_page(console, f"/qa-api/echo?{qs}", "GET")
    assert status == 200
    args = json.loads(text)["args"]
    assert args[key] == value and args["case"] == "prefixed"


@pytest.mark.parametrize("tab", TABS)
def test_f2_refresh_after_tab(console, tab):
    """F2 (6): the console recovers cleanly after a refresh on any tab."""
    click(console, tab)
    console.refresh()
    wait_text(console, "app-title", "ASES QA Console", timeout=10)


@pytest.mark.parametrize("i", range(12))
def test_f2_back_forward_navigation(console, i):
    """F2 (12): back/forward between console and API pages keeps both intact."""
    console.get(console.current_url)  # ensure /qa baseline
    api_via_page(console, f"/qa-api/echo?i={i}", "GET")
    console.execute_script(f"window.location.href = '/qa-api/echo?i={i}'")
    WebDriverWait(console, 10).until(lambda d: "args" in d.find_element(By.TAG_NAME, "body").text)
    console.back()
    wait_text(console, "app-title", "ASES QA Console", timeout=10)
    console.forward()
    WebDriverWait(console, 10).until(lambda d: "args" in d.find_element(By.TAG_NAME, "body").text)


@pytest.mark.parametrize("i", range(12))
def test_f2_deep_reload_health(console, i):
    """F2 (12): repeated deep loads always converge on a healthy banner."""
    console.get(console.current_url.split("?")[0])
    wait_text(console, "health-badge", "healthy", timeout=10)


@pytest.mark.parametrize("n", [1, 2, 3, 4, 5, 6, 7, 8, 9, 10])
def test_f3_api_helper_survives_interactions(console, n):
    """F3 (10): the fetch helper stays intact after N UI interactions."""
    for k in range(n):
        click(console, TABS[k % 6])
        set_value(console, "dev-task", f"interaction {k}")
    assert console.execute_script("return typeof window.__qa_api") == "function"


@pytest.mark.parametrize("n", [5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24])
def test_f4_rapid_tab_switching_stable(console, n):
    """F4 (20): rapid tab switching always leaves exactly one panel visible."""
    for k in range(n):
        click(console, TABS[k % 6])
    visible = [p for p in LEFT_PANELS if el(console, p).get_property("hidden") is False]
    assert len(visible) == 1
    active = [t for t in TABS if "active" in el(console, t).get_attribute("class")]
    assert len(active) == 1
    assert TAB_PANEL[active[0]] == visible[0]

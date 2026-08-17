"""
ASES QA Console — proof harness for the 1000-case Selenium gate.

Builds the REAL agent_service FastAPI app (main.app) with every external
dependency replaced by deterministic in-memory fakes:

    Postgres  -> FakePool   (tenants table pre-seeded with a known API key)
    Redis     -> FakeRedis  (rate limiting + prompt cache counters)
    RQ queue  -> fake enqueue/status with a deterministic job lifecycle
                 (queued -> running -> complete/failed, advanced per poll)

On top of that it mounts:
    GET  /qa              real interactive HTML console (forms, tabs, poller)
    GET  /qa-api/state    snapshot of the in-memory job registry
    POST /qa-api/reset    wipe jobs + rate-limit counters between tests
    GET  /qa-api/echo     echoes query params (URL round-trip proofs)

No live Redis, Postgres, Docker, OpenAI, GitHub or Vercel is touched.
The browser tests exercise the genuine HTTP routes, Pydantic validation,
auth dependency and rate limiter — only the backends are simulated.
"""

import hashlib
import os
import sys
import uuid
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AGENT_SERVICE = os.path.join(ROOT, "agent_service")
if AGENT_SERVICE not in sys.path:
    sys.path.insert(0, AGENT_SERVICE)

# Rate-limit knobs must be set BEFORE main.py is imported (read at import time).
os.environ.setdefault("RATE_LIMIT_RPM", "6")
os.environ.setdefault("RATE_LIMIT_BURST", "2")

QA_TENANT = "default"
QA_API_KEY = "qa-test-key-000"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Fake backends
# ---------------------------------------------------------------------------

class FakeRedis:
    """Minimal in-memory Redis: enough for rate limiting + prompt cache."""

    def __init__(self):
        self.store = {}

    def incr(self, key):
        self.store[key] = int(self.store.get(key, 0)) + 1
        return self.store[key]

    def expire(self, key, seconds):
        return True

    def get(self, key):
        return self.store.get(key)

    def set(self, key, value, *a, **kw):
        self.store[key] = value
        return True

    def setex(self, key, ttl, value):
        self.store[key] = value
        return True

    def delete(self, *keys):
        for k in keys:
            self.store.pop(k, None)

    def ping(self):
        return True

    def flushall(self):
        self.store.clear()


FAKE_REDIS = FakeRedis()


class FakePool:
    """asyncpg-shaped in-memory pool. Only the queries ASES issues matter."""

    def __init__(self):
        self.tenants = {
            QA_TENANT: {
                "id": str(uuid.uuid4()),
                "api_key_hash": hashlib.sha256(QA_API_KEY.encode()).hexdigest(),
                "status": "active",
            }
        }
        self.executions = []

    async def fetchval(self, query, *args):
        q = query.lower()
        if "api_key_hash" in q:
            t = self.tenants.get(args[0])
            if t and t["status"] == "active":
                return t["api_key_hash"]
            return None
        if "select id from tenants" in q:
            t = self.tenants.get(args[0])
            return t["id"] if t else None
        return None

    async def fetchrow(self, query, *args):
        return None

    async def fetch(self, query, *args):
        return []

    async def execute(self, query, *args):
        self.executions.append((query, args))
        return "INSERT 0 1"


FAKE_POOL = FakePool()


# ---------------------------------------------------------------------------
# Fake job queue with a deterministic, poll-driven lifecycle
# ---------------------------------------------------------------------------

JOBS = {}

SLOW_POLLS = 5      # [qa:slow] jobs stay running until the 5th poll
TERMINAL_POLLS = 2  # normal jobs reach a terminal state on the 2nd poll


def _simulate_result(task_type, payload):
    """Deterministic pipeline result derived from task_type + payload."""
    task = str(payload.get("task", ""))
    if "[qa:fail]" in task:
        return {
            "success": False,
            "error": "qa-simulated pipeline failure",
            "tokens_used": 250,
            "cost_usd": 0.002,
            "iterations": 1,
            "logs": "qa-simulated failure path",
        }

    project = payload.get("project_name") or "qa-project"
    if task_type == "dev_generate_code":
        return {
            "success": True,
            "repo_url": f"https://github.com/qa/{project}",
            "preview_url": f"https://{project}.qa.vercel.app",
            "iterations": 1,
            "tokens_used": 1234,
            "cost_usd": 0.0123,
            "duration_seconds": 4.2,
            "files_generated": ["src/index.js", "tests/smoke.test.js"],
            "clarity_score": 9.0,
            "logs": "qa-simulated success",
        }
    if task_type in ("dev_test", "dev_scaffold", "dev_deploy"):
        return {
            "success": True,
            "action": task_type.replace("dev_", ""),
            "tokens_used": 512,
            "cost_usd": 0.005,
            "logs": "qa-simulated success",
        }
    if task_type == "lead_pipeline":
        return {"success": True, "score": 87, "proposal": "qa-simulated proposal"}
    if task_type == "outreach_personalize":
        return {
            "success": True,
            "subject": f"QA intro for {payload.get('name', 'lead')}",
            "body": "qa-simulated personalized email body",
        }
    if task_type.startswith("crm_"):
        return {"success": True, "action": task_type.replace("crm_", "")}
    return {"success": True, "logs": "qa-simulated generic result"}


def fake_enqueue(task_type, payload, tenant_id, execution_id):
    JOBS[execution_id] = {
        "task_type": task_type,
        "payload": payload,
        "tenant_id": tenant_id,
        "polls": 0,
        "status": "queued",
        "enqueued_at": _now_iso(),
        "started_at": None,
        "ended_at": None,
        "result": None,
        "error": None,
    }
    return execution_id


def fake_status(execution_id):
    job = JOBS.get(execution_id)
    if job is None:
        return {"status": "not_found", "execution_id": execution_id}

    job["polls"] += 1
    task = str(job["payload"].get("task", ""))
    slow = "[qa:slow]" in task
    terminal_at = SLOW_POLLS if slow else TERMINAL_POLLS

    if job["polls"] == 1:
        job["status"] = "running"
        job["started_at"] = _now_iso()
    elif job["polls"] >= terminal_at and job["status"] not in ("complete", "failed"):
        result = _simulate_result(job["task_type"], job["payload"])
        job["result"] = result
        job["status"] = "complete" if result.get("success") else "failed"
        if job["status"] == "failed":
            job["error"] = result.get("error", "unknown error")
        job["ended_at"] = _now_iso()

    resp = {
        "execution_id": execution_id,
        "status": job["status"],
        "enqueued_at": job["enqueued_at"],
        "started_at": job["started_at"],
        "ended_at": job["ended_at"],
    }
    if job["status"] == "complete":
        resp["result"] = job["result"]
    if job["status"] == "failed":
        resp["error"] = job["error"]
    return resp


# ---------------------------------------------------------------------------
# QA console HTML (real UI, served by the real FastAPI app)
# ---------------------------------------------------------------------------

QA_CONSOLE_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>ASES QA Console</title>
<style>
  :root { --ok:#1a7f37; --bad:#cf222e; --warn:#9a6700; --bg:#f6f8fa; --line:#d0d7de; }
  * { box-sizing: border-box; }
  body { font-family: system-ui, sans-serif; margin: 0; background: var(--bg); color: #1f2328; }
  header { display:flex; align-items:center; gap:12px; padding:12px 20px; background:#24292f; color:#fff; }
  header h1 { font-size:18px; margin:0; }
  .badge { padding:2px 10px; border-radius:12px; font-size:12px; font-weight:600; background:#57606a; }
  .badge.ok { background: var(--ok); } .badge.bad { background: var(--bad); } .badge.warn { background: var(--warn); }
  nav { display:flex; gap:4px; padding:8px 20px; background:#fff; border-bottom:1px solid var(--line); }
  nav button { padding:6px 14px; border:1px solid var(--line); background:#fff; border-radius:6px; cursor:pointer; }
  nav button.active { background:#0969da; color:#fff; border-color:#0969da; }
  main { display:grid; grid-template-columns: 1fr 1fr; gap:16px; padding:16px 20px; }
  section.panel { background:#fff; border:1px solid var(--line); border-radius:8px; padding:16px; }
  section.panel[hidden] { display:none; }
  h2 { font-size:15px; margin:0 0 12px; }
  label { display:block; font-size:12px; font-weight:600; margin:8px 0 2px; }
  input, select, textarea { width:100%; padding:6px 8px; border:1px solid var(--line); border-radius:6px; font:inherit; }
  textarea { min-height:60px; resize:vertical; }
  .row { display:flex; gap:10px; } .row > div { flex:1; }
  button.submit { margin-top:12px; padding:8px 18px; border:0; border-radius:6px; background:#0969da; color:#fff; font-weight:600; cursor:pointer; }
  button.submit:disabled { background:#8c959f; cursor:not-allowed; }
  button.ghost { margin-top:12px; margin-left:8px; padding:8px 14px; border:1px solid var(--line); border-radius:6px; background:#fff; cursor:pointer; }
  .validation { margin-top:8px; font-size:12px; color: var(--bad); min-height:16px; }
  .counter { font-size:11px; color:#57606a; }
  pre#resp-body { background:#f6f8fa; border:1px solid var(--line); border-radius:6px; padding:10px; font-size:11px; max-height:220px; overflow:auto; white-space:pre-wrap; }
  ul#status-timeline { margin:8px 0; padding-left:18px; font-size:12px; }
  footer { padding:10px 20px; font-size:11px; color:#57606a; border-top:1px solid var(--line); background:#fff; }
  .chip { display:inline-block; padding:2px 8px; border-radius:10px; font-size:11px; font-weight:700; }
  .chip.ok { background:#dafbe1; color:var(--ok); } .chip.bad { background:#ffebe9; color:var(--bad); }
</style>
</head>
<body>
<header>
  <h1 id="app-title" data-testid="app-title">ASES QA Console</h1>
  <span id="version-badge" class="badge" data-testid="version-badge">v2.0.0</span>
  <span id="health-badge" class="badge" data-testid="health-badge">checking…</span>
  <span id="latency-badge" class="badge" data-testid="latency-badge">-- ms</span>
  <span style="flex:1"></span>
  <span id="auth-chip" class="chip" data-testid="auth-chip">AUTH IDLE</span>
</header>

<nav aria-label="QA sections">
  <button id="tab-dev"     class="tab active" data-testid="tab-dev" data-panel="panel-dev">Dev Task</button>
  <button id="tab-process" class="tab" data-testid="tab-process" data-panel="panel-process">Process Job</button>
  <button id="tab-crm"     class="tab" data-testid="tab-crm" data-panel="panel-crm">CRM Webhook</button>
  <button id="tab-email"   class="tab" data-testid="tab-email" data-panel="panel-email">Personalize Email</button>
  <button id="tab-status"  class="tab" data-testid="tab-status" data-panel="panel-status">Job Status</button>
  <button id="tab-auth"    class="tab" data-testid="tab-auth" data-panel="panel-auth">Auth Lab</button>
</nav>

<main>
  <div>
    <section class="panel" id="panel-dev" data-testid="panel-dev" aria-labelledby="h-dev">
      <h2 id="h-dev">Dev Task</h2>
      <label for="dev-action">Action</label>
      <select id="dev-action" data-testid="dev-action">
        <option value="generate_code">generate_code</option>
        <option value="test">test</option>
        <option value="scaffold">scaffold</option>
        <option value="deploy">deploy</option>
      </select>
      <label for="dev-action-custom">Custom action (negative testing)</label>
      <input id="dev-action-custom" data-testid="dev-action-custom" placeholder="leave blank to use the select">
      <label for="dev-task">Task description</label>
      <textarea id="dev-task" data-testid="dev-task" placeholder="Describe the feature to build (min 10 chars)"></textarea>
      <span id="dev-task-count" class="counter" data-testid="dev-task-count">0 chars</span>
      <div class="row">
        <div><label for="dev-stack">Tech stack</label>
          <select id="dev-stack" data-testid="dev-stack">
            <option>Node.js + Express</option><option>Python + FastAPI</option>
            <option>React + Vite</option><option>Next.js</option><option>Go + Chi</option>
          </select></div>
        <div><label for="dev-project">Project name</label>
          <input id="dev-project" data-testid="dev-project" placeholder="my-api"></div>
      </div>
      <label for="dev-requirements">Requirements</label>
      <input id="dev-requirements" data-testid="dev-requirements" placeholder="optional requirements">
      <div class="row">
        <div><label for="dev-iterations">Max iterations (1–20)</label>
          <input id="dev-iterations" data-testid="dev-iterations" type="number" value="3"></div>
        <div><label for="dev-budget">Token budget (≥1000)</label>
          <input id="dev-budget" data-testid="dev-budget" type="number" value="20000"></div>
        <div><label for="dev-cost">Cost limit USD</label>
          <input id="dev-cost" data-testid="dev-cost" type="number" step="0.01" value="5"></div>
      </div>
      <button class="submit" id="dev-submit" data-testid="dev-submit">Submit dev task</button>
      <button class="ghost" id="dev-reset" data-testid="dev-reset">Reset form</button>
      <div class="validation" id="dev-validation" data-testid="dev-validation" role="alert"></div>
    </section>

    <section class="panel" id="panel-process" data-testid="panel-process" hidden aria-labelledby="h-process">
      <h2 id="h-process">Process Job (lead pipeline)</h2>
      <div class="row">
        <div><label for="proc-jobid">Job ID</label><input id="proc-jobid" data-testid="proc-jobid"></div>
        <div><label for="proc-title">Title</label><input id="proc-title" data-testid="proc-title"></div>
      </div>
      <label for="proc-desc">Description</label>
      <textarea id="proc-desc" data-testid="proc-desc"></textarea>
      <div class="row">
        <div><label for="proc-link">Link</label><input id="proc-link" data-testid="proc-link"></div>
        <div><label for="proc-pubdate">Pub date</label><input id="proc-pubdate" data-testid="proc-pubdate" placeholder="optional"></div>
      </div>
      <button class="submit" id="proc-submit" data-testid="proc-submit">Submit process job</button>
      <div class="validation" id="proc-validation" data-testid="proc-validation" role="alert"></div>
    </section>

    <section class="panel" id="panel-crm" data-testid="panel-crm" hidden aria-labelledby="h-crm">
      <h2 id="h-crm">CRM Webhook</h2>
      <label for="crm-action">Action</label>
      <select id="crm-action" data-testid="crm-action">
        <option value="new_client">new_client</option>
        <option value="update_status">update_status</option>
        <option value="add_note">add_note</option>
        <option value="invoice_paid">invoice_paid</option>
      </select>
      <label for="crm-payload">Payload (JSON)</label>
      <textarea id="crm-payload" data-testid="crm-payload">{"client_id": "c-1", "name": "Ada Lovelace"}</textarea>
      <button class="submit" id="crm-submit" data-testid="crm-submit">Send webhook</button>
      <div class="validation" id="crm-validation" data-testid="crm-validation" role="alert"></div>
    </section>

    <section class="panel" id="panel-email" data-testid="panel-email" hidden aria-labelledby="h-email">
      <h2 id="h-email">Personalize Email</h2>
      <div class="row">
        <div><label for="em-leadid">Lead ID</label><input id="em-leadid" data-testid="em-leadid"></div>
        <div><label for="em-name">Name</label><input id="em-name" data-testid="em-name"></div>
      </div>
      <div class="row">
        <div><label for="em-company">Company</label><input id="em-company" data-testid="em-company"></div>
        <div><label for="em-notes">Notes</label><input id="em-notes" data-testid="em-notes"></div>
      </div>
      <button class="submit" id="em-submit" data-testid="em-submit">Personalize</button>
      <div class="validation" id="em-validation" data-testid="em-validation" role="alert"></div>
    </section>

    <section class="panel" id="panel-status" data-testid="panel-status" hidden aria-labelledby="h-status">
      <h2 id="h-status">Job Status</h2>
      <label for="status-id">Execution ID</label>
      <input id="status-id" data-testid="status-id">
      <button class="submit" id="status-poll" data-testid="status-poll">Poll status</button>
      <p>Status: <span id="status-badge" class="badge" data-testid="status-badge">idle</span>
         Polls: <span id="status-polls" data-testid="status-polls">0</span></p>
      <ul id="status-timeline" data-testid="status-timeline" aria-live="polite"></ul>
      <pre id="status-result" data-testid="status-result"></pre>
    </section>

    <section class="panel" id="panel-auth" data-testid="panel-auth" hidden aria-labelledby="h-auth">
      <h2 id="h-auth">Auth Lab</h2>
      <label for="tenant-id">Tenant ID (x-tenant-id)</label>
      <input id="tenant-id" data-testid="tenant-id" value="default">
      <label for="api-key">API key (x-api-key)</label>
      <input id="api-key" data-testid="api-key" value="qa-test-key-000">
      <button class="submit" id="auth-check" data-testid="auth-check">Check /health</button>
      <div class="validation" id="auth-message" data-testid="auth-message" role="alert"></div>
    </section>
  </div>

  <div>
    <section class="panel" id="panel-response" data-testid="panel-response" aria-labelledby="h-resp">
      <h2 id="h-resp">Last API response</h2>
      <p>HTTP <span id="resp-code" class="badge" data-testid="resp-code">---</span>
         Endpoint: <span id="resp-endpoint" data-testid="resp-endpoint">none</span></p>
      <pre id="resp-body" data-testid="resp-body">no request yet</pre>
    </section>
  </div>
</main>

<footer>
  <span id="footer-build" data-testid="footer-build">ASES QA Console • selenium proof harness • build 1.0</span>
  <span id="qa-meta" data-testid="qa-meta" data-app="ases" data-mode="qa" data-endpoints="6" hidden></span>
</footer>

<script>
(function () {
  "use strict";
  var $ = function (id) { return document.getElementById(id); };

  // ---- tabs -------------------------------------------------------------
  var tabs = document.querySelectorAll("nav .tab");
  tabs.forEach(function (btn) {
    btn.addEventListener("click", function () {
      tabs.forEach(function (b) { b.classList.remove("active"); });
      btn.classList.add("active");
      ["panel-dev","panel-process","panel-crm","panel-email","panel-status","panel-auth"]
        .forEach(function (p) { $(p).hidden = true; });
      $(btn.dataset.panel).hidden = false;
    });
  });

  // ---- health banner ----------------------------------------------------
  function checkHealth() {
    var t0 = performance.now();
    fetch("/health").then(function (r) { return r.json(); }).then(function (j) {
      var dt = Math.round(performance.now() - t0);
      var badge = $("health-badge");
      badge.textContent = j.status;
      badge.className = "badge " + (j.status === "healthy" ? "ok" : "bad");
      $("latency-badge").textContent = dt + " ms";
      $("version-badge").textContent = "v" + j.version;
    }).catch(function () {
      var badge = $("health-badge");
      badge.textContent = "unreachable";
      badge.className = "badge bad";
    });
  }
  checkHealth();
  setInterval(checkHealth, 5000);

  // ---- API helper -------------------------------------------------------
  function api(path, method, body) {
    var headers = {
      "x-tenant-id": $("tenant-id").value || "",
      "x-api-key": $("api-key").value || ""
    };
    if (body !== undefined) headers["Content-Type"] = "application/json";
    return fetch(path, {
      method: method, headers: headers,
      body: body === undefined ? undefined : JSON.stringify(body)
    }).then(function (r) {
      return r.text().then(function (txt) {
        var json = null; try { json = JSON.parse(txt); } catch (e) {}
        $("resp-code").textContent = String(r.status);
        $("resp-code").className = "badge " + (r.status < 400 ? "ok" : "bad");
        $("resp-endpoint").textContent = path;
        $("resp-body").textContent = txt || "(empty)";
        var chip = $("auth-chip");
        if (r.status === 401) { chip.textContent = "AUTH FAIL"; chip.className = "chip bad"; }
        else if (r.status < 400) { chip.textContent = "AUTH OK"; chip.className = "chip ok"; }
        return { status: r.status, json: json, text: txt };
      });
    });
  }
  window.__qa_api = api;

  // ---- dev task form: client-side validation mirrors server rules -------
  var VALID_ACTIONS = ["generate_code", "test", "scaffold", "deploy"];
  function devAction() {
    var custom = $("dev-action-custom").value.trim();
    return custom !== "" ? custom : $("dev-action").value;
  }
  function validateDev() {
    var errors = [];
    var action = devAction();
    var task = $("dev-task").value;
    var project = $("dev-project").value.trim();
    var iterations = parseInt($("dev-iterations").value, 10);
    var budget = parseInt($("dev-budget").value, 10);
    var cost = $("dev-cost").value.trim();

    $("dev-task-count").textContent = task.length + " chars";

    if (VALID_ACTIONS.indexOf(action) === -1) errors.push("Unknown action: " + action);
    if (task.trim().length < 10) errors.push("Task must be at least 10 characters");
    if (action === "generate_code" && project === "") errors.push("Project name is required");
    if (isNaN(iterations) || iterations < 1 || iterations > 20) errors.push("Iterations must be between 1 and 20");
    if (isNaN(budget) || budget < 1000) errors.push("Token budget must be at least 1000");
    if (cost !== "" && !(parseFloat(cost) > 0)) errors.push("Cost limit must be positive");

    $("dev-validation").textContent = errors.join(" | ");
    $("dev-submit").disabled = errors.length > 0;
    return errors.length === 0;
  }
  ["dev-action","dev-action-custom","dev-task","dev-project","dev-iterations","dev-budget","dev-cost"]
    .forEach(function (id) { $(id).addEventListener("input", validateDev); });

  $("dev-reset").addEventListener("click", function () {
    $("dev-action").value = "generate_code";
    $("dev-action-custom").value = "";
    $("dev-task").value = "";
    $("dev-stack").value = "Node.js + Express";
    $("dev-project").value = "";
    $("dev-requirements").value = "";
    $("dev-iterations").value = "3";
    $("dev-budget").value = "20000";
    $("dev-cost").value = "5";
    validateDev();
  });

  $("dev-submit").addEventListener("click", function () {
    if (!validateDev()) return;
    api("/dev-task", "POST", {
      action: devAction(),
      task: $("dev-task").value,
      tech_stack: $("dev-stack").value,
      project_name: $("dev-project").value.trim() || null,
      requirements: $("dev-requirements").value,
      max_iterations: parseInt($("dev-iterations").value, 10),
      token_budget: parseInt($("dev-budget").value, 10),
      cost_limit_usd: $("dev-cost").value.trim() === "" ? null : parseFloat($("dev-cost").value)
    }).then(function (res) {
      if (res.json && res.json.execution_id) {
        $("status-id").value = res.json.execution_id;
      }
    });
  });

  // ---- process job ------------------------------------------------------
  $("proc-submit").addEventListener("click", function () {
    var missing = ["proc-jobid","proc-title","proc-desc","proc-link"]
      .filter(function (id) { return $(id).value.trim() === ""; });
    if (missing.length) {
      $("proc-validation").textContent = "Missing: " + missing.join(", ");
      return;
    }
    $("proc-validation").textContent = "";
    api("/process-job", "POST", {
      job_id: $("proc-jobid").value.trim(),
      title: $("proc-title").value.trim(),
      description: $("proc-desc").value.trim(),
      link: $("proc-link").value.trim(),
      pub_date: $("proc-pubdate").value.trim() || null
    }).then(function (res) {
      if (res.json && res.json.execution_id) $("status-id").value = res.json.execution_id;
    });
  });

  // ---- crm webhook ------------------------------------------------------
  $("crm-submit").addEventListener("click", function () {
    var payload;
    try { payload = JSON.parse($("crm-payload").value); }
    catch (e) { $("crm-validation").textContent = "Payload is not valid JSON"; return; }
    $("crm-validation").textContent = "";
    api("/crm-webhook", "POST", {
      action: $("crm-action").value,
      payload: payload
    }).then(function (res) {
      if (res.json && res.json.execution_id) $("status-id").value = res.json.execution_id;
    });
  });

  // ---- personalize email ------------------------------------------------
  $("em-submit").addEventListener("click", function () {
    var missing = ["em-leadid","em-name"].filter(function (id) { return $(id).value.trim() === ""; });
    if (missing.length) { $("em-validation").textContent = "Missing: " + missing.join(", "); return; }
    $("em-validation").textContent = "";
    api("/personalize-email", "POST", {
      lead_id: $("em-leadid").value.trim(),
      name: $("em-name").value.trim(),
      company: $("em-company").value.trim(),
      notes: $("em-notes").value.trim()
    }).then(function (res) {
      if (res.json && res.json.execution_id) $("status-id").value = res.json.execution_id;
    });
  });

  // ---- status poller (sequential: next poll only after prior response) --
  var polling = false;
  $("status-poll").addEventListener("click", function () {
    var id = $("status-id").value.trim();
    if (!id || polling) return;
    $("status-timeline").innerHTML = "";
    $("status-result").textContent = "";
    var polls = 0;
    polling = true;
    function doPoll() {
      polls += 1;
      api("/jobs/" + encodeURIComponent(id), "GET").then(function (res) {
        var st = res.json ? res.json.status : "http_" + res.status;
        $("status-badge").textContent = st;
        $("status-badge").className = "badge " +
          (st === "complete" ? "ok" : (st === "failed" || st === "not_found" ? "bad" : "warn"));
        $("status-polls").textContent = String(polls);
        var li = document.createElement("li");
        li.textContent = "poll " + polls + ": " + st;
        li.setAttribute("data-poll", String(polls));
        $("status-timeline").appendChild(li);
        if (res.json && (res.json.result || res.json.error)) {
          $("status-result").textContent = JSON.stringify(res.json.result || {error: res.json.error}, null, 2);
        }
        if (["complete","failed","not_found"].indexOf(st) !== -1 || polls >= 20) {
          polling = false;
        } else {
          setTimeout(doPoll, 250);
        }
      });
    }
    doPoll();
  });

  // ---- auth lab ---------------------------------------------------------
  $("auth-check").addEventListener("click", function () {
    api("/health", "GET").then(function (res) {
      $("auth-message").textContent = "HTTP " + res.status + " " + (res.text || "");
    });
  });

  validateDev();
})();
</script>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# App factory — patch fakes onto the real app, then mount QA routes
# ---------------------------------------------------------------------------

_built = False


def build_app():
    """Return the real main.app wired to in-memory fakes + QA routes."""
    global _built

    import db
    import auth
    import main
    import redis_cache

    async def fake_get_db_pool():
        return FAKE_POOL

    async def fake_close_db_pool():
        return None

    async def fake_reconcile():
        return None

    def fake_cleanup(max_age_minutes=None):
        return None

    db.get_db_pool = fake_get_db_pool
    auth.get_db_pool = fake_get_db_pool
    main.close_db_pool = fake_close_db_pool
    main.reconcile_sandboxes_on_startup = fake_reconcile
    main.cleanup_expired_sandboxes = fake_cleanup
    redis_cache._get_redis = lambda: FAKE_REDIS
    main.enqueue_agent_job = fake_enqueue
    main.get_job_status = fake_status

    # Deterministic rate limiting: pin the window key so the per-test counter
    # never straddles a real minute boundary (avoids flaky 429 timing). The
    # counter still resets between tests via /qa-api/reset -> flushall().
    main._rate_limit_key = lambda tenant_id: f"ases:ratelimit:{tenant_id}:qafixed"

    app = main.app

    if not _built:
        from fastapi import Request
        from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

        @app.get("/", include_in_schema=False)
        async def root():
            return RedirectResponse(url="/qa")

        @app.get("/qa", include_in_schema=False)
        async def qa_console():
            return HTMLResponse(QA_CONSOLE_HTML)

        @app.get("/qa-api/state", include_in_schema=False)
        async def qa_state():
            return JSONResponse({
                "jobs": {
                    jid: {"status": j["status"], "task_type": j["task_type"], "polls": j["polls"]}
                    for jid, j in JOBS.items()
                },
                "rate_limit_keys": sorted(
                    k for k in FAKE_REDIS.store if k.startswith("ases:ratelimit:")
                ),
            })

        @app.post("/qa-api/reset", include_in_schema=False)
        async def qa_reset(request: Request):
            JOBS.clear()
            FAKE_REDIS.flushall()
            return JSONResponse({"reset": True})

        @app.get("/qa-api/echo", include_in_schema=False)
        async def qa_echo(request: Request):
            return JSONResponse({
                "path": request.url.path,
                "args": dict(request.query_params),
            })

        _built = True

    return app


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(build_app(), host="127.0.0.1", port=8123)

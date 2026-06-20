// failsafe.cjs -- independent supervisor: HALT -> KILL -> LIQUIDATE -> FLAG
const { spawnSync } = require("child_process");
const fs = require("fs");
const path = require("path");

const HEARTBEAT_FILE = path.join(__dirname, ".heartbeat"); // engine writes Date.now() every 5s
const HALT_FILE      = path.join(__dirname, ".HALT");      // engine MUST refuse new buys if this exists
const INCIDENT_DIR   = path.join(__dirname, "incidents");
const HEALTH_URL     = process.env.HEALTH_URL || "http://127.0.0.1:3000/api/health";
const ENGINE_PM2_NAME = process.env.ENGINE_PM2_NAME || "trading-engine";

const HEARTBEAT_MAX_AGE_MS = 60_000;
const POLL_MS = 10_000;
const MAX_FAILS = 3;

let fails = 0, panicking = false;

async function checkHealth() {
  try {
    const age = Date.now() - Number(fs.readFileSync(HEARTBEAT_FILE, "utf8").trim());
    if (age > HEARTBEAT_MAX_AGE_MS) return `heartbeat stale ${Math.round(age/1000)}s`;
  } catch { return "heartbeat missing"; }
  try {
    const res = await fetch(HEALTH_URL, { signal: AbortSignal.timeout(5000) });
    if (!res.ok) return `health HTTP ${res.status}`;
    const j = await res.json();
    if (j.status && j.status !== "ok") return `health=${j.status}`;
  } catch (e) { return `health unreachable: ${e.message}`; }
  return null;
}

async function alert(text) {
  const msg = `\u{1F6A8} TRADING FAILSAFE\n${new Date().toISOString()}\n${text}`;
  try {
    if (process.env.TELEGRAM_BOT_TOKEN && process.env.TELEGRAM_CHAT_ID) {
      await fetch(`https://api.telegram.org/bot${process.env.TELEGRAM_BOT_TOKEN}/sendMessage`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ chat_id: process.env.TELEGRAM_CHAT_ID, text: msg }),
      });
    }
    if (process.env.ALERT_WEBHOOK_URL) {
      await fetch(process.env.ALERT_WEBHOOK_URL, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ content: msg }), // Discord/Slack-compatible
      });
    }
  } catch (e) { console.error("alert failed", e.message); }
}

function writeIncident(reason, extra) {
  fs.mkdirSync(INCIDENT_DIR, { recursive: true });
  const f = path.join(INCIDENT_DIR, `incident-${Date.now()}.json`);
  fs.writeFileSync(f, JSON.stringify({ at: new Date().toISOString(), reason, ...extra }, null, 2)); // never include keys/env
  return f;
}

function killEngine() {
  // Targeted kill -- never blanket `pkill node` (that kills this failsafe + liquidator)
  if (process.platform === "win32") {
    spawnSync("powershell", ["-Command",
      `Get-CimInstance Win32_Process | ? { $_.CommandLine -match 'trading-engine|live-runner|index.cjs' } | % { Stop-Process -Id $_.ProcessId -Force }`]);
  } else {
    spawnSync("pm2", ["stop", ENGINE_PM2_NAME]); // or: spawnSync("pkill", ["-f", "live-runner"])
  }
}

async function panic(reason) {
  if (panicking) return;
  panicking = true;
  console.error(`[FAILSAFE] PANIC: ${reason}`);

  try { fs.writeFileSync(HALT_FILE, reason); } catch {}            // 1. HALT new buys
  await alert(`PANIC START \u2014 ${reason}\nHalting + killing engine + liquidating...`);

  killEngine();                                                    // 2. KILL engine

  const out = spawnSync(process.execPath, [path.join(__dirname, "dist", "liquidator.cjs")], // 3. LIQUIDATE
    { encoding: "utf8", timeout: 5 * 60_000 });
  const ok = out.status === 0;

  const file = writeIncident(reason, { liquidatorExit: out.status, stdout: out.stdout?.slice(-2000) }); // 4. FLAG
  await alert(`PANIC ${ok ? "RESOLVED \u2705 all positions flat" : "PARTIAL \u26A0\uFE0F check incident"}\n${reason}\nincident: ${path.basename(file)}`);

  // Unattended mode: hand off to the auto-fix orchestrator. It keeps the system
  // HALTED + FLAT until a fix passes tests + a paper canary, then resumes live.
  if (process.env.AUTO_FIX === "true") {
    try {
      const { spawn } = require("child_process");
      const child = spawn(process.execPath, [path.join(__dirname, "autofix.cjs"), file],
        { cwd: __dirname, detached: true, stdio: "ignore" });
      child.unref();
      await alert("AUTO-FIX launched (unattended). System stays HALTED + FLAT until a fix passes tests + paper canary.");
    } catch (e) { await alert(`AUTO-FIX launch failed: ${e.message}`); }
  }

  process.exit(ok ? 0 : 1);
}

process.on("SIGUSR1", () => panic("manual SIGUSR1")); // manual trigger: kill -USR1 <pid>

(async function loop() {
  console.log("[FAILSAFE] watchdog online");
  for (;;) {
    if (fs.existsSync(path.join(__dirname, ".PANIC"))) await panic("manual .PANIC file");
    const problem = await checkHealth();
    if (problem) {
      fails++;
      console.warn(`[FAILSAFE] unhealthy (${fails}/${MAX_FAILS}): ${problem}`);
      if (fails >= MAX_FAILS) await panic(problem);
    } else if (fails) { console.log("[FAILSAFE] recovered"); fails = 0; }
    await new Promise(r => setTimeout(r, POLL_MS));
  }
})();

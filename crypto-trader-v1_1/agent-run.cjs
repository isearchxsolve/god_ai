// agent-run.cjs -- adapter so AUTO_FIX can drive ANY headless coding agent.
// AUTO_FIX (autofix.cjs) calls AGENT_CMD; point AGENT_CMD at this adapter:
//     AGENT_CMD=node agent-run.cjs "{INCIDENT}" {BRANCH}
// Then choose the agent with AGENT_PROVIDER=opencode|antigravity|custom.
const { spawnSync } = require("child_process");

const prompt   = process.argv[2] || "Fix the latest production incident. Keep changes minimal. npm test must pass.";
const branch   = process.argv[3] || "";
const provider = (process.env.AGENT_PROVIDER || "custom").toLowerCase();
const root     = __dirname;
const onWin    = process.platform === "win32";

function run(cmd, args) {
  console.log(`[AGENT] provider=${provider} branch=${branch}`);
  console.log(`[AGENT] exec: ${cmd} ${args.join(" ")}`);
  const r = spawnSync(cmd, args, { cwd: root, stdio: "inherit", env: process.env, shell: onWin });
  process.exit(r.status == null ? 1 : r.status);
}

switch (provider) {
  case "opencode":
    // opencode non-interactive run mode -- edits the repo in place on the current branch.
    run("opencode", ["run", prompt]);
    break;
  case "antigravity":
    // Antigravity headless task mode.
    run("antigravity", ["run", "--headless", "--prompt", prompt]);
    break;
  default: {
    // custom: put your literal command in AGENT_RAW_CMD ({INCIDENT}/{BRANCH} substituted).
    const raw = (process.env.AGENT_RAW_CMD || "")
      .replace("{INCIDENT}", prompt)
      .replace("{BRANCH}", branch);
    if (!raw) { console.error("[AGENT] AGENT_PROVIDER=custom but AGENT_RAW_CMD is empty."); process.exit(2); }
    run(onWin ? "cmd" : "sh", [onWin ? "/c" : "-c", raw]);
  }
}

import os

projects = [
    r"D:\neon_unified",
    r"D:\omniroute-monetizer\state\worktrees\20260819-122249-qual\neon",
    r"D:\omniroute-monetizer\state\worktrees\20260819-122249-qual\crypto",
    r"C:\god_ai\oioi\oioi",
    r"C:\god_ai\ases_v3_1",
    r"D:\ideation_to_prototype",
    r"C:\god_ai\emergentsh",
    r"D:\god_ai\ai_video_monetizer",
    r"D:\god_ai\lasthelp\lasthelp",
    r"C:\god_ai\crypto-trader-v1_1",
    r"D:\god_ai\voice_agent_avatar\voice-agent-clinic",
    r"D:\dev\antigravity-kandover",
    r"D:\nemo_test",
    r"D:\god_ai\OMEGA",
    r"C:\god_ai\timeofmylife"
]

injection_text = """# 🚨 TOP PRIORITY AGENT RULES 🚨

1. **DETAILED WORKLOG SUMMARIES:** The `MASTER_WORKLOG.md` entry MUST NEVER be a simple one-line summary. Each and every action, observation, and step must be detailed extensively in the worklog. Make it a habit. This is the absolute top priority.
2. **INCREMENTAL COMMITS:** Incremental commits should be done continuously. This is the second highest priority. Make it a habit.

### THREE ARCHITECTURAL PILLARS (MANDATORY FOR ALL AGENTS)
1. **Business Vision Compliance:** This is the highest priority. All actions must align with the end goal of a production-ready, monetizable product.
2. **Open-Ended & Deep-Dive Audits:** Do not perform shallow or baseline audits. Look for hidden gaps and perform deep open-ended investigations.
3. **Extreme Priority on UI Polish:** The UI must be highly polished, pixel-perfect, and feature a "wow" effect (glassmorphism, 2026 state-of-the-art design). A businessman will forgive backend glitches if the UI is breathtaking.

---

"""

targets = ["AGENTS.md", ".sixthrules"]

for proj in projects:
    if not os.path.exists(proj):
        continue
    for target in targets:
        path = os.path.join(proj, target)
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
            if "THREE ARCHITECTURAL PILLARS" not in content:
                with open(path, "w", encoding="utf-8") as f:
                    f.write(injection_text + content)
                print(f"Injected into {path}")
            else:
                print(f"Already exists in {path}")

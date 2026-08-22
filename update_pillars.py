import os
import re

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
    r"C:\god_ai\timeofmylife",
    r"D:\omniroute-monetizer"
]

OLD_PILLAR_TEXT = """3. **Extreme Priority on UI Polish:** The UI must be highly polished, pixel-perfect, and feature a "wow" effect (glassmorphism, 2026 state-of-the-art design). A businessman will forgive backend glitches if the UI is breathtaking."""

NEW_PILLAR_TEXT = """3. **Extreme Priority on UI Polish & Research:** The UI is the FIRST priority. It must be highly polished, pixel-perfect, and feature a "wow" effect (glassmorphism, 2026 state-of-the-art design). Furthermore, the UI MUST be well-researched. When given a target (e.g., "build an OiiOii clone"), the agent MUST search the internet to study the actual look and feel of the target UI before proceeding, ensuring a well-grounded visual replication. A businessman will forgive backend glitches if the UI is breathtaking."""

targets = ["AGENTS.md", ".sixthrules"]

for proj in projects:
    if not os.path.exists(proj):
        continue
    for target in targets:
        path = os.path.join(proj, target)
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
            
            if OLD_PILLAR_TEXT in content:
                content = content.replace(OLD_PILLAR_TEXT, NEW_PILLAR_TEXT)
                with open(path, "w", encoding="utf-8") as f:
                    f.write(content)
                print(f"Updated UI pillar in {path}")
            elif NEW_PILLAR_TEXT not in content:
                print(f"Old text not found in {path}, might need manual check")

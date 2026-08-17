#!/usr/bin/env python3
"""
Continue.dev + NVIDIA NIM Setup & Launcher (FIXED)
Uses shell=True for Windows .cmd compatibility.
"""

import json
import os
import subprocess
import sys
import time
from pathlib import Path

# ============================================
# CONFIGURATION - EDIT THESE
# ============================================

API_KEYS = [
    "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",
    "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",
    "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",
    "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",
]

PROJECTS = [
    r"C:\Users\Admin\Downloads\god_ai\OMEGA",
    r"C:\dev\antigravity-kandover",
    r"C:\god_ai\crypto-trader-v1_1",
    r"C:\god_ai\ases_v3_1",
]

MODELS = [
    "z-ai/glm-5.2",
    "nvidia/nemotron-3-ultra-550b-a55b",
    "deepseek-ai/deepseek-v4-flash",
    "moonshotai/kimi-k2.6",
]

NAMES = [
    "OMEGA-GLM5",
    "Antigravity-Nemotron",
    "CryptoTrader-DeepSeek",
    "ASES-Kimi",
]

# ============================================
# WINDOWS HELPERS
# ============================================

def run_cmd(command, capture=True):
    """Run a shell command with shell=True for Windows .cmd compatibility."""
    if capture:
        result = subprocess.run(command, shell=True, capture_output=True, text=True)
        return result
    else:
        subprocess.Popen(command, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return None

def check_vscode():
    """Check if VS Code: is installed."""
    print("[0/7] Checking VS Code: installation...")
    result = run_cmd("where code")
    if result.returncode != 0:
        print("ERROR: VS Code: is not installed or not in PATH!")
        print("Please install VS Code: from https://code.visualstudio.com/")
        sys.exit(1)
    print("  VS Code: found.")

def install_continue():
    """Install Continue.dev extension."""
    print("\n[1/7] Installing Continue.dev extension...")
    result = run_cmd("code --install-extension Continue.continue")
    if "successfully installed" in result.stdout or "is already installed" in result.stdout:
        print("  Continue.dev extension ready.")
    else:
        print("  WARNING: Extension install may have failed.")
        if result.stdout:
            print(f"  stdout: {result.stdout.strip()}")
        if result.stderr:
            print(f"  stderr: {result.stderr.strip()}")

def check_node():
    """Check Node.js installation."""
    print("\n[2/7] Checking Node.js for Continue.dev core...")
    result = run_cmd("node --version")
    if result.returncode == 0:
        print(f"  Node.js {result.stdout.strip()} found.")
    else:
        print("  WARNING: Node.js not found. Continue.dev may have limited functionality.")

def create_continue_config(project_path, api_key, model, name):
    """Create .continue/config.json for a project."""
    continue_dir = Path(project_path) / ".continue"
    continue_dir.mkdir(parents=True, exist_ok=True)

    config = {
        "models": [{
            "title": f"{name} NIM",
            "provider": "openai",
            "model": model,
            "apiBase": "https://integrate.api.nvidia.com/v1",
            "apiKey": api_key,
            "completionOptions": {
                "maxTokens": 131072,
                "temperature": 0.2
            }
        }],
        "tabAutocompleteModel": {
            "title": f"{name} Autocomplete",
            "provider": "openai",
            "model": model,
            "apiBase": "https://integrate.api.nvidia.com/v1",
            "apiKey": api_key
        },
        "customCommands": [
            {
                "name": "fix",
                "prompt": "Fix the code in the selected file. Look for bugs, type errors, and logical issues. Return only the corrected code.",
                "description": "Fix code issues"
            },
            {
                "name": "refactor",
                "prompt": "Refactor the selected code for better readability, performance, and maintainability. Follow best practices.",
                "description": "Refactor code"
            },
            {
                "name": "explain",
                "prompt": "Explain the selected code in detail. Break down the logic, data flow, and any design patterns used.",
                "description": "Explain code"
            }
        ],
        "contextProviders": [
            {"name": "diff", "params": {}},
            {"name": "folder", "params": {}},
            {"name": "codebase", "params": {}}
        ],
        "slashCommands": [
            {"name": "edit", "description": "Edit selected code"},
            {"name": "comment", "description": "Add comments"},
            {"name": "share", "description": "Export session"}
        ]
    }

    config_path = continue_dir / "config.json"
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)

    print(f"  Created config for {name}")

def create_vscode_settings(project_path, name):
    """Create .vscode/settings.json for a project."""
    vscode_dir = Path(project_path) / ".vscode"
    vscode_dir.mkdir(parents=True, exist_ok=True)

    settings = {
        "continue.enableTabAutocomplete": True,
        "continue.allowAnonymousTelemetry": False,
        "window.title": f"{name} - ${{activeEditorShort}}${{separator}}${{rootName}}"
    }

    settings_path = vscode_dir / "settings.json"
    with open(settings_path, "w", encoding="utf-8") as f:
        json.dump(settings, f, indent=2, ensure_ascii=False)

def launch_vscode(project_path, name):
    """Launch VS Code: for a project in a new window."""
    print(f"\n  Launching {name}...")
    print(f"    Project: {project_path}")
    # Use shell=True so code.cmd is properly resolved on Windows
    run_cmd(f'code --new-window "{project_path}"', capture=False)
    time.sleep(3)

def main():
    print("=" * 50)
    print("  Continue.dev + NVIDIA NIM Setup & Launcher")
    print("=" * 50)
    print()

    # Validate API keys
    if API_KEYS[0] == "nvapi-account-1-key-here":
        print("WARNING: You have not edited the API keys in this script!")
        print("Please open this file in a text editor and replace the placeholder keys.")
        input("\nPress Enter to continue anyway...")

    # Step 0: Check VS Code:
    check_vscode()

    # Step 1: Install Continue.dev
    install_continue()

    # Step 2: Check Node.js
    check_node()

    # Step 3: Show config
    print("\n[3/7] Configuring NVIDIA NIM API keys...")
    print("  4 accounts configured.")

    # Step 4: Show projects
    print("\n[4/7] Configuring project paths and models...")
    for i, (proj, model, name) in enumerate(zip(PROJECTS, MODELS, NAMES)):
        print(f"  Project {i+1}: {name}")
        print(f"    Path:  {proj}")
        print(f"    Model: {model}")
        Path(proj).mkdir(parents=True, exist_ok=True)

    # Step 5: Create Continue configs
    print("\n[5/7] Creating Continue.dev project configs...")
    for proj, key, model, name in zip(PROJECTS, API_KEYS, MODELS, NAMES):
        create_continue_config(proj, key, model, name)

    # Step 6: Create VS Code: settings
    print("\n[6/7] Creating VS Code: workspace settings...")
    for proj, name in zip(PROJECTS, NAMES):
        create_vscode_settings(proj, name)
    print("  VS Code: workspace settings created.")

    # Step 7: Launch VS Code: instances
    print("\n[7/7] Launching 4 VS Code: instances with Continue.dev...")
    for proj, name in zip(PROJECTS, NAMES):
        launch_vscode(proj, name)

    print("\n" + "=" * 50)
    print("  Setup Complete! All 4 VS Code: instances launched!")
    print("=" * 50)
    print()
    for i, (name, proj, model) in enumerate(zip(NAMES, PROJECTS, MODELS)):
        print(f"Window {i+1}: {name}")
        print(f"  Project: {proj}")
        print(f"  Model:   {model}")
    print()
    print("Each VS Code: window has:")
    print("  - Its own Continue.dev config with unique NVIDIA API key")
    print("  - Its own project directory")
    print("  - Its own AI model")
    print("  - Tab autocomplete enabled")
    print()
    print("NO shared 32-worker OpenCode limit.")
    print("Each instance talks DIRECTLY to NVIDIA NIM.")
    print()
    print("To use:")
    print("  1. In any VS Code: window, open Continue panel (Ctrl+L)")
    print("  2. Start chatting with your model")
    print("  3. Use tab autocomplete as you type")
    print("  4. Select code and use /fix, /refactor, or /explain")
    print()
    input("Press Enter to exit...")

if __name__ == "__main__":
    main()

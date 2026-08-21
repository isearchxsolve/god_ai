#!/usr/bin/env python3
"""Package the application into a distributable ZIP."""
import os
import zipfile
from pathlib import Path

def create_zip():
    zip_name = "api_money_bot_complete.zip"
    with zipfile.ZipFile(zip_name, 'w', zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk("."):
            if "__pycache__" in root or "sessions" in root or zip_name in root or ".git" in root:
                continue
            for file in files:
                if file.endswith((".py", ".txt", ".md", ".example", ".bat", ".sh", ".json")):
                    path = os.path.join(root, file)
                    zf.write(path, os.path.relpath(path, "."))
        print(f"✅ Created {zip_name}")

if __name__ == "__main__":
    create_zip()

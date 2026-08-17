import os
import zipfile

workspace = r"c:\god_ai"

# Define distinct, real engineering projects
distinct_projects = {
    "ases_v3_1": "ASES Autonomous Software Engineering System v3.1",
    "OMEGA": "OMEGA SOTA Multi-Agent Platform",
    "emergentsh": "EmergentSH Multi-Agent App Generator",
    "oioi": "OiOi Multi-Agent Web Application Clone",
    "crypto-trader-v1_1": "CryptoTrader v1.1 Heavyweight Trading Engine",
    "api_money_bot_complete": "API Money Bot v3.0 Automation Suite",
    "ai_video_monetizer": "AI Video Monetizer Automation Engine",
    "voice_agent_avatar": "Voice Agent Avatar Real-Time Clinic AI",
    "solana-auto-trader-live-llm": "Solana Auto-Trader LLM & Sniper System",
    "guardian_app": "Guardian App Cross-Platform Flutter Core",
    "convergence_framework": "Convergence Framework & Optimization Suite"
}

created_zips = []

for folder, label in distinct_projects.items():
    folder_path = os.path.join(workspace, folder)
    if not os.path.exists(folder_path):
        print(f"Directory {folder} not found, skipping.")
        continue
        
    zip_name = f"{folder}_engineering_marvel.zip"
    zip_path = os.path.join(workspace, zip_name)
    
    file_count = 0
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(folder_path):
            # Aggressively exclude build/git/temp dirs to avoid huge file bloat
            dirs[:] = [d for d in dirs if d not in [
                'node_modules', '.git', '__pycache__', '.venv', 'dist', 'build', 
                '.next', '.dart_tool', '.idea', '.vs', 'coverage', 'tmp'
            ]]
            for f in files:
                if f.endswith('.zip') or f.endswith('.pyc') or f.endswith('.log'):
                    continue
                full_p = os.path.join(root, f)
                rel_p = os.path.relpath(full_p, workspace)
                try:
                    zf.write(full_p, rel_p)
                    file_count += 1
                except Exception as e:
                    print(f"Error zipping {full_p}: {e}")
                    
    size_mb = round(os.path.getsize(zip_path) / (1024 * 1024), 2)
    created_zips.append((folder, zip_name, size_mb, file_count))
    print(f"Successfully zipped {folder} -> {zip_name} ({size_mb} MB, {file_count} files)")

print("\n--- SUMMARY OF ALL CREATED ZIP FILES ---")
for folder, zip_name, sz, cnt in created_zips:
    print(f"Zip File: {zip_name} | Size: {sz} MB | Files: {cnt}")

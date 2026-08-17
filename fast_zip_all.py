import os
import zipfile

workspace = r"c:\god_ai"

distinct_projects = [
    "ases_v3_1",
    "OMEGA",
    "emergentsh",
    "oioi",
    "crypto-trader-v1_1",
    "api_money_bot_complete",
    "ai_video_monetizer",
    "voice_agent_avatar",
    "solana-auto-trader-live-llm",
    "guardian_app",
    "convergence_framework"
]

ignored_dir_names = {
    'node_modules', '.git', '__pycache__', '.venv', 'venv', 'dist', 
    'build', '.next', '.dart_tool', '.idea', '.vs', 'coverage', 'tmp',
    '.neon_worktrees', 'attached_assets'
}

created_summary = []

for folder in distinct_projects:
    folder_path = os.path.join(workspace, folder)
    if not os.path.exists(folder_path):
        print(f"FOLDER NOT FOUND: {folder}")
        continue
        
    zip_name = f"{folder}_engineering_marvel.zip"
    zip_path = os.path.join(workspace, zip_name)
    
    file_count = 0
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(folder_path):
            # Prune ignored directory names anywhere in the path
            dirs[:] = [d for d in dirs if d.lower() not in ignored_dir_names]
            
            for f in files:
                if f.endswith('.zip') or f.endswith('.pyc') or f.endswith('.log') or f.endswith('.tflite') or f.endswith('.dll') or f.endswith('.exe'):
                    continue
                full_p = os.path.join(root, f)
                try:
                    rel_p = os.path.relpath(full_p, workspace)
                    zf.write(full_p, rel_p)
                    file_count += 1
                except Exception as e:
                    # Catch special device mounts like \\.\nul or permission errors
                    pass
                    
    sz_mb = round(os.path.getsize(zip_path) / (1024 * 1024), 2)
    created_summary.append((zip_name, sz_mb, file_count))
    print(f"CREATED: {zip_name} ({sz_mb} MB, {file_count} files)")

print("\n================ FINAL VERIFIED ZIP LIST ================")
for zname, sz, cnt in created_summary:
    print(f"ZIP: {zname} | SIZE: {sz} MB | FILES: {cnt}")

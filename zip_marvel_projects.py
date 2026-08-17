import os
import zipfile

workspace = r"c:\god_ai"

projects_to_zip = [
    "ases_v3_1",
    "OMEGA",
    "emergentsh",
    "oioi",
    "crypto-trader-v1_1",
    "api_money_bot_complete",
    "ai_video_monetizer",
    "solana-auto-trader-live-llm",
    "guardian_app",
    "screen_guard_final",
    "convergence_framework"
]

zipped_results = []

for proj in projects_to_zip:
    proj_path = os.path.join(workspace, proj)
    if not os.path.exists(proj_path):
        print(f"Skipping {proj}, directory not found.")
        continue
    
    zip_filename = f"{proj}_engineering_marvel.zip"
    zip_filepath = os.path.join(workspace, zip_filename)
    
    file_count = 0
    with zipfile.ZipFile(zip_filepath, 'w', zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(proj_path):
            # Exclude heavy temporary/build dirs
            dirs[:] = [d for d in dirs if d not in ['node_modules', '.git', '__pycache__', '.venv', 'dist', 'build', '.next', '.dart_tool', '.idea', '.vs']]
            for f in files:
                if f.endswith('.zip') or f.endswith('.pyc'):
                    continue
                full_f = os.path.join(root, f)
                rel_f = os.path.relpath(full_f, workspace)
                try:
                    zf.write(full_f, rel_f)
                    file_count += 1
                except Exception as e:
                    print(f"Error writing {full_f}: {e}")
                    
    sz_mb = round(os.path.getsize(zip_filepath) / (1024 * 1024), 2)
    zipped_results.append({
        'project': proj,
        'zip_file': zip_filename,
        'zip_path': zip_filepath,
        'size_mb': sz_mb,
        'files_zipped': file_count
    })

print("ZIP COMPLETION SUMMARY:")
for r in zipped_results:
    print(f"- {r['project']}: Created {r['zip_file']} ({r['size_mb']} MB, {r['files_zipped']} files)")

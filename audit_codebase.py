import os
import glob
import json

workspace = r"c:\god_ai"

dirs = [d for d in os.listdir(workspace) if os.path.isdir(os.path.join(workspace, d)) and not d.startswith('.')]

audit_report = []

for d in sorted(dirs):
    dir_path = os.path.join(workspace, d)
    
    total_lines = 0
    py_files = 0
    ts_files = 0
    js_files = 0
    md_files = 0
    other_files = 0
    
    has_tests = False
    has_git = os.path.exists(os.path.join(dir_path, '.git'))
    has_readme = False
    readme_text = ""
    
    main_files = []
    
    for root, subdirs, files in os.walk(dir_path):
        subdirs[:] = [sd for sd in subdirs if sd not in ['node_modules', '.git', '__pycache__', '.venv', 'dist', 'build', '.next']]
        for f in files:
            fp = os.path.join(root, f)
            ext = os.path.splitext(f)[1].lower()
            
            if 'test' in f.lower() or 'spec' in f.lower():
                has_tests = True
                
            if f.lower().startswith('readme'):
                has_readme = True
                try:
                    with open(fp, 'r', encoding='utf-8', errors='ignore') as rf:
                        readme_text = rf.read(1500)
                except:
                    pass
            
            if ext == '.py':
                py_files += 1
            elif ext in ['.ts', '.tsx']:
                ts_files += 1
            elif ext in ['.js', '.jsx']:
                js_files += 1
            elif ext == '.md':
                md_files += 1
            else:
                other_files += 1
                
            # Count lines for code files
            if ext in ['.py', '.ts', '.tsx', '.js', '.jsx', '.html', '.css', '.dart', '.kt', '.java', '.sql']:
                try:
                    with open(fp, 'r', encoding='utf-8', errors='ignore') as cf:
                        total_lines += len(cf.readlines())
                except:
                    pass
                    
            if len(main_files) < 15:
                rel_p = os.path.relpath(fp, dir_path)
                main_files.append(rel_p)
                
    audit_report.append({
        "folder": d,
        "loc": total_lines,
        "py_files": py_files,
        "ts_files": ts_files,
        "js_files": js_files,
        "md_files": md_files,
        "other_files": other_files,
        "has_tests": has_tests,
        "has_readme": has_readme,
        "readme_summary": readme_text[:250].replace('\n', ' '),
        "sample_files": main_files[:10]
    })

print(json.dumps(audit_report, indent=2))

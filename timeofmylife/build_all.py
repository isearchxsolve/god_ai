"""Build all three volumes."""
import subprocess, sys, os

base = os.path.dirname(os.path.abspath(__file__))
scripts = ['build_vol1.py', 'build_vol2.py', 'build_vol3.py']

for script in scripts:
    path = os.path.join(base, script)
    print(f'\n{"="*60}')
    print(f'Building {script}...')
    print(f'{"="*60}')
    result = subprocess.run(
        [sys.executable, path],
        cwd=base,
        capture_output=False
    )
    if result.returncode != 0:
        print(f'FAILED: {script}')
        sys.exit(1)

print(f'\n{"="*60}')
print('All volumes built successfully.')
print(f'{"="*60}')

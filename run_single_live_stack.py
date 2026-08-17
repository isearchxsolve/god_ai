import os, sys, shutil, importlib.util, ast, time
from pathlib import Path

def main():
    stack = sys.argv[1] if len(sys.argv) > 1 else "fastapi-react"
    api_key = os.environ.get("NIM_API_KEY") or "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"
    
    agent_path = Path(r"C:\god_ai\emergentsh\neon_architect_v4_7_mobile_env.py")
    spec = importlib.util.spec_from_file_location("neon", str(agent_path))
    neon = importlib.util.module_from_spec(spec)
    sys.modules["neon"] = neon
    spec.loader.exec_module(neon)

    target_dir = Path(rf"C:\god_ai\live_generated_{stack}")
    if target_dir.exists():
        shutil.rmtree(target_dir, ignore_errors=True)
    target_dir.mkdir(parents=True, exist_ok=True)

    cfg = dict(neon.DEFAULT_CONFIG)
    cfg["api_key"] = api_key
    cfg["base_url"] = getattr(neon, "NIM_BASE_URL", "https://integrate.api.nvidia.com/v1")
    cfg["default_model"] = "glm-5.2"

    print(f"=== Starting Live Generation for Stack: {stack} ===")
    print(f"Target directory: {target_dir}")

    pool = neon.build_pool(cfg)
    print(f"Pool initialized with {len(pool.providers)} providers: {[p.name for p in pool.providers]}")

    orch = neon.GenerationOrchestrator(pool, cfg)

    start_time = time.time()
    def on_progress(phase, msg):
        print(f"  [{phase}] {msg}")

    desc = f"Complete production-ready Task Management application with real AI NIM completion endpoints ({stack})"
    result = orch.generate(
        description=desc,
        project_dir=target_dir,
        stack=stack,
        on_progress=on_progress,
    )

    elapsed = time.time() - start_time
    print(f"\n=== Generation Summary ({elapsed:.1f}s) ===")
    print(f"Success: {result.success}")
    print(f"Files created (template): {len(result.files_created)}")
    print(f"Files generated (AI): {len(result.files_generated)}")
    if result.errors:
        print(f"Errors ({len(result.errors)}):")
        for e in result.errors:
            print(f"  - {e}")

    # Check generated files on disk
    print("\n=== Disk Verification ===")
    all_files = list(target_dir.rglob("*"))
    files_on_disk = [p for p in all_files if p.is_file()]
    print(f"Total files on disk: {len(files_on_disk)}")
    for f in sorted(files_on_disk):
        rel = f.relative_to(target_dir)
        sz = f.stat().st_size
        print(f"  {rel} ({sz} bytes)")

    # Python AST Check
    py_files = [p for p in files_on_disk if p.suffix == ".py"]
    print(f"\n=== Python AST Validation ({len(py_files)} files) ===")
    ast_errors = []
    for py in py_files:
        try:
            ast.parse(py.read_text(encoding="utf-8", errors="replace"))
            print(f"  [VALID] {py.relative_to(target_dir)}")
        except SyntaxError as e:
            err = f"{py.relative_to(target_dir)}: {e.msg} at line {e.lineno}"
            print(f"  [INVALID] {err}")
            ast_errors.append(err)

    if ast_errors:
        print(f"\nFAILED AST Check on {len(ast_errors)} files!")
        sys.exit(1)
    else:
        print("\nALL Python files parsed cleanly with ZERO syntax defects!")

if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Harness for the repair loop added to neon_architect_patched.py.

Rather than importing the full 12k-line file (which pulls in Rich, argparse,
NIM client bootstrapping, etc.), this extracts the exact logic added for
gaps #1-#3 (test execution, static consistency check, repair loop) verbatim
from the patched file and runs it against a REAL, deliberately broken
generated project on disk — no mocking of subprocess or the filesystem.

The only thing faked is the model call (_call_nim) — replaced with a
scripted function that returns a real, correct fix on its first invocation,
so we can prove the round-trip (write fix -> re-run pytest -> observe
pass) actually works end to end without needing live NIM credentials.
"""
import ast
import json
import subprocess
import shutil
from pathlib import Path
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


# ── Verbatim from the patched file ──────────────────────────────────────────

@dataclass
class TestRunResult:
    ran: bool
    passed: bool
    output: str = ""


@dataclass
class GenerationResult:
    success: bool
    project_dir: Path
    files_generated: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    stack: str = "fastapi-react"
    test_output: Optional[TestRunResult] = None
    repair_rounds: int = 0


def run_tests(project_dir: Path, stack: str) -> TestRunResult:
    if stack in ("fastapi-react", "flutter-fastapi"):
        if not (project_dir / "tests").exists():
            return TestRunResult(ran=False, passed=False, output="No tests/ directory found.")
        runner = shutil.which("pytest") or (shutil.which("python3") and "python3")
        cmd = (
            [runner, "-m", "pytest", "tests/", "-x", "--tb=short", "-q"]
            if runner == "python3"
            else [runner, "tests/", "-x", "--tb=short", "-q"]
        )
    else:
        return TestRunResult(ran=False, passed=False, output=f"No test runner defined for stack={stack!r}.")

    try:
        proc = subprocess.run(cmd, cwd=str(project_dir), capture_output=True, text=True, timeout=60)
        output = (proc.stdout or "") + (proc.stderr or "")
        return TestRunResult(ran=True, passed=proc.returncode == 0, output=output[-6000:])
    except Exception as e:
        return TestRunResult(ran=False, passed=False, output=f"Test run failed to execute: {e}")


def check_python_import_consistency(project_dir: Path, generated_paths: List[str]) -> List[str]:
    py_files = [p for p in generated_paths if p.endswith(".py")]
    if not py_files:
        return []
    module_map: Dict[str, str] = {}
    for rel_path in py_files:
        mod = rel_path[:-3].replace("/", ".").replace("\\", ".")
        module_map[mod] = rel_path
        if mod.endswith(".__init__"):
            module_map[mod[: -len(".__init__")]] = rel_path

    problems: List[str] = []
    for rel_path in py_files:
        fp = project_dir / rel_path
        if not fp.exists():
            continue
        try:
            source = fp.read_text(encoding="utf-8", errors="replace")
            tree = ast.parse(source, filename=rel_path)
        except SyntaxError as e:
            problems.append(f"{rel_path}: syntax error — {e.msg} (line {e.lineno})")
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                if node.level and node.level > 0:
                    continue
                if not node.module or not node.module.startswith(
                    tuple(m.split(".")[0] for m in module_map) or ("__nomatch__",)
                ):
                    continue
                if node.module in module_map:
                    continue
                # No ancestor-package escape — see fix note in the patched
                # file. A package's own __init__.py existing doesn't mean
                # every submodule under it was generated.
                problems.append(
                    f"{rel_path}: imports '{node.module}' but no generated file "
                    f"provides that module (generated: {sorted(module_map)})"
                )
    return problems


def repair_pass(
    ctx: Dict[str, Any],
    project_dir: Path,
    result: GenerationResult,
    call_model,  # scripted stand-in for SpecializedAgent._call_nim
    max_rounds: int = 3,
    seed_failure_output: Optional[str] = None,
) -> TestRunResult:
    log: List[str] = []

    def _prog(phase: str, msg: str) -> None:
        log.append(f"[{phase}] {msg}")
        print(f"[{phase}] {msg}")

    if seed_failure_output:
        test_result = TestRunResult(ran=True, passed=False, output=seed_failure_output)
    else:
        test_result = run_tests(project_dir, ctx["stack"])
        if not test_result.ran:
            _prog("test", f"tests did not run: {test_result.output[:200]}")
            return test_result
        if test_result.passed:
            _prog("test", "tests passed on first run")
            return test_result

    for round_n in range(1, max_rounds + 1):
        _prog("repair", f"round {round_n}/{max_rounds}: tests failing, requesting fix…")

        candidate_paths = [p for p in result.files_generated if p.endswith((".py", ".ts", ".tsx", ".js", ".dart"))]
        file_blob = ""
        for rel_path in candidate_paths[:12]:
            fp = project_dir / rel_path
            if fp.exists():
                file_blob += f"\n--- {rel_path} ---\n{fp.read_text(encoding='utf-8', errors='replace')[:3000]}\n"

        prompt = (
            f"Stack: {ctx['stack']}\n\nFailing test output:\n{test_result.output[:4000]}\n\n"
            f"Current file contents:\n{file_blob[:12000]}\n\n"
            'Return corrected file contents as a JSON object: {"path": "content", ...}.'
        )

        try:
            raw = call_model(prompt)
            fixes = json.loads(raw)
        except (json.JSONDecodeError, RuntimeError) as e:
            result.errors.append(f"repair round {round_n}: could not parse/obtain fix — {e}")
            _prog("repair", f"round {round_n} failed to parse: {e}")
            continue

        if not isinstance(fixes, dict) or not fixes:
            result.errors.append(f"repair round {round_n}: model returned no usable fixes")
            continue

        for rel_path, content in fixes.items():
            if not isinstance(content, str) or not content.strip():
                continue
            safe_rel = rel_path.strip().lstrip("/\\")
            dest = (project_dir / safe_rel).resolve()
            try:
                dest.relative_to(project_dir.resolve())
            except ValueError:
                result.errors.append(f"repair round {round_n}: rejected out-of-tree path {rel_path!r}")
                continue
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(content, encoding="utf-8")
            ctx[safe_rel] = content
            if safe_rel not in result.files_generated:
                result.files_generated.append(safe_rel)
            _prog("repair", f"wrote fix to {safe_rel}")

        test_result = run_tests(project_dir, ctx["stack"])
        if not test_result.ran:
            _prog("repair", f"round {round_n}: tests still don't run — {test_result.output[:150]}")
            return test_result
        if test_result.passed:
            _prog("repair", f"tests passed after round {round_n}")
            result.repair_rounds = round_n
            return test_result

    result.repair_rounds = max_rounds
    _prog("repair", f"tests still failing after {max_rounds} repair round(s)")
    return test_result


# ── Scripted "model" — no live NIM call, but a REAL correct fix ────────────

CALL_COUNT = {"n": 0}

def scripted_call_model(prompt: str) -> str:
    """Stands in for SpecializedAgent._call_nim. Returns a real, correct
    fix for the missing backend/database.py module on its first call —
    exercising the exact write -> re-run -> pass path with no mocking of
    subprocess or the filesystem underneath it.
    """
    CALL_COUNT["n"] += 1
    assert "backend.database" in prompt, "expected the failing import to appear in the repair prompt"
    fix = {
        "backend/database.py": (
            "from sqlalchemy import create_engine\n"
            "from sqlalchemy.orm import declarative_base, sessionmaker\n\n"
            'engine = create_engine("sqlite:///./app.db", connect_args={"check_same_thread": False})\n'
            "SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)\n"
            "Base = declarative_base()\n"
        )
    }
    return json.dumps(fix)


def main() -> None:
    project_dir = Path("/home/claude/harness_project").resolve()
    generated_paths = [
        "backend/__init__.py",
        "backend/models.py",
        "backend/main.py",
        "tests/__init__.py",
        "tests/conftest.py",
        "tests/test_api.py",
    ]
    ctx = {"stack": "fastapi-react", "project_name": "harness_project"}
    result = GenerationResult(success=False, project_dir=project_dir, stack="fastapi-react",
                               files_generated=list(generated_paths))

    print("=== STEP 1: static import-consistency check (real ast.parse) ===")
    problems = check_python_import_consistency(project_dir, generated_paths)
    for p in problems:
        print(" -", p)
    assert problems, "expected the missing backend.database import to be caught"
    assert any("backend.database" in p for p in problems)
    print(f"CONFIRMED: static check caught {len(problems)} issue(s) before any test ran.\n")

    print("=== STEP 2: repair pass, seeded from the static check ===")
    seed = "Static import-consistency check found:\n" + "\n".join(problems)
    final = repair_pass(ctx, project_dir, result, scripted_call_model, seed_failure_output=seed)

    print("\n=== RESULT ===")
    print("ran:", final.ran, "passed:", final.passed)
    print("repair_rounds:", result.repair_rounds)
    print("model calls made:", CALL_COUNT["n"])
    print("errors recorded:", result.errors)
    print("\n--- final pytest output ---")
    print(final.output)

    assert final.ran is True
    assert final.passed is True, "repair loop did not converge to a passing test suite"
    assert result.repair_rounds == 1, "expected convergence on round 1 with a correct scripted fix"
    assert CALL_COUNT["n"] == 1, "expected exactly one model call for a correct first fix"
    assert (project_dir / "backend/database.py").exists()
    print("\nALL ASSERTIONS PASSED — repair loop verified end-to-end against a real broken project.")


if __name__ == "__main__":
    main()

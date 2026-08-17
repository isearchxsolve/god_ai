import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "agent_service"))

import pytest

from semantic_differ import SemanticDiffer, _extract_python_interface


@pytest.mark.parametrize("i", range(100), ids=[f"js-diff-{i}" for i in range(100)])
def test_js_interface_diff_detects_removed_and_added(i):
    path = f"src/mod{i}.js"
    before = [{"path": path, "content": f"export function foo_{i}() {{}}"}]
    after = [{"path": path, "content": f"export function foo_{i}_new() {{}}"}]

    report = SemanticDiffer().diff(before, after)

    assert report.changed_files
    changed = report.changed_files[0]
    assert f"foo_{i}" in changed.interface_removed
    assert f"foo_{i}_new" in changed.interface_added


@pytest.mark.parametrize("i", range(50), ids=[f"py-iface-{i}" for i in range(50)])
def test_python_interface_extraction(i):
    iface = _extract_python_interface(f"mod{i}.py", f"def func_{i}():\n    return {i}\n")
    assert iface.path == f"mod{i}.py"
    assert f"func_{i}" in iface.exports


@pytest.mark.parametrize("i", range(30), ids=[f"resolve-{i}" for i in range(30)])
def test_resolve_relative_returns_candidate(i):
    differ = SemanticDiffer()
    resolved = differ._resolve_relative(f"src/dir{i}/file.js", f"./dep{i}")
    assert resolved is not None
    assert resolved.endswith(f"dep{i}.js")

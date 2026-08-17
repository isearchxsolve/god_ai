import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "agent_service"))

import pytest

from interface_cache import _path_pattern, _synthesize_exports


PATH_CASES = []
for i in range(60):
    PATH_CASES.append((f"nested-{i}", f"src/dir{i}/file{i}.js", f"dir{i}/file{i}.js"))
for i in range(20):
    PATH_CASES.append((f"single-{i}", f"file{i}.py", f"file{i}.py"))


@pytest.mark.parametrize("case_id,path,expected", PATH_CASES, ids=[c[0] for c in PATH_CASES])
def test_path_pattern(case_id, path, expected):
    assert _path_pattern(path) == expected


@pytest.mark.parametrize("i", range(20), ids=[f"py-exports-{i}" for i in range(20)])
def test_synthesize_python_exports(i):
    content = _synthesize_exports(f"mod{i}.py", [f"func_{i}"])
    assert f"def func_{i}():" in content


@pytest.mark.parametrize("i", range(20), ids=[f"js-exports-{i}" for i in range(20)])
def test_synthesize_js_exports(i):
    content = _synthesize_exports(f"mod{i}.js", [f"func_{i}"])
    assert f"export function func_{i}()" in content

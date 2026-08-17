import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "agent_service"))

import pytest

from dependency_debugger import _extract_error_locations


def node_case(i):
    return f"at Object.<anonymous> (src/routes{i}.js:{i + 1}:5)", f"src/routes{i}.js", i + 1


def python_case(i):
    return f'File "src/auth{i}.py", line {i + 1}', f"src/auth{i}.py", i + 1


def go_case(i):
    return f"FAIL: routes_test{i}.go:{i + 1}", f"routes_test{i}.go", i + 1


CASES = []
for i in range(40):
    text, path, line = node_case(i)
    CASES.append((f"node-{i}", text, path, line))
for i in range(40):
    text, path, line = python_case(i)
    CASES.append((f"python-{i}", text, path, line))
for i in range(20):
    text, path, line = go_case(i)
    CASES.append((f"go-{i}", text, path, line))


@pytest.mark.parametrize("case_id,text,path,line", CASES, ids=[c[0] for c in CASES])
def test_extract_error_locations(case_id, text, path, line):
    locations = _extract_error_locations(text)
    assert (path, line) in locations


@pytest.mark.parametrize("i", range(20), ids=[f"no-location-{i}" for i in range(20)])
def test_extract_error_locations_no_match(i):
    assert _extract_error_locations(f"no useful error output {i}") == []

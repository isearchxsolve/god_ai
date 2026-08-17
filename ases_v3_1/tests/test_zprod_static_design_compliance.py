import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "agent_service"))

import pytest

from static_reviewer import _design_compliance


def make_spec(components=None, colors=None):
    return {
        "has_design": True,
        "spec": {
            "design_system": {"colors": colors or {}},
            "components": components or [],
        },
    }


@pytest.mark.parametrize("i", range(100), ids=[f"missing-root-{i}" for i in range(100)])
def test_missing_root_block_is_flagged(i):
    files = [{"path": f"app{i}.css", "content": f".x{i} {{ margin: {i}px; }} :focus {{}} prefers-reduced-motion"}}]
    issues = _design_compliance(files, make_spec())
    assert any(issue.code == "DS007" for issue in issues)


@pytest.mark.parametrize("i", range(50), ids=[f"root-present-{i}" for i in range(50)])
def test_present_root_block_is_not_flagged(i):
    files = [
        {
            "path": f"app{i}.css",
            "content": f":root {{ --color-x{i}: #123456; }} :focus {{}} @media (prefers-reduced-motion) {{}}",
        }
    ]
    issues = _design_compliance(files, make_spec())
    assert not any(issue.code == "DS007" for issue in issues)


@pytest.mark.parametrize("i", range(25), ids=[f"missing-testid-{i}" for i in range(25)])
def test_missing_testid_is_flagged(i):
    spec = make_spec(components=[{"name": f"Btn{i}", "data_testid": f"btn{i}"}])
    files = [{"path": f"comp{i}.jsx", "content": "<div />"}]
    issues = _design_compliance(files, spec)
    assert any(issue.code == "DS002" for issue in issues)


@pytest.mark.parametrize("i", range(25), ids=[f"present-testid-{i}" for i in range(25)])
def test_present_testid_is_not_flagged(i):
    spec = make_spec(components=[{"name": f"Btn{i}", "data_testid": f"btn{i}"}])
    content = (
        f"<div data-testid='btn{i}' data-testid='btn{i}-trigger' data-testid='btn{i}-content'></div>"
    )
    files = [{"path": f"comp{i}.jsx", "content": content}]
    issues = _design_compliance(files, spec)
    assert not any(issue.code == "DS002" for issue in issues)

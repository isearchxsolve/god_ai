import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "agent_service"))

import pytest

from visual_reviewer import _has_frontend, _should_run_visual


@pytest.mark.parametrize("i", range(30), ids=[f"frontend-stack-{i}" for i in range(30)])
def test_has_frontend_true_for_frontend_stacks(i):
    stack = ["react", "next.js", "vue", "svelte", "html"][i % 5]
    assert _has_frontend(stack, []) is True


@pytest.mark.parametrize("i", range(30), ids=[f"frontend-files-{i}" for i in range(30)])
def test_has_frontend_true_for_frontend_files(i):
    ext = [".jsx", ".tsx", ".vue", ".html"][i % 4]
    files = [{"path": f"src/component{i}{ext}", "content": ""}]
    assert _has_frontend("python", files) is True


@pytest.mark.parametrize("i", range(30), ids=[f"gate-{i}" for i in range(30)])
def test_should_run_visual_last_mile_gate(i):
    iteration = 1 + (i % 5)
    max_iterations = 5
    should, reason = _should_run_visual(iteration, max_iterations, "")

    if max_iterations - iteration > 2:
        assert should is False
        assert reason
    else:
        assert should is True
        assert reason == ""


@pytest.mark.parametrize("i", range(30), ids=[f"rich-errors-{i}" for i in range(30)])
def test_should_run_visual_skips_rich_errors(i):
    should, reason = _should_run_visual(4, 5, "x" * 300)
    assert should is False
    assert "Rich text feedback" in reason

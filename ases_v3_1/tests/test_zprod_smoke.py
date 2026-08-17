import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "agent_service"))

import pytest

from design_regenerator import is_design_level_failure, score_design_failure

CASES = [(i, f"layout issue {i}") for i in range(50)]


@pytest.mark.smoke
@pytest.mark.parametrize("i,desc", CASES, ids=[f"smoke-{i}" for i, _ in CASES])
def test_smoke_design_score_is_bounded(i, desc):
    score = score_design_failure({"description": desc})
    assert 0.0 <= score <= 1.0
    assert isinstance(is_design_level_failure({"description": desc}, 0.5), bool)

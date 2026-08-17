import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "agent_service"))

import pytest

import design_regenerator as dr

KEYWORDS = (
    dr.STRONG_DESIGN_SIGNALS
    + dr.MEDIUM_DESIGN_SIGNALS
    + dr.WEAK_DESIGN_SIGNALS
    + dr.CODE_COUNTER_SIGNALS
)
SCORE_CASES = [(i, f"{KEYWORDS[i % len(KEYWORDS)]} observed in case {i}") for i in range(200)]


@pytest.mark.parametrize("i,desc", SCORE_CASES, ids=[f"score-{i}" for i, _ in SCORE_CASES])
def test_score_design_failure_is_bounded(i, desc):
    score = dr.score_design_failure({"description": desc})
    assert isinstance(score, float)
    assert 0.0 <= score <= 1.0


@pytest.mark.parametrize("i,desc", SCORE_CASES[:20], ids=[f"threshold-{i}" for i, _ in SCORE_CASES[:20]])
def test_is_design_level_failure_returns_bool(i, desc):
    assert isinstance(dr.is_design_level_failure({"description": desc}, 0.5), bool)


EXTRACT_CASES = [(i, {"description": f"desc {i}"}, f"desc {i}") for i in range(15)]
EXTRACT_CASES += [
    (100, None, ""),
    (101, "plain text", "plain text"),
    (102, {"message": "msg"}, "msg"),
    (103, {"text": "txt"}, "txt"),
    (104, {"error": "err"}, "err"),
    (105, {"issue": "iss"}, "iss"),
    (106, {"unknown": "x"}, ""),
    (107, 123, "123"),
    (108, ["list"], "['list']"),
    (109, {"description": ""}, ""),
]


@pytest.mark.parametrize("case_id,value,expected", EXTRACT_CASES, ids=[f"extract-{c[0]}" for c in EXTRACT_CASES])
def test_extract_description(case_id, value, expected):
    assert dr._extract_description(value) == expected


def test_generate_css_variables_empty():
    assert dr._generate_css_variables(None) == ""
    assert dr._generate_css_variables({}) == ""


def test_generate_css_variables_tokens():
    out = dr._generate_css_variables({"design_tokens": {"primary_color": "#123456"}})
    assert "--primary-color: #123456;" in out

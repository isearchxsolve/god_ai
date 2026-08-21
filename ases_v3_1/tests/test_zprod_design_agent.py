import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "agent_service"))

import pytest

from design_agent import _generate_css_variables, _parse_design_json, format_design_for_coder


@pytest.mark.parametrize("i", range(30), ids=[f"parse-valid-{i}" for i in range(30)])
def test_parse_design_json_valid(i):
    parsed = _parse_design_json(f'{{"components": [{{"name": "C{i}"}}]}}')
    assert parsed is not None
    assert parsed["components"][0]["name"] == f"C{i}"


@pytest.mark.parametrize("i", range(10), ids=[f"parse-fenced-{i}" for i in range(10)])
def test_parse_design_json_fenced(i):
    parsed = _parse_design_json(f'```json\n{{"case": {i}}}\n```')
    assert parsed == {"case": i}


@pytest.mark.parametrize("i", range(10), ids=[f"parse-invalid-{i}" for i in range(10)])
def test_parse_design_json_invalid(i):
    # The parser's public contract is a safe empty mapping, avoiding nullable
    # handling at every downstream planner/coder boundary.
    assert _parse_design_json(f"not json {i}") == {}


@pytest.mark.parametrize("i", range(20), ids=[f"css-vars-{i}" for i in range(20)])
def test_generate_css_variables(i):
    spec = {
        "design_system": {
            "colors": {"primary": f"#11{i:04d}"},
            "typography": {"font_family": "Inter"},
        },
        "responsive_breakpoints": {"md": "768px"},
    }
    css = _generate_css_variables(spec)
    assert ":root {" in css
    assert "--color-primary:" in css
    assert "--breakpoint-md: 768px;" in css


@pytest.mark.parametrize("i", range(20), ids=[f"format-{i}" for i in range(20)])
def test_format_design_for_coder(i):
    result = {
        "has_design": True,
        "spec": {
            "layout": {"max_width": "1280px", "grid_columns": 12, "gutter": "1rem"},
            "components": [
                {
                    "name": f"Comp{i}",
                    "purpose": "test",
                    "layout_rules": ["flex"],
                    "data_testid": f"comp-{i}",
                    "states": ["default"],
                    "interaction_rules": ["click works"],
                }
            ],
            "notes_for_coder": ["Use CSS variables"],
        },
        "css_variables": ":root {}",
        "issues": [],
    }

    text = format_design_for_coder(result)
    assert "DESIGN SPECIFICATION" in text
    assert f"Comp{i}" in text
    assert "__ASES_READY__" in text


def test_format_design_for_coder_no_design():
    assert format_design_for_coder({"has_design": False}) == ""

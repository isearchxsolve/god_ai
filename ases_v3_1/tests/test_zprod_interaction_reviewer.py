import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "agent_service"))

import pytest

from interaction_reviewer import _generate_tests_from_spec, _get_dev_command, _resolve_stack_from_files


STACK_CASES = []
for i in range(20):
    STACK_CASES.append((f"next-{i}", [{"path": f"next.config{i}.js"}], "next.js"))
for i in range(20):
    STACK_CASES.append((f"react-{i}", [{"path": f"src/App{i}.jsx"}], "react"))
for i in range(10):
    STACK_CASES.append((f"vue-{i}", [{"path": f"src/App{i}.vue"}], "vue"))


@pytest.mark.parametrize("case_id,files,expected", STACK_CASES, ids=[c[0] for c in STACK_CASES])
def test_resolve_stack_from_files(case_id, files, expected):
    assert _resolve_stack_from_files(files) == expected


@pytest.mark.parametrize(
    "stack",
    ["react", "next.js", "nextjs", "vue", "svelte", "angular"],
    ids=["react", "next.js", "nextjs", "vue", "svelte", "angular"],
)
def test_get_dev_command_known_stacks(stack):
    assert _get_dev_command(stack)


@pytest.mark.parametrize("i", range(20), ids=[f"unknown-stack-{i}" for i in range(20)])
def test_get_dev_command_unknown_stack(i):
    assert _get_dev_command(f"unknown-{i}") is None


RULES = [
    "opens on click",
    "closes on escape",
    "closes on backdrop click",
    "dropdown menu",
    "toggle switch",
    "submit form",
    "tab navigate",
    "mobile menu hamburger collapse",
]


@pytest.mark.parametrize("i", range(50), ids=[f"spec-tests-{i}" for i in range(50)])
def test_generate_tests_from_spec_creates_tests(i):
    rule = RULES[i % len(RULES)]
    spec = {
        "components": [
            {
                "name": f"Component{i}",
                "data_testid": f"component-{i}",
                "interaction_rules": [rule],
            }
        ]
    }

    tests = _generate_tests_from_spec(spec)

    assert tests
    assert all(t.name for t in tests)
    assert len({t.name for t in tests}) == len(tests)

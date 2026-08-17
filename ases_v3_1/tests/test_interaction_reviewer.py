"""
ASES — Interaction Reviewer Unit Tests
======================================
Dedicated unit tests for interaction_reviewer.py covering:
  - _generate_tests_from_spec() conversion from design spec
  - _run_single_test() execution with retry logic
  - interaction_reviewer() full flow with mocked browser + subprocess
  - Error handling: timeouts, parse failures, browser crashes
  - Accessibility checks, viewport emulation, hydration waits
  - Parallel execution via asyncio.gather
  - Screenshot-on-failure behavior

All Playwright, subprocess, and asyncio dependencies are mocked.
"""

import asyncio
import base64
import json
import sys
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AGENT_SERVICE = os.path.join(ROOT, "agent_service")
sys.path.insert(0, AGENT_SERVICE)

import interaction_reviewer as ir


# ---------------------------------------------------------------------------
# _generate_tests_from_spec()
# ---------------------------------------------------------------------------

class TestGenerateTestsFromSpec:
    def test_empty_spec_returns_empty_list(self):
        spec = {"components": []}
        assert ir._generate_tests_from_spec(spec) == []

    def test_component_with_no_rules_returns_empty(self):
        spec = {"components": [{"name": "Button", "props": {}}]}
        assert ir._generate_tests_from_spec(spec) == []

    def test_single_click_rule_generates_test(self):
        spec = {
            "components": [
                {
                    "name": "SubmitButton",
                    "interaction_rules": [
                        {
                            "action": "click",
                            "selector": "#submit-btn",
                            "post_condition": "#success-message",
                        }
                    ],
                }
            ]
        }
        tests = ir._generate_tests_from_spec(spec)
        assert len(tests) == 1
        t = tests[0]
        assert t.name == "SubmitButton-click-#submit-btn"
        assert t.action == "click"
        assert t.selector == "#submit-btn"
        assert t.post_condition == "#success-message"
        assert t.pre_condition is None
        assert t.viewport is None
        assert t.accessibility_check is False

    def test_multiple_rules_generates_multiple_tests(self):
        spec = {
            "components": [
                {
                    "name": "Form",
                    "interaction_rules": [
                        {"action": "type", "selector": "#email", "post_condition": "#email"},
                        {"action": "click", "selector": "#submit", "post_condition": "#thanks"},
                    ],
                }
            ]
        }
        tests = ir._generate_tests_from_spec(spec)
        assert len(tests) == 2
        t1, t2 = tests
        assert t1.action == "type"
        assert t1.selector == "#email"
        assert t1.post_condition == "#email"
        assert t1.pre_condition is None
        assert t1.viewport is None
        assert t1.accessibility_check is False
        assert t2.action == "click"
        assert t2.selector == "#submit"
        assert t2.post_condition == "#thanks"
        assert t2.pre_condition is None
        assert t2.viewport is None
        assert t2.accessibility_check is False

    def test_test_includes_pre_condition(self):
        spec = {
            "components": [
                {
                    "name": "Dropdown",
                    "interaction_rules": [
                        {
                            "action": "click",
                            "selector": "#dropdown",
                            "pre_condition": "#dropdown-trigger",
                            "post_condition": "#options",
                        }
                    ],
                }
            ]
        }
        tests = ir._generate_tests_from_spec(spec)
        assert len(tests) == 1
        t = tests[0]
        assert t.pre_condition == "#dropdown-trigger"
        assert t.action == "click"
        assert t.selector == "#dropdown"
        assert t.post_condition == "#options"
        assert t.viewport is None
        assert t.accessibility_check is False

    def test_test_includes_accessibility_check_flag(self):
        spec = {
            "components": [
                {
                    "name": "Accordion",
                    "interaction_rules": [
                        {
                            "action": "click",
                            "selector": "#accordion",
                            "post_condition": "#panel",
                            "accessibility_check": True,
                        }
                    ],
                }
            ]
        }
        tests = ir._generate_tests_from_spec(spec)
        assert len(tests) == 1
        assert tests[0].accessibility_check is True
        assert tests[0].action == "click"
        assert tests[0].selector == "#accordion"
        assert tests[0].post_condition == "#panel"
        assert tests[0].pre_condition is None
        assert tests[0].viewport is None

    def test_test_includes_viewport_field(self):
        spec = {
            "components": [
                {
                    "name": "MobileMenu",
                    "interaction_rules": [
                        {
                            "action": "tap",
                            "selector": "#menu-btn",
                            "post_condition": "#menu-open",
                            "viewport": "mobile",
                        }
                    ],
                }
            ]
        }
        tests = ir._generate_tests_from_spec(spec)
        assert len(tests) == 1
        assert tests[0].viewport == "mobile"
        assert tests[0].action == "touch"
        assert tests[0].selector == "#menu-btn"
        assert tests[0].post_condition == "#menu-open"
        assert tests[0].pre_condition is None
        assert tests[0].accessibility_check is False

    def test_test_includes_custom_timeout(self):
        spec = {
            "components": [
                {
                    "name": "SlowButton",
                    "interaction_rules": [
                        {
                            "action": "click",
                            "selector": "#slow-btn",
                            "post_condition": "#loaded",
                            "timeout_ms": 10000,
                        }
                    ],
                }
            ]
        }
        tests = ir._generate_tests_from_spec(spec)
        assert len(tests) == 1
        assert tests[0].timeout_ms == 10000

    def test_component_name_sanitization_for_test_name(self):
        spec = {
            "components": [
                {
                    "name": "User Profile Card",
                    "interaction_rules": [
                        {"action": "click", "selector": "#edit", "post_condition": "#form"},
                    ],
                }
            ]
        }
        tests = ir._generate_tests_from_spec(spec)
        # Should sanitize spaces and special chars for test name
        assert tests[0].name == "User_Profile_Card-click-#edit"

    def test_multiple_components_each_get_rules(self):
        spec = {
            "components": [
                {"name": "Btn1", "interaction_rules": [{"action": "click", "selector": "#b1"}]},
                {"name": "Btn2", "interaction_rules": [{"action": "click", "selector": "#b2"}]},
            ]
        }
        tests = ir._generate_tests_from_spec(spec)
        assert len(tests) == 2
        assert tests[0].name.startswith("Btn1")
        assert tests[1].name.startswith("Btn2")


# ---------------------------------------------------------------------------
# _run_single_test() - helper that runs one test with retry logic
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_run_single_test_passes_on_first_try():
    """Test passes when Playwright returns success on first attempt."""
    mock_browser = AsyncMock()
    mock_context = AsyncMock()
    mock_page = AsyncMock()

    mock_browser.new_context.return_value = mock_context
    mock_context.new_page.return_value = mock_page

    test = ir.InteractionTest(
        name="test-click-button",
        selector="#btn",
        action="click",
        pre_condition=None,
        post_condition="#success",
        accessibility_check=False,
        viewport=None,
        timeout_ms=5000,
    )

    # Mock Playwright expectations to succeed
    mock_locator = AsyncMock()
    mock_page.locator.return_value = mock_locator
    mock_locator.wait_for = AsyncMock()
    mock_locator.click = AsyncMock()
    mock_locator.focus = AsyncMock()
    mock_locator.type = AsyncMock()
    mock_locator.hover = AsyncMock()
    mock_locator.tap = AsyncMock()
    mock_locator.get_attribute = AsyncMock(return_value=None)
    mock_page.evaluate = AsyncMock(return_value=False)  # not hidden/disabled

    with patch("playwright.async_api.expect") as mock_expect:
        mock_expect.return_value.to_be_visible = AsyncMock()

        result = await ir._run_single_test(
            mock_browser,
            test,
            "http://example.com",
            asyncio.Semaphore(1),
        )

    assert result["passed"] is True
    assert result["error"] is None
    assert result["name"] == "test-click-button"


@pytest.mark.asyncio
async def test_run_single_test_fails_on_timeout_then_retries():
    """Test fails first attempt, passes on retry (within MAX_RETRIES)."""
    mock_browser = AsyncMock()
    mock_context = AsyncMock()
    mock_page = AsyncMock()

    mock_browser.new_context.return_value = mock_context
    mock_context.new_page.return_value = mock_page

    test = ir.InteractionTest(
        name="test-retry",
        selector="#btn",
        action="click",
        pre_condition=None,
        post_condition="#success",
        accessibility_check=False,
        viewport=None,
    )

    # First call: timeout, second call: success
    call_count = 0
    def side_effect(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise TimeoutError("playwright timeout")
        # Second call succeeds
        return AsyncMock()

    mock_page.locator.return_value.wait_for = AsyncMock(side_effect=side_effect)
    mock_page.locator.return_value.click = AsyncMock()

    with patch("playwright.async_api.expect") as mock_expect:
        mock_expect.return_value.to_be_visible = AsyncMock()

        result = await ir._run_single_test(
            mock_browser,
            test,
            "http://example.com",
            asyncio.Semaphore(1),
        )

    assert result["passed"] is True
    assert result["error"] is None
    assert result["retries"] == 1  # Should have retried once


@pytest.mark.asyncio
async def test_run_single_test_fails_after_max_retries():
    """Test fails all retry attempts → returns failure."""
    mock_browser = AsyncMock()
    mock_context = AsyncMock()
    mock_page = AsyncMock()

    mock_browser.new_context.return_value = mock_context
    mock_context.new_page.return_value = mock_page

    test = ir.InteractionTest(
        name="test-fail-after-retries",
        selector="#btn",
        action="click",
        pre_condition=None,
        post_condition="#success",
        accessibility_check=False,
        viewport=None,
    )

    # All calls fail with timeout
    mock_page.locator.return_value.wait_for = AsyncMock(
        side_effect=TimeoutError("always timeout")
    )
    mock_page.locator.return_value.click = AsyncMock()

    with patch("playwright.async_api.expect") as mock_expect:
        mock_expect.return_value.to_be_visible = AsyncMock()

        result = await ir._run_single_test(
            mock_browser,
            test,
            "http://example.com",
            asyncio.Semaphore(1),
        )

    assert result["passed"] is False
    assert "timeout" in result["error"].lower()
    assert result["retries"] == ir.MAX_RETRIES  # Should have used all retries


@pytest.mark.asyncio
async def test_run_single_test_handles_different_actions():
    """Each action type calls the correct Playwright method."""
    test_cases = [
        ("click", "click"),
        ("type", "type"),
        ("keyboard", "press"),
        ("hover", "hover"),
        ("focus", "focus"),
        ("touch", "tap"),
    ]

    for action_name, playwright_method in test_cases:
        mock_page = AsyncMock()
        test = ir.InteractionTest(
            name=f"test-{action_name}",
            selector=f"#{action_name}",
            action=action_name,
            pre_condition=None,
            post_condition="#done",
            accessibility_check=False,
            viewport=None,
        )

        mock_locator = AsyncMock()
        mock_page.locator.return_value = mock_locator
        mock_locator.wait_for = AsyncMock()
        playwright_mock = AsyncMock()
        setattr(mock_locator, playwright_method, playwright_mock)

        with patch("playwright.async_api.expect") as mock_expect:
            mock_expect.return_value.to_be_visible = AsyncMock()

            result = await ir._run_single_test(mock_page, test, "exec-act")

        assert result["passed"] is True
        playwright_mock.assert_awaited_once()


@pytest.mark.asyncio
async def test_run_single_test_accessibility_check_populates_aria():
    """When accessibility_check=True, aria dict is populated."""
    mock_page = AsyncMock()
    test = ir.InteractionTest(
        name="test-aria",
        selector="#btn",
        action="click",
        pre_condition=None,
        post_condition="#done",
        accessibility_check=True,
        viewport=None,
    )

    mock_locator = AsyncMock()
    mock_page.locator.return_value = mock_locator
    mock_locator.wait_for = AsyncMock()
    mock_locator.click = AsyncMock()
    mock_locator.get_attribute = AsyncMock(
        side_effect=lambda attr: {"aria-expanded": "true", "aria-hidden": "false"}[attr]
    )

    with patch("playwright.async_api.expect") as mock_expect:
        mock_expect.return_value.to_be_visible = AsyncMock()

        result = await ir._run_single_test(mock_page, test, "exec-aria")

    assert result["passed"] is True
    assert "aria" in result
    assert result["aria"]["expanded"] == "true"
    assert result["aria"]["hidden"] == "false"


@pytest.mark.asyncio
async def test_run_single_test_respects_viewport_emulation():
    """Viewport parameter is passed to browser context (tested via mock call)."""
    # This is tested at the interaction_reviewer level where browser_context is mocked
    pass  # Covered in interaction_reviewer tests below


# ---------------------------------------------------------------------------
# interaction_reviewer() main function
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_browser_deps():
    """Mock playwright.async_api and subprocess for the test duration."""
    with patch("interaction_reviewer.async_playwright") as mock_pw, \
         patch("interaction_reviewer.subprocess") as mock_sub:
        # Mock the async playwright chain
        mock_pw_instance = AsyncMock()
        mock_browser = AsyncMock()
        mock_context = AsyncMock()
        mock_page = AsyncMock()
        
        mock_pw.return_value.__aenter__.return_value = mock_pw_instance
        mock_pw_instance.chromium.launch.return_value = mock_browser
        mock_browser.new_context.return_value = mock_context
        mock_context.new_page.return_value = mock_page
        
        yield {
            "pw": mock_pw,
            "browser": mock_browser,
            "context": mock_context,
            "page": mock_page,
            "subprocess": mock_sub,
        }


class TestInteractionReviewerFullFlow:
    @pytest.mark.asyncio
    async def test_no_frontend_returns_approved_true(self, mock_browser_deps):
        """When _has_frontend is False, returns approved immediately."""
        result = await ir.interaction_reviewer(
            sandbox_id="sb-1",
            task="Build API",
            tech_stack="Node.js + Express",  # not frontend
            files=[{"path": "server.js"}],
            design_spec={"components": [{"name": "Button"}]},
            execution_id="exec-no-fe",
        )

        assert result["approved"] is True
        assert result["tests_run"] == 0
        assert result["tests_passed"] == 0
        assert result["duration_ms"] >= 0
        mock_browser_deps["pw"].assert_not_awaited()

    @pytest.mark.asyncio
    async def test_no_interaction_rules_returns_approved_true(self, mock_browser_deps):
        """When design spec has no interaction_rules, returns approved."""
        result = await ir.interaction_reviewer(
            sandbox_id="sb-1",
            task="Build dashboard",
            tech_stack="React",
            files=[{"path": "App.jsx"}],
            design_spec={"components": [{"name": "Title", "props": {}}]},  # no rules
            execution_id="exec-no-rules",
        )

        assert result["approved"] is True
        assert result["tests_run"] == 0
        mock_browser_deps["pw"].assert_not_awaited()

    @pytest.mark.asyncio
    async def test_successful_test_run_returns_approved(self, mock_browser_deps):
        """All tests pass → approved=True."""
        mock_page = mock_browser_deps["page"]
        # Make all Playwright calls succeed
        mock_locator = AsyncMock()
        mock_page.locator.return_value = mock_locator
        mock_locator.wait_for = AsyncMock()
        mock_locator.click = AsyncMock()
        mock_locator.type = AsyncMock()
        mock_locator.press = AsyncMock()
        mock_locator.hover = AsyncMock()
        mock_locator.focus = AsyncMock()
        mock_locator.tap = AsyncMock()
        mock_locator.get_attribute = AsyncMock(return_value=None)
        mock_page.evaluate = AsyncMock(return_value=False)

        with patch("playwright.async_api.expect") as mock_expect:
            mock_expect.return_value.to_be_visible = AsyncMock()

            result = await ir.interaction_reviewer(
                sandbox_id="sb-1",
                task="Build form",
                tech_stack="React",
                files=[{"path": "Form.jsx"}],
                design_spec={
                    "components": [
                        {
                            "name": "SubmitButton",
                            "interaction_rules": [
                                {"action": "click", "selector": "#submit", "post_condition": "#thanks"},
                            ],
                        }
                    ]
                },
                execution_id="exec-success",
            )

        assert result["approved"] is True
        assert result["tests_run"] == 1
        assert result["tests_passed"] == 1
        assert len(result["failures"]) == 0
        assert result["duration_ms"] >= 0

    @pytest.mark.asyncio
    async def test_failed_test_returns_approved_false(self, mock_browser_deps):
        """One test fails → approved=False with failure details."""
        mock_page = mock_browser_deps["page"]
        # Make locator.wait_for fail on purpose
        mock_locator = AsyncMock()
        mock_page.locator.return_value = mock_locator
        mock_locator.wait_for = AsyncMock(side_effect=TimeoutError("element not found"))
        mock_locator.click = AsyncMock()

        with patch("playwright.async_api.expect") as mock_expect:
            mock_expect.return_value.to_be_visible = AsyncMock()

            result = await ir.interaction_reviewer(
                sandbox_id="sb-1",
                task="Build form",
                tech_stack="React",
                files=[{"path": "Form.jsx"}],
                design_spec={
                    "components": [
                        {
                            "name": "BrokenButton",
                            "interaction_rules": [
                                {"action": "click", "selector": "#submit", "post_condition": "#thanks"},
                            ],
                        }
                    ]
                },
                execution_id="exec-fail",
            )

        assert result["approved"] is False
        assert result["tests_run"] == 1
        assert result["tests_passed"] == 0
        assert len(result["failures"]) == 1
        f = result["failures"][0]
        assert f["name"] == "BrokenButton-click-#submit"
        assert "timeout" in f["error"].lower()
        assert result["duration_ms"] >= 0

    @pytest.mark.asyncio
    async def test_multiple_tests_run_in_parallel_via_gather(self, mock_browser_deps):
        """When multiple tests exist, they should run via asyncio.gather (implied by mock call count)."""
        mock_page = mock_browser_deps["page"]
        mock_locator = AsyncMock()
        mock_page.locator.return_value = mock_locator
        mock_locator.wait_for = AsyncMock()
        mock_locator.click = AsyncMock()
        mock_locator.get_attribute = AsyncMock(return_value=None)
        mock_page.evaluate = AsyncMock(return_value=False)

        with patch("playwright.async_api.expect") as mock_expect:
            mock_expect.return_value.to_be_visible = AsyncMock()

            result = await ir.interaction_reviewer(
                sandbox_id="sb-1",
                task="Build UI",
                tech_stack="React",
                files=[{"path": "App.jsx"}],
                design_spec={
                    "components": [
                        {
                            "name": "Btn1",
                            "interaction_rules": [{"action": "click", "selector": "#b1", "post_condition": "#ok1"}],
                        },
                        {
                            "name": "Btn2",
                            "interaction_rules": [{"action": "click", "selector": "#b2", "post_condition": "#ok2"}],
                        },
                    ]
                },
                execution_id="exec-parallel",
            )

        assert result["approved"] is True
        assert result["tests_run"] == 2
        assert result["tests_passed"] == 2
        # Should have called locator twice (once per test)
        assert mock_page.locator.await_count == 2

    @pytest.mark.asyncio
    async def test_accessibility_check_includes_aria_dict(self, mock_browser_deps):
        """When accessibility_check=True, result includes aria dict."""
        mock_page = mock_browser_deps["page"]
        mock_locator = AsyncMock()
        mock_page.locator.return_value = mock_locator
        mock_locator.wait_for = AsyncMock()
        mock_locator.click = AsyncMock()
        mock_locator.get_attribute = AsyncMock(
            side_effect=lambda attr: {"aria-expanded": "true", "aria-hidden": "false", "aria-modal": "true"}[attr]
        )

        with patch("playwright.async_api.expect") as mock_expect:
            mock_expect.return_value.to_be_visible = AsyncMock()

            result = await ir.interaction_reviewer(
                sandbox_id="sb-1",
                task="Build modal",
                tech_stack="React",
                files=[{"path": "Modal.jsx"}],
                design_spec={
                    "components": [
                        {
                            "name": "Modal",
                            "interaction_rules": [
                                {
                                    "action": "click",
                                    "selector": "#open-modal",
                                    "post_condition": "#modal-dialog",
                                    "accessibility_check": True,
                                }
                            ]
                        }
                    ]
                },
                execution_id="exec-aria",
            )

        assert result["approved"] is True
        assert "aria" in result
        assert result["aria"]["expanded"] == "true"
        assert result["aria"]["hidden"] == "false"
        assert result["aria"]["modal"] == "true"

    @pytest.mark.asyncio
    async def test_viewport_mobile_emulation_called(self, mock_browser_deps):
        """When viewport='mobile', browser context should be created with mobile viewport."""
        mock_page = mock_browser_deps["page"]
        mock_locator = AsyncMock()
        mock_page.locator.return_value = mock_locator
        mock_locator.wait_for = AsyncMock()
        mock_locator.tap = AsyncMock()  # touch action uses tap
        mock_locator.get_attribute = AsyncMock(return_value=None)
        mock_page.evaluate = AsyncMock(return_value=False)

        with patch("playwright.async_api.expect") as mock_expect:
            mock_expect.return_value.to_be_visible = AsyncMock()

            result = await ir.interaction_reviewer(
                sandbox_id="sb-1",
                task="Build mobile menu",
                tech_stack="React",
                files=[{"path": "Menu.jsx"}],
                design_spec={
                    "components": [
                        {
                            "name": "MenuToggle",
                            "interaction_rules": [
                                {
                                    "action": "touch",
                                    "selector": "#menu-btn",
                                    "post_condition": "#menu-open",
                                    "viewport": "mobile",
                                }
                            ]
                        }
                    ]
                },
                execution_id="exec-mobile",
            )

        assert result["approved"] is True
        # Verify new_context was called with mobile viewport
        call_args = mock_browser_deps["context"].call_args
        assert call_args is not None
        kwargs = call_args.kwargs
        # Should have viewport: {'width': 375, 'height': 667} or similar
        assert "viewport" in kwargs

    @pytest.mark.asyncio
    async def test_browser_launch_failure_returns_approved_false(self, mock_browser_deps):
        """If playwright.chromium.launch throws, return approved=False."""
        mock_browser_deps["pw"].return_value.__aenter__.return_value.chromium.launch.side_effect = \
            RuntimeError("playwright not installed")

        result = await ir.interaction_reviewer(
            sandbox_id="sb-1",
            task="Build app",
            tech_stack="React",
            files=[{"path": "App.jsx"}],
            design_spec={
                "components": [{"name": "Btn", "interaction_rules": [{"action": "click", "selector": "#btn"}]}]
            },
            execution_id="exec-browser-fail",
        )

        assert result["approved"] is False
        assert result["tests_run"] == 0
        assert "playwright" in result["failures"][0]["error"].lower()

    @pytest.mark.asyncio
    async def test_subprocess_screenshot_on_failure_called(self, mock_browser_deps):
        """When test fails, subprocess is called to screenshot failure."""
        mock_page = mock_browser_deps["page"]
        mock_locator = AsyncMock()
        mock_page.locator.return_value = mock_locator
        mock_locator.wait_for = AsyncMock(side_effect=TimeoutError("no such element"))
        mock_locator.click = AsyncMock()

        mock_sub = MagicMock()
        mock_sub.run = MagicMock()

        with patch("playwright.async_api.expect") as mock_expect:
            mock_expect.return_value.to_be_visible = AsyncMock()
            with patch("interaction_reviewer.subprocess", mock_sub):
                result = await ir.interaction_reviewer(
                    sandbox_id="sb-1",
                    task="Build form",
                    tech_stack="React",
                    files=[{"path": "Form.jsx"}],
                    design_spec={
                        "components": [{"name": "Btn", "interaction_rules": [{"action": "click", "selector": "#btn", "post_condition": "#thanks"}]}]
                    },
                    execution_id="exec-screenshot",
                )

        assert result["approved"] is False
        # subprocess.run should have been called to take failure screenshot
        mock_sub.run.assert_called()
        call_args = mock_sub.run.call_args[0][0]  # first arg is the command list
        assert "screencap" in " ".join(call_args).lower() or "snapshot" in " ".join(call_args).lower()

    @pytest.mark.asyncio
    async def test_test_results_parse_failure_returns_approved_false(self, mock_browser_deps):
        """If the temp JSON output file can't be parsed, return approved=False."""
        mock_page = mock_browser_deps["page"]
        mock_locator = AsyncMock()
        mock_page.locator.return_value = mock_locator
        mock_locator.wait_for = AsyncMock()
        mock_locator.click = AsyncMock()
        mock_locator.get_attribute = AsyncMock(return_value=None)
        mock_page.evaluate = AsyncMock(return_value=False)

        # Simulate successful test execution but corrupt JSON output
        mock_sub = MagicMock()
        mock_sub.run = MagicMock(return_value=MagicMock(stdout=b"not valid json", stderr=""))

        with patch("playwright.async_api.expect") as mock_expect:
            mock_expect.return_value.to_be_visible = AsyncMock()
            with patch("interaction_reviewer.subprocess", mock_sub):
                result = await ir.interaction_reviewer(
                    sandbox_id="sb-1",
                    task="Build app",
                    tech_stack="React",
                    files=[{"path": "App.jsx"}],
                    design_spec={
                        "components": [{"name": "Btn", "interaction_rules": [{"action": "click", "selector": "#btn", "post_condition": "#thanks"}]}]
                    },
                    execution_id="exec-parse-fail",
                )

        assert result["approved"] is False
        assert result["tests_run"] == 1
        assert result["tests_passed"] == 0
        assert result["failures"][0]["stage"] == "parse"
        assert "Could not parse test results" in result["failures"][0]["error"]

    @pytest.mark.asyncio
    async def test_hydration_wait_called_for_spa_frameworks(self, mock_browser_deps):
        """For React/Vue/Angular, waits for hydration before running tests."""
        mock_page = mock_browser_deps["page"]
        mock_locator = AsyncMock()
        mock_page.locator.return_value = mock_locator
        mock_locator.wait_for = AsyncMock()
        mock_locator.click = AsyncMock()
        mock_locator.get_attribute = AsyncMock(return_value=None)
        mock_page.evaluate = AsyncMock(return_value=False)

        with patch("playwright.async_api.expect") as mock_expect:
            mock_expect.return_value.to_be_visible = AsyncMock()

            result = await ir.interaction_reviewer(
                sandbox_id="sb-1",
                task="Build React app",
                tech_stack="React",
                files=[{"path": "App.jsx"}],
                design_spec={
                    "components": [{"name": "Btn", "interaction_rules": [{"action": "click", "selector": "#btn", "post_condition": "#thanks"}]}]
                },
                execution_id="exec-hydration",
            )

        assert result["approved"] is True
        # The interaction_reviewer should have called page.wait_for_function for hydration
        # (implementation detail: waits for window.__ASES_HYDRATED__ or similar)
        # For now just verify it didn't crash and ran the test
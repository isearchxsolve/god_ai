"""
ASES - Design Regenerator (v3.0 compatibility implementation)
=============================================================
Provides the scored design-failure heuristic used by the learned failure
classifier, plus safe fallback implementations for surgical design patching
and full design-spec regeneration.

This module is intentionally dependency-light so it can be imported safely
from tests and from the failure classifier without pulling in optional LLM
or database dependencies.
"""

from copy import deepcopy
import json
import re
from typing import Any, Dict, Optional

# ---------------------------------------------------------------------------
# Keyword weights
# ---------------------------------------------------------------------------
# These mirror the scored heuristic described in the v2.9/v2.10 changes:
# strong design signals outweigh medium/weak signals, while code-level
# counter-signals subtract from the score.

STRONG_DESIGN_SIGNALS = [
    "z-index",
    "clip",
    "overflow",
    "position",
    "layout",
    "stacking",
    "modal clipped",
    "hidden behind",
    "obscured by",
]

MEDIUM_DESIGN_SIGNALS = [
    "contrast",
    "color",
    "typography",
    "font",
    "spacing",
    "breakpoint",
    "responsive",
    "grid",
    "flex",
    "padding",
    "margin",
    "alignment",
    "border",
    "radius",
    "shadow",
]

WEAK_DESIGN_SIGNALS = [
    "state",
    "animation",
    "transition",
    "hover",
    "focus",
    "visible",
    "hidden",
    "display",
]

CODE_COUNTER_SIGNALS = [
    "syntax",
    "import",
    "undefined",
    "typeerror",
    "referenceerror",
    "cannot read",
    "is not a function",
    "unexpected token",
    "module not found",
    "missing dependency",
]


def _extract_description(failure: Any) -> str:
    """
    Extract a textual description from a failure object.

    Accepts:
      - plain string
      - dict with common description keys
      - any other object, stringified as a fallback
    """
    if failure is None:
        return ""

    if isinstance(failure, str):
        return failure

    if isinstance(failure, dict):
        for key in ("description", "message", "text", "error", "issue"):
            value = failure.get(key)
            if value:
                return str(value)
        return ""

    return str(failure)


def score_design_failure(failure: Dict[str, Any]) -> float:
    """
    Score a failure as design-level likelihood in [0.0, 1.0].

    Higher means more likely to require a design-spec change.
    """
    description = _extract_description(failure).lower()
    if not description:
        return 0.0

    score = 0.0

    score += 0.40 * sum(1 for kw in STRONG_DESIGN_SIGNALS if kw in description)
    score += 0.25 * sum(1 for kw in MEDIUM_DESIGN_SIGNALS if kw in description)
    score += 0.15 * sum(1 for kw in WEAK_DESIGN_SIGNALS if kw in description)
    score -= 0.30 * sum(1 for kw in CODE_COUNTER_SIGNALS if kw in description)

    return max(0.0, min(1.0, score))


def is_design_level_failure(failure: Dict[str, Any], threshold: float = 0.5) -> bool:
    """
    Classify a failure as design-level using the scored heuristic.
    """
    return score_design_failure(failure) >= threshold


def _parse_design_json(content: str) -> Optional[Dict[str, Any]]:
    """Safely extract one JSON object from a model response.

    The parser deliberately accepts only JSON objects: callers use the result
    as a design specification and should never execute or evaluate model text.
    """
    if not isinstance(content, str):
        return None
    candidates = [content.strip()]
    fenced = re.search(r"```(?:json)?\s*(.*?)```", content, re.DOTALL | re.IGNORECASE)
    if fenced:
        candidates.append(fenced.group(1).strip())
    loose = re.search(r"(\{.*\})", content, re.DOTALL)
    if loose:
        candidates.append(loose.group(1))
    for candidate in candidates:
        try:
            decoded = json.loads(candidate)
        except (TypeError, json.JSONDecodeError):
            continue
        if isinstance(decoded, dict):
            return decoded
    return None


def _apply_patches(target: Dict[str, Any], patches: Dict[str, Any]) -> None:
    """Apply constrained dotted-key/list-index patches to an in-memory spec.

    Patch paths are data, not code: no attribute access, expressions, or
    traversal are supported. Missing dictionary keys and adjacent list slots
    are created, making repairs deterministic while preserving the input type.
    """
    if not isinstance(target, dict) or not isinstance(patches, dict):
        raise TypeError("target and patches must both be dictionaries")
    segment_pattern = re.compile(r"([A-Za-z_][A-Za-z0-9_-]*)(?:\[(\d+)\])?$")
    for path, value in patches.items():
        if not isinstance(path, str) or not path or ".." in path:
            raise ValueError(f"Invalid patch path: {path!r}")
        segments = path.split(".")
        current: Any = target
        for index, raw_segment in enumerate(segments):
            match = segment_pattern.fullmatch(raw_segment)
            if not match:
                raise ValueError(f"Invalid patch path: {path!r}")
            key, list_index = match.groups()
            last = index == len(segments) - 1
            if not isinstance(current, dict):
                raise ValueError(f"Patch path does not resolve to an object: {path!r}")
            if list_index is None:
                if last:
                    current[key] = value
                    continue
                current = current.setdefault(key, {})
                if not isinstance(current, dict):
                    raise ValueError(f"Patch path collides with a scalar: {path!r}")
                continue
            values = current.setdefault(key, [])
            if not isinstance(values, list):
                raise ValueError(f"Patch path collides with a non-list: {path!r}")
            item_index = int(list_index)
            while len(values) <= item_index:
                values.append(None)
            if last:
                values[item_index] = value
            else:
                if values[item_index] is None:
                    values[item_index] = {}
                if not isinstance(values[item_index], dict):
                    raise ValueError(f"Patch path collides with a scalar: {path!r}")
                current = values[item_index]


def _extract_testids(spec: Optional[Dict[str, Any]]) -> Dict[str, Dict[str, str]]:
    """Return predictable interaction-test selectors for named components."""
    if not isinstance(spec, dict):
        return {}
    result: Dict[str, Dict[str, str]] = {}
    for component in spec.get("components", []):
        if not isinstance(component, dict):
            continue
        name = component.get("name")
        testid = component.get("data_testid")
        if isinstance(name, str) and name and isinstance(testid, str) and testid:
            result[name] = {
                "root": testid,
                "trigger": f"{testid}-trigger",
                "content": f"{testid}-content",
            }
    return result


def _generate_css_variables(spec: Optional[Dict[str, Any]]) -> str:
    """
    Generate a small CSS variable block from design tokens if present.

    This is intentionally conservative: if no tokens are available, it
    returns an empty string.
    """
    if not isinstance(spec, dict):
        return ""

    tokens = spec.get("design_tokens") or spec.get("css_variables") or {}

    if isinstance(tokens, str):
        return tokens

    if not isinstance(tokens, dict) or not tokens:
        design_system = spec.get("design_system", {})
        if not isinstance(design_system, dict):
            return ""
        colors = design_system.get("colors", {})
        typography = design_system.get("typography", {})
        radii = design_system.get("radii", {})
        breakpoints = spec.get("responsive_breakpoints", {})
        flattened: Dict[str, Any] = {}
        if isinstance(colors, dict):
            flattened.update({f"color-{key}": value for key, value in colors.items()})
        if isinstance(typography, dict):
            if "font_family" in typography:
                flattened["font-family"] = typography["font_family"]
            if "body_size" in typography:
                flattened["font-size-body"] = typography["body_size"]
            if isinstance(typography.get("heading_sizes"), dict):
                flattened.update({f"font-size-{key}": value for key, value in typography["heading_sizes"].items()})
        if isinstance(radii, dict):
            flattened.update({f"radius-{key}": value for key, value in radii.items()})
        if isinstance(breakpoints, dict):
            flattened.update({f"breakpoint-{key}": value for key, value in breakpoints.items()})
        tokens = flattened
    if not tokens:
        return ""

    lines = []
    for name, value in tokens.items():
        css_name = str(name).strip().replace("_", "-").lower()
        lines.append(f"--{css_name}: {value};")

    if not lines:
        return ""

    return ":root {\n  " + "\n  ".join(lines) + "\n}"


async def patch_design_spec(
    original_spec: Optional[Dict[str, Any]] = None,
    failure_context: Optional[Dict[str, Any]] = None,
    config: Optional[Any] = None,
    execution_id: str = "",
) -> Optional[Dict[str, Any]]:
    """
    Attempt a surgical design-spec patch.

    This compatibility implementation returns None, signalling that the
    caller should fall back to full regeneration. That keeps behaviour safe
    when no LLM-backed patch strategy is available.
    """
    return None


async def regenerate_design_spec(
    original_spec: Optional[Dict[str, Any]] = None,
    failure_context: Optional[Dict[str, Any]] = None,
    task: str = "",
    tech_stack: str = "",
    requirements: str = "",
    config: Optional[Any] = None,
    execution_id: str = "",
) -> Dict[str, Any]:
    """
    Fallback full design-spec regeneration.

    Returns a full design-result envelope compatible with agent_loop.py.
    Without an LLM backend available, it preserves the original spec and
    marks it as regenerated.
    """
    spec = deepcopy(original_spec) if isinstance(original_spec, dict) else {}
    spec["regenerated"] = True

    if isinstance(failure_context, dict):
        failure_type = failure_context.get("type")
        if failure_type:
            spec["last_regeneration_reason"] = failure_type

    return {
        "has_design": True,
        "spec": spec,
        "css_variables": _generate_css_variables(spec),
        "issues": [],
        "tokens": 0,
        "from_cache": False,
        "regenerated": True,
        "patched": False,
    }

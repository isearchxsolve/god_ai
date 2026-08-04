"""TDD tests for the Scriptwriter agent contract.

Validates the typed I/O schema, validation rules, retry policy math, and
provider fallback chain ordering. These tests assert real behavior of the
dataclasses and helper functions in scriptwriter_contract.py.
"""

from __future__ import annotations

import pytest

from backend.app.agents.contracts.scriptwriter_contract import (
    RetryPolicy,
    SceneBeat,
    ScriptFormat,
    ScriptTone,
    ScriptwriterInput,
    ScriptwriterOutput,
    SCRIPTWRITER_PROVIDER_CHAIN,
    default_retry_policy,
    validate_output_against_input,
)


class TestSceneBeat:
    def test_valid_scene_beat(self):
        beat = SceneBeat(index=0, description="Hero enters the neon-lit alley")
        assert beat.index == 0
        assert beat.description == "Hero enters the neon-lit alley"
        assert beat.dialogue == ""
        assert beat.duration_seconds == 5.0

    def test_negative_index_rejected(self):
        with pytest.raises(ValueError, match="index must be >= 0"):
            SceneBeat(index=-1, description="bad beat")

    def test_empty_description_rejected(self):
        with pytest.raises(ValueError, match="description must be non-empty"):
            SceneBeat(index=0, description="")

    def test_whitespace_description_rejected(self):
        with pytest.raises(ValueError, match="description must be non-empty"):
            SceneBeat(index=0, description="   ")

    def test_zero_duration_rejected(self):
        with pytest.raises(ValueError, match="duration_seconds must be > 0"):
            SceneBeat(index=0, description="beat", duration_seconds=0.0)

    def test_custom_fields_preserved(self):
        beat = SceneBeat(
            index=3,
            description="The chase begins",
            dialogue="Run!",
            shot_direction="Tracking shot, low angle",
            duration_seconds=8.5,
        )
        assert beat.dialogue == "Run!"
        assert beat.shot_direction == "Tracking shot, low angle"
        assert beat.duration_seconds == 8.5


class TestScriptwriterInput:
    def test_valid_input_defaults(self):
        inp = ScriptwriterInput(idea="A robot learns to paint", style_id="anime-90s")
        assert inp.idea == "A robot learns to paint"
        assert inp.style_id == "anime-90s"
        assert inp.target_format == ScriptFormat.CREATIVE_CLIP
        assert inp.tone == ScriptTone.DRAMATIC
        assert inp.language == "en"
        assert inp.reference_asset_ids == ()

    def test_empty_idea_rejected(self):
        with pytest.raises(ValueError, match="idea must be non-empty"):
            ScriptwriterInput(idea="", style_id="anime-90s")

    def test_empty_style_id_rejected(self):
        with pytest.raises(ValueError, match="style_id must be non-empty"):
            ScriptwriterInput(idea="idea", style_id="")

    def test_zero_duration_rejected(self):
        with pytest.raises(ValueError, match="target_duration_seconds must be > 0"):
            ScriptwriterInput(
                idea="idea", style_id="s", target_duration_seconds=0.0
            )

    def test_excessive_duration_rejected(self):
        with pytest.raises(ValueError, match="<= 600"):
            ScriptwriterInput(
                idea="idea", style_id="s", target_duration_seconds=601.0
            )

    def test_reference_assets_immutable(self):
        inp = ScriptwriterInput(
            idea="idea",
            style_id="s",
            reference_asset_ids=("a1", "a2"),
        )
        assert inp.reference_asset_ids == ("a1", "a2")


class TestScriptwriterOutput:
    def _make_beats(self, n: int = 3) -> tuple[SceneBeat, ...]:
        return tuple(
            SceneBeat(index=i, description=f"Beat {i}", duration_seconds=5.0)
            for i in range(n)
        )

    def test_valid_output(self):
        out = ScriptwriterOutput(
            title="The Last Pixel",
            logline="A pixel dreams of becoming a vector.",
            beats=self._make_beats(3),
            raw_text="...",
            provider_used="groq",
            model_used="llama-3.3-70b-versatile",
            tokens_used=512,
        )
        assert out.title == "The Last Pixel"
        assert out.beat_count() == 3
        assert out.total_duration_seconds == 15.0

    def test_empty_title_rejected(self):
        with pytest.raises(ValueError, match="title must be non-empty"):
            ScriptwriterOutput(
                title="",
                logline="logline",
                beats=self._make_beats(1),
                raw_text="",
                provider_used="groq",
                model_used="m",
            )

    def test_empty_logline_rejected(self):
        with pytest.raises(ValueError, match="logline must be non-empty"):
            ScriptwriterOutput(
                title="t",
                logline="",
                beats=self._make_beats(1),
                raw_text="",
                provider_used="groq",
                model_used="m",
            )

    def test_empty_beats_rejected(self):
        with pytest.raises(ValueError, match="beats must contain at least one"):
            ScriptwriterOutput(
                title="t",
                logline="l",
                beats=(),
                raw_text="",
                provider_used="groq",
                model_used="m",
            )

    def test_negative_tokens_rejected(self):
        with pytest.raises(ValueError, match="tokens_used must be >= 0"):
            ScriptwriterOutput(
                title="t",
                logline="l",
                beats=self._make_beats(1),
                raw_text="",
                provider_used="groq",
                model_used="m",
                tokens_used=-1,
            )


class TestRetryPolicy:
    def test_defaults(self):
        rp = default_retry_policy()
        assert rp.max_attempts == 3
        assert rp.base_delay_seconds == 1.0
        assert rp.max_delay_seconds == 30.0
        assert rp.backoff_multiplier == 2.0

    def test_delay_for_attempt_exponential(self):
        rp = RetryPolicy(max_attempts=5, base_delay_seconds=1.0, backoff_multiplier=2.0)
        assert rp.delay_for_attempt(1) == 1.0
        assert rp.delay_for_attempt(2) == 2.0
        assert rp.delay_for_attempt(3) == 4.0
        assert rp.delay_for_attempt(4) == 8.0

    def test_delay_capped_at_max(self):
        rp = RetryPolicy(
            max_attempts=10,
            base_delay_seconds=1.0,
            max_delay_seconds=10.0,
            backoff_multiplier=2.0,
        )
        assert rp.delay_for_attempt(10) == 10.0

    def test_invalid_max_attempts(self):
        with pytest.raises(ValueError, match="max_attempts must be >= 1"):
            RetryPolicy(max_attempts=0)

    def test_invalid_base_delay(self):
        with pytest.raises(ValueError, match="base_delay_seconds must be > 0"):
            RetryPolicy(base_delay_seconds=0.0)

    def test_max_delay_below_base_rejected(self):
        with pytest.raises(ValueError, match="max_delay_seconds must be >= base"):
            RetryPolicy(base_delay_seconds=10.0, max_delay_seconds=1.0)

    def test_attempt_below_one_rejected(self):
        rp = default_retry_policy()
        with pytest.raises(ValueError, match="attempt must be >= 1"):
            rp.delay_for_attempt(0)


class TestProviderChain:
    def test_chain_is_non_empty(self):
        assert len(SCRIPTWRITER_PROVIDER_CHAIN) > 0

    def test_groq_is_primary(self):
        assert SCRIPTWRITER_PROVIDER_CHAIN[0] == "groq"

    def test_chain_has_four_providers(self):
        assert len(SCRIPTWRITER_PROVIDER_CHAIN) == 4

    def test_chain_no_duplicates(self):
        assert len(set(SCRIPTWRITER_PROVIDER_CHAIN)) == len(SCRIPTWRITER_PROVIDER_CHAIN)


class TestValidateOutputAgainstInput:
    def _make_input(self, target: float = 15.0) -> ScriptwriterInput:
        return ScriptwriterInput(
            idea="idea", style_id="s", target_duration_seconds=target
        )

    def _make_output(self, total_duration: float, beats: int = 3) -> ScriptwriterOutput:
        per = total_duration / beats if beats else 0
        beat_tuple = tuple(
            SceneBeat(index=i, description=f"b{i}", duration_seconds=per)
            for i in range(beats)
        )
        return ScriptwriterOutput(
            title="t",
            logline="l",
            beats=beat_tuple,
            raw_text="",
            provider_used="groq",
            model_used="m",
        )

    def test_valid_duration_no_errors(self):
        inp = self._make_input(target=15.0)
        out = self._make_output(total_duration=15.0)
        assert validate_output_against_input(out, inp) == []

    def test_too_short_flagged(self):
        inp = self._make_input(target=20.0)
        out = self._make_output(total_duration=5.0)
        errors = validate_output_against_input(out, inp)
        assert any("too short" in e for e in errors)

    def test_too_long_flagged(self):
        inp = self._make_input(target=10.0)
        out = self._make_output(total_duration=30.0)
        errors = validate_output_against_input(out, inp)
        assert any("too long" in e for e in errors)

    def test_within_tolerance_no_errors(self):
        inp = self._make_input(target=15.0)
        out = self._make_output(total_duration=8.0)
        assert validate_output_against_input(out, inp) == []

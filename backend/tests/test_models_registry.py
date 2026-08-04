"""Tests for the free-tier model registry."""

from __future__ import annotations

from backend.app.registry.models import (
    ModelEntry,
    categories,
    get_model,
    list_models,
    model_count,
    models_by_capability,
    serialize,
)


def test_registry_has_at_least_twenty_five_models():
    assert model_count() >= 25, f"expected >=25 models, got {model_count()}"


def test_registry_covers_all_four_categories():
    cats = set(categories())
    assert {"image", "video", "audio", "text"}.issubset(cats), cats


def test_every_model_has_required_fields():
    for m in list_models():
        assert m.id
        assert m.name
        assert m.provider
        assert m.category in {"image", "video", "audio", "text"}
        assert m.speed in {"fast", "balanced", "slow"}
        assert isinstance(m.capabilities, frozenset)
        assert m.endpoint.startswith(("http://", "https://")), m.endpoint


def test_get_model_returns_entry_for_known_id():
    m = get_model("pollinations/flux")
    assert m is not None
    assert m.provider == "Pollinations"
    assert "ref-image" in m.capabilities


def test_get_model_returns_none_for_unknown_id():
    assert get_model("does/not-exist") is None


def test_list_models_filters_by_category():
    images = list_models("image")
    assert images and all(m.category == "image" for m in images)
    videos = list_models("video")
    assert videos and all(m.category == "video" for m in videos)
    assert not list_models("nonexistent")


def test_models_by_capability_returns_matching_models():
    video_models = models_by_capability("video")
    assert video_models
    assert all("video" in m.capabilities for m in video_models)


def test_pollinations_models_are_keyless_https():
    poll = [m for m in list_models() if m.provider == "Pollinations"]
    assert poll
    for m in poll:
        assert m.endpoint.startswith("https://"), m.endpoint


def test_serialize_round_trips_all_models():
    data = serialize()
    assert len(data) == model_count()
    for entry in data:
        assert isinstance(entry["id"], str)
        assert isinstance(entry["capabilities"], list)
        assert entry["category"] in {"image", "video", "audio", "text"}


def test_model_entry_is_immutable():
    m = get_model("pollinations/flux")
    assert m is not None
    try:
        m.name = "mutated"  # type: ignore[misc]
        raise AssertionError("ModelEntry should be frozen")
    except AttributeError:
        pass


def test_each_model_id_is_unique():
    ids = [m.id for m in list_models()]
    assert len(ids) == len(set(ids)), "duplicate model ids"


def test_to_dict_matches_serialize_entry():
    m = get_model("groq/llama-3.3-70b")
    assert m is not None
    d = m.to_dict()
    assert d["id"] == "groq/llama-3.3-70b"
    assert d["provider"] == "Groq"
    assert "text" in d["capabilities"]

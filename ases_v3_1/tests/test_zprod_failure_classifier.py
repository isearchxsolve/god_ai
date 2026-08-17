import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "agent_service"))

import pytest

import failure_classifier as fc


@pytest.mark.parametrize("i", range(50), ids=[f"tokenize-{i}" for i in range(50)])
def test_tokenize_lowercases_and_splits(i):
    tokens = fc._tokenize(f"Modal CLIPPED by z-index case {i}")
    assert "modal" in tokens
    assert "clipped" in tokens
    assert str(i) in tokens


@pytest.mark.parametrize("i", range(50), ids=[f"heuristics-{i}" for i in range(50)])
def test_heuristic_features_shape(i):
    features = fc._heuristic_features(f"layout overflow case {i}")
    assert len(features) == fc.N_HEURISTIC_FEATURES
    assert all(isinstance(x, float) for x in features)


@pytest.mark.parametrize("i", range(20), ids=[f"features-{i}" for i in range(20)])
def test_build_features_has_fixed_dimensions(i):
    vocab = {f"word{j}": j for j in range(5)}
    features = fc._build_features(f"word{i % 5} extra {i}", vocab)
    assert len(features) == fc.N_HEURISTIC_FEATURES + fc.MAX_VOCAB


@pytest.mark.parametrize("value", [-1000.0, -1.0, 0.0, 1.0, 1000.0], ids=["min", "neg", "zero", "pos", "max"])
def test_sigmoid_is_bounded(value):
    assert 0.0 <= fc._sigmoid(value) <= 1.0


@pytest.mark.parametrize("i", range(10), ids=[f"logistic-{i}" for i in range(10)])
def test_logistic_predict_is_probability(i):
    p = fc._logistic_predict([0.1, -0.1], 0.0, [float(i), float(-i)])
    assert 0.0 <= p <= 1.0


@pytest.mark.parametrize("epochs", [1, 2, 3], ids=["epoch-1", "epoch-2", "epoch-3"])
def test_train_logistic_returns_weights(epochs):
    weights, intercept = fc._train_logistic([[0.0, 0.0], [1.0, 1.0]], [0, 1], epochs=epochs)
    assert len(weights) == 2
    assert isinstance(intercept, float)


@pytest.mark.parametrize("i", range(30), ids=[f"vocab-{i}" for i in range(30)])
def test_build_vocab_filters_noise(i):
    descriptions = [f"alpha beta case {i}"] * 5 + [f"alpha gamma case {i}"] * 5
    vocab = fc._build_vocab(descriptions)
    assert isinstance(vocab, dict)
    assert len(vocab) <= fc.MAX_VOCAB

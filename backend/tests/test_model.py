from types import SimpleNamespace

import numpy as np
import pytest

from project import model as model_module
from project.config import load_config
from project.model import FakeBackend, ModelConfigError, load_backend, pick_device
from tests.synthetic import GLASS, PINK, PURPLE, he_slide, solid


@pytest.fixture
def cfg():
    return load_config()


def mixed_tiles():
    return [solid(PINK), solid(PURPLE), solid(GLASS), solid((150, 100, 170)), he_slide(256, 256)]


def test_probabilities_per_tile_sum_to_one(cfg):
    probs = FakeBackend(cfg).predict(mixed_tiles())
    np.testing.assert_allclose(probs.sum(axis=1), 1.0, atol=1e-5)
    assert (probs >= 0).all()


def test_one_row_per_tile_and_one_column_per_class(cfg):
    backend = FakeBackend(cfg)
    for n in (0, 1, 7, cfg["batch_size"] + 3):
        assert backend.predict([solid(PINK)] * n).shape == (n, len(cfg["classes"]))


def test_same_tile_in_same_scores_out(cfg):
    first = FakeBackend(cfg).predict(mixed_tiles())
    second = FakeBackend(cfg).predict(mixed_tiles())
    np.testing.assert_array_equal(first, second)


def test_fake_backend_scores_pink_purple_above_pale(cfg):
    probs = FakeBackend(cfg).predict([solid((150, 100, 170)), solid((235, 225, 230))])
    tumor = cfg["classes"].index("tumor")
    assert probs[0, tumor] > probs[1, tumor]


def test_fake_config_loads_the_fake_backend(cfg):
    backend = load_backend({**cfg, "model": "fake"})
    assert isinstance(backend, FakeBackend) and backend.name == "fake"


def test_conch_without_a_token_refuses_to_start(cfg, monkeypatch):
    monkeypatch.delenv("HF_TOKEN", raising=False)
    monkeypatch.setattr(model_module, "cached_hf_token", lambda: None)  # no `hf auth login` either
    with pytest.raises(ModelConfigError, match="HF_TOKEN"):
        load_backend({**cfg, "model": "conch"})


def test_conch_load_failure_raises_instead_of_falling_back(cfg, monkeypatch):
    token = "hf_test_value_not_a_real_token"
    monkeypatch.setenv("HF_TOKEN", token)

    def fail_to_load(cfg, token):
        raise OSError(f"401 Unauthorized for token {token}: pytorch_model.bin not found")

    monkeypatch.setattr(model_module, "ConchBackend", fail_to_load)
    with pytest.raises(ModelConfigError, match="Could not load CONCH") as err:
        load_backend({**cfg, "model": "conch"})
    assert token not in str(err.value)


def test_unknown_model_name_is_rejected(cfg):
    with pytest.raises(ModelConfigError, match="model"):
        load_backend({**cfg, "model": "resnet"})


def fake_torch(cuda, mps):
    return SimpleNamespace(
        cuda=SimpleNamespace(is_available=lambda: cuda),
        backends=SimpleNamespace(mps=SimpleNamespace(is_available=lambda: mps)),
    )


def test_device_order_is_cuda_then_mps_then_cpu():
    assert pick_device(fake_torch(cuda=True, mps=True)) == "cuda"
    assert pick_device(fake_torch(cuda=False, mps=True)) == "mps"
    assert pick_device(fake_torch(cuda=False, mps=False)) == "cpu"


# --- organ-aware prompts -------------------------------------------------------------------------

from project.model import prompts_for


def test_prompts_for_an_organ_override_only_its_classes(cfg):
    lung = prompts_for(cfg, "lung")
    assert list(lung) == cfg["classes"]
    assert lung["tumor"] == cfg["organ_prompts"]["lung"]["tumor"]
    assert lung["stroma"] == cfg["prompts"]["stroma"]          # not overridden: generic
    assert prompts_for(cfg, "other") == {c: cfg["prompts"][c] for c in cfg["classes"]}
    assert prompts_for(cfg, None) == prompts_for(cfg, cfg["default_organ"])


def test_unknown_organ_is_rejected(cfg):
    with pytest.raises(ValueError, match="organ"):
        prompts_for(cfg, "spleen")


def test_predict_is_classify_of_embed(cfg):
    backend = FakeBackend(cfg)
    tiles = mixed_tiles()
    emb = backend.embed(tiles)
    assert emb.shape[0] == len(tiles)
    np.testing.assert_allclose(backend.classify(emb, "lung"), backend.predict(tiles, organ="lung"))
    assert backend.classify(emb[:0], "other").shape == (0, len(cfg["classes"]))

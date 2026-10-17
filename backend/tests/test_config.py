import pytest
import yaml

from project.config import REQUIRED_KEYS, ConfigError, load_config


def test_config_loads_with_every_required_key():
    cfg = load_config()
    for key in REQUIRED_KEYS:
        assert key in cfg, f"config.yaml is missing '{key}'"
    assert cfg["model"] in ("conch", "fake")
    assert set(cfg["prompts"]) == set(cfg["classes"])
    assert cfg["classes"] == ["tumor", "stroma", "immune", "necrosis", "normal", "fat_other"]


def test_missing_key_is_reported(tmp_path):
    cfg = load_config()
    del cfg["tile_px"]
    path = tmp_path / "config.yaml"
    path.write_text(yaml.safe_dump(cfg))
    with pytest.raises(ConfigError, match="tile_px"):
        load_config(path)


def test_organs_and_their_prompts_are_consistent():
    cfg = load_config()
    assert cfg["organs"] == ["colon", "lung", "breast", "pancreas", "prostate", "other"]
    assert cfg["default_organ"] in cfg["organs"]
    assert set(cfg["organ_prompts"]) <= set(cfg["organs"]) - {"other"}
    for organ, override in cfg["organ_prompts"].items():
        assert set(override) <= set(cfg["classes"]), organ
        assert all(isinstance(p, str) and p for prompts in override.values() for p in prompts), organ
    assert cfg["tcga"]["organ"] in cfg["organs"]

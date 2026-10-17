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

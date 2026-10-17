import pytest
import yaml

from project.config import REQUIRED_KEYS, ConfigError, load_config, with_prompt_set


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


def test_every_prompt_set_covers_every_class():
    cfg = load_config()
    assert "v2" in cfg["prompt_sets"]
    for name, prompts in cfg["prompt_sets"].items():
        assert set(prompts) == set(cfg["classes"]), f"prompt set {name} doesn't match classes"
        assert all(prompts[c] for c in cfg["classes"]), f"prompt set {name} has a class with no prompts"


def test_prompts_come_from_the_selected_set():
    cfg = load_config()
    assert cfg["prompts"] == cfg["prompt_sets"][cfg["prompt_set"]]
    other = with_prompt_set(cfg, "v2")
    assert other["prompt_set"] == "v2"
    assert other["prompts"] == cfg["prompt_sets"]["v2"]
    assert cfg["prompts"] == cfg["prompt_sets"][cfg["prompt_set"]]  # the original is untouched


def test_unknown_prompt_set_is_reported(tmp_path):
    cfg = load_config()
    cfg["prompt_set"] = "v99"
    path = tmp_path / "config.yaml"
    path.write_text(yaml.safe_dump(cfg))
    with pytest.raises(ConfigError, match="v99"):
        load_config(path)

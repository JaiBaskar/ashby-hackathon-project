import pytest
import yaml

from project.config import REPO_ROOT, REQUIRED_KEYS, ConfigError, load_config, with_prompt_set


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


def test_every_prompt_set_covers_every_class():
    cfg = load_config()
    assert "v2" in cfg["prompt_sets"]
    for name, pset in cfg["prompt_sets"].items():
        prompts = {k: v for k, v in pset.items() if k != "organs"}  # organs: optional per-organ overrides
        assert set(prompts) == set(cfg["classes"]), f"prompt set {name} doesn't match classes"
        assert all(prompts[c] for c in cfg["classes"]), f"prompt set {name} has a class with no prompts"


def test_prompts_come_from_the_selected_set():
    cfg = load_config()
    selected = cfg["prompt_sets"][cfg["prompt_set"]]
    assert cfg["prompts"] == {k: v for k, v in selected.items() if k != "organs"}
    assert cfg["organ_prompts"] == (selected.get("organs") or {})
    other = with_prompt_set(cfg, "v2")
    assert other["prompt_set"] == "v2"
    assert other["prompts"] == cfg["prompt_sets"]["v2"]
    assert other["organ_prompts"] == {}
    assert cfg["prompts"] == {k: v for k, v in selected.items() if k != "organs"}  # the original is untouched


def test_unknown_prompt_set_is_reported(tmp_path):
    cfg = load_config()
    cfg["prompt_set"] = "v99"
    path = tmp_path / "config.yaml"
    path.write_text(yaml.safe_dump(cfg))
    with pytest.raises(ConfigError, match="v99"):
        load_config(path)


def test_box_sizes_are_whole_tiles_and_include_the_default():
    cfg = load_config()
    tile_um = cfg["tile_px"] * cfg["target_mpp"]
    assert cfg["box_sizes_um"] == sorted(cfg["box_sizes_um"])
    for size in cfg["box_sizes_um"]:
        assert size / tile_um == round(size / tile_um) >= 1, f"{size} µm is not a whole number of tiles"
    assert cfg["region_tiles"] * tile_um in cfg["box_sizes_um"]


@pytest.mark.parametrize("sizes, message", [([512, 1000], "1000"), ([1024, 2048], "512")])
def test_bad_box_sizes_are_reported(tmp_path, sizes, message):
    cfg = load_config()
    cfg["box_sizes_um"] = sizes  # 1000 µm isn't a whole number of 128 µm tiles; the 512 µm default is missing
    path = tmp_path / "config.yaml"
    path.write_text(yaml.safe_dump(cfg))
    with pytest.raises(ConfigError, match=message):
        load_config(path)


def test_project_model_env_overrides_the_configured_model(monkeypatch):
    monkeypatch.setenv("PROJECT_MODEL", "fake")
    assert load_config()["model"] == "fake"
    monkeypatch.delenv("PROJECT_MODEL")
    assert load_config()["model"] == yaml.safe_load((REPO_ROOT / "config.yaml").read_text())["model"]

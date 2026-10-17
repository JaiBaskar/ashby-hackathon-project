"""Loads config.yaml, the single home for paths, seeds and thresholds (AGENTS.md §3)."""

import os
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]

REQUIRED_KEYS = [
    "model", "seed", "classes", "prompt_set", "prompt_sets",
    "tile_px", "target_mpp", "default_mpp", "max_display_px", "max_upload_mb", "max_tiles",
    "tissue_min_saturation", "tissue_threshold", "batch_size",
    "region_tiles", "box_sizes_um", "min_coverage", "top_k", "weights", "reason_cutoffs", "paths",
]


class ConfigError(ValueError):
    pass


def load_config(path=None):
    path = Path(path or os.environ.get("PROJECT_CONFIG") or REPO_ROOT / "config.yaml")
    cfg = yaml.safe_load(path.read_text())
    missing = [k for k in REQUIRED_KEYS if k not in cfg]
    if missing:
        raise ConfigError(f"{path} is missing required keys: {', '.join(missing)}")
    check_box_sizes(cfg, path)
    return with_prompt_set(cfg, cfg["prompt_set"])


def check_box_sizes(cfg, path):
    """Every offered box is a whole number of tiles, and the default box (region_tiles) is on offer."""
    tile_um = cfg["tile_px"] * cfg["target_mpp"]
    for size in cfg["box_sizes_um"]:
        if size < tile_um or abs(size / tile_um - round(size / tile_um)) > 1e-9:
            raise ConfigError(f"{path}: box size {size} µm is not a whole number of {tile_um:g} µm tiles")
    default = cfg["region_tiles"] * tile_um
    if default not in cfg["box_sizes_um"]:
        raise ConfigError(f"{path}: box_sizes_um must include the default box, {default:g} µm (region_tiles)")


def with_prompt_set(cfg, name):
    """A copy of cfg whose `prompts` are prompt_sets[name]; the model reads only `prompts`."""
    if name not in cfg["prompt_sets"]:
        raise ConfigError(f"prompt_set '{name}' is not in prompt_sets ({', '.join(cfg['prompt_sets'])})")
    return {**cfg, "prompt_set": name, "prompts": cfg["prompt_sets"][name]}


def repo_path(relative):
    """Resolve a path from config.yaml against the repo root."""
    return REPO_ROOT / relative

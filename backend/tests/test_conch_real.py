"""Real CONCH checks: `make test-real`. Needs CONCH access, a Hugging Face token and the weights.

Never run on the Delta login node (rules.md §1); on Delta use an approved GPU job.
"""

import json

import numpy as np
import pytest
from PIL import Image

from project.config import load_config, repo_path, with_prompt_set
from project.evaldata import TUMOR, bcss_tiles
from project.metrics import auroc
from project.model import find_hf_token, load_backend
from tests.synthetic import PURPLE, he_slide, solid

pytestmark = pytest.mark.realmodel

N_CRC_TILES = 200
N_BCSS_TILES = 300
MIN_AUROC = 0.8  # fixed before any BCSS run (reports/decisions.md)
PROMPT_SETS = ["v2"]  # v1 (colon-leaning) was retired after the CRC + BCSS comparison


@pytest.fixture(scope="module")
def cfg():
    return load_config()


@pytest.fixture(scope="module")
def conch_for(cfg):
    if not find_hf_token():
        pytest.fail("make test-real needs HF_TOKEN (or `hf auth login`) from an account with CONCH access.")
    backends = {}

    def get(prompt_set):
        if prompt_set not in backends:
            backends[prompt_set] = load_backend({**with_prompt_set(cfg, prompt_set), "model": "conch"})
        return backends[prompt_set]
    return get


def test_real_conch_same_tile_same_scores(conch_for, cfg):
    conch = conch_for(cfg["prompt_set"])
    tiles = [he_slide(256, 256), solid(PURPLE)]
    first, second = conch.predict(tiles), conch.predict(tiles)
    assert first.shape == (2, len(cfg["classes"]))
    np.testing.assert_allclose(first, second, atol=1e-5)
    np.testing.assert_allclose(first.sum(axis=1), 1.0, atol=1e-5)


def crc_tiles(cfg):
    """CRC-VAL-HE-7K (Kather et al. 2019): colorectal, 224 px tiles at 0.5 µm/px, one folder per class."""
    root = repo_path(cfg["paths"]["crc_val_dir"])
    files = sorted(root.glob("*/*.tif"))
    if not files:
        pytest.skip(f"CRC-VAL-HE-7K not found at {root} (config key paths.crc_val_dir). "
                    "Get it with scripts/get_crc_val.sh.")
    rng = np.random.default_rng(cfg["seed"])
    picked = [files[i] for i in sorted(rng.choice(len(files), size=N_CRC_TILES, replace=False))]
    images = [Image.open(p).convert("RGB") for p in picked]
    return images, np.array([p.parent.name == "TUM" for p in picked]), {
        "dataset": "CRC-VAL-HE-7K (Kather et al. 2019), colorectal", "positive": "TUM"}


def bcss(cfg):
    """BCSS (Amgad et al. 2019): TCGA breast regions with tissue masks (scripts/get_bcss.py)."""
    root = repo_path(cfg["paths"]["bcss_dir"])
    if not (root / "masks").is_dir():
        pytest.skip(f"BCSS not found at {root} (config key paths.bcss_dir). Get it with scripts/get_bcss.py.")
    tiles = bcss_tiles(root, n=N_BCSS_TILES, seed=cfg["seed"])
    return [t.image for t in tiles], np.array([t.code == TUMOR for t in tiles]), {
        "dataset": "BCSS (Amgad et al. 2019), TCGA breast", "positive": "tumor (code 1)",
        "n_rois": len({t.roi for t in tiles})}


@pytest.mark.parametrize("prompt_set", PROMPT_SETS)
@pytest.mark.parametrize("dataset", ["crc", "bcss"])
def test_real_conch_tumor_auroc(conch_for, cfg, dataset, prompt_set):
    images, is_tumor, meta = {"crc": crc_tiles, "bcss": bcss}[dataset](cfg)
    probs = conch_for(prompt_set).predict(images)
    score = auroc(is_tumor, probs[:, cfg["classes"].index("tumor")])

    out = repo_path(cfg["paths"]["results"]) / f"conch_auroc_{dataset}_{prompt_set}.json"
    out.write_text(json.dumps({
        "metric": "tumor vs rest AUROC, zero-shot",
        "auroc": round(float(score), 4),
        "n_tiles": len(images),
        "n_tumor": int(is_tumor.sum()),
        "seed": cfg["seed"],
        "prompt_set": prompt_set,
        **meta,
    }, indent=2) + "\n")
    assert score >= MIN_AUROC, f"{dataset}/{prompt_set}: tumor-vs-rest AUROC {score:.3f} < {MIN_AUROC} ({out})"

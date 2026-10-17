"""Real CONCH checks: `make test-real`. Needs CONCH access, a Hugging Face token and the weights.

Never run on the Delta login node (rules.md §1); on Delta use an approved GPU job.
"""

import json

import numpy as np
import pytest
from PIL import Image

from project.config import load_config, repo_path
from project.metrics import auroc
from project.model import find_hf_token, load_backend
from tests.synthetic import PURPLE, he_slide, solid

pytestmark = pytest.mark.realmodel

N_CRC_TILES = 200


@pytest.fixture(scope="module")
def cfg():
    return load_config()


@pytest.fixture(scope="module")
def conch(cfg):
    if not find_hf_token():
        pytest.fail("make test-real needs HF_TOKEN (or `hf auth login`) from an account with CONCH access.")
    return load_backend({**cfg, "model": "conch"})


def test_real_conch_same_tile_same_scores(conch, cfg):
    tiles = [he_slide(256, 256), solid(PURPLE)]
    first, second = conch.predict(tiles), conch.predict(tiles)
    assert first.shape == (2, len(cfg["classes"]))
    np.testing.assert_allclose(first, second, atol=1e-5)
    np.testing.assert_allclose(first.sum(axis=1), 1.0, atol=1e-5)


def test_real_conch_tumor_auroc_on_crc_val_he_7k(conch, cfg):
    root = repo_path(cfg["paths"]["crc_val_dir"])
    files = sorted(root.glob("*/*.tif"))
    if not files:
        pytest.skip(
            f"CRC-VAL-HE-7K not found at {root} (config key paths.crc_val_dir). "
            "Get it with scripts/get_crc_val.sh."
        )
    rng = np.random.default_rng(cfg["seed"])
    picked = [files[i] for i in sorted(rng.choice(len(files), size=N_CRC_TILES, replace=False))]
    is_tumor = np.array([p.parent.name == "TUM" for p in picked])
    probs = conch.predict([Image.open(p).convert("RGB") for p in picked])
    score = auroc(is_tumor, probs[:, cfg["classes"].index("tumor")])

    out = repo_path(cfg["paths"]["results"]) / f"conch_auroc_{cfg['prompt_set']}.json"
    out.write_text(json.dumps({
        "metric": "tumor (TUM) vs rest AUROC, zero-shot",
        "auroc": round(float(score), 4),
        "n_tiles": len(picked),
        "n_tumor": int(is_tumor.sum()),
        "seed": cfg["seed"],
        "prompt_set": cfg["prompt_set"],
        "dataset": "CRC-VAL-HE-7K (Kather et al. 2019)",
    }, indent=2) + "\n")
    assert score >= 0.8, f"tumor-vs-rest AUROC {score:.3f} < 0.8 (written to {out})"

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
    # CRC-VAL-HE-7K is colorectal tissue, so the colon prompts are the ones the app would use; the generic
    # ("other") prompts are recorded too. These 200 tiles were never used to choose prompts.
    emb = conch.embed([Image.open(p).convert("RGB") for p in picked])
    t = cfg["classes"].index("tumor")
    score = auroc(is_tumor, conch.classify(emb, "colon")[:, t])
    score_generic = auroc(is_tumor, conch.classify(emb, "other")[:, t])

    out = repo_path(cfg["paths"]["results"]) / f"conch_auroc_{cfg['prompt_set']}.json"
    out.write_text(json.dumps({
        "metric": "tumor (TUM) vs rest AUROC, zero-shot",
        "auroc": round(float(score), 4),
        "organ": "colon",
        "auroc_generic_prompts": round(float(score_generic), 4),
        "n_tiles": len(picked),
        "n_tumor": int(is_tumor.sum()),
        "seed": cfg["seed"],
        "prompt_set": cfg["prompt_set"],
        "dataset": "CRC-VAL-HE-7K (Kather et al. 2019)",
    }, indent=2) + "\n")
    assert score >= 0.8, f"tumor-vs-rest AUROC {score:.3f} < 0.8 (written to {out})"


def test_real_conch_slide_pipeline_tracks_known_tumor_share(conch, cfg, tmp_path):
    """Mosaic .svs slides of labeled CRC tiles with 10%, 50% and 90% tumor tiles, through the same
    score_slide the TCGA validation uses. Catches slide-reading bugs (pipeline ≠ tiles scored directly)
    and shows how the whole-slide tumor % relates to the true tumor share."""
    from project.ingest import open_slide
    from project.tcga import score_slide
    from project.tiling import build_grid
    from tests.test_tcga import mosaic
    from tests.synthetic import save_tiled_tiff

    root = repo_path(cfg["paths"]["crc_val_dir"])
    if not sorted(root.glob("TUM/*.tif")):
        pytest.skip(f"CRC-VAL-HE-7K not found at {root} (config key paths.crc_val_dir).")
    tumor_files = sorted(root.glob("TUM/*.tif"))
    other_files = sorted(p for p in root.glob("*/*.tif") if p.parent.name not in ("TUM", "BACK"))
    rng = np.random.default_rng(cfg["seed"])
    tile_px, n_cells, t = cfg["tile_px"], 36, cfg["classes"].index("tumor")

    rows = []
    for share in (0.1, 0.5, 0.9):
        n_tum = round(share * n_cells)
        picks = [tumor_files[i] for i in rng.choice(len(tumor_files), n_tum, replace=False)]
        picks += [other_files[i] for i in rng.choice(len(other_files), n_cells - n_tum, replace=False)]
        picks = [picks[i] for i in rng.permutation(n_cells)]
        cells = [Image.open(p).convert("RGB").resize((tile_px, tile_px), Image.BILINEAR) for p in picks]
        path = tmp_path / f"mosaic_{share}.svs"
        save_tiled_tiff(mosaic(cells, 6, tile_px), path, mpp=cfg["target_mpp"])

        out = score_slide(path, cfg, conch, organ="colon")
        # Compare on the same cells the pipeline kept: tiles that aren't mostly tissue (e.g. fat) are skipped.
        kept = [t.row * 6 + t.col for t in build_grid(open_slide(path, None, cfg["default_mpp"]), cfg).tiles]
        probs = conch.predict([cells[i] for i in kept], organ="colon")
        rows.append({
            "true_tumor_share_pct": 100 * n_tum / n_cells,
            "pipeline_tumor_pct": round(out["app_tumor_pct"], 2),
            "direct_tumor_pct": round(float(probs[:, t].mean() * 100), 2),
            "tiles_called_tumor_pct": round(float((probs.argmax(axis=1) == t).mean() * 100), 2),
            "n_tiles": out["n_tiles"],
        })

    out_path = repo_path(cfg["paths"]["results"]) / f"conch_pipeline_check_{cfg['prompt_set']}.json"
    out_path.write_text(json.dumps({"dataset": "CRC-VAL-HE-7K mosaics, 6x6 tiles, BACK excluded", "organ": "colon",
                                    "seed": cfg["seed"], "rows": rows}, indent=2) + "\n")
    for r in rows:
        assert abs(r["pipeline_tumor_pct"] - r["direct_tumor_pct"]) < 1.0, r   # the reading path adds no error
    pipeline = [r["pipeline_tumor_pct"] for r in rows]
    assert pipeline == sorted(pipeline) and pipeline[-1] - pipeline[0] > 20, rows   # more tumor → higher %

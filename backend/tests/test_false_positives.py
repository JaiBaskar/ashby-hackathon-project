"""False positives: the app suggesting a region as tumor-rich where there is no tumor.

Fast tests (demo model, synthetic images) check that low or scattered tumor scores never become a suggested
region. The realmodel tests (`make test-real`) run real CONCH, through the same slide-reading path as the app,
on mosaic slides built only from tiles that experts labeled as non-tumor (CRC-VAL-HE-7K, BCSS), and expect no
region at all. Each dataset also gets a tumor-only mosaic as a positive control, so "no regions" can't come
from a pipeline that never suggests any.
"""

import io
import json
import time

import numpy as np
import pytest
from fastapi.testclient import TestClient
from PIL import Image

from project.api import create_app
from project.config import load_config, repo_path
from project.evaldata import TUMOR, bcss_tiles
from project.ingest import open_slide
from project.regions import eligible_windows, meets_minimum, rank_regions, score_grid
from project.tiling import build_grid, read_tiles
from tests.synthetic import save_tiled_tiff, solid
from tests.test_regions import full_tissue, grid
from tests.test_tcga import mosaic

STROMA = (225, 140, 160)  # deep eosin pink: tissue the demo model scores well under 20% tumor


@pytest.fixture
def cfg():
    return load_config()


# --- fast: the ranking never turns weak or scattered tumor scores into a region -------------------

def test_scattered_tumor_like_tiles_dont_make_a_region(cfg):
    # One 95% tile in every 4 × 4 block on a 5% background: every window averages (15 × 5% + 95%) / 16 ≈ 11%.
    assert cfg["region_tiles"] == 4
    probs = grid(cfg, 16, 16, tumor=0.05)
    probs[::4, ::4] = grid(cfg, 4, 4, tumor=0.95)
    regions, note = rank_regions(probs, full_tissue(16, 16), cfg, tile_size=256, scale=1.0)
    assert regions == []
    assert "11%" in note


def test_a_dense_tumor_patch_still_makes_a_region(cfg):
    # The control for the test above: the same tiles gathered into one block do make a region there.
    probs = grid(cfg, 16, 16, tumor=0.05)
    probs[8:12, 4:8] = grid(cfg, 4, 4, tumor=0.95)
    regions, _ = rank_regions(probs, full_tissue(16, 16), cfg, tile_size=256, scale=1.0)
    assert (regions[0]["row"], regions[0]["col"]) == (8, 4)


def test_tumor_free_slide_gets_no_regions_end_to_end(cfg, tmp_path, monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    cfg["model"] = "fake"
    cfg["paths"] = {**cfg["paths"], "uploads": str(tmp_path / "uploads"), "jobs": str(tmp_path / "jobs")}
    client = TestClient(create_app(cfg))
    buf = io.BytesIO()
    solid(STROMA, size=(4096, 3072)).save(buf, format="PNG")  # 16 × 12 tiles: room for a 1024 µm box too
    job_id = client.post("/api/jobs", files={"file": ("slide.png", buf.getvalue(), "image/png")}).json()["job_id"]

    deadline = time.monotonic() + 30
    while (body := client.get(f"/api/jobs/{job_id}").json())["status"] not in ("done", "error"):
        assert time.monotonic() < deadline, body
        time.sleep(0.02)
    assert body["status"] == "done", body
    result = body["result"]
    assert result["slide_composition"]["tumor"] < cfg["min_tumor_pct"] / 100
    assert result["regions"] == []
    assert "20% tumor minimum" in result["note"]

    bigger = client.get(f"/api/jobs/{job_id}/regions", params={"box_um": 1024}).json()
    assert bigger["regions"] == [] and "tumor minimum" in bigger["note"]
    assert client.get(f"/api/jobs/{job_id}/heatmap.png").status_code == 200  # the heatmap is still there to look at
    row = next(j for j in client.get("/api/jobs").json()["jobs"] if j["id"] == job_id)
    assert row["best_tumor"] is None and row["n_regions"] == 0


# --- real CONCH on expert-labeled non-tumor tissue -------------------------------------------------

N_SIDE = 8                # mosaics are 8 × 8 tiles: 25 candidate windows of 4 × 4
N_BCSS_SAMPLE = 1500      # BCSS tiles sampled before splitting into non-tumor and tumor
CRC_NON_TUMOR = ["NORM", "STR", "MUS", "LYM", "DEB", "MUC"]  # BACK and ADI are glass and fat, dropped by the tissue filter
BCSS_CODES = {2: "stroma", 3: "lymphocytic_infiltrate", 4: "necrosis_or_debris"}


def crc_mosaics(cfg, rng):
    """{name: (cells, is_tumor)}: one mosaic per CRC-VAL-HE-7K non-tumor class, one mixing them, one all TUM."""
    root = repo_path(cfg["paths"]["crc_val_dir"])
    if not sorted(root.glob("TUM/*.tif")):
        pytest.skip(f"CRC-VAL-HE-7K not found at {root} (config key paths.crc_val_dir). Get it with scripts/get_crc_val.sh.")
    n = N_SIDE * N_SIDE

    def pick(files, k):
        return [Image.open(files[i]).convert("RGB") for i in sorted(rng.choice(len(files), k, replace=False))]

    out = {c: (pick(sorted(root.glob(f"{c}/*.tif")), n), False) for c in CRC_NON_TUMOR}
    mixed = sorted(p for c in CRC_NON_TUMOR for p in root.glob(f"{c}/*.tif"))
    out["mixed non-tumor"] = (pick(mixed, n), False)
    out["TUM (control)"] = (pick(sorted(root.glob("TUM/*.tif")), n), True)
    return out, "colon", "CRC-VAL-HE-7K (Kather et al. 2019), colorectal"


def bcss_mosaics(cfg, rng):
    """{name: (cells, is_tumor)}: BCSS non-tumor classes with enough tiles, all non-tumor mixed, and tumor."""
    root = repo_path(cfg["paths"]["bcss_dir"])
    if not (root / "masks").is_dir():
        pytest.skip(f"BCSS not found at {root} (config key paths.bcss_dir). Get it with scripts/get_bcss.py.")
    tiles = bcss_tiles(root, n=N_BCSS_SAMPLE, seed=cfg["seed"])
    n = N_SIDE * N_SIDE

    def pick(group):
        return [group[i].image for i in sorted(rng.choice(len(group), n, replace=False))]

    out = {}
    for code, name in BCSS_CODES.items():
        group = [t for t in tiles if t.code == code]
        if len(group) >= n:
            out[name] = (pick(group), False)
    out["mixed non-tumor"] = (pick([t for t in tiles if t.code != TUMOR]), False)
    out["tumor (control)"] = (pick([t for t in tiles if t.code == TUMOR]), True)
    return out, "breast", "BCSS (Amgad et al. 2019), TCGA breast"


def through_the_app(cells, path, cfg, backend, organ):
    """The mosaic as a scanned slide, read, tiled, scored and ranked exactly as an upload would be."""
    tile_px = cfg["tile_px"]
    save_tiled_tiff(mosaic([c.resize((tile_px, tile_px), Image.BILINEAR) for c in cells], N_SIDE, tile_px),
                    path, mpp=cfg["target_mpp"])
    slide = open_slide(path, None, cfg["default_mpp"])
    grid_ = build_grid(slide, cfg)
    probs = backend.predict(read_tiles(slide, grid_.tiles, tile_px), organ=organ)
    grid_probs = score_grid(grid_.tiles, probs, grid_.tissue.shape)
    regions, note = rank_regions(grid_probs, grid_.tissue, cfg, grid_.tile_size, grid_.scale)
    return probs, regions, note, eligible_windows(grid_probs, grid_.tissue, cfg)


@pytest.mark.realmodel
@pytest.mark.parametrize("dataset", ["crc", "bcss"])
def test_real_conch_suggests_no_region_on_tissue_without_tumor(cfg, dataset, tmp_path):
    from project.model import find_hf_token, load_backend

    if not find_hf_token():
        pytest.fail("make test-real needs HF_TOKEN (or `hf auth login`) from an account with CONCH access.")
    rng = np.random.default_rng(cfg["seed"])
    mosaics, organ, source = {"crc": crc_mosaics, "bcss": bcss_mosaics}[dataset](cfg, rng)
    conch = load_backend({**cfg, "model": "conch"})
    t, minimum = cfg["classes"].index("tumor"), cfg["min_tumor_pct"]

    rows = []
    for i, (name, (cells, is_tumor)) in enumerate(mosaics.items()):
        probs, regions, note, windows = through_the_app(cells, tmp_path / f"mosaic_{i}.svs", cfg, conch, organ)
        window_tumor = [w["composition"]["tumor"] for w in windows]
        rows.append({
            "mosaic": name,
            "has_tumor": is_tumor,
            "n_tiles": len(probs),
            "mean_tile_tumor_pct": round(float(probs[:, t].mean() * 100), 2),
            "tiles_tumor_top_class_pct": round(float((probs.argmax(axis=1) == t).mean() * 100), 2),
            "tiles_tumor_ge_50_pct": round(float((probs[:, t] >= 0.5).mean() * 100), 2),
            "n_windows": len(windows),
            "windows_at_minimum": sum(meets_minimum(v, minimum) for v in window_tumor),
            "max_window_tumor_pct": round(max(window_tumor, default=0.0) * 100, 2),
            "n_regions": len(regions),
            "note": note,
        })

    clean = [r for r in rows if not r["has_tumor"]]
    out = repo_path(cfg["paths"]["results"]) / f"false_positives_{dataset}_{cfg['prompt_set']}.json"
    out.write_text(json.dumps({
        "check": "regions suggested on mosaics with no tumor tile (false positives), real CONCH zero-shot",
        "dataset": source,
        "organ": organ,
        "prompt_set": cfg["prompt_set"],
        "seed": cfg["seed"],
        "mosaic_tiles": f"{N_SIDE}x{N_SIDE}",
        "region_tiles": cfg["region_tiles"],
        "min_tumor_pct": minimum,
        "non_tumor_mosaics": len(clean),
        "non_tumor_mosaics_with_regions": sum(r["n_regions"] > 0 for r in clean),
        "non_tumor_windows_at_minimum": sum(r["windows_at_minimum"] for r in clean),
        "non_tumor_windows": sum(r["n_windows"] for r in clean),
        "rows": rows,
    }, indent=2) + "\n")

    control = [r for r in rows if r["has_tumor"]]
    assert control and all(r["n_regions"] > 0 for r in control), f"tumor control got no regions ({out})"
    false_positives = [r["mosaic"] for r in clean if r["n_regions"] > 0]
    assert not false_positives, f"{dataset}: regions suggested on tumor-free tissue: {false_positives} ({out})"

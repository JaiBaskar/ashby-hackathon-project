"""Phase 8: scoring slides with the app's pipeline and comparing app vs. pathologist vs. ABSOLUTE.

Synthetic images and numbers only (AGENTS.md §6, §7).
"""

import numpy as np
import pandas as pd
import pytest

from project.config import load_config
from project.ingest import open_slide
from project.model import FakeBackend
from project.tcga import apply_mapping, evaluate, fit_mapping, score_slide
from project.tiling import build_grid, read_tiles
from tests.synthetic import he_slide


@pytest.fixture
def cfg():
    return load_config()


def test_score_slide_is_the_mean_tile_tumor_probability(tmp_path, cfg):
    path = tmp_path / "slide.png"
    he_slide(2048, 1536).save(path)
    backend = FakeBackend(cfg)
    out = score_slide(path, cfg, backend)

    slide = open_slide(path, None, cfg["default_mpp"])
    grid = build_grid(slide, cfg)
    probs = backend.predict(read_tiles(slide, grid.tiles, cfg["tile_px"]))
    expected = 100 * probs[:, cfg["classes"].index("tumor")].mean()
    assert out["app_tumor_pct"] == pytest.approx(expected)
    assert 0 <= out["app_tumor_pct"] <= 100
    assert out["n_tiles"] == len(grid.tiles) > 0
    assert out["model"] == "fake"


def test_fit_mapping_hand_computed():
    # Truth = 0.5 × app + 10 exactly → slope 0.5, intercept 10.
    slope, intercept = fit_mapping([0, 50, 100], [10, 35, 60])
    assert slope == pytest.approx(0.5) and intercept == pytest.approx(10.0)
    np.testing.assert_allclose(apply_mapping([20, 300, -100], slope, intercept), [20, 100, 0])  # clipped to 0–100


def labels_and_scores(seed=0):
    rng = np.random.default_rng(seed)
    rows, scores = [], []
    for split, n in (("train", 40), ("cal", 10), ("test", 60)):
        for i in range(n):
            sid = f"{split}-{i}"
            truth = float(rng.uniform(15, 95))
            rows.append({"slide_id": sid, "hospital": f"{split[:2]}{i % 5}", "split": split,
                         "pathologist_pct": float(np.clip(truth + 15 + rng.normal(0, 12), 0, 100)),
                         "truth_pct": truth})
            scores.append({"slide_id": sid, "app_tumor_pct": float(np.clip(0.5 * truth + 5 + rng.normal(0, 5), 0, 100)),
                           "model": "fake"})
    return pd.DataFrame(rows), pd.DataFrame(scores)


def run(cfg, labels, scores):
    return evaluate(labels, scores, cfg["tcga"], seed=cfg["seed"])


def test_evaluate_compares_on_the_same_test_slides(cfg):
    labels, scores = labels_and_scores()
    scores = scores[scores.slide_id != "test-0"]          # one test slide wasn't scored
    out = run(cfg, labels, scores)
    assert out["split"] == "test"
    assert out["n_slides"] == 59
    assert out["n_test_slides_without_app_score"] == 1
    assert out["n_hospitals"] == labels[labels.split == "test"].hospital.nunique()
    assert out["n_below_cutoff"] == int((labels[(labels.split == "test") & (labels.slide_id != "test-0")]
                                          .truth_pct < cfg["tcga"]["catch_cutoff"]).sum())
    for method in ("pathologist", "app_raw", "app_calibrated"):
        assert set(out["methods"][method]) == {"mae", "pearson_r", "catch_rate"}
    for key in ("app_raw", "app_calibrated"):
        b = out["bootstrap"][key]
        assert b["n"] == cfg["tcga"]["n_bootstrap"]
        assert b["ci_low"] <= b["diff"] <= b["ci_high"]
        assert b["verdict"] in ("better", "comparable", "worse")


def test_pathologist_numbers_match_a_direct_computation(cfg):
    labels, scores = labels_and_scores()
    out = run(cfg, labels, scores)
    test = labels[labels.split == "test"]
    assert out["methods"]["pathologist"]["mae"] == pytest.approx(
        np.abs(test.pathologist_pct - test.truth_pct).mean())


def test_mapping_is_fit_on_train_hospitals_only(cfg):
    labels, scores = labels_and_scores()
    base = run(cfg, labels, scores)["mapping"]

    moved_test = labels.copy()
    moved_test.loc[moved_test.split == "test", "truth_pct"] = 50.0   # test truth must not touch the fit
    assert run(cfg, moved_test, scores)["mapping"] == base

    moved_train = labels.copy()
    moved_train.loc[moved_train.split == "train", "truth_pct"] *= 0.5
    assert run(cfg, moved_train, scores)["mapping"] != base
    assert base["fit_on"] == "train" and base["n_slides"] == 40


def test_no_hospital_shared_between_train_and_test_is_enforced(cfg):
    labels, scores = labels_and_scores()
    labels.loc[labels.slide_id == "train-0", "hospital"] = labels.loc[labels.slide_id == "test-0", "hospital"].iloc[0]
    with pytest.raises(ValueError, match="hospital"):
        run(cfg, labels, scores)


def test_tcga_dir_env_var_wins(cfg, monkeypatch, tmp_path):
    from project.tcga import tcga_dir

    monkeypatch.delenv("TCGA_DIR", raising=False)
    assert tcga_dir(cfg).name == "tcga"
    monkeypatch.setenv("TCGA_DIR", str(tmp_path))
    assert tcga_dir(cfg) == tmp_path

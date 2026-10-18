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
        assert set(out["methods"][method]) == {"mae", "pearson_r", "catch_rate", "within_hospital_r", "between_hospital_r", "n_hospitals_within"}
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


# --- train-only checks before the test split is touched -------------------------------------------

from project.tcga import slides_to_score, split_check


def test_slides_to_score_filters_by_split_and_skips_done():
    labels = pd.DataFrame({"slide_id": ["a", "b", "c", "d", "e"],
                           "split": ["train", "test", "train", "train", "cal"],
                           "selected": [True, True, True, False, True]})
    on_disk = {"a", "b", "c", "d", "e"} - {"c"}
    todo = slides_to_score(labels, done={"x"}, splits=["train"], exists=lambda s: s in on_disk)
    assert todo == ["a"]                       # c isn't downloaded, d isn't selected, b and e are other splits
    assert slides_to_score(labels, done={"a"}, splits=["train", "test"], exists=lambda s: True) == ["b", "c"]


def test_split_check_uses_only_that_split(cfg):
    labels, scores = labels_and_scores()
    out = split_check(labels, scores, "train", cutoff=cfg["tcga"]["catch_cutoff"])
    train = labels[labels.split == "train"].merge(scores, on="slide_id")
    assert out["split"] == "train" and out["n_slides"] == 40
    assert out["app_raw"]["pearson_r"] == pytest.approx(np.corrcoef(train.app_tumor_pct, train.truth_pct)[0, 1])
    assert out["pathologist"]["mae"] == pytest.approx(np.abs(train.pathologist_pct - train.truth_pct).mean())
    assert out["app_raw"]["min"] <= out["app_raw"]["median"] <= out["app_raw"]["max"]


def test_split_check_refuses_the_test_split(cfg):
    labels, scores = labels_and_scores()
    with pytest.raises(ValueError, match="test"):
        split_check(labels, scores, "test", cutoff=60)


# --- the slide-reading path gives the same scores as the tiles themselves -------------------------

from PIL import Image

from tests.synthetic import GLASS, PINK, PURPLE, save_tiled_tiff, solid


def mosaic(cells, cols, tile_px):
    """Paste equal-size cell images row-major into one image."""
    rows = -(-len(cells) // cols)
    img = Image.new("RGB", (cols * tile_px, rows * tile_px), GLASS)
    for i, cell in enumerate(cells):
        img.paste(cell.resize((tile_px, tile_px)), ((i % cols) * tile_px, (i // cols) * tile_px))
    return img


def test_scanned_slide_scores_match_scoring_its_tiles_directly(tmp_path, cfg):
    # A .svs (tiled TIFF through OpenSlide) built from known tiles at target_mpp: every tile the pipeline
    # cuts should be exactly one cell, so the slide's tumor % equals the mean over the cells scored directly.
    tile_px = cfg["tile_px"]
    colors = [PURPLE, PINK, (150, 100, 170), (200, 120, 160), (120, 80, 150), (225, 170, 190)]
    cells = [solid(colors[i % len(colors)], size=(tile_px, tile_px)) for i in range(24)]
    path = tmp_path / "mosaic.svs"
    save_tiled_tiff(mosaic(cells, 6, tile_px), path, mpp=cfg["target_mpp"])

    backend = FakeBackend(cfg)
    out = score_slide(path, cfg, backend)
    direct = backend.predict(cells)[:, cfg["classes"].index("tumor")].mean() * 100
    assert out["mpp"] == pytest.approx(cfg["target_mpp"]) and out["mpp_estimated"] is False
    assert out["n_tiles"] == len(cells)
    assert out["app_tumor_pct"] == pytest.approx(direct, abs=0.5)


# --- embeddings: one GPU pass, any prompt set re-scored later ------------------------------------

from project.tcga import score_from_embeddings, scores_path


def test_score_slide_saves_embeddings_in_the_agreed_format(tmp_path, cfg):
    path = tmp_path / "slide.png"
    he_slide(2048, 1536).save(path)
    backend = FakeBackend(cfg)
    emb_path = tmp_path / "emb" / "slide.npz"
    out = score_slide(path, cfg, backend, organ="lung", emb_path=emb_path)

    z = np.load(emb_path)
    assert z["feats"].dtype == np.float32 and z["feats"].shape[0] == out["n_tiles"]
    assert z["coords"].dtype == np.int64 and z["coords"].shape == (out["n_tiles"], 2)
    assert str(z["model"]) == "fake"
    grid = build_grid(open_slide(path, None, cfg["default_mpp"]), cfg)
    np.testing.assert_array_equal(z["coords"], [[t.x, t.y] for t in grid.tiles])   # columns (x, y), AGENTS.md §4
    assert out["organ"] == "lung" and out["prompt_set"] == cfg["prompt_set"]


def test_rescoring_from_embeddings_matches_scoring_the_slide(tmp_path, cfg):
    path = tmp_path / "slide.png"
    he_slide(2048, 1536).save(path)
    backend = FakeBackend(cfg)
    emb_path = tmp_path / "slide.npz"
    first = score_slide(path, cfg, backend, organ="colon", emb_path=emb_path)
    again = score_from_embeddings(emb_path, cfg, backend, organ="colon")
    for key in ("app_tumor_pct", "app_necrosis_pct", "n_tiles", "organ", "prompt_set", "model"):
        assert again[key] == pytest.approx(first[key]) if isinstance(first[key], float) else again[key] == first[key]


def test_scores_file_is_per_prompt_set(cfg, tmp_path, monkeypatch):
    monkeypatch.setenv("TCGA_DIR", str(tmp_path))
    assert scores_path(cfg) == tmp_path / f"app_scores_{cfg['prompt_set']}.csv"
    assert scores_path({**cfg, "prompt_set": "v9"}).name == "app_scores_v9.csv"


# --- explore (train only) and evaluating a chosen method on test ---------------------------------

from project.tcga import explore
from tests.test_purity_models import synthetic


def labelled(df, test_hospitals=("H8", "H9")):
    labels = df[["slide_id", "hospital", "truth_pct", "pathologist_pct"]].assign(
        split=np.where(df["hospital"].isin(test_hospitals), "test", "train"))
    feats = df.drop(columns=["hospital", "truth_pct", "pathologist_pct"])
    return labels, feats


def test_explore_compares_every_method_on_train_hospitals_only(cfg):
    labels, feats = labelled(synthetic(signal=True))
    out = explore(labels, feats, "train", cutoff=cfg["tcga"]["catch_cutoff"], seed=cfg["seed"])
    assert out["split"] == "train" and out["n_slides"] == (labels.split == "train").sum()
    assert out["cv"] == "leave-one-hospital-out" and out["n_hospitals"] == 8
    from project.purity_models import METHODS
    assert set(out["methods"]) == set(METHODS) | {"pathologist"}
    for m in out["methods"].values():
        assert set(m) >= {"mae", "pearson_r"}
    assert out["methods"]["ridge_embedding"]["mae"] < out["methods"]["dummy"]["mae"]
    assert out["shuffled_labels"]["ridge_embedding_mae"] >= 0.95 * out["shuffled_labels"]["dummy_mae"]


def test_explore_refuses_the_test_split(cfg):
    labels, feats = labelled(synthetic())
    with pytest.raises(ValueError, match="test"):
        explore(labels, feats, "test", cutoff=60, seed=1)


def test_evaluate_adds_a_chosen_method_fit_on_train(cfg):
    df = synthetic(signal=True)
    labels, feats = labelled(df)
    scores = feats[["slide_id"]].assign(app_tumor_pct=df["p_tumor"] * 100, model="conch")
    out = evaluate(labels, scores, cfg["tcga"], seed=cfg["seed"], features=feats, method="ridge_embedding")
    m = out["methods"]["app_ridge_embedding"]
    assert set(m) == {"mae", "pearson_r", "catch_rate", "within_hospital_r", "between_hospital_r", "n_hospitals_within"}
    assert out["bootstrap"]["app_ridge_embedding"]["verdict"] in ("better", "comparable", "worse")
    assert out["chosen_method"] == "ridge_embedding"
    # changing test truth leaves the method's predictions alone (it never saw test)
    moved = labels.assign(truth_pct=np.where(labels.split == "test", 50.0, labels.truth_pct))
    again = evaluate(moved, scores, cfg["tcga"], seed=cfg["seed"], features=feats, method="ridge_embedding")
    assert again["predictions_fingerprint"] == out["predictions_fingerprint"]


def test_explore_reports_within_hospital_signal(cfg):
    labels, feats = labelled(synthetic(signal=True))
    out = explore(labels, feats, "train", cutoff=cfg["tcga"]["catch_cutoff"], seed=cfg["seed"])
    ridge = out["methods"]["ridge_embedding"]
    assert ridge["within_hospital_r"] > 0.5            # it reads the slide, not just the hospital
    assert "between_hospital_r" in ridge and "within_hospital_r" in out["methods"]["pathologist"]


def test_evaluate_reports_within_hospital_signal_for_the_chosen_method(cfg):
    df = synthetic(signal=True)
    labels, feats = labelled(df, test_hospitals=("H6", "H7", "H8", "H9"))
    scores = feats[["slide_id"]].assign(app_tumor_pct=df["p_tumor"] * 100, model="conch")
    out = evaluate(labels, scores, cfg["tcga"], seed=cfg["seed"], features=feats, method="ridge_embedding")
    assert "within_hospital_r" in out["methods"]["app_ridge_embedding"]
    assert "within_hospital_r" in out["methods"]["pathologist"]


def test_explore_shows_no_within_hospital_signal_when_embeddings_only_encode_the_hospital(cfg):
    from tests.test_purity_models import hospital_only

    labels, feats = labelled(hospital_only())
    out = explore(labels, feats, "train", cutoff=cfg["tcga"]["catch_cutoff"], seed=cfg["seed"])
    assert abs(out["methods"]["ridge_embedding"]["within_hospital_r"]) < 0.3

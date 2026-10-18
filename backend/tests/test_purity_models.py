"""Slide-level purity methods, compared by leave-one-hospital-out CV on train (AGENTS.md §8 Phase 4).

Synthetic numbers only (AGENTS.md §6, §7).
"""

import numpy as np
import pandas as pd
import pytest

from project.purity_models import (
    METHODS,
    cross_validate,
    fit_predict,
    hospital_folds,
    ridge_fit,
    ridge_predict,
    slide_features,
)


# --- building blocks ------------------------------------------------------------------------------

def test_hospital_folds_never_share_a_hospital():
    hospitals = np.array(["A", "A", "B", "C", "C", "C", "D"])
    folds = hospital_folds(hospitals)
    assert len(folds) == 4
    seen = []
    for train, val in folds:
        assert not set(hospitals[train]) & set(hospitals[val])
        assert len(set(hospitals[val])) == 1
        seen += list(val)
    assert sorted(seen) == list(range(len(hospitals)))   # every slide is predicted exactly once


def test_ridge_hand_computed():
    # y = 2x exactly. With alpha = 0 the fit is exact; with alpha > 0 the slope shrinks toward 0.
    X, y = np.array([[1.0], [2.0], [3.0]]), np.array([2.0, 4.0, 6.0])
    np.testing.assert_allclose(ridge_predict(ridge_fit(X, y, alpha=0.0), np.array([[4.0]])), [8.0], atol=1e-9)
    # Features are standardized (z = (x - 2) / sd, so sum z^2 = 3) and the intercept isn't penalized.
    # z-slope = sum z(y - mean y) / (sum z^2 + alpha): alpha = 3 halves it, so the x-slope is 1, not 2,
    # and x = 4 predicts mean y + 1 * (4 - 2) = 4 + 2 = 6.
    np.testing.assert_allclose(ridge_predict(ridge_fit(X, y, alpha=3.0), np.array([[4.0]])), [6.0], atol=1e-9)


def test_slide_features_from_tile_probabilities():
    classes = ["tumor", "stroma", "immune", "necrosis", "normal", "fat_other"]
    probs = np.array([
        [0.6, 0.1, 0.1, 0.1, 0.05, 0.05],   # tumor wins
        [0.2, 0.5, 0.1, 0.1, 0.05, 0.05],   # stroma wins
        [0.1, 0.1, 0.1, 0.1, 0.1, 0.5],     # fat/other wins
        [0.5, 0.1, 0.1, 0.2, 0.05, 0.05],   # tumor wins
    ])
    emb = np.arange(8, dtype=np.float32).reshape(4, 2)
    f = slide_features(probs, emb, classes)
    assert f["p_tumor"] == pytest.approx(probs[:, 0].mean())
    assert f["share_tumor"] == pytest.approx(0.5) and f["share_fat_other"] == pytest.approx(0.25)
    # tumor among cell-containing classes (tumor, stroma, immune, normal), per tile then averaged
    cells = probs[:, [0, 1, 2, 4]].sum(axis=1)
    assert f["tumor_vs_cells"] == pytest.approx((probs[:, 0] / cells).mean())
    assert [f["emb_0"], f["emb_1"]] == pytest.approx([3.0, 4.0])


# --- methods on synthetic slides ------------------------------------------------------------------

def synthetic(n_hospitals=10, per=12, signal=True, seed=0):
    """Slides whose embedding carries purity (signal=True) or nothing (signal=False)."""
    rng = np.random.default_rng(seed)
    rows = []
    direction = rng.normal(size=16)
    direction /= np.linalg.norm(direction)
    for h in range(n_hospitals):
        for i in range(per):
            truth = float(rng.uniform(15, 90))
            emb = rng.normal(0, 1, 16) + (direction * (truth - 50) / 10 if signal else 0)
            tumor = np.clip(truth / 100 + rng.normal(0, 0.05), 0.01, 0.99) if signal else rng.uniform(0.1, 0.9)
            row = {"slide_id": f"h{h}-{i}", "hospital": f"H{h}", "truth_pct": truth,
                   "pathologist_pct": float(np.clip(truth + 20 + rng.normal(0, 15), 0, 100)),
                   "p_tumor": tumor, "share_tumor": tumor, "tumor_vs_cells": tumor}
            row.update({f"emb_{k}": float(v) for k, v in enumerate(emb)})
            rows.append(row)
    return pd.DataFrame(rows)


def test_cross_validation_predicts_every_slide_once_and_clips():
    df = synthetic()
    for name in METHODS:
        pred = cross_validate(df, name, seed=1)
        assert pred.shape == (len(df),) and np.isfinite(pred).all(), name
        assert (pred >= 0).all() and (pred <= 100).all(), name


def test_dummy_predicts_the_training_fold_median():
    df = synthetic()
    pred = cross_validate(df, "dummy", seed=1)
    for train, val in hospital_folds(df["hospital"].to_numpy()):
        assert pred[val] == pytest.approx(np.median(df["truth_pct"].to_numpy()[train]))


def test_ridge_beats_dummy_when_there_is_signal():
    df = synthetic(signal=True)
    mae = lambda p: np.abs(p - df["truth_pct"]).mean()
    assert mae(cross_validate(df, "ridge_embedding", seed=1)) < 0.7 * mae(cross_validate(df, "dummy", seed=1))


def test_shuffled_labels_give_no_better_than_dummy():
    df = synthetic(signal=True)
    shuffled = df.assign(truth_pct=np.random.default_rng(3).permutation(df["truth_pct"].to_numpy()))
    mae = lambda p: np.abs(p - shuffled["truth_pct"]).mean()
    assert mae(cross_validate(shuffled, "ridge_embedding", seed=1)) >= 0.95 * mae(cross_validate(shuffled, "dummy", seed=1))


def test_same_seed_same_predictions():
    df = synthetic()
    np.testing.assert_array_equal(cross_validate(df, "ridge_embedding", seed=5), cross_validate(df, "ridge_embedding", seed=5))


def test_fit_predict_uses_only_the_training_rows():
    df = synthetic()
    train, test = df[df.hospital != "H0"], df[df.hospital == "H0"]
    base = fit_predict(train, test, "ridge_embedding", seed=1)
    moved = test.assign(truth_pct=50.0)                       # test truth must not matter
    np.testing.assert_array_equal(fit_predict(train, moved, "ridge_embedding", seed=1), base)
    with pytest.raises(ValueError, match="hospital"):
        fit_predict(df, test, "ridge_embedding", seed=1)      # a test hospital inside training


def hospital_only(n_hospitals=10, per=12, seed=0):
    """Slides whose embedding only says which hospital they came from; purity varies by hospital."""
    rng = np.random.default_rng(seed)
    rows = []
    for h in range(n_hospitals):
        level, site = rng.uniform(20, 80), rng.normal(0, 3, 16)
        for i in range(per):
            row = {"slide_id": f"h{h}-{i}", "hospital": f"H{h}", "truth_pct": float(level + rng.normal(0, 10)),
                   "pathologist_pct": 80.0, "p_tumor": 0.5, "share_tumor": 0.5, "tumor_vs_cells": 0.5}
            row.update({f"emb_{k}": float(v) for k, v in enumerate(site + rng.normal(0, 0.3, 16))})
            rows.append(row)
    return pd.DataFrame(rows)

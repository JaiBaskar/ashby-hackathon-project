"""Small NumPy metrics, each with a hand-computed test (AGENTS.md §7)."""

import numpy as np


def auroc(labels, scores):
    """Area under the ROC curve: the chance a random positive outscores a random negative (ties count half)."""
    labels = np.asarray(labels).astype(bool)
    scores = np.asarray(scores, dtype=float)
    n_pos = int(labels.sum())
    n_neg = labels.size - n_pos
    if n_pos == 0 or n_neg == 0:
        raise ValueError("AUROC needs at least one positive and one negative label")
    _, inverse, counts = np.unique(scores, return_inverse=True, return_counts=True)
    ranks = (np.cumsum(counts) - (counts - 1) / 2)[inverse]  # average 1-based rank within ties
    return float((ranks[labels].sum() - n_pos * (n_pos + 1) / 2) / (n_pos * n_neg))


# --- purity metrics (AGENTS.md §1): always computed for the app and the pathologist on the same slides ---

def mae(truth, pred):
    """Mean absolute error, in percentage points."""
    return float(np.mean(np.abs(np.asarray(pred, float) - np.asarray(truth, float))))


def pearson_r(x, y):
    x, y = np.asarray(x, float), np.asarray(y, float)
    dx, dy = x - x.mean(), y - y.mean()
    denom = np.sqrt((dx ** 2).sum() * (dy ** 2).sum())
    return float((dx * dy).sum() / denom) if denom > 0 else float("nan")  # undefined for a constant input


def catch_rate(truth, pred, cutoff):
    """Among slides truly below the cutoff, the share the method also puts below it."""
    truth, pred = np.asarray(truth, float), np.asarray(pred, float)
    low = truth < cutoff
    if not low.any():
        raise ValueError(f"catch rate needs at least one slide with truth below {cutoff}")
    return float((pred[low] < cutoff).mean())


def bootstrap_mae_diff(truth, pathologist, app, n, seed):
    """Pathologist MAE − app MAE, with a 95% percentile interval from n seeded resamples of the slides."""
    truth, path, app = (np.asarray(v, float) for v in (truth, pathologist, app))
    err_path, err_app = np.abs(path - truth), np.abs(app - truth)
    idx = np.random.default_rng(seed).integers(0, len(truth), (n, len(truth)))
    diffs = err_path[idx].mean(axis=1) - err_app[idx].mean(axis=1)
    lo, hi = np.percentile(diffs, [2.5, 97.5])
    return {"diff": float(err_path.mean() - err_app.mean()), "ci_low": float(lo), "ci_high": float(hi), "n": n}


def verdict(ci_low, ci_high):
    """'better' only when the whole interval of (pathologist MAE − app MAE) is above 0 (AGENTS.md §8 Phase 5)."""
    if ci_low > 0:
        return "better"
    if ci_high < 0:
        return "worse"
    return "comparable"

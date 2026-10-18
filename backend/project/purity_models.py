"""Slide-level purity methods built on CONCH tile outputs, compared by leave-one-hospital-out CV.

Every method maps one slide's features to a purity % and is fit on training hospitals only (AGENTS.md §8 Phase 4):
  dummy             the training median, whatever the slide (the bar every method must beat)
  mean_tumor_prob   straight line from the mean tile tumor probability (the app's whole-slide tumor %)
  tumor_tile_share  straight line from the share of tiles whose top class is tumor
  tumor_vs_cells    straight line from tumor / (tumor + stroma + immune + normal), per tile, averaged
  ridge_embedding   ridge regression from the mean CONCH embedding plus tumor_tile_share; alpha picked by
                    leave-one-hospital-out CV inside the training hospitals only (nested)
CONCH itself is never trained; only these small slide-level fits are.
"""

import numpy as np

CELL_CLASSES = ("tumor", "stroma", "immune", "normal")
ALPHAS = [0.1, 1.0, 10.0, 100.0, 1000.0, 10000.0]


def slide_features(probs, embeddings, classes):
    """One slide's features from its tiles' class probabilities [N, C] and CONCH embeddings [N, D]."""
    probs = np.asarray(probs, float)
    out = {f"p_{c}": float(probs[:, i].mean()) for i, c in enumerate(classes)}
    top = probs.argmax(axis=1)
    out.update({f"share_{c}": float((top == i).mean()) for i, c in enumerate(classes)})
    cells = probs[:, [classes.index(c) for c in CELL_CLASSES]].sum(axis=1)
    out["tumor_vs_cells"] = float((probs[:, classes.index("tumor")] / np.maximum(cells, 1e-12)).mean())
    out.update({f"emb_{k}": float(v) for k, v in enumerate(np.asarray(embeddings, float).mean(axis=0))})
    return out


def hospital_folds(hospitals):
    """Leave-one-hospital-out: (train indices, validation indices), one fold per hospital."""
    hospitals = np.asarray(hospitals)
    return [(np.flatnonzero(hospitals != h), np.flatnonzero(hospitals == h)) for h in sorted(set(hospitals))]


def ridge_fit(X, y, alpha):
    """Ridge on standardized features; the intercept isn't penalized."""
    X, y = np.asarray(X, float), np.asarray(y, float)
    mu, sd = X.mean(axis=0), X.std(axis=0)
    sd = np.where(sd > 0, sd, 1.0)
    Z = (X - mu) / sd
    w = np.linalg.solve(Z.T @ Z + alpha * np.eye(Z.shape[1]), Z.T @ (y - y.mean()))
    return {"w": w, "b": float(y.mean()), "mu": mu, "sd": sd}


def ridge_predict(model, X):
    return ((np.asarray(X, float) - model["mu"]) / model["sd"]) @ model["w"] + model["b"]


def _columns(df, prefix):
    return [c for c in df.columns if c.startswith(prefix)]


def _fit_line(x, y):
    slope, intercept = np.polyfit(np.asarray(x, float), np.asarray(y, float), 1)
    return lambda new: slope * np.asarray(new, float) + intercept


def _ridge_features(df):
    return df[_columns(df, "emb_") + ["share_tumor"]].to_numpy(float)


def _fit(train, method, seed):
    """A function from a features frame to predictions, fit on `train` only."""
    y = train["truth_pct"].to_numpy(float)
    if method == "dummy":
        median = float(np.median(y))
        return lambda df: np.full(len(df), median)
    if method in ("mean_tumor_prob", "tumor_tile_share", "tumor_vs_cells"):
        col = {"mean_tumor_prob": "p_tumor", "tumor_tile_share": "share_tumor", "tumor_vs_cells": "tumor_vs_cells"}[method]
        line = _fit_line(train[col], y)
        return lambda df: line(df[col])
    if method == "ridge_embedding":
        X = _ridge_features(train)
        folds = hospital_folds(train["hospital"].to_numpy())
        errors = []
        for alpha in ALPHAS:  # inner CV on the training hospitals only
            err = [np.abs(ridge_predict(ridge_fit(X[tr], y[tr], alpha), X[va]) - y[va]).mean() for tr, va in folds]
            errors.append(np.mean(err))
        model = ridge_fit(X, y, ALPHAS[int(np.argmin(errors))])
        return lambda df: ridge_predict(model, _ridge_features(df))
    raise ValueError(f"unknown method '{method}'; choose one of {', '.join(METHODS)}")


METHODS = ["dummy", "mean_tumor_prob", "tumor_tile_share", "tumor_vs_cells", "ridge_embedding"]


def fit_predict(train, test, method, seed):
    """Fit on train, predict test, clipped to [0, 100]. Refuses any hospital in both."""
    shared = set(train["hospital"]) & set(test["hospital"])
    if shared:
        raise ValueError(f"hospital in both training and prediction rows: {', '.join(sorted(shared))}")
    return np.clip(_fit(train, method, seed)(test), 0, 100)


def cross_validate(df, method, seed):
    """Out-of-fold prediction for every slide, each from a fit that never saw that slide's hospital."""
    pred = np.empty(len(df))
    for tr, va in hospital_folds(df["hospital"].to_numpy()):
        pred[va] = fit_predict(df.iloc[tr], df.iloc[va], method, seed)
    return pred

"""Independent re-derivation of headline metrics from a predictions CSV.

Usage:
    python scripts/independent_check.py <predictions_csv> <results_json>

Written without reading or importing anything under backend/. Recomputes MAE,
Pearson r, catch rate and paired-bootstrap MAE differences from the per-slide
predictions, and compares them with the numbers reported in the results JSON.
Prints aggregate numbers only (no slide ids, no rows). Exit 0 if all checks
pass, 1 otherwise.
"""

import json
import math
import sys

import numpy as np
import pandas as pd

EXPECTED_COLUMNS = [
    "slide_id", "hospital", "truth_pct", "pathologist", "app_raw",
    "app_calibrated", "dummy", "app_ridge_embedding",
]
METRIC_TOL = 1e-6
CI_TOL = 1.0
SEED = 20261017


def mae(pred, truth):
    return float(np.mean(np.abs(pred - truth)))


def pearson(pred, truth):
    p = pred - pred.mean()
    t = truth - truth.mean()
    denom = math.sqrt(float(np.sum(p * p)) * float(np.sum(t * t)))
    if denom == 0.0:
        return float("nan")
    return float(np.sum(p * t) / denom)


def catch_rate(pred, truth, cutoff):
    below = truth < cutoff
    if not below.any():
        return float("nan")
    return float(np.mean(pred[below] < cutoff))


def paired_bootstrap(a, b, truth, n, rng):
    """MAE(a) - MAE(b): full-sample diff and 2.5/97.5 percentiles over n resamples."""
    err_a = np.abs(a - truth)
    err_b = np.abs(b - truth)
    diff = float(err_a.mean() - err_b.mean())
    k = len(truth)
    vals = np.empty(n)
    for i in range(n):
        idx = rng.integers(0, k, size=k)
        vals[i] = err_a[idx].mean() - err_b[idx].mean()
    lo, hi = np.percentile(vals, [2.5, 97.5])
    return diff, float(lo), float(hi)


def close(x, y, tol):
    if x is None or y is None:
        return False
    x = float(x)
    y = float(y)
    if math.isnan(x) and math.isnan(y):
        return True
    if math.isnan(x) or math.isnan(y):
        return False
    return abs(x - y) <= tol


def fmt(x):
    if x is None:
        return "missing"
    x = float(x)
    if math.isnan(x):
        return "nan"
    return "{:.6f}".format(x)


def main(argv):
    if len(argv) != 3:
        print(__doc__)
        return 2
    df = pd.read_csv(argv[1])
    with open(argv[2], "r", encoding="utf-8") as fh:
        res = json.load(fh)  # json accepts NaN by default

    all_ok = True

    missing = [c for c in EXPECTED_COLUMNS if c not in df.columns]
    if missing:
        print("FAIL: CSV missing columns: " + ", ".join(missing))
        return 1

    n_ok = len(df) == int(res["n_slides"])
    all_ok &= n_ok
    print("Row count: csv={} reported n_slides={} -> {}".format(
        len(df), res["n_slides"], "PASS" if n_ok else "FAIL"))

    cutoff = float(res.get("catch_cutoff", 60))
    truth = df["truth_pct"].to_numpy(dtype=float)
    if not np.all(np.isfinite(truth)):
        print("FAIL: non-finite truth_pct values")
        all_ok = False
    n_below = int(np.sum(truth < cutoff))
    print("Catch cutoff: {} ; slides with truth < cutoff: {}".format(cutoff, n_below))
    print()

    header = "{:<22}{:<8}{:>14}{:>14}{:>8}".format("method", "metric", "recomputed", "reported", "result")
    print("== Per-method metrics (tol {}) ==".format(METRIC_TOL))
    print(header)
    print("-" * len(header))
    for m, rep in res["methods"].items():
        if m not in df.columns:
            print("{:<22}column missing from CSV -> FAIL".format(m))
            all_ok = False
            continue
        pred = df[m].to_numpy(dtype=float)
        mine = {
            "mae": mae(pred, truth),
            "pearson_r": pearson(pred, truth),
            "catch_rate": catch_rate(pred, truth, cutoff),
        }
        for key in ("mae", "pearson_r", "catch_rate"):
            ok = close(mine[key], rep.get(key), METRIC_TOL)
            all_ok &= ok
            print("{:<22}{:<8}{:>14}{:>14}{:>8}".format(
                m, key.replace("pearson_r", "r").replace("catch_rate", "catch"),
                fmt(mine[key]), fmt(rep.get(key)), "PASS" if ok else "FAIL"))
    print()

    rng = np.random.default_rng(SEED)
    sections = [
        ("bootstrap", "pathologist"),
        ("bootstrap_vs_dummy", "dummy"),
    ]
    for section, ref in sections:
        entries = res.get(section, {})
        print("== {}: MAE({}) - MAE(method) (diff tol {}, CI tol {}) ==".format(
            section, ref, METRIC_TOL, CI_TOL))
        print(header)
        print("-" * len(header))
        for m, rep in entries.items():
            if m not in df.columns:
                print("{:<22}column missing from CSV -> FAIL".format(m))
                all_ok = False
                continue
            n = int(rep["n"])
            d, lo, hi = paired_bootstrap(
                df[ref].to_numpy(dtype=float), df[m].to_numpy(dtype=float), truth, n, rng)
            for key, val, tol in (("diff", d, METRIC_TOL), ("ci_low", lo, CI_TOL), ("ci_high", hi, CI_TOL)):
                ok = close(val, rep.get(key), tol)
                all_ok &= ok
                print("{:<22}{:<8}{:>14}{:>14}{:>8}".format(
                    m, key, fmt(val), fmt(rep.get(key)), "PASS" if ok else "FAIL"))
            print("{:<22}(n resamples = {})".format("", n))
        print()

    print("OVERALL: {}".format("PASS" if all_ok else "FAIL"))
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))

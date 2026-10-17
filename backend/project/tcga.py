"""Phase 8: does the app's tumor estimate track ABSOLUTE purity better than the pathologist's?

    python -m project.tcga labels               # login node: GDC + ABSOLUTE → <tcga_dir>/labels.csv
    python -m project.tcga download --yes       # login node: selected slides → <tcga_dir>/slides/ (asks without --yes)
    python -m project.tcga score --split train  # GPU job only: CONCH on each downloaded slide → app_scores.csv
    python -m project.tcga check --split train  # CPU: app vs. pathologist on train only, before test is scored
    python -m project.tcga evaluate             # CPU: results/tcga_validation.json

labels.csv, slides and per-slide scores are patient-level and stay under tcga_dir (or $TCGA_DIR) (gitignored, AGENTS.md §3, §6).
Only aggregate numbers go to results/.
"""

import argparse
import json
import os
import sys
import time

import numpy as np
import pandas as pd

from project import gdc
from project.config import load_config, repo_path
from project.ingest import open_slide
from project.labels import assign_splits, build_labels, check_labels, read_absolute, select_slides
from project.metrics import bootstrap_mae_diff, catch_rate, mae, pearson_r, verdict
from project.model import load_backend
from project.tiling import build_grid, read_tiles


# --- scoring --------------------------------------------------------------------------------------

def score_slide(path, cfg, backend):
    """The app's whole-slide composition: mean class probability over the analyzed tiles, in percent."""
    slide = open_slide(path, None, cfg["default_mpp"])
    try:
        grid = build_grid(slide, cfg)
        parts = []
        for i in range(0, len(grid.tiles), cfg["batch_size"]):
            parts.append(backend.predict(read_tiles(slide, grid.tiles[i:i + cfg["batch_size"]], cfg["tile_px"])))
        mean = np.concatenate(parts).mean(axis=0) * 100
    finally:
        close = getattr(getattr(slide, "osr", None), "close", None)
        if close:
            close()
    out = {f"app_{c}_pct": float(v) for c, v in zip(cfg["classes"], mean)}
    out.update(n_tiles=len(grid.tiles), n_tissue_tiles=grid.n_tissue_tiles, capped=grid.capped,
               mpp=slide.mpp, mpp_estimated=slide.mpp_estimated, model=backend.name)
    return out


# --- evaluation -----------------------------------------------------------------------------------

def fit_mapping(app, truth):
    """Least-squares line truth ≈ slope × app + intercept."""
    slope, intercept = np.polyfit(np.asarray(app, float), np.asarray(truth, float), 1)
    return float(slope), float(intercept)


def apply_mapping(app, slope, intercept):
    return np.clip(slope * np.asarray(app, float) + intercept, 0, 100)


def method_metrics(truth, pred, cutoff):
    return {"mae": mae(truth, pred), "pearson_r": pearson_r(truth, pred), "catch_rate": catch_rate(truth, pred, cutoff)}


def evaluate(labels, scores, tcga_cfg, seed):
    """App (raw and mapped) vs. pathologist vs. ABSOLUTE, on exactly the same test slides (AGENTS.md §9)."""
    split_hospitals = labels.groupby("split")["hospital"].apply(set)
    shared = split_hospitals.get("train", set()) & split_hospitals.get("test", set())
    if shared:
        raise ValueError(f"hospital in both train and test: {', '.join(sorted(shared))}")

    df = labels.merge(scores[["slide_id", "app_tumor_pct"]], on="slide_id", how="left")
    train = df[(df["split"] == "train") & df["app_tumor_pct"].notna()]
    test_all = df[df["split"] == "test"]
    test = test_all[test_all["app_tumor_pct"].notna()]
    if len(train) < 2:
        raise ValueError(f"need ≥ 2 scored train slides to fit the mapping, have {len(train)}")
    if test.empty:
        raise ValueError("no scored test slides")

    slope, intercept = fit_mapping(train["app_tumor_pct"], train["truth_pct"])
    cutoff, n_boot = tcga_cfg["catch_cutoff"], tcga_cfg["n_bootstrap"]
    truth = test["truth_pct"].to_numpy()
    preds = {
        "pathologist": test["pathologist_pct"].to_numpy(),
        "app_raw": test["app_tumor_pct"].to_numpy(),
        "app_calibrated": apply_mapping(test["app_tumor_pct"], slope, intercept),
    }
    out = {
        "question": "Does the app's whole-slide tumor % track ABSOLUTE purity better than the pathologist's %?",
        "split": "test",
        "n_slides": int(len(test)),
        "n_hospitals": int(test["hospital"].nunique()),
        "n_below_cutoff": int((truth < cutoff).sum()),
        "n_test_slides_without_app_score": int(len(test_all) - len(test)),
        "catch_cutoff": cutoff,
        "mapping": {"slope": slope, "intercept": intercept, "fit_on": "train", "n_slides": int(len(train))},
        "methods": {m: method_metrics(truth, p, cutoff) for m, p in preds.items()},
        "bootstrap": {},
        "seed": seed,
    }
    for m in ("app_raw", "app_calibrated"):
        b = bootstrap_mae_diff(truth, preds["pathologist"], preds[m], n=n_boot, seed=seed)
        b["verdict"] = verdict(b["ci_low"], b["ci_high"])
        b["meaning"] = "pathologist MAE − app MAE in points (> 0: app closer to ABSOLUTE); 95% percentile interval"
        out["bootstrap"][m] = b
    return out


def split_check(labels, scores, split, cutoff):
    """Aggregate app vs. pathologist numbers on one non-test split, to judge the method before touching test.

    Never the test split: anything tuned after looking at test results would inflate the final claim.
    """
    if split == "test":
        raise ValueError("check never looks at the test split; use `evaluate` once the method is fixed")
    df = labels[labels["split"] == split].merge(scores[["slide_id", "app_tumor_pct"]], on="slide_id")
    df = df[df["app_tumor_pct"].notna()]
    if len(df) < 3:
        raise ValueError(f"only {len(df)} scored {split} slides; score more first")
    truth = df["truth_pct"].to_numpy()
    out = {"split": split, "n_slides": int(len(df)), "n_hospitals": int(df["hospital"].nunique()),
           "n_below_cutoff": int((truth < cutoff).sum())}
    for name, col in (("pathologist", "pathologist_pct"), ("app_raw", "app_tumor_pct")):
        pred = df[col].to_numpy()
        out[name] = {"pearson_r": pearson_r(truth, pred), "mae": mae(truth, pred),
                     "min": float(pred.min()), "median": float(np.median(pred)), "max": float(pred.max())}
    out["truth"] = {"min": float(truth.min()), "median": float(np.median(truth)), "max": float(truth.max())}
    return out


def slides_to_score(labels, done, splits, exists):
    """Selected slides of the given splits that are downloaded and not yet scored, in labels.csv order."""
    picked = labels[labels["selected"] & labels["split"].isin(splits)]
    return [s for s in picked["slide_id"] if s not in done and exists(s)]


# --- command line ---------------------------------------------------------------------------------

def tcga_dir(cfg):
    """TCGA_DIR wins, so Delta jobs can point at /work/nvme/bfqi/$USER/tcga without editing config.yaml."""
    return repo_path(os.environ.get("TCGA_DIR") or cfg["paths"]["tcga_dir"])


def slide_path(cfg, slide_id):
    return tcga_dir(cfg) / "slides" / f"{slide_id}.svs"


def cmd_labels(cfg, args):
    t = cfg["tcga"]
    out_dir = tcga_dir(cfg)
    out_dir.mkdir(parents=True, exist_ok=True)
    gdc.download(t["absolute_url"], out_dir / "absolute.txt")
    slides = gdc.slides_from_hits(gdc.fetch_slide_hits(t["project"]), t["slide_kinds"])
    labels, flags = build_labels(slides, read_absolute(out_dir / "absolute.txt"))
    labels = select_slides(assign_splits(labels, t["split_fractions"], cfg["seed"]), t["max_slides"], cfg["seed"])
    check_labels(labels, t)
    labels.to_csv(out_dir / "labels.csv", index=False)

    summary = {"project": t["project"], "slide_kinds": t["slide_kinds"], "n_slides": len(labels), **flags}
    for s, g in labels.groupby("split"):
        sel = g[g["selected"]]
        summary[s] = {"slides": len(g), "hospitals": int(g["hospital"].nunique()),
                      "below_cutoff": int((g["truth_pct"] < t["catch_cutoff"]).sum()),
                      "selected": len(sel), "selected_gb": round(sel["file_size"].sum() / 1e9, 1)}
    (repo_path(cfg["paths"]["results"]) / "tcga_labels_summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))
    if flags["multi_slide_samples_with_different_pct"]:
        print(f"Note: {flags['multi_slide_samples_with_different_pct']} samples have several slides with different "
              "pathologist percentages. They stay separate rows (AGENTS.md section 4).")


def cmd_download(cfg, args):
    labels = pd.read_csv(tcga_dir(cfg) / "labels.csv")
    todo = labels[labels["selected"] & labels["split"].isin(args.split)]
    todo = todo[[not slide_path(cfg, s).exists() for s in todo["slide_id"]]]
    gb = todo["file_size"].sum() / 1e9
    print(f"{len(todo)} slides to download ({', '.join(args.split)}), {gb:.1f} GB, to {tcga_dir(cfg) / 'slides'}")
    if not args.yes:
        print("Nothing downloaded. Re-run with --yes once a human has approved this size (CLAUDE.md).")
        return
    for i, row in enumerate(todo.itertuples(), 1):
        gdc.download(gdc.file_url(row.file_id), slide_path(cfg, row.slide_id), row.file_size)
        print(f"[{i}/{len(todo)}] {row.file_size / 1e6:.0f} MB", flush=True)


def cmd_score(cfg, args):
    cfg = {**cfg, "model": args.model}
    backend = load_backend(cfg)
    labels = pd.read_csv(tcga_dir(cfg) / "labels.csv")
    out_path = tcga_dir(cfg) / "app_scores.csv"
    done = set(pd.read_csv(out_path)["slide_id"]) if out_path.exists() else set()
    todo = slides_to_score(labels, done, args.split, lambda s: slide_path(cfg, s).exists())
    if args.limit:
        todo = todo[:args.limit]
    print(f"Scoring {len(todo)} {'/'.join(args.split)} slides with {backend.name} "
          f"({len(done)} already scored)", flush=True)
    for i, slide_id in enumerate(todo, 1):
        start = time.monotonic()
        try:
            row = {"slide_id": slide_id, **score_slide(slide_path(cfg, slide_id), cfg, backend), "error": ""}
        except Exception as e:  # one bad slide shouldn't stop the job; it's left out of the evaluation
            row = {"slide_id": slide_id, "error": f"{type(e).__name__}: {e}"}
        pd.DataFrame([row]).to_csv(out_path, mode="a", header=not out_path.exists(), index=False)
        print(f"[{i}/{len(todo)}] {time.monotonic() - start:.0f} s {'error' if row['error'] else 'ok'}", flush=True)


def cmd_evaluate(cfg, args):
    labels = pd.read_csv(tcga_dir(cfg) / "labels.csv")
    scores = pd.read_csv(tcga_dir(cfg) / "app_scores.csv")
    scores = scores[scores["app_tumor_pct"].notna()]
    models = sorted(scores["model"].dropna().unique())
    if models != ["conch"] and not args.allow_fake:
        sys.exit(f"app_scores.csv has model(s) {models}; the validation must use CONCH.")
    result = evaluate(labels, scores, cfg["tcga"], seed=cfg["seed"])
    result.update(project=cfg["tcga"]["project"], slide_kinds=cfg["tcga"]["slide_kinds"], model=models,
                  prompt_set=cfg["prompt_set"])
    out = repo_path(cfg["paths"]["results"]) / "tcga_validation.json"
    out.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


def cmd_check(cfg, args):
    labels = pd.read_csv(tcga_dir(cfg) / "labels.csv")
    scores = pd.read_csv(tcga_dir(cfg) / "app_scores.csv")
    out = split_check(labels, scores, args.split, cfg["tcga"]["catch_cutoff"])
    out.update(prompt_set=cfg["prompt_set"], model=sorted(scores["model"].dropna().unique()))
    path = repo_path(cfg["paths"]["results"]) / f"tcga_check_{args.split}_{cfg['prompt_set']}.json"
    path.write_text(json.dumps(out, indent=2) + "\n")
    print(json.dumps(out, indent=2))


def main(argv=None):
    p = argparse.ArgumentParser(prog="python -m project.tcga", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("labels")
    d = sub.add_parser("download")
    d.add_argument("--split", nargs="+", default=["test", "train"], choices=["train", "cal", "test"])
    d.add_argument("--yes", action="store_true", help="actually download (after a human approved the size)")
    s = sub.add_parser("score")
    s.add_argument("--model", default="conch", choices=["conch", "fake"])
    s.add_argument("--split", nargs="+", default=["train", "test"], choices=["train", "cal", "test"])
    s.add_argument("--limit", type=int, default=0, help="score at most this many slides (0 = all)")
    c = sub.add_parser("check")
    c.add_argument("--split", default="train", choices=["train", "cal"])
    e = sub.add_parser("evaluate")
    e.add_argument("--allow-fake", action="store_true", help="for pipeline checks only; never report these numbers")
    args = p.parse_args(argv)
    cfg = load_config()
    {"labels": cmd_labels, "download": cmd_download, "score": cmd_score, "check": cmd_check,
     "evaluate": cmd_evaluate}[args.cmd](cfg, args)


if __name__ == "__main__":
    main()

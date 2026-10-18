"""Phase 8: does the app's tumor estimate track ABSOLUTE purity better than the pathologist's?

    python -m project.tcga labels               # login node: GDC + ABSOLUTE → <tcga_dir>/labels.csv
    python -m project.tcga download --yes       # login node: selected slides → <tcga_dir>/slides/ (asks without --yes)
    python -m project.tcga score --split train  # GPU job: CONCH tile embeddings (saved) → app_scores_<prompts>.csv
    python -m project.tcga score --embeddings-only  # CPU job: re-score saved embeddings after a prompt change
    python -m project.tcga check --split train  # CPU: app vs. pathologist on train only, before test is scored
    python -m project.tcga features             # CPU job: slide-level features from the saved embeddings
    python -m project.tcga explore --split train  # leave-one-hospital-out comparison of methods, train only
    python -m project.tcga evaluate --method M  # CPU: results/tcga_validation_<prompts>.json, once, on test

labels.csv, slides and per-slide scores are patient-level and stay under tcga_dir (or $TCGA_DIR) (gitignored, AGENTS.md §3, §6).
Only aggregate numbers go to results/.
"""

import argparse
import hashlib
import json
import os
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

from project import gdc
from project.config import load_config, repo_path
from project.ingest import open_slide
from project.labels import assign_splits, build_labels, check_labels, read_absolute, select_slides
from project.metrics import bootstrap_mae_diff, catch_rate, mae, pearson_r, verdict
from project.model import load_backend
from project.purity_models import METHODS, cross_validate, fit_predict, slide_features
from project.tiling import build_grid, read_tiles


# --- scoring --------------------------------------------------------------------------------------

def _summary(probs, cfg, organ, model, n_tissue_tiles, capped, mpp, mpp_estimated):
    mean = probs.mean(axis=0) * 100
    out = {f"app_{c}_pct": float(v) for c, v in zip(cfg["classes"], mean)}
    out.update(n_tiles=int(len(probs)), n_tissue_tiles=int(n_tissue_tiles), capped=bool(capped), mpp=mpp,
               mpp_estimated=bool(mpp_estimated), model=str(model), organ=organ or cfg["default_organ"],
               prompt_set=cfg["prompt_set"])
    return out


def score_slide(path, cfg, backend, organ=None, emb_path=None):
    """The app's whole-slide composition: mean class probability over the analyzed tiles, in percent.

    With emb_path, the tile embeddings are saved too (AGENTS.md §4: feats [N, D] float32, coords [N, 2] int64
    as (x, y), model), so other prompt sets can be scored later without reading the slide again.
    """
    slide = open_slide(path, None, cfg["default_mpp"])
    try:
        grid = build_grid(slide, cfg)
        parts = []
        for i in range(0, len(grid.tiles), cfg["batch_size"]):
            parts.append(backend.embed(read_tiles(slide, grid.tiles[i:i + cfg["batch_size"]], cfg["tile_px"])))
        feats = np.concatenate(parts).astype(np.float32)
    finally:
        close = getattr(getattr(slide, "osr", None), "close", None)
        if close:
            close()
    meta = dict(n_tissue_tiles=grid.n_tissue_tiles, capped=grid.capped, mpp=slide.mpp,
                mpp_estimated=slide.mpp_estimated)
    if emb_path is not None:
        emb_path = Path(emb_path)
        emb_path.parent.mkdir(parents=True, exist_ok=True)
        coords = np.array([[t.x, t.y] for t in grid.tiles], np.int64).reshape(-1, 2)
        np.savez(emb_path, feats=feats, coords=coords, model=backend.name,
                 **{k: np.nan if v is None else v for k, v in meta.items()})
    return _summary(backend.classify(feats, organ), cfg, organ, backend.name, **meta)


def score_from_embeddings(emb_path, cfg, backend, organ=None):
    """Re-score a slide from its saved embeddings with the current prompts: no slide reading, no GPU needed."""
    z = np.load(emb_path)
    if str(z["model"]) != backend.name:
        raise ValueError(f"{emb_path} holds {z['model']} embeddings, not {backend.name}")
    mpp = float(z["mpp"])
    return _summary(backend.classify(z["feats"], organ), cfg, organ, str(z["model"]), int(z["n_tissue_tiles"]),
                    bool(z["capped"]), None if np.isnan(mpp) else mpp, bool(z["mpp_estimated"]))


# --- evaluation -----------------------------------------------------------------------------------

def fit_mapping(app, truth):
    """Least-squares line truth ≈ slope × app + intercept."""
    slope, intercept = np.polyfit(np.asarray(app, float), np.asarray(truth, float), 1)
    return float(slope), float(intercept)


def apply_mapping(app, slope, intercept):
    return np.clip(slope * np.asarray(app, float) + intercept, 0, 100)


def method_metrics(truth, pred, cutoff):
    return {"mae": mae(truth, pred), "pearson_r": pearson_r(truth, pred), "catch_rate": catch_rate(truth, pred, cutoff)}


def evaluate(labels, scores, tcga_cfg, seed, features=None, method=None):
    """App (raw and mapped) vs. pathologist vs. ABSOLUTE, on exactly the same test slides (AGENTS.md §9).

    With `features` and a `method` (chosen beforehand with `explore` on train), that method is fit on the train
    hospitals and reported too. A dummy (train median) is always reported as the bar to beat.
    """
    split_hospitals = labels.groupby("split")["hospital"].apply(set)
    shared = split_hospitals.get("train", set()) & split_hospitals.get("test", set())
    if shared:
        raise ValueError(f"hospital in both train and test: {', '.join(sorted(shared))}")

    df = labels.merge(scores[["slide_id", "app_tumor_pct"]], on="slide_id", how="left")
    if method is not None:  # only slides with features, so every method is compared on the same slides
        df = df.merge(features, on="slide_id", how="inner", suffixes=("", "_feat"))
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
        "dummy": np.full(len(test), float(np.median(train["truth_pct"]))),
    }
    if method is not None:
        preds[f"app_{method}"] = fit_predict(train, test, method, seed)
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
    if method is not None:
        out["chosen_method"] = method
        rounded = np.round(preds[f"app_{method}"], 6).tobytes()
        out["predictions_fingerprint"] = hashlib.sha256(rounded).hexdigest()[:16]
    for m in [k for k in preds if k != "pathologist"]:
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


def explore(labels, features, split, cutoff, seed):
    """Every purity method on one non-test split, by leave-one-hospital-out CV: pick a method before test.

    Each slide is predicted by a fit that never saw its hospital. A shuffled-label run of the ridge model shows
    what "no real signal" looks like. Never the test split.
    """
    if split == "test":
        raise ValueError("explore never looks at the test split; pick a method on train, then run `evaluate`")
    df = labels[labels["split"] == split].merge(features, on="slide_id", how="inner", suffixes=("", "_feat"))
    df = df.reset_index(drop=True)
    if df["hospital"].nunique() < 3:
        raise ValueError(f"need ≥ 3 {split} hospitals with features, have {df['hospital'].nunique()}")
    truth = df["truth_pct"].to_numpy(float)

    def metrics(pred):
        out = {"mae": mae(truth, pred), "pearson_r": pearson_r(truth, pred)}
        if (truth < cutoff).any():
            out["catch_rate"] = catch_rate(truth, pred, cutoff)
        return out

    out = {"split": split, "n_slides": int(len(df)), "n_hospitals": int(df["hospital"].nunique()),
           "n_below_cutoff": int((truth < cutoff).sum()), "cv": "leave-one-hospital-out", "seed": seed,
           "methods": {m: metrics(cross_validate(df, m, seed)) for m in METHODS}}
    out["methods"]["pathologist"] = metrics(df["pathologist_pct"].to_numpy(float))
    shuffled = df.assign(truth_pct=np.random.default_rng(seed).permutation(truth))
    shuffled_mae = lambda m: mae(shuffled["truth_pct"], cross_validate(shuffled, m, seed))
    out["shuffled_labels"] = {"ridge_embedding_mae": shuffled_mae("ridge_embedding"),
                              "dummy_mae": shuffled_mae("dummy")}
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


def emb_path(cfg, slide_id):
    return tcga_dir(cfg) / "embeddings" / f"{slide_id}.npz"


def features_path(cfg):
    return tcga_dir(cfg) / f"features_{cfg['prompt_set']}.csv"


def scores_path(cfg):
    """One scores file per prompt set, so results from different prompts never mix."""
    return tcga_dir(cfg) / f"app_scores_{cfg['prompt_set']}.csv"


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
    organ = cfg["tcga"]["organ"]
    labels = pd.read_csv(tcga_dir(cfg) / "labels.csv")
    out_path = scores_path(cfg)
    done = set(pd.read_csv(out_path)["slide_id"]) if out_path.exists() else set()

    def available(s):
        return emb_path(cfg, s).exists() or (not args.embeddings_only and slide_path(cfg, s).exists())

    todo = slides_to_score(labels, done, args.split, available)
    if args.limit:
        todo = todo[:args.limit]
    print(f"Scoring {len(todo)} {'/'.join(args.split)} slides with {backend.name}, organ {organ}, "
          f"prompts {cfg['prompt_set']} ({len(done)} already scored)", flush=True)
    for i, slide_id in enumerate(todo, 1):
        start = time.monotonic()
        saved = emb_path(cfg, slide_id)
        try:
            if saved.exists():  # embedded before: re-score with the current prompts, no slide reading
                scored = score_from_embeddings(saved, cfg, backend, organ)
            else:
                scored = score_slide(slide_path(cfg, slide_id), cfg, backend, organ, emb_path=saved)
            row = {"slide_id": slide_id, **scored, "error": ""}
        except Exception as e:  # one bad slide shouldn't stop the job; it's left out of the evaluation
            row = {"slide_id": slide_id, "error": f"{type(e).__name__}: {e}"}
        pd.DataFrame([row]).to_csv(out_path, mode="a", header=not out_path.exists(), index=False)
        print(f"[{i}/{len(todo)}] {time.monotonic() - start:.0f} s {'error' if row['error'] else 'ok'}", flush=True)


def cmd_features(cfg, args):
    """Slide-level features from saved embeddings (class probabilities with the current prompts, tile shares,
    mean embedding). CPU job: it loads CONCH's text encoder."""
    cfg = {**cfg, "model": args.model}
    backend = load_backend(cfg)
    organ = cfg["tcga"]["organ"]
    labels = pd.read_csv(tcga_dir(cfg) / "labels.csv")
    rows = []
    for slide_id in labels.loc[labels["selected"], "slide_id"]:
        saved = emb_path(cfg, slide_id)
        if saved.exists():
            z = np.load(saved)
            probs = backend.classify(z["feats"], organ)
            rows.append({"slide_id": slide_id, **slide_features(probs, z["feats"], cfg["classes"])})
    pd.DataFrame(rows).to_csv(features_path(cfg), index=False)
    print(f"{len(rows)} slides -> {features_path(cfg)} (organ {organ}, prompts {cfg['prompt_set']})")


def cmd_explore(cfg, args):
    labels = pd.read_csv(tcga_dir(cfg) / "labels.csv")
    features = pd.read_csv(features_path(cfg))
    out = explore(labels, features, args.split, cfg["tcga"]["catch_cutoff"], cfg["seed"])
    out.update(organ=cfg["tcga"]["organ"], prompt_set=cfg["prompt_set"])
    path = repo_path(cfg["paths"]["results"]) / f"tcga_explore_{args.split}_{cfg['prompt_set']}.json"
    path.write_text(json.dumps(out, indent=2) + "\n")
    print(json.dumps(out, indent=2))
    best = min(METHODS, key=lambda m: out["methods"][m]["mae"])
    print(f"Lowest cross-validated MAE on {args.split}: {best}. Compare it with dummy before choosing.")


def cmd_evaluate(cfg, args):
    labels = pd.read_csv(tcga_dir(cfg) / "labels.csv")
    scores = pd.read_csv(scores_path(cfg))
    scores = scores[scores["app_tumor_pct"].notna()]
    models = sorted(scores["model"].dropna().unique())
    if models != ["conch"] and not args.allow_fake:
        sys.exit(f"{scores_path(cfg).name} has model(s) {models}; the validation must use CONCH.")
    features = pd.read_csv(features_path(cfg)) if args.method else None
    result = evaluate(labels, scores, cfg["tcga"], seed=cfg["seed"], features=features, method=args.method)
    result.update(project=cfg["tcga"]["project"], slide_kinds=cfg["tcga"]["slide_kinds"], model=models,
                  organ=cfg["tcga"]["organ"], prompt_set=cfg["prompt_set"])
    out = repo_path(cfg["paths"]["results"]) / f"tcga_validation_{cfg['prompt_set']}.json"
    out.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


def cmd_check(cfg, args):
    labels = pd.read_csv(tcga_dir(cfg) / "labels.csv")
    scores = pd.read_csv(scores_path(cfg))
    out = split_check(labels, scores, args.split, cfg["tcga"]["catch_cutoff"])
    out.update(organ=cfg["tcga"]["organ"], prompt_set=cfg["prompt_set"], model=sorted(scores["model"].dropna().unique()))
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
    s.add_argument("--embeddings-only", action="store_true",
                   help="only slides with saved embeddings: re-score new prompts without reading slides (CPU is fine)")
    c = sub.add_parser("check")
    c.add_argument("--split", default="train", choices=["train", "cal"])
    f = sub.add_parser("features")
    f.add_argument("--model", default="conch", choices=["conch", "fake"])
    x = sub.add_parser("explore")
    x.add_argument("--split", default="train", choices=["train", "cal"])
    e = sub.add_parser("evaluate")
    e.add_argument("--method", choices=METHODS, help="also report this method (chosen with `explore` on train)")
    e.add_argument("--allow-fake", action="store_true", help="for pipeline checks only; never report these numbers")
    args = p.parse_args(argv)
    cfg = load_config()
    {"labels": cmd_labels, "download": cmd_download, "score": cmd_score, "check": cmd_check,
     "features": cmd_features, "explore": cmd_explore,
     "evaluate": cmd_evaluate}[args.cmd](cfg, args)


if __name__ == "__main__":
    main()

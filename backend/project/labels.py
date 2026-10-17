"""labels.csv for the TCGA validation (AGENTS.md §4, §8 Phase 1): pathologist % and ABSOLUTE purity per slide."""

import re

import numpy as np
import pandas as pd

SAMPLE_RE = re.compile(r"^TCGA-[A-Z0-9]{2}-[A-Z0-9]{4}-\d{2}[A-Z]$")
COLUMNS = ["slide_id", "sample_id", "patient_id", "hospital", "pathologist_pct", "truth_pct", "file_id", "file_size"]
SPLITS = ("train", "cal", "test")


class LabelsError(ValueError):
    pass


def parse_barcode(barcode):
    """Sample (16 chars), patient (12) and hospital = tissue source site (chars 6–7) from a TCGA barcode."""
    return {"sample_id": barcode[:16], "patient_id": barcode[:12], "hospital": barcode[5:7]}


def read_absolute(path):
    """ABSOLUTE calls as sample_id → truth_pct. The only place purity goes from a fraction to percent."""
    df = pd.read_csv(path, sep="\t")
    df = df[df["call status"].eq("called") & df["purity"].notna()].copy()
    df["sample_id"] = df["sample"].astype(str).str[:16]
    df = df[df["sample_id"].map(lambda s: bool(SAMPLE_RE.match(s)))]
    df = df[~df["sample_id"].duplicated(keep=False)]  # two calls for one sample: ambiguous, so neither is used
    df["truth_pct"] = df["purity"] * 100
    return df[["sample_id", "truth_pct"]].reset_index(drop=True)


def build_labels(slides, absolute):
    """Join slides (one pathologist % each) to ABSOLUTE on the 16-char sample_id.

    Several slides of one sample stay separate rows; the count with differing percentages is flagged.
    """
    parsed = pd.DataFrame([parse_barcode(b) for b in slides["slide_barcode"]], index=slides.index)
    df = pd.concat([slides, parsed], axis=1).merge(absolute, on="sample_id", how="inner")
    df["pathologist_pct"] = df["pathologist_pct"].astype(float)
    per_sample = df.groupby("sample_id")["pathologist_pct"].nunique()
    flags = {"multi_slide_samples_with_different_pct": int((per_sample > 1).sum())}
    return df[COLUMNS].sort_values("slide_id").reset_index(drop=True), flags


def assign_splits(labels, fractions, seed):
    """Whole hospitals go to one split. Hospitals are shuffled (seeded) and fill test, then cal, then train."""
    hospitals = sorted(labels["hospital"].unique())
    np.random.default_rng(seed).shuffle(hospitals)
    sizes = labels["hospital"].value_counts()
    n = len(labels)
    filled = {s: 0 for s in SPLITS}
    split_of = {}
    for h in hospitals:
        if filled["test"] < fractions["test"] * n:
            s = "test"
        elif filled["cal"] < fractions["cal"] * n:
            s = "cal"
        else:
            s = "train"
        split_of[h] = s
        filled[s] += sizes[h]
    return labels.assign(split=labels["hospital"].map(split_of))


def select_slides(labels, max_slides, seed):
    """Mark a seeded sample of at most max_slides[split] slides per split to download and score."""
    rng = np.random.default_rng(seed)
    selected = pd.Series(False, index=labels.index)
    for s in SPLITS:
        idx = labels.index[labels["split"] == s].to_numpy().copy()
        rng.shuffle(idx)
        selected[idx[:max_slides.get(s, 0)]] = True
    return labels.assign(selected=selected)


def check_labels(labels, tcga_cfg):
    """Every AGENTS.md §8 Phase 1 rule. Raises LabelsError listing each problem."""
    problems = []
    required = ["slide_id", "sample_id", "patient_id", "hospital", "pathologist_pct", "truth_pct", "split"]
    missing_cols = [c for c in required if c not in labels.columns]
    if missing_cols:
        raise LabelsError(f"labels are missing columns: {', '.join(missing_cols)}")
    n_missing = int(labels[required].isna().any(axis=1).sum())
    if n_missing:
        problems.append(f"{n_missing} rows have missing values in required columns")
    if labels["slide_id"].duplicated().any():
        problems.append("slide_id is not unique")
    bad_ids = ~labels["sample_id"].astype(str).map(lambda s: bool(SAMPLE_RE.match(s)))
    if bad_ids.any():
        problems.append(f"{int(bad_ids.sum())} sample_id values don't match {SAMPLE_RE.pattern}")
    if not (labels["patient_id"] == labels["sample_id"].str[:12]).all():
        problems.append("patient_id is not the first 12 chars of sample_id")
    if not (labels["hospital"] == labels["sample_id"].str[5:7]).all():
        problems.append("hospital is not chars 6–7 of the barcode")
    for col in ("pathologist_pct", "truth_pct"):
        out = ~labels[col].dropna().between(0, 100)
        if out.any():
            problems.append(f"{int(out.sum())} {col} values outside [0, 100]")
    if labels["truth_pct"].median() <= 1:
        problems.append("median truth_pct ≤ 1: ABSOLUTE purity looks like a fraction, not a percent")
    if not labels["split"].isin(SPLITS).all():
        problems.append(f"split must be one of {SPLITS}")
    leaking = labels.groupby("hospital")["split"].nunique()
    if (leaking > 1).any():
        problems.append(f"hospital in more than one split: {', '.join(leaking[leaking > 1].index)}")
    test = labels[labels["split"] == "test"]
    if len(test) < tcga_cfg["min_test_slides"]:
        problems.append(f"test split has {len(test)} slides; needs ≥ {tcga_cfg['min_test_slides']}")
    low = int((test["truth_pct"] < tcga_cfg["catch_cutoff"]).sum())
    if low < tcga_cfg["min_test_below_cutoff"]:
        problems.append(f"test has {low} slides with truth below {tcga_cfg['catch_cutoff']}%; "
                        f"needs ≥ {tcga_cfg['min_test_below_cutoff']}")
    if problems:
        raise LabelsError("; ".join(problems))

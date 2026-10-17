"""Phase 8: labels.csv from GDC slide metadata and ABSOLUTE purity (AGENTS.md §4, §8 Phase 1).

Synthetic barcodes and numbers only: no real TCGA rows in tests (AGENTS.md §6).
"""

import numpy as np
import pandas as pd
import pytest

from project.config import load_config
from project.gdc import slides_from_hits
from project.labels import (
    SAMPLE_RE,
    LabelsError,
    assign_splits,
    build_labels,
    check_labels,
    parse_barcode,
    read_absolute,
    select_slides,
)


@pytest.fixture
def cfg():
    return load_config()


def barcode(site, patient, sample="01A", slide="01-TS1"):
    return f"TCGA-{site}-{patient:04d}-{sample}-{slide}"


def absolute_table(tmp_path, rows):
    """rows: (aliquot barcode, call status, purity fraction). Written like the PanCanAtlas file."""
    df = pd.DataFrame(rows, columns=["sample", "call status", "purity"])
    df.insert(0, "array", df["sample"].str[:15])
    df["ploidy"] = 2.0
    path = tmp_path / "absolute.txt"
    df.to_csv(path, sep="\t", index=False)
    return path


def slide_table(rows):
    """rows: (slide barcode, pathologist %)."""
    return pd.DataFrame(
        [{"slide_id": f"{b}.uuid{i}", "slide_barcode": b, "file_id": f"f{i}", "file_size": 1000 + i,
          "pathologist_pct": p} for i, (b, p) in enumerate(rows)]
    )


# --- barcodes and ABSOLUTE ------------------------------------------------------------------------

def test_parse_barcode():
    out = parse_barcode("TCGA-55-1234-01A-01-TS1")
    assert out == {"sample_id": "TCGA-55-1234-01A", "patient_id": "TCGA-55-1234", "hospital": "55"}
    assert SAMPLE_RE.match(out["sample_id"])


def test_absolute_is_converted_to_percent_once_and_filtered(tmp_path):
    path = absolute_table(tmp_path, [
        ("TCGA-AA-0001-01A-11D-A000-01", "called", 0.52),
        ("TCGA-AA-0002-01A-11D-A000-01", "legacy_call", 0.40),   # not a final call: dropped
        ("TCGA-AA-0003-01A-11D-A000-01", "called", None),        # no purity: dropped
        ("odd-format-sample", "called", 0.70),                   # not a TCGA aliquot barcode: dropped
    ])
    df = read_absolute(path)
    assert list(df.columns) == ["sample_id", "truth_pct"]
    assert df.to_dict("records") == [{"sample_id": "TCGA-AA-0001-01A", "truth_pct": pytest.approx(52.0)}]


def test_ambiguous_absolute_samples_are_dropped(tmp_path):
    path = absolute_table(tmp_path, [
        ("TCGA-AA-0001-01A-11D-A000-01", "called", 0.52),
        ("TCGA-AA-0001-01A-21D-A000-01", "called", 0.61),   # same sample, second aliquot, different call
    ])
    assert read_absolute(path).empty


# --- GDC hits -------------------------------------------------------------------------------------

def gdc_hit(file_id, name, pct, size=123):
    stem = name.split(".")[0]
    return {"file_id": file_id, "file_name": name, "file_size": size,
            "cases": [{"samples": [{"portions": [{"slides": [
                {"submitter_id": stem, "percent_tumor_cells": pct},
                {"submitter_id": stem.replace("TS1", "BS1"), "percent_tumor_cells": 5},
            ]}]}]}]}


def test_slides_from_hits_takes_the_pct_recorded_on_that_slide():
    hits = [
        gdc_hit("a", "TCGA-AA-0001-01A-01-TS1.abc.svs", 70),
        gdc_hit("b", "TCGA-AA-0002-01A-01-DX1.def.svs", 60),   # diagnostic slide: not a kind we want
        gdc_hit("c", "TCGA-AA-0003-01A-01-TS1.ghi.svs", None), # no pathologist %: dropped
    ]
    df = slides_from_hits(hits, kinds=["TS", "BS"])
    assert df.to_dict("records") == [{
        "slide_id": "TCGA-AA-0001-01A-01-TS1.abc", "slide_barcode": "TCGA-AA-0001-01A-01-TS1",
        "file_id": "a", "file_size": 123, "pathologist_pct": 70.0,
    }]


# --- joining --------------------------------------------------------------------------------------

def test_build_labels_joins_on_the_16_char_sample_id(tmp_path):
    absolute = read_absolute(absolute_table(tmp_path, [
        ("TCGA-AA-0001-01A-11D-A000-01", "called", 0.52),
        ("TCGA-BB-0002-01A-11D-A000-01", "called", 0.30),
    ]))
    slides = slide_table([
        (barcode("AA", 1), 70),
        (barcode("BB", 2, slide="01-BS1"), 40),
        (barcode("CC", 3), 50),                      # no ABSOLUTE call: dropped
        (barcode("AA", 1, sample="11A"), 0),         # normal-tissue sample 11A: different sample_id, no call
    ])
    labels, flags = build_labels(slides, absolute)
    assert list(labels.columns[:7]) == [
        "slide_id", "sample_id", "patient_id", "hospital", "pathologist_pct", "truth_pct", "file_id"]
    got = labels.set_index("sample_id")
    assert got.loc["TCGA-AA-0001-01A", "truth_pct"] == pytest.approx(52.0)
    assert got.loc["TCGA-AA-0001-01A", "pathologist_pct"] == 70
    assert got.loc["TCGA-BB-0002-01A", "hospital"] == "BB"
    assert len(labels) == 2
    assert flags["multi_slide_samples_with_different_pct"] == 0


def test_two_slides_of_one_sample_stay_separate_and_are_flagged(tmp_path):
    absolute = read_absolute(absolute_table(tmp_path, [("TCGA-AA-0001-01A-11D-A000-01", "called", 0.5)]))
    slides = slide_table([(barcode("AA", 1, slide="01-TS1"), 70), (barcode("AA", 1, slide="01-BS1"), 40)])
    labels, flags = build_labels(slides, absolute)
    assert len(labels) == 2
    assert sorted(labels["pathologist_pct"]) == [40, 70]
    assert flags["multi_slide_samples_with_different_pct"] == 1


# --- splits ---------------------------------------------------------------------------------------

def synthetic_labels(n_sites=30, per_site=8, seed=0):
    rng = np.random.default_rng(seed)
    rows = []
    for s in range(n_sites):
        site = f"{chr(65 + s // 10)}{s % 10}"
        for p in range(per_site):
            b = barcode(site, s * 100 + p)
            rows.append({"slide_id": b + ".x", "sample_id": b[:16], "patient_id": b[:12], "hospital": site,
                         "pathologist_pct": float(rng.integers(20, 95)),
                         "truth_pct": float(rng.uniform(15, 95)), "file_id": f"f{s}-{p}", "file_size": 10})
    return pd.DataFrame(rows)


def test_no_hospital_in_more_than_one_split(cfg):
    labels = assign_splits(synthetic_labels(), cfg["tcga"]["split_fractions"], seed=cfg["seed"])
    assert set(labels["split"]) == {"train", "cal", "test"}
    assert (labels.groupby("hospital")["split"].nunique() == 1).all()


def test_splits_are_seeded_and_roughly_sized(cfg):
    fr = cfg["tcga"]["split_fractions"]
    a = assign_splits(synthetic_labels(), fr, seed=cfg["seed"])
    b = assign_splits(synthetic_labels(), fr, seed=cfg["seed"])
    pd.testing.assert_series_equal(a["split"], b["split"])
    share = a["split"].value_counts(normalize=True)
    assert abs(share["test"] - fr["test"]) <= 0.1
    assert abs(share["cal"] - fr["cal"]) <= 0.1


def test_select_slides_caps_each_split_and_is_seeded(cfg):
    labels = assign_splits(synthetic_labels(), cfg["tcga"]["split_fractions"], seed=cfg["seed"])
    caps = {"train": 20, "cal": 0, "test": 30}
    a = select_slides(labels, caps, seed=cfg["seed"])
    b = select_slides(labels, caps, seed=cfg["seed"])
    pd.testing.assert_series_equal(a["selected"], b["selected"])
    picked = a[a["selected"]]["split"].value_counts()
    assert picked.get("train", 0) == 20 and picked.get("cal", 0) == 0
    assert picked["test"] == min(30, (labels["split"] == "test").sum())


# --- checks ---------------------------------------------------------------------------------------

def checked(cfg, labels, **override):
    t = {**cfg["tcga"], "min_test_slides": 10, "min_test_below_cutoff": 2, **override}
    return check_labels(labels, t)


def test_good_labels_pass(cfg):
    labels = assign_splits(synthetic_labels(), cfg["tcga"]["split_fractions"], seed=cfg["seed"])
    checked(cfg, labels)


def leak_one_slide(d):
    """Move one slide of the first hospital into another split."""
    d = d.copy()
    first = d.index[d.hospital == d.hospital.iloc[0]][0]
    d.loc[first, "split"] = next(s for s in ("train", "cal", "test") if s != d.loc[first, "split"])
    return d


@pytest.mark.parametrize("breakage, message", [
    (leak_one_slide, "hospital"),
    (lambda d: d.assign(truth_pct=d.truth_pct / 100), "fraction"),
    (lambda d: d.assign(pathologist_pct=d.pathologist_pct.where(d.index != 3, 140.0)), "pathologist_pct"),
    (lambda d: d.assign(truth_pct=d.truth_pct.where(d.index != 3, np.nan)), "missing"),
    (lambda d: d.assign(sample_id=d.sample_id.where(d.index != 3, "TCGA-AA-1-01A")), "sample_id"),
    (lambda d: pd.concat([d, d.iloc[[0]]], ignore_index=True), "slide_id"),
])
def test_bad_labels_are_rejected(cfg, breakage, message):
    labels = assign_splits(synthetic_labels(), cfg["tcga"]["split_fractions"], seed=cfg["seed"])
    with pytest.raises(LabelsError, match=message):
        checked(cfg, breakage(labels))


def test_small_test_split_is_rejected(cfg):
    labels = assign_splits(synthetic_labels(), cfg["tcga"]["split_fractions"], seed=cfg["seed"])
    with pytest.raises(LabelsError, match="test split"):
        checked(cfg, labels, min_test_slides=10_000)
    with pytest.raises(LabelsError, match="below"):
        checked(cfg, labels, min_test_below_cutoff=10_000)

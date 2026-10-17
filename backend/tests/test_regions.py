"""Phase 3: region ranking, rule-based reasons and the tumor heatmap. Synthetic score grids only, no images."""

import re

import numpy as np
import pytest

from project.config import load_config
from project.regions import (
    parse_pct,
    pct,
    rank_regions,
    region_score,
    score_grid,
    slide_composition,
    tumor_heatmap,
)
from project.tiling import Tile


@pytest.fixture
def cfg():
    return load_config()


def grid(cfg, rows, cols, tumor=0.2, necrosis=0.02):
    """[rows, cols, n_classes] probabilities: the given tumor and necrosis, the rest shared evenly."""
    classes = cfg["classes"]
    probs = np.zeros((rows, cols, len(classes)))
    probs[..., classes.index("tumor")] = tumor
    probs[..., classes.index("necrosis")] = necrosis
    rest = [i for i, c in enumerate(classes) if c not in ("tumor", "necrosis")]
    probs[..., rest] = ((1 - probs.sum(axis=-1)) / len(rest))[..., None]
    return probs


def set_block(cfg, probs, r, c, n, tumor, necrosis=0.0):
    probs[r:r + n, c:c + n] = grid(cfg, n, n, tumor, necrosis)


def full_tissue(rows, cols):
    return np.ones((rows, cols))


def rank(cfg, probs, tissue, tile_size=256, scale=1.0):
    return rank_regions(probs, tissue, cfg, tile_size=tile_size, scale=scale)


def overlaps(a, b, n):
    return abs(a["row"] - b["row"]) < n and abs(a["col"] - b["col"]) < n


# --- score formula --------------------------------------------------------------------------------

def test_score_matches_hand_computed_example(cfg):
    # Four tiles: tumor 0.6, 0.8, 0.6, 0.8 -> mean 0.7, population std 0.1; necrosis 0.1, 0.1, 0, 0 -> mean 0.05.
    # score = 0.7 - 1.0 * 0.05 - 0.5 * 0.1 = 0.6 with the config weights (necrosis 1.0, variation 0.5).
    assert cfg["weights"] == {"necrosis": 1.0, "variation": 0.5}
    tumor = np.array([0.6, 0.8, 0.6, 0.8])
    necrosis = np.array([0.1, 0.1, 0.0, 0.0])
    assert region_score(tumor, necrosis, cfg["weights"]) == pytest.approx(0.6, abs=1e-12)


def test_ranked_region_score_uses_the_formula(cfg):
    cfg["region_tiles"] = 2
    probs = grid(cfg, 2, 2)
    t, k = cfg["classes"].index("tumor"), cfg["classes"].index("necrosis")
    probs[..., t] = [[0.6, 0.8], [0.6, 0.8]]
    probs[..., k] = [[0.1, 0.1], [0.0, 0.0]]
    regions, _ = rank(cfg, probs, full_tissue(2, 2))
    assert regions[0]["score"] == pytest.approx(0.6, abs=1e-9)
    assert regions[0]["tumor_std"] == pytest.approx(0.1, abs=1e-9)
    assert regions[0]["composition"]["tumor"] == pytest.approx(0.7, abs=1e-9)


# --- ranking --------------------------------------------------------------------------------------

def test_top_region_lands_on_the_high_tumor_patch(cfg):
    n = cfg["region_tiles"]
    probs = grid(cfg, 16, 16, tumor=0.1)
    set_block(cfg, probs, 6, 9, n, tumor=0.9)
    regions, _ = rank(cfg, probs, full_tissue(16, 16))
    assert (regions[0]["row"], regions[0]["col"]) == (6, 9)


def test_exactly_top_k_regions_when_enough_are_eligible(cfg):
    rng = np.random.default_rng(cfg["seed"])
    probs = grid(cfg, 20, 20)
    probs[..., cfg["classes"].index("tumor")] += rng.uniform(0, 0.3, (20, 20))
    probs /= probs.sum(axis=-1, keepdims=True)
    regions, note = rank(cfg, probs, full_tissue(20, 20))
    assert len(regions) == cfg["top_k"] == 5
    assert note is None


def test_fewer_regions_come_with_a_note(cfg):
    n = cfg["region_tiles"]
    regions, note = rank(cfg, grid(cfg, n, 2 * n), full_tissue(n, 2 * n))
    assert len(regions) == 2
    assert note and "2" in note


def test_no_eligible_region_gives_empty_list_and_note(cfg):
    regions, note = rank(cfg, grid(cfg, 8, 8), np.zeros((8, 8)))
    assert regions == []
    assert note


def test_image_smaller_than_one_region_gives_note(cfg):
    regions, note = rank(cfg, grid(cfg, 2, 2), full_tissue(2, 2))
    assert regions == []
    assert note


def test_regions_never_overlap_and_meet_min_coverage(cfg):
    n = cfg["region_tiles"]
    rng = np.random.default_rng(cfg["seed"])
    probs = grid(cfg, 24, 24)
    probs[..., cfg["classes"].index("tumor")] += rng.uniform(0, 0.5, (24, 24))
    probs /= probs.sum(axis=-1, keepdims=True)
    tissue = rng.uniform(0.8, 1.0, (24, 24))  # windows average ~0.9: some pass min_coverage, some don't
    tissue[:, :6] = 0.0  # glass along the left edge
    regions, _ = rank(cfg, probs, tissue)
    assert regions
    for i, a in enumerate(regions):
        assert a["tissue_coverage"] >= cfg["min_coverage"]
        assert a["tissue_coverage"] == pytest.approx(tissue[a["row"]:a["row"] + n, a["col"]:a["col"] + n].mean())
        for b in regions[i + 1:]:
            assert not overlaps(a, b, n)


def test_exactly_one_best_and_it_is_rank_one(cfg):
    regions, _ = rank(cfg, grid(cfg, 20, 20), full_tissue(20, 20))
    best = [r for r in regions if r["is_best"]]
    assert len(best) == 1 and best[0]["rank"] == 1
    assert [r["rank"] for r in regions] == list(range(1, len(regions) + 1))


def test_ranks_sorted_by_score_descending(cfg):
    rng = np.random.default_rng(cfg["seed"])
    probs = grid(cfg, 20, 20)
    probs[..., cfg["classes"].index("tumor")] += rng.uniform(0, 0.6, (20, 20))
    probs /= probs.sum(axis=-1, keepdims=True)
    scores = [r["score"] for r in rank(cfg, probs, full_tissue(20, 20))[0]]
    assert scores == sorted(scores, reverse=True)


def test_each_composition_sums_to_one(cfg):
    rng = np.random.default_rng(cfg["seed"])
    probs = rng.dirichlet(np.ones(len(cfg["classes"])), (20, 20))
    regions, _ = rank(cfg, probs, full_tissue(20, 20))
    for r in regions:
        assert list(r["composition"]) == cfg["classes"]
        assert sum(r["composition"].values()) == pytest.approx(1.0, abs=1e-9)


def test_high_necrosis_loses_to_slightly_lower_tumor(cfg):
    n = cfg["region_tiles"]
    probs = grid(cfg, n, 3 * n, tumor=0.05)
    set_block(cfg, probs, 0, 0, n, tumor=0.70, necrosis=0.25)       # score 0.70 - 0.25 = 0.45
    set_block(cfg, probs, 0, 2 * n, n, tumor=0.60, necrosis=0.0)    # score 0.60
    regions, _ = rank(cfg, probs, full_tissue(n, 3 * n))
    assert (regions[0]["row"], regions[0]["col"]) == (0, 2 * n)

    cfg["weights"]["necrosis"] = 0.0                                # necrosis no longer penalized
    regions, _ = rank(cfg, probs, full_tissue(n, 3 * n))
    assert (regions[0]["row"], regions[0]["col"]) == (0, 0)


def test_unanalyzed_tiles_are_left_out_of_composition(cfg):
    # Tiles dropped by the max_tiles cap are NaN in the score grid; the region uses the tiles it has.
    n = cfg["region_tiles"]
    probs = grid(cfg, n, n, tumor=0.5)
    probs[0, 0] = np.nan
    regions, _ = rank(cfg, probs, full_tissue(n, n))
    assert regions[0]["composition"]["tumor"] == pytest.approx(0.5)


# --- boxes in display pixels ----------------------------------------------------------------------

def test_box_is_in_display_pixels(cfg):
    n = cfg["region_tiles"]
    probs = grid(cfg, 12, 12, tumor=0.1)
    set_block(cfg, probs, 2, 3, n, tumor=0.9)
    # 512 original px per tile, display downsampled 4x -> 128 display px per tile.
    best = rank(cfg, probs, full_tissue(12, 12), tile_size=512, scale=4.0)[0][0]
    assert (best["x"], best["y"], best["w"], best["h"]) == (3 * 128, 2 * 128, n * 128, n * 128)
    assert best["size_um"] == pytest.approx(n * cfg["tile_px"] * cfg["target_mpp"])


# --- reasons --------------------------------------------------------------------------------------

def test_pct_round_trips():
    assert pct(0.62) == "62%"
    assert pct(0.98) == "98%"
    assert parse_pct("Low necrosis (3%), which favors good DNA yield") == [3]
    assert parse_pct("a 12% and 98% b") == [12, 98]


def ranked_example(cfg):
    n = cfg["region_tiles"]
    rng = np.random.default_rng(cfg["seed"])
    probs = grid(cfg, 24, 24, tumor=0.15, necrosis=0.10)
    for i, (r, c) in enumerate([(2, 2), (2, 12), (12, 4), (14, 14), (8, 19)]):
        set_block(cfg, probs, r, c, n, tumor=0.8 - 0.08 * i, necrosis=[0.01, 0.2, 0.03, 0.0, 0.12][i])
    probs[..., cfg["classes"].index("tumor")] += rng.uniform(0, 0.03, (24, 24))
    probs /= probs.sum(axis=-1, keepdims=True)
    tissue = np.clip(rng.uniform(0.85, 1.05, (24, 24)), 0, 1)
    return rank(cfg, probs, tissue)[0]


def test_every_quoted_number_matches_the_region(cfg):
    regions = ranked_example(cfg)
    best_tumor = int(pct(regions[0]["composition"]["tumor"])[:-1])
    assert len(regions) == 5
    for r in regions:
        assert r["reasons"], f"rank {r['rank']} has no reasons"
        for reason in r["reasons"]:
            low = reason.lower()
            nums = parse_pct(reason)
            if " point" in low:
                diff = abs(best_tumor - int(pct(r["composition"]["tumor"])[:-1]))
                assert [int(x) for x in re.findall(r"(\d+) points?", reason)] == [diff], reason
            elif "necrosis" in low:
                assert nums == [int(pct(r["composition"]["necrosis"])[:-1])], reason
            elif "coverage" in low:
                assert nums == [int(pct(r["tissue_coverage"])[:-1])], reason
            elif "tumor content" in low and nums:
                assert nums == [int(pct(r["composition"]["tumor"])[:-1])], reason


def test_reasons_are_only_emitted_when_true(cfg):
    regions = ranked_example(cfg)
    cut = cfg["reason_cutoffs"]
    top_tumor = max(r["composition"]["tumor"] for r in regions)
    for r in regions:
        text = " ".join(r["reasons"])
        if "Highest tumor content" in text:
            assert r["composition"]["tumor"] >= top_tumor
        assert ("Low necrosis" in text) == (r["composition"]["necrosis"] <= cut["low_necrosis"])
        assert ("Fully on tissue" in text) == (r["tissue_coverage"] >= cut["full_coverage"])
        assert ("low variation" in text) == (r["tumor_std"] <= cut["low_variation"])
        if r["rank"] > 1:
            assert "best region" in text
        else:
            assert "best region" not in text


def test_highest_tumor_reason_checks_every_eligible_candidate(cfg):
    # The best-scoring region isn't the most tumor-rich candidate when necrosis drags the richer one down.
    n = cfg["region_tiles"]
    probs = grid(cfg, n, 3 * n, tumor=0.05)
    set_block(cfg, probs, 0, 0, n, tumor=0.70, necrosis=0.25)
    set_block(cfg, probs, 0, 2 * n, n, tumor=0.60, necrosis=0.0)
    regions, _ = rank(cfg, probs, full_tissue(n, 3 * n))
    assert regions[0]["col"] == 2 * n
    assert not any("Highest tumor content" in s for s in regions[0]["reasons"])
    richer = next(r for r in regions if r["col"] == 0)
    assert any("Highest tumor content" in s for s in richer["reasons"])


# --- score grid and heatmap -----------------------------------------------------------------------

def test_tile_scores_land_at_row_y_col_x(cfg):
    n_cls = len(cfg["classes"])
    tiles = [Tile(row=1, col=3, x=3 * 256, y=256, size=256, tissue=1.0)]
    probs = np.full((1, n_cls), 1 / n_cls)
    out = score_grid(tiles, probs, shape=(4, 6))
    assert out.shape == (4, 6, n_cls)
    np.testing.assert_allclose(out[1, 3], 1 / n_cls)
    assert np.isnan(out[3, 1]).all()
    assert np.isnan(out).all(axis=-1).sum() == 4 * 6 - 1


def test_heatmap_places_tile_at_its_display_position(cfg):
    classes = cfg["classes"]
    probs = np.full((4, 6, len(classes)), np.nan)
    probs[1, 3] = grid(cfg, 1, 1, tumor=0.9)[0, 0]
    # 100 original px per tile, display downsampled 2x -> 50 display px per tile; display is 300 x 200.
    img = tumor_heatmap(probs, classes, tile_size=100, scale=2.0, display_size=(300, 200))
    assert img.size == (300, 200) and img.mode == "RGBA"
    arr = np.asarray(img)
    assert arr.shape == (200, 300, 4)
    assert arr[1 * 50 + 25, 3 * 50 + 25, 3] > 150       # inside tile (row 1, col 3): opaque
    assert arr[3 * 50 + 25, 1 * 50 + 25, 3] == 0        # the transposed spot stays clear
    assert arr[25, 25, 3] == 0


def test_heatmap_opacity_follows_tumor(cfg):
    classes = cfg["classes"]
    probs = np.concatenate([grid(cfg, 1, 1, tumor=0.2), grid(cfg, 1, 1, tumor=0.8)], axis=1)
    arr = np.asarray(tumor_heatmap(probs, classes, tile_size=10, scale=1.0, display_size=(20, 10)))
    assert arr[5, 15, 3] > arr[5, 5, 3]


def test_slide_composition_is_the_mean_over_tiles_and_sums_to_one(cfg):
    classes = cfg["classes"]
    probs = np.array([grid(cfg, 1, 1, tumor=0.2)[0, 0], grid(cfg, 1, 1, tumor=0.6)[0, 0]])
    comp = slide_composition(probs, classes)
    assert list(comp) == classes
    assert comp["tumor"] == pytest.approx(0.4)
    assert sum(comp.values()) == pytest.approx(1.0)

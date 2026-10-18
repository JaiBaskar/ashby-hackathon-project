"""Phase 3: region ranking, rule-based reasons and the tumor heatmap. Synthetic score grids only, no images."""

import colorsys
import re

import numpy as np
import pytest

from project.config import load_config
from project.regions import (
    HEATMAP_MAX_ALPHA,
    HEATMAP_MIN_SPAN,
    HEATMAP_RGB,
    box_tiles,
    default_box_um,
    measure_box,
    parse_pct,
    pct,
    rank_regions,
    region_score,
    score_grid,
    slide_composition,
    heatmap_range,
    tumor_heatmap,
)
from project.tiling import Tile
from tests.synthetic import PINK, PURPLE


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


# --- minimum tumor for sequencing: no region reaches it → no regions, and the note says so -------

def test_minimum_tumor_is_twenty_percent_in_config(cfg):
    assert cfg["min_tumor_pct"] == 20  # matches the results screen's default (frontend DEFAULT_THRESHOLD)


def test_no_region_reaching_the_minimum_gives_no_regions_and_says_so(cfg):
    probs = grid(cfg, 16, 16, tumor=0.1)
    regions, note = rank(cfg, probs, full_tissue(16, 16))
    assert regions == []
    assert "20% tumor minimum" in note
    assert "10%" in note  # the most tumor-rich region's share, so the pathologist sees how far off it is


def test_one_region_at_the_minimum_is_enough_to_rank(cfg):
    n = cfg["region_tiles"]
    probs = grid(cfg, 16, 16, tumor=0.05)
    set_block(cfg, probs, 4, 8, n, tumor=0.20)
    regions, note = rank(cfg, probs, full_tissue(16, 16))
    assert (regions[0]["row"], regions[0]["col"]) == (4, 8)
    assert len(regions) == cfg["top_k"] and note is None


@pytest.mark.parametrize("tumor, has_regions", [(0.196, True), (0.194, False)])
def test_minimum_compares_the_percent_as_shown(cfg, tumor, has_regions):
    # 19.6% shows as "20%" and must not read as below a 20% minimum; 19.4% shows as "19%".
    regions, note = rank(cfg, grid(cfg, 8, 8, tumor=tumor), full_tissue(8, 8))
    assert bool(regions) == has_regions
    assert ("tumor minimum" in (note or "")) != has_regions


def test_minimum_checks_every_candidate_not_just_the_top_scores(cfg):
    # The necrotic block reaches 30% tumor but scores below the even 15% background, so it isn't the top pick.
    n = cfg["region_tiles"]
    probs = grid(cfg, n, 3 * n, tumor=0.15, necrosis=0.0)
    set_block(cfg, probs, 0, 2 * n, n, tumor=0.30, necrosis=0.25)
    regions, _ = rank(cfg, probs, full_tissue(n, 3 * n))
    assert regions
    assert regions[0]["composition"]["tumor"] == pytest.approx(0.15)


def test_minimum_comes_from_config(cfg):
    probs = grid(cfg, 8, 8, tumor=0.15)
    assert rank(cfg, probs, full_tissue(8, 8))[0] == []
    cfg["min_tumor_pct"] = 10
    assert rank(cfg, probs, full_tissue(8, 8))[0]


def test_coverage_note_wins_when_no_region_is_on_tissue(cfg):
    regions, note = rank(cfg, grid(cfg, 8, 8, tumor=0.05), np.zeros((8, 8)))
    assert regions == []
    assert "on tissue" in note and "tumor minimum" not in note


# --- boxes in display pixels ----------------------------------------------------------------------

def test_box_is_in_display_pixels(cfg):
    n = cfg["region_tiles"]
    probs = grid(cfg, 12, 12, tumor=0.1)
    set_block(cfg, probs, 2, 3, n, tumor=0.9)
    # 512 original px per tile, display downsampled 4x -> 128 display px per tile.
    best = rank(cfg, probs, full_tissue(12, 12), tile_size=512, scale=4.0)[0][0]
    assert (best["x"], best["y"], best["w"], best["h"]) == (3 * 128, 2 * 128, n * 128, n * 128)
    assert best["size_um"] == pytest.approx(n * cfg["tile_px"] * cfg["target_mpp"])


def test_box_tiles_converts_offered_sizes(cfg):
    tile_um = cfg["tile_px"] * cfg["target_mpp"]  # 128 µm
    assert default_box_um(cfg) == cfg["region_tiles"] * tile_um
    for size in cfg["box_sizes_um"]:
        n = box_tiles(cfg, size)
        assert isinstance(n, int) and n * tile_um == size
    assert box_tiles(cfg, 1024.0) == 8  # a float from a query string works too


@pytest.mark.parametrize("size", [1000, 0, -512, 64])
def test_box_tiles_refuses_sizes_not_offered(cfg, size):
    with pytest.raises(ValueError, match="not one of"):
        box_tiles(cfg, size)


def test_a_bigger_box_covers_more_tiles_and_reports_its_size(cfg):
    probs = grid(cfg, 20, 20, tumor=0.1)
    set_block(cfg, probs, 4, 4, 8, tumor=0.9)
    big = {**cfg, "region_tiles": box_tiles(cfg, 1024)}
    best = rank(big, probs, full_tissue(20, 20))[0][0]
    assert (best["row"], best["col"]) == (4, 4)
    assert (best["w"], best["h"]) == (8 * 256, 8 * 256)
    assert best["size_um"] == pytest.approx(1024)
    assert best["composition"]["tumor"] == pytest.approx(0.9)


# --- free-form box: any rectangle, tiles weighted by how much of them it covers ------------------

def measure(cfg, probs, tissue, x, y, w, h, tile_size=256, scale=1.0, mpp=0.5):
    return measure_box(probs, tissue, cfg, tile_size, scale, mpp, x, y, w, h)


def test_a_box_on_exactly_one_tile_reports_that_tile(cfg):
    probs = grid(cfg, 4, 4, tumor=0.1)
    set_block(cfg, probs, 1, 2, 1, tumor=0.8, necrosis=0.1)
    box = measure(cfg, probs, full_tissue(4, 4), x=512, y=256, w=256, h=256)
    assert box["composition"]["tumor"] == pytest.approx(0.8)
    assert box["composition"]["necrosis"] == pytest.approx(0.1)
    assert box["tumor_std"] == pytest.approx(0.0)
    assert box["score"] == pytest.approx(0.8 - 0.1)
    assert box["tiles"] == pytest.approx(1.0)
    assert (box["width_um"], box["height_um"]) == (pytest.approx(128), pytest.approx(128))


def test_partial_tiles_count_by_the_area_the_box_covers(cfg):
    # Box from x = 192 to 448 covers the last quarter of tile 0 and three quarters of tile 1 (rows 0–1).
    probs = grid(cfg, 2, 3, tumor=0.0)
    probs[:, 1] = grid(cfg, 2, 1, tumor=0.8)[:, 0]
    box = measure(cfg, probs, full_tissue(2, 3), x=192, y=0, w=256, h=512)
    assert box["composition"]["tumor"] == pytest.approx(0.25 * 0.0 + 0.75 * 0.8)
    assert box["tumor_std"] == pytest.approx(np.sqrt(0.25 * 0.6 ** 2 + 0.75 * 0.2 ** 2))
    assert box["tiles"] == pytest.approx(2.0)
    assert sum(box["composition"].values()) == pytest.approx(1.0)


def test_any_rectangle_shape_and_scale_is_measured_in_µm(cfg):
    probs = grid(cfg, 10, 10)
    # 512 original px per tile, display downsampled 4x: 128 display px per tile, 1 original px = 0.25 µm.
    box = measure(cfg, probs, full_tissue(10, 10), x=10, y=20, w=300, h=90, tile_size=512, scale=4.0, mpp=0.25)
    assert (box["width_um"], box["height_um"]) == (pytest.approx(300 * 4 * 0.25), pytest.approx(90 * 4 * 0.25))
    assert box["tiles"] == pytest.approx((300 / 128) * (90 / 128))
    assert (box["x"], box["y"], box["w"], box["h"]) == (10, 20, 300, 90)


def test_coverage_counts_glass_inside_the_box(cfg):
    probs = grid(cfg, 2, 2)
    tissue = np.array([[1.0, 0.0], [1.0, 0.0]])
    probs[:, 1] = np.nan  # glass tiles aren't analyzed
    box = measure(cfg, probs, tissue, x=0, y=0, w=512, h=512)
    assert box["tissue_coverage"] == pytest.approx(0.5)
    assert box["composition"]["tumor"] == pytest.approx(0.2)  # only analyzed tiles, weights renormalized
    assert any("50% on tissue" in r for r in box["reasons"])


def test_the_box_is_clipped_to_the_tile_grid(cfg):
    probs = grid(cfg, 2, 2, tumor=0.4)
    box = measure(cfg, probs, full_tissue(2, 2), x=-100, y=256, w=1000, h=1000)
    assert (box["x"], box["y"], box["w"], box["h"]) == (0, 256, 512, 256)
    assert box["composition"]["tumor"] == pytest.approx(0.4)


@pytest.mark.parametrize("x, y, w, h", [(0, 0, 0, 100), (0, 0, 100, -5), (5000, 0, 100, 100)])
def test_an_empty_box_is_refused(cfg, x, y, w, h):
    with pytest.raises(ValueError, match="box"):
        measure(cfg, grid(cfg, 2, 2), full_tissue(2, 2), x, y, w, h)


def test_a_box_with_no_analyzed_tile_is_refused(cfg):
    probs = np.full((2, 2, len(cfg["classes"])), np.nan)
    with pytest.raises(ValueError, match="no analyzed tissue"):
        measure(cfg, probs, np.zeros((2, 2)), 0, 0, 256, 256)


def test_free_box_reasons_quote_its_own_numbers(cfg):
    probs = grid(cfg, 4, 4, tumor=0.5, necrosis=0.02)
    box = measure(cfg, probs, full_tissue(4, 4), x=0, y=0, w=1024, h=1024)
    assert "Low necrosis (2%), which favors good DNA yield" in box["reasons"]
    assert "Fully on tissue (100% coverage)" in box["reasons"]
    assert "Tumor content is even across the box (low variation)" in box["reasons"]
    small = measure(cfg, probs, full_tissue(4, 4), x=0, y=0, w=200, h=200)
    assert any("fewer than 4 tiles" in r for r in small["reasons"])


def test_a_free_box_on_a_suggested_region_matches_it(cfg):
    n = cfg["region_tiles"]
    rng = np.random.default_rng(0)
    probs = grid(cfg, 12, 12)
    probs[..., 0] = rng.uniform(0, 0.6, (12, 12))
    probs[..., 1] = 1 - probs[..., 0] - probs[..., 2:].sum(axis=-1)
    tissue = full_tissue(12, 12)
    best = rank(cfg, probs, tissue)[0][0]
    box = measure(cfg, probs, tissue, best["x"], best["y"], best["w"], best["h"])
    assert box["score"] == pytest.approx(best["score"])
    assert box["tumor_std"] == pytest.approx(best["tumor_std"])
    for c in cfg["classes"]:
        assert box["composition"][c] == pytest.approx(best["composition"][c])
    assert box["tiles"] == pytest.approx(n * n)


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
    img = tumor_heatmap(probs, classes, tile_size=100, scale=2.0, display_size=(300, 200), value_range=(0.0, 1.0))
    assert img.size == (300, 200) and img.mode == "RGBA"
    arr = np.asarray(img)
    assert arr.shape == (200, 300, 4)
    assert arr[1 * 50 + 25, 3 * 50 + 25, 3] > 100       # inside tile (row 1, col 3): clearly tinted
    assert arr[3 * 50 + 25, 1 * 50 + 25, 3] == 0        # the transposed spot stays clear
    assert arr[25, 25, 3] == 0


def test_heatmap_opacity_follows_tumor(cfg):
    classes = cfg["classes"]
    probs = np.concatenate([grid(cfg, 1, 1, tumor=0.2), grid(cfg, 1, 1, tumor=0.8)], axis=1)
    arr = np.asarray(tumor_heatmap(probs, classes, tile_size=10, scale=1.0, display_size=(20, 10)))
    assert arr[5, 15, 3] > arr[5, 5, 3]


def tumor_grid(cfg, values):
    """[rows, cols, n_classes] with the given tumor probabilities (NaN = not analyzed)."""
    values = np.asarray(values, float)
    probs = grid(cfg, *values.shape, tumor=0.5)
    probs[..., cfg["classes"].index("tumor")] = values
    probs[np.isnan(values)] = np.nan
    return probs


def alpha_map(cfg, values, tile=20, **kw):
    values = np.asarray(values, float)
    rows, cols = values.shape
    img = tumor_heatmap(tumor_grid(cfg, values), cfg["classes"], tile_size=tile, scale=1.0,
                        display_size=(cols * tile, rows * tile), **kw)
    return np.asarray(img)[..., 3].astype(int)


# The color scale: stretched over the slide's own spread, so a slide that is all "fairly high" still shows contrast.

def test_heatmap_range_is_the_slides_spread_widened_to_a_minimum():
    values = np.linspace(0.78, 0.90, 200)
    lo, hi = heatmap_range(values)
    assert hi - lo == pytest.approx(HEATMAP_MIN_SPAN)
    assert (lo + hi) / 2 == pytest.approx(0.84, abs=0.01)   # centered on the slide's spread


def test_heatmap_range_keeps_a_wide_spread_and_ignores_outliers():
    values = np.concatenate([np.linspace(0.1, 0.9, 1000), [0.0, 1.0]])
    lo, hi = heatmap_range(values)
    assert lo == pytest.approx(np.percentile(values, 5)) and hi == pytest.approx(np.percentile(values, 95))


def test_heatmap_range_stays_within_0_and_1():
    assert heatmap_range(np.full(50, 0.98)) == pytest.approx((1 - HEATMAP_MIN_SPAN, 1.0))
    assert heatmap_range(np.full(50, 0.01)) == pytest.approx((0.0, HEATMAP_MIN_SPAN))
    assert heatmap_range(np.array([np.nan])) == (0.0, 1.0)


def test_heatmap_shows_contrast_on_a_uniformly_high_slide(cfg):
    # The demo model scored a real slide 0.78–0.90 everywhere; with opacity ∝ probability every tile looked the same.
    a = alpha_map(cfg, [[0.78, 0.84, 0.90]] * 3)
    low, high = a[30, 10], a[30, 50]
    assert high >= 3 * max(low, 1)


def test_heatmap_never_hides_the_tissue(cfg):
    a = alpha_map(cfg, [[1.0] * 3] * 3, value_range=(0.0, 1.0))
    assert a.max() <= round(HEATMAP_MAX_ALPHA * 255) <= 0.7 * 255


def test_tiles_below_the_range_are_clear(cfg):
    a = alpha_map(cfg, [[0.2] * 3 + [0.9] * 3] * 3, value_range=(0.5, 1.0))
    assert a[30, 10] == 0 and a[30, 110] > 0


def test_heatmap_has_no_seams_between_matching_tiles(cfg):
    a = alpha_map(cfg, [[0.9] * 4] * 3, value_range=(0.0, 1.0))
    row = a[30, 20:60]
    assert row.max() - row.min() <= 2


def test_heatmap_edges_fade_instead_of_stepping(cfg):
    nan = np.nan
    values = [[nan] * 5] + [[nan, 0.9, 0.9, 0.9, nan]] * 3 + [[nan] * 5]
    row = alpha_map(cfg, values, value_range=(0.0, 1.0))[50]
    assert np.abs(np.diff(row)).max() < row.max() / 3
    assert ((row > 0) & (row < row.max() * 0.9)).sum() >= 8


def test_heatmap_fades_where_the_tile_grid_ends_before_the_image(cfg):
    # Only whole tiles are cut, so a strip at the right and bottom is never analyzed. The overlay must fade out
    # into it, not stop at the grid's edge (a real slide showed a full-strength cut-off line there).
    probs = tumor_grid(cfg, [[0.9] * 3] * 3)
    img = tumor_heatmap(probs, cfg["classes"], tile_size=20, scale=1.0, display_size=(75, 75), value_range=(0.0, 1.0))
    a = np.asarray(img)[..., 3].astype(int)
    peak = a.max()
    assert np.abs(np.diff(a[30, :], axis=0)).max() < peak / 3      # across the right edge of the grid
    assert np.abs(np.diff(a[:, 30], axis=0)).max() < peak / 3      # across the bottom edge
    # The fade is centered on the grid's edge (like tissue edges): about half strength there, near clear inside the strip.
    assert a[30, 59] <= peak * 0.6 and a[59, 30] <= peak * 0.6
    assert a[30, 66] < peak * 0.1 and a[66, 30] < peak * 0.1
    assert a[5, 5] > peak * 0.8                                     # the image's own top-left border stays tinted


def test_heatmap_corners_are_rounded_not_square(cfg):
    nan = np.nan
    values = [[nan] * 5] + [[nan, 0.9, 0.9, 0.9, nan]] * 3 + [[nan] * 5]
    a = alpha_map(cfg, values, value_range=(0.0, 1.0))
    # Tissue spans 20..80. Just inside the corner is fainter than just inside the middle of an edge.
    assert a[23, 23] < a[23, 50] * 0.75


def test_slide_composition_is_the_mean_over_tiles_and_sums_to_one(cfg):
    classes = cfg["classes"]
    probs = np.array([grid(cfg, 1, 1, tumor=0.2)[0, 0], grid(cfg, 1, 1, tumor=0.6)[0, 0]])
    comp = slide_composition(probs, classes)
    assert list(comp) == classes
    assert comp["tumor"] == pytest.approx(0.4)
    assert sum(comp.values()) == pytest.approx(1.0)


def _hue_deg(rgb):
    return colorsys.rgb_to_hsv(*(v / 255 for v in rgb))[0] * 360


@pytest.mark.parametrize("stain", [PINK, PURPLE])
def test_heatmap_tint_hue_is_far_from_both_stains(stain):
    # The overlay sits on eosin pink and hematoxylin purple; a tint near either hue disappears into the tissue.
    gap = abs(_hue_deg(HEATMAP_RGB) - _hue_deg(stain)) % 360
    assert min(gap, 360 - gap) >= 60

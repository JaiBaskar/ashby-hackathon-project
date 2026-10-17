"""Region ranking, rule-based reasons and the tumor heatmap.

Score grids are indexed [row, col] = [y, x] (AGENTS.md §4); tiles that weren't analyzed are NaN.
"""

import re

import numpy as np
from PIL import Image

HEATMAP_RGB = (214, 40, 110)   # tumor overlay color; opacity follows the tumor probability
HEATMAP_MAX_ALPHA = 0.85


def pct(fraction):
    """The one place percentages are formatted, so tests can parse them back."""
    return f"{round(fraction * 100)}%"


def parse_pct(text):
    return [int(m) for m in re.findall(r"(\d+)%", text)]


def region_score(tumor, necrosis, weights):
    """tumor − w_necrosis × necrosis − w_variation × std(tumor across tiles), from per-tile values."""
    tumor, necrosis = np.asarray(tumor, float), np.asarray(necrosis, float)
    return float(tumor.mean() - weights["necrosis"] * necrosis.mean() - weights["variation"] * tumor.std())


def score_grid(tiles, probs, shape):
    """Per-tile probabilities placed on the full tile grid: out[tile.row, tile.col]; other tiles are NaN."""
    out = np.full((*shape, probs.shape[1]), np.nan)
    for tile, p in zip(tiles, probs):
        out[tile.row, tile.col] = p
    return out


def slide_composition(probs, classes):
    mean = np.nanmean(probs, axis=0)
    return {c: float(v) for c, v in zip(classes, mean)}


def _candidates(probs, tissue, cfg):
    """Every eligible N×N window, with its numbers."""
    n = cfg["region_tiles"]
    classes = cfg["classes"]
    t, k = classes.index("tumor"), classes.index("necrosis")
    rows, cols = tissue.shape
    out = []
    for r in range(rows - n + 1):
        for c in range(cols - n + 1):
            coverage = float(tissue[r:r + n, c:c + n].mean())
            block = probs[r:r + n, c:c + n].reshape(-1, len(classes))
            block = block[~np.isnan(block).any(axis=1)]
            if coverage < cfg["min_coverage"] or len(block) == 0:
                continue
            comp = block.mean(axis=0)
            out.append({
                "row": r, "col": c,
                "score": region_score(block[:, t], block[:, k], cfg["weights"]),
                "tissue_coverage": coverage,
                "tumor_std": float(block[:, t].std()),
                "composition": {cl: float(v) for cl, v in zip(classes, comp)},
            })
    return out


def _pick(candidates, n, top_k):
    """Greedy: take the best, drop candidates that overlap it, repeat."""
    remaining = sorted(candidates, key=lambda d: (-d["score"], d["row"], d["col"]))
    picked = []
    while remaining and len(picked) < top_k:
        best = remaining.pop(0)
        picked.append(best)
        remaining = [d for d in remaining if abs(d["row"] - best["row"]) >= n or abs(d["col"] - best["col"]) >= n]
    return picked


def _reasons(region, best, top_tumor, cutoffs):
    comp = region["composition"]
    out = []
    if region["rank"] == 1:
        out.append(f"Highest overall score of all candidates ({region['score']:.2f})")
    if comp["tumor"] >= top_tumor:
        out.append(f"Highest tumor content of all candidates ({pct(comp['tumor'])})")
    if comp["necrosis"] <= cutoffs["low_necrosis"]:
        out.append(f"Low necrosis ({pct(comp['necrosis'])}), which favors good DNA yield")
    if region["tissue_coverage"] >= cutoffs["full_coverage"]:
        out.append(f"Fully on tissue ({pct(region['tissue_coverage'])} coverage)")
    if region["tumor_std"] <= cutoffs["low_variation"]:
        out.append("Tumor content is even across the region (low variation)")
    if region["rank"] > 1:
        diff = parse_pct(pct(best["composition"]["tumor"]))[0] - parse_pct(pct(comp["tumor"]))[0]
        unit = "point" if abs(diff) == 1 else "points"
        if diff > 0:
            out.append(f"Tumor content is {diff} {unit} lower than the best region")
        elif diff < 0:
            out.append(
                f"Tumor content is {-diff} {unit} higher than the best region, "
                "but more necrosis or uneven tumor lowers its score"
            )
        else:
            out.append(f"Tumor content matches the best region ({pct(comp['tumor'])})")
    return out


def _note(found, n_windows, cfg):
    n, top_k = cfg["region_tiles"], cfg["top_k"]
    if found >= top_k:
        return None
    if n_windows == 0:
        return f"The image is smaller than one region ({n}×{n} tiles), so no regions could be suggested."
    if found == 0:
        return (f"No {n}×{n}-tile region is at least {pct(cfg['min_coverage'])} on tissue, "
                "so no regions could be suggested.")
    regions, are = ("region", "is") if found == 1 else ("regions", "are")
    return (f"Only {found} non-overlapping {n}×{n}-tile {regions} {are} at least {pct(cfg['min_coverage'])} "
            f"on tissue, so {found} {are} shown instead of {top_k}.")


def rank_regions(probs, tissue, cfg, tile_size, scale):
    """Top non-overlapping eligible regions, best first, and a note when fewer than top_k exist.

    probs: [rows, cols, n_classes] (NaN where a tile wasn't analyzed); tissue: [rows, cols] tissue fractions.
    tile_size is the tile edge in original pixels; scale is original pixels per display pixel.
    """
    n = cfg["region_tiles"]
    rows, cols = tissue.shape
    n_windows = max(0, rows - n + 1) * max(0, cols - n + 1)
    candidates = _candidates(probs, tissue, cfg)
    picked = _pick(candidates, n, cfg["top_k"])
    top_tumor = max((d["composition"]["tumor"] for d in candidates), default=0.0)

    px = tile_size / scale
    for i, region in enumerate(picked):
        region.update(
            rank=i + 1, is_best=i == 0,
            x=round(region["col"] * px), y=round(region["row"] * px), w=round(n * px), h=round(n * px),
            size_um=n * cfg["tile_px"] * cfg["target_mpp"],
        )
    for region in picked:
        region["reasons"] = _reasons(region, picked[0], top_tumor, cfg["reason_cutoffs"])
    return picked, _note(len(picked), n_windows, cfg)


def tumor_heatmap(probs, classes, tile_size, scale, display_size):
    """Transparent RGBA overlay at display size: each analyzed tile tinted with opacity ∝ its tumor probability."""
    tumor = probs[..., classes.index("tumor")]
    rows, cols = tumor.shape
    small = np.zeros((rows, cols, 4), np.uint8)
    small[..., :3] = HEATMAP_RGB
    small[..., 3] = np.where(np.isnan(tumor), 0, np.round(np.nan_to_num(tumor) * HEATMAP_MAX_ALPHA * 255))
    px = tile_size / scale
    overlay = Image.fromarray(small, "RGBA").resize(
        (max(1, round(cols * px)), max(1, round(rows * px))), Image.NEAREST
    )
    canvas = Image.new("RGBA", display_size, (0, 0, 0, 0))
    canvas.paste(overlay, (0, 0))
    return canvas

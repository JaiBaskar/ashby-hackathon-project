"""Tissue detection, the tile grid and the display image."""

from dataclasses import dataclass

import numpy as np
from PIL import Image

from project.ingest import IngestError

NO_TISSUE = "No tissue found in this image."


class NoTissueError(ValueError):
    pass


@dataclass
class Tile:
    row: int
    col: int
    x: int          # top-left corner in original pixels
    y: int
    size: int       # edge in original pixels
    tissue: float   # fraction of the tile that is tissue


@dataclass
class TileGrid:
    tile_size: int              # tile edge in original pixels
    tissue: np.ndarray          # tissue fraction of every tile, indexed [row, col] = [y, x] (AGENTS.md §4)
    tiles: list                 # tiles to analyze, row-major
    display: Image.Image        # downsampled image the browser shows
    scale: float                # original pixels per display pixel


def tissue_mask(rgb, min_saturation):
    """True where a pixel is stained tissue: glass is unsaturated, H&E is not."""
    arr = np.asarray(rgb, dtype=np.float32)
    hi, lo = arr.max(axis=-1), arr.min(axis=-1)
    return (hi - lo) / np.maximum(hi, 1.0) >= min_saturation


def tissue_fraction(rgb, min_saturation):
    return float(tissue_mask(rgb, min_saturation).mean())


def make_display(slide, max_px):
    """The image downsampled so its longest side is ≤ max_px, and original pixels per display pixel."""
    scale = max(1.0, max(slide.width, slide.height) / max_px)
    size = (max(1, round(slide.width / scale)), max(1, round(slide.height / scale)))
    return slide.thumbnail(size), scale


def to_original(x, y, scale):
    return x * scale, y * scale


def build_grid(slide, cfg):
    """Cut the image into tiles of tile_px at target_mpp and keep the ones that are mostly tissue."""
    tile_px = cfg["tile_px"]
    tile_size = tile_px if slide.mpp is None else max(1, round(tile_px * cfg["target_mpp"] / slide.mpp))
    rows, cols = slide.height // tile_size, slide.width // tile_size
    if rows == 0 or cols == 0:
        raise IngestError(
            f"This image is smaller than one tile ({tile_size} px at {slide.mpp} µm/px). Check the image scale."
        )

    display, scale = make_display(slide, cfg["max_display_px"])
    mask = tissue_mask(display, cfg["tissue_min_saturation"])
    tissue = np.zeros((rows, cols))
    for r in range(rows):
        y0 = min(int(r * tile_size / scale), mask.shape[0] - 1)
        y1 = max(y0 + 1, round((r + 1) * tile_size / scale))
        for c in range(cols):
            x0 = min(int(c * tile_size / scale), mask.shape[1] - 1)
            x1 = max(x0 + 1, round((c + 1) * tile_size / scale))
            tissue[r, c] = mask[y0:y1, x0:x1].mean()

    tiles = [
        Tile(r, c, c * tile_size, r * tile_size, tile_size, float(tissue[r, c]))
        for r in range(rows)
        for c in range(cols)
        if tissue[r, c] >= cfg["tissue_threshold"]
    ]
    if not tiles:
        raise NoTissueError(NO_TISSUE)
    return TileGrid(tile_size, tissue, tiles, display, scale)


def read_tiles(slide, tiles, tile_px):
    return [slide.read_region(t.x, t.y, t.size, tile_px) for t in tiles]

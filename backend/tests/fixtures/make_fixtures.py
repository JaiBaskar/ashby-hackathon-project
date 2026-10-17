"""Synthetic images for the Playwright end-to-end tests (implementation-steps.md §5, Phase 7). Never real slides.

Run from the repo root: .venv/bin/python backend/tests/fixtures/make_fixtures.py <out_dir>
Writes slide.png (flat pink tissue with purple patches on glass), blank.png (glass only) and large.png (> 10 MB,
for the upload-size check through the Next.js rewrite). Same seed (config.yaml) → same bytes.
"""

import sys
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # backend/, when run as a script

from project.config import load_config  # noqa: E402
from tests.synthetic import GLASS, PINK, PURPLE  # noqa: E402

# 20 × 14 tiles at the default scale (5120 px × 0.5 µm/px ÷ (256 px × 0.5 µm/px)): room for 15 non-overlapping
# 4 × 4 regions. Five purple patches sit at least 6 tiles apart, so the top 5 regions are one per patch.
SLIDE_SIZE = (5120, 3584)
TILE = 256
PATCHES = [(3, 4, 1.8), (3, 11, 1.6), (3, 17, 1.4), (10, 6, 1.5), (10, 14, 1.3)]  # (row, col, radius) in tiles
BLANK_SIZE = (1600, 1200)
LARGE_SIZE = (2048, 2048)


def _slide():
    w, h = SLIDE_SIZE
    yy, xx = np.mgrid[0:h, 0:w]
    arr = np.empty((h, w, 3), np.float32)
    arr[:] = GLASS
    # A rounded rectangle of tissue with a margin of glass, so the edges are not eligible regions.
    tissue = (np.abs((xx - w / 2) / (0.48 * w)) ** 10 + np.abs((yy - h / 2) / (0.47 * h)) ** 10) <= 1
    arr[tissue] = PINK
    # Purple tumor-like patches of different sizes, so the regions rank differently.
    for row, col, r in PATCHES:
        disc = (xx - col * TILE) ** 2 + (yy - row * TILE) ** 2 <= (r * TILE) ** 2
        arr[disc & tissue] = PURPLE
    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))


def _blank():
    return Image.new("RGB", BLANK_SIZE, GLASS)


def _large(seed):
    # Pink tissue with heavy noise: incompressible, so the PNG is over Next's default 10 MB body limit.
    w, h = LARGE_SIZE
    arr = np.array(PINK, np.float32) + np.random.default_rng(seed).normal(0, 60.0, (h, w, 3))
    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))


def make_fixtures(out_dir):
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    seed = load_config()["seed"]
    paths = {"slide": out / "slide.png", "blank": out / "blank.png", "large": out / "large.png"}
    _slide().save(paths["slide"])
    _blank().save(paths["blank"])
    _large(seed).save(paths["large"])
    return {**paths, "slide_size": SLIDE_SIZE}


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    for key, value in make_fixtures(sys.argv[1]).items():
        print(key, value)

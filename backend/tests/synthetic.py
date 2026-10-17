"""Synthetic H&E-like images for tests. Never real slides (AGENTS.md §6, §7)."""

import numpy as np
import tifffile
from PIL import Image

from project.config import load_config

SEED = load_config()["seed"]
PINK = (232, 180, 200)    # eosin
PURPLE = (107, 76, 154)   # hematoxylin
GLASS = (246, 246, 246)   # blank slide


def solid(color, size=(256, 256), noise=4.0):
    w, h = size
    rng = np.random.default_rng(SEED)
    arr = np.array(color, np.float32) + rng.normal(0, noise, (h, w, 3))
    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))


def he_slide(width, height):
    """White glass with a pink tissue ellipse and purple, tumor-like patches."""
    rng = np.random.default_rng(SEED)
    yy, xx = np.mgrid[0:height, 0:width]
    arr = np.empty((height, width, 3), np.float32)
    arr[:] = GLASS
    tissue = ((xx - width / 2) / (0.45 * width)) ** 2 + ((yy - height / 2) / (0.42 * height)) ** 2 <= 1
    arr[tissue] = PINK
    for cx, cy, r in [(0.35, 0.45, 0.10), (0.62, 0.55, 0.12), (0.5, 0.28, 0.07)]:
        disc = (xx - cx * width) ** 2 + (yy - cy * height) ** 2 <= (r * min(width, height)) ** 2
        arr[disc & tissue] = PURPLE
    arr += rng.normal(0, 4.0, arr.shape)
    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))


def save_tiled_tiff(image, path, mpp=None):
    """Write a tiled TIFF that OpenSlide opens as generic-tiff; mpp goes in the resolution tags."""
    extra = {}
    if mpp:
        extra = {"resolution": (1e4 / mpp, 1e4 / mpp), "resolutionunit": "CENTIMETER"}
    tifffile.imwrite(path, np.asarray(image), tile=(256, 256), photometric="rgb", compression="zlib", **extra)

"""Labeled tiles from public datasets, for checking the zero-shot model (not used by the app).

BCSS (Amgad et al. 2019, CC0): TCGA breast cancer regions at 0.25 µm/px, one RGB and one mask PNG per
region, mask codes as in PathologyDataScience/BCSS meta/gtruth_codes.tsv.
"""

from dataclasses import dataclass

import numpy as np
from PIL import Image

TUMOR = 1
# Dropped on both sides: outside_roi (0), exclude (7), undetermined (15), angioinvasion (19) and
# dcis (20), which is in-situ cancer and so neither clearly tumor nor clearly not.
BCSS_EXCLUDED = {0, 7, 15, 19, 20}


@dataclass
class LabeledTile:
    image: Image.Image
    code: int       # BCSS mask code of the whole tile
    roi: str        # file stem of the region it came from
    x: int          # top-left corner in region pixels
    y: int


def bcss_tiles(root, n, seed, src_px=512, out_px=256, min_purity=0.9):
    """A seeded sample of up to n tiles where one mask code covers at least min_purity of the tile.

    Tiles are non-overlapping src_px crops, resized to out_px (512 px at 0.25 µm/px → 256 px at 0.5,
    the app's target_mpp). Tiles touching outside_roi or dominated by an excluded code are dropped.
    """
    Image.MAX_IMAGE_PIXELS = None  # BCSS regions run to ~10^8 pixels, past Pillow's default; trusted files
    images = sorted((root / "rgbs_colorNormalized").glob("*.png"))
    candidates = []
    for image_path in images:
        mask_path = root / "masks" / image_path.name
        if not mask_path.exists():
            raise FileNotFoundError(f"no mask for {image_path.stem} at {mask_path}")
        mask = np.asarray(Image.open(mask_path))
        with Image.open(image_path) as img:
            if img.size != (mask.shape[1], mask.shape[0]):
                raise ValueError(f"{image_path.stem}: image is {img.size}, mask is {mask.shape[::-1]}")
        for y in range(0, mask.shape[0] - src_px + 1, src_px):
            for x in range(0, mask.shape[1] - src_px + 1, src_px):
                block = mask[y:y + src_px, x:x + src_px]
                if (block == 0).any():
                    continue
                codes, counts = np.unique(block, return_counts=True)
                code = int(codes[counts.argmax()])
                if counts.max() >= min_purity * block.size and code not in BCSS_EXCLUDED:
                    candidates.append((image_path, x, y, code))

    rng = np.random.default_rng(seed)
    picked = sorted(rng.choice(len(candidates), size=min(n, len(candidates)), replace=False))
    tiles, open_path, img = [], None, None
    for i in picked:  # candidates are grouped by region, so each image opens once
        image_path, x, y, code = candidates[i]
        if image_path != open_path:
            img, open_path = Image.open(image_path).convert("RGB"), image_path
        crop = img.crop((x, y, x + src_px, y + src_px)).resize((out_px, out_px), Image.Resampling.LANCZOS)
        tiles.append(LabeledTile(crop, code, image_path.stem, x, y))
    return tiles

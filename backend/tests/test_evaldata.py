import numpy as np
import pytest
from PIL import Image

from project.evaldata import TUMOR, bcss_tiles

B = 16  # src_px in these tests: one block = one candidate tile


def write_roi(root, name, codes, colors=None, image_size=None):
    """A BCSS-style ROI: codes is a grid of per-block mask values (a 2-tuple splits a block left/right)."""
    rows, cols = len(codes), len(codes[0])
    mask = np.zeros((rows * B, cols * B), np.uint8)
    rgb = np.zeros((rows * B, cols * B, 3), np.uint8)
    for r in range(rows):
        for c in range(cols):
            code = codes[r][c]
            block = mask[r * B:(r + 1) * B, c * B:(c + 1) * B]
            if isinstance(code, tuple):
                block[:, :B // 2], block[:, B // 2:] = code
            else:
                block[:] = code
            rgb[r * B:(r + 1) * B, c * B:(c + 1) * B] = (colors or {}).get((r, c), (200, 150, 180))
    (root / "masks").mkdir(exist_ok=True)
    (root / "rgbs_colorNormalized").mkdir(exist_ok=True)
    Image.fromarray(mask).save(root / "masks" / f"{name}.png")
    img = Image.fromarray(rgb)
    if image_size:
        img = img.resize(image_size)
    img.save(root / "rgbs_colorNormalized" / f"{name}.png")


def test_pure_blocks_kept_mixed_outside_and_excluded_dropped(tmp_path):
    write_roi(tmp_path, "roi", [
        [1, 2, (1, 2)],     # tumor, stroma, half/half
        [9, (0, 1), 20],    # fat, partly outside the ROI, DCIS (excluded)
    ])
    tiles = bcss_tiles(tmp_path, n=100, seed=0, src_px=B, out_px=8)
    assert sorted(t.code for t in tiles) == [1, 2, 9]
    assert all(t.roi == "roi" for t in tiles)


def test_tiles_are_resized_crops_of_the_right_place(tmp_path):
    write_roi(tmp_path, "roi", [[2, 1], [2, 2]], colors={(0, 1): (90, 60, 150)})
    tiles = bcss_tiles(tmp_path, n=100, seed=0, src_px=B, out_px=8)
    tumor = [t for t in tiles if t.code == TUMOR]
    assert len(tumor) == 1
    assert (tumor[0].x, tumor[0].y) == (B, 0)
    assert tumor[0].image.size == (8, 8)
    np.testing.assert_allclose(np.asarray(tumor[0].image).reshape(-1, 3).mean(axis=0), (90, 60, 150), atol=1)
    for t in tiles:
        assert 0 <= t.x and t.x + B <= 2 * B and 0 <= t.y and t.y + B <= 2 * B


def test_partial_edge_blocks_are_skipped(tmp_path):
    write_roi(tmp_path, "roi", [[1, 1]])
    mask = Image.open(tmp_path / "masks" / "roi.png")
    Image.fromarray(np.pad(np.asarray(mask), ((0, 5), (0, 5)), constant_values=1)).save(tmp_path / "masks" / "roi.png")
    img = Image.open(tmp_path / "rgbs_colorNormalized" / "roi.png").convert("RGB")
    Image.fromarray(np.pad(np.asarray(img), ((0, 5), (0, 5), (0, 0)))).save(tmp_path / "rgbs_colorNormalized" / "roi.png")
    tiles = bcss_tiles(tmp_path, n=100, seed=0, src_px=B, out_px=8)
    assert len(tiles) == 2


def test_sample_is_seeded_and_capped(tmp_path):
    write_roi(tmp_path, "a", [[1, 2, 1, 2]] * 3)
    write_roi(tmp_path, "b", [[2, 1, 9, 1]] * 3)
    first = bcss_tiles(tmp_path, n=10, seed=7, src_px=B, out_px=8)
    second = bcss_tiles(tmp_path, n=10, seed=7, src_px=B, out_px=8)
    other = bcss_tiles(tmp_path, n=10, seed=8, src_px=B, out_px=8)
    key = lambda tiles: [(t.roi, t.x, t.y) for t in tiles]
    assert len(first) == 10
    assert key(first) == key(second)
    assert key(first) != key(other)
    assert len(bcss_tiles(tmp_path, n=1000, seed=7, src_px=B, out_px=8)) == 24


def test_image_and_mask_size_mismatch_raises(tmp_path):
    write_roi(tmp_path, "roi", [[1, 2]], image_size=(3 * B, B))
    with pytest.raises(ValueError, match="roi"):
        bcss_tiles(tmp_path, n=10, seed=0, src_px=B, out_px=8)


def test_missing_mask_raises(tmp_path):
    write_roi(tmp_path, "roi", [[1, 2]])
    (tmp_path / "masks" / "roi.png").unlink()
    with pytest.raises(FileNotFoundError, match="roi"):
        bcss_tiles(tmp_path, n=10, seed=0, src_px=B, out_px=8)

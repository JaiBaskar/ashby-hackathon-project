import numpy as np
import pytest
from PIL import Image

from project.config import load_config
from project.ingest import IngestError, open_slide
from project.tiling import (
    NO_TISSUE, NoTissueError, Tile, build_grid, cap_tiles, make_display, read_tiles, tissue_fraction, to_original,
)
from tests.synthetic import GLASS, PINK, PURPLE, he_slide, save_tiled_tiff, solid


@pytest.fixture
def cfg():
    return load_config()


def write(image, path):
    if path.suffix in (".tiff", ".svs"):
        save_tiled_tiff(image, path, mpp=0.25)
    else:
        image.save(path)
    return path


def open_cfg(path, cfg, user_mpp=None):
    return open_slide(path, user_mpp=user_mpp, default_mpp=cfg["default_mpp"])


# Loading files

@pytest.mark.parametrize("ext", [".png", ".jpg", ".jpeg", ".tif", ".tiff", ".svs"])
def test_supported_files_load(tmp_path, cfg, ext):
    path = write(he_slide(600, 400), tmp_path / f"slide{ext}")
    slide = open_cfg(path, cfg)
    assert (slide.width, slide.height) == (600, 400)
    region = slide.read_region(100, 50, 200, 64)
    assert region.mode == "RGB" and region.size == (64, 64)


@pytest.mark.parametrize("name", ["slide.gif", "slide.bmp", "notes.txt", "slide"])
def test_unsupported_files_are_rejected_with_a_message(tmp_path, cfg, name):
    path = tmp_path / name
    path.write_bytes(b"not an image")
    with pytest.raises(IngestError, match="Unsupported file type.*PNG, JPEG, TIFF or SVS"):
        open_cfg(path, cfg)


@pytest.mark.parametrize("ext", [".png", ".jpg", ".tif", ".tiff", ".svs"])
def test_corrupted_files_are_rejected_with_a_message(tmp_path, cfg, ext):
    path = tmp_path / f"broken{ext}"
    path.write_bytes(np.random.default_rng(0).bytes(5000))
    with pytest.raises(IngestError, match="Could not read this file"):
        open_cfg(path, cfg)


def test_truncated_jpeg_is_rejected(tmp_path, cfg):
    good = write(he_slide(600, 400), tmp_path / "good.jpg")
    bad = tmp_path / "bad.jpg"
    bad.write_bytes(good.read_bytes()[: good.stat().st_size // 2])
    with pytest.raises(IngestError, match="Could not read this file"):
        open_cfg(bad, cfg)


@pytest.mark.parametrize("mpp", ["abc", "0", "-1"])
def test_bad_user_scale_is_rejected(tmp_path, cfg, mpp):
    path = write(he_slide(600, 400), tmp_path / "slide.png")
    with pytest.raises(IngestError, match="positive number"):
        open_cfg(path, cfg, user_mpp=mpp)


# Tissue detection

def test_white_tile_has_almost_no_tissue(cfg):
    assert tissue_fraction(solid(GLASS), cfg["tissue_min_saturation"]) < 0.05
    assert tissue_fraction(solid((255, 255, 255)), cfg["tissue_min_saturation"]) < 0.05


def test_he_tiles_are_tissue(cfg):
    assert tissue_fraction(solid(PINK), cfg["tissue_min_saturation"]) > 0.8
    assert tissue_fraction(solid(PURPLE), cfg["tissue_min_saturation"]) > 0.8


def test_white_image_has_no_tissue(tmp_path, cfg):
    path = write(solid(GLASS, size=(1200, 900)), tmp_path / "blank.png")
    with pytest.raises(NoTissueError) as err:
        build_grid(open_cfg(path, cfg), cfg)
    assert str(err.value) == NO_TISSUE == "No tissue found in this image."


def test_only_tissue_tiles_are_kept(tmp_path, cfg):
    arr = np.full((512, 1024, 3), GLASS, np.uint8)
    arr[:, 512:] = PINK  # right half is tissue
    path = write(Image.fromarray(arr), tmp_path / "half.png")
    grid = build_grid(open_cfg(path, cfg), cfg)
    assert grid.tissue.shape == (2, 4)  # [rows, cols] = [y, x]
    assert (grid.tissue[:, :2] < 0.05).all() and (grid.tissue[:, 2:] > 0.95).all()
    assert sorted((t.row, t.col) for t in grid.tiles) == [(0, 2), (0, 3), (1, 2), (1, 3)]


# Tile grid

def test_every_tile_lies_inside_the_image(tmp_path, cfg):
    path = write(solid(PINK, size=(1000, 700)), tmp_path / "pink.png")
    slide = open_cfg(path, cfg)
    grid = build_grid(slide, cfg)
    assert len(grid.tiles) == (1000 // 256) * (700 // 256)
    for t in grid.tiles:
        assert t.x >= 0 and t.y >= 0
        assert t.x + t.size <= slide.width and t.y + t.size <= slide.height


def test_scan_with_known_mpp_is_tiled_at_target_mpp(tmp_path, cfg):
    path = write(he_slide(1600, 1200), tmp_path / "scan.svs")  # 0.25 µm/px in the TIFF tags
    slide = open_cfg(path, cfg, user_mpp="1.0")  # the scan's own scale wins over a typed one
    assert slide.mpp == pytest.approx(0.25) and slide.mpp_estimated is False
    grid = build_grid(slide, cfg)
    assert grid.tile_size == round(cfg["tile_px"] * cfg["target_mpp"] / 0.25)


def test_photo_uses_the_typed_mpp_and_marks_it_estimated(tmp_path, cfg):
    path = write(he_slide(1600, 1200), tmp_path / "photo.jpg")
    slide = open_cfg(path, cfg, user_mpp="1.0")
    assert slide.mpp == 1.0 and slide.mpp_estimated is True
    assert build_grid(slide, cfg).tile_size == round(cfg["tile_px"] * cfg["target_mpp"] / 1.0)


def test_photo_without_a_scale_uses_the_default_mpp(tmp_path, cfg):
    for path in (write(he_slide(1600, 1200), tmp_path / "photo.png"), tmp_path / "plain.tiff"):
        if path.suffix == ".tiff":
            save_tiled_tiff(he_slide(1600, 1200), path)  # tiled TIFF with no resolution tags
        slide = open_cfg(path, cfg)
        assert slide.mpp == cfg["default_mpp"] and slide.mpp_estimated is True


def test_tiles_are_read_at_tile_px(tmp_path, cfg):
    path = write(he_slide(1600, 1200), tmp_path / "scan.svs")
    slide = open_cfg(path, cfg)
    grid = build_grid(slide, cfg)
    tiles = read_tiles(slide, grid.tiles[:3], cfg["tile_px"])
    assert [t.size for t in tiles] == [(cfg["tile_px"], cfg["tile_px"])] * 3
    assert all(t.mode == "RGB" for t in tiles)


# Display image

def test_display_image_fits_max_display_px_and_scale_maps_back(tmp_path, cfg):
    arr = np.full((1200, 3000, 3), PINK, np.uint8)
    arr[600:900, 1500:1800] = PURPLE  # a marker in original pixels
    slide = open_cfg(write(Image.fromarray(arr), tmp_path / "wide.png"), cfg)
    display, scale = make_display(slide, 1000)
    assert max(display.size) <= 1000 and display.size == (1000, 400)
    assert scale == pytest.approx(3.0)
    assert to_original(100, 40, scale) == pytest.approx((300, 120))
    # A display pixel inside the marker maps back to an original pixel inside the marker.
    dx, dy = 550, 250
    ox, oy = to_original(dx, dy, scale)
    assert 1500 <= ox < 1800 and 600 <= oy < 900
    assert display.getpixel((dx, dy)) == pytest.approx(PURPLE, abs=12)


def test_small_images_are_not_upscaled(tmp_path, cfg):
    slide = open_cfg(write(solid(PINK, size=(500, 300)), tmp_path / "small.png"), cfg)
    display, scale = make_display(slide, cfg["max_display_px"])
    assert display.size == (500, 300) and scale == 1.0


def test_scan_display_respects_max_display_px(tmp_path, cfg):
    slide = open_cfg(write(he_slide(2400, 1000), tmp_path / "scan.svs"), cfg)
    display, scale = make_display(slide, 800)
    assert display.size == (800, round(1000 / 3)) and scale == pytest.approx(3.0)


# Tile cap (Phase 2)

def make_tiles(rows, cols, size=256):
    return [Tile(r, c, c * size, r * size, size, 1.0) for r in range(rows) for c in range(cols)]


def test_tile_cap_keeps_exactly_max_tiles_spread_evenly():
    tiles = make_tiles(10, 10)
    kept, capped = cap_tiles(tiles, 10)
    assert capped is True and len(kept) == 10
    assert len({(t.row, t.col) for t in kept}) == 10
    assert min(t.row for t in kept) == 0 and max(t.row for t in kept) == 9  # covers the whole tissue
    gaps = np.diff([tiles.index(t) for t in kept])
    assert gaps.max() - gaps.min() <= 1  # evenly spaced


def test_tile_cap_not_hit_keeps_everything():
    tiles = make_tiles(2, 3)
    kept, capped = cap_tiles(tiles, 10)
    assert kept == tiles and capped is False


def test_build_grid_records_when_the_cap_is_hit(tmp_path, cfg):
    path = write(solid(PINK, size=(1024, 1024)), tmp_path / "pink.png")  # 4 x 4 tissue tiles
    grid = build_grid(open_cfg(path, cfg), {**cfg, "max_tiles": 5})
    assert len(grid.tiles) == 5 and grid.capped is True and grid.n_tissue_tiles == 16
    grid = build_grid(open_cfg(path, cfg), cfg)
    assert len(grid.tiles) == 16 and grid.capped is False and grid.n_tissue_tiles == 16

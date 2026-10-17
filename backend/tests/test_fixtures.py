"""The Phase 7 end-to-end fixtures do what the Playwright flows need (implementation-steps.md §5, Phase 7)."""

import pytest

from project.config import load_config
from project.ingest import open_slide
from project.model import FakeBackend
from project.regions import rank_regions, score_grid
from project.tiling import NO_TISSUE, NoTissueError, build_grid, read_tiles
from tests.fixtures.make_fixtures import make_fixtures


@pytest.fixture(scope="module")
def fixtures(tmp_path_factory):
    return make_fixtures(tmp_path_factory.mktemp("e2e"))


def analyze(path, cfg):
    slide = open_slide(path, None, cfg["default_mpp"])
    grid = build_grid(slide, cfg)
    probs = FakeBackend(cfg).predict(read_tiles(slide, grid.tiles, cfg["tile_px"]))
    return grid, rank_regions(score_grid(grid.tiles, probs, grid.tissue.shape), grid.tissue, cfg, grid.tile_size, grid.scale)


def test_slide_fixture_fits_five_regions(fixtures):
    cfg = load_config()
    # tiles per side = image px × mpp ÷ (tile_px × target_mpp): room for 5 non-overlapping N×N blocks
    rows, cols = (px * cfg["default_mpp"] / (cfg["tile_px"] * cfg["target_mpp"]) for px in fixtures["slide_size"][::-1])
    n = cfg["region_tiles"]
    assert (rows // n) * (cols // n) >= cfg["top_k"]

    _, (regions, note) = analyze(fixtures["slide"], cfg)
    assert len(regions) == cfg["top_k"]
    assert note is None


def test_blank_fixture_has_no_tissue(fixtures):
    with pytest.raises(NoTissueError, match=NO_TISSUE):
        analyze(fixtures["blank"], load_config())


def test_large_fixture_is_over_ten_mb_and_under_the_limit(fixtures):
    size = fixtures["large"].stat().st_size
    assert size > 10 * 1024 * 1024
    assert size < load_config()["max_upload_mb"] * 1024 * 1024


def test_fixtures_are_deterministic(tmp_path, fixtures):
    again = make_fixtures(tmp_path)
    for key in ("slide", "blank"):
        assert again[key].read_bytes() == fixtures[key].read_bytes()

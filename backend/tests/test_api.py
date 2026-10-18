"""Phase 4: the FastAPI service, with the fake model and synthetic images only."""

import io
import time

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from project.api import STEPS, Job, Result, create_app
from project.config import load_config
from project.model import FakeBackend, ModelConfigError
from project.tiling import NO_TISSUE
from tests.synthetic import GLASS, he_slide, solid


@pytest.fixture
def cfg(tmp_path):
    cfg = load_config()
    cfg["paths"] = {**cfg["paths"], "uploads": str(tmp_path / "uploads")}
    return cfg


@pytest.fixture
def client(cfg):
    return TestClient(create_app(cfg))


def png_bytes(image):
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    return buf.getvalue()


def upload(client, data, name="slide.png", mpp=None):
    form = {"mpp": str(mpp)} if mpp is not None else {}
    return client.post("/api/jobs", files={"file": (name, data, "application/octet-stream")}, data=form)


def poll(client, job_id, timeout=30):
    seen = []
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        body = client.get(f"/api/jobs/{job_id}").json()
        seen.append(body)
        if body["status"] in ("done", "error"):
            return body, seen
        time.sleep(0.02)
    raise AssertionError(f"job {job_id} did not finish in {timeout}s; last: {seen[-1]}")


def test_upload_runs_to_done_and_result_validates(client):
    r = upload(client, png_bytes(he_slide(2048, 1536)))
    assert r.status_code == 200
    job_id = r.json()["job_id"]
    body, _ = poll(client, job_id)
    assert body["status"] == "done", body
    assert body["progress"] == 1.0
    result = Result.model_validate(body["result"])
    assert result.regions and result.regions[0].is_best
    assert result.image.url == f"/api/jobs/{job_id}/display.png"
    assert result.heatmap_url == f"/api/jobs/{job_id}/heatmap.png"
    assert 0.0 <= result.heatmap_range.low < result.heatmap_range.high <= 1.0
    assert result.image.mpp_estimated is True
    assert sum(result.slide_composition.values()) == pytest.approx(1.0)
    for region in result.regions:
        assert 0 <= region.x and region.x + region.w <= result.image.width
        assert 0 <= region.y and region.y + region.h <= result.image.height


def test_display_and_heatmap_pngs_are_served_at_display_size(client):
    job_id = upload(client, png_bytes(he_slide(2048, 1536))).json()["job_id"]
    body, _ = poll(client, job_id)
    w, h = body["result"]["image"]["width"], body["result"]["image"]["height"]
    for name, mode in (("display.png", "RGB"), ("heatmap.png", "RGBA")):
        r = client.get(f"/api/jobs/{job_id}/{name}")
        assert r.status_code == 200 and r.headers["content-type"] == "image/png"
        img = Image.open(io.BytesIO(r.content))
        assert img.size == (w, h) and img.mode == mode


def test_typed_mpp_reaches_the_result(client):
    job_id = upload(client, png_bytes(he_slide(1024, 1024)), mpp=0.25).json()["job_id"]
    body, _ = poll(client, job_id)
    assert body["result"]["image"]["mpp"] == 0.25


def test_step_and_progress_never_go_backwards(client, cfg):
    app = create_app(cfg)
    client = TestClient(app)
    job_id = upload(client, png_bytes(he_slide(2048, 1536))).json()["job_id"]
    _, seen = poll(client, job_id)
    history = app.state.jobs[job_id].history  # every (step, progress) the worker recorded
    for trail in (history, [(s["step"], s["progress"]) for s in seen]):
        steps = [STEPS.index(s) for s, _ in trail if s is not None]
        progress = [p for _, p in trail]
        assert steps == sorted(steps)
        assert progress == sorted(progress)
    assert [s for s, _ in history if s is not None][-1] == "ranking"
    assert {s for s, _ in history if s is not None} == set(STEPS)


@pytest.mark.parametrize("name", ["notes.txt", "slide.gif", "slide"])
def test_bad_file_type_is_400(client, name):
    r = upload(client, b"hello", name=name)
    assert r.status_code == 400
    assert "Unsupported file type" in r.json()["detail"]


def test_corrupt_file_is_400(client):
    r = upload(client, b"\x89PNG\r\n\x1a\nnot really a png", name="slide.png")
    assert r.status_code == 400
    assert "corrupted" in r.json()["detail"]


def test_bad_mpp_is_400(client):
    r = upload(client, png_bytes(he_slide(512, 512)), mpp=-1)
    assert r.status_code == 400


def test_too_large_is_413(cfg):
    cfg["max_upload_mb"] = 1
    client = TestClient(create_app(cfg))
    r = upload(client, b"\0" * (1024 * 1024 + 1))
    assert r.status_code == 413
    assert "1 MB" in r.json()["detail"]


def test_unknown_job_is_404(client):
    assert client.get("/api/jobs/nope").status_code == 404
    assert client.get("/api/jobs/nope/display.png").status_code == 404
    assert client.get("/api/jobs/nope/heatmap.png").status_code == 404


def test_blank_image_ends_in_error(client):
    job_id = upload(client, png_bytes(solid(GLASS, size=(1024, 1024)))).json()["job_id"]
    body, _ = poll(client, job_id)
    assert body["status"] == "error"
    assert body["error"] == NO_TISSUE
    assert body.get("result") is None


def test_model_matches_config(client, cfg):
    job_id = upload(client, png_bytes(he_slide(1024, 1024))).json()["job_id"]
    first = client.get(f"/api/jobs/{job_id}").json()
    assert first["model"] == cfg["model"] == "fake"
    body, _ = poll(client, job_id)
    assert body["result"]["model"] == "fake"


def test_app_refuses_to_start_without_conch_token(cfg, monkeypatch):
    from project import model as model_module

    monkeypatch.delenv("HF_TOKEN", raising=False)
    monkeypatch.setattr(model_module, "cached_hf_token", lambda: None)
    cfg["model"] = "conch"
    with pytest.raises(ModelConfigError, match="no Hugging Face token"):
        create_app(cfg)


# --- box size: re-rank a finished job without running the model again --------------------------

def test_result_reports_the_box_size_and_the_sizes_on_offer(client, cfg):
    job_id = upload(client, png_bytes(he_slide(2048, 1536))).json()["job_id"]
    result = poll(client, job_id)[0]["result"]
    assert result["box_um"] == cfg["region_tiles"] * cfg["tile_px"] * cfg["target_mpp"]
    assert result["box_sizes_um"] == cfg["box_sizes_um"]
    assert result["regions_url"] == f"/api/jobs/{job_id}/regions"


def test_regions_at_another_box_size_reuse_the_tile_scores(cfg, monkeypatch):
    calls = []
    original = FakeBackend.predict
    monkeypatch.setattr(FakeBackend, "predict", lambda self, tiles: calls.append(len(tiles)) or original(self, tiles))
    client = TestClient(create_app(cfg))
    job_id = upload(client, png_bytes(he_slide(4096, 3072))).json()["job_id"]
    result = poll(client, job_id)[0]["result"]
    n_calls = len(calls)

    default = client.get(f"/api/jobs/{job_id}/regions", params={"box_um": result["box_um"]})
    assert default.status_code == 200
    assert default.json()["regions"] == result["regions"]

    big = client.get(f"/api/jobs/{job_id}/regions", params={"box_um": 1024})
    assert big.status_code == 200
    body = big.json()
    assert body["box_um"] == 1024
    assert body["regions"], body
    first = result["regions"][0]
    for region in body["regions"]:
        assert (region["w"], region["h"]) == (2 * first["w"], 2 * first["h"])
        assert region["size_um"] == pytest.approx(1024)
        assert sum(region["composition"].values()) == pytest.approx(1.0)
    assert len(calls) == n_calls  # the model was not run again


def test_a_box_too_big_for_the_image_comes_back_empty_with_a_note(client):
    job_id = upload(client, png_bytes(he_slide(2048, 1536))).json()["job_id"]  # 8 × 6 tiles
    poll(client, job_id)
    body = client.get(f"/api/jobs/{job_id}/regions", params={"box_um": 2048}).json()  # 16 × 16 tiles
    assert body["regions"] == []
    assert "smaller than one region" in body["note"]


@pytest.mark.parametrize("box_um", ["1000", "0", "-512", "big"])
def test_box_size_not_on_offer_is_400_or_422(client, box_um):
    job_id = upload(client, png_bytes(he_slide(2048, 1536))).json()["job_id"]
    poll(client, job_id)
    r = client.get(f"/api/jobs/{job_id}/regions", params={"box_um": box_um})
    assert r.status_code in (400, 422)
    if r.status_code == 400:
        assert "512" in r.json()["detail"]  # names the sizes on offer


def test_regions_of_an_unknown_job_is_404(client):
    assert client.get("/api/jobs/nope/regions", params={"box_um": 512}).status_code == 404


def test_regions_before_the_job_is_done_is_409(cfg):
    app = create_app(cfg)
    client = TestClient(app)
    job = Job("fake")
    app.state.jobs["running"] = job
    r = client.get("/api/jobs/running/regions", params={"box_um": 512})
    assert r.status_code == 409
    assert "still" in r.json()["detail"]

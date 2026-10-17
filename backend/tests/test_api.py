"""Phase 4: the FastAPI service, with the fake model and synthetic images only."""

import io
import time
from datetime import datetime

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from project.api import STEPS, Job, Result, create_app
from project.config import load_config
from project.model import FakeBackend, ModelConfigError
from project.store import MemoryStore
from project.tiling import NO_TISSUE
from tests.synthetic import GLASS, he_slide, solid


@pytest.fixture(autouse=True)
def no_database(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)  # the fast suite never touches a real database


@pytest.fixture
def cfg(tmp_path):
    cfg = load_config()
    cfg["model"] = "fake"  # the fast suite never loads CONCH, whatever config.yaml says (AGENTS.md §7)
    cfg["paths"] = {**cfg["paths"], "uploads": str(tmp_path / "uploads"), "jobs": str(tmp_path / "jobs")}
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


# --- request history (store) ----------------------------------------------------------------------

def test_jobs_list_is_newest_first_with_created_at_and_cancer_type(client):
    first = upload(client, png_bytes(he_slide(1024, 1024))).json()["job_id"]
    poll(client, first)
    second = upload(client, png_bytes(he_slide(1024, 1024))).json()["job_id"]
    poll(client, second)
    body = client.get("/api/jobs").json()
    assert body["store"] == "memory"
    assert [j["id"] for j in body["jobs"]] == [second, first]
    for j in body["jobs"]:
        assert j["status"] == "done" and j["model"] == "fake"
        assert j["cancer_type"] is None  # no classifier yet (reports/decisions.md)
        assert datetime.fromisoformat(j["created_at"]).tzinfo is not None


def test_job_status_has_created_at_and_cancer_type(client):
    job_id = upload(client, png_bytes(he_slide(1024, 1024))).json()["job_id"]
    body, _ = poll(client, job_id)
    assert datetime.fromisoformat(body["created_at"]).tzinfo is not None
    assert body["cancer_type"] is None


def test_finished_job_survives_a_restart(cfg):
    store = MemoryStore()
    before = TestClient(create_app(cfg, store=store))
    job_id = upload(before, png_bytes(he_slide(2048, 1536))).json()["job_id"]
    done, _ = poll(before, job_id)
    pngs = {n: before.get(f"/api/jobs/{job_id}/{n}").content for n in ("display.png", "heatmap.png")}

    after = TestClient(create_app(cfg, store=store))  # new process: empty memory, same store and disk
    body = after.get(f"/api/jobs/{job_id}").json()
    assert body["status"] == "done"
    assert body["result"] == done["result"]
    assert body["created_at"] == done["created_at"]
    for name, content in pngs.items():
        r = after.get(f"/api/jobs/{job_id}/{name}")
        assert r.status_code == 200 and r.content == content
    assert [j["id"] for j in after.get("/api/jobs").json()["jobs"]] == [job_id]


def test_failed_job_is_recorded(cfg):
    store = MemoryStore()
    client = TestClient(create_app(cfg, store=store))
    job_id = upload(client, png_bytes(solid(GLASS, size=(1024, 1024)))).json()["job_id"]
    poll(client, job_id)
    rec = store.get(job_id)
    assert (rec.status, rec.error) == ("error", NO_TISSUE)


def test_uploaded_filename_is_never_stored(cfg):
    store = MemoryStore()
    client = TestClient(create_app(cfg, store=store))
    job_id = upload(client, png_bytes(he_slide(1024, 1024)), name="MRN-4417-smith.png").json()["job_id"]
    poll(client, job_id)
    assert "4417" not in repr(store.get(job_id))
    assert "4417" not in client.get("/api/jobs").text
    assert "4417" not in client.get(f"/api/jobs/{job_id}").text


def test_store_failure_does_not_break_the_result(cfg):
    class BrokenStore(MemoryStore):
        def finish(self, *args, **kwargs):
            raise ConnectionError("database went away")

    client = TestClient(create_app(cfg, store=BrokenStore()))
    job_id = upload(client, png_bytes(he_slide(2048, 1536))).json()["job_id"]
    body, _ = poll(client, job_id)
    assert body["status"] == "done" and body["result"]["regions"]


@pytest.mark.parametrize("bad_id", ["..%2F..%2Fconfig", "x" * 32, "0" * 31])
def test_image_routes_reject_ids_that_are_not_job_ids(client, bad_id):
    assert client.get(f"/api/jobs/{bad_id}/display.png").status_code == 404


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


# --- free-form box: measure any rectangle on a finished job ---------------------------------------

def test_measure_any_box_on_a_finished_job(cfg, monkeypatch):
    calls = []
    original = FakeBackend.predict
    monkeypatch.setattr(FakeBackend, "predict", lambda self, tiles: calls.append(len(tiles)) or original(self, tiles))
    client = TestClient(create_app(cfg))
    job_id = upload(client, png_bytes(he_slide(4096, 3072))).json()["job_id"]
    result = poll(client, job_id)[0]["result"]
    assert result["measure_url"] == f"/api/jobs/{job_id}/measure"
    n_calls = len(calls)

    best = result["regions"][0]
    same = client.get(result["measure_url"], params={k: best[k] for k in ("x", "y", "w", "h")})
    assert same.status_code == 200, same.text
    body = same.json()
    assert body["score"] == pytest.approx(best["score"])
    assert body["composition"]["tumor"] == pytest.approx(best["composition"]["tumor"])

    odd = client.get(result["measure_url"], params={"x": 333.5, "y": 120, "w": 517, "h": 211}).json()
    assert (odd["x"], odd["y"], odd["w"], odd["h"]) == (333.5, 120, 517, 211)
    assert sum(odd["composition"].values()) == pytest.approx(1.0)
    assert odd["width_um"] / odd["height_um"] == pytest.approx(517 / 211)
    assert len(calls) == n_calls  # measured from the stored tile scores


def test_measure_refuses_an_empty_box_or_glass(client):
    job_id = upload(client, png_bytes(he_slide(2048, 1536))).json()["job_id"]
    poll(client, job_id)
    empty = client.get(f"/api/jobs/{job_id}/measure", params={"x": 10, "y": 10, "w": 0, "h": 50})
    assert empty.status_code == 400 and "box" in empty.json()["detail"]
    glass = client.get(f"/api/jobs/{job_id}/measure", params={"x": 0, "y": 0, "w": 40, "h": 40})  # corner glass
    assert glass.status_code == 400 and "no analyzed tissue" in glass.json()["detail"]


def test_measure_unknown_or_unfinished_job(cfg):
    app = create_app(cfg)
    client = TestClient(app)
    params = {"x": 0, "y": 0, "w": 100, "h": 100}
    assert client.get("/api/jobs/nope/measure", params=params).status_code == 404
    app.state.jobs["running"] = Job("fake")
    assert client.get("/api/jobs/running/measure", params=params).status_code == 409


def test_box_resize_still_works_after_a_restart(cfg):
    store = MemoryStore()
    before = TestClient(create_app(cfg, store=store))
    job_id = upload(before, png_bytes(he_slide(4096, 3072))).json()["job_id"]
    poll(before, job_id)
    expected = before.get(f"/api/jobs/{job_id}/regions", params={"box_um": 1024}).json()

    after = TestClient(create_app(cfg, store=store))  # tile scores now come from data/jobs/<id>/ranking.npz
    r = after.get(f"/api/jobs/{job_id}/regions", params={"box_um": 1024})
    assert r.status_code == 200
    assert r.json() == expected


def test_free_box_still_measures_after_a_restart(cfg):
    store = MemoryStore()
    before = TestClient(create_app(cfg, store=store))
    job_id = upload(before, png_bytes(he_slide(4096, 3072)), mpp=0.25).json()["job_id"]
    poll(before, job_id)
    params = {"x": 333.5, "y": 120, "w": 517, "h": 211}
    expected = before.get(f"/api/jobs/{job_id}/measure", params=params).json()

    after = TestClient(create_app(cfg, store=store))  # tile scores and scale come from data/jobs/<id>/ranking.npz
    r = after.get(f"/api/jobs/{job_id}/measure", params=params)
    assert r.status_code == 200
    assert r.json() == expected
    assert r.json()["width_um"] == pytest.approx(517 * 2 * 0.25)  # display is half size; the typed 0.25 µm/px kept

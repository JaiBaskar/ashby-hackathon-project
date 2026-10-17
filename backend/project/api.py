"""FastAPI service. Every route is under /api, so the Next.js rewrite passes paths through unchanged.

Run with: uvicorn --factory --app-dir backend project.api:create_app
"""

import io
import logging
import re
import threading
import uuid
from datetime import datetime
from pathlib import Path
from typing import Literal, Optional

import numpy as np
from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel

from project.config import load_config, repo_path
from project.ingest import SUPPORTED_EXTENSIONS, IngestError, open_slide
from project.model import load_backend
from project.regions import (
    box_tiles, default_box_um, rank_regions, score_grid, slide_composition, tumor_heatmap,
)
from project.store import now, open_store
from project.tiling import NoTissueError, build_grid, read_tiles

log = logging.getLogger(__name__)

STEPS = ["finding_tissue", "tiling", "analyzing", "ranking"]
CHUNK = 1024 * 1024
JOB_ID = re.compile(r"^[0-9a-f]{32}$")  # uuid4().hex; anything else never reaches the disk


# --- response models (the Result JSON in implementation-steps.md §4) ------------------------------

class ImageInfo(BaseModel):
    url: str
    width: int
    height: int
    mpp: Optional[float]
    mpp_estimated: bool


class TileInfo(BaseModel):
    count: int
    capped: bool


class Region(BaseModel):
    rank: int
    is_best: bool
    x: int
    y: int
    w: int
    h: int
    score: float
    tissue_coverage: float
    tumor_std: float
    composition: dict[str, float]
    size_um: Optional[float]
    reasons: list[str]


class Result(BaseModel):
    model: str
    image: ImageInfo
    heatmap_url: str
    regions_url: str
    box_um: float
    box_sizes_um: list[float]
    tiles: TileInfo
    slide_composition: dict[str, float]
    regions: list[Region]
    note: Optional[str]


class Regions(BaseModel):
    """The regions for one box size, from GET /api/jobs/{id}/regions?box_um=…"""
    box_um: float
    regions: list[Region]
    note: Optional[str]


class JobCreated(BaseModel):
    job_id: str


class JobStatus(BaseModel):
    status: Literal["queued", "running", "done", "error"]
    step: Optional[str]
    progress: float
    model: str
    result: Optional[Result] = None
    error: Optional[str] = None
    created_at: Optional[datetime] = None
    cancer_type: Optional[str] = None   # most likely cancer type; None until a classifier exists


class JobSummary(BaseModel):
    id: str
    created_at: datetime
    status: Literal["running", "done", "error"]
    model: str
    cancer_type: Optional[str]


class JobList(BaseModel):
    store: Literal["postgres", "memory"]
    jobs: list[JobSummary]


# --- jobs -----------------------------------------------------------------------------------------

class Job:
    def __init__(self, model):
        self.status = "queued"
        self.step = None
        self.progress = 0.0
        self.model = model
        self.result = None
        self.error = None
        self.display_png = None
        self.heatmap_png = None
        self.created_at = now()
        self.cancer_type = None
        self.ranking = None  # (tile scores, tissue, tile_size, scale), kept so a box resize skips the model
        self.history = [(None, 0.0)]
        self.lock = threading.Lock()

    def advance(self, step, progress):
        """Move forward only: step and progress never go backwards."""
        with self.lock:
            if STEPS.index(step) >= (STEPS.index(self.step) if self.step else -1) and progress >= self.progress:
                self.status, self.step, self.progress = "running", step, progress
                self.history.append((step, progress))

    def status_body(self):
        with self.lock:
            return JobStatus(status=self.status, step=self.step, progress=self.progress, model=self.model,
                             result=self.result, error=self.error, created_at=self.created_at,
                             cancer_type=self.cancer_type)


def png(image):
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    return buf.getvalue()


def record(store_call, job_id, *args):
    """Write to the store; a database problem is logged, never shown in place of the result."""
    try:
        store_call(job_id, *args)
    except Exception:
        log.exception("could not record job %s in the store", job_id)


def run_job(job, job_id, slide, path, cfg, backend, store, job_dir):
    try:
        job.advance("finding_tissue", 0.05)
        grid = build_grid(slide, cfg)
        job.display_png = png(grid.display)
        job_dir.mkdir(parents=True, exist_ok=True)
        (job_dir / "display.png").write_bytes(job.display_png)

        job.advance("tiling", 0.15)
        tiles = grid.tiles

        job.advance("analyzing", 0.2)
        batch = cfg["batch_size"]
        parts = []
        for i in range(0, len(tiles), batch):
            parts.append(backend.predict(read_tiles(slide, tiles[i:i + batch], cfg["tile_px"])))
            job.advance("analyzing", 0.2 + 0.7 * min(1.0, (i + batch) / len(tiles)))
        probs = np.concatenate(parts)

        job.advance("ranking", 0.95)
        classes = cfg["classes"]
        grid_probs = score_grid(tiles, probs, grid.tissue.shape)
        job.ranking = (grid_probs, grid.tissue, grid.tile_size, grid.scale)
        # On disk too, so a box resize still works for this job after a restart (data/, never committed).
        np.savez(job_dir / "ranking.npz", probs=grid_probs, tissue=grid.tissue, tile_size=grid.tile_size,
                 scale=grid.scale)
        regions, note = rank_regions(grid_probs, grid.tissue, cfg, grid.tile_size, grid.scale)
        job.heatmap_png = png(tumor_heatmap(grid_probs, classes, grid.tile_size, grid.scale, grid.display.size))
        (job_dir / "heatmap.png").write_bytes(job.heatmap_png)
        result = Result(
            model=backend.name,
            image=ImageInfo(url=f"/api/jobs/{job_id}/display.png", width=grid.display.width,
                            height=grid.display.height, mpp=slide.mpp, mpp_estimated=slide.mpp_estimated),
            heatmap_url=f"/api/jobs/{job_id}/heatmap.png",
            regions_url=f"/api/jobs/{job_id}/regions",
            box_um=default_box_um(cfg),
            box_sizes_um=cfg["box_sizes_um"],
            tiles=TileInfo(count=len(tiles), capped=grid.capped),
            slide_composition=slide_composition(probs, classes),
            regions=[Region(**r) for r in regions],
            note=note,
        )
        record(store.finish, job_id, result.model_dump(mode="json"), job.cancer_type)
        with job.lock:
            job.result, job.status, job.progress = result, "done", 1.0
            job.history.append((job.step, 1.0))
    except (NoTissueError, IngestError) as e:
        record(store.fail, job_id, str(e))
        with job.lock:
            job.status, job.error = "error", str(e)
    except Exception as e:
        log.exception("job %s failed", job_id)
        message = f"Analysis failed ({type(e).__name__}). Try another image."
        record(store.fail, job_id, message)
        with job.lock:
            job.status, job.error = "error", message
    finally:
        close = getattr(getattr(slide, "osr", None), "close", None)
        if close:
            close()
        path.unlink(missing_ok=True)  # uploads aren't kept after analysis


# --- app ------------------------------------------------------------------------------------------

def save_upload(file, dest, max_bytes, max_mb):
    """Stream the upload to disk, stopping with a 413 as soon as it passes max_upload_mb."""
    size = 0
    with open(dest, "wb") as out:
        while chunk := file.read(CHUNK):
            size += len(chunk)
            if size > max_bytes:
                out.close()
                dest.unlink(missing_ok=True)
                raise HTTPException(413, f"This file is larger than the {max_mb} MB limit.")
            out.write(chunk)


def create_app(cfg=None, store=None):
    cfg = cfg or load_config()
    backend = load_backend(cfg)  # Phase 2 startup check: refuses to start rather than fall back to the demo model
    store = store or open_store()  # Postgres if DATABASE_URL is set; refuses to start if it can't connect
    uploads = repo_path(cfg["paths"]["uploads"])
    uploads.mkdir(parents=True, exist_ok=True)
    jobs_dir = repo_path(cfg["paths"]["jobs"])

    app = FastAPI(title="Biopsy sampling-site finder")
    app.state.jobs = {}
    app.state.store = store
    not_found = "No analysis with this id. It may have been run on another machine or before history was kept."

    def get_status(request, job_id):
        """The live job if this process ran it, else the stored record (e.g. after a restart)."""
        job = request.app.state.jobs.get(job_id)
        if job is not None:
            return job.status_body()
        rec = store.get(job_id) if JOB_ID.match(job_id) else None
        if rec is None:
            raise HTTPException(404, not_found)
        return JobStatus(status=rec.status, step=None, progress=1.0 if rec.status == "done" else 0.0,
                         model=rec.model, result=rec.result, error=rec.error, created_at=rec.created_at,
                         cancer_type=rec.cancer_type)

    def get_ranking(request, job_id):
        """Tile scores for re-ranking: from memory if this process ran the job, else from disk."""
        job = request.app.state.jobs.get(job_id)
        if job is not None:
            with job.lock:
                return job.ranking
        path = jobs_dir / job_id / "ranking.npz"
        if not JOB_ID.match(job_id) or not path.is_file():
            return None
        with np.load(path) as f:
            return f["probs"], f["tissue"], int(f["tile_size"]), float(f["scale"])

    def get_png(request, job_id, name):
        job = request.app.state.jobs.get(job_id)
        if job is not None:
            return image_response(getattr(job, name.replace(".", "_")))
        path = jobs_dir / job_id / name
        if not JOB_ID.match(job_id) or not path.is_file():
            raise HTTPException(404, not_found)
        return image_response(path.read_bytes())

    @app.post("/api/jobs", response_model=JobCreated)
    def create_job(request: Request, file: UploadFile = File(...), mpp: Optional[str] = Form(None)):
        ext = Path(file.filename or "").suffix.lower()
        if ext not in SUPPORTED_EXTENSIONS:  # before saving anything, and naming the user's file
            raise HTTPException(
                400, f"Unsupported file type '{ext or file.filename}'. Upload a PNG, JPEG, TIFF or SVS image."
            )
        job_id = uuid.uuid4().hex
        path = uploads / f"{job_id}{ext}"
        max_mb = cfg["max_upload_mb"]
        save_upload(file.file, path, max_mb * 1024 * 1024, max_mb)
        try:
            slide = open_slide(path, mpp, cfg["default_mpp"])
        except IngestError as e:
            path.unlink(missing_ok=True)
            raise HTTPException(400, str(e)) from e
        job = Job(backend.name)
        request.app.state.jobs[job_id] = job
        record(store.create, job_id, backend.name, cfg["prompt_set"], job.created_at)
        threading.Thread(target=run_job, args=(job, job_id, slide, path, cfg, backend, store, jobs_dir / job_id),
                         daemon=True).start()
        return JobCreated(job_id=job_id)

    @app.get("/api/jobs", response_model=JobList)
    def list_jobs():
        return JobList(store=store.name, jobs=[
            JobSummary(id=r.id, created_at=r.created_at, status=r.status, model=r.model, cancer_type=r.cancer_type)
            for r in store.list()
        ])

    @app.get("/api/jobs/{job_id}", response_model=JobStatus)
    def job_status(request: Request, job_id: str):
        return get_status(request, job_id)

    @app.get("/api/jobs/{job_id}/regions", response_model=Regions)
    def regions_at_size(request: Request, job_id: str, box_um: float):
        """Re-rank a finished job's stored tile scores with another box size. The model isn't run again."""
        status = get_status(request, job_id)  # 404 for an unknown id
        try:
            n = box_tiles(cfg, box_um)
        except ValueError as e:
            raise HTTPException(400, str(e)) from e
        ranking = get_ranking(request, job_id) if status.status == "done" else None
        if ranking is None:
            raise HTTPException(409, "This analysis is still running, or it failed. Box size can change once it's done.")
        probs, tissue, tile_size, scale = ranking
        regions, note = rank_regions(probs, tissue, {**cfg, "region_tiles": n}, tile_size, scale)
        return Regions(box_um=box_um, regions=[Region(**r) for r in regions], note=note)

    @app.get("/api/jobs/{job_id}/display.png")
    def display_png(request: Request, job_id: str):
        return get_png(request, job_id, "display.png")

    @app.get("/api/jobs/{job_id}/heatmap.png")
    def heatmap_png(request: Request, job_id: str):
        return get_png(request, job_id, "heatmap.png")

    return app


def image_response(data):
    if data is None:
        raise HTTPException(404, "This image isn't ready yet.")
    return Response(data, media_type="image/png", headers={"Cache-Control": "private, max-age=3600"})

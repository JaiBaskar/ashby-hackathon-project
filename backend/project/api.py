"""FastAPI service. Every route is under /api, so the Next.js rewrite passes paths through unchanged.

Run with: uvicorn --factory --app-dir backend project.api:create_app
"""

import io
import logging
import threading
import uuid
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
from project.tiling import NoTissueError, build_grid, read_tiles

log = logging.getLogger(__name__)

STEPS = ["finding_tissue", "tiling", "analyzing", "ranking"]
CHUNK = 1024 * 1024


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
                             result=self.result, error=self.error)


def png(image):
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    return buf.getvalue()


def run_job(job, job_id, slide, path, cfg, backend):
    try:
        job.advance("finding_tissue", 0.05)
        grid = build_grid(slide, cfg)
        job.display_png = png(grid.display)

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
        regions, note = rank_regions(grid_probs, grid.tissue, cfg, grid.tile_size, grid.scale)
        job.heatmap_png = png(tumor_heatmap(grid_probs, classes, grid.tile_size, grid.scale, grid.display.size))
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
        with job.lock:
            job.result, job.status, job.progress = result, "done", 1.0
            job.history.append((job.step, 1.0))
    except (NoTissueError, IngestError) as e:
        with job.lock:
            job.status, job.error = "error", str(e)
    except Exception as e:
        log.exception("job %s failed", job_id)
        with job.lock:
            job.status, job.error = "error", f"Analysis failed ({type(e).__name__}). Try another image."
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


def create_app(cfg=None):
    cfg = cfg or load_config()
    backend = load_backend(cfg)  # Phase 2 startup check: refuses to start rather than fall back to the demo model
    uploads = repo_path(cfg["paths"]["uploads"])
    uploads.mkdir(parents=True, exist_ok=True)

    app = FastAPI(title="Biopsy sampling-site finder")
    app.state.jobs = {}

    def get_job(request, job_id):
        job = request.app.state.jobs.get(job_id)
        if job is None:
            raise HTTPException(404, "No analysis with this id. It may have expired when the server restarted.")
        return job

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
        threading.Thread(target=run_job, args=(job, job_id, slide, path, cfg, backend), daemon=True).start()
        return JobCreated(job_id=job_id)

    @app.get("/api/jobs/{job_id}", response_model=JobStatus)
    def job_status(request: Request, job_id: str):
        return get_job(request, job_id).status_body()

    @app.get("/api/jobs/{job_id}/regions", response_model=Regions)
    def regions_at_size(request: Request, job_id: str, box_um: float):
        """Re-rank a finished job's stored tile scores with another box size. The model isn't run again."""
        job = get_job(request, job_id)
        try:
            n = box_tiles(cfg, box_um)
        except ValueError as e:
            raise HTTPException(400, str(e)) from e
        with job.lock:
            ranking = job.ranking if job.status == "done" else None
        if ranking is None:
            raise HTTPException(409, "This analysis is still running, or it failed. Box size can change once it's done.")
        probs, tissue, tile_size, scale = ranking
        regions, note = rank_regions(probs, tissue, {**cfg, "region_tiles": n}, tile_size, scale)
        return Regions(box_um=box_um, regions=[Region(**r) for r in regions], note=note)

    @app.get("/api/jobs/{job_id}/display.png")
    def display_png(request: Request, job_id: str):
        return image_response(get_job(request, job_id).display_png)

    @app.get("/api/jobs/{job_id}/heatmap.png")
    def heatmap_png(request: Request, job_id: str):
        return image_response(get_job(request, job_id).heatmap_png)

    return app


def image_response(data):
    if data is None:
        raise HTTPException(404, "This image isn't ready yet.")
    return Response(data, media_type="image/png", headers={"Cache-Control": "private, max-age=3600"})

"""TCGA open-access data from the GDC API (api.gdc.cancer.gov). No token needed; login node only (compute nodes are offline)."""

import json
import shutil
import urllib.request
from pathlib import Path

import pandas as pd

API = "https://api.gdc.cancer.gov"
SLIDE_FIELDS = [
    "file_id", "file_name", "file_size",
    "cases.samples.portions.slides.submitter_id", "cases.samples.portions.slides.percent_tumor_cells",
]


def _post(endpoint, body):
    req = urllib.request.Request(f"{API}/{endpoint}", json.dumps(body).encode(), {"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=300) as r:
        return json.load(r)


def fetch_slide_hits(project):
    """Every open-access slide image file of one TCGA project, with its slides' recorded percentages."""
    body = {
        "filters": {"op": "and", "content": [
            {"op": "=", "content": {"field": "data_type", "value": "Slide Image"}},
            {"op": "=", "content": {"field": "access", "value": "open"}},
            {"op": "=", "content": {"field": "cases.project.project_id", "value": project}},
        ]},
        "fields": ",".join(SLIDE_FIELDS), "format": "JSON", "size": 100000,
    }
    return _post("files", body)["data"]["hits"]


def slides_from_hits(hits, kinds):
    """One row per slide file of the wanted kinds (e.g. TS, BS), with the pathologist % recorded on that slide."""
    rows = []
    for h in hits:
        stem = h["file_name"].rsplit(".", 1)[0]          # <slide barcode>.<uuid>
        slide_barcode = stem.split(".")[0]
        if slide_barcode.rsplit("-", 1)[-1][:2] not in kinds:
            continue
        pct = None
        for case in h.get("cases", []):
            for sample in case.get("samples", []):
                for portion in sample.get("portions", []):
                    for slide in portion.get("slides", []):
                        if slide.get("submitter_id") == slide_barcode:
                            pct = slide.get("percent_tumor_cells")
        if pct is None:
            continue
        rows.append({"slide_id": stem, "slide_barcode": slide_barcode, "file_id": h["file_id"],
                     "file_size": int(h["file_size"]), "pathologist_pct": float(pct)})
    return pd.DataFrame(rows, columns=["slide_id", "slide_barcode", "file_id", "file_size", "pathologist_pct"])


def download(url, dest, expected_size=None):
    """Stream to dest (via a .part file), skipping a file already there at the expected size."""
    dest = Path(dest)
    if dest.exists() and (expected_size is None or dest.stat().st_size == expected_size):
        return False
    dest.parent.mkdir(parents=True, exist_ok=True)
    part = dest.with_name(dest.name + ".part")
    with urllib.request.urlopen(url, timeout=600) as r, open(part, "wb") as out:
        shutil.copyfileobj(r, out, length=8 * 1024 * 1024)
    if expected_size is not None and part.stat().st_size != expected_size:
        raise IOError(f"{dest.name}: got {part.stat().st_size} bytes, expected {expected_size}")
    part.replace(dest)
    return True


def file_url(file_id):
    return f"{API}/data/{file_id}"

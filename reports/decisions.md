# Decisions

One line each: decision + reason.

## Phase 0
- Python 3.12 venv at `.venv`: it has wheels for torch, OpenSlide and CONCH's dependencies; Delta uses its own module torch (AGENTS.md §5).
- Frontend pinned to Vite 6.4.4 / Vitest 3.2.7: newer Vite needs Node ≥ 22.12, and this machine has Node 22.5.1.
- `@testing-library/jest-dom` pinned to 6.9.1: npm marks 6.10.0 as a broken release.
- Tailwind CSS 4 through `@tailwindcss/vite`: current major; Phase 5 tokens go in its CSS `@theme`.
- Frontend scaffolded by hand instead of `create-vite`, so every version is pinned and nothing extra ships.
- pytest config lives in `backend/pyproject.toml`; tests run from the repo root with `pytest backend`.
- Added `make setup` and `make setup-real`, so teammates can build the environment with one command.
- `make dev` starts only the frontend until the API exists (Phase 4).
- `config.yaml` sits at the repo root; `PROJECT_CONFIG` can point elsewhere (e.g. tests, Delta).
- On this Mac, `make` only runs as `DEVELOPER_DIR=/Library/Developer/CommandLineTools make …`: `xcode-select` points at Xcode.app, whose make shim fails. A human fix (e.g. `sudo xcode-select -s /Library/Developer/CommandLineTools`) is out of scope for an agent.

## Phase 1
- OpenSlide from the `openslide-bin` 4.0.1.2 wheel (bundles the C library; no `brew install`); import confirmed.
- The .svs/.tiff path is tested with tiny tiled TIFFs generated inside the tests (zlib, mpp in the TIFF resolution tags, which OpenSlide reports as `openslide.mpp-x`); nothing binary is committed.
- .tif/.tiff go to OpenSlide first (tiled or pyramidal scans, with their mpp); plain untiled TIFFs fall back to Pillow, with an estimated scale.
- A scan's own mpp wins over a typed one; photos use the typed mpp, then `default_mpp`, and are marked estimated.
- Tissue = HSV saturation ≥ `tissue_min_saturation` (glass is unsaturated, H&E isn't), measured on the display image; a tile's tissue fraction is the mean over its footprint there. This is cheap even for whole-slide scans.
- The tile grid starts at (0, 0) and drops the partial right and bottom edge, so every tile is fully inside the image.
- Transparent pixels (PNG alpha, outside an OpenSlide region) are composited onto white so they read as glass; phone photos are EXIF-rotated.
- An image smaller than one tile at its scale is an `IngestError` with a message about the scale, not "No tissue found".

## Phase 2
- "Token present" = `HF_TOKEN` in the environment, else the token cached by `hf auth login` (`huggingface_hub.get_token()`), so Delta users who logged in don't have to export the token.
- CONCH is pinned to commit 141cc09 and loaded exactly as in its source: `create_model_from_pretrained("conch_ViT-B-16", "hf_hub:MahmoodLab/CONCH", device=…, hf_auth_token=…)`, `.eval()`, `torch.no_grad()`, `encode_image(proj_contrast=True, normalize=True)`.
- `transformers` pinned to 4.57.6: a smoke test with randomly initialized CONCH showed its tokenizer crashes on transformers 5 (`batch_encode_plus` was removed). This also applies to Delta installs.
- Zero-shot scores: each class's embedding is the mean of its normalized prompt embeddings, renormalized; probabilities are the softmax of `logit_scale` × cosine similarity.
- `FakeBackend` scores mean tile color with fixed formulas (purple → tumor, pink → stroma, white → fat/other); deterministic and demo-only.
- A failed CONCH load is a `ModelConfigError` that names the cause, with the token blanked out if it ever appears; there's never a fallback to the fake model.
- `max_tiles` cap keeps evenly spaced tiles from the row-major tissue list; the full tissue grid stays intact for region coverage, and `TileGrid.capped` / `n_tissue_tiles` record the cut.
- AUROC is rank-based (Mann-Whitney) with ties counted half, in NumPy, so there's no scikit-learn dependency.
- The real-model AUROC result goes to `results/conch_auroc_<prompt_set>.json`, so a one-time prompt change keeps both results.
- When the token is missing, the realmodel tests fail with a clear message instead of skipping; only missing CRC data skips (the brief's rule).
- CRC-VAL-HE-7K: `scripts/get_crc_val.sh` shows the size (~800 MB) and asks before downloading; not run yet, since realmodel tests run in Phase 7.

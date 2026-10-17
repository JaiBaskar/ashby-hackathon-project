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

## Frontend moved to Next.js (after Phase 2)
- Frontend rewritten from Vite to Next.js 16.4.2 (App Router) at the team's request. All ML logic stays in Python behind FastAPI; Phases 1–2 are unchanged. This replaces the Phase 0 lines about Vite, `@tailwindcss/vite` and `create-vite`.
- Next.js reaches FastAPI through an `/api/*` rewrite in `frontend/next.config.ts`: one origin and no CORS. `API_URL` (default `http://localhost:8000`) is read when `next dev`/`next build` starts. Tested: `next start` ignored an `API_URL` set after the build.
- `experimental.proxyClientMaxBodySize` = `max_upload_mb` + 1 MB, read from `config.yaml`. Tested with a 40 MB upload through `next dev`: by default Next cut the body at 10 MB and the backend request failed; with the setting, all 41,943,251 bytes arrived.
- Vite 6.4.4 stays as a pinned dev dependency: Vitest runs on Vite, and npm would otherwise install Vite 7, which needs Node ≥ 22.12.
- React 19.2.9 (inside Next 16's peer range); Tailwind CSS 4 through `@tailwindcss/postcss`; no ESLint for now (fewer dependencies).
- Vitest uses `vitest.config.mts` with `@vitejs/plugin-react` and an `@` alias, so there's no extra tsconfig-paths plugin.
- `frontend/AGENTS.md` is written by `next dev` (verified in `next/dist/server/lib/generate-agent-files.js`) and committed, so it doesn't keep showing up as a change.
- Planned App Router layout for Phase 6: `/`, `/upload`, `/jobs/[id]`. Each job gets a URL that survives a reload.
- In this agent's sandbox, Python processes can't accept local connections, though Node can (the macOS firewall is off). So the upload check used a Node stand-in for FastAPI. FastAPI's own tests (Phase 4) use the in-process TestClient.

## Phase 3
- Windows dev machine: Python 3.12.10 and Node 24.20.0 (LTS) installed with winget, at the user's request. There's no `make`, so the suite ran as `.venv/Scripts/python -m pytest backend -m "not realmodel and not gpu and not delta"` and `npm test` (the Makefile's `.venv/bin/python` path is Mac/Linux only).
- `rank_regions` takes the full `[rows, cols, classes]` score grid (NaN for tiles dropped by the `max_tiles` cap) and the tissue grid. A region's composition, score and tumor std use its analyzed tiles; coverage uses every tile's tissue fraction.
- Tumor std is the population std (ddof=0) across the region's tiles, matching the hand-computed test.
- Candidates tie-break on (row, col) after score, so equal scores always give the same order.
- Rank 1 always gets "Highest overall score of all candidates (0.79)": true by construction, so the best region never shows an empty reason list.
- "Highest tumor content" is checked against every eligible window, not just the 5 picked, as the brief says.
- Ranks 2–5 compare tumor with the best region using the rounded percentages shown, so the quoted gap always matches the two numbers on screen. When a lower-ranked region has more tumor, the reason says so and names necrosis or unevenness as the cause.
- `size_um` = N × `tile_px` × `target_mpp` always (scale is never unknown: photos fall back to `default_mpp` and are marked estimated).
- Heatmap: one tint (`HEATMAP_RGB`), opacity = tumor × 0.85; unanalyzed tiles are transparent. Drawn at tile resolution and scaled up with nearest-neighbour, so each tile is a crisp block.
- Test fixture fix: the overlap/coverage test drew tissue from U(0.6, 1.0), so no window could reach `min_coverage` 0.9. Changed to U(0.8, 1.0): 203 of 441 windows are eligible, so the filter is exercised. The 0.9 threshold didn't move.

## Phase 4
- FastAPI 0.143.3, uvicorn 0.54.0, python-multipart 0.0.32 (needed for form uploads). The TestClient uses `httpx2` 2.13.1: Starlette 1.8 warns that plain `httpx` is deprecated for it, and tests pass with httpx2 alone.
- App factory `create_app(cfg)`, run with `uvicorn --factory`, so importing the module never loads a model and tests can pass their own config. It calls `load_backend` first, so a missing CONCH token stops the server before it serves anything.
- One background thread per job with an in-memory store (no queue library): enough for a demo, and the TestClient sees real polling. Jobs are lost on restart; the 404 message says so.
- The file type is checked against the user's filename before anything is written (400 names their file); the body is streamed to disk in 1 MB chunks and stops with 413 once it passes `max_upload_mb`; then `open_slide` decodes it, so a corrupt file is a 400 right away.
- Each job records every (step, progress) it reaches in `Job.history`; `advance` ignores any move backwards, and the test checks both the history and what polling saw.
- display.png and heatmap.png are kept as PNG bytes in memory; the upload file is deleted when the job ends (closed first, since Windows can't delete an open file).
- Unexpected worker errors show "Analysis failed (<type>). Try another image." and log the traceback server-side, so internals don't reach the browser.
- `make dev` starts uvicorn on :8000 in the background and `next dev` in the foreground; `trap 'kill 0' EXIT` stops both on Ctrl-C.
- Live check (uvicorn on Windows, synthetic 2048×1536 fixture): job done, 28 tiles, 1 region with a note, display.png served, upload deleted. The fixture only fits one 4×4 region; Phase 7's fixture must be bigger (brief §5, Phase 7).
- Note grammar fixed for exactly one region ("1 region is ... so 1 is shown").

## Phase 5
- This Mac has only Python 3.14 (no 3.12): `.venv` was built with `python3.14 -m venv .venv`, and every pinned backend requirement installed and passed (86 tests). The Makefile's `python3.12` line is unchanged.
- Box contrast: no single color reaches 3:1 on both eosin pink (L ≈ 0.540) and hematoxylin purple (L ≈ 0.106) except near-black (`#000000` 3.13:1 on purple, `#0A0A0A` 2.95:1). Every box is a black 2 px outer outline plus a colored inner stroke, and the test requires, per box style and tissue color, that at least one layer reaches 3:1. The 3:1 bar didn't move.
- Box inner strokes: best = the accent `#2DB391` at 4 px, others = light neutral `#F4F3EF` at 2 px; the thicker stroke plus a "Best" label make the best box visible without color. Box tokens are the same in both themes because they sit on the slide.
- Accent is a teal-green: its hue is far from both stains, so it never blends into the tissue, and it isn't Tailwind blue.
- Fonts: Newsreader (display) and IBM Plex Sans (body) from `@fontsource-variable/*` 5.3.0 via `next/font/local`, so builds and tests stay offline; both are OFL and credited in the README.
- Tailwind's default colors, type scale, radii, shadows and fonts are reset with `--*: initial` inside `@theme`, so only our tokens exist. `@theme static` emits every token as a CSS variable; fonts use `@theme inline`, as the Next.js font docs show.
- Dark mode follows `prefers-color-scheme` by redefining the chrome tokens on `:root`; components need no `dark:` variants. A manual theme toggle isn't in the brief.
- The token test also fails on any hex color in `app/` or `components/` outside `globals.css`, to keep "tokens only" enforced in Phase 6.
- Contrast math lives in `frontend/lib/contrast.ts` (WCAG 2.x), with hand-computed checks: 21:1 black on white, pink L = 0.5397, 3.13 and 2.95 on purple.

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

## Phase 6
- `/jobs/[id]` is a Server Component that fetches the job from FastAPI (`API_URL`) once, so a reload of a results URL renders straight away and an unknown id hits `notFound()` → `not-found.tsx`. A Client Component (`JobView`) then polls `/api/jobs/{id}` every second until done or error.
- Polling stops on done/error, turns a 404 (job lost on restart) into the error screen, and gives up after 5 network failures in a row with a readable message, so the screen never spins forever.
- Boxes are positioned in px from a measured scale (rendered image width ÷ display width), re-measured on image load, window resize and ResizeObserver. Testable in jsdom by stubbing `getBoundingClientRect`, which percentage positioning wouldn't be.
- The best region is selected when results open, so the detail panel is never empty; boxes are `<button aria-pressed>`, so Enter and Space work natively.
- `max_upload_mb` and `default_mpp` reach the browser through `next.config.ts` `env`, read from `config.yaml` by `frontend/app-settings.ts`; `vitest.config.mts` uses the same function, so tests check the real config values.
- Browsers can't display TIFF/SVS: the upload screen shows a "no preview" card with the file name for those, and an image preview for PNG/JPEG.
- `app/icon.svg` added: without it the browser's automatic `/favicon.ico` request 404s and logs a console error, which Phase 7 forbids.
- `app/error.tsx` covers the API being down when a job page loads (the server-side fetch throws).
- `@testing-library/user-event` 14.6.1 added for keyboard and upload interactions.
- Live check (FastAPI fake model + `next dev`, synthetic 3400×2400 image uploaded through the `/api` rewrite): results, box selection, heatmap toggle and the not-found page work; no horizontal scroll at 375 px on any screen; layout checked at 375 px and 1440 px in light and dark. That image fits only 2 regions; the Phase 7 fixture must fit 5.
- Not changed, flagged for Phase 7: the backend heatmap tint `HEATMAP_RGB` (214, 40, 110) is close to eosin pink, so the overlay reads weakly on pink tissue.

## Phase 7
- Playwright 1.63.0 (pinned; Chromium headless shell only). Its `webServer` starts uvicorn on :8100 and `next build && next start` on :3100 with `API_URL` set before the build, so `make dev` ports stay free and every test goes through the `/api` rewrite.
- Fixtures come from `backend/tests/fixtures/make_fixtures.py`, run by Playwright's global setup into `frontend/e2e/.fixtures/` (gitignored), so no images are committed. A backend test (`test_fixtures.py`) checks them with the real pipeline and the demo model.
- Slide fixture: 5120×3584 px of flat colors (82 KB). At the default 0.5 µm/px that's 20 × 14 tiles (5120 × 0.5 ÷ (256 × 0.5)), room for 15 non-overlapping 4 × 4 regions. The first 4096×3072 version with an ellipse of tissue gave only 4 regions with flat colors (greedy picks left awkward gaps), so the five purple patches now sit ≥ 6 tiles apart and the top 5 are one per patch.
- Per-pixel noise was dropped from the slide and blank fixtures: with noise the slide PNG was 19 MB. The demo model and tissue mask need only the colors.
- The > 10 MB check posts a 12.3 MB noise PNG through Next's port and expects FastAPI's 200 with a `job_id`.
- Every Playwright test fails on any console error or page error (an auto fixture). The 375 px no-scroll test covers home, upload and results; the not-found page was left out because Chrome logs its 404 document status as a console error, which is the intended response, not a bug.
- Two test selectors were fixed while writing the specs (not app code): the score renders as "Score 0.43" with a space, and Next's route announcer also has `role="alert"`, so the error check finds the message by its text and then checks its role.
- Screenshots: `e2e/screenshots.spec.ts` saves home, upload, analyzing, results, results with heatmap, and error, at 375 and 1440 px in light and dark (24 files, 1.6 MB). The demo model finishes in about a second, so for the analyzing shot the browser's polling is held on a fixed mid-run state with `page.route`; the server-rendered first state is still real.
- Heatmap tint changed from magenta `(214, 40, 110)` to amber `(255, 196, 0)`, as flagged in Phase 6: the old hue was 1° from eosin pink, so the overlay vanished on tissue. A new test requires ≥ 60° of hue from both stains (amber: 70° from pink).
- `make test` now runs Playwright too (`make test-e2e`); `make setup` installs Chromium. `PYTHON` overrides the venv path (e.g. Windows).
- `make test-real` didn't run: this Mac has no torch or CONCH in `.venv`, no `HF_TOKEN` or cached token, no CONCH weights and no CRC-VAL-HE-7K. Installing them means > 1 GB downloads, which need human approval (CLAUDE.md), and a CONCH-licensed account. `scripts/test_real.sbatch` is ready for Delta but wasn't submitted.

## Prompt sets and the BCSS breast check
- Goal: tumor detection for any cancer, not only colon. CONCH is used zero-shot; nothing is trained.
- `config.yaml` now holds named `prompt_sets`; `prompt_set` picks one and `load_config` resolves it into `cfg["prompts"]`, so the model code didn't change. `v1` is the original set, which leans toward colon ("normal mucosa", "adenocarcinoma"). `v2` is worded for any organ: it adds invasive, squamous cell and poorly differentiated carcinoma, and its normal class uses "benign epithelium" and "normal glands or ducts". Stroma, immune, necrosis and fat/other are the same in both.
- Fixed before any BCSS run: the bar stays at tumor-vs-rest AUROC ≥ 0.8 for both datasets; `v2` was frozen and not tuned on BCSS; `v2` becomes the default only if it clears 0.8 on both datasets and its mean AUROC across them is ≥ `v1`'s.
- BCSS (TCGA breast, CC0): `scripts/get_bcss.py` takes a seeded subset (config `seed`) of the 151 regions while the total stays ≤ 0.9 GB, pinned to mirror commit `846c11f`. `project/evaldata.py` cuts non-overlapping 512 px crops at 0.25 µm/px, resizes them to 256 px (0.5 µm/px, the app's `target_mpp`), and keeps a crop only when one mask code covers ≥ 90% and no pixel is outside the region. DCIS, angioinvasion, "exclude" and "undetermined" crops are dropped from both sides.
- The test asks for 300 BCSS tiles; the subset holds fewer pure crops than that, so all of them are used. Tile, tumor and region counts are in each result file.
- Results: `results/conch_auroc_{crc,bcss}_{v1,v2}.json` (written by `make test-real`). All four clear 0.8, and `v2` met the rule, so `prompt_set` is now `v2`. The gap between the sets is small on both datasets, about one point, likely within sampling noise at these tile counts. Read it as "v2 is no worse on colon and works on breast", not as a clear win.
- `results/conch_auroc_v1.json` from the first run is replaced by `conch_auroc_crc_v1.json`, which reproduces the same value.
- This supersedes the Phase 7 note that `make test-real` didn't run: it now runs on this Mac (MPS) with the cached weights and `HF_HUB_OFFLINE=1`.
- `v1` was then removed from `config.yaml` and the real-model tests, at the team's request, so `v2` is the only prompt set. Its wording is still in git history (commit `c62722d`). The `v1` result files are kept as the record of the comparison that retired it.

## Box size utility
- The results screen offers box sizes from `config.yaml` `box_sizes_um` (512, 1024, 2048 µm, shown as 0.5, 1 and 2 mm), so the box can match the punch or core that will be cut. The default stays `region_tiles: 4` (512 µm).
- Changing size doesn't run the model again. Each job keeps its tile-score grid, tissue grid and scale; `GET /api/jobs/{id}/regions?box_um=…` re-ranks them with `region_tiles = box_um ÷ 128`. The tiles themselves stay 256 px at 0.5 µm/px: they're sized for the model, and the box only averages more or fewer of them.
- Sizes are a fixed list, not free input: every box is a whole number of 128 µm tiles (checked when config loads), each size can be tested, and scores at one size stay comparable. A size not on the list is a 400 that names the ones on offer; a job that isn't done yet is a 409.
- 512 µm is labeled "0.5 mm" in the picker; the region panel keeps the exact size ("512 µm square").
- One size per ranking: boxes of different sizes are never mixed, because a small box can sit inside one tumor pocket and would always outscore a larger one.
- The frontend fetches each size once and keeps it, so switching back is instant; the first size comes with the job result. A failed re-rank keeps the current boxes and shows the server's message.
- The reason cutoffs (`low_variation` etc.) and the benchmark's pass checks were set at 512 µm and haven't been re-checked at 1 and 2 mm.

## Heatmap contrast and smoothing
- On a real slide the demo model scored almost every tile 0.78–0.90 tumor, so with opacity ∝ probability (0 → 0.85) 98% of the overlay sat at ≥ 70% of full opacity: a flat amber wash with tile-sized squares that hid the tissue.
- The color scale now spans the slide's own 5th–95th percentile of tumor probability (`heatmap_range`), widened to at least 20 points (`HEATMAP_MIN_SPAN`) so small noise isn't amplified, and kept within [0, 1]. Below the range is clear; the top of the range is `HEATMAP_MAX_ALPHA` = 0.65 (was 0.85), so the tissue still shows. The API returns `heatmap_range` and the results page shows it in a legend ("scaled to this slide"), so the stretch is visible to the reader.
- Tumor probability is interpolated bicubically between tile centers (normalized so unanalyzed tiles don't pull values to 0), and the tissue edge fades with rounded corners.
- `test_heatmap_places_tile_at_its_display_position` checked "> 150" (opaque under the old 0.85 maximum); with a 0.65 maximum that is out of reach, so it now checks "> 100" with an explicit 0–1 range. Its intent (the tile lands at [row, col], the transposed spot stays clear) is unchanged.
- Checked through the site on a synthetic tumor-rich image (88% tumor, demo model): overlay opacity now spans 0.11–0.56 (5th–95th percentile) instead of one level.
- Found on a real 4874 × 7128 image under CONCH: the tile grid stopped 3 px short on the right and 63 px short at the bottom (only whole tiles are cut), and the overlay ended there in a hard line (neighbouring-pixel opacity jump 0.65). When the grid stops short of the display, `tumor_heatmap` now treats the strip beyond it as unanalyzed, so the overlay fades out across the grid's edge like it does at tissue edges. Re-run on the same image: largest jump 0.035; regions and composition unchanged. New test: `test_heatmap_fades_where_the_tile_grid_ends_before_the_image`.

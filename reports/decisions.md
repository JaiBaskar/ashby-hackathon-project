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

## Request history (Postgres on Tiger Cloud)
- Every analysis is recorded in a store: `PostgresStore` when `DATABASE_URL` is set (a Tiger Cloud DEV service, `ashby-prize` (id `yni5q7anm1`), shared tier, us-east-1), else `MemoryStore`. One contract test suite covers both (`backend/tests/test_store.py`; Postgres cases run with `make test-db` in a throwaway schema).
- Privacy: the cloud gets only job metadata (id, created time, status, model, prompt set, cancer type) and the Result JSON (numbers, reasons, region boxes). Never the uploaded file, its filename or any image; a test uploads `MRN-4417-smith.png` and checks the name appears nowhere. Display and heatmap PNGs stay on this machine in `data/jobs/<id>/` (gitignored), so history links still work after a restart on the same machine.
- `DATABASE_URL` set but unreachable → the server refuses to start (same rule as the model: no silent fallback). The error never echoes the URL, which may hold a password. Once running, a failed store write is logged and the result is still shown.
- Rows left `running` by a crash are marked as errors on startup ("The server restarted during this analysis").
- Image routes only touch the disk for 32-hex-character job ids, so a crafted id can't read other files.
- Cancer type: the column, API field and card attribute exist but stay null and read "Not identified yet": the classifier is on hold while the model changes. Filling it in is one argument in `run_job` (`job.cancer_type`).
- Playwright starts its backend with `DATABASE_URL` empty, so test runs never land in the real history.
- The tile-score grid behind box resizing is also saved as `data/jobs/<id>/ranking.npz` (gitignored), so changing the box size still works for a job after a restart.
- After the merge with the box-size work, `main` had `model: conch` in `config.yaml`. The API tests now force the demo model in their fixture, and Playwright starts FastAPI with `PROJECT_MODEL=fake` (a new override in `load_config`), so `make test` still needs no token, weights or GPU (AGENTS.md §7) while `make dev` uses CONCH.

## Free-form box
- Users can draw their own rectangle on the slide ("Draw a box"), or turn a suggested region into one ("Adjust this box"), then move it and resize it from 8 handles, like a screenshot selection. Dragging a side past the opposite one flips the box. Arrow keys move it 16 display px, and Shift + arrow keys resize it from the bottom-right; from the keyboard, "Draw a box" places a best-region-sized box in the middle and focuses it.
- `GET /api/jobs/{id}/measure?x=&y=&w=&h=` (display px) measures any rectangle from the job's stored tile scores; the model isn't run again. Each tile counts by the share of it the box covers, so the box needn't line up with the 128 µm grid. A box placed exactly on a suggested region gives that region's score, composition and tumor std (tested).
- Unanalyzed tiles (glass, or dropped by `max_tiles`) count toward coverage but not composition; a box with no analyzed tile is a 400 that says to move it over tissue. The box is clipped to the tile grid, which drops the partial right and bottom edge of the image.
- Free-box reasons only state facts about the box itself (low necrosis, coverage, evenness), plus a warning when it covers fewer than 4 tiles' worth of area, since those numbers rest on very few tiles. It has no rank, so there's no "highest of all candidates" reason.
- Pointer drags measure once, on release; keyboard changes wait 300 ms after the last key. Only the latest request's answer is shown.
- The free box is dashed (the suggestions are solid), with the same black outer outline, so it's distinguishable without color and keeps contrast on both stains.
- jsdom has no `PointerEvent`; `vitest.setup.ts` adds a small MouseEvent-based stand-in for the drag tests.
- The image scale (µm/px) is saved with the tile scores in `ranking.npz`, so a free box still gets its size in µm after a restart; files saved before this fall back to `default_mpp`.

## Phase 8 (TCGA validation): code
- Project TCGA-LUAD, frozen slides (TS/BS) only: a schema-only probe of the GDC showed `percent_tumor_cells` is recorded on TS/BS slides and essentially never on DX slides (BRCA 1 of 1,133; LUAD 0 of 541), so the comparison uses the slides the pathologist actually read (AGENTS.md §4). LUAD has 718 such slides with an ABSOLUTE call, ~125 MB median each.
- ABSOLUTE: PanCanAtlas `TCGA_mastercalls.abs_tables_JSedit.fixed.txt` (GDC data id 4f277128-…). Only `call status == called`; sample_id = first 16 chars of the aliquot barcode in `sample` (9,991 of 10,786 rows match the §4 regex; the rest are non-TCGA-format names). A sample with two calls is dropped as ambiguous (none in the current file). Fraction → percent happens only in `labels.read_absolute`.
- slide_id = GDC file stem (`<slide barcode>.<uuid>`), unique by construction; the pathologist % is taken from the slide record whose barcode matches that file.
- Samples with several slides keep one row per slide (AGENTS.md §4); the labels step prints how many have differing percentages (173 samples in LUAD) instead of listing them.
- Splits: hospitals shuffled with the config seed, filling test (30%), then cal (10%), then train. LUAD result: test 261 slides / 17 hospitals, train 378 / 15, cal 79 / 1 (one large site). `check_labels` enforces every §8 Phase 1 rule and passed on the real table.
- Downloads are capped per split (`max_slides`: train 100, test 150, cal 0; seeded sample): ~65 GB in total, under the ~200 GB ask-first line. Cal isn't scored, since conformal intervals aren't part of this step.
- The app's raw tumor % is a mean softmax probability, not a cell fraction, so the evaluation also reports a straight-line mapping fit on train hospitals only (a test checks that changing test truth leaves the fit unchanged). Pearson r is the same for both; MAE and catch rate differ.
- Verdict from the bootstrap of (pathologist MAE − app MAE): "better" if the 95% interval is above 0, "worse" if below 0, otherwise "comparable" (AGENTS.md §8 Phase 5 names only better/comparable; "worse" is added so a clear loss isn't reported as "comparable").
- `pearson_r` returns NaN for a constant input instead of dividing by zero.
- `evaluate` refuses scores from the demo model unless `--allow-fake` (pipeline checks only), so fake numbers can't land in `results/tcga_validation.json` by accident.
- `TCGA_DIR` overrides `paths.tcga_dir`, so Delta jobs use `/work/nvme/bfqi/$USER/tcga` without editing config.yaml. labels.csv, slides and per-slide scores never leave it; only aggregate counts (`results/tcga_labels_summary.json`) and metrics are committed.
- Scoring is resumable (appends one row per slide to app_scores.csv; a failed slide records its error and is left out), so a timed-out job can be resubmitted. Per AGENTS.md §8 Phase 3, the first job is `--limit 5`.
- Smoke test: `score --model fake` and `evaluate --allow-fake` ran end to end on 6 synthetic tiled TIFFs saved as .svs in a scratch TCGA_DIR; the second `score` run skipped all 6.
- Frontend tests on this PC needed `npm ci` again (teammates added `@testing-library/user-event`); then 64/64 passed.

## Phase 8: first CONCH run and a train-first check
- 5-slide GPU check (job 22955904): all ok, ~30 s per slide (12–38 s), model conch, scanner mpp 0.5, 627–2,000 tiles. The whole-slide tumor % was 1.5–6.1% on all five, far below typical LUAD purity, and necrosis was high on two (19%, 48%). Likely causes: frozen-section look (CONCH and the CRC check are FFPE) and generic prompts.
- So scoring goes train first: `score --split train`, then `check --split train` prints aggregate app vs. pathologist numbers (Pearson r, MAE, ranges) on train hospitals only and writes `results/tcga_check_train_<prompt_set>.json`. `check` refuses the test split: any prompt change is judged on train only, and test is scored and evaluated once, after the method is fixed.
- Python 3.11 on Delta (pytorch-conda/2.8): nested same-quote f-strings are 3.12-only, so one was rewritten; a tokenizer scan found no others in backend/.

## Prompt set v3: organ-aware prompts (after the 5-slide TCGA run)
(Written as "v2" on the phase8/tcga branch; renamed v3 when merged with main, whose v2 is the organ-neutral set above. Figures below are unchanged.)
- Diagnosis: with prompt set v1, CONCH almost never made "tumor" the top class. A mosaic .svs of 89% CRC tumor tiles scored 0.8% tumor, and on 60 held-out TUM dev tiles tumor won 3 times (29 went to "normal"). Tumor still ranked above other tissue (AUROC 0.92), which is why the v1 AUROC test passed. Not a code bug: a new test shows the slide-reading path (OpenSlide → tiles → CONCH) gives exactly the scores of the same tiles scored directly (fake model and real CONCH).
- Fix: organ-aware prompts. `organs: [colon, lung, breast, pancreas, prostate, other]`; each organ overrides the generic tumor and normal prompts with that organ's cancer and normal tissue; "other" uses the generic set. This mirrors how CONCH's authors ran zero-shot classification (organ and cancer named in the prompt).
- Choice made on a CRC dev sample (60 tiles per class, seeded, the 200 AUROC tiles excluded), never on the AUROC tiles or TCGA test: `scripts/prompt_dev/`, results in `results/prompt_dev_crc.json`. Colon `colon_d`: TUM tiles called tumor 5% → 50%, tumor calls 97% correct, mean per-class accuracy 0.71 → 0.85. Generic `generic_a`: tumor 5% → 35%, no false tumor calls, but other classes drop (0.71 → 0.62); kept because the app's job is finding tumor. Two rounds of candidates only, to limit fitting to the dev tiles.
- Lung, breast, pancreas and prostate prompts follow the colon pattern and are untested on tile data; lung is checked on the TCGA train split. 
- Held-out check (organ-aware set): AUROC 0.926 colon / 0.934 generic on the 200 AUROC tiles (v1: 0.923). Mosaic slides with 11/50/89% tumor tiles now score 6.3/21.6/42.7% (v1: 0.03/2.5/0.8%), and the new realmodel test (more tumor → higher %, by > 20 points) passes.
- Test fix: the mosaic test first compared the pipeline (which skips non-tissue tiles) with all 36 cells; it now compares on the cells the pipeline kept, and they match exactly. The 1-point tolerance is unchanged.
- Backends split into `embed` and `classify(embeddings, organ)`; `predict = classify(embed)`. CONCH text embeddings are computed once per organ at startup. An unknown organ is a ValueError (API: 400 before the upload is saved).
- API: optional `organ` form field (default `default_organ`), passed to the model and returned as `result.organ`. Frontend: "Organ" select on the upload screen (options and default from config.yaml through next.config `env`, labels in `lib/format.ts`), and "Organ: …" on the results screen.
- TCGA: `tcga.organ: lung`. The GPU job now saves each slide's tile embeddings (`$TCGA_DIR/embeddings/<slide_id>.npz`: feats float32 [N, 512], coords int64 (x, y), model, plus tiling metadata), and scores go to `app_scores_<prompt_set>.csv`, so v1 and v2 never mix. `score --embeddings-only` re-scores saved embeddings with new prompts; `scripts/tcga_rescore.sbatch` runs it on the CPU account. The old v1 `app_scores.csv` (5 slides) is ignored.
- Results files are per prompt set (`conch_auroc_<set>`, `conch_pipeline_check_<set>`, `tcga_check_<split>_<set>`, `tcga_validation_<set>`), so v1 and v2 numbers can be reported side by side.
- Not run on this PC: the Playwright end-to-end suite (its browsers aren't installed here). The organ select defaults to "other", so the existing flows send the same request plus `organ=other`.

## Merge of phase8/tcga with main (organ prompts + prompt sets)
- main's named `prompt_sets` structure is kept. A prompt set may now carry an optional `organs:` block of per-organ tumor/normal overrides; `with_prompt_set` exposes it as `cfg["organ_prompts"]` next to `cfg["prompts"]`.
- `v3` = main's `v2` (unchanged, the generic base for "other") + the organ overrides from phase8/tcga, written with a YAML anchor so the two can't drift. `prompt_set: v3`.
- Why both: on the CRC dev tiles (`scripts/prompt_dev/`), main's v2 calls 17% of tumor tiles tumor and 18% of normal tiles normal; the colon overrides give 50% and 98%. v2 stays the generic set because it was frozen before the BCSS check and passes it.
- Since v2's stroma/immune/necrosis/fat prompts equal the ones the colon overrides were tested with, v3-colon is exactly the tested `colon_d` set.
- The real-model AUROC test now scores each dataset with its organ's prompts (CRC → colon, BCSS → breast) for v2 and v3, and records the generic-prompt AUROC alongside. The bar stays 0.8.
- main's box-size tests stubbed `FakeBackend.predict(self, tiles)`; the pipeline now passes `organ=`, so the stubs accept and forward it. main's prompt-set tests skip a set's `organs` key when comparing it with the class list.
- `Result.organ` is optional (null for jobs recorded in the history store before the organ picker); the results screen shows "Organ: …" only when it's set. `cancer_type` (main) is separate: a future predicted type, still null.
- For e2e specs, Playwright config and screenshots, both branches had added their own copies; main's newer versions were kept.

## Phase 8: train check result and method comparison
- Train check (v3, lung prompts, 100 train slides, 12 hospitals): app whole-slide tumor % vs ABSOLUTE r = −0.02, MAE 23.4; pathologist r = 0.11, MAE 36.4 (median 85% vs true 43%). Neither tracks purity on these frozen sections; the app's lower MAE comes from being centred, not from tracking (results/tcga_check_train_v3.json on Delta).
- Likely causes: the frozen section is a neighbouring face of the sequenced piece; frozen artifacts; tile-level probability ≠ cell fraction; lung prompts untested. The near-zero pathologist r points at the data as much as the model.
- Next step chosen: compare slide-level methods on train only before scoring test (`backend/project/purity_models.py`, `tcga features` + `tcga explore`, `scripts/tcga_explore.sbatch`, CPU only): dummy (train median), three zero-shot summaries with a straight-line fit (mean tumor probability, share of tumor-top tiles, tumor among cell-containing classes), and ridge on the mean CONCH embedding + tumor-tile share (AGENTS.md §8 Phase 4's design). Leave-one-hospital-out CV on train; ridge alpha by nested leave-one-hospital-out inside each training fold. A shuffled-label ridge run is reported next to the dummy.
- Rule for choosing: a method counts only if its cross-validated MAE beats the dummy's and its r is clearly above 0; otherwise the honest result is "no method tracks ABSOLUTE on frozen TCGA-LUAD slides".
- `evaluate` now always reports the dummy, and with `--method` also the chosen method, fit on train hospitals only, with its own bootstrap vs the pathologist; all on the same test slides (those with features).
- Ridge is implemented in NumPy (standardized features, unpenalized intercept) with a hand-computed test, so no new dependency.
- Within- vs between-hospital correlation (`metrics.within_between_r`), reported for every method in `explore` and `evaluate`. Within: truth and prediction centred on their hospital's mean (hospitals with ≥ 2 slides; ≥ 3 points overall), then correlated; between: correlation of hospital means. Added after the ridge model's train CV (r = 0.73, MAE 11.4 vs dummy 17.5; shuffled-label ridge 17.96 vs dummy 17.87) to rule out a model that only recognizes hospitals (stain, scanner) whose typical purity differs. A test builds embeddings that encode only the hospital and checks the ridge shows no within-hospital signal there.
- The dummy's leave-one-hospital-out r of −0.43 is an artifact of the folds (holding out a high-purity hospital lowers the remaining median), not a result; the zero-shot straight-line fits track the dummy (flat slopes), i.e. no signal from the prompts on frozen lung.
- After the first test evaluation, `evaluate --method` also bootstraps the chosen method against the dummy (`bootstrap_vs_dummy`: dummy MAE − method MAE, 95% percentile interval). Reason: on TCGA-LUAD the recorded pathologist estimates run so high that a constant guess also "beats" them, so the meaningful bar is the dummy.
- `evaluate --method` writes the per-slide test predictions to `$TCGA_DIR/test_predictions_<prompt_set>.csv` (patient-level, never committed) for an independent recheck.
- `scripts/independent_check.py` was written by a fresh subagent from the metric definitions only, without reading `backend/` (CLAUDE.md's post-MVP check). It recomputes MAE, Pearson r, catch rate and both bootstraps from that CSV and compares them with the results JSON (exact for point values, ±1 point for bootstrap ends, since its RNG differs). Checked on synthetic data against this repo's `evaluate`: all pass.

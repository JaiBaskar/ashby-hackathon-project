# ashby-puppymoggers

A web app for the Ashby Hackathon (UIUC) that helps a pathologist decide where to cut. Upload one H&E slide or a batch (scans or photos). The backend tiles each image, scores every tile with the CONCH pathology model (zero-shot), and ranks regions by tumor content, necrosis and evenness. **Research prototype, not for clinical use.**

What a pathologist gets:

- **Worklist:** every case with a slide thumbnail, best-region tumor %, a "ready for sequencing" verdict, live progress for running cases, search, filters and a reviewed tick.
- **Case workspace:**
  - the slide on a dark stage, with zoom and tumor (deep orange) and necrosis (blue) heatmaps at adjustable opacity, each with a banded color key;
  - the five suggested regions as numbered boxes and in a sortable table;
  - each region checked against the lab's minimum tumor fraction for sequencing (default 20%);
  - if no region on the slide reaches the 20% minimum (`min_tumor_pct` in `config.yaml`), no regions are suggested and the case says so, with the best region's tumor %.
- **Boxes you can reshape:** grab any box by a corner or edge, or draw your own; the numbers are re-measured while you drag, from the stored tile scores. Suggestions can also be re-ranked at 0.5, 1 or 2 mm to match a punch.
- **Sampling sheet:** a print-ready page for the histotech, with the instruction, the slide with numbered boxes and a 1 mm scale bar, the region table, notes and sign-off lines. **Copy summary** puts the same numbers on the clipboard for the report.
- **Case labels, notes and reviewed ticks stay in your browser**, never on the server or in the shared history, because they can identify a patient.
- **Keyboard first:** 1–9 regions, H tumor heatmap, N necrosis heatmap, D draw, +/−/0 zoom, J/K next/previous case, P sheet, ? for the list.

## How it fits together

- `frontend/`: the Next.js app (App Router, TypeScript, Tailwind CSS) that people use. It holds no ML.
- `backend/`: a FastAPI service with all the ML logic in Python: reading slides (OpenSlide, Pillow), tiling, CONCH scoring and region ranking.
- Request history: every analysis is recorded in Postgres (a Tiger Cloud service) when `DATABASE_URL` is set in `.env`, else in memory. Only job metadata and the result numbers are stored, never the image or its filename; images stay in `data/jobs/` on this machine. The worklist (`/`) reads them; `/history` redirects there.
- The browser only talks to Next.js. Next.js forwards every `/api/*` request to FastAPI (`API_URL`, default `http://localhost:8000`), so both run as one site with no CORS setup.

Build plan: `.claude/implementation-steps.md`. Agent rules: `.claude/AGENTS.md`, `.claude/CLAUDE.md`, `.claude/rules.md`.

## Request history database

Analyses are stored in Postgres on Tiger Cloud: service **`ashby-prize`** (id `yni5q7anm1`, DEV, us-east-1), table `public.jobs`. Code: `backend/project/store.py`.

### Connect the app

1. Install the [Tiger CLI](https://docs.tigerdata.com/) and run `tiger auth login` with an account in the team's Tiger project.
2. Save the connection string into `.env` (gitignored) without printing the password:
   ```bash
   u=$(tiger db uri yni5q7anm1 --with-password) && printf 'DATABASE_URL=%s\nTEST_DATABASE_URL=%s\n' "$u" "$u" >> .env && unset u
   ```
3. Run `make dev`, which loads `.env`. To confirm, run `curl -s localhost:3000/api/jobs | head -c 80`: it should say `"store":"postgres"`.
   - `"store":"memory"` means `DATABASE_URL` isn't set, so history is lost on restart.
   - If the URL is set but the database can't be reached, the server refuses to start rather than silently falling back to memory.

Never commit `.env` or paste the URL into a chat or an LLM: it contains the password.

### Fetch the data

**Through the app's API** (works with either store; the app must be running):

| Request | Returns |
|---|---|
| `GET /api/jobs` | `{store, jobs: [...]}`. The newest 100 analyses, each with `id`, `created_at`, `status`, `model`, `cancer_type`, `organ`, `best_tumor`, `best_necrosis`, `n_regions`, `progress`, `best_box`, `image_size` |
| `GET /api/jobs/{id}` | One analysis: `status`, `created_at`, `cancer_type` and the full `result` (regions, composition, reasons) |
| `GET /api/jobs/{id}/display.png`, `/heatmap.png` | The slide and heatmap images. They come from `data/jobs/{id}/` on the machine that ran the analysis, never from the database |

```bash
curl -s localhost:3000/api/jobs | python3 -m json.tool | head -40
curl -s localhost:3000/api/jobs/<id> | python3 -m json.tool
```

**Straight from Postgres**, with the Tiger CLI (password from your keyring):

```bash
tiger db query yni5q7anm1 -c "SELECT id, created_at, status, model, prompt_set, cancer_type
                               FROM jobs ORDER BY created_at DESC LIMIT 20"
tiger db query yni5q7anm1 -c "SELECT result->'regions'->0 FROM jobs WHERE id = '<id>'"
tiger db psql yni5q7anm1      # interactive psql session
```

From Python, use `PostgresStore` so the column handling matches the app:

```python
import os
from project.store import PostgresStore    # run from backend/, with .env loaded
store = PostgresStore(os.environ["DATABASE_URL"])
for job in store.list(limit=10):
    print(job.id, job.created_at, job.status, job.cancer_type)
```

Agents can use the Tiger MCP server (`db_query` with `service_id: yni5q7anm1`). Select only the columns you need, never `SELECT *`.

### The `jobs` table

| Column | Type | Meaning |
|---|---|---|
| `id` | text, primary key | Job id (32 hex characters), also the `/jobs/{id}` URL |
| `created_at` | timestamptz | When the analysis was requested (UTC). Indexed, newest first |
| `status` | text | `running`, `done` or `error`. Rows left `running` by a crash become `error` on the next startup |
| `model` | text | `conch`, or `fake` for the demo model |
| `prompt_set` | text | Which prompt set in `config.yaml` was used |
| `cancer_type` | text, nullable | Most likely cancer type; null until a classifier is added |
| `result` | jsonb, nullable | The full Result JSON from `GET /api/jobs/{id}` (regions, tissue composition, reasons) |
| `error` | text, nullable | The message shown when an analysis failed |
| `finished_at` | timestamptz, nullable | When it finished or failed |

**Not stored, by design:** the uploaded file, its filename, any image, case labels and notes. Labels and notes stay in the browser, because they can identify a patient. `make test-db` runs the store tests against `TEST_DATABASE_URL` in a throwaway schema, which is dropped afterwards.

## Commands

| Command | What it does |
|---|---|
| `make setup` | Python venv (`.venv`) and frontend packages |
| `make setup-real` | Adds torch and CONCH, for the real model |
| `make dev` | Starts the app at http://localhost:3000 (Next.js, with FastAPI on :8000) |
| `make test` | All fast tests: backend, Vitest and Playwright end-to-end. No GPU, internet or token needed (uses the demo model) |
| `make test-e2e` | Only the Playwright flows; also saves screenshots to `reports/screenshots/` |
| `make test-db` | Postgres store tests in a throwaway schema; needs `TEST_DATABASE_URL` |
| `make test-real` | Tests that need real CONCH weights and `HF_TOKEN` (see `.env.example`), including the false-positive check: no region may be suggested on slides built only from non-tumor tiles (`results/false_positives_*.json`). On Delta: `scripts/test_real.sbatch` |

All settings (model, scale, thresholds, paths, seed) are in `config.yaml`.

## TCGA validation (Phase 8)

Does the app's whole-slide tumor % (`slide_composition.tumor` × 100, real CONCH) track ABSOLUTE purity better than the pathologist's recorded %? Code: `backend/project/tcga.py`, `labels.py`, `gdc.py`; settings under `tcga:` in `config.yaml`. It uses TCGA-LUAD frozen slides (TS/BS), because that's where the pathologist's % was recorded, and splits by hospital (tissue source site), never by slide.

On Delta, from the repo root. Commands marked **approval** spend GPU hours or download a lot: a human approves each one first.

```bash
# Once, on the login node
module load pytorch-conda/2.8; unset PYTHONNOUSERSITE
export HF_HOME=/work/nvme/bfqi/$USER/hf TCGA_DIR=/work/nvme/bfqi/$USER/tcga
pip install --user -r backend/requirements.txt          # plus CONCH: see backend/requirements-real.txt
hf auth login                                           # your own CONCH-approved account
hf download MahmoodLab/CONCH                            # approval (> 1 GB); download only, never load it here

# 1. labels.csv (login node, small downloads): GDC metadata + the ABSOLUTE table, split and checked
cd backend && python -m project.tcga labels && cd ..
python -m pytest backend -m delta -v                   # the Phase 1 checks on the real labels

# 2. slides (login node): prints the size first; re-run with --yes once approved
cd backend && python -m project.tcga download && cd ..
cd backend && python -m project.tcga download --yes && cd ..          # approval (tens of GB)

# 3. CONCH (GPU): saves each slide's tile embeddings once and scores them with the lung prompts.
#    5 slides first, then train only, check, then test. Resumable.
mkdir -p logs && sbatch scripts/tcga_score.sbatch --limit 5           # approval
sbatch scripts/tcga_score.sbatch --split train                        # approval, after checking the 5
tail -n 50 logs/<jobid>.out
cd backend && python -m project.tcga check --split train && cd ..     # app vs. pathologist on train only
sbatch scripts/tcga_score.sbatch --split test                         # approval, once the method is fixed
#    After a prompt change: re-score from the saved embeddings on CPU (no GPU hours)
sbatch scripts/tcga_rescore.sbatch                                    # approval

# 4. the comparison (CPU, seconds): writes results/tcga_validation.json
cd backend && python -m project.tcga evaluate
```

`results/tcga_validation_<prompt_set>.json` reports, on the test hospitals only: slide and hospital counts, MAE, Pearson r and the catch rate below 60% for the pathologist, the raw app % and the app % after a straight-line mapping fit on the train hospitals; and a 1,000-resample bootstrap of (pathologist MAE − app MAE) with its 95% interval. The app is called "better" only if that interval is entirely above 0. `check` never looks at the test split: any change to the method (e.g. the prompts) is judged on train hospitals only, so the test result stays honest. `labels.csv`, the slides, tile embeddings and per-slide scores (`app_scores_<prompt_set>.csv`, one file per prompt set) stay in `$TCGA_DIR` and are never committed.

## Credits

- **CONCH**: Lu, M.Y. et al. *A visual-language foundation model for computational pathology.* Nature Medicine 30, 863–874 (2024). Weights: `MahmoodLab/CONCH` on Hugging Face (gated; each user needs their own access).
- **CRC-VAL-HE-7K** (tile set for the accuracy check): Kather, J.N. et al. *Predicting survival from colorectal cancer histology slides using deep learning: a retrospective multicenter study.* PLOS Medicine 16(1): e1002730 (2019). Zenodo record 1214456.
- **TCGA** (slides and pathologist %): The Cancer Genome Atlas Research Network, via the NCI Genomic Data Commons (open access). LUAD: *Comprehensive molecular profiling of lung adenocarcinoma.* Nature 511, 543–550 (2014).
- **ABSOLUTE** purity calls: Carter, S.L. et al. *Absolute quantification of somatic DNA alterations in human cancer.* Nature Biotechnology 30, 413–421 (2012); PanCanAtlas table from Taylor, A.M. et al. *Genomic and functional approaches to understanding cancer aneuploidy.* Cancer Cell 33, 676–689 (2018).
- **BCSS** (breast regions for the second accuracy check): Amgad, M. et al. *Structured crowdsourcing enables convolutional segmentation of histology images.* Bioinformatics 35(18): 3461–3467 (2019). CC0 1.0; seeded subset fetched from the Hugging Face mirror `nabil-m/bcss` by `scripts/get_bcss.py`.
- **OpenSlide**: Goode, A. et al. *OpenSlide: A vendor-neutral software foundation for digital pathology.* J Pathol Inform 4:27 (2013).
- **Fonts**: Newsreader (Production Type) and IBM Plex Sans (IBM), both SIL Open Font License 1.1, bundled through the Fontsource packages.
- **Tiger Cloud** (managed PostgreSQL/TimescaleDB) for request history, via psycopg 3.
- Pillow, NumPy, pandas, PyYAML, tifffile, pytest, PyTorch, FastAPI, psycopg; Next.js, React, TypeScript, Tailwind CSS, Vitest, Testing Library, Playwright.

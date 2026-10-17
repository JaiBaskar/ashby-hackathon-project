# Ashby Hackathon 2026 — Code Rules

Sources: Opening Session slides (Oct 17, 2026) and [ncsa/ashby-hackathon-2026](https://github.com/ncsa/ashby-hackathon-2026) (`HACKATHON_COMPUTE.md`, `STUDENT_GUIDE.md`, `README.md`). Where they disagree, the repo (newer) wins.

---

## 1. Where Code Runs

- **Never run training, inference, `serve.py`, or `run_embeddings.py` on the Delta login node.** The process is silently killed.
- Login node is only for: editing files, `pip install`, `git`, submitting jobs, and lightweight HTTP clients (`client.py`, `curl`).
- All compute runs as a Slurm job (`sbatch` or `srun`) on a compute node.
- Compute nodes have **no internet**. Install packages and download weights from the login node first.
- Do not use DeltaAI (`bfqi-dtai-gh`).

## 2. Environment Setup

```bash
module load pytorch-conda/2.8
unset PYTHONNOUSERSITE          # required after EVERY module load, or --user packages are invisible
pip install --user "open_clip_torch>=2.24"
# only if running CONCH/MUSK yourself:
pip install --user git+https://github.com/mahmoodlab/CONCH.git
pip install --user git+https://github.com/lilab-stanford/MUSK.git fairscale sentencepiece
```

- Put `unset PYTHONNOUSERSITE` directly after `module load pytorch-conda/2.8` in every script and notebook.
- Set `export HF_HOME=/work/nvme/bfqi/$USER/hf` so large model downloads don't fill the home directory.

## 3. GPU Jobs

| Rule | Value |
|---|---|
| Account / partition | `--account=bfqi-delta-gpu --partition=gpuA100x4` |
| `--reservation` flag | Do not use; not needed |
| GPUs per team at once | **1** |
| GPU budget | **10 GPU-hours per person** (job waits with `QOSGrpBillingMinutes` if exceeded) |
| Job length | 1–2 hours; set a realistic `--time` |
| Per-GPU request ceiling | ≤16 CPUs and ≤~62 GB RAM (more burns budget faster) |
| `*-interactive` partitions | Cost double; 1 job per person; max 1 hour |
| Saturday overnight jobs | Must finish by **7:59 am Sunday** |
| Reserved nodes end | **Sun 6:00 pm** — any job whose time limit crosses Sun 8:00 am or 6:00 pm goes to the slow regular queue |

- Start on CPU (`--account=bfqi-delta-cpu --partition=cpu`). Use a GPU only when needed.
- End idle Jupyter/interactive sessions: `squeue -u $USER`, then `scancel <jobid>`.
- Never write scripts that resubmit jobs in a loop.

## 4. Storage

| Path | Use |
|---|---|
| `/u/<username>` (100 GB) | Code, environments, small files |
| `/work/nvme/bfqi/<username>` | Data, embeddings, checkpoints (not backed up) |
| `/work/nvme/bfqi/teams/<team>` | Team-shared outputs (`mkdir -p` it) |
| `/projects/bfqi/shared/datasets/` | Read-only datasets |
| `/work/nvme/bfqi/shared/datasets/quilt/` | Quilt-1M |

- **Do not use `/work/hdd`.**
- Keep code in home or on GitHub (`/work/nvme` is not backed up).
- Everything under `/projects/bfqi` and `/work/nvme/bfqi` is readable by all participants. Store nothing private there.
- Read shared datasets in place. **Do not copy them.**
- Ask in `#compute-issues` before downloading anything over ~200 GB.

## 5. Models and Licensing

| Model | Spec string | Access |
|---|---|---|
| CONCH | `conch` | Gated — your own HF access required |
| MUSK | `musk` | Gated — your own HF access required |
| QuiltNet-B-32 | `openclip:wisdomik/QuiltNet-B-32` | Open |
| PLIP | `hfclip:vinid/plip` | Open |

- Each person must accept CONCH/MUSK terms on Hugging Face, then run `hf auth login` on Delta. **This applies to the hosted servers too.**
- **Never share copies of gated weights.**
- Other models load without new code via `openclip:<hf-repo>`, `openclip:<arch>@<hf-repo>/<file>`, or `hfclip:<hf-repo>`.
- Embeddings from different models are not comparable. Use one model per experiment.
- Use pathology encoders (CONCH/MUSK) to classify tiles, not general vision-language models.
- Keep VLMs to ~14B parameters or smaller on one GPU.

## 6. Hosted Model Servers

- Endpoints and API keys: posted in `#compute-issues`. Run until **Sun 6:00 pm**.
- Call only **from inside Delta** (login node, OnDemand, or a job), never from a laptop.
- Auth: `Authorization: Bearer <key>`. Endpoints: `POST /embed`, `POST /classify`, `GET /health`.
- Send images as a batch in one request, not one image per call.
- Max a few thousand tiles at a time (~60 images/sec shared by everyone). For full datasets, run your own GPU job.

## 7. Data

- Use only public, de-identified data (shared datasets, TCGA open access, published sets).
- **Never paste patient data into an LLM chat or API.**
- Work on tiles (224–512 px), not whole-slide images.
- Use frozen weights: embed once, save, then train small heads or prompt zero-shot.
- **Split train/test by patient or slide, never by tile.** CRC-100K has no patient IDs; state that its random split overstates accuracy.
- LLMFlux image inputs must be PNG or JPEG. Convert `.tif` tiles first.

## 8. Secrets and AI Coding Agents

- Store API keys in environment variables (`export LUMEN_API_KEY=sk_...`), never in code or commits.
- If a key leaks, delete it on your Lumen Profile immediately and create a new one.
- Never paste passwords, API keys, or tokens into any agent or chat.
- Read every `sbatch`/`srun` command an agent proposes before approving it. Never let an agent submit GPU jobs unattended.
- Test agent-written code on a few tiles before running it at scale.
- In HPC-GPT, start a fresh session (`/new`) when switching tasks.

## 9. Credit

- Cite every model, dataset, and tool used in the final presentation.

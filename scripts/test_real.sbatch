#!/bin/bash
# Real-CONCH tests (make test-real) on one Delta A100. Submit from the repo root, after human approval:
#   mkdir -p logs && sbatch scripts/test_real.sbatch
# Before submitting, on the login node (rules.md §1–2, AGENTS.md §5): pip install --user -r backend/requirements.txt
# (plus CONCH), `hf auth login`, `hf download MahmoodLab/CONCH` (needs approval: > 1 GB), and point
# paths.crc_val_dir in config.yaml at CRC-VAL-HE-7K (look under /projects/bfqi/shared/datasets/ first).
# 30 minutes: well inside the 2 h cap, and it must end before Sun 7:59 am and Sun 6:00 pm (rules.md §3).
#SBATCH --job-name=puppymoggers-test-real
#SBATCH --account=bfqi-delta-gpu
#SBATCH --partition=gpuA100x4
#SBATCH --gpus-per-node=1
#SBATCH --cpus-per-task=16
#SBATCH --mem=32G
#SBATCH --time=00:30:00
#SBATCH --output=logs/%j.out

set -euo pipefail
module load pytorch-conda/2.8
unset PYTHONNOUSERSITE
export HF_HOME=/work/nvme/bfqi/$USER/hf
export HF_HUB_OFFLINE=1

python -m pytest backend -m realmodel -v

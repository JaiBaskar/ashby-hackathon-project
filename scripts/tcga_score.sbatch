#!/bin/bash
# Phase 8: score the downloaded TCGA slides with CONCH on one Delta A100. Resumable: slides already in
# app_scores.csv are skipped, so a second job picks up where a timed-out one stopped.
# Full steps: README.md § "TCGA validation". Submit from the repo root, after human approval (CLAUDE.md):
#   mkdir -p logs && sbatch scripts/tcga_score.sbatch --limit 5     # first 5 slides only; check them
#   mkdir -p logs && sbatch scripts/tcga_score.sbatch               # then the rest
# 1 h 30 min: inside the 2 h cap. Every job must end before Sun 7:59 am and Sun 6:00 pm (rules.md §3).
#SBATCH --job-name=puppymoggers-tcga-score
#SBATCH --account=bfqi-delta-gpu
#SBATCH --partition=gpuA100x4
#SBATCH --gpus-per-node=1
#SBATCH --cpus-per-task=16
#SBATCH --mem=32G
#SBATCH --time=01:30:00
#SBATCH --output=logs/%j.out

set -euo pipefail
module load pytorch-conda/2.8
unset PYTHONNOUSERSITE
export HF_HOME=/work/nvme/bfqi/$USER/hf
export HF_HUB_OFFLINE=1
export TCGA_DIR=/work/nvme/bfqi/$USER/tcga

cd backend
python -m project.tcga score "$@"

#!/bin/bash
# Slide-level features from the saved CONCH embeddings, then a leave-one-hospital-out comparison of purity
# methods on the TRAIN hospitals only (results/tcga_explore_train_<prompt_set>.json). CPU only, no GPU hours.
# Submit from the repo root, after human approval (CLAUDE.md):
#   mkdir -p logs && sbatch scripts/tcga_explore.sbatch
# Never the login node: `features` loads CONCH's text encoder (AGENTS.md §5).
#SBATCH --job-name=puppymoggers-tcga-explore
#SBATCH --account=bfqi-delta-cpu
#SBATCH --partition=cpu
#SBATCH --cpus-per-task=16
#SBATCH --mem=32G
#SBATCH --time=00:30:00
#SBATCH --output=logs/%j.out

set -euo pipefail
module load pytorch-conda/2.8
unset PYTHONNOUSERSITE
export HF_HOME=/work/nvme/bfqi/$USER/hf
export HF_HUB_OFFLINE=1
export TCGA_DIR=/work/nvme/bfqi/$USER/tcga

cd backend
python -m project.tcga features
python -m project.tcga explore --split train

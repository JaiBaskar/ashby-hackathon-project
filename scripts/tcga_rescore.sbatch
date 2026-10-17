#!/bin/bash
# Re-score saved CONCH tile embeddings with the current prompts in config.yaml: no slide reading, no GPU.
# Use after changing prompts or the TCGA organ. Writes $TCGA_DIR/app_scores_<prompt_set>.csv.
# Submit from the repo root, after human approval (CLAUDE.md):
#   mkdir -p logs && sbatch scripts/tcga_rescore.sbatch
# CPU work goes on the CPU account (AGENTS.md §5), never the login node: it loads CONCH's text encoder.
#SBATCH --job-name=puppymoggers-tcga-rescore
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
python -m project.tcga score --embeddings-only --split train test "$@"

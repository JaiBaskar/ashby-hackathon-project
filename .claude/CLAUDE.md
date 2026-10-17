# CLAUDE.md

@AGENTS.md

All project rules live in `AGENTS.md` (imported above) so that Claude Code and opencode/`hpc-gpt` follow the same instructions. Edit rules there, not here. This file adds only Claude Code–specific behavior.

## Before starting work

- At the start of a phase, use plan mode: list the tests you will write for that phase (from `AGENTS.md` §8), the files you'll touch, and any Delta job you'll need. Wait for approval before writing code.
- Track the phase's steps with the task list: tests written → tests fail → implementation → tests pass → human check (where §8 requires one).
- If the repo `README.md` has changed since you last read it, re-read it before planning.

## Commands that need explicit human approval

Ask before running each of these, showing the exact command. Never chain them inside a script or loop that runs without the human seeing it.
- `sbatch`, `srun`, `salloc`, `scancel` (they spend the team's GPU-hours)
- Any download larger than 1 GB, or any `hf download`
- `git push`, `git reset --hard`, `rm -rf`, anything that deletes data under `/work/nvme`

Running `pytest` on the fast suite, `squeue`, `quota`, `accounts`, and reading files need no approval.

## Working with large files

- Never `Read` or `cat` a slide, `.npz`, `.h5`, or a CSV with more than ~200 rows. Inspect them with a short Python command that prints shape, dtype, columns, `head()`, and summary stats.
- Never open slide thumbnails, tiles, or heatmap PNGs with the Read tool (`AGENTS.md` §6: no patient images to an LLM). Save them and tell the human where they are.
- Job logs: read with `tail -n 50 logs/<jobid>.out`, not the whole file.

## Subagents

- For the post-MVP check of headline results, you may use one subagent that hasn't seen the implementation to re-derive MAE, correlation, catch rate, and the bootstrap interval from `results/` and `labels.csv`, and compare.
- Subagents follow `AGENTS.md` too. They never submit Slurm jobs.

## When you finish a step

Report, in this order: which tests were added, the fast-suite result (pass/fail counts), any number produced (with split and slide count), and the next step. Keep it short.

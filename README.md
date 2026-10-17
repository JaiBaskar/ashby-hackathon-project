# ashby-puppymoggers

A web app for the Ashby Hackathon (UIUC). Upload a photo or scan of an H&E biopsy slide, and it suggests the five best regions to sample. The backend tiles the image, scores each tile with the CONCH pathology model (zero-shot), and ranks regions by tumor content, necrosis and evenness. Each suggestion comes with its estimated tissue composition and rule-based reasons. **Research prototype, not for clinical use.**

Build plan: `.claude/implementation-steps.md`. Agent rules: `.claude/AGENTS.md`, `.claude/CLAUDE.md`, `.claude/rules.md`.

## Commands

| Command | What it does |
|---|---|
| `make setup` | Python venv (`.venv`) and frontend packages |
| `make setup-real` | Adds torch and CONCH, for the real model |
| `make dev` | Starts the app |
| `make test` | All fast tests: no GPU, internet or token needed (uses the demo model) |
| `make test-real` | Tests that need real CONCH weights and `HF_TOKEN` (see `.env.example`) |

All settings (model, scale, thresholds, paths, seed) are in `config.yaml`.

## Credits

- **CONCH**: Lu, M.Y. et al. *A visual-language foundation model for computational pathology.* Nature Medicine 30, 863–874 (2024). Weights: `MahmoodLab/CONCH` on Hugging Face (gated; each user needs their own access).
- **CRC-VAL-HE-7K** (tile set for the accuracy check): Kather, J.N. et al. *Predicting survival from colorectal cancer histology slides using deep learning: a retrospective multicenter study.* PLOS Medicine 16(1): e1002730 (2019). Zenodo record 1214456.
- **OpenSlide**: Goode, A. et al. *OpenSlide: A vendor-neutral software foundation for digital pathology.* J Pathol Inform 4:27 (2013).
- Pillow, NumPy, PyYAML, tifffile, pytest, PyTorch; React, Vite, TypeScript, Tailwind CSS, Vitest, Testing Library.

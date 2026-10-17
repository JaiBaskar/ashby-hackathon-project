"""Download a seeded subset of BCSS (Amgad et al. 2019, CC0) for the real-model breast check.

Source: the Hugging Face mirror nabil-m/bcss of the authors' release (151 TCGA-BRCA regions, 4.9 GB).
Regions are shuffled with config.yaml `seed` and taken while the total stays under --max-gb, so the
same seed always gives the same regions. Lands in paths.bcss_dir (under data/, gitignored).
CLAUDE.md: an agent needs human approval for any download over 1 GB, so the default stays below it.
"""

import argparse
import sys
from pathlib import Path

import numpy as np
from huggingface_hub import HfApi, hf_hub_download

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from project.config import load_config, repo_path  # noqa: E402

REPO = "nabil-m/bcss"


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--max-gb", type=float, default=0.9)
    parser.add_argument("--yes", action="store_true", help="skip the confirmation prompt")
    args = parser.parse_args()

    cfg = load_config()
    dest = repo_path(cfg["paths"]["bcss_dir"])
    info = HfApi().dataset_info(REPO, files_metadata=True)
    sizes = {s.rfilename: s.size or 0 for s in info.siblings}
    rois = sorted(Path(f).stem for f in sizes if f.startswith("rgbs_colorNormalized/") and f.endswith(".png"))

    order = np.random.default_rng(cfg["seed"]).permutation(len(rois))
    picked, total = [], 0
    for i in order:
        files = [f"rgbs_colorNormalized/{rois[i]}.png", f"masks/{rois[i]}.png"]
        size = sum(sizes[f] for f in files)
        if total + size <= args.max_gb * 1e9:
            picked.append(files)
            total += size

    print(f"BCSS subset: {len(picked)} of {len(rois)} regions, {total / 1e9:.2f} GB "
          f"(seed {cfg['seed']}, {REPO}@{info.sha[:7]}) → {dest}")
    if not args.yes and input("Download it? [y/N] ").strip() != "y":
        sys.exit("Cancelled.")
    for files in picked:
        for f in files:
            hf_hub_download(REPO, f, repo_type="dataset", revision=info.sha, local_dir=dest)
    print(f"Done: {len(list((dest / 'masks').glob('*.png')))} regions in {dest}.")


if __name__ == "__main__":
    main()

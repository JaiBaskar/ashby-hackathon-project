"""Embed a seeded CRC-VAL-HE-7K dev sample (60 tiles per class) (disjoint from the 200 AUROC tiles) once; save to npz.

    python scripts/prompt_dev/embed_dev.py backend <dev.npz>   (CONCH access needed; CPU is fine)"""
import sys
sys.path.insert(0, sys.argv[1])
import numpy as np
from PIL import Image
from project.config import load_config, repo_path
from project.model import load_backend
import torch

cfg = load_config()
root = repo_path(cfg["paths"]["crc_val_dir"])
files = sorted(root.glob("*/*.tif"))
rng = np.random.default_rng(cfg["seed"])
auroc = set(rng.choice(len(files), size=200, replace=False).tolist())   # same draw as the AUROC test
dev_rng = np.random.default_rng([cfg["seed"], 1])
feats, labels = [], []
conch = load_backend({**cfg, "model": "conch"})
for d in sorted(p for p in root.iterdir() if p.is_dir()):
    idx = [i for i, f in enumerate(files) if f.parent == d and i not in auroc]
    pick = dev_rng.choice(idx, size=60, replace=False)
    imgs = [Image.open(files[i]).convert("RGB") for i in pick]
    with torch.no_grad():
        batch = torch.stack([conch.preprocess(im) for im in imgs]).to(conch.device)
        emb = conch.model.encode_image(batch, proj_contrast=True, normalize=True).float().cpu().numpy()
    feats.append(emb); labels += [d.name] * len(imgs)
    print(d.name, len(imgs), flush=True)
np.savez(sys.argv[2], feats=np.concatenate(feats), labels=np.array(labels))

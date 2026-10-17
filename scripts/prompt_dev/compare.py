"""Compare prompt candidates on cached CRC dev embeddings (from embed_dev.py); writes a JSON of the results.

    python scripts/prompt_dev/embed_dev.py backend <dev.npz>
    python scripts/prompt_dev/compare.py backend <dev.npz> scripts/prompt_dev/candidates.yaml results/prompt_dev_crc.json

The dev tiles are a seeded sample of CRC-VAL-HE-7K that excludes the 200 AUROC-test tiles. Each candidate
overrides some classes of the "v1" entry. Per class: share of that class's tiles CONCH puts in the right class.
"""
import sys, json
sys.path.insert(0, sys.argv[1])
import numpy as np, torch, yaml
from conch.open_clip_custom import create_model_from_pretrained, get_tokenizer, tokenize
from project.model import find_hf_token
model, _ = create_model_from_pretrained("conch_ViT-B-16", "hf_hub:MahmoodLab/CONCH", hf_auth_token=find_hf_token())
model.eval(); tok = get_tokenizer(); scale = float(model.logit_scale.exp())
d = np.load(sys.argv[2]); X = torch.tensor(d["feats"]); y = d["labels"]
CLASSES = ["tumor", "stroma", "immune", "necrosis", "normal", "fat_other"]
MAP = {"ADI": "fat_other", "DEB": "necrosis", "LYM": "immune", "MUC": "fat_other", "MUS": "stroma", "NORM": "normal", "STR": "stroma", "TUM": "tumor"}
def text_emb(prompts):
    with torch.no_grad():
        e = model.encode_text(tokenize(tok, prompts)).mean(0)
    return e / e.norm()
def evaluate(pset):
    T = torch.stack([text_emb(pset[c]) for c in CLASSES])
    p = (scale * X @ T.T).softmax(-1).numpy()
    pred = np.array(CLASSES)[p.argmax(1)]
    keep = y != "BACK"
    truth = np.array([MAP.get(v, "") for v in y])
    per = {c: float((pred[keep & (truth == c)] == c).mean()) for c in CLASSES}
    tum = y == "TUM"
    tum_to = {c: int((pred[tum] == c).sum()) for c in CLASSES}
    return {"TUM_called": tum_to, "tumor_recall": round(per["tumor"], 3), "balanced_acc": round(float(np.mean(list(per.values()))), 3),
            "tumor_precision": round(float((truth[keep & (pred == "tumor")] == "tumor").mean()) if (keep & (pred == "tumor")).any() else 0.0, 3),
            "mean_p_tumor_TUM": round(float(p[tum, 0].mean()), 3), "mean_p_tumor_other": round(float(p[keep & ~tum, 0].mean()), 3),
            "per_class": {k: round(v, 2) for k, v in per.items()}}
cands = yaml.safe_load(open(sys.argv[3], encoding="utf-8"))
base = cands.pop("v1")
results = {}
for name, override in [("v1", {})] + list(cands.items()):
    results[name] = evaluate({**base, **override})
    print(name, json.dumps(results[name]))
out = {"dataset": "CRC-VAL-HE-7K dev sample, 60 tiles per class, AUROC tiles excluded", "n_tiles": int(len(y)), "candidates": results}
open(sys.argv[4], "w", encoding="utf-8").write(json.dumps(out, indent=2) + chr(10))

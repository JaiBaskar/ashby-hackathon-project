"""Tile classifiers: real CONCH zero-shot, or a deterministic demo model for tests and offline work."""

import os

import numpy as np


class ModelConfigError(RuntimeError):
    """The configured model can't run. The server refuses to start rather than fall back to the demo model."""


class ModelBackend:
    name = ""

    def __init__(self, cfg):
        self.classes = cfg["classes"]

    def predict(self, tiles):
        """Class probabilities for a list of RGB tiles: shape [len(tiles), len(classes)], rows sum to 1."""
        raise NotImplementedError


def softmax(logits):
    e = np.exp(logits - logits.max(axis=1, keepdims=True))
    return e / e.sum(axis=1, keepdims=True)


class FakeBackend(ModelBackend):
    """Scores tiles from their mean color: purple → tumor, pink → stroma, white → fat/other. Demo only."""

    name = "fake"

    def predict(self, tiles):
        if not tiles:
            return np.zeros((0, len(self.classes)))
        rgb = np.array([np.asarray(t.convert("RGB"), np.float32).reshape(-1, 3).mean(axis=0) for t in tiles]) / 255
        r, g, b = rgb.T
        bright = rgb.mean(axis=1)
        sat = (rgb.max(axis=1) - rgb.min(axis=1)) / np.maximum(rgb.max(axis=1), 1e-6)
        logits = {
            "tumor": 12 * np.clip(b - g, 0, None) + 3 * (1 - bright),
            "stroma": 10 * np.clip(r - b, 0, None) + 4 * np.clip(r - g, 0, None) * bright,
            "immune": 8 * np.clip(0.4 - bright, 0, None) / 0.4 + (1 - bright),
            "necrosis": 6 * np.clip(r - b, 0, None) * np.clip(1 - 2 * sat, 0, None) + 0.5,
            "normal": np.full(len(tiles), 1.2),
            "fat_other": 8 * np.clip(bright - 0.85, 0, None) / 0.15 + 2 * (1 - sat) * bright,
        }
        return softmax(np.stack([logits[c] for c in self.classes], axis=1))


def pick_device(torch):
    if torch.cuda.is_available():
        return "cuda"
    if torch.backends.mps.is_available():
        return "mps"
    return "cpu"


class ConchBackend(ModelBackend):
    """CONCH zero-shot (AGENTS.md §5): cosine similarity between image and class-prompt embeddings."""

    name = "conch"

    def __init__(self, cfg, token):
        super().__init__(cfg)
        import torch
        from conch.open_clip_custom import create_model_from_pretrained, get_tokenizer, tokenize

        self.torch = torch
        self.batch_size = cfg["batch_size"]
        self.device = pick_device(torch)
        model, self.preprocess = create_model_from_pretrained(
            "conch_ViT-B-16", "hf_hub:MahmoodLab/CONCH", device=self.device, hf_auth_token=token
        )
        self.model = model.eval()
        tokenizer = get_tokenizer()
        with torch.no_grad():
            class_embeddings = []
            for c in self.classes:
                tokens = tokenize(tokenizer, cfg["prompts"][c]).to(self.device)
                emb = self.model.encode_text(tokens).mean(dim=0)  # prompt embeddings come back normalized
                class_embeddings.append(emb / emb.norm())
            self.text = torch.stack(class_embeddings)
            self.logit_scale = self.model.logit_scale.exp()

    def predict(self, tiles):
        torch = self.torch
        out = [np.zeros((0, len(self.classes)))]
        with torch.no_grad():
            for i in range(0, len(tiles), self.batch_size):
                batch = torch.stack([self.preprocess(t.convert("RGB")) for t in tiles[i:i + self.batch_size]])
                emb = self.model.encode_image(batch.to(self.device), proj_contrast=True, normalize=True)
                probs = (self.logit_scale * emb @ self.text.T).softmax(dim=-1)
                out.append(probs.float().cpu().numpy())
        return np.concatenate(out).astype(np.float64)


def cached_hf_token():
    """The token saved by `hf auth login`, if huggingface_hub is installed."""
    try:
        from huggingface_hub import get_token
    except ImportError:
        return None
    return get_token()


def find_hf_token():
    return os.environ.get("HF_TOKEN") or cached_hf_token()


def load_backend(cfg):
    """The model named in config.yaml. Never silently swaps CONCH for the demo model."""
    if cfg["model"] == "fake":
        return FakeBackend(cfg)
    if cfg["model"] != "conch":
        raise ModelConfigError(f"Unknown model '{cfg['model']}' in config.yaml. Use 'conch' or 'fake'.")
    token = find_hf_token()
    if not token:
        raise ModelConfigError(
            "config.yaml asks for model: conch, but no Hugging Face token was found. Set HF_TOKEN "
            "(in .env or the environment) or run `hf auth login`, using an account that accepted the "
            "CONCH license. The server will not fall back to the demo model."
        )
    try:
        return ConchBackend(cfg, token)
    except Exception as e:
        detail = str(e).replace(token, "<token>")
        raise ModelConfigError(
            f"Could not load CONCH ({type(e).__name__}: {detail}). Check that your account has CONCH access and "
            "the weights are downloaded (offline Delta jobs need `hf download MahmoodLab/CONCH` first). "
            "The server will not fall back to the demo model."
        ) from e

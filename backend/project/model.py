"""Tile classifiers: real CONCH zero-shot, or a deterministic demo model for tests and offline work."""

import os

import numpy as np


class ModelConfigError(RuntimeError):
    """The configured model can't run. The server refuses to start rather than fall back to the demo model."""


def prompts_for(cfg, organ):
    """The prompt lists for one organ: the generic prompts, with that organ's overrides on top."""
    organ = organ or cfg["default_organ"]
    if organ not in cfg["organs"]:
        raise ValueError(f"Unknown organ '{organ}'. Choose one of: {', '.join(cfg['organs'])}.")
    override = cfg["organ_prompts"].get(organ, {})
    return {c: override.get(c, cfg["prompts"][c]) for c in cfg["classes"]}


class ModelBackend:
    name = ""

    def __init__(self, cfg):
        self.cfg = cfg
        self.classes = cfg["classes"]

    def embed(self, tiles):
        """One feature row per RGB tile."""
        raise NotImplementedError

    def classify(self, embeddings, organ=None):
        """Class probabilities from embed()'s rows: shape [n, len(classes)], rows sum to 1."""
        raise NotImplementedError

    def predict(self, tiles, organ=None):
        """Class probabilities for a list of RGB tiles, using the organ's prompts."""
        return self.classify(self.embed(tiles), organ)


def softmax(logits):
    e = np.exp(logits - logits.max(axis=1, keepdims=True))
    return e / e.sum(axis=1, keepdims=True)


class FakeBackend(ModelBackend):
    """Scores tiles from their mean color: purple → tumor, pink → stroma, white → fat/other. Demo only.

    The organ is checked but doesn't change the scores."""

    name = "fake"

    def embed(self, tiles):
        if not tiles:
            return np.zeros((0, 3))
        return np.array([np.asarray(t.convert("RGB"), np.float32).reshape(-1, 3).mean(axis=0) for t in tiles]) / 255

    def classify(self, embeddings, organ=None):
        prompts_for(self.cfg, organ)
        rgb = np.asarray(embeddings, float).reshape(-1, 3)
        if len(rgb) == 0:
            return np.zeros((0, len(self.classes)))
        r, g, b = rgb.T
        bright = rgb.mean(axis=1)
        sat = (rgb.max(axis=1) - rgb.min(axis=1)) / np.maximum(rgb.max(axis=1), 1e-6)
        logits = {
            "tumor": 12 * np.clip(b - g, 0, None) + 3 * (1 - bright),
            "stroma": 10 * np.clip(r - b, 0, None) + 4 * np.clip(r - g, 0, None) * bright,
            "immune": 8 * np.clip(0.4 - bright, 0, None) / 0.4 + (1 - bright),
            "necrosis": 6 * np.clip(r - b, 0, None) * np.clip(1 - 2 * sat, 0, None) + 0.5,
            "normal": np.full(len(rgb), 1.2),
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
            self.text = {}  # organ → [n_classes, dim] class embeddings
            for organ in cfg["organs"]:
                prompts = prompts_for(cfg, organ)
                class_embeddings = []
                for c in self.classes:
                    tokens = tokenize(tokenizer, prompts[c]).to(self.device)
                    emb = self.model.encode_text(tokens).mean(dim=0)  # prompt embeddings come back normalized
                    class_embeddings.append(emb / emb.norm())
                self.text[organ] = torch.stack(class_embeddings)
            self.logit_scale = self.model.logit_scale.exp()

    def embed(self, tiles):
        """CONCH image embeddings, [n, 512] float32 (proj_contrast=True, normalize=True; AGENTS.md §4)."""
        torch = self.torch
        out = [np.zeros((0, 512), np.float32)]
        with torch.no_grad():
            for i in range(0, len(tiles), self.batch_size):
                batch = torch.stack([self.preprocess(t.convert("RGB")) for t in tiles[i:i + self.batch_size]])
                emb = self.model.encode_image(batch.to(self.device), proj_contrast=True, normalize=True)
                out.append(emb.float().cpu().numpy())
        return np.concatenate(out)

    def classify(self, embeddings, organ=None):
        torch = self.torch
        organ = organ or self.cfg["default_organ"]
        prompts_for(self.cfg, organ)
        text = self.text[organ]
        with torch.no_grad():
            emb = torch.as_tensor(np.asarray(embeddings, np.float32), device=self.device)
            probs = (self.logit_scale * emb @ text.T.to(emb.dtype)).softmax(dim=-1)
        return probs.float().cpu().numpy().astype(np.float64).reshape(-1, len(self.classes))


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

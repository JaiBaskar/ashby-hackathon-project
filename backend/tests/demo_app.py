"""The API on the demo model, for the Playwright suite: it must run with no GPU, token or weights (AGENTS.md §7)."""

from project.api import create_app as create_api
from project.config import load_config


def create_app():
    return create_api({**load_config(), "model": "fake"})

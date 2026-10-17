"""Phase 8 checks on the real labels.csv (AGENTS.md §8 Phase 1). Run on Delta after `python -m project.tcga labels`:
    TCGA_DIR=/work/nvme/bfqi/$USER/tcga python -m pytest backend -m delta -v
"""

import pandas as pd
import pytest

from project.config import load_config
from project.labels import check_labels
from project.tcga import tcga_dir

pytestmark = pytest.mark.delta


def test_real_labels_follow_every_phase_1_rule():
    cfg = load_config()
    path = tcga_dir(cfg) / "labels.csv"
    if not path.exists():
        pytest.fail(f"{path} not found. Build it with `python -m project.tcga labels` (set TCGA_DIR on Delta).")
    labels = pd.read_csv(path)
    check_labels(labels, cfg["tcga"])  # unique slides, sample_id regex, 0–100, median > 1, no missing,
    #                                    no hospital in two splits, enough test slides and test slides below 60%
    assert labels["selected"].any()

import pytest

from project.metrics import auroc


def test_auroc_hand_computed():
    # Positives 0.35 and 0.8 vs negatives 0.1 and 0.4: 3 of 4 pairs ranked right → 0.75.
    assert auroc([0, 0, 1, 1], [0.1, 0.4, 0.35, 0.8]) == pytest.approx(0.75)


def test_auroc_counts_ties_as_half():
    # Pairs: (0.5 vs 0.5) tie = 0.5, (0.5 vs 0.2) = 1, (0.9 vs 0.5) = 1, (0.9 vs 0.2) = 1 → 3.5 / 4.
    assert auroc([0, 1, 0, 1], [0.5, 0.5, 0.2, 0.9]) == pytest.approx(0.875)


def test_auroc_perfect_and_reversed():
    assert auroc([0, 0, 1], [0.1, 0.2, 0.9]) == 1.0
    assert auroc([1, 1, 0], [0.1, 0.2, 0.9]) == 0.0


def test_auroc_needs_both_classes():
    with pytest.raises(ValueError):
        auroc([1, 1], [0.2, 0.3])

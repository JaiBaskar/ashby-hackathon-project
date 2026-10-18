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


# --- Phase 8: purity metrics (AGENTS.md §1, §8 Phase 5) ------------------------------------------

from project.metrics import bootstrap_mae_diff, catch_rate, mae, pearson_r, verdict


def test_mae_hand_computed():
    # |50-60| + |70-65| + |30-30| = 10 + 5 + 0 → 15 / 3 = 5 points.
    assert mae([50, 70, 30], [60, 65, 30]) == pytest.approx(5.0)


def test_pearson_hand_computed():
    # x = 1,2,3; y = 1,2,4. dx = -1,0,1; dy = -4/3,-1/3,5/3. Σdxdy = 3, Σdx² = 2, Σdy² = 42/9.
    # r = 3 / sqrt(2 × 42/9) = 3 / 3.05505 = 0.98198.
    assert pearson_r([1, 2, 3], [1, 2, 4]) == pytest.approx(0.98198, abs=1e-5)
    assert pearson_r([1, 2, 3], [3, 2, 1]) == pytest.approx(-1.0)


def test_catch_rate_hand_computed():
    # Truth below 60: 40, 55, 59.9 (60 itself is not below). Their predictions 50, 65, 59 → 2 of 3 caught.
    truth = [40, 55, 70, 59.9, 60]
    pred = [50, 65, 40, 59, 58]
    assert catch_rate(truth, pred, cutoff=60) == pytest.approx(2 / 3)


def test_catch_rate_needs_a_slide_below_cutoff():
    with pytest.raises(ValueError):
        catch_rate([70, 80], [50, 50], cutoff=60)


def test_bootstrap_constant_gap_is_exact():
    # The app is always right and the pathologist always 10 points off: every resample gives
    # pathologist MAE − app MAE = 10 − 0 = 10, so the interval is (10, 10) and the app is "better".
    truth = [20, 35, 50, 65, 80, 90]
    out = bootstrap_mae_diff(truth, [t + 10 for t in truth], truth, n=1000, seed=1)
    assert out["diff"] == pytest.approx(10.0)
    assert out["ci_low"] == pytest.approx(10.0) and out["ci_high"] == pytest.approx(10.0)
    assert out["n"] == 1000
    assert verdict(out["ci_low"], out["ci_high"]) == "better"


def test_bootstrap_identical_methods_are_comparable():
    truth = [20, 35, 50, 65, 80]
    pred = [25, 30, 55, 60, 85]
    out = bootstrap_mae_diff(truth, pred, pred, n=200, seed=1)
    assert out["ci_low"] == 0.0 and out["ci_high"] == 0.0
    assert verdict(out["ci_low"], out["ci_high"]) == "comparable"


def test_bootstrap_is_seeded():
    rng_truth = [10, 30, 45, 60, 75, 90, 20, 50]
    path = [30, 25, 60, 70, 70, 95, 40, 45]
    app = [15, 35, 40, 55, 80, 85, 30, 60]
    a = bootstrap_mae_diff(rng_truth, path, app, n=500, seed=7)
    b = bootstrap_mae_diff(rng_truth, path, app, n=500, seed=7)
    assert a == b
    assert a["ci_low"] <= a["diff"] <= a["ci_high"]


def test_verdict_needs_the_interval_to_exclude_zero():
    assert verdict(0.5, 4.0) == "better"
    assert verdict(-0.5, 4.0) == "comparable"
    assert verdict(0.0, 4.0) == "comparable"
    assert verdict(-4.0, -0.5) == "worse"


import numpy as np

from project.metrics import within_between_r


def test_within_and_between_hospital_correlation_hand_computed():
    # Hospital A: truth 10, 20 (mean 15); B: 50, 70 (mean 60). Pred A: 12, 18 (15); B: 60, 64 (62).
    # Within: centered truth −5, 5, −10, 10; centered pred −3, 3, −2, 2.
    # Σxy = 15 + 15 + 20 + 20 = 70; Σx² = 250; Σy² = 26 → r = 70 / sqrt(6500) = 0.86824.
    # Between: hospital means (15, 60) vs (15, 62): two points on a rising line → r = 1.
    out = within_between_r([10, 20, 50, 70], [12, 18, 60, 64], ["A", "A", "B", "B"])
    assert out["within_hospital_r"] == pytest.approx(0.86824, abs=1e-5)
    assert out["between_hospital_r"] == pytest.approx(1.0)
    assert out["n_hospitals_within"] == 2


def test_a_hospital_lookup_has_no_within_hospital_signal():
    # Predicting each hospital's average truth, plus noise unrelated to the slide, tracks hospitals only.
    rng = np.random.default_rng(0)
    hospitals = np.repeat(list("ABCDEFGH"), 15)
    level = dict(zip("ABCDEFGH", rng.uniform(20, 80, 8)))
    truth = np.array([level[h] for h in hospitals]) + rng.normal(0, 10, len(hospitals))
    pred = np.array([level[h] for h in hospitals]) + rng.normal(0, 3, len(hospitals))
    out = within_between_r(truth, pred, hospitals)
    assert abs(out["within_hospital_r"]) < 0.25
    assert out["between_hospital_r"] > 0.9


def test_single_slide_hospitals_are_left_out_of_within():
    # A has 3 slides on a rising line (centred: −10, 0, 10 vs −10, 0, 10 → r = 1); B and C have one slide each.
    out = within_between_r([10, 20, 30, 50, 60], [11, 21, 31, 90, 5], ["A", "A", "A", "B", "C"])
    assert out["n_hospitals_within"] == 1 and out["within_hospital_r"] == pytest.approx(1.0)


from project.metrics import bootstrap_r_diff


def test_r_difference_bootstrap_identical_methods_is_zero():
    truth = [10, 25, 40, 55, 70, 85]
    pred = [15, 20, 45, 50, 75, 80]
    out = bootstrap_r_diff(truth, pred, pred, n=200, seed=1)
    assert out["diff"] == 0.0 and out["ci_low"] == 0.0 and out["ci_high"] == 0.0 and out["n"] == 200


def test_r_difference_bootstrap_point_value_and_seed():
    # a tracks truth exactly (r = 1); b is reversed (r = −1): r(a) − r(b) = 2 on every resample with ≥ 2 values.
    truth = [10.0, 20, 30, 40, 50, 60, 70, 80]
    a, b = truth, truth[::-1]
    out = bootstrap_r_diff(truth, a, b, n=300, seed=4)
    assert out["diff"] == pytest.approx(2.0)
    assert out["ci_low"] == pytest.approx(2.0) and out["ci_high"] == pytest.approx(2.0)
    rng_truth = [10, 30, 45, 60, 75, 90, 20, 50]
    x, y = [12, 28, 50, 58, 70, 95, 25, 40], [30, 25, 60, 70, 70, 95, 40, 45]
    assert bootstrap_r_diff(rng_truth, x, y, n=300, seed=4) == bootstrap_r_diff(rng_truth, x, y, n=300, seed=4)


def test_r_difference_bootstrap_with_constant_truth_is_undefined_not_an_error():
    out = bootstrap_r_diff([50, 50, 50, 50], [10, 20, 30, 40], [40, 30, 20, 10], n=50, seed=1)
    assert np.isnan(out["diff"]) and np.isnan(out["ci_low"]) and np.isnan(out["ci_high"])

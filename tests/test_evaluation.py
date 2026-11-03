import math

from birdbrain.evaluation import paired, sign_flip_p


def test_sign_flip_p_is_exact_for_small_samples():
    assert sign_flip_p([1, 1, 1, 1]) == 2 / 16
    assert sign_flip_p([0, 0]) == 1.0


def test_paired_comparison_matches_seeds():
    a = {s: {"seed": s, "inBasket": 4} for s in range(5)}
    b = {s: {"seed": s, "inBasket": 4 + (s % 2)} for s in range(1, 6)}
    r = paired(a, b, "inBasket")
    assert r["n"] == 4 and r["only_a"] == [0] and r["only_b"] == [5]
    assert math.isclose(r["diff"], 0.5) and r["wins"] == 2 and r["ties"] == 2

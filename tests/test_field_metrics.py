from bibraeval.field_metrics import exact, levenshtein


def test_fuzzy_match_reorders_predicted_values_by_similarity() -> None:
    metric = levenshtein()

    gt_values, predicted_values = metric._match(
        ["Wolfgang Borchert", "Rowohlt"], ["Rowolt", "Wolfgang Borchert"]
    )

    assert gt_values == ["Wolfgang Borchert", "Rowohlt"]
    assert predicted_values == ["Wolfgang Borchert", "Rowolt"]


def test_fuzzy_match_handles_best_match_in_last_position() -> None:
    metric = levenshtein()

    gt_values, predicted_values = metric._match(
        ["Bronstein", "Semendjajew", "Musiol", "Mühling"],
        ["K.A. Semendjajev", "I.N. Bronstein", "Mühling", "Nowak"],
        threshold=0.0,
    )

    assert gt_values == ["Bronstein", "Semendjajew", "Musiol", "Mühling"]
    assert predicted_values == [
        "I.N. Bronstein",
        "K.A. Semendjajev",
        "Nowak",
        "Mühling",
    ]


def test_fuzzy_match_leaves_below_threshold_values_unmatched() -> None:
    metric = levenshtein()

    gt_values, predicted_values = metric._match(["apple"], ["appld"], threshold=0.81)

    assert gt_values == ["apple", None]
    assert predicted_values == [None, "appld"]


def test_exact_match_reorders_predicted_values_by_similarity() -> None:
    metric = exact()

    gt_values, predicted_values = metric._match(
        ["Wolfgang Borchert", "Rowohlt"], ["Rowolt", "Wolfgang Borchert"]
    )

    assert gt_values == ["Wolfgang Borchert", "Rowohlt", None]
    assert predicted_values == ["Wolfgang Borchert", None, "Rowolt"]


def test_exact_match_scores_reordered_list_values() -> None:
    metric = exact()

    score = metric.score(
        ["Wolfgang Borchert", "Rowohlt"], ["Rowohlt", "Wolfgang Borchert"]
    )

    assert score == 1.0


def test_exact_match_penalizes_unmatched_list_values() -> None:
    metric = exact()

    score = metric.score(["Wolfgang Borchert", "Rowohlt"], ["Wolfgang Borchert"])

    # prec: 1.0, rec: 1/2, f1: 2/3
    assert score == 2 / 3


def test_levenshtein_match_scalar_values() -> None:

    metric = levenshtein(threshold=0.8)

    score = metric.score("apple", "appld")

    assert score == 0.8


def test_levenshtein_match_list_values() -> None:

    metric = levenshtein(threshold=0.8)

    score = metric.score(["apple", "banana"], ["appld", "banan"])
    print(score)
    assert score > 0.0
    assert score < 1.0


def test_exact_any_of_scores_one_if_any_value_matches() -> None:
    metric = exact(list_comparison="any-of")

    assert metric.score(["Wolfgang Borchert", "Rowohlt"], ["Rowohlt", "x"]) == 1.0
    assert metric.score(["Wolfgang Borchert"], ["Rowohlt"]) == 0.0


def test_levenshtein_any_of_returns_best_pair_score() -> None:
    metric = levenshtein(threshold=0.8, list_comparison="any-of")

    assert metric.score(["apple", "kiwi"], ["appld", "zzzz"]) == 0.8


def test_any_of_with_empty_list_scores_zero() -> None:
    assert exact(list_comparison="any-of").score([], ["Rowohlt"]) == 0.0
    assert levenshtein(list_comparison="any-of").score(["Rowohlt"], []) == 0.0

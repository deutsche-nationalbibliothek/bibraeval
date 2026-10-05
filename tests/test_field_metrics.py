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
        threshold = 0.0
    )

    assert gt_values == ["Bronstein", "Semendjajew", "Musiol", "Mühling"]
    assert predicted_values == ["I.N. Bronstein", "K.A. Semendjajev", "Nowak", "Mühling"]


def test_fuzzy_match_leaves_below_threshold_values_unmatched() -> None:
    metric = levenshtein()

    gt_values, predicted_values = metric._match(
        ["apple"], ["appld"], threshold=0.81
    )

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
    assert score == 2/3


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

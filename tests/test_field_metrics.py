from bibraeval.field_metrics import exactMatch, levenshteinMatch


def test_fuzzy_match_reorders_predicted_values_by_similarity() -> None:
    metric = exactMatch()

    gold_values, predicted_values = metric._fuzzy_match(
        ["Wolfgang Borchert", "Rowohlt"], ["Rowohlt", "Wolfgang Borchert"]
    )

    assert gold_values == ["Wolfgang Borchert", "Rowohlt"]
    assert predicted_values == ["Wolfgang Borchert", "Rowohlt"]


def test_exact_match_scores_reordered_list_values() -> None:
    metric = exactMatch()

    score = metric.score(
        ["Wolfgang Borchert", "Rowohlt"], ["Rowohlt", "Wolfgang Borchert"]
    )

    assert score == 1.0


def test_exact_match_penalizes_unmatched_list_values() -> None:
    metric = exactMatch()

    score = metric.score(["Wolfgang Borchert", "Rowohlt"], ["Wolfgang Borchert"])

    assert score == 0.5


def test_levenshtein_match_scalar_values() -> None:

    metric = levenshteinMatch()

    score = metric.score("apple", "appld")

    assert score == 0.8


def test_levenshtein_match_list_values() -> None:

    metric = levenshteinMatch()

    score = metric.score(["apple", "banana"], ["appld", "banan"])
    print(score)
    assert score > 0.0
    assert score < 1.0

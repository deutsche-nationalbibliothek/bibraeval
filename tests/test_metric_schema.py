import pytest
from pydantic import ValidationError

from bibraeval.field_metrics import exact, levenshtein
from bibraeval.metric_schema import field_metric_schema

FIELD_METRICS = {
    "title": {"metric": "levenshtein", "match_threshold": 0.7, "weight": 2.0},
    "year": {"metric": "exact"},
    "authors": {
        "metric": "levenshtein",
        "match_threshold": 0.7,
        "weight": 1.5,
        "list_comparison": "any-of",
    },
}


def test_from_dict_accepts_flat_and_nested_mapping() -> None:
    flat = field_metric_schema.from_dict(FIELD_METRICS)
    nested = field_metric_schema.from_dict({"fields": FIELD_METRICS})

    assert flat == nested
    assert flat.fields["title"].weight == 2.0
    assert flat.fields["year"].weight == 1.0
    assert flat.fields["year"].list_comparison == "all-of"


def test_from_yaml_loads_field_metrics(tmp_path) -> None:
    path = tmp_path / "field-metrics.yaml"
    path.write_text(
        """
fields:
  title:
    metric: "levenshtein"
    match_threshold: 0.7
    weight: 2.0
  year:
    metric: "exact"
    weight: 1.0
  authors:
    metric: "levenshtein"
    match_threshold: 0.7
    weight: 1.5
    list_comparison: "any-of"
""",
        encoding="utf-8",
    )

    assert field_metric_schema.from_yaml(path) == field_metric_schema.from_dict(
        FIELD_METRICS
    )


@pytest.mark.parametrize(
    "config",
    [
        {"metric": "binary"},
        {"metric": "levenshtein"},
        {"metric": "levenshtein", "match_threshold": 1.5},
        {"metric": "exact", "match_threshold": 0.7},
        {"metric": "exact", "weight": -1.0},
        {"metric": "exact", "list_comparison": "none-of"},
        {"metric": "exact", "unknown": True},
    ],
)
def test_invalid_field_config_raises(config: dict) -> None:
    with pytest.raises(ValidationError):
        field_metric_schema.from_dict({"title": config})


def test_build_metric_instantiates_configured_metric() -> None:
    schema = field_metric_schema.from_dict(FIELD_METRICS)

    title_metric = schema.build_metric("title")
    authors_metric = schema.build_metric("authors")
    year_metric = schema.build_metric("year")

    assert isinstance(title_metric, levenshtein)
    assert title_metric.threshold == 0.7
    assert title_metric.list_comparison == "all-of"
    assert isinstance(authors_metric, levenshtein)
    assert authors_metric.list_comparison == "any-of"
    assert isinstance(year_metric, exact)

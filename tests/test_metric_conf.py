import pytest
import yaml
from pydantic import ValidationError

from bibraeval.field_metrics import Exact, Levenshtein
from bibraeval.metric_conf import FieldMetricMapping

FIELD_METRICS = {
    "title": {"metric": "Levenshtein", "match_threshold": 0.7, "weight": 2.0},
    "year": {"metric": "Exact"},
    "authors": {
        "metric": "Levenshtein",
        "match_threshold": 0.7,
        "weight": 1.5,
        "list_comparison": "any-of",
    },
}


def test_from_dict_accepts_flat_and_nested_mapping() -> None:
    flat = FieldMetricMapping.from_dict(FIELD_METRICS)
    nested = FieldMetricMapping.from_dict({"fields": FIELD_METRICS})

    assert flat == nested
    assert flat.fields["title"].weight == 2.0
    assert flat.fields["year"].weight == 1.0
    assert flat.fields["year"].list_comparison == "all-of"


@pytest.mark.parametrize("metric_name", ["Levenshtein", "levenshtein"])
def test_from_yaml_loads_field_metrics(tmp_path, metric_name: str) -> None:
    path = tmp_path / "field-metrics.yaml"
    expected = {
        field_name: {**config, "metric": metric_name}
        if config["metric"] == "Levenshtein"
        else config
        for field_name, config in FIELD_METRICS.items()
    }
    path.write_text(yaml.safe_dump({"fields": expected}), encoding="utf-8")
    assert FieldMetricMapping.from_yaml(path) == FieldMetricMapping.from_dict(expected)


@pytest.mark.parametrize(
    "config",
    [
        {"metric": "binary"},
        {"metric": "Levenshtein"},
        {"metric": "levenshtein"},
        {"metric": "Levenshtein", "match_threshold": 1.5},
        {"metric": "levenshtein", "match_threshold": 1.5},
        {"metric": "Exact", "match_threshold": 0.7},
        {"metric": "Exact", "weight": -1.0},
        {"metric": "Exact", "list_comparison": "none-of"},
        {"metric": "Exact", "unknown": True},
    ],
)
def test_invalid_field_config_raises(config: dict) -> None:
    with pytest.raises(ValidationError):
        FieldMetricMapping.from_dict({"title": config})


@pytest.mark.parametrize("metric_name", ["Levenshtein", "levenshtein"])
def test_build_metric_instantiates_configured_metric(metric_name: str) -> None:
    field_metrics = {
        field_name: {**config, "metric": metric_name}
        if config["metric"] == "Levenshtein"
        else config
        for field_name, config in FIELD_METRICS.items()
    }
    schema = FieldMetricMapping.from_dict(field_metrics)

    title_metric = schema.build_metric("title")
    authors_metric = schema.build_metric("authors")
    year_metric = schema.build_metric("year")

    assert isinstance(title_metric, Levenshtein)
    assert title_metric.threshold == 0.7
    assert title_metric.list_comparison == "all-of"
    assert isinstance(authors_metric, Levenshtein)
    assert authors_metric.list_comparison == "any-of"
    assert isinstance(year_metric, Exact)

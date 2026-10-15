# Configuring metrics

BIBRA-Eval requires records that follow a specific JSON-scheme. Built on top
of the record scheme is an evaluation scheme, that specifies the fields
that should be part of the comparison and the metrics that apply to each field.

Pass a flat field mapping, a `FieldMetricMapping`, or a YAML path as
`field_metric_config`. When a mapping is supplied, fields not listed in it are
not scored. Without a mapping, all fields from the validated metadata are
scored with `Exact` and weight `1.0`.

```python
field_metrics = {
    "title": {
        "metric": "levenshtein",
        "match_threshold": 0.75,
        "weight": 2.0,
    },
    "year": {"metric": "exact"},
    "authors": {
        "metric": "levenshtein",
        "match_threshold": 0.7,
        "weight": 1.5,
        "list_comparison": "all-of",
    },
}

evaluator = Evaluator(
    "data/gold.jsonl",
    "data/predictions.jsonl",
    PublicationMetadata,
    field_metric_config=field_metrics,
)
```

Metric names are case-insensitive `exact`/`Exact` or
`levenshtein`/`Levenshtein`. Weights must be positive. Levenshtein requires a
`match_threshold` from 0 through 1; Exact does not accept one.

## Scalar values

`Exact` returns 1 for equal values and 0 otherwise. `Levenshtein` returns the
normalized Levenshtein similarity ratio. The threshold does not turn a scalar
score into a binary decision.

## List values

For lists, the metric first aligns entries one-to-one. `Exact` aligns equal
entries; `Levenshtein` prioritizes exact matches and then uses a global
similarity-based assignment, leaving pairs below `match_threshold` unmatched.
The alignment similarity uses `SequenceMatcher`; agreement for aligned pairs
uses the configured scalar metric.

`all-of` computes a precision/recall/F1-style score across matched and
unmatched entries, so missing or extra entries affect the result. `any-of`
returns the highest scalar agreement among aligned pairs and is useful when one
matching item is sufficient. Empty or entirely unmatched lists score 0.

## YAML configuration

The mapping may be written flat or under a `fields` key:

```yaml
fields:
  title:
    metric: levenshtein
    match_threshold: 0.75
    weight: 2.0
  year:
    metric: exact
```

Pass the path directly as `field_metric_config="field-metrics.yaml"`.
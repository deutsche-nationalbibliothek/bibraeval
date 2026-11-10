# Configuring metrics

BIBRA-Eval uses two separate configurations:

- Metadata schema: A Pydantic `BaseModel` defining the structure and data types of the metadata records.

- Metric configuration: A `FieldMetricMapping` defining which metadata fields are evaluated and which comparison metric, matching threshold, list comparison strategy, and weight are applied to each field.

Pass a flat field mapping, a `FieldMetricMapping`, or a YAML path as `field_metric_config`. 

When a metric configuration is supplied, fields not listed in it are not scored. 
Without a metric configuration, all fields from the validated metadata are scored with the default `Exact` comparison metric and a uniform weight of `1.0`.

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

Metric names are case-insensitive `exact`/`Exact` or `levenshtein`/`Levenshtein`. 
Weights must be positive. 
Levenshtein requires a `match_threshold` from 0 through 1; Exact does not accept one.

## Scalar values

`Exact` returns 1 for equal values and 0 otherwise. 
`Levenshtein` returns the normalized Levenshtein similarity ratio. The threshold does not turn a scalar score into a binary decision.

## List values

For lists, the metric first aligns entries one-to-one. 
- `Exact` aligns equal entries; 
- `Levenshtein` prioritizes exact matches and then uses a global similarity-based assignment, leaving pairs below `match_threshold` unmatched.
- The alignment similarity uses [difflibs `SequenceMatcher`](https://docs.python.org/3/library/difflib.html).

Once list alignment is established, agreement for aligned pairs is measured with the configured scalar metric (Levenshtein ratio).

- `all-of` computes a precision/recall/F1-style score across matched and unmatched entries, so missing or extra entries affect the result. 
- `any-of` returns the highest scalar agreement among aligned pairs and is useful when one
matching item is sufficient. 

Empty or entirely unmatched lists score 0.

## YAML configuration

The metric configuration may be written flat or under a `fields` key:

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

## Example

Try out this example:

```python
from pydantic import BaseModel, ConfigDict, Field
from bibraeval.comparator import Comparator
from bibraeval.data_ingester import RecordCollection


class PublicationMetadata(BaseModel):
    """Response model for publication metadata extraction."""

    model_config = ConfigDict(populate_by_name=True)

    language: list[str] = Field(default_factory=list)
    title: str | None = None
    year: str | None = None
    authors: list[str] = Field(default_factory=list)
    p_isbn: list[str] = Field(default_factory=list, alias="p-isbn")


field_metric_config = {
    "title": {"metric": "Levenshtein", "match_threshold": 0.7, "weight": 2.0},
    "year": {"metric": "Exact", "weight": 1.0},
    "authors": {
        "metric": "Levenshtein",
        "match_threshold": 0.7,
        "weight": 1.5,
        "list_comparison": "all-of",
    },
    "p-isbn": {"metric": "Exact", "weight": 1.0},
    "language": {
        "metric": "Levenshtein",
        "match_threshold": 0.6,
        "weight": 1.0,
        "list_comparison": "all-of",
    },
}

ground_truth = RecordCollection[PublicationMetadata]()
ground_truth.add_payload(
    doc_id="123",
    payload={
        "title": "Epic work on subject indexing",
        "authors": ["Librarian, The"],
        "language": ["eng"],
    },
    schema=PublicationMetadata,
)

ground_truth.add_payload(
    doc_id="007",
    payload={
        "title": "Struggles of modern library systems - A Collection",
        "authors": ["Musterperson, Maxi", "Doe, John"],
        "year": "1915",
        "language": ["ger", "eng"],
    },
    schema=PublicationMetadata,
)

predictions = RecordCollection[PublicationMetadata]()
predictions.add_payload(
    doc_id="123",
    payload={
        "title": "_Epic work on subject indexing_",
        "authors": ["Librarian, A"],
        "language": ["eng"],
    },
    schema=PublicationMetadata,
)

predictions.add_payload(
    doc_id="007",
    payload={
        "title": "Struggles of modern library systems",
        "year": "2026",
        "authors": ["Musterperson", "Doe"],
        "language": ["german", "eng"],
        "p-isbn": ["978-3-86539-327-2"],
    },
    schema=PublicationMetadata,
)


comp = Comparator(
    ground_truth,
    predictions,
    metric_schema=field_metric_config,
    drop_mismatched_doc_ids=True,
)

comp.compute_cell_agreement()
```

```text
shape: (10, 8)
┌────────┬────────────┬────────────┬─────────────┬─────────────┬─────────────┬────────────┬────────┐
│ doc_id ┆ field_name ┆ gt_present ┆ pred_presen ┆ gt_value    ┆ pred_value  ┆ cell_agree ┆ weight │
│ ---    ┆ ---        ┆ ---        ┆ t           ┆ ---         ┆ ---         ┆ ment       ┆ ---    │
│ str    ┆ str        ┆ bool       ┆ ---         ┆ object      ┆ object      ┆ ---        ┆ f64    │
│        ┆            ┆            ┆ bool        ┆             ┆             ┆ f64        ┆        │
╞════════╪════════════╪════════════╪═════════════╪═════════════╪═════════════╪════════════╪════════╡
│ 007    ┆ authors    ┆ true       ┆ true        ┆ ['Musterper ┆ ['Musterper ┆ 0.421053   ┆ 1.5    │
│        ┆            ┆            ┆             ┆ son, Maxi', ┆ son',       ┆            ┆        │
│        ┆            ┆            ┆             ┆ 'Doe, J…    ┆ 'Doe']      ┆            ┆        │
│ 007    ┆ language   ┆ true       ┆ true        ┆ ['ger',     ┆ ['german',  ┆ 0.909091   ┆ 1.0    │
│        ┆            ┆            ┆             ┆ 'eng']      ┆ 'eng']      ┆            ┆        │
│ 007    ┆ p-isbn     ┆ false      ┆ true        ┆ []          ┆ ['978-3-865 ┆ 0.0        ┆ 1.0    │
│        ┆            ┆            ┆             ┆             ┆ 39-327-2']  ┆            ┆        │
│ 007    ┆ title      ┆ true       ┆ true        ┆ Struggles   ┆ Struggles   ┆ 0.823529   ┆ 2.0    │
│        ┆            ┆            ┆             ┆ of modern   ┆ of modern   ┆            ┆        │
│        ┆            ┆            ┆             ┆ library sy… ┆ library sy… ┆            ┆        │
│ 007    ┆ year       ┆ true       ┆ true        ┆ 1915        ┆ 2026        ┆ 0.0        ┆ 1.0    │
│ 123    ┆ authors    ┆ true       ┆ true        ┆ ['Librarian ┆ ['Librarian ┆ 0.916667   ┆ 1.5    │
│        ┆            ┆            ┆             ┆ , The']     ┆ , A']       ┆            ┆        │
│ 123    ┆ language   ┆ true       ┆ true        ┆ ['eng']     ┆ ['eng']     ┆ 1.0        ┆ 1.0    │
│ 123    ┆ p-isbn     ┆ false      ┆ false       ┆ []          ┆ []          ┆ 0.0        ┆ 1.0    │
│ 123    ┆ title      ┆ true       ┆ true        ┆ Epic work   ┆ _Epic work  ┆ 0.966667   ┆ 2.0    │
│        ┆            ┆            ┆             ┆ on subject  ┆ on subject  ┆            ┆        │
│        ┆            ┆            ┆             ┆ indexing    ┆ indexing…   ┆            ┆        │
│ 123    ┆ year       ┆ false      ┆ false       ┆ null        ┆ null        ┆ 1.0        ┆ 1.0    │
└────────┴────────────┴────────────┴─────────────┴─────────────┴─────────────┴────────────┴────────┘
```
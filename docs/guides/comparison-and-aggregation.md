# Comparing and aggregating

`Comparator` exposes the per-document, per-field comparison matrix. Its base
columns are `doc_id`, `field_name`, `gt_present`, `pred_present`, `gt_value`,
and `pred_value`. `compute_cell_agreement()` adds `cell_agreement` and
`weight`; with a field metric mapping, only configured fields are returned.

```python
from bibraeval import Aggregator, Comparator, RecordCollection

ground_truth = RecordCollection.create_from_file("gold.jsonl", PublicationMetadata)
predictions = RecordCollection.create_from_file(
    "predictions.jsonl", PublicationMetadata
)
comparator = Comparator(ground_truth, predictions, metric_schema=field_metrics)
matrix = comparator.comparison_matrix
scored_cells = comparator.compute_cell_agreement()
```

Presence is separate from agreement. `None`, an empty string, and an empty
list are absent; `0` and `False` as field content are counted as "present".
A prediction without a gold value contributes zero precision and no recall
observation. A gold value without a prediction contributes zero recall and
no precision observation. When both sides are absent, neither precision
nor recall has an observation.

## Aggregation modes

Create an `Aggregator` from the comparator, then compute intermediate results
and summarize them:

```python
aggregator = Aggregator(comparator)
intermediate = aggregator.compute_intermediate_results("field_name")
summary = aggregator.summarise_results(intermediate)
```

- `doc-avg`: compute weighted field precision and recall within each document,
  derive document F1, then average document results.
- `field-avg`: compute precision, recall, and F1 per field across documents,
  then average fields using their configured weights.
- `micro-avg`: pool cell-level precision and recall before deriving F1.

`Evaluator` uses `field-avg` by default. Its `mode` accepts exactly
`doc-avg`, `field-avg`, or `micro-avg`. For the lower-level `Aggregator`, use
`group_by="doc_id"` for document averaging, `group_by="field_name"` for field
averaging, and `group_by=None` for an overall micro average.

Summary rows contain `metric`, `mode`, `value`, and `support`, plus any strata
columns. Support describes the observations contributing to a result; it can
be fractional for weighted field summaries.

## Example

BIBRA-Eval allows specification of custom Metadata Schemas and a custom schema
to define metrics per field. List-Type fields are matched on a fuzzy 
matching principle, that can be adjusted with a custom `match_threshold`. 
Lists can be compared in two modes: "all-of" counts all values in ground_truth
and predictions and computes an f1-score between both.
"any-of" only return the best match. 
E.g. if language is a field that can have multiple values, "any-of" comparison 
would only require for one of the values to be found, whereas "all-of" 
requires all values to be found.

```python
from pydantic import BaseModel, ConfigDict, Field
from bibraeval.comparator import Comparator


class PublicationMetadata(BaseModel):
    """Response model for publication metadata extraction."""

    model_config = ConfigDict(populate_by_name=True)

    language: list[str] = Field(default_factory=list)
    title: str | None = None
    year: str | None = None
    authors: list[str] = Field(default_factory=list)
    p_isbn: list[str] = Field(default_factory=list, alias="p-isbn")


FieldMetricMapping = {
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
    metric_schema=FieldMetricMapping,
    drop_mismatched_doc_ids=True,
)

comp.comparison_matrix

comp.compute_cell_agreement()
```

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
# Quick start

Define the metadata fields to validate, then use `Evaluator` to load both
datasets and compute a summary. Each input can be a JSON directory or JSONL
file; see [Preparing inputs](inputs.md) for their exact formats.

```python
from pydantic import BaseModel

from bibraeval import Evaluator


class PublicationMetadata(BaseModel):
    title: str | None = None
    year: str | None = None
    authors: list[str] = []


evaluator = Evaluator(
    gt_path="data/gold.jsonl",
    pred_path="data/predictions.jsonl",
    schema=PublicationMetadata,
    mode="field-avg",
)

summary = evaluator.compute_metrics()
print("Summary Metrics:")
print(summary)

intermediate_results = evaluator.get_intermediate_results()
print("Intermediate Results:")
print(intermediate_results)

comparison_matrix = evaluator.get_comparison_matrix()
print("Comparison Matrix:")
print(comparison_matrix)
```

The default metric is exact matching with uniform field weights. Configure
fuzzy matching and weights with `field_metric_config`; choose `doc-avg`,
`field-avg`, or `micro-avg` with `mode`. These modes have the following meaning:

- `doc-avg` document macro-average: compute average result per doc first (along
     all fields), then compute average across documents
- `field-avg` field macro-average: compute average results per field (along all
     documents), then compute average across all fields
- `micro` micro-average: direct pooling of field-to-field results in one score

Summary: evaluator.compute_metrics() returns Polars DataFrame in long form, with 
a row for each metric and columns `metric`, `mode`, `value`,and `support`. 
Here, `support` refers to the

- average number of documents that contributed to the metric per field (for
    mode `field-avg`)
- exact number of documents that contributed to the document average (for mode
    `doc-avg`)
- the number of (doc, field) tuples that contributed to the micro average (for
    mode `micro`)

Intermediate results: evaluator.get_intermediate_results() returns Polars DataFrame,
with a row for each field for `field-avg`, or a row for each document for `doc-avg`.
Columns are `support_prec`, `prec`, `support_rec`, `rec`, and `f1`.

Comparison matrix: evaluator.get_comparison_matrix() returns Polars DataFrame,
with a row for each document and field and columns `doc_id`, `field_name`, 
`gt_present`, `pred_present`, `gt_value`, `pred_value`, `cell_agreement` and `weight`.

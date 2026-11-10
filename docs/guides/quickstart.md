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
    authors: list[str] = Field(default_factory=list)


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

```text
Summary Metrics:
shape: (3, 4)
┌────────┬───────────┬──────────┬─────────┐
│ metric ┆ mode      ┆ value    ┆ support │
│ ---    ┆ ---       ┆ ---      ┆ ---     │
│ str    ┆ str       ┆ f64      ┆ f64     │
╞════════╪═══════════╪══════════╪═════════╡
│ f1     ┆ field-avg ┆ 0.431682 ┆ 43.8    │
│ prec   ┆ field-avg ┆ 0.460207 ┆ 39.8    │
│ rec    ┆ field-avg ┆ 0.411724 ┆ 43.0    │
└────────┴───────────┴──────────┴─────────┘
```
```text
Intermediate Results:
shape: (5, 7)
┌────────────┬──────────────┬──────────┬─────────────┬──────────┬────────┬──────────┐
│ field_name ┆ support_prec ┆ prec     ┆ support_rec ┆ rec      ┆ weight ┆ f1       │
│ ---        ┆ ---          ┆ ---      ┆ ---         ┆ ---      ┆ ---    ┆ ---      │
│ str        ┆ u32          ┆ f64      ┆ u32         ┆ f64      ┆ f64    ┆ f64      │
╞════════════╪══════════════╪══════════╪═════════════╪══════════╪════════╪══════════╡
│ alt_title  ┆ 29           ┆ 0.214891 ┆ 27          ┆ 0.230809 ┆ 1.0    ┆ 0.222566 │
│ creator    ┆ 46           ┆ 0.337738 ┆ 44          ┆ 0.353089 ┆ 1.0    ┆ 0.345243 │
│ publisher  ┆ 46           ┆ 0.471997 ┆ 48          ┆ 0.452331 ┆ 1.0    ┆ 0.461955 │
│ title      ┆ 45           ┆ 0.579438 ┆ 48          ┆ 0.543224 ┆ 1.0    ┆ 0.560747 │
│ year       ┆ 33           ┆ 0.69697  ┆ 48          ┆ 0.479167 ┆ 1.0    ┆ 0.567901 │
└────────────┴──────────────┴──────────┴─────────────┴──────────┴────────┴──────────┘
```
```text
Comparison Matrix:
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

The default metric is exact matching with uniform field weights. Configure
fuzzy matching and weights with `field_metric_config`; choose `doc-avg`,
`field-avg`, or `micro-avg` with `mode`. These modes have the following meaning:

- `doc-avg` document macro-average: compute average result per document first (along
     all fields), then compute average across documents
- `field-avg` field macro-average: compute average results per field (along all
     documents), then compute average across all fields
- `micro-avg` micro-average: direct pooling of field-to-field results in one score

Summary: evaluator.compute_metrics() returns a Polars DataFrame in long format, with 
one row for each metric, and columns `metric`, `mode`, `value`, and `support`. 
Here, `support` refers to:

- the average number of documents that contributed to the metric per field (for
    mode `field-avg`)
- the exact number of documents that contributed to the document average (for mode
    `doc-avg`)
- the number of (doc, field) tuples that contributed to the micro average (for
    mode `micro-avg`)

Intermediate results: evaluator.get_intermediate_results() returns Polars DataFrame,
with a row for each field for `field-avg`, or a row for each document for `doc-avg`.
Columns are `support_prec`, `prec`, `support_rec`, `rec`, and `f1`.

Comparison matrix: evaluator.get_comparison_matrix() returns Polars DataFrame,
with a row for each document and field and columns `doc_id`, `field_name`, 
`gt_present`, `pred_present`, `gt_value`, `pred_value`, `cell_agreement` and `weight`.

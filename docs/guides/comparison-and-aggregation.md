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
print(scored_cells.head())
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

Presence is separate from agreement. `None`, an empty string, and an empty
list are absent; `0` and `False` as field content are counted as "present".
A prediction without a gold value contributes zero precision and no recall
observation. A gold value without a prediction contributes zero recall and
no precision observation. When both sides are absent, neither precision
nor recall has an observation.

## Aggregation modes

Bibra-Eval supports three aggregation modes:

- `doc-avg`: compute weighted field precision and recall within each document,
  derive document F1, then average document results.
- `field-avg`: compute precision, recall, and F1 per field across documents,
  then average fields using their configured weights.
- `micro-avg`: pool cell-level precision and recall before deriving F1.

`Evaluator` uses `field-avg` by default. Its `mode` accepts exactly
`doc-avg`, `field-avg`, or `micro-avg`. 

Summary rows contain `metric`, `mode`, `value`, and `support`, plus any strata
columns. Support describes the observations contributing to a result; it can
be fractional for weighted field summaries.

To understand how aggregation works, you can also manually call the steps
that the `Evaluator` class wraps internally:

Create an `Aggregator` from the comparator, then compute intermediate results
and summarize them. For the lower-level `Aggregator`, use
`group_by="doc_id"` for document averaging, `group_by="field_name"` for field
averaging, and `group_by=None` for an overall micro average.

```python
# compute intermediate results
aggregator = Aggregator(comparator)
intermediate = aggregator.compute_intermediate_results(group_by="field_name")
intermediate.data
```

```text
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

```python
# summarise intermediate results
aggregator.summarise_results(intermediate)
```

```text
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

**Note:** Passing `intermediate` here is optional, but can be used to alter
intermediate results before summarisation.

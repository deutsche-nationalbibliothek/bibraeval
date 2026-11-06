# Drill down by strata

Add document-level attributes to the comparison matrix before constructing
`Aggregator`. Join a table with one row per `doc_id`; duplicated IDs in the
strata table would duplicate comparison rows and change the results.

```python
import polars as pl

from bibraeval import Aggregator

strata = pl.DataFrame(
    {
        "doc_id": ["001", "002"],
        "format": ["book", "article"],
    }
)
comparator.comparison_matrix = comparator.comparison_matrix.join(
    strata, on="doc_id", how="left"
)

aggregator = Aggregator(comparator)
per_format = aggregator.compute_intermediate_results(["doc_id", "format"])
summary = aggregator.summarise_results(per_format)
```

```text
shape: (48, 5)
┌──────────┬────────┬─────────┬──────────┬─────────┐
│ format   ┆ metric ┆ mode    ┆ value    ┆ support │
│ ---      ┆ ---    ┆ ---     ┆ ---      ┆ ---     │
│ str      ┆ str    ┆ str     ┆ f64      ┆ u32     │
╞══════════╪════════╪═════════╪══════════╪═════════╡
│ book     ┆ f1     ┆ doc-avg ┆ 0.256158 ┆ 1       │
│ book     ┆ prec   ┆ doc-avg ┆ 0.298851 ┆ 1       │
│ book     ┆ rec    ┆ doc-avg ┆ 0.224138 ┆ 1       │
│ article  ┆ f1     ┆ doc-avg ┆ 0.348614 ┆ 1       │
│ article  ┆ prec   ┆ doc-avg ┆ 0.313753 ┆ 1       │
│ article  ┆ rec    ┆ doc-avg ┆ 0.392191 ┆ 1       │
└──────────┴────────┴─────────┴──────────┴─────────┘
```

Grouping by `doc_id` and a stratum keeps per-document macro results separate
within each stratum. For a stratified micro average, group only by the stratum:

```python
per_format_micro = aggregator.compute_intermediate_results("format")
format_summary = aggregator.summarise_results(per_format_micro)
```

```text
shape: (48, 5)
┌──────────┬────────┬───────────┬──────────┬─────────┐
│ format   ┆ metric ┆ mode      ┆ value    ┆ support │
│ ---      ┆ ---    ┆ ---       ┆ ---      ┆ ---     │
│ str      ┆ str    ┆ str       ┆ f64      ┆ f64     │
╞══════════╪════════╪═══════════╪══════════╪═════════╡
│ book     ┆ f1     ┆ micro-avg ┆ 0.256158 ┆ 4.0     │
│ book     ┆ prec   ┆ micro-avg ┆ 0.298851 ┆ 3.0     │
│ book     ┆ rec    ┆ micro-avg ┆ 0.224138 ┆ 4.0     │
│ article  ┆ f1     ┆ micro-avg ┆ 0.348614 ┆ 5.0     │
│ article  ┆ prec   ┆ micro-avg ┆ 0.313753 ┆ 5.0     │
│ article  ┆ rec    ┆ micro-avg ┆ 0.392191 ┆ 4.0     │
└──────────┴────────┴───────────┴──────────┴─────────┘
```

`IntermediateResults.strata` reports grouping columns other than `doc_id` and
`field_name`. Value columns such as `gt_value` and `pred_value` cannot be used
as grouping keys. Missing stratum values are grouped together in a `null` group
in the Polars results.

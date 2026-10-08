"""Aggregation of field-level comparisons into macro-averaged metrics."""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

import polars as pl

from bibraeval.comparator import Comparator

AggregationMode = Literal["doc-avg", "field-avg", "micro-avg"]

METRICS = ("f1", "prec", "rec")
_PRIMARY_KEYS = ("doc_id", "field_name")
_UNGROUPABLE = ("gt_value", "pred_value")


@dataclass(frozen=True)
class IntermediateResults:
    """Per-group precision, recall and f1 together with their grouping variables."""

    data: pl.DataFrame
    group_by: tuple[str, ...]
    mode: AggregationMode

    @property
    def strata(self) -> list[str]:
        return [col for col in self.group_by if col not in _PRIMARY_KEYS]

    @property
    def weighted_summary(self) -> bool:
        return "field_name" in self.group_by


class Aggregator:
    """Aggregates the field-level comparison of a `Comparator` into metrics."""

    def __init__(self, comparator: Comparator):
        self.comparator = comparator
        self.intermediate_results: IntermediateResults | None = None
        self.cells = self._compute_cell_scores(comparator.compute_cell_agreement())

    @staticmethod
    def _compute_cell_scores(cells: pl.DataFrame) -> pl.DataFrame:
        """Mask cell agreement by presence for precision and recall."""
        agreement = pl.col("cell_agreement")
        return cells.with_columns(
            pl.when(~pl.col("pred_present"))
            .then(None)
            .when(pl.col("gt_present"))
            .then(agreement)
            .otherwise(0.0)
            .cast(pl.Float64)
            .alias("prec_score"),
            pl.when(~pl.col("gt_present"))
            .then(None)
            .when(pl.col("pred_present"))
            .then(agreement)
            .otherwise(0.0)
            .cast(pl.Float64)
            .alias("rec_score"),
        )

    def compute_intermediate_results(
        self, group_by: str | Sequence[str]
    ) -> IntermediateResults:
        """Compute precision, recall and f1 per group.

        `group_by` must contain `doc_id` or `field_name`. When grouping by
        `field_name`, field weights are carried to the summary step; otherwise
        they are applied as weighted means within each group.
        """
        group_cols = (group_by,) if isinstance(group_by, str) else tuple(group_by)
        self._validate_group_by(group_cols)

        weighted_summary = "field_name" in group_cols
        aggs: list[pl.Expr] = []
        for name, score in (("prec", "prec_score"), ("rec", "rec_score")):
            aggs.append(pl.col(score).count().alias(f"n_{name}"))
            if weighted_summary:
                aggs.append(pl.col(score).mean().alias(name))
            else:
                aggs.append(_weighted_mean(pl.col(score), pl.col("weight")).alias(name))
        if weighted_summary:
            aggs.append(pl.col("weight").first())

        data = (
            self.cells.group_by(group_cols, maintain_order=True)
            .agg(aggs)
            .with_columns(_f1(pl.col("prec"), pl.col("rec")).alias("f1"))
            .sort(group_cols)
        )
        self.intermediate_results = IntermediateResults(
            data=data, group_by=group_cols, mode=_mode(group_cols)
        )
        return self.intermediate_results

    def _validate_group_by(self, group_cols: tuple[str, ...]) -> None:
        if not any(col in group_cols for col in _PRIMARY_KEYS):
            raise ValueError("group_by must include 'doc_id' or 'field_name'.")
        missing = [col for col in group_cols if col not in self.cells.columns]
        if missing:
            raise ValueError(f"group_by columns not found: {missing}")
        invalid = [col for col in group_cols if col in _UNGROUPABLE]
        if invalid:
            raise ValueError(f"Cannot group by value columns: {invalid}")

    def summarise_results(
        self, intermediate: IntermediateResults | None = None
    ) -> pl.DataFrame:
        """Macro-average intermediate results, preserving stratification columns."""
        if intermediate is None:
            intermediate = self.intermediate_results
        if intermediate is None:
            raise ValueError(
                "No intermediate results; call compute_intermediate_results first."
            )

        strata = intermediate.strata
        index = strata + (["weight"] if intermediate.weighted_summary else [])
        long = intermediate.data.select(*index, *METRICS).unpivot(
            on=list(METRICS), index=index, variable_name="metric"
        )
        value = (
            _weighted_mean(pl.col("value"), pl.col("weight"))
            if intermediate.weighted_summary
            else pl.col("value").mean()
        )
        return (
            long.group_by([*strata, "metric"])
            .agg(value.alias("value"), pl.col("value").count().alias("support"))
            .with_columns(pl.lit(intermediate.mode).alias("mode"))
            .select(*strata, "metric", "mode", "value", "support")
            .sort([*strata, "metric"])
        )


def _weighted_mean(score: pl.Expr, weight: pl.Expr) -> pl.Expr:
    """Weighted mean over non-null scores; null if no weight remains."""
    weight_sum = weight.filter(score.is_not_null()).sum()
    return (
        pl.when(weight_sum > 0)
        .then((score * weight).sum() / weight_sum)
        .otherwise(None)
    )


def _f1(prec: pl.Expr, rec: pl.Expr) -> pl.Expr:
    return (
        pl.when(prec.is_null() & rec.is_null())
        .then(None)
        .when(prec.is_null() | rec.is_null() | ((prec + rec) == 0))
        .then(0.0)
        .otherwise(2 * prec * rec / (prec + rec))
    )


def _mode(group_cols: tuple[str, ...]) -> AggregationMode:
    if "doc_id" in group_cols and "field_name" in group_cols:
        return "micro-avg"
    if "doc_id" in group_cols:
        return "doc-avg"
    return "field-avg"

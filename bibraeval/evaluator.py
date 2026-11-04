"""One-pass evaluation of predicted records against ground truth records."""

from pathlib import Path
from typing import Any, get_args

import polars as pl
from pydantic import BaseModel

from bibraeval.aggregator import AggregationMode, Aggregator
from bibraeval.comparator import Comparator
from bibraeval.data_ingester import RecordCollection
from bibraeval.metric_conf import FieldMetricMapping

_GROUP_BY: dict[AggregationMode, str | None] = {
    "doc-avg": "doc_id",
    "field-avg": "field_name",
    "micro-avg": None,
}


class Evaluator:
    """Loads record collections, compares them and returns summarised metrics.

    Without a `field_metric_config`, all fields are scored by exact matching
    with uniform weights.
    """

    def __init__(
        self,
        gt_path: str | Path,
        pred_path: str | Path,
        schema: type[BaseModel],
        mode: AggregationMode = "field-avg",
        field_metric_config: FieldMetricMapping
        | dict[str, Any]
        | str
        | Path
        | None = None,
        drop_mismatched_doc_ids: bool = False,
    ):
        """Configure a one-call evaluation workflow.

        Args:
            gt_path: Directory of JSON records or a JSONL file for ground truth.
            pred_path: Directory of JSON records or a JSONL file for predictions.
            schema: Pydantic model used to validate each record's metadata.
            mode: Summary mode: ``doc-avg``, ``field-avg`` (the default), or
                ``micro-avg``.
            field_metric_config: Per-field configuration as a
                ``FieldMetricMapping``, flat mapping, or YAML path. With no
                configuration all model fields use exact matching and weight
                1.0.
            drop_mismatched_doc_ids: If true, evaluate only IDs present in both
                datasets; otherwise mismatched IDs raise ``ValueError``.

        Raises:
            ValueError: If ``mode`` is unsupported.
        """
        if mode not in get_args(AggregationMode):
            raise ValueError(
                f"Invalid mode {mode!r}; expected one of {get_args(AggregationMode)}."
            )
        if isinstance(field_metric_config, (str, Path)):
            field_metric_config = FieldMetricMapping.from_yaml(field_metric_config)

        self.gt_path = Path(gt_path)
        self.pred_path = Path(pred_path)
        self.schema = schema
        self.mode = mode
        self.field_metric_config = field_metric_config
        self.drop_mismatched_doc_ids = drop_mismatched_doc_ids

        self.comparison_matrix = None
        self.intermediate_results = None
        self.summary = None

    def compute_metrics(self, results_dir: str | Path | None = None) -> pl.DataFrame:
        """Load records, compare them, and return summary metrics.

        Args:
            results_dir: If specified, save the summary metrics, intermediate
                results, and comparison matrix to CSV files in this directory.

        Returns:
            A polars dataframe with one row per ``metric``, summarised according to the
            specified ``mode``. The dataframe's columns are:

            * ``metric`` containing the metric name,
            * ``mode`` containing the aggregation mode,
            * ``value`` containing the aggregated metric value,
            * ``support`` containing the number of records used to compute the metric.

        Notes:
            Each call starts a new evaluation and clears results from previous runs.
            If the computation fails, no results from the failed run are available
            through the getter methods. Failures during CSV export do not invalidate
            the computed results.
        """
        # Clear previous results to avoid returning stale data if computation fails
        self.comparison_matrix = None
        self.intermediate_results = None
        self.summary = None

        # Load records and compute metrics
        comparator = Comparator(
            ground_truth=self._load(self.gt_path),
            predictions=self._load(self.pred_path),
            metric_schema=self.field_metric_config,
            drop_mismatched_doc_ids=self.drop_mismatched_doc_ids,
        )
        aggregator = Aggregator(comparator)
        intermediate = aggregator.compute_intermediate_results(_GROUP_BY[self.mode])
        summary = aggregator.summarise_results(intermediate)

        # Store results for later retrieval after successful computation
        self.summary = summary
        self.intermediate_results = intermediate.data
        self.comparison_matrix = aggregator.comparison_matrix

        # Save results to CSV if a directory is specified
        if results_dir is not None:
            self._save_results(results_dir)

        return summary

    def get_comparison_matrix(self) -> pl.DataFrame:
        """Return the comparison matrix for the current evaluation.

        Returns:
            A Polars DataFrame with one row per document and metadata field, containing
            the following columns:

            * ``doc_id``: the document ID,
            * ``field_name``: the name of the metadata field,
            * ``gt_present``: whether the ground truth value is present,
            * ``pred_present``: whether the predicted value is present,
            * ``gt_value``: the ground truth value for the field,
            * ``pred_value``: the predicted value for the field,
            * ``cell_agreement``: how much the ground truth and predicted values agree
                according to the field's metric,
            * ``weight``: the weight assigned to the field for metric computation.

        Raises:
            ValueError: If the comparison matrix is not available, which occurs if
                ``compute_metrics()`` has not been called yet.
        """
        if self.comparison_matrix is None:
            raise ValueError(
                "Comparison matrix is not available. Run compute_metrics() first."
            )
        return self.comparison_matrix

    def get_intermediate_results(self) -> pl.DataFrame:
        """Return the intermediate results for the current evaluation.

        Returns:
            A Polars DataFrame containing precision, recall and F1 per group.
            The exact structure of the dataframe depends on the aggregation mode.

        Raises:
            ValueError: If the intermediate results are not available, which occurs if
                ``compute_metrics()`` has not been called yet.
        """
        if self.intermediate_results is None:
            raise ValueError(
                "Intermediate results are not available. Run compute_metrics() first."
            )
        return self.intermediate_results

    def _load(self, path: Path) -> RecordCollection[BaseModel]:
        if path.is_dir():
            return RecordCollection.create_from_dir(path, schema=self.schema)
        return RecordCollection.create_from_file(path, schema=self.schema)

    def _save_to_csv(
        self, df: pl.DataFrame, target_dir: str | Path, filename: str
    ) -> None:
        """Save a polars dataframe to a CSV file.

        Args:
            df: The polars dataframe to save.
            target_dir: The directory where the CSV file will be saved.
            filename: The name of the CSV file.
        """
        # csv writer does not support object dtype
        object_columns = [col for col, dtype in df.schema.items() if dtype == pl.Object]
        for col in object_columns:
            df = df.with_columns(
                pl.Series(
                    col,
                    [
                        str(value) if value is not None else None
                        for value in df[col].to_list()
                    ],
                    dtype=pl.String,
                )
            )

        target_dir = Path(target_dir)
        target_dir.mkdir(parents=True, exist_ok=True)
        file_path = target_dir / filename
        df.write_csv(file_path)

    def _save_results(self, target_dir: str | Path) -> None:
        """Save all evaluation results - summary, intermediate results, comparison
        matrix - as CSV files."""

        assert self.summary is not None
        assert self.intermediate_results is not None
        assert self.comparison_matrix is not None

        self._save_to_csv(
            df=self.summary,
            target_dir=target_dir,
            filename="summary_metrics.csv",
        )
        self._save_to_csv(
            df=self.intermediate_results,
            target_dir=target_dir,
            filename="intermediate_results.csv",
        )
        self._save_to_csv(
            df=self.comparison_matrix,
            target_dir=target_dir,
            filename="comparison_matrix.csv",
        )

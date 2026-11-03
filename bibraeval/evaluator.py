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
        self.intermediate = None
        self.comparator = None
        self.aggregator = None

    def compute_metrics(self) -> pl.DataFrame:
        """Load records, compare them, and return summary metrics.

        Returns:
            A polars dataframe with one row per ``metric``, summarised according to the
            specified ``mode``. The dataframe's columns are:

            * ``metric`` containing the metric name,
            * ``mode`` containing the aggregation mode,
            * ``value`` containing the aggregated metric value,
            * ``support`` containing the number of records used to compute the metric.
        """
        self.comparator = Comparator(
            ground_truth=self._load(self.gt_path),
            predictions=self._load(self.pred_path),
            metric_schema=self.field_metric_config,
            drop_mismatched_doc_ids=self.drop_mismatched_doc_ids,
        )
        self.aggregator = Aggregator(self.comparator)
        self.intermediate = self.aggregator.compute_intermediate_results(
            _GROUP_BY[self.mode]
        )
        return self.aggregator.summarise_results(self.intermediate)

    def get_comparison_matrix(self) -> pl.DataFrame:
        """Return the comparison matrix for the current evaluation.

        Returns:
            A polars dataframe with one row per document and metadata field, containing
            the following columns:

            * ``doc_id``: the document ID,
            * ``field_name``: the name of the metadata field,
            * ``gt_present``: whether the ground truth value is present,
            * ``pred_present``: whether the predicted value is present,
            * ``gt_value``: the ground truth value for the field,
            * ``pred_values``: the predicted value for the field,
            * ``cell_agreement``: how much the ground truth and predicted values agree
                according to the field's metric,
            * ``weight``: the weight assigned to the field for metric computation.

        Raises:
            ValueError: If the comparison matrix is not available, which occurs if
                ``compute_metrics()`` has not been called yet.
        """
        if self.comparator is None:
            raise ValueError(
                "Comparison matrix is not available. Run compute_metrics() first."
            )
        return self.comparator.compute_cell_agreement()

    def get_intermediate_results(self) -> pl.DataFrame:
        """Return the intermediate results for the current evaluation.

        Returns:
            A polars dataframe precision, recall and f1 per group.
            The exact structure of the dataframe depends on the aggregation mode.

        Raises:
            ValueError: If the intermediate results are not available, which occurs if
                ``compute_metrics()`` has not been called yet.
        """
        if self.intermediate is None:
            raise ValueError(
                "Intermediate results are not available. Run compute_metrics() first."
            )
        return self.intermediate.data

    def _load(self, path: Path) -> RecordCollection[BaseModel]:
        if path.is_dir():
            return RecordCollection.create_from_dir(path, schema=self.schema)
        return RecordCollection.create_from_file(path, schema=self.schema)

"""One-pass evaluation of predicted records against ground truth records."""

from pathlib import Path
from typing import Any, get_args

import polars as pl
from pydantic import BaseModel

from bibraeval.aggregator import AggregationMode, Aggregator
from bibraeval.comparator import Comparator
from bibraeval.data_ingester import RecordCollection
from bibraeval.metric_schema import field_metric_schema

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
        field_metric_config: field_metric_schema
        | dict[str, Any]
        | str
        | Path
        | None = None,
        drop_mismatched_doc_ids: bool = False,
    ):
        if mode not in get_args(AggregationMode):
            raise ValueError(
                f"Invalid mode {mode!r}; expected one of {get_args(AggregationMode)}."
            )
        if isinstance(field_metric_config, (str, Path)):
            field_metric_config = field_metric_schema.from_yaml(field_metric_config)

        self.gt_path = Path(gt_path)
        self.pred_path = Path(pred_path)
        self.schema = schema
        self.mode = mode
        self.field_metric_config = field_metric_config
        self.drop_mismatched_doc_ids = drop_mismatched_doc_ids

    def compute_metrics(self) -> pl.DataFrame:
        """Load records, compare them and return the summarised metrics."""
        comparator = Comparator(
            ground_truth=self._load(self.gt_path),
            predictions=self._load(self.pred_path),
            metric_schema=self.field_metric_config,
            drop_mismatched_doc_ids=self.drop_mismatched_doc_ids,
        )
        aggregator = Aggregator(comparator)
        intermediate = aggregator.compute_intermediate_results(_GROUP_BY[self.mode])
        return aggregator.summarise_results(intermediate)

    def _load(self, path: Path) -> RecordCollection[BaseModel]:
        if path.is_dir():
            return RecordCollection.create_from_dir(path, schema=self.schema)
        return RecordCollection.create_from_file(path, schema=self.schema)

from typing import Any

import polars as pl

from bibraeval.data_ingester import MetadataT, RecordCollection
from bibraeval.field_metrics import exact, fieldMetric
from bibraeval.metric_schema import field_metric_schema


class Comparator:
    """Comparator for fusing records from two Record Collections based on their doc_id."""

    def __init__(
        self,
        ground_truth: RecordCollection[MetadataT],
        predictions: RecordCollection[MetadataT],
        metric_schema: field_metric_schema | dict[str, Any] | None = None,
        drop_mismatched_doc_ids: bool = False,
    ):
        self.ground_truth = ground_truth
        self.predictions = predictions
        self.drop_mismatched_doc_ids = drop_mismatched_doc_ids
        if isinstance(metric_schema, dict):
            metric_schema = field_metric_schema.from_dict(metric_schema)
        self.metric_schema = metric_schema

        if not self.drop_mismatched_doc_ids:
            self._check_doc_id_match()
        self.comparison_matrix = self._fuse_records()

    def _check_doc_id_match(self) -> bool:
        """Check if two record collections contain the same doc_ids."""
        gt_doc_ids = set(self.ground_truth.records)
        pred_doc_ids = set(self.predictions.records)
        if gt_doc_ids == pred_doc_ids:
            return True

        mismatches_gt_not_pred = gt_doc_ids - pred_doc_ids
        mismatches_pred_not_gold = pred_doc_ids - gt_doc_ids
        n_mismatches = len(gt_doc_ids ^ pred_doc_ids)
        raise ValueError(
            f"Record collections have {n_mismatches} mismatched doc_ids: "
            f"ground_truth not in predictions: {mismatches_gt_not_pred}, "
            f"predictions not in ground_truth: {mismatches_pred_not_gold}"
            f"Use drop_mismatched_doc_ids=True to ignore mismatched doc_ids."
        )

    def _fuse_records(self) -> pl.DataFrame:
        """Fuse records into one long Polars DataFrame by doc_id and field.

        Columns returned:
        - `doc_id`
        - `field_name`
        - `gt_present`
        - `pred_present`
        - `gt_value` (may be nested for list fields)
        - `pred_value` (may be nested for list fields)
        """
        fused_data = []
        for doc_id in sorted(self.ground_truth.records):
            if self.drop_mismatched_doc_ids and doc_id not in self.predictions.records:
                continue
            gt_record = self.ground_truth.records[doc_id]
            pred_record = self.predictions.records[doc_id]
            gt_metadata = gt_record.metadata.model_dump(by_alias=True)
            pred_metadata = pred_record.metadata.model_dump(by_alias=True)
            field_names = sorted(gt_metadata.keys() | pred_metadata.keys())

            for field_name in field_names:
                gt_value = gt_metadata.get(field_name)
                pred_value = pred_metadata.get(field_name)
                fused_data.append(
                    {
                        "doc_id": doc_id,
                        "field_name": field_name,
                        # custom test for presence of value, exclusing empty
                        # strings and empty lists
                        "gt_present": self._is_present(gt_value),
                        "pred_present": self._is_present(pred_value),
                        "gt_value": gt_value,
                        "pred_value": pred_value,
                    }
                )

        return pl.DataFrame(
            fused_data,
            schema_overrides={"gt_value": pl.Object, "pred_value": pl.Object},
        )

    @staticmethod
    def _is_present(value: object) -> bool:
        return value is not None and value != "" and value != []

    def compute_cell_agreement(
        self,
        comparison_matrix: pl.DataFrame | None = None,
        metric: fieldMetric | None = None,
    ) -> pl.DataFrame:
        """Compute cell-level agreement between gold and predicted values.

        With a `metric_schema`, only fields listed in the schema are scored, each
        with its configured metric and weight. Otherwise all fields are scored
        with `metric` (default `exact()`) and weight 1.0.
        """
        if comparison_matrix is None:
            comparison_matrix = self.comparison_matrix

        if self.metric_schema is not None:
            if metric is not None:
                raise ValueError("Pass either metric or metric_schema, not both.")
            return self._compute_schema_agreement(comparison_matrix, self.metric_schema)

        if metric is None:
            metric = exact()

        scores = [
            metric.score(gt_value, pred_value)
            for gt_value, pred_value in comparison_matrix.select(
                "gt_value", "pred_value"
            ).iter_rows()
        ]
        return comparison_matrix.with_columns(
            pl.Series("cell_agreement", scores, dtype=pl.Float64),
            pl.lit(1.0, dtype=pl.Float64).alias("weight"),
        )

    def _compute_schema_agreement(
        self, comparison_matrix: pl.DataFrame, schema: field_metric_schema
    ) -> pl.DataFrame:
        comparison_matrix = comparison_matrix.filter(
            pl.col("field_name").is_in(list(schema.fields))
        )
        metrics = {name: schema.build_metric(name) for name in schema.fields}

        scores = [
            metrics[field_name].score(gt_value, pred_value)
            for field_name, gt_value, pred_value in comparison_matrix.select(
                "field_name", "gt_value", "pred_value"
            ).iter_rows()
        ]
        weights = [
            schema.fields[field_name].weight
            for field_name in comparison_matrix["field_name"]
        ]
        return comparison_matrix.with_columns(
            pl.Series("cell_agreement", scores, dtype=pl.Float64),
            pl.Series("weight", weights, dtype=pl.Float64),
        )

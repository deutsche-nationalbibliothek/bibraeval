import polars as pl

from bibraeval.data_ingester import MetadataT, RecordCollection


class Comparator:
    """Comparator for fusing records from two Record Collections based on their doc_id."""

    def __init__(
        self,
        gold_standard: RecordCollection[MetadataT],
        predictions: RecordCollection[MetadataT],
        metricSchema: dict[str, object] | None = None,
        drop_mismatched_doc_ids: bool = False,
    ):
        self.gold_standard = gold_standard
        self.predictions = predictions
        self.drop_mismatched_doc_ids = drop_mismatched_doc_ids
        self.metricSchema = metricSchema

        if not self.drop_mismatched_doc_ids:
            self._check_doc_id_match()
        self.fused_records = self._fuse_records()

    def _check_doc_id_match(self) -> bool:
        """Check if two record collections contain the same doc_ids."""
        gold_doc_ids = set(self.gold_standard.records)
        pred_doc_ids = set(self.predictions.records)
        if gold_doc_ids == pred_doc_ids:
            return True

        mismatches_gold_not_pred = gold_doc_ids - pred_doc_ids
        mismatches_pred_not_gold = pred_doc_ids - gold_doc_ids
        n_mismatches = len(gold_doc_ids ^ pred_doc_ids)
        raise ValueError(
            f"Record collections have {n_mismatches} mismatched doc_ids: "
            f"gold_standard not in predictions: {mismatches_gold_not_pred}, "
            f"predictions not in gold_standard: {mismatches_pred_not_gold}"
            f"Use drop_mismatched_doc_ids=True to ignore mismatched doc_ids."
        )

    def _fuse_records(self) -> pl.DataFrame:
        """Fuse records into one long Polars DataFrame by doc_id and field.

        Columns returned:
        - `doc_id`
        - `field_name`
        - `gold_present`
        - `pred_present`
        - `gt_value` (may be nested for list fields)
        - `pred_value` (may be nested for list fields)
        """
        fused_data = []
        for doc_id in sorted(self.gold_standard.records):
            if self.drop_mismatched_doc_ids and doc_id not in self.predictions.records:
                continue
            gold_record = self.gold_standard.records[doc_id]
            pred_record = self.predictions.records[doc_id]
            gold_metadata = gold_record.metadata.model_dump(by_alias=True)
            pred_metadata = pred_record.metadata.model_dump(by_alias=True)
            field_names = sorted(gold_metadata.keys() | pred_metadata.keys())

            for field_name in field_names:
                gt_value = gold_metadata.get(field_name)
                pred_value = pred_metadata.get(field_name)
                fused_data.append(
                    {
                        "doc_id": doc_id,
                        "field_name": field_name,
                        # custom test for presence of value, exclusing empty
                        # strings and empty lists
                        "gold_present": self._is_present(gt_value),
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
        self, fused_df: pl.DataFrame | None = None
    ) -> pl.DataFrame:
        """Compute cell-level agreement between gold and predicted values."""
        if fused_df is None:
            fused_df = self.fused_records

        return fused_df.with_columns(
            (
                pl.col("gold_present")
                & pl.col("pred_present")
                & (pl.col("gt_value") == pl.col("pred_value"))
            ).alias("cell_agreement")
        )

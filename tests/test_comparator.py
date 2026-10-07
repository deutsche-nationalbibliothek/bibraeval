import polars as pl
import pytest
from pydantic import BaseModel, ConfigDict, Field

from bibraeval.comparator import Comparator
from bibraeval.data_ingester import RecordCollection
from bibraeval.field_metrics import levenshtein
from bibraeval.metric_schema import field_metric_schema


class PublicationMetadata(BaseModel):
    """Response model for publication metadata extraction."""

    model_config = ConfigDict(populate_by_name=True)

    language: list[str] = Field(default_factory=list)
    title: str | None = None
    year: str | None = None
    p_isbn: list[str] = Field(default_factory=list, alias="p-isbn")


def test_comparator_fuses_record_collections_to_long_table() -> None:
    ground_truth = RecordCollection[PublicationMetadata]()
    ground_truth.add_payload(
        doc_id="103571650X",
        payload={
            "title": "Werke der Freiheit",
            "year": "2013",
            "language": ["ger"],
            "p-isbn": [],
        },
        schema=PublicationMetadata,
    )
    predictions = RecordCollection[PublicationMetadata]()
    predictions.add_payload(
        doc_id="103571650X",
        payload={
            "title": "Werke der Freiheit",
            "year": None,
            "language": [],
            "p-isbn": ["978-3-86539-327-2"],
        },
        schema=PublicationMetadata,
    )

    comparison_matrix = Comparator(ground_truth, predictions).comparison_matrix

    assert comparison_matrix.columns == [
        "doc_id",
        "field_name",
        "gt_present",
        "pred_present",
        "gt_value",
        "pred_value",
    ]
    assert comparison_matrix.to_dicts() == [
        {
            "doc_id": "103571650X",
            "field_name": "language",
            "gt_present": True,
            "pred_present": False,
            "gt_value": ["ger"],
            "pred_value": [],
        },
        {
            "doc_id": "103571650X",
            "field_name": "p-isbn",
            "gt_present": False,
            "pred_present": True,
            "gt_value": [],
            "pred_value": ["978-3-86539-327-2"],
        },
        {
            "doc_id": "103571650X",
            "field_name": "title",
            "gt_present": True,
            "pred_present": True,
            "gt_value": "Werke der Freiheit",
            "pred_value": "Werke der Freiheit",
        },
        {
            "doc_id": "103571650X",
            "field_name": "year",
            "gt_present": True,
            "pred_present": False,
            "gt_value": "2013",
            "pred_value": None,
        },
    ]


def test_compute_cell_agreement_scores_list_values_and_preserves_missing() -> None:
    ground_truth = RecordCollection[PublicationMetadata]()
    ground_truth.add_payload(
        doc_id="103571650X",
        payload={"language": ["ger", "eng"]},
        schema=PublicationMetadata,
    )
    predictions = RecordCollection[PublicationMetadata]()
    predictions.add_payload(
        doc_id="103571650X",
        payload={"language": ["eng", "ger"]},
        schema=PublicationMetadata,
    )

    scores = Comparator(ground_truth, predictions).compute_cell_agreement()

    assert (
        scores.filter(pl.col("field_name") == "language")["cell_agreement"].item()
        == 1.0
    )

    # TODO: Implement handling for missing values in cell agreement scores.
    # assert (
    #     scores.filter(pl.col("field_name") == "title")["cell_agreement"].item() is None
    # )


def test_compute_cell_agreement_uses_supplied_metric() -> None:
    ground_truth = RecordCollection[PublicationMetadata]()
    ground_truth.add_payload(
        doc_id="103571650X",
        payload={"title": "cat"},
        schema=PublicationMetadata,
    )
    predictions = RecordCollection[PublicationMetadata]()
    predictions.add_payload(
        doc_id="103571650X",
        payload={"title": "cut"},
        schema=PublicationMetadata,
    )

    scores = Comparator(ground_truth, predictions).compute_cell_agreement(
        metric=levenshtein()
    )

    assert scores.filter(pl.col("field_name") == "title")[
        "cell_agreement"
    ].item() == pytest.approx(2 / 3)


def test_comparator_raises_for_mismatched_doc_ids() -> None:
    ground_truth = RecordCollection[PublicationMetadata]()
    ground_truth.add_payload(
        doc_id="103571650X",
        payload={"title": "Werke der Freiheit"},
        schema=PublicationMetadata,
    )
    predictions = RecordCollection[PublicationMetadata]()
    predictions.add_payload(
        doc_id="991651952",
        payload={"title": "DAS GESAMTWERK WOLFGANG BORCHERT"},
        schema=PublicationMetadata,
    )

    with pytest.raises(ValueError, match="mismatched doc_ids"):
        Comparator(ground_truth, predictions)


def test_comparator_drops_mismatched_doc_ids() -> None:
    ground_truth = RecordCollection[PublicationMetadata]()
    ground_truth.add_payload(
        doc_id="103571650X",
        payload={"title": "Werke der Freiheit"},
        schema=PublicationMetadata,
    )
    ground_truth.add_payload(
        doc_id="991651952",
        payload={"title": "DAS GESAMTWERK WOLFGANG BORCHERT"},
        schema=PublicationMetadata,
    )
    predictions = RecordCollection[PublicationMetadata]()
    predictions.add_payload(
        doc_id="103571650X",
        payload={"title": "Werke der Freiheit"},
        schema=PublicationMetadata,
    )
    predictions.add_payload(
        doc_id="1101366915",
        payload={"title": "Only in predictions"},
        schema=PublicationMetadata,
    )

    comparison_matrix = Comparator(
        ground_truth,
        predictions,
        drop_mismatched_doc_ids=True,
    ).comparison_matrix

    assert set(comparison_matrix["doc_id"].unique().to_list()) == {"103571650X"}
    assert comparison_matrix.filter(pl.col("field_name") == "title").to_dicts() == [
        {
            "doc_id": "103571650X",
            "field_name": "title",
            "gt_present": True,
            "pred_present": True,
            "gt_value": "Werke der Freiheit",
            "pred_value": "Werke der Freiheit",
        }
    ]


def _schema_comparator(
    metric_schema: field_metric_schema | dict | None,
) -> Comparator:
    ground_truth = RecordCollection[PublicationMetadata]()
    ground_truth.add_payload(
        doc_id="103571650X",
        payload={"title": "cat", "year": "2013", "language": ["ger", "eng"]},
        schema=PublicationMetadata,
    )
    predictions = RecordCollection[PublicationMetadata]()
    predictions.add_payload(
        doc_id="103571650X",
        payload={"title": "cut", "year": "2013", "language": ["eng", "fre"]},
        schema=PublicationMetadata,
    )
    return Comparator(ground_truth, predictions, metric_schema=metric_schema)


SCHEMA = {
    "title": {"metric": "levenshtein", "match_threshold": 0.7, "weight": 2.0},
    "language": {"metric": "exact", "list_comparison": "any-of", "weight": 1.5},
    "publisher": {"metric": "exact"},
}


def test_compute_cell_agreement_with_schema_scores_only_listed_fields() -> None:
    scores = _schema_comparator(SCHEMA).compute_cell_agreement()

    assert scores.columns[-2:] == ["cell_agreement", "weight"]
    assert scores["field_name"].to_list() == ["language", "title"]
    rows = {row["field_name"]: row for row in scores.to_dicts()}
    assert rows["title"]["cell_agreement"] == pytest.approx(2 / 3)
    assert rows["title"]["weight"] == 2.0
    assert rows["language"]["cell_agreement"] == 1.0
    assert rows["language"]["weight"] == 1.5


def test_compute_cell_agreement_accepts_schema_object_or_dict() -> None:
    from_dict = _schema_comparator(SCHEMA).compute_cell_agreement()
    from_schema = _schema_comparator(
        field_metric_schema.from_dict(SCHEMA)
    ).compute_cell_agreement()

    assert from_dict.drop("gt_value", "pred_value").equals(
        from_schema.drop("gt_value", "pred_value")
    )


def test_compute_cell_agreement_without_schema_adds_default_weight() -> None:
    scores = _schema_comparator(None).compute_cell_agreement()

    assert scores["weight"].to_list() == [1.0] * scores.height


def test_compute_cell_agreement_rejects_metric_with_schema() -> None:
    with pytest.raises(ValueError, match="either metric or metric_schema"):
        _schema_comparator(SCHEMA).compute_cell_agreement(metric=levenshtein())

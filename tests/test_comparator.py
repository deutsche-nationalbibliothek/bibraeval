import polars as pl
import pytest
from pydantic import BaseModel, ConfigDict, Field

from bibraeval.comparator import Comparator
from bibraeval.data_ingestor import RecordCollection


class PublicationMetadata(BaseModel):
    """Response model for publication metadata extraction."""

    model_config = ConfigDict(populate_by_name=True)

    language: list[str] = Field(default_factory=list)
    title: str | None = None
    year: str | None = None
    p_isbn: list[str] = Field(default_factory=list, alias="p-isbn")


def test_comparator_fuses_record_collections_to_long_table() -> None:
    gold_standard = RecordCollection[PublicationMetadata]()
    gold_standard.add_payload(
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

    fused_records = Comparator(gold_standard, predictions).fused_records

    assert fused_records.columns == [
        "doc_id",
        "field_name",
        "gold_present",
        "pred_present",
        "gt_value",
        "pred_value",
    ]
    assert fused_records.to_dicts() == [
        {
            "doc_id": "103571650X",
            "field_name": "language",
            "gold_present": True,
            "pred_present": False,
            "gt_value": ["ger"],
            "pred_value": [],
        },
        {
            "doc_id": "103571650X",
            "field_name": "p-isbn",
            "gold_present": False,
            "pred_present": True,
            "gt_value": [],
            "pred_value": ["978-3-86539-327-2"],
        },
        {
            "doc_id": "103571650X",
            "field_name": "title",
            "gold_present": True,
            "pred_present": True,
            "gt_value": "Werke der Freiheit",
            "pred_value": "Werke der Freiheit",
        },
        {
            "doc_id": "103571650X",
            "field_name": "year",
            "gold_present": True,
            "pred_present": False,
            "gt_value": "2013",
            "pred_value": None,
        },
    ]


def test_comparator_raises_for_mismatched_doc_ids() -> None:
    gold_standard = RecordCollection[PublicationMetadata]()
    gold_standard.add_payload(
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
        Comparator(gold_standard, predictions)


def test_comparator_drops_mismatched_doc_ids() -> None:
    gold_standard = RecordCollection[PublicationMetadata]()
    gold_standard.add_payload(
        doc_id="103571650X",
        payload={"title": "Werke der Freiheit"},
        schema=PublicationMetadata,
    )
    gold_standard.add_payload(
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

    fused_records = Comparator(
        gold_standard,
        predictions,
        drop_mismatched_doc_ids=True,
    ).fused_records

    assert set(fused_records["doc_id"].unique().to_list()) == {"103571650X"}
    assert fused_records.filter(pl.col("field_name") == "title").to_dicts() == [
        {
            "doc_id": "103571650X",
            "field_name": "title",
            "gold_present": True,
            "pred_present": True,
            "gt_value": "Werke der Freiheit",
            "pred_value": "Werke der Freiheit",
        }
    ]

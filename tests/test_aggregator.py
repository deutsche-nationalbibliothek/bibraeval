import polars as pl
import pytest
from pydantic import BaseModel, ConfigDict, Field

from bibraeval.aggregator import Aggregator
from bibraeval.comparator import Comparator
from bibraeval.data_ingester import RecordCollection


class PublicationMetadata(BaseModel):
    """Response model for publication metadata extraction."""

    model_config = ConfigDict(populate_by_name=True)

    language: list[str] = Field(default_factory=list)
    title: str | None = None
    year: str | None = None


SCHEMA = {
    "title": {"metric": "exact", "weight": 2.0},
    "year": {"metric": "exact", "weight": 1.0},
    "language": {"metric": "exact", "weight": 1.0},
}


@pytest.fixture
def comparator() -> Comparator:
    """
    Create and return a Comparator instance with two examples for
    ground truth and predictions.
    """
    ground_truth = RecordCollection[PublicationMetadata]()
    ground_truth.add_payload(
        doc_id="A",
        payload={"title": "T", "year": "2013", "language": ["ger"]},
        schema=PublicationMetadata,
    )
    ground_truth.add_payload(
        doc_id="B", payload={"title": "U"}, schema=PublicationMetadata
    )
    predictions = RecordCollection[PublicationMetadata]()
    predictions.add_payload(
        doc_id="A",
        payload={"title": "T", "year": "2014"},
        schema=PublicationMetadata,
    )
    predictions.add_payload(
        doc_id="B",
        payload={"title": "X", "year": "2020"},
        schema=PublicationMetadata,
    )
    return Comparator(ground_truth, predictions, SCHEMA)


def _summary_dict(summary: pl.DataFrame) -> dict[str, tuple[float, int]]:
    return {
        metric: (value, support)
        for metric, value, support in summary.select(
            "metric", "value", "support"
        ).iter_rows()
    }


def test_cell_scores_mask_by_presence(comparator: Comparator) -> None:
    cells = Aggregator(comparator).cells
    scores = {
        (doc_id, field): (prec, rec)
        for doc_id, field, prec, rec in cells.select(
            "doc_id", "field_name", "prec_score", "rec_score"
        ).iter_rows()
    }

    assert scores[("A", "title")] == (1.0, 1.0)
    assert scores[("A", "language")] == (None, 0.0)
    assert scores[("B", "year")] == (0.0, None)
    assert scores[("B", "language")] == (None, None)


def test_doc_avg_uses_weights_within_groups(comparator: Comparator) -> None:
    agg = Aggregator(comparator)
    intermediate = agg.compute_intermediate_results(group_by="doc_id")

    assert intermediate.mode == "doc-avg"
    assert "weight" not in intermediate.data.columns
    row_a = intermediate.data.filter(pl.col("doc_id") == "A").to_dicts()[0]
    # title has weight 2, year has weight 1, language has weight 1
    assert row_a["prec"] == pytest.approx(2 / 3)
    assert row_a["rec"] == pytest.approx(0.5)
    assert row_a["f1"] == pytest.approx(4 / 7)
    assert (row_a["n_prec"], row_a["n_rec"]) == (2, 3)

    summary = agg.summarise_results()
    assert summary.columns == ["metric", "mode", "value", "support"]
    assert summary["metric"].to_list() == ["f1", "prec", "rec"]
    result = _summary_dict(summary)
    assert result["f1"] == (pytest.approx(2 / 7), 2)
    assert result["prec"] == (pytest.approx(1 / 3), 2)
    assert result["rec"] == (pytest.approx(0.25), 2)


def test_field_avg_uses_weights_in_summary(comparator: Comparator) -> None:
    agg = Aggregator(comparator)
    intermediate = agg.compute_intermediate_results(group_by="field_name")

    assert intermediate.mode == "field-avg"
    language = intermediate.data.filter(pl.col("field_name") == "language")
    assert language["prec"].item() is None
    assert language["f1"].item() == 0.0

    result = _summary_dict(agg.summarise_results())
    assert result["prec"] == (pytest.approx(1 / 3), 2)
    assert result["rec"] == (pytest.approx(0.25), 3)
    assert result["f1"] == (pytest.approx(0.25), 3)


def test_micro_avg_support_uses_max_presence_counts(comparator: Comparator) -> None:
    comparator.comparison_matrix = comparator.comparison_matrix.with_columns(
        pl.when(pl.col("doc_id") == "A")
        .then(pl.lit("Book"))
        .otherwise(pl.lit("Article"))
        .alias("doc_group")
    )
    agg = Aggregator(comparator)
    intermediate = agg.compute_intermediate_results(group_by=["doc_group"])

    assert intermediate.mode == "micro-avg"
    summary = agg.summarise_results()
    supports = {
        (doc_group, metric): support
        for doc_group, metric, support in summary.select(
            "doc_group", "metric", "support"
        ).iter_rows()
    }
    assert supports[("Book", "f1")] == 3
    assert supports[("Book", "prec")] == 2
    assert supports[("Book", "rec")] == 3
    assert supports[("Article", "f1")] == 2
    assert supports[("Article", "prec")] == 2
    assert supports[("Article", "rec")] == 1

    overall = agg.compute_intermediate_results(group_by=None)
    assert (overall.data["n_prec"].item(), overall.data["n_rec"].item()) == (4, 4)
    assert agg.summarise_results()["support"].to_list() == [4, 4, 4]


def test_summary_preserves_strata(comparator: Comparator) -> None:
    comparator.comparison_matrix = comparator.comparison_matrix.with_columns(
        pl.when(pl.col("doc_id") == "A")
        .then(pl.lit("Book"))
        .otherwise(pl.lit("Article"))
        .alias("doc_group")
    )
    agg = Aggregator(comparator)
    agg.compute_intermediate_results(group_by=["doc_id", "doc_group"])
    summary = agg.summarise_results()

    assert summary.columns == ["doc_group", "metric", "mode", "value", "support"]
    book = _summary_dict(summary.filter(pl.col("doc_group") == "Book"))
    article = _summary_dict(summary.filter(pl.col("doc_group") == "Article"))
    assert book["f1"] == (pytest.approx(4 / 7), 1)
    assert book["prec"] == (pytest.approx(2 / 3), 1)
    assert article["rec"] == (0.0, 1)


@pytest.mark.parametrize(
    ("group_by", "match"),
    [
        (["doc_id", "missing"], "not found"),
        (["doc_id", "gt_value"], "value columns"),
    ],
)
def test_invalid_group_by_raises(
    comparator: Comparator, group_by: str | list[str], match: str
) -> None:
    with pytest.raises(ValueError, match=match):
        Aggregator(comparator).compute_intermediate_results(group_by=group_by)


def test_summarise_without_intermediate_results_raises(
    comparator: Comparator,
) -> None:
    with pytest.raises(ValueError, match="compute_intermediate_results"):
        Aggregator(comparator).summarise_results()

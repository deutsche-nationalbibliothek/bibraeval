import json
from pathlib import Path
from unittest.mock import patch

import polars as pl
import pytest
import yaml
from polars.testing import assert_frame_equal
from pydantic import BaseModel, ConfigDict, Field

from bibraeval.aggregator import AggregationMode, Aggregator
from bibraeval.comparator import Comparator
from bibraeval.data_ingester import RecordCollection
from bibraeval.evaluator import Evaluator
from bibraeval.metric_conf import FieldMetricMapping


class PublicationMetadata(BaseModel):
    """Response model for publication metadata extraction."""

    model_config = ConfigDict(populate_by_name=True)

    language: list[str] = Field(default_factory=list)
    title: str | None = None
    year: str | None = None


CONFIG = {
    "title": {"metric": "levenshtein", "match_threshold": 0.5, "weight": 2.0},
    "year": {"metric": "exact", "weight": 1.0},
}

GT = {
    "A": {"title": "Title", "year": "2013", "language": ["ger"]},
    "B": {"title": "Other"},
}
PRED = {
    "A": {"title": "Titel", "year": "2014"},
    "B": {"title": "Other", "year": "2020"},
}


def _write_dir(directory: Path, records: dict[str, dict]) -> Path:
    directory.mkdir()
    for doc_id, payload in records.items():
        (directory / f"{doc_id}.json").write_text(json.dumps(payload))
    return directory


def _write_jsonl(file_path: Path, records: dict[str, dict]) -> Path:
    lines = [
        json.dumps({"doc_id": doc_id, "record": payload})
        for doc_id, payload in records.items()
    ]
    file_path.write_text("\n".join(lines))
    return file_path


@pytest.fixture
def gt_dir(tmp_path: Path) -> Path:
    return _write_dir(tmp_path / "gt", GT)


@pytest.fixture
def pred_dir(tmp_path: Path) -> Path:
    return _write_dir(tmp_path / "pred", PRED)


def _manual_summary(
    gt_path: Path, pred_path: Path, config, group_by: str | None
) -> pl.DataFrame:
    comparator = Comparator(
        RecordCollection.create_from_dir(gt_path, schema=PublicationMetadata),
        RecordCollection.create_from_dir(pred_path, schema=PublicationMetadata),
        config,
    )
    aggregator = Aggregator(comparator)
    return aggregator.summarise_results(
        aggregator.compute_intermediate_results(group_by)
    )


@pytest.mark.parametrize(
    ("mode", "group_by"),
    [("doc-avg", "doc_id"), ("field-avg", "field_name"), ("micro-avg", None)],
)
def test_matches_manual_pipeline(
    gt_dir: Path, pred_dir: Path, mode: AggregationMode, group_by: str | None
) -> None:
    result = Evaluator(
        gt_dir, pred_dir, PublicationMetadata, mode=mode, field_metric_config=CONFIG
    ).compute_metrics()

    assert_frame_equal(result, _manual_summary(gt_dir, pred_dir, CONFIG, group_by))
    assert result["mode"].unique().to_list() == [mode]


def test_default_mode_is_field_avg(gt_dir: Path, pred_dir: Path) -> None:
    result = Evaluator(gt_dir, pred_dir, PublicationMetadata).compute_metrics()

    assert result["mode"].unique().to_list() == ["field-avg"]


def test_without_config_uses_exact_matching_on_all_fields(
    gt_dir: Path, pred_dir: Path
) -> None:
    result = Evaluator(gt_dir, pred_dir, PublicationMetadata).compute_metrics()

    assert_frame_equal(result, _manual_summary(gt_dir, pred_dir, None, "field_name"))


def test_reads_jsonl_files(tmp_path: Path, gt_dir: Path, pred_dir: Path) -> None:
    gt_file = _write_jsonl(tmp_path / "gt.jsonl", GT)
    pred_file = _write_jsonl(tmp_path / "pred.jsonl", PRED)

    from_files = Evaluator(
        gt_file, pred_file, PublicationMetadata, field_metric_config=CONFIG
    ).compute_metrics()
    from_dirs = Evaluator(
        gt_dir, pred_dir, PublicationMetadata, field_metric_config=CONFIG
    ).compute_metrics()

    assert_frame_equal(from_files, from_dirs)


@pytest.mark.parametrize("config_type", ["schema", "yaml_str", "yaml_path"])
def test_config_types_are_equivalent(
    tmp_path: Path, gt_dir: Path, pred_dir: Path, config_type: str
) -> None:
    yaml_path = tmp_path / "field-metrics.yaml"
    yaml_path.write_text(yaml.safe_dump(CONFIG))
    config = {
        "schema": FieldMetricMapping.from_dict(CONFIG),
        "yaml_str": str(yaml_path),
        "yaml_path": yaml_path,
    }[config_type]

    result = Evaluator(
        gt_dir, pred_dir, PublicationMetadata, field_metric_config=config
    ).compute_metrics()
    expected = Evaluator(
        gt_dir, pred_dir, PublicationMetadata, field_metric_config=CONFIG
    ).compute_metrics()

    assert_frame_equal(result, expected)


def test_invalid_mode_raises(gt_dir: Path, pred_dir: Path) -> None:
    with pytest.raises(ValueError, match="Invalid mode"):
        Evaluator(gt_dir, pred_dir, PublicationMetadata, mode="macro-avg")  # ty: ignore[invalid-argument-type]


def test_mismatched_doc_ids(tmp_path: Path, pred_dir: Path) -> None:
    gt_dir = _write_dir(tmp_path / "gt_extra", {**GT, "C": {"title": "Extra"}})

    with pytest.raises(ValueError, match="mismatched doc_ids"):
        Evaluator(gt_dir, pred_dir, PublicationMetadata).compute_metrics()

    result = Evaluator(
        gt_dir, pred_dir, PublicationMetadata, drop_mismatched_doc_ids=True
    ).compute_metrics()
    assert result.height > 0


@pytest.mark.parametrize("extra_side", ["gt", "pred"])
def test_mismatched_doc_ids_raise_when_not_dropped(
    tmp_path: Path, extra_side: str
) -> None:
    extra = {"C": {"title": "Extra"}}
    gt_dir = _write_dir(tmp_path / "gt", {**GT, **extra} if extra_side == "gt" else GT)
    pred_dir = _write_dir(
        tmp_path / "pred", {**PRED, **extra} if extra_side == "pred" else PRED
    )
    evaluator = Evaluator(
        gt_dir, pred_dir, PublicationMetadata, drop_mismatched_doc_ids=False
    )

    with pytest.raises(ValueError, match="mismatched doc_ids"):
        evaluator.compute_metrics()


def test_get_comparison_matrix_raises_if_not_computed(
    gt_dir: Path, pred_dir: Path
) -> None:
    evaluator = Evaluator(gt_dir, pred_dir, PublicationMetadata)

    with pytest.raises(ValueError, match="Comparison matrix is not available"):
        evaluator.get_comparison_matrix()


def test_get_comparison_matrix_returns_correct_structure(
    gt_dir: Path, pred_dir: Path
) -> None:
    evaluator = Evaluator(gt_dir, pred_dir, PublicationMetadata)
    evaluator.compute_metrics()

    comparison_matrix = evaluator.get_comparison_matrix()

    assert comparison_matrix.height > 0
    assert set(comparison_matrix.columns) == {
        "doc_id",
        "field_name",
        "gt_present",
        "pred_present",
        "gt_value",
        "pred_value",
        "cell_agreement",
        "weight",
    }


def test_get_intermediate_results_raises_if_not_computed(
    gt_dir: Path, pred_dir: Path
) -> None:
    evaluator = Evaluator(gt_dir, pred_dir, PublicationMetadata)

    with pytest.raises(ValueError, match="Intermediate results are not available"):
        evaluator.get_intermediate_results()


def test_get_intermediate_results_returns_correct_structure(
    gt_dir: Path, pred_dir: Path
) -> None:
    evaluator = Evaluator(gt_dir, pred_dir, PublicationMetadata)
    evaluator.compute_metrics()

    intermediate_results = evaluator.get_intermediate_results()

    assert intermediate_results.height > 0
    assert set(intermediate_results.columns) == {
        "field_name",
        "support_prec",
        "prec",
        "support_rec",
        "rec",
        "weight",
        "f1",
    }


@pytest.mark.parametrize("results_dir", [None, "/some/path"])
def test_compute_metrics_saves_results(
    gt_dir: Path, pred_dir: Path, results_dir: str | None
) -> None:
    evaluator = Evaluator(
        gt_dir, pred_dir, PublicationMetadata, field_metric_config=CONFIG
    )

    with patch.object(evaluator, "_save_results") as mock_save:
        summary = evaluator.compute_metrics(results_dir)

    assert isinstance(summary, pl.DataFrame)
    assert {"metric", "mode", "value", "support"} <= set(summary.columns)

    if results_dir is not None:
        mock_save.assert_called_once_with(results_dir)
    else:
        mock_save.assert_not_called()


def test_save_to_csv(tmp_path: Path) -> None:
    evaluator = Evaluator(tmp_path, tmp_path, BaseModel)

    df = pl.DataFrame(
        {
            "doc_id": ["doc1", "doc2"],
            "title": ["Book A", "Book B"],
        }
    )

    target_dir = tmp_path / "nested" / "results"
    evaluator._save_to_csv(df, target_dir, "results.csv")

    file_path = target_dir / "results.csv"

    assert file_path.exists()

    saved_df = pl.read_csv(file_path)
    assert saved_df.equals(df)


def test_save_to_csv_converts_object_columns(tmp_path: Path) -> None:
    evaluator = Evaluator(tmp_path, tmp_path, BaseModel)

    df = pl.DataFrame(
        {
            "doc_id": ["doc1", "doc2"],
            "value": pl.Series(
                "value",
                [{"title": "Book A"}, {"title": "Book B"}],
                dtype=pl.Object,
            ),
        }
    )

    evaluator._save_to_csv(df, tmp_path, "results.csv")

    saved_df = pl.read_csv(tmp_path / "results.csv")

    assert saved_df.schema["value"] == pl.String
    assert saved_df["value"].to_list() == [
        "{'title': 'Book A'}",
        "{'title': 'Book B'}",
    ]


def test_save_results(tmp_path: Path) -> None:
    evaluator = Evaluator(tmp_path, tmp_path, BaseModel)

    evaluator.summary = pl.DataFrame(
        {
            "metric": ["f1", "prec", "rec"],
            "mode": ["field-avg"] * 3,
            "value": [0.9, 0.85, 0.95],
            "support": [10, 10, 10],
        }
    )

    evaluator.intermediate_results = pl.DataFrame(
        {
            "field_name": ["title", "author"],
            "prec": [0.9, 0.8],
            "rec": [0.95, 0.85],
            "f1": [0.92, 0.82],
        }
    )

    evaluator.comparison_matrix = pl.DataFrame(
        {
            "doc_id": ["doc1", "doc2"],
            "field_name": ["title", "author"],
            "cell_agreement": [1.0, 0.8],
        }
    )

    evaluator._save_results(tmp_path)

    expected_files = {
        "summary_metrics.csv": evaluator.summary,
        "intermediate_results.csv": evaluator.intermediate_results,
        "comparison_matrix.csv": evaluator.comparison_matrix,
    }

    for filename, expected_df in expected_files.items():
        file_path = tmp_path / filename

        assert file_path.exists()

        saved_df = pl.read_csv(file_path)
        assert saved_df.equals(expected_df)

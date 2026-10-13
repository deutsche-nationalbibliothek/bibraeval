import json
from pathlib import Path

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
    lines = [json.dumps({"doc_id": doc_id, **p}) for doc_id, p in records.items()]
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

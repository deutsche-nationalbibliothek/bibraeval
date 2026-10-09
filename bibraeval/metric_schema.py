"""Per-field metric configuration for record comparison."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

from bibraeval.field_metrics import ListComparison, exact, fieldMetric, levenshtein


class FieldMetricConfig(BaseModel):
    """Metric configuration for a single metadata field."""

    model_config = ConfigDict(extra="forbid")

    metric: Literal["exact", "levenshtein"]
    match_threshold: float | None = Field(default=None, ge=0.0, le=1.0)
    weight: float = Field(default=1.0, gt=0.0)
    list_comparison: ListComparison = "all-of"

    @model_validator(mode="after")
    def _check_match_threshold(self) -> FieldMetricConfig:
        if self.metric == "levenshtein" and self.match_threshold is None:
            raise ValueError("match_threshold is required for metric 'levenshtein'")
        if self.metric != "levenshtein" and self.match_threshold is not None:
            raise ValueError(
                f"match_threshold is not supported for metric '{self.metric}'"
            )
        return self


class field_metric_schema(BaseModel):
    """Mapping of field names to their metric configuration."""

    model_config = ConfigDict(extra="forbid")

    fields: dict[str, FieldMetricConfig]

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> field_metric_schema:
        """Build a schema from `{"fields": {...}}` or a flat field mapping."""
        if set(data) == {"fields"}:
            return cls.model_validate(data)
        return cls.model_validate({"fields": data})

    @classmethod
    def from_yaml(cls, path: str | Path) -> field_metric_schema:
        """Load a schema from a YAML file, e.g. `field-metrics.yaml`."""
        with Path(path).open(encoding="utf-8") as file:
            data = yaml.safe_load(file)
        if not isinstance(data, dict):
            raise TypeError(
                f"Expected a dictionary in {path}, got {type(data).__name__}"
            )
        return cls.from_dict(data)

    def build_metric(self, field_name: str) -> fieldMetric:
        """Instantiate the configured metric for `field_name`."""
        config = self.fields[field_name]
        if config.metric == "levenshtein":
            if config.match_threshold is None:
                raise ValueError(f"Field '{field_name}' lacks a match_threshold")
            return levenshtein(
                threshold=config.match_threshold,
                list_comparison=config.list_comparison,
            )
        return exact(list_comparison=config.list_comparison)

"""BIBRA evaluation package."""

from .aggregator import Aggregator, IntermediateResults
from .comparator import Comparator
from .data_ingester import Record, RecordCollection
from .field_metrics import Exact, FieldMetric, Levenshtein
from .metric_conf import FieldMetricConfig, FieldMetricMapping

__all__ = [
    "Aggregator",
    "Comparator",
    "Exact",
    "FieldMetric",
    "FieldMetricConfig",
    "FieldMetricMapping",
    "Levenshtein",
    "IntermediateResults",
    "Record",
    "RecordCollection",
]

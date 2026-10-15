# BIBRA-Eval


![Status: Work in
Progress](https://img.shields.io/badge/status-work--in--progress-orange.png)

Evaluating descriptive cataloguing records created with BIBRA.
[BIBRA](https://github.com/NatLibFi/BIBRA) is an (L)LM-based assistance
tool, to generate bibliographic metadata from a given PDF-Input.
`BIBRA-Eval` provides tooling to make direct comparisons of
LLM-generated BIBRA JSON-Records with gold-standard records coming from
a different source (e.g. manual indexing). It validates records against a 
Pydantic schema, scores configured fields, and summarizes precision, recall, 
and F1 with document, field, or micro averaging. Its comparison matrix also 
supports stratified drill-downs.

## Installation

From a checkout of this package, install it into the active environment:

```bash
uv pip install -e .
```

The package requires Python 3.11 or newer. Import the public API with
`import bibraeval`; no `bibra-eval` command-line interface is currently
provided.

## Quick start

Prepare two datasets with matching document IDs, then pass their paths and a
Pydantic metadata model to `Evaluator`:

```python
from pydantic import BaseModel

from bibraeval import Evaluator


class PublicationMetadata(BaseModel):
    title: str | None = None
    year: str | None = None


result = Evaluator(
    "data/gold.jsonl",
    "data/predictions.jsonl",
    PublicationMetadata,
).compute_metrics()
print(result)
```

By default, every schema field is compared with exact matching and uniform
weight. `Evaluator` defaults to `field-avg`; set `mode` to `doc-avg` or
`micro-avg` to choose another aggregation. The result is a Polars DataFrame
with one row per metric and `metric`, `mode`, `value`, and `support` columns.

## Inputs and matching

Each input can be a directory of JSON files or a JSONL file. Directory
filenames (without `.json`) are document IDs; JSONL records require a non-empty
string `doc_id` property. Remaining values are validated by the supplied
Pydantic model. IDs must match across datasets by default. Set
`drop_mismatched_doc_ids=True` to evaluate only the IDs present on both sides.

## Field metrics

Configure fields with `FieldMetricMapping` or a dictionary/YAML file. Supported
metrics are `exact` and `levenshtein`; each field may also have a positive
weight and list comparison mode (`all-of` or `any-of`). Levenshtein
configuration requires a `match_threshold` between 0 and 1 for aligning list
items. Scalar Levenshtein scores are similarity ratios and are not cut off by
that list-alignment threshold.

## Documentation

Start with the [documentation index](docs/index.md) for focused guides and the
generated [API reference](docs/api/index.md). See the
[architecture guide](docs/guides/architecture.md) for a complete class diagram
for developers.
To build the Sphinx site, install the `docs` dependency group and run
`sphinx-build -W -b html docs docs/_build/html` from this directory. See
[docs/README.md](docs/README.md) for the exact local setup commands.

## Disclaimer

This project was constructed under assistance of Github Copilot. While the
class hierarchy and overall software specification comes from the developers, 
AI  assistance was used to generate code, tests and documentation. All AI 
generated content has been reviewed line by line and the authors take
full responsibility for the generated code (AI:AMBER following the 
[AI Traffic Lights Protocol](https://nlkw.de/en/blog/ai-tlp/) by Nila Löber).

## Example

BIBRA-Eval allows specification of custom Metadata Schemas and a custom schema
to define metrics per field. List-Type fields are matched on a fuzzy 
matching principle, that can be adjusted with a custom `match_threshold`. 
Lists can be compared in two modes: "all-of" counts all values in ground_truth
and predictions and computes an f1-score between both.
"any-of" only return the best match. 
E.g. if language is a field that can have multiple values, "any-of" comparison 
would only require for one of the values to be found, whereas "all-of" 
requires all values to be found.

```python
from pydantic import BaseModel, ConfigDict, Field
from bibraeval.comparator import Comparator


class PublicationMetadata(BaseModel):
    """Response model for publication metadata extraction."""

    model_config = ConfigDict(populate_by_name=True)

    language: list[str] = Field(default_factory=list)
    title: str | None = None
    year: str | None = None
    authors: list[str] = Field(default_factory=list)
    p_isbn: list[str] = Field(default_factory=list, alias="p-isbn")


FieldMetricMapping = {
    "title": {"metric": "Levenshtein", "match_threshold": 0.7, "weight": 2.0},
    "year": {"metric": "Exact", "weight": 1.0},
    "authors": {
        "metric": "Levenshtein",
        "match_threshold": 0.7,
        "weight": 1.5,
        "list_comparison": "all-of",
    },
    "p-isbn": {"metric": "Exact", "weight": 1.0},
    "language": {
        "metric": "Levenshtein",
        "match_threshold": 0.6,
        "weight": 1.0,
        "list_comparison": "all-of",
    },
}

ground_truth = RecordCollection[PublicationMetadata]()
ground_truth.add_payload(
    doc_id="123",
    payload={
        "title": "Epic work on subject indexing",
        "authors": ["Librarian, The"],
        "language": ["eng"],
    },
    schema=PublicationMetadata,
)

ground_truth.add_payload(
    doc_id="007",
    payload={
        "title": "Struggles of modern library systems - A Collection",
        "authors": ["Musterperson, Maxi", "Doe, John"],
        "year": "1915",
        "language": ["ger", "eng"],
    },
    schema=PublicationMetadata,
)

predictions = RecordCollection[PublicationMetadata]()
predictions.add_payload(
    doc_id="123",
    payload={
        "title": "_Epic work on subject indexing_",
        "authors": ["Librarian, A"],
        "language": ["eng"],
    },
    schema=PublicationMetadata,
)

predictions.add_payload(
    doc_id="007",
    payload={
        "title": "Struggles of modern library systems",
        "year": "2026",
        "authors": ["Musterperson", "Doe"],
        "language": ["german", "eng"],
        "p-isbn": ["978-3-86539-327-2"],
    },
    schema=PublicationMetadata,
)


comp = Comparator(
    ground_truth,
    predictions,
    metric_schema=FieldMetricMapping,
    drop_mismatched_doc_ids=True,
)

comp.comparison_matrix

comp.compute_cell_agreement()
```

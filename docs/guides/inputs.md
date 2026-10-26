# Preparing inputs

## Metadata schema

Provide a {Pydantic `BaseModel`](https://pydantic.dev/docs/validation/latest/api/pydantic/base_model/)
describing the fields to validate. Pydantic's configured
validation and extra-field behaviour applies.

```python
from pydantic import BaseModel, ConfigDict, Field


class PublicationMetadata(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    title: str | None = None
    year: str | None = None
    authors: list[str] = Field(default_factory=list)
    p_isbn: list[str] = Field(default_factory=list, alias="p-isbn")
```

**Note**: One particular instance of such a pydantic BaseModel is BIBRA's 
internal metadatascheme that you can import from BIBRA itself:

```python
from bibra.types import PublicationMetadata
```

## JSON directory

Use one JSON object per `*.json` file. The filename stem is the document ID;
the JSON object contains metadata only. Only files directly inside the given
directory are read.

```text
ground_truth/
  001.json
  002.json
predictions/
  001.json
  002.json
```

For example, `ground_truth/001.json` could contain:

```json
{"title": "A sample title", "year": "2024", "authors": ["A. Author"]}
```

## JSONL file

Use one JSON object per line, including a non-empty string `"doc_id"` and the
 actual `"record"` in a nested substructure. Blank lines are ignored.

```json
{"doc_id": "001", "record": {"title": "A sample title", "year": "2024"}}
{"doc_id": "002", "record": {"title": "Another title", "authors": ["B. Writer"]}}
```

Duplicate IDs replace earlier records in the same collection, so keep IDs
unique. Invalid JSON, a non-object record, a missing JSONL `doc_id`, or schema
validation errors int the "record" part stop ingestion.

## Matching IDs

Records are matched by ID, never by input order. By default, the two datasets
must contain exactly the same IDs or evaluation raises `ValueError`. Set
`drop_mismatched_doc_ids=True` on `Evaluator` or `Comparator` to compare only
IDs that occur in both datasets; IDs unique to either side are ignored.

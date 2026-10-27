from __future__ import annotations

import json
from pathlib import Path
from typing import Any, TypeVar

from pydantic import BaseModel, Field

MetadataT = TypeVar("MetadataT", bound=BaseModel)


class Record[MetadataT: BaseModel](BaseModel):
    """A record with a stable document identifier and validated metadata.

    ``metadata`` is parsed with the caller-supplied Pydantic model; ``doc_id``
    is kept separately so records can be matched independently of row order.
    """

    doc_id: str
    metadata: MetadataT

    @classmethod
    def from_payload(
        cls,
        doc_id: str,
        payload: dict[str, Any],
        schema: type[MetadataT],
    ) -> Record[MetadataT]:
        """Validate a metadata payload and create a record for ``doc_id``.

        Args:
            doc_id: Stable identifier used to match this record across datasets.
            payload: Metadata fields accepted by ``schema``.
            schema: Pydantic model used to validate the metadata.
        """
        validated_metadata = schema.model_validate(payload)
        return cls(doc_id=doc_id, metadata=validated_metadata)


class RecordCollection[MetadataT: BaseModel](BaseModel):
    """A collection of records keyed by document identifier."""

    records: dict[str, Record[MetadataT]] = Field(default_factory=dict)

    @classmethod
    def create_from_dir(
        cls,
        directory: str | Path,
        schema: type[MetadataT],
    ) -> RecordCollection[MetadataT]:
        """Load ``*.json`` records from a directory, using each filename stem
        as its document ID.

        Files must contain JSON objects. Other files and nested directories are
        ignored.
        """
        collection = cls()
        for record_path in sorted(Path(directory).glob("*.json")):
            with record_path.open(encoding="utf-8") as record_file:
                payload = json.load(record_file)
            if not isinstance(payload, dict):
                msg = f"Record file {record_path} must contain a JSON object."
                raise TypeError(msg)
            collection.add_payload(
                doc_id=record_path.stem,
                payload=payload,
                schema=schema,
            )
        return collection

    @classmethod
    def create_from_file(
        cls,
        file_path: str | Path,
        schema: type[MetadataT],
    ) -> RecordCollection[MetadataT]:
        """Load JSONL records whose objects each contain a non-empty ``doc_id``.

        Blank lines are ignored. Duplicate IDs replace the earlier record.
        """
        collection = cls()
        with Path(file_path).open(encoding="utf-8") as jsonl_file:
            for line_number, line in enumerate(jsonl_file, start=1):
                if not line.strip():
                    continue
                payload = json.loads(line)
                if not isinstance(payload, dict):
                    msg = (
                        f"Line {line_number} in {file_path} must contain a JSON object."
                    )
                    raise TypeError(msg)
                doc_id = payload.get("doc_id")
                if not isinstance(doc_id, str) or not doc_id:
                    msg = f"Line {line_number} in {file_path} must contain a doc_id."
                    raise ValueError(msg)
                collection.add_payload(
                    doc_id=doc_id,
                    payload={
                        key: value for key, value in payload.items() if key != "doc_id"
                    },
                    schema=schema,
                )
        return collection

    def add_record(self, record: Record[MetadataT]) -> None:
        """Store a record, replacing any existing record with the same ID."""
        self.records[record.doc_id] = record

    def get_record(self, doc_id: str) -> Record[MetadataT] | None:
        """Return a record by ID, or ``None`` when the ID is absent."""
        return self.records.get(doc_id)

    def add_payload(
        self,
        doc_id: str,
        payload: dict[str, Any],
        schema: type[MetadataT],
    ) -> Record[MetadataT]:
        """Validate payload against metadata schema and store
        payload, replacing an existing matching ID."""
        record = Record.from_payload(doc_id=doc_id, payload=payload, schema=schema)
        self.add_record(record)
        return record

    def as_list(self) -> list[Record[MetadataT]]:
        """Return the stored records as a list in insertion order."""
        return list(self.records.values())

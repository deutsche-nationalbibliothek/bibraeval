from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field

MetadataT = TypeVar("MetadataT", bound=BaseModel)


class Record(BaseModel, Generic[MetadataT]):
    """A record with a stable document identifier and validated metadata."""

    doc_id: str
    metadata: MetadataT

    @classmethod
    def from_payload(
        cls,
        doc_id: str,
        payload: dict[str, Any],
        schema: type[MetadataT],
    ) -> Record[MetadataT]:
        validated_metadata = schema.model_validate(payload)
        return cls(doc_id=doc_id, metadata=validated_metadata)


class RecordCollection(BaseModel, Generic[MetadataT]):
    """A collection of records keyed by document identifier."""

    records: dict[str, Record[MetadataT]] = Field(default_factory=dict)

    @classmethod
    def create_from_dir(
        cls,
        directory: str | Path,
        schema: type[MetadataT],
    ) -> RecordCollection[MetadataT]:
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
        self.records[record.doc_id] = record

    def get_record(self, doc_id: str) -> Record[MetadataT] | None:
        return self.records.get(doc_id)

    def add_payload(
        self,
        doc_id: str,
        payload: dict[str, Any],
        schema: type[MetadataT],
    ) -> Record[MetadataT]:
        record = Record.from_payload(doc_id=doc_id, payload=payload, schema=schema)
        self.add_record(record)
        return record

    def as_list(self) -> list[Record[MetadataT]]:
        return list(self.records.values())

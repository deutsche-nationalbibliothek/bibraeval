from __future__ import annotations

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
    ) -> "Record[MetadataT]":
        validated_metadata = schema.model_validate(payload)
        return cls(doc_id=doc_id, metadata=validated_metadata)


class RecordCollection(BaseModel, Generic[MetadataT]):
    """A collection of records keyed by document identifier."""

    records: dict[str, Record[MetadataT]] = Field(default_factory=dict)

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
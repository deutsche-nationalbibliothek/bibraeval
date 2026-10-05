from pydantic import BaseModel, ConfigDict, Field

from bibraeval.data_ingester import Record, RecordCollection


class PublicationMetadata(BaseModel):
    """Response model for publication metadata extraction."""

    model_config = ConfigDict(populate_by_name=True)

    language: list[str] = Field(default_factory=list)
    title: str | None = None
    alt_title: str | None = None
    creator: list[str] = Field(default_factory=list)
    year: str | None = None
    publisher: list[str] = Field(default_factory=list)
    publisher_place: list[str] = Field(default_factory=list)
    doi: str | None = None
    e_isbn: list[str] = Field(default_factory=list, alias="e-isbn")
    p_isbn: list[str] = Field(default_factory=list, alias="p-isbn")
    e_issn: str | None = Field(default=None, alias="e-issn")
    p_issn: str | None = Field(default=None, alias="p-issn")
    type_coar: str | None = None


PAYLOAD = {
    "title": "Werke der Freiheit",
    "year": "2013",
    "creator": ["Georg Büchner"],
    "language": ["ger"],
    "publisher": ["Marix-Verl."],
    "p-isbn": ["978-3-86539-327-2", "3-86539-327-6"],
}


def test_record_from_payload_validates_user_metadata_schema() -> None:
    record = Record.from_payload(
        doc_id="103571650X",
        payload=PAYLOAD,
        schema=PublicationMetadata,
    )

    assert record.doc_id == "103571650X"
    assert record.metadata.title == "Werke der Freiheit"
    assert record.metadata.year == "2013"
    assert record.metadata.creator == ["Georg Büchner"]
    assert record.metadata.language == ["ger"]
    assert record.metadata.publisher == ["Marix-Verl."]
    assert record.metadata.p_isbn == ["978-3-86539-327-2", "3-86539-327-6"]


def test_record_collection_stores_records_by_doc_id() -> None:
    collection = RecordCollection[PublicationMetadata]()
    record = Record.from_payload(
        doc_id="103571650X",
        payload=PAYLOAD,
        schema=PublicationMetadata,
    )

    collection.add_record(record)

    assert collection.get_record("103571650X") == record
    assert len(collection.as_list()) == 1
    assert collection.as_list()[0].doc_id == "103571650X"


def test_record_collection_create_from_dir_loads_json_records(tmp_path) -> None:
    record1_path = tmp_path / "103571650X.json"
    record1_path.write_text(
        '{' \
            '"title": "Werke der Freiheit", ' \
            '"year": "2013"' \
        '}',
        encoding="utf-8",
    )
    record2_path = tmp_path / "991651952.json"
    record2_path.write_text(
        '{' \
            '"language": ["de"], ' \
            '"title": "DAS GESAMTWERK WOLFGANG BORCHERT",' \
            ' "alt_title": null, "creator": ["Wolfgang Borchert"], ' \
            '"year": null, "publisher": ["Rowohlt Taschenbuch Verlag"], ' \
            '"doi": null, ' \
            '"e-isbn": [], ' \
            '"p-isbn": [], ' \
            '"e-issn": null, ' \
            '"p-issn": null, ' \
            '"type_coar": "book"' \
        '}',
        encoding="utf-8",
    )

    collection = RecordCollection.create_from_dir(tmp_path, PublicationMetadata)

    record1 = collection.get_record("103571650X")
    assert record1 is not None
    assert record1.metadata.title == "Werke der Freiheit"
    assert record1.metadata.year == "2013"

    record2 = collection.get_record("991651952")
    assert record2 is not None
    assert record2.metadata.title == "DAS GESAMTWERK WOLFGANG BORCHERT"
    assert record2.metadata.language == ["de"]


def test_record_collection_create_from_file_loads_jsonl_records(tmp_path) -> None:
    record_path = tmp_path / "records.jsonl"
    record_path.write_text(
        """
        {"doc_id": "103571650X", "title": "Werke der Freiheit", "year": "2013"}\n
        {"doc_id": "991651952", "language": ["de"], "title": "DAS GESAMTWERK WOLFGANG BORCHERT", "alt_title": null, "creator": ["Wolfgang Borchert"], "year": null, "publisher": ["Rowohlt Taschenbuch Verlag"], "doi": null, "e-isbn": [], "p-isbn": [], "e-issn": null, "p-issn": null, "type_coar": "book"}\n
        """,
        encoding="utf-8",
    )

    collection = RecordCollection.create_from_file(record_path, PublicationMetadata)
    assert len(collection.as_list()) == 2

    record = collection.get_record("991651952")
    assert record is not None
    assert record.metadata.title == "DAS GESAMTWERK WOLFGANG BORCHERT"
    assert record.metadata.language == ["de"]
    assert record.metadata.creator == ["Wolfgang Borchert"]
    assert record.metadata.publisher == ["Rowohlt Taschenbuch Verlag"]

    record = collection.get_record("103571650X")
    assert record is not None
    assert record.metadata.title == "Werke der Freiheit"
    assert record.metadata.year == "2013"

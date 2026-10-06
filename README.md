# BIBRA-Eval


![Status: Work in
Progress](https://img.shields.io/badge/status-work--in--progress-orange.png)

Evaluating descriptive cataloguing records created with BIBRA.
[BIBRA](https://github.com/NatLibFi/BIBRA) is an (L)LM-based assistance
tool, to generate bibliographic metadata from a given PDF-Input.
`BIBRA-Eval` provides tooling to make direct comparisons of
LLM-generated BIBRA JSON-Records with gold-standard records coming from
a different source (e.g. manual indexing).

## Metrics

BIBRA-Eval requires records that follow a specific JSON-scheme. Built on
top of the record scheme is an evaluation scheme, that specifies the
fields that should be part of the comparison and the metrics that apply
to each field.

- binary metrics: some fields like `year` or `isbn` are best evaluated
  by requiring exact matches. So matches are either true or false
- string difference: fields like title or publisher should allow some
  degree of tolerance between two records. Here we measure the
  levenshtein distance, i.e. the minimal number of string edits that
  lead from field content `x` to the gold-standard content `y`
- llm-as-a-judge (`experimental`): fields with complex content, that may
  be expressed in equivalent but dissimilar form, may be judged by a
  light LLM
- metrics for list comparison: fields with multiple subfields (e.g. a
  list of authors) are aligned with a fuzzy match. The score per field
  is calculated as the average levenshtein distance between the matches

The evaluation scheme also supports optional weights per field,
e.g. correctness of the title could be more important then correctness
of the alt_title.

## Levels of evaluation

Metrics can be calculated along various levels:

- direct record comparison (record to record results): this forms the
  basis for all other computations
- field average: what is the average agreement across all documents in a
  test set along one particular field
- record average: what is the average agreement in a test set across all
  fields and documents

In determining results, there are different paths or modes for
aggregating results:

- document macro-average: compute average result per doc first (along
  all fields), then compute average across documents
- field macro-average: compute average results per field (along all
  documents), then compute average across all fields
- micro-average: no intermediate aggregation, average all field-to-field
  results in one

## Data format

The required input format is either a folder (`directory-format`) of
json-records following BIBRA’s JSON-Scheme or a single jsonl-file (
`single-file-format`) containing all records of a test set in a single
file.

For data in `directory-format` the gold-standard and the predictions
should be separate directories. Matches between records are performed on
the basis of record-file-names. So these should match between both
directories.

For data in ( `single-file-format`) a `doc_id` field is mandatory, to
make matches.

## Client

BIBRA-Eval provides a client to start evaluation from terminal.

Directory format:

``` bash
bibra-eval --mode field-avg GOLD-STANDRAD-DIR/ PREDICTIONS-DIR/
```

Output: \| field \| precision \| rec \| acc \| cfa \| \|————————————–\|
\| title \| … \| … \| … \| … \| \| creator \| … \| … \| … \| … \| \| …
\| … \| … \| … \| … \| \| ———-\| \| TOTAL (field-avg) \| … \| … \| … \|
… \|

The setting `--mode field-avg` is default. You can also use `micro` and
`doc-avg`.

## Python API

For interactive analysis BIBRA-Eval provides a python API to use in
individually tailored evaluation worksflows:

``` python
import bibraeval as be

GOLD_DIR = ...
PRED_DIR = ...

eval_schema = ...

comp = be.comparator(gold_dir=GOLD_DIR, pred_dir=PRED_DIR)

comp.compute_comparison_matrix()
comp.matrix.show()
```

The comparison matrix has a tabular format:

| doc_id | field_name | gold_present | pred_present | gt_value | pred_value |
|----|----|----|----|----|----|
| `103571650X` | `language` | false | false | `[]` | `[]` |
| `103571650X` | `p-isbn` | false | true | `[]` | `['978-3-86539-327-2']` |
| `103571650X` | `title` | true | true | `Werke der Freiheit` | `Werke der Freiheit` |
| `103571650X` | `year` | false | false | `null` | `null` |

``` python

comp.compute_intermediate_results()

comp.intermed.show()

comp.compute_metrics()

comp.metrics.show()
```

## Class Diagram

``` mermaid
classDiagram
    class MetadataT {
        <<type parameter>>
    }

    class BaseModel {
        <<Pydantic>>
    }

    class Record~MetadataT~ {
        +str doc_id
        +MetadataT metadata
        +from_payload(doc_id, payload, schema)
    }

    class RecordCollection~MetadataT~ {
        +dict records
        +create_from_dir(directory, schema)
        +create_from_file(file_path, schema)
        +add_record(record)
        +get_record(doc_id)
        +add_payload(doc_id, payload, schema)
        +as_list()
    }

    class Comparator {
        +RecordCollection gold_standard
        +RecordCollection predictions
        +bool drop_mismatched_doc_ids
        +DataFrame fused_records
        +compute_cell_agreement(fused_df, metric)
    }

    class fieldMetric {
        +score(gt_value, predicted_value) float
        #_score_scalar(gt_value, predicted_value) float
        #_match(gt_values, predicted_values) tuple
    }

    class exact {
        #_score_scalar(gt_value, predicted_value) float
        #_match(gt_values, predicted_values) tuple
    }

    class levenshtein {
        +float threshold
        +levenshtein(threshold)
        #_score_scalar(gt_value, predicted_value) float
        #_match(gt_values, predicted_values, threshold) tuple
    }

    RecordCollection~MetadataT~ "1" *-- "0..*" Record~MetadataT~ : records
    BaseModel <|-- Record~MetadataT~
    BaseModel <|-- RecordCollection~MetadataT~
    Record~MetadataT~ --> MetadataT : metadata
    Comparator --> RecordCollection~MetadataT~ : gold_standard and predictions
    Comparator --> fieldMetric : metric
    fieldMetric <|-- exact
    fieldMetric <|-- levenshtein
```

# Rules, Plan and Architecture

## About

BIBRA-Eval is a package designed to compute evaluation metrics between
metadata records produced by BIBRA and some gold standard records, e.g. stemming
from manual descriptive cataloguing. It aims to facilitate evaluation of
automatic cataloguing with BIBRA, enabling a tight feedback loop between
model optimization and metric results.
BIBRA-eval is also designed to facilitate drill down analyses of automatic
cataloguing results, providing insights into data domains with weak and
strong system performance.

## Rules

BIBRA-Eval is a `python` package. We use `polars` for processing data-frames.
Code is formatted with `ruff`. Tests are written with `pytest`. Data types are
defined with `pydantic`. Packaging is done with `uv`. We use github actions
for automatic checks.

### Code Style

We follow BIBRA's AGENTS.md rule for code, in particular:

Python code style follows Ruff format. Max line length 88 chars. Imports on top 
of file unless there are special reasons (document reason with comment). Modules
and classes must have docstrings.

### Code Quality Enforcement

Ruff checks are a mandatory gate before claiming any task complete. Every
agentic tool invocation must run both:

```bash
uv run ruff check --fix — linting (auto-fix where possible)
uv run ruff format — formatting (auto-format)
```

Run the checks again with `uv run ruff check` and `uv run ruff format --check`
to verify everything passes. Do not claim a task complete until both pass.

### Testing

Always run Pytest tests after any code changes.

### Python Tests

Run with verbose output: `uv run pytest -v`

Or run specific test files: `uv run pytest tests/test_<test_file>.py -v`

## Architecture

The package should contain submodules for each of the following parts:

### Data contract

This section defines the canonical input and output contracts used by BIBRA-Eval.
The goal is to ensure that all modules agree on what constitutes a valid record,
how missing values are represented, how field comparisons are encoded, and which
aggregation rules are valid.

#### Record identity

Each record must have a stable document identifier that can be used to match
records across gold-standard and prediction data.

Required:

- `doc_id`: identifier used to match records across datasets

Rules:

- `doc_id` must be unique within a dataset
- records are matched by `doc_id`, not by row order
- records present in only one dataset are discarded from further computation, warnings are written accordingly
- duplicate `doc_id` values are invalid input

Example:

```json
{
  "doc_id": "1234567890",
  "title": "Example title",
  "authors": ["Doe, Jane", "Smith, John"]
}
```

#### Valid record structure

A record is valid if it is a JSON object with:

- a valid `doc_id`
- supported field names according to the evaluation schema
- supported value types
- no duplicate field names
- field names that do not match the evaluation schema are ignored during
  data ingestions, but do not cause errors

Allowed types:

- scalar strings, numbers, booleans
- lists of scalar values
- nested objects only when explicitly supported by the field schema

During data ingestion the following cases are considered equivalent:

- missing field
- `null` value
- empty string
- empty list

#### Evaluation schema

The evaluation schema defines which fields are compared and which metric applies
to each field. Each field definition should specify:

- field name
- metric type
- optional weight
- whether the field is required
- whether comparison is scalar or list-aware

Example:

```json
{
  "title": {"metric": "levenshtein", "weight": 2.0, "required": true},
  "year": {"metric": "binary", "weight": 1.0, "required": false},
  "authors": {"metric": "list_fuzzy", "weight": 1.5, "required": false}
}
```

#### Comparison matrix contract

The comparison stage produces a row-per-field comparison matrix. Each row should
contain enough information to reconstruct the comparison logic in a later
aggregation stage.

Required columns:

- `doc_id`
- `field_name`
- `gold_present`
- `pred_present`
- `gold_value`
- `pred_value`
- `fa`
- `weight`

Optional columns:

- `doc_strata`: a list of be free column names defined by the user


Interpretation:

- `gold_present` and `pred_present` indicate whether each side contains a value
- `fa` is the field agreement score for that record/field pair
- `weight` is the field-level weight used in subsequent aggregation

Example:

```json
{
  "doc_id": "1234567890",
  "field_name": "title",
  "gold_present": true,
  "pred_present": true,
  "gold_value": "Example title",
  "pred_value": "Example Title",
  "fa": 0.93,
  "weight": 2.0
}
```

The comparison matrix must satisfy the following invariants:

- one row per `(doc_id, field_name)` comparison
- rows are valid even if one side ("gold_value" or "pred_value") is missing
- missingness is represented explicitly, not by silent coercion to zero
- if "gold_value" or "pred_value" is missing, "fa" is missing, too
- the schema is consistent across all metrics

#### Field agreement

`fa` is the field agreement score for a single field comparison between two
records. The score is metric-dependent and is interpreted as follows:

- `fa = 1.0` means perfect agreement
- `fa = 0.0` means complete disagreement
- intermediate values represent partial agreement

Supported metric families:

- binary comparison
- string similarity via Levenshtein distance
- list-aware fuzzy comparison
- experimental LLM-as-a-judge scoring

For list-valued fields, the list is first aligned and then the agreement of each
matched entry is computed; the final field score is then averaged across matched
items.

#### Missing-value policy

Missing values must follow explicit rules, not ad hoc logic. Recommended rules:

- gold missing, pred present: not applicable for recall, 0 for accuracy
- gold present, pred missing: not applicable for precision, 0 for accuracy
- both missing: not applicable
- both present: compare normally

This policy must be shared across all metrics. A metric may deviate only if the
metric specification makes that treatment explicit.

#### List comparison contract

List-valued fields are compared by aligning entries between the gold and
predicted lists and then comparing the matched items.

Required behavior:

- list comparison is item-level and symmetry-aware
- order is not assumed unless explicitly specified by the field schema
- duplicates are handled consistently by the metric definition
- the field-level list score is the mean of the matched-item agreement scores

Example:

```json
{
  "gold_value": ["Doe, Jane", "Smith, John"],
  "pred_value": ["Smith, John", "Doe, Jane"]
}
```

The implementation should determine the best alignment strategy for the field and
then compute the average agreement of the matched entries.

#### Aggregation contract

Aggregation is performed in three stages:

1. record-by-record comparison
   - produces the comparison matrix
2. intermediate aggregation
   - aggregate either across fields or across documents
   - preserve `doc_strata` when present
3. final aggregation
   - combine the intermediate results into a final score

Supported modes:

- document macro-average: compute per-document scores first, then average
  across documents
- field macro-average: compute per-field scores first, then average across
  fields
- micro-average: aggregate all valid field comparisons directly without an
  intermediate layer

Rules:

- weights are applied consistently across all aggregation stages
- empty or all-NA groups are excluded from the denominator unless the metric
  definition says otherwise
- `doc_strata` fields must be preserved in intermediate outputs for stratified
  analysis

#### Validation and failure behavior

The ingestion layer should validate inputs before computing results.

Validation failures should include:

- missing `doc_id`
- duplicate `doc_id`s
- mismatched record sets between gold and prediction data raise warnings
- invalid metric names or unsupported field schema entries

Errors should be explicit and should include the record identifier and the field
that failed validation.

#### Output contract

Final results should include enough metadata to understand the score and its
scope.

Recommended output fields:

- `metric`: Precision, Recall, Accuracy
- `aggregation`: doc-avg, field-avg, micro-avg
- `value`
- `n_valid_comparisons` (number of (records,fields) with non-empty entries)
- `doc_strata` when relevant

Example:

```json
{
  "metric": "precision",
  "aggregation": "micro-avg",
  "value": 0.82,
  "n_valid_comparisons": 1247
}
```

This contract defines the operational invariants for the package: valid data,
explicit missingness rules, explicit field agreement semantics, canonical
comparison rows, and deterministic aggregation. These guarantees are required to
ensure consistent and interpretable evaluation results across ingestion,
comparison, and metric aggregation.

### Data ingestion

BIBRA-Eval needs data ingestion methods, that check if the provided json-records
are syntactically correct. Also it needs to verify that doc_id's match for
gold-standard records and predictions.

The bibra data-schema defined needs to be checked by data ingestion methods.

## Metrics

### Field level comparison

A module `comparator` provides methods for realising field level 
comparison. `fa` measures the **field agreement**: what is the agreement between
two fields, conditioned on their mutual existence. `fa` is either measured
`binary`-score, `levenshtein`-distance or an `llm-as-a-judge`-score.
`fa` should always be between zero and one. `levenshtein`-distance is
scaled accordingly. 

Fields can contain lists and their comparison must first match the list entries,
then compute the `fa` of matching list entry, which is then
averaged over the number of list entries.

### Elementary Metrics

**Precision**: we don't count missing values if there was no prediction for
the field

|        | pred_y   | pred_n |
|--------|----------|--------|
| gold_y |  fa      | NA     |
| gold_n |  0       | NA     |

Precision:
```python
for f in fields:
    if pred_data.f:
        score[f] = metric[f](pred_data[f], gold_data[f])
```

Here metric[f] provides the appropriate field agreement score defined for
field `f` in the evaluation schema

Interpretation: high scores mean that the fields extracted by the system are
accurate.

**Recall-like**: we don't count missing values if there was no gold-standard
for the field

|        | pred_y   | pred_n |
|--------|----------|--------|
| gold_y |  fa      | 0      |
| gold_n |  NA      | NA     |

Recall:
```python
for f in fields:
    if gold_data.f:
        score[f] = metric[f](gold_data[f], pred_data[f])
```

**Accuracy**: every inconsistency is scored as 0

|        | pred_y   | pred_n |
|--------|----------|--------|
| gold_y |  fa      | 0      |
| gold_n |  0       | NA     |

```python
for f in fields:
    score[f] = metric[f](gold_data[f], pred_data[f])
```

**Common field agreement**: only compare entries that exist in both records

|        | pred_y   | pred_n |
|--------|----------|--------|
| gold_y |  fa      | NA     |
| gold_n |  NA      | NA     |

```python
for f in fields:
    if gold_data.f and pred_data.f:
        score[f] = metric[f](gold_data[f], pred_data[f])
```

### Metric aggregation

Metric aggregation is structured in modular three-step approach:

* **record-by-record-comparison** leading to a `comparison_matrix`. Primary
  identifiers for each observation of the comparison matrix are `doc_id`
  and `fieldname`. A desired intermediate output is a table like this

| doc_id | fieldname | pred y/n | gold y/n   | fa  |
| ...    | ...       | ...      | ...        | ... |

* **compute intermediate results**: first layer of aggregation (either across
    fields or across records) computes (weighted) averages over one axis
    (`fields` or `documents`) of the comparison matrix
* aggregate: computes (weighted) averages over the second axis of the comparison
  matrix leading to `final_results`

`comparison_matrix`, `intermediate_results` and `aggregate_results` are classes
designed to interoperate with one-another. Each should have their own `compute`
method.

In determining results, there are different paths or modes for aggregating
results:

* document macro-average: compute average result per doc first (along all
    fields), then compute average across documents
* field macro-average: compute average results per field (along all documents),
   then compute average across all fields
* micro-average: no intermediate aggregation, average all field-to-field results
   in one  

Each computation step should allow to handle additional `doc_strata` fields,
metadata fields that define subgroups of records, that should be preserved in
the computation steps, to allow a stratified analysis of results.
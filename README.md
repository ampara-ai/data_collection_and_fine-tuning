# Ampara Legal RAG

This repository contains the data pipelines used to build a contrastive-learning
dataset for legal embedding models in the Peruvian domain of violence against
women and family members.

It covers the complete workflow: collecting legal and case-law sources,
normalizing documents, producing structured case summaries, generating
colloquial questions, selecting positive documents, mining hard negatives, and
creating train/test files grouped by court decision.

## Repository structure

```text
.
├── recoleccion/            # Source collection, parsing, normalization, and chunks
│   ├── data_types/         # Five document families
│   └── data/processed/     # Consolidated document corpus
├── generacion_dataset/     # Case selection and synthetic question generation
│   ├── data/input/         # Inputs copied from recoleccion
│   ├── data/intermediate/  # PDFs, summaries, and candidate data
│   └── data/output/        # Questions and training triples
├── entrenamiento/          # Train/test preparation and experiment notebooks
├── pyproject.toml          # Python project and dependencies
└── uv.lock                 # Locked dependency versions
```

The repository is divided into three stages:

| Stage | Purpose |
|---|---|
| [`recoleccion/`](recoleccion/README.md) | Collect and normalize legal sources, case law, and institutional documents |
| [`generacion_dataset/`](generacion_dataset/README.md) | Build candidate sets and generate colloquial legal questions |
| [`entrenamiento/`](entrenamiento/README.md) | Create the sentence-level train/test split and model-ready files |

## Data sources

| Type | Content | Role |
|---:|---|---|
| 01 | Law No. 30364 | Main legislation on violence against women and family members |
| 02 | Peruvian Criminal Code | Substantive criminal law |
| 03 | Peruvian Criminal Procedure Code | Procedure, evidence, and victim participation |
| 04 | Case law | Anonymized historical facts and legal reasoning |
| 05 | Institutional documents | Guidance and public-service procedures |

LP Derecho is used as an operational source for structuring the Criminal Code,
the Criminal Procedure Code, and their case-law links. Law No. 30364 also uses
material from SPIJ and El Peruano. Source URLs are retained in document metadata.

The Criminal Procedure Code is collected from both LP Derecho pages and covers
numeric articles 1 through 566, including the preliminary title and inserted
articles.

## Requirements

- Python 3.12 or newer
- [`uv`](https://docs.astral.sh/uv/)

Install the locked environment from the repository root:

```bash
uv sync --frozen
```

Scripts that call OpenRouter or ResumeAI also require the corresponding values
from [`.env.example`](.env.example). Do not commit `.env` or API keys.

## Local checks

The following commands do not download data or call an LLM:

```bash
uv run --frozen python -m unittest discover -s generacion_dataset/tests -v

PYTHONPATH=recoleccion/data_types/tipo_03_codigo_procesal_penal/src \
  uv run --frozen python -m unittest discover \
  -s recoleccion/data_types/tipo_03_codigo_procesal_penal/tests -v

uv run --frozen python generacion_dataset/scripts/audit_candidate_resolution.py
uv run --frozen python entrenamiento/scripts/audit_training_split.py
uv run --frozen python scripts/audit_markdown_links.py
```

To inspect all resolved candidates for one case:

```bash
uv run --frozen python \
  generacion_dataset/scripts/audit_candidate_resolution.py \
  --case-id jp_00008_e0002
```

## Build the document corpus

The normalization commands use the source files already present under each
`recoleccion/data_types/` directory.

```bash
uv run --frozen python recoleccion/run_base_documental.py plan

uv run --frozen python recoleccion/run_base_documental.py tipo01-normalize
uv run --frozen python recoleccion/run_base_documental.py tipo01-chunk

uv run --frozen python recoleccion/run_base_documental.py tipo02-normalize
uv run --frozen python recoleccion/run_base_documental.py tipo02-chunk

uv run --frozen python recoleccion/run_base_documental.py tipo03-normalize
uv run --frozen python recoleccion/run_base_documental.py tipo03-chunk

uv run --frozen python recoleccion/run_base_documental.py tipo04-normalize
uv run --frozen python recoleccion/run_base_documental.py tipo04-chunk

uv run --frozen python recoleccion/run_base_documental.py tipo05-normalize
uv run --frozen python recoleccion/run_base_documental.py tipo05-chunk

uv run --frozen python recoleccion/run_base_documental.py consolidate-chunks
uv run --frozen python generacion_dataset/scripts/prepare_base_inputs.py
```

The consolidated corpus is written to:

```text
recoleccion/data/processed/document_chunks_all.jsonl
```

## Update the Criminal Procedure Code

This step downloads and merges the two LP Derecho pages. It does not search for
case law and does not call an LLM.

```bash
PYTHONPATH=recoleccion/data_types/tipo_03_codigo_procesal_penal/src \
  uv run --frozen python \
  recoleccion/data_types/tipo_03_codigo_procesal_penal/scripts/fetch_and_filter_cpp.py

uv run --frozen python recoleccion/run_base_documental.py tipo03-normalize
uv run --frozen python recoleccion/run_base_documental.py tipo03-chunk
uv run --frozen python recoleccion/run_base_documental.py consolidate-chunks
uv run --frozen python generacion_dataset/scripts/prepare_base_inputs.py
```

## Case-law pipeline

The case-law stage can be run from the repository root in this order:

```bash
uv run --frozen python recoleccion/run_base_documental.py tipo04-build-seeds
uv run --frozen python recoleccion/run_base_documental.py tipo04-fetch-indexes
uv run --frozen python recoleccion/run_base_documental.py tipo04-parse-entries
uv run --frozen python recoleccion/run_base_documental.py tipo04-resolve-content
uv run --frozen python recoleccion/run_base_documental.py tipo04-summarize
uv run --frozen python recoleccion/run_base_documental.py tipo04-build-contextual-chunks
uv run --frozen python recoleccion/run_base_documental.py tipo04-normalize
uv run --frozen python recoleccion/run_base_documental.py tipo04-chunk
```

`tipo04-fetch-indexes` and `tipo04-resolve-content` access external websites.
`tipo04-parse-entries` and `tipo04-summarize` call external language-model
services. Existing processed case-law files can be reused when this stage does
not need to be repeated.

## Generate the contrastive-learning dataset

First copy the consolidated inputs:

```bash
uv run --frozen python generacion_dataset/scripts/prepare_base_inputs.py
```

For each case, the candidate set contains:

1. the case-law document;
2. the Criminal Code or Criminal Procedure Code article that linked to it;
3. legal provisions cited in the structured case summary;
4. concordances associated with the source article.

The LLM receives the literal text of every candidate and selects one or more
candidate IDs as positives. Case law and concordances are candidates, not
automatic positives. A separate pool of 20 BM25 distractors is also shown to
the LLM, which selects only documents that are topically close but do not help
answer each question. Generated triples reject positive/negative collisions by
ID, document, normalized text, and court-decision reference.

The generator retries a case up to three times when the model returns invalid
IDs or an output that fails validation. When a historical decision is paired
with a legal article from the current repository snapshot, the record is marked
`requires_historical_version_review` and the prompt avoids presenting old
penalties or wording as current law.

Run the generator with `OPENROUTER_API_KEY` configured:

```bash
uv run --frozen python \
  generacion_dataset/scripts/generate_colloquial_legal_questions.py
```

The default is a maximum of five questions per eligible case. With the current
178 eligible cases, a successful run produces between 712 and 890 questions.

Validate the generated positives, negatives, IDs, and temporal labels before
building the train/test files:

```bash
uv run --frozen python \
  generacion_dataset/scripts/audit_generated_dataset.py
```

Main outputs:

```text
generacion_dataset/data/output/legal_questions_dataset/
├── candidate_sets.jsonl
├── questions_with_positive_context.jsonl
├── generation_errors.jsonl
├── run_manifest.json
└── training_triples.jsonl
```

## Prepare training and evaluation files

The split is performed by `case_id`, so every question derived from the same
court decision remains entirely in either train or test.

```bash
uv run --frozen python entrenamiento/scripts/preprocesing_dataset.py \
  --input generacion_dataset/data/output/legal_questions_dataset/training_triples.jsonl \
  --output entrenamiento/data \
  --test_size 0.1 \
  --seed 520
```

Outputs:

```text
entrenamiento/data/
├── training.json
├── corpus.jsonl
├── test_queries.jsonl
├── test_qrels.jsonl
└── split_manifest.json
```

The resulting `train_cases` and `test_cases` sets must not overlap.

## External operations

These commands access external services or replace generated files:

| Command or script | Effect |
|---|---|
| `run_recoleccion.py` | Downloads or updates source material |
| `download_pdf_candidates.py` | Downloads candidate court-decision PDFs |
| `run_resumeai_batch.py` | Sends PDFs to ResumeAI-Legal |
| `generate_colloquial_legal_questions.py` | Calls OpenRouter and rewrites dataset outputs |
| `preprocesing_dataset.py` | Rewrites files under `entrenamiento/data/` |

LP Derecho is an operational source. When an authoritative current legal text
is required, compare it against the corresponding official publication.

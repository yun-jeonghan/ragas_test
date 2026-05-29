# Architecture

This project is a benchmark and evaluation harness, not a user facing chatbot.

## Top level layout

- pyproject.toml - package metadata, dependencies, scripts, formatting, test config.
- README.md - short project overview.
- src/graphrag_ragas_eval/ - application code.
- tests/ - unit tests for loaders, schemas, and metric wiring.
- data/
  - raw/graphrag/ - GraphRAG parquet exports copied or mounted from the indexer output.
  - benchmarks/ - question sets and reference labels.
  - results/ - evaluation outputs and score tables.
- reports/ - human readable summaries and charts.
- workspaces/graphrag/ - document staging and GraphRAG index workspace.
- scripts/ - one off utilities and batch jobs.

## Modules

### src/graphrag_ragas_eval/config.py

Central configuration models and environment handling.

Responsibilities:

- Resolve input and output paths.
- Store LLM provider settings.
- Store GraphRAG search defaults.
- Store evaluation toggles and metric selection.

### src/graphrag_ragas_eval/schemas.py

Typed data models for the benchmark.

Responsibilities:

- Represent GraphRAG row records after loading parquet files.
- Represent benchmark questions and labeled examples.
- Represent GraphRAG search runs and evaluation outputs.

### src/graphrag_ragas_eval/graphrag/loaders.py

Parquet readers and adapters for GraphRAG output tables.

Responsibilities:

- Read entities.parquet, relationships.parquet, communities.parquet, community_reports.parquet, text_units.parquet, and optional covariates.parquet.
- Normalize column names into stable internal models.
- Provide validation and fail fast errors when required files are missing.

### src/graphrag_ragas_eval/graphrag/search.py

GraphRAG query wrappers.

Responsibilities:

- Define a common GraphRAGSearcher interface.
- Provide local and global search adapters.
- Return both answer text and retrieved contexts in a Ragas friendly shape.

### src/graphrag_ragas_eval/graphrag/workspace.py

GraphRAG workspace management and CLI bridge.

Responsibilities:

- Stage input documents into a GraphRAG compatible workspace.
- Initialize the workspace through the GraphRAG CLI.
- Run GraphRAG indexing from the staged documents.

### src/graphrag_ragas_eval/graphrag_runner.py

Higher level orchestration for document ingestion and indexing.

Responsibilities:

- Combine stage, init, and index into one repeatable flow.
- Return the workspace path and staged file list for downstream steps.

### src/graphrag_ragas_eval/eval/dataset.py

Benchmark dataset loading and conversion.

Responsibilities:

- Load JSONL or JSON benchmark examples.
- Convert examples into Ragas samples.
- Keep reference answer and reference context alignment explicit.

### src/graphrag_ragas_eval/eval/ragas_runner.py

Ragas evaluation orchestration.

Responsibilities:

- Build the dataset.
- Select and run metrics.
- Persist raw scores and aggregates.

### src/graphrag_ragas_eval/eval/replay.py

Helpers for loading saved GraphRAG search results.

Responsibilities:

- Load replayable search result JSON.
- Convert saved results into GraphRAGSearchResult objects.

### src/graphrag_ragas_eval/llm.py

LLM provider selection and Ragas client construction.

Responsibilities:

- Read OpenAI or vLLM settings from environment variables.
- Build an OpenAI-compatible client for Ragas.
- Keep the provider swap isolated to one file.

### src/graphrag_ragas_eval/cli.py

Command line entry points.

Responsibilities:

- inspect - check input tables and benchmark files.
- graphrag stage - copy source documents into the workspace.
- graphrag init - initialize a GraphRAG workspace after staging documents.
- graphrag index - run GraphRAG indexing end to end.
- evaluate - score saved search results with Ragas.

## Data flow

1. Load GraphRAG parquet outputs.
2. Load benchmark samples.
3. Choose search mode per sample.
4. Run GraphRAG retrieval and generation.
5. Collect contexts, answer, metadata, and citations.
6. Score with Ragas.
7. Add graph aware post metrics.
8. Save results and aggregates.

## Design rules

- Keep parquet as the canonical source for GraphRAG output.
- Keep benchmark samples immutable once published.
- Store raw outputs and derived metrics separately.
- Make local and global search interchangeable behind one interface.

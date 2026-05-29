# GraphRAG Ragas Eval

Evaluation harness for measuring GraphRAG retrieval and generation quality with Ragas, plus graph aware metrics.

## Goals

- Load GraphRAG parquet outputs as the source of truth.
- Run local and global GraphRAG search against a benchmark question set.
- Score retrieval and answer quality with Ragas.
- Add graph specific metrics that Ragas does not cover directly.

## Layout

See docs/architecture.md for the file by file design.


# Search wrapper design

The search layer hides GraphRAG implementation details behind a stable contract.

## Contract

Input:

- question
- sample_id
- search mode
- optional runtime knobs

Output:

- answer text
- ordered retrieved contexts
- citations
- metadata

## Wrapper rules

- Local search is used for entity centric or single document questions.
- Global search is used for cross community or synthesis questions.
- Both wrappers must return the same result shape so the evaluator does not care which backend was used.
- The backend can be GraphRAG native, a cached replay backend, or an in memory fixture backend for tests.

## Recommended backend interface

- search(question, mode, sample_id, ...)
- returns a GraphRAGSearchResult

## Why this shape

This makes it easy to:

- score local and global search separately,
- plug in GraphRAG native APIs later,
- replay old runs for regression testing,
- compare search strategies under the same benchmark set.


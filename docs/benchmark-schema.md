# Benchmark schema

The benchmark is stored as JSON or JSONL. Each row represents one question and one expected answer set.

## Required fields

- sample_id: stable unique identifier.
- question: the user question.
- query_type: local, global, multi hop, comparison, or unanswerable.
- search_mode: local or global.
- reference_answer: canonical answer used for faithfulness and answer relevancy evaluation.

## Optional fields

- reference_contexts: supporting passages used for context precision and context recall.
- expected_entities: entities that should appear in the retrieved evidence.
- expected_relationships: relationships that should be covered by the retrieved evidence.
- expected_community_ids: GraphRAG community identifiers that should be involved.
- source_doc_ids: source document identifiers for traceability.
- difficulty: easy, medium, hard.
- metadata: free form extra fields.

## Example row

{
  "sample_id": "q1",
  "question": "Who is Scrooge?",
  "query_type": "local",
  "search_mode": "local",
  "reference_answer": "Scrooge is a miser.",
  "reference_contexts": ["Scrooge is a miser."],
  "expected_entities": ["Scrooge"],
  "difficulty": "easy"
}


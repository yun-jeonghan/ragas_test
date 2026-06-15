# Test Progress

This file tracks the latest verified status of the main `grev` flows.
Run `scripts/test_grev_progress.sh` to refresh it from the latest matrix output.

## Snapshot

- Last verified: 2026-06-14 06:16:08 UTC
- Test root: `data/test_20260614_061231`
- Summary file: `/home/openclaw/projects/graphrag-eval/data/test_20260614_061231/output/summary.jsonl`

## Core GraphRAG Flow

- [x] `grev init` - exit 0
- [x] `graphrag normalize` - exit 0
- [x] `graphrag stage` - exit 0
- [x] `graphrag init` - exit 0
- [x] `graphrag index standard` - exit 0
- [x] `graphrag index ontology+postprocess` - exit 0
- [x] `graphrag postprocess` - exit 0
- [x] `inspect` - exit 0

## Question Generation

- [x] `benchmark generate-questions` - exit 0
- [ ] `ragas generate-questions` - exit 1, log `/home/openclaw/projects/graphrag-eval/data/test_20260614_061231/output/logs/08b-ragas-generate-questions.log`

## BenchmarkQED

- [x] `benchmark-qed autod` - exit 0
- [x] `benchmark-qed autoq` - exit 0
- [ ] `benchmark-qed autoe` - exit 1, log `/home/openclaw/projects/graphrag-eval/data/test_20260614_061231/output/logs/11-benchmark-qed-autoe.log`
- [ ] `benchmark-qed smoke` - exit 1, log `/home/openclaw/projects/graphrag-eval/data/test_20260614_061231/output/logs/12-benchmark-qed-smoke.log`
- [x] `benchmark-qed retrieval-smoke` - exit 0
- [x] `benchmark-qed retrieval-reference` - exit 0
- [x] `benchmark-qed retrieval-score` - exit 0
- [ ] `benchmark-qed assertion-score` - exit 1, log `/home/openclaw/projects/graphrag-eval/data/test_20260614_061231/output/logs/16-benchmark-qed-assertion-score.log`
- [ ] `benchmark-qed assertion-report` - exit 1, log `/home/openclaw/projects/graphrag-eval/data/test_20260614_061231/output/logs/17-benchmark-qed-assertion-report.log`

## Evaluation Wrappers

- [ ] `evaluate` - exit 1, log `/home/openclaw/projects/graphrag-eval/data/test_20260614_061231/output/logs/18-evaluate.log`
- [ ] `ragas evaluate` - exit 1, log `/home/openclaw/projects/graphrag-eval/data/test_20260614_061231/output/logs/19-ragas-evaluate.log`
- [x] `kg-gen mine evaluate` - exit 0
- [x] `kg-correctness evaluate` - exit 0
- [ ] `ograg2 evaluate` - exit 1, log `/home/openclaw/projects/graphrag-eval/data/test_20260614_061231/output/logs/23-ograg2-evaluate.log`
- [ ] `pipeline report` - not run

## Result Summary

- Passed: 16
- Failed: 8

## Notes

- A checked item means the latest matrix run exited with code `0`.
- Failed steps stay listed here so it is obvious what needs attention next.

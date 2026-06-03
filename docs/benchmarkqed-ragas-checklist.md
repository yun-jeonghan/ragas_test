# BenchmarkQED / Ragas Checklist

이 문서는 `BenchmarkQED`와 `Ragas`를 같은 평가 스택의 두 구현체로 보고, 공식 문서를 기준으로 기능을 체크리스트 형태로 정리한 것이다.

체크 표시는 이 저장소의 현재 smoke 테스트에서 실제로 확인된 항목이다.

## Overview

- 이 저장소는 `BenchmarkQED`와 `Ragas`를 공통 벤치마킹 스택으로 다룬다.
- `BenchmarkQED`는 벤치마크 생성과 특수 평가 모드가 강한 쪽이다.
- `Ragas`는 metric 기반 RAG 평가와 testset generation이 강한 쪽이다.
- 이 저장소는 두 라이브러리를 연결하는 어댑터와 래퍼를 둔다.

## BenchmarkQED

### AutoD

- [x] 문서 코퍼스를 샘플링하고 요약한다.
- [x] smoke에서 AutoD summary JSON이 생성된다.

### AutoQ

- [x] local 질문 생성이 동작한다.
- [x] smoke에서 질문 JSON이 생성된다.
- [ ] global 질문 생성은 smoke에서 아직 검증하지 않았다.
- [ ] multi-hop 질문 생성은 smoke에서 아직 검증하지 않았다.
- [ ] unanswerable 질문 생성은 smoke에서 아직 검증하지 않았다.

### Assertions

- [x] assertion 생성 파이프라인이 동작한다.
- [x] assertion score 정규화 문제가 패치되어 smoke에서 assertion이 생성된다.
- [x] smoke에서 assertion-prep JSON이 생성된다.
- [ ] hierarchical assertion 생성은 smoke에서 아직 검증하지 않았다.

### AutoE

- [x] saved answer 평가 경로가 동작한다.
- [x] smoke에서 AutoE evaluation JSON이 생성된다.
- [ ] pairwise-scores 모드는 smoke에서 아직 검증하지 않았다.
- [ ] reference-scores 모드는 smoke에서 아직 검증하지 않았다.
- [ ] assertion-scores 모드는 smoke에서 아직 검증하지 않았다.
- [ ] hierarchical-assertion-scores 모드는 smoke에서 아직 검증하지 않았다.

### Retrieval

- [x] retrieval prep가 동작한다.
- [x] smoke에서 retrieval-results JSON이 생성된다.
- [ ] generate-retrieval-reference 모드는 smoke에서 아직 검증하지 않았다.
- [ ] retrieval-scores 모드는 smoke에서 아직 검증하지 않았다.

## Ragas

### Metrics used in this repo

- [x] `faithfulness`를 smoke evaluation에서 사용한다.
- [x] `context_precision`을 smoke evaluation에서 사용한다.
- [x] `context_recall`을 smoke evaluation에서 사용한다.
- [x] `answer_relevancy`를 smoke evaluation에서 사용한다.

### Other official metrics

- [ ] `answer_correctness`는 smoke에서 아직 검증하지 않았다.
- [ ] `context_entities_recall`은 smoke에서 아직 검증하지 않았다.
- [ ] `semantic_similarity`는 smoke에서 아직 검증하지 않았다.
- [ ] multi-turn / agent 계열 metric은 smoke에서 아직 검증하지 않았다.

### Dataset generation

- [ ] Ragas는 testset generation 기능을 가진다.
- [ ] 이 저장소의 current smoke는 Ragas testset generation을 직접 실행하지는 않는다.

## Interpretation

- 둘은 같은 평가 스택의 두 구현체로 볼 수 있다.
- 차이는 평가 디테일과 지원하는 모드/metric의 폭이다.
- 이 저장소의 smoke는 BenchmarkQED 생성 흐름과 Ragas metric 평가 흐름을 함께 검증한다.

## Sources

- BenchmarkQED AutoQ: <https://microsoft.github.io/benchmark-qed/notebooks/autoq/>
- BenchmarkQED AutoE: <https://microsoft.github.io/benchmark-qed/notebooks/autoe/>
- BenchmarkQED Assertions: <https://microsoft.github.io/benchmark-qed/notebooks/assertion_gen/>
- BenchmarkQED Retrieval Metrics: <https://microsoft.github.io/benchmark-qed/notebooks/retrieval_metrics/>
- Ragas testset generation: <https://docs.ragas.io/en/stable/getstarted/rag_testset_generation/>
- Ragas metric index: <https://docs.ragas.io/en/stable/concepts/metrics/available_metrics/index.html>
- Ragas faithfulness: <https://docs.ragas.io/en/stable/concepts/metrics/available_metrics/faithfulness/>
- Ragas context precision: <https://docs.ragas.io/en/stable/concepts/metrics/available_metrics/context_precision/>
- Ragas context recall: <https://docs.ragas.io/en/stable/concepts/metrics/available_metrics/context_recall/>
- Ragas answer relevancy: <https://docs.ragas.io/en/stable/concepts/metrics/available_metrics/answer_relevance/>

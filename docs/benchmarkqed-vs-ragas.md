# Benchmarking Stack: BenchmarkQED and Ragas

이 문서는 `benchmarkqed`와 `ragas`를 같은 계열의 평가/생성 라이브러리로 보고, 이 저장소에서 어떻게 공통 스택으로 다루는지 공식 문서 기준으로 정리한 메모다.

좀 더 실무적인 체크리스트는 [`docs/benchmarkqed-ragas-checklist.md`](./benchmarkqed-ragas-checklist.md)를 보면 된다.

## 한 줄 요약

- `BenchmarkQED`와 `Ragas`는 둘 다 RAG 벤치마크를 만들고 평가하는 역할을 하는 라이브러리다.
- `BenchmarkQED`는 벤치마크 생성과 AutoE 계열의 특수 평가 모드가 강하고, `Ragas`는 일반 RAG metric 평가와 testset generation이 강하다.
- 이 저장소는 둘을 서로 다른 “업무”가 아니라, 같은 평가 스택의 두 구현체로 다룬다.

## 공통 역할

두 라이브러리 모두 다음 역할을 수행한다.

- 평가용 질문/테스트셋 생성
- 검색 결과와 답변의 품질 평가
- retrieval 관련 reference 또는 ground truth 비슷한 평가 기준 구성

## BenchmarkQED가 더 강한 영역

공식 문서 기준으로 BenchmarkQED는 AutoD, AutoQ, AutoE, retrieval metrics notebook을 통해 벤치마크 데이터 생성과 평가를 자동화한다.

- AutoD: 문서 코퍼스를 샘플링/요약한다.
- AutoQ: 질문을 생성한다.
- AutoE: RAG method 간 점수를 계산한다.

AutoE에는 다음과 같은 모드가 있다.

- `pairwise-scores`
  - 두 RAG 답변을 LLM-as-a-judge 방식으로 비교한다.
  - 목적은 상대 비교와 win rate 집계다.
- `reference-scores`
  - 생성된 답변을 기준 답안(reference)과 비교해 점수화한다.
- `assertion-scores`
  - 질문에 달린 assertions를 점수화한다.
- `hierarchical-assertion-scores`
  - supporting assertions가 있는 계층형 assertions를 점수화한다.
- `generate-retrieval-reference`
  - retrieval 평가용 reference clusters를 생성한다.
- `retrieval-scores`
  - retrieval 품질을 precision, recall, fidelity로 평가한다.

BenchmarkQED retrieval notebook은 Part 1에서 query별 cluster references를 만들고, Part 2에서 그 pre-generated reference clusters를 사용해 retrieval scoring을 수행한다. Part 2는 Part 1과 독립적으로 실행할 수 있지만, reference 파일은 필요하다.

## Ragas가 더 강한 영역

Ragas는 RAG 품질을 여러 metric으로 평가하는 라이브러리다. 여기서 중요한 점은, BenchmarkQED의 AutoE와는 별개의 도구라는 것이다.

이 저장소에서 주로 쓰는 Ragas metric은 아래다.

- `faithfulness`
  - `response`가 `retrieved context`와 사실적으로 일치하는지 본다.
  - 답변의 claim들이 검색된 컨텍스트로 뒷받침되는지 평가한다.
- `context_precision`
  - 검색된 컨텍스트가 질문/답변에 얼마나 유용했는지 본다.
  - 공식 문서에서는 reference answer를 기준으로 각 context를 비교하는 설명을 제공한다.
- `context_recall`
  - reference contexts 중에서 얼마나 잘 찾아왔는지 본다.
- `answer_relevancy`
  - 답변이 user input에 얼마나 직접적으로 맞는지 본다.
  - 사실성 자체보다 질문 적합성에 더 초점을 둔다.

## 가장 중요한 구분

### 1) 둘은 같은 역할의 라이브러리다

- 둘 다 질문 생성과 평가를 다루는 라이브러리다.
- 둘 다 retrieval 관련 평가를 다룰 수 있다.
- 둘 다 synthetic testset 또는 benchmark artifact를 만들어낼 수 있다.

### 2) 차이는 평가 디테일과 초점이다

- `BenchmarkQED`는 pairwise, reference, assertion, hierarchical assertion, retrieval reference 같은 모드가 강하다.
- `Ragas`는 faithfulness, context precision, context recall, answer relevancy 같은 metric 체계가 강하다.
- 그래서 운영상으로는 같은 “평가 스택”이지만, 구현 상세는 서로 다르다.

### 3) retrieval 평가를 말할 때도 기준이 다르다

- BenchmarkQED retrieval:
  - reference clusters와 query relevance 결과를 사용한다.
  - `generate-retrieval-reference`와 `retrieval-scores`가 분리되어 있다.
- Ragas retrieval-like metrics:
  - `retrieved_contexts`와 `reference_answer` 또는 `reference_contexts`를 사용한다.

즉, “retrieval을 평가한다”는 말만 보면 비슷해 보여도, BenchmarkQED와 Ragas는 기준 데이터와 계산 방식이 다르다.

## 이 저장소에서의 역할 분담

- `benchmark_qed/`
  - BenchmarkQED 워크플로우 래퍼
  - AutoD / AutoQ / Assertion / Retrieval reference / Retrieval score
- `ragas/`
  - Ragas metric 평가
- `adapters/`
  - BenchmarkQED와 Ragas 사이의 데이터 형태 변환

## 실무적 해석

- 먼저 “같은 역할의 두 라이브러리”라고 생각하고 구현한다.
- 그 다음에 각 라이브러리의 고유한 평가 디테일만 분리해서 다룬다.
- 이 저장소는 그 차이를 코드 레벨에서 흡수하는 어댑터 레이어를 가진다.

## 공식 문서

- BenchmarkQED AutoE CLI: <https://microsoft.github.io/benchmark-qed/cli/autoe/>
- BenchmarkQED Retrieval Metrics: <https://microsoft.github.io/benchmark-qed/notebooks/retrieval_metrics/>
- BenchmarkQED Assertion Generation: <https://microsoft.github.io/benchmark-qed/notebooks/assertion_gen/>
- Ragas Faithfulness: <https://docs.ragas.io/en/stable/concepts/metrics/available_metrics/faithfulness/>
- Ragas Context Precision: <https://docs.ragas.io/en/stable/concepts/metrics/available_metrics/context_precision/>
- Ragas Context Recall: <https://docs.ragas.io/en/stable/concepts/metrics/available_metrics/context_recall/>
- Ragas Answer Relevancy: <https://docs.ragas.io/en/stable/concepts/metrics/available_metrics/answer_relevance/>

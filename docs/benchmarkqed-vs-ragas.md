# BenchmarkQED vs Ragas

이 문서는 `benchmarkqed`와 `ragas`를 헷갈리지 않도록, 각 프로젝트의 역할과 이 저장소에서의 쓰임을 공식 문서 기준으로 정리한 메모다.

## 한 줄 요약

- `BenchmarkQED`는 RAG 벤치마크를 자동 생성하고, AutoE로 다양한 비교/평가 모드를 제공하는 도구 묶음이다.
- `Ragas`는 `retrieved_contexts`, `reference_answer`, `reference_contexts`, `response` 등을 사용해 RAG 품질을 점수화하는 평가 라이브러리다.

## BenchmarkQED가 하는 일

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

## Ragas가 하는 일

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

### 1) BenchmarkQED는 “벤치마크 생성/수집/특수 평가” 쪽

- AutoD/AutoQ/AutoE 흐름을 가진다.
- assertions를 만들고 점수화할 수 있다.
- retrieval reference clusters를 만들고 retrieval scoring을 할 수 있다.

### 2) Ragas는 “RAG 출력 품질을 metric으로 측정”하는 쪽

- generated answer와 retrieved contexts를 metric 단위로 평가한다.
- `faithfulness`, `context_precision`, `context_recall`, `answer_relevancy` 같은 metric이 핵심이다.

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
- `eval/`
  - Ragas metric 평가
- `adapters/`
  - BenchmarkQED와 Ragas 사이의 데이터 형태 변환

## 공식 문서

- BenchmarkQED AutoE CLI: <https://microsoft.github.io/benchmark-qed/cli/autoe/>
- BenchmarkQED Retrieval Metrics: <https://microsoft.github.io/benchmark-qed/notebooks/retrieval_metrics/>
- BenchmarkQED Assertion Generation: <https://microsoft.github.io/benchmark-qed/notebooks/assertion_gen/>
- Ragas Faithfulness: <https://docs.ragas.io/en/stable/concepts/metrics/available_metrics/faithfulness/>
- Ragas Context Precision: <https://docs.ragas.io/en/stable/concepts/metrics/available_metrics/context_precision/>
- Ragas Context Recall: <https://docs.ragas.io/en/stable/concepts/metrics/available_metrics/context_recall/>
- Ragas Answer Relevancy: <https://docs.ragas.io/en/stable/concepts/metrics/available_metrics/answer_relevance/>


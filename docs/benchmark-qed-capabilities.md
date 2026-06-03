# BenchmarkQED 기능 정리

이 문서는 `vendor/benchmark-qed` 기준으로, CLI와 notebook이 각각 어떤 일을 하는지 빠르게 찾을 수 있게 정리한 메모다.

공식 문서 주소:

- <https://microsoft.github.io/benchmark-qed/>

## 한눈에 보기

BenchmarkQED는 크게 3축으로 나뉜다.

- `AutoD`: 데이터 샘플링, 구조화, 요약
- `AutoQ`: 질문 생성
- `AutoE`: 답변 평가와 통계 검정

여기에 더해,

- `config`: 설정 파일 템플릿 생성
- `data`: 공개 데이터셋 다운로드

가 붙는다.

## CLI 기능

### `benchmark-qed config`

설정 파일 템플릿을 만든다.

- `config init autoq`
- `config init autoe_pairwise`
- `config init autoe_reference`
- `config init autoe_assertion`

용도:

- AutoQ / AutoE / retrieval 평가용 YAML 스켈레톤 생성
- Azure Blob Storage 연동 설정 포함 가능

참고:

- 공식 `config init` 문서상 생성 타입은 `autoq`, `autoe_pairwise`, `autoe_reference`, `autoe_assertion`까지만 나온다.
- `generate-retrieval-reference`와 `retrieval-scores`는 `autoe` 쪽 실행 명령이지, `config init` 타입으로 문서화되어 있지 않다.

### `benchmark-qed data`

데이터셋을 내려받는 유틸리티다.

- 공개 benchmark 데이터셋 다운로드
- 로컬 실험용 raw data 준비

### `benchmark-qed autoq`

질문 생성 CLI다.

실행 가능한 흐름:

- `data_local`
  - 문서 단위 로컬 질문 생성
  - 비교적 작은 텍스트 조각에서 바로 답할 수 있는 질문 생성
- `data_global`
  - 여러 local question을 기반으로 global question 생성
  - 넓은 범위를 요하는 질문 생성
- `data_linked`
  - entity를 공유하는 local question들을 묶어 multi-hop 질문 생성
- `activity_local`
  - activity/persona 기반 로컬 질문 생성
- `activity_global`
  - activity/persona 기반 글로벌 질문 생성
- `generate-assertions`
  - 기존 질문에 대한 assertion 생성
  - local / global / linked assertion 흐름을 지원
- `assertion-stats`
  - 생성된 assertion 통계 확인

실무적으로는 다음 순서로 많이 쓴다.

1. `data_local`
2. `data_global` 또는 `data_linked`
3. `generate-assertions`
4. `assertion-stats`

### `benchmark-qed autoe`

RAG 답변 평가 CLI다.

지원하는 주요 기능:

- `pairwise-scores`
  - 두 RAG 시스템을 LLM judge로 상대 비교
- `reference-scores`
  - reference answer와 비교하는 평가
- `assertion-scores`
  - assertion 기반 평가
- `hierarchical-assertion-scores`
  - hierarchical assertion 기반 평가
- `assertion-significance`
  - assertion score에 대한 유의성 검정
- `hierarchical-assertion-significance`
  - hierarchical assertion score에 대한 유의성 검정
- `generate-retrieval-reference`
  - retrieval relevance ground truth 생성
- `retrieval-scores`
  - retrieval precision / recall / fidelity 평가

이 CLI는 사실상 BenchmarkQED의 평가 엔진이다.

## Notebook 기능

notebook은 CLI를 이해하기 위한 데모/레퍼런스 역할이 강하다.

### `autod.ipynb`

AutoD 전체 흐름을 보여준다.

- Configs
- Load documents
- Create text units
- Sample text units using a Kmeans-based sampler
- Summarize sampled text units using map-reduce

### `autoq.ipynb`

AutoQ 질문 생성 흐름을 보여준다.

- Configs
- Data Sampling
- Data-Local Questions
- Data Global Questions
- Data-Linked Questions
- Activity Questions
- Generate Activity Context
- Generate Activity Local Questions
- Generate Activity Global Questions

### `autoe.ipynb`

AutoE 평가 흐름을 보여준다.

- Pairwise Comparisons of RAG Methods
- Reference-based Scoring
- Assertion-based Scoring
- Hierarchical Assertions

### `assertion_gen.ipynb`

이미 존재하는 질문에 대해 assertion을 생성하는 흐름을 보여준다.

- Shared Configuration
- Data-Local Assertions
- Data-Global Assertions
- Notes on Assertion Generation

### `retrieval_metrics.ipynb`

retrieval 평가 전용 노트북이다.

- Reference Generation
- Retrieval Scoring
- Retrieval Relevance Assessment
- Precision
- Recall
- Fidelity
- Summary Comparison

## 기능별 대응표

- 질문 생성:
  - CLI: `benchmark-qed autoq ...`
  - Notebook: `docs/notebooks/autoq.ipynb`
- 데이터 요약/샘플링:
  - CLI: `benchmark-qed config init autoq`, `benchmark-qed autoq ...` 전 단계
  - Notebook: `docs/notebooks/autod.ipynb`
- 답변 평가:
  - CLI: `benchmark-qed autoe pairwise-scores`, `reference-scores`, `assertion-scores`
  - Notebook: `docs/notebooks/autoe.ipynb`
- assertion 생성:
  - CLI: `benchmark-qed autoq generate-assertions`
  - Notebook: `docs/notebooks/assertion_gen.ipynb`
- retrieval metric 평가:
  - CLI: `benchmark-qed autoe generate-retrieval-reference`, `retrieval-scores`
  - Notebook: `docs/notebooks/retrieval_metrics.ipynb`

## 추천 실행 순서

로컬 실험 기준으로는 보통 아래 순서가 제일 자연스럽다.

1. `config init`
2. `autod`
3. `autoq`
4. `generate-assertions`
5. `autoe`
6. `generate-retrieval-reference`
7. `retrieval-scores`
8. `smoke`

retrieval reference / scores 쪽 설정 파일은 별도로 작성해야 하고, `config init`이 공식적으로 템플릿을 만들어주는 항목은 아니다.

## 참고

- 실제 구현은 `vendor/benchmark-qed/benchmark_qed/` 아래에 있다.
- 이 문서는 upstream CLI와 notebook 구조를 빠르게 훑기 위한 요약이다.

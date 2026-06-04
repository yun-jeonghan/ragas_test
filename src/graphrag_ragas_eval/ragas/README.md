# Ragas Wrapper

`src/graphrag_ragas_eval/ragas/` 는 이 저장소가 upstream `ragas` 를 감싸는 경계입니다.

이 폴더는 다음을 담당합니다.

- GraphRAG / benchmark 결과를 `ragas` 입력 형식으로 바꾸는 어댑터
- `ragas` metric 평가 실행
- `ragas` testset generation 실행
- smoke report로 저장할 JSON 결과 정리

## 빠른 시작

1. 저장소를 clone 합니다.
   - `git clone --recurse-submodules git@github.com:yun-jeonghan/ragas_test.git`
   - 이미 clone 했다면 `git submodule update --init --recursive` 를 실행합니다.
2. `.env.example` 을 `.env` 로 복사합니다.
   - `cp .env.example .env`
3. `.env` 에서 최소한 아래 값을 맞춥니다.
   - `GREV_RAGAS_PROVIDER`
   - `GREV_RAGAS_MODEL`
   - `GREV_RAGAS_BASE_URL`
   - `GREV_RAGAS_API_KEY`
   - `GREV_RAGAS_EMBEDDINGS_PROVIDER`
   - `GREV_RAGAS_EMBEDDINGS_MODEL`
   - `GREV_RAGAS_EMBEDDINGS_BASE_URL`
   - `GREV_RAGAS_EMBEDDINGS_API_KEY`
4. 개발 의존성을 설치합니다.
   - `pip install -e ".[dev]"`
   - 로컬 CPU embeddings까지 쓰려면 `pip install -e ".[dev,cpu]"`
5. 질문 생성 또는 평가를 실행합니다.

## `.env` 구성

`ragas` 는 `GREV_RAGAS_*` prefix 를 읽습니다. 같은 prefix 아래에서 chat 모델과 embedding 모델을 각각 독립적으로 바꿀 수 있습니다.

### 평가용 LLM

- `GREV_RAGAS_PROVIDER`
- `GREV_RAGAS_MODEL`
- `GREV_RAGAS_BASE_URL`
- `GREV_RAGAS_API_KEY`
- `GREV_RAGAS_EXTRA_BODY`
- `GREV_RAGAS_MAX_TOKENS`

예시:

```env
GREV_RAGAS_PROVIDER=ollama
GREV_RAGAS_MODEL=qwen2.5:0.5b
GREV_RAGAS_BASE_URL=http://127.0.0.1:11434/v1
GREV_RAGAS_API_KEY=ollama
GREV_RAGAS_MAX_TOKENS=256
```

### 평가용 embeddings

- `GREV_RAGAS_EMBEDDINGS_PROVIDER`
- `GREV_RAGAS_EMBEDDINGS_MODEL`
- `GREV_RAGAS_EMBEDDINGS_BASE_URL`
- `GREV_RAGAS_EMBEDDINGS_API_KEY`
- `GREV_RAGAS_EMBEDDINGS_EXTRA_BODY`
- `GREV_RAGAS_EMBEDDINGS_DEVICE`
- `GREV_RAGAS_EMBEDDINGS_MAX_SEQ_LENGTH`
- `GREV_RAGAS_EMBEDDINGS_QUERY_PREFIX`
- `GREV_RAGAS_EMBEDDINGS_DOCUMENT_PREFIX`
- `GREV_RAGAS_EMBEDDINGS_NORMALIZE`

예시:

```env
GREV_RAGAS_EMBEDDINGS_PROVIDER=ollama
GREV_RAGAS_EMBEDDINGS_MODEL=nomic-embed-text
GREV_RAGAS_EMBEDDINGS_BASE_URL=http://127.0.0.1:11434/v1
GREV_RAGAS_EMBEDDINGS_API_KEY=ollama
GREV_RAGAS_EMBEDDINGS_MAX_SEQ_LENGTH=128
```

### 질문 생성용 설정

- `GREV_RAGAS_TESTSET_SIZE`
- `GREV_RAGAS_QUESTION_MODES`

`GREV_RAGAS_TESTSET_SIZE` 는 `grev ragas generate-questions` 의 기본 생성 개수입니다. CLI 에서 따로 지정하지 않으면 이 값이 들어갑니다.

`GREV_RAGAS_QUESTION_MODES` 는 ragas testset generation 에 사용할 query synthesizer 를 고릅니다. 콤마로 여러 개를 지정할 수 있습니다.

- `default`
  - ragas 기본 query distribution 을 그대로 사용
- `single-hop-specific`
- `multi-hop-abstract`
- `multi-hop-specific`
- `single-hop`
  - single-hop-specific 의 축약형
- `multi-hop`
  - multi-hop-abstract + multi-hop-specific

예시:

```env
GREV_RAGAS_TESTSET_SIZE=1
GREV_RAGAS_QUESTION_MODES=single-hop-specific
```

기본 모드만 쓰고 싶으면 `GREV_RAGAS_QUESTION_MODES=default` 로 두면 됩니다.

## 자주 쓰는 명령

### 질문 생성

```bash
grev ragas generate-questions \
  --source examples/sample_docs \
  --output data/benchmarks/ragas-questions.json
```

### 평가

```bash
grev ragas evaluate \
  --benchmark data/benchmarks/sample_benchmark.json \
  --search-results data/results/sample_search_results.json \
  --output data/results/ragas-evaluation.json
```

### smoke report

```bash
grev report smoke \
  --evaluation data/results/ragas-evaluation.json \
  --generated-questions data/benchmarks/ragas-questions.json \
  --output reports/ragas-smoke-report.html \
  --title "Ragas Smoke Report"
```

## 출력 구조

- 질문 생성 JSON
  - `metadata`
  - `questions`
- 평가 JSON
  - `scores`
  - `results`
  - `aggregate`

질문 생성 결과는 benchmark artifact 로 쓰고, 평가 결과는 report renderer 가 읽습니다.

## clone 후 다른 환경에서 쓰는 순서

1. 저장소 clone
2. submodule 초기화
3. `.env.example` 을 `.env` 로 복사
4. LLM / embeddings endpoint 를 운영 환경에 맞게 수정
5. `pip install -e ".[dev]"`
6. `grev ragas generate-questions` 또는 `grev ragas evaluate` 실행

`ragas` 가 OpenAI-compatible endpoint 를 쓰는 경우에는 `BASE_URL` 에 `/v1` 까지 포함한 루트 주소를 넣어야 합니다.
Ollama, vLLM, 내부 게이트웨이 모두 이 형태를 그대로 씁니다.

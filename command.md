# 실행 커맨드

이 문서는 이 저장소를 처음부터 실행할 때 필요한 명령만 모아둡니다.
모델명, endpoint, key 값은 이 문서에 하드코딩하지 말고 `.env.example` 과 쉘 env 로만 넣습니다.

## 0. 초기 설정

    cd /home/openclaw/projects/graphrag-eval
    python3 -m venv .venv
    . .venv/bin/activate
    pip install -e ".[dev]"
    pip install graphrag
    cp .env.example .env

- `.env`의 기본 예시는 OpenRouter GPT-4o 기준입니다.

OpenRouter GPT-4o 기준으로 Ragas와 BenchmarkQED 값을 각각 맞춰 넣습니다.

- `GREV_RAGAS_PROVIDER=openrouter`
- `GREV_RAGAS_MODEL=openai/gpt-4o`
- `GREV_RAGAS_BASE_URL=https://openrouter.ai/api/v1`
- `GREV_RAGAS_API_KEY=<openrouter-api-key>`
- `GREV_RAGAS_MAX_TOKENS=256`
- `GREV_RAGAS_EMBEDDINGS_PROVIDER=openrouter`
- `GREV_RAGAS_EMBEDDINGS_MODEL=openai/text-embedding-3-small`
- `GREV_RAGAS_EMBEDDINGS_BASE_URL=https://openrouter.ai/api/v1`
- `GREV_RAGAS_EMBEDDINGS_API_KEY=<openrouter-api-key>`
- `GREV_RAGAS_EMBEDDINGS_MAX_SEQ_LENGTH=128`
- `GREV_BENCHMARKQED_PROVIDER=openrouter`
- `GREV_BENCHMARKQED_MODEL=openai/gpt-4o`
- `GREV_BENCHMARKQED_BASE_URL=https://openrouter.ai/api/v1`
- `GREV_BENCHMARKQED_API_KEY=<openrouter-api-key>`
- `GREV_BENCHMARKQED_MAX_TOKENS=256`
- `GREV_BENCHMARKQED_EMBEDDINGS_PROVIDER=openrouter`
- `GREV_BENCHMARKQED_EMBEDDINGS_MODEL=openai/text-embedding-3-small`
- `GREV_BENCHMARKQED_EMBEDDINGS_BASE_URL=https://openrouter.ai/api/v1`
- `GREV_BENCHMARKQED_EMBEDDINGS_API_KEY=<openrouter-api-key>`
- `GREV_BENCHMARKQED_EMBEDDINGS_MAX_SEQ_LENGTH=128`

PDF 추출 모드도 `.env`에서 바로 고를 수 있습니다.

- `GREV_PDF_EXTRACTOR_MODE=chandra_only`
- `GREV_PDF_OCR_BACKEND=chandra`

MinerU 하이브리드로 갈 때는:

- `GREV_PDF_EXTRACTOR_MODE=mineru_hybrid`
- `GREV_PDF_MINERU_COMMAND=mineru`
- `GREV_PDF_OCR_BACKEND=chandra`

개별 prefix를 쓰고 싶으면 아래처럼 덮어쓸 수 있습니다.

- `GREV_RAGAS_PROVIDER=<provider>`
- `GREV_RAGAS_MODEL=<chat-model-name>`
- `GREV_RAGAS_BASE_URL=<openai-compatible-base-url>`
- `GREV_RAGAS_API_KEY=<api-key>`
- `GREV_RAGAS_MAX_TOKENS=256`
- `GREV_BENCHMARKQED_PROVIDER=<provider>`
- `GREV_BENCHMARKQED_MODEL=<chat-model-name>`
- `GREV_BENCHMARKQED_BASE_URL=<openai-compatible-base-url>`
- `GREV_BENCHMARKQED_API_KEY=<api-key>`
- `GREV_BENCHMARKQED_MAX_TOKENS=256`

같은 서버에 embeddings 엔드포인트도 같이 열려 있으면 아래도 같은 값으로 맞추면 됩니다.

- `GREV_RAGAS_EMBEDDINGS_PROVIDER=<provider>`
- `GREV_RAGAS_EMBEDDINGS_MODEL=<embedding-model-name>`
- `GREV_RAGAS_EMBEDDINGS_BASE_URL=<openai-compatible-base-url>`
- `GREV_RAGAS_EMBEDDINGS_API_KEY=<api-key>`
- `GREV_BENCHMARKQED_EMBEDDINGS_PROVIDER=<provider>`
- `GREV_BENCHMARKQED_EMBEDDINGS_MODEL=<embedding-model-name>`
- `GREV_BENCHMARKQED_EMBEDDINGS_BASE_URL=<openai-compatible-base-url>`
- `GREV_BENCHMARKQED_EMBEDDINGS_API_KEY=<api-key>`

- `GREV_RAGAS_PROVIDER=<provider>`
- `GREV_RAGAS_MODEL=<chat-model-name>`
- `GREV_RAGAS_BASE_URL=<openai-compatible-base-url>`
- `GREV_RAGAS_API_KEY=<api-key>`

OpenRouter GPT-4o로 바꿀 때는 아래처럼 바꿉니다.

- `GREV_RAGAS_PROVIDER=openrouter`
- `GREV_RAGAS_MODEL=openai/gpt-4o`
- `GREV_RAGAS_BASE_URL=https://openrouter.ai/api/v1`
- `GREV_RAGAS_API_KEY=<openrouter-api-key>`
- `GREV_RAGAS_EXTRA_BODY={"chat_template_kwargs":{"enable_thinking":false}}`

upstream benchmark-qed AutoE도 같은 방식으로 별도 설정을 씁니다.

- `GREV_BENCHMARKQED_PROVIDER=<provider>`
- `GREV_BENCHMARKQED_MODEL=<chat-model-name>`
- `GREV_BENCHMARKQED_BASE_URL=<openai-compatible-base-url>`
- `GREV_BENCHMARKQED_API_KEY=<api-key>`

OpenRouter GPT-4o로 바꿀 때는 아래처럼 바꿉니다.

- `GREV_BENCHMARKQED_PROVIDER=openrouter`
- `GREV_BENCHMARKQED_MODEL=openai/gpt-4o`
- `GREV_BENCHMARKQED_BASE_URL=https://openrouter.ai/api/v1`
- `GREV_BENCHMARKQED_API_KEY=<openrouter-api-key>`
- `GREV_BENCHMARKQED_EXTRA_BODY={"chat_template_kwargs":{"enable_thinking":false}}`

kg-gen MINE 스타일 판정도 같은 방식으로 별도 설정을 씁니다.

- `GREV_KGGEN_MINE_PROVIDER=<provider>`
- `GREV_KGGEN_MINE_MODEL=<chat-model-name>`
- `GREV_KGGEN_MINE_BASE_URL=<openai-compatible-base-url>`
- `GREV_KGGEN_MINE_API_KEY=<api-key>`
- `GREV_KGGEN_MINE_MAX_TOKENS=256`

OpenRouter GPT-4o로 바꿀 때는 아래처럼 바꿉니다.

- `GREV_KGGEN_MINE_PROVIDER=openrouter`
- `GREV_KGGEN_MINE_MODEL=openai/gpt-4o`
- `GREV_KGGEN_MINE_BASE_URL=https://openrouter.ai/api/v1`
- `GREV_KGGEN_MINE_API_KEY=<openrouter-api-key>`
- `GREV_KGGEN_MINE_EXTRA_BODY={"chat_template_kwargs":{"enable_thinking":false}}`

## 1. 문서 넣고 GraphRAG 인덱싱

예시 문서를 그대로 쓰려면:

    grev graphrag normalize --source examples/sample_docs --workspace-root workspaces/graphrag --clean
    grev graphrag stage --source examples/sample_docs --workspace-root workspaces/graphrag
    grev graphrag index --source examples/sample_docs --workspace-root workspaces/graphrag --force

MinerU 하이브리드 모드로 돌리려면:

    GREV_PDF_EXTRACTOR_MODE=mineru_hybrid \
    GREV_PDF_MINERU_COMMAND=mineru \
    GREV_PDF_OCR_BACKEND=chandra \
    grev graphrag normalize --source examples/sample_docs --workspace-root workspaces/graphrag --clean

단계별로 나눠서 돌리려면:

    grev graphrag normalize --source examples/sample_docs --workspace-root workspaces/graphrag
    grev graphrag stage --source examples/sample_docs --workspace-root workspaces/graphrag
    grev graphrag init --source examples/sample_docs --workspace-root workspaces/graphrag --force
    grev graphrag index --source examples/sample_docs --workspace-root workspaces/graphrag

초소형 스모크를 하려면 질문 수와 메트릭 수를 줄입니다.

    grev generate-questions --source examples/sample_docs --output data/benchmarks/generated_questions.json --num-questions 1 --modes local
    grev benchmark-qed autod --source examples/sample_docs --output data/benchmark-qed/autod-summary.json --target-size 1
    grev benchmark-qed autoq --source examples/sample_docs --output data/benchmark-qed/autoq-questions.json --num-questions 1 --modes local
    grev benchmark-qed autoe --benchmark data/benchmarks/sample_benchmark.json --search-results data/results/sample_search_results.json --output data/benchmark-qed/autoe-evaluation.json --metrics context_precision
    grev kg-gen mine evaluate --benchmark data/benchmarks/sample_benchmark.json --search-results data/results/sample_search_results.json --output data/kggen-mine/evaluation.json

사용자 온톨로지와 후처리를 함께 쓰려면:

    grev graphrag index +      --source examples/sample_docs +      --workspace-root workspaces/graphrag +      --ontology-path workspaces/graphrag/config/user_ontology.json +      --postprocess +      --description-limit 200

인덱싱이 끝난 뒤 후처리만 다시 돌리려면:

    grev graphrag postprocess --workspace-root workspaces/graphrag --description-limit 200

## 2. GraphRAG 결과 확인

    grev inspect --graphrag-root workspaces/graphrag/output

## 3. 평가 실행

샘플 검색 결과를 기준으로 평가:

    grev evaluate \
      --benchmark data/benchmarks/sample_benchmark.json \
      --search-results data/results/sample_search_results.json \
      --output data/results/evaluation.json

OpenRouter GPT-4o 기준으로 평가:

    grev evaluate \
      --benchmark data/benchmarks/sample_benchmark.json \
      --search-results data/results/sample_search_results.json \
      --output data/results/evaluation.json \
      --provider openrouter \
      --base-url https://openrouter.ai/api/v1 \
      --api-key <openrouter-api-key> \
      --model openai/gpt-4o

`.env`에 이미 위 값들을 넣어두면 `--provider/--base-url/--api-key/--model` 플래그는 생략해도 됩니다.
스모크에서는 `--metrics context_precision` 같이 1개만 주는 편이 가장 가볍습니다.

`grev eval run` 기반 ontology eval harness 는 별도 레포 `/home/openclaw/projects/ontology-eval-harness` 로 분리되었습니다. 단일 평가, A/B 비교, human review CSV, regression detection 예시는 새 레포의 문서를 보시면 됩니다.

## 4. 질문 생성

문서에서 평가 질문을 만들기:

    grev generate-questions --source examples/sample_docs --output data/benchmarks/generated_questions.json --num-questions 1 --modes local

multi-hop, unanswerable도 포함하려면:

    grev generate-questions --source examples/sample_docs --output data/benchmarks/generated_questions.json --num-questions 4 --modes local global multi-hop unanswerable

## 5. upstream benchmark-qed 명령

AutoD 요약:

    grev benchmark-qed autod --source examples/sample_docs --output data/benchmark-qed/autod-summary.json --target-size 1

AutoQ 질문 생성:

    grev benchmark-qed autoq --source examples/sample_docs --output data/benchmark-qed/autoq-questions.json --num-questions 1 --modes local

AutoE 평가:

    grev benchmark-qed autoe --benchmark data/benchmarks/sample_benchmark.json --search-results data/results/sample_search_results.json --output data/benchmark-qed/autoe-evaluation.json --metrics context_precision

kg-gen MINE 스타일 평가:

    grev kg-gen mine evaluate --benchmark data/benchmarks/sample_benchmark.json --search-results data/results/sample_search_results.json --output data/kggen-mine/evaluation.json

## 5. 문법 확인

    python3 -m compileall -q src tests

## 6. 자주 보는 파일

- README.md - 전체 요약
- docs/sample-workflow.md - 전체 흐름
- docs/evaluation-modes.md - 평가 항목과 질문 모드

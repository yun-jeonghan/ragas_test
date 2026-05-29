# 실행 커맨드

이 문서는 이 저장소를 처음부터 실행할 때 필요한 명령만 모아둡니다.

## 0. 초기 설정

    cd /home/openclaw/projects/graphrag-ragas-eval
    python3 -m venv .venv
    . .venv/bin/activate
    pip install -e ".[dev]"
    pip install graphrag
    cp .env.example .env

- `.env`에서 기본값은 OpenAI 테스트용입니다.

- `GREV_RAGAS_PROVIDER=openai`
- `GREV_RAGAS_MODEL=gpt-4o-mini`
- `GREV_RAGAS_API_KEY=<your-openai-key>`

vLLM로 바꿀 때는 아래처럼 바꿉니다.

- `GREV_RAGAS_PROVIDER=vllm`
- `GREV_RAGAS_MODEL=<vllm-model-name>`
- `GREV_RAGAS_BASE_URL=http://<vllm-host>:8000/v1`
- `GREV_RAGAS_API_KEY=vllm`

BenchmarkQED 스타일 AutoE도 같은 방식으로 별도 설정을 씁니다.

- `GREV_BENCHMARKQED_PROVIDER=openai`
- `GREV_BENCHMARKQED_MODEL=gpt-4o-mini`
- `GREV_BENCHMARKQED_API_KEY=<your-openai-key>`

vLLM로 바꿀 때는 아래처럼 바꿉니다.

- `GREV_BENCHMARKQED_PROVIDER=vllm`
- `GREV_BENCHMARKQED_MODEL=<vllm-model-name>`
- `GREV_BENCHMARKQED_BASE_URL=http://<vllm-host>:8000/v1`
- `GREV_BENCHMARKQED_API_KEY=vllm`

## 1. 문서 넣고 GraphRAG 인덱싱

예시 문서를 그대로 쓰려면:

    grev graphrag index --source examples/sample_docs --workspace-root workspaces/graphrag --force

단계별로 나눠서 돌리려면:

    grev graphrag stage --source examples/sample_docs --workspace-root workspaces/graphrag
    grev graphrag init --source examples/sample_docs --workspace-root workspaces/graphrag --force
    grev graphrag index --source examples/sample_docs --workspace-root workspaces/graphrag

## 2. GraphRAG 결과 확인

    grev inspect --graphrag-root workspaces/graphrag/output

## 3. 평가 실행

샘플 검색 결과를 기준으로 평가:

    grev evaluate \
      --benchmark data/benchmarks/sample_benchmark.json \
      --search-results data/results/sample_search_results.json \
      --output data/results/evaluation.json

vLLM endpoint를 명시해서 평가:

    grev evaluate \
      --benchmark data/benchmarks/sample_benchmark.json \
      --search-results data/results/sample_search_results.json \
      --output data/results/evaluation.json \
      --provider vllm \
      --base-url http://127.0.0.1:8000/v1 \
      --api-key vllm \
      --model <vllm-model-name>

## 4. 질문 생성

문서에서 평가 질문을 만들기:

    grev generate-questions --source examples/sample_docs --output data/benchmarks/generated_questions.json --num-questions 10 --modes local global

multi-hop, unanswerable도 포함하려면:

    grev generate-questions --source examples/sample_docs --output data/benchmarks/generated_questions.json --num-questions 10 --modes local global multi-hop unanswerable

## 5. BenchmarkQED 스타일 명령

AutoD 요약:

    grev benchmark-qed autod --source examples/sample_docs --output data/benchmark-qed/autod-summary.json

AutoQ 질문 생성:

    grev benchmark-qed autoq --source examples/sample_docs --output data/benchmark-qed/autoq-questions.json --num-questions 10 --modes local global

AutoE 평가:

    grev benchmark-qed autoe --benchmark data/benchmarks/sample_benchmark.json --search-results data/results/sample_search_results.json --output data/benchmark-qed/autoe-evaluation.json

## 5. 문법 확인

    python3 -m compileall -q src tests

## 6. 자주 보는 파일

- README.md - 전체 요약
- docs/sample-workflow.md - 전체 흐름
- docs/evaluation-modes.md - 평가 항목과 질문 모드
- docs/question-generation.md - 질문 생성 방식
- docs/graphrag-workspace.md - GraphRAG 작업공간 설명

# GraphRAG Ragas Eval

GraphRAG로 만든 그래프 기반 검색과 생성 결과를 Ragas로 평가하는 프로젝트입니다.

## 목적

- GraphRAG가 만든 parquet 출력물을 기준 데이터로 읽습니다.
- local/global 검색 결과를 같은 형식으로 감싸서 평가합니다.
- Ragas 지표로 검색 품질과 답변 품질을 측정합니다.
- 그래프 특유의 품질은 별도 지표로 보강합니다.

## upstream 기준

- `vendor/ragas` - <https://github.com/yun-jeonghan/ragas> (upstream origin: <https://github.com/explodinggradients/ragas.git>)
- `vendor/benchmark-qed` - <https://github.com/microsoft/benchmark-qed.git>
- `vendor/kg-gen` - <https://github.com/stair-lab/kg-gen>

각 구현은 위 upstream을 기준으로 입력/출력 포맷만 감싸는 구조입니다.

## 기본 구조

- data/raw/graphrag/ - GraphRAG 인덱싱 출력물
- data/benchmarks/ - 평가 질문셋
- data/results/ - 평가 결과
- reports/ - 사람이 읽는 요약 리포트
- workspaces/graphrag/ - 문서를 넣고 GraphRAG 인덱싱을 돌리는 별도 작업공간

## 자주 쓰는 명령

- grev init - 프로젝트 경로 출력
- grev inspect - GraphRAG parquet 확인
- grev graphrag stage - 문서를 GraphRAG 워크스페이스로 복사
- grev graphrag init - GraphRAG 작업공간 초기화
- grev graphrag index - 문서 반영 후 인덱싱 실행
- grev evaluate - 저장된 검색 결과를 Ragas로 평가
- grev generate-questions - 문서에서 평가 질문 생성
- grev benchmark-qed autod/autoq/autoe - upstream `benchmark-qed` 흐름
- grev kg-gen mine evaluate - kg-gen MINE 스타일 binary correctness 평가
- grev kg-correctness evaluate - 위 명령의 호환 별칭
- grev report smoke - JSON 결과를 HTML 리포트로 렌더링

`grev eval run` 기반 ontology eval harness 는 별도 레포 `/home/openclaw/projects/ontology-eval-harness` 로 분리되었습니다. 이 레포에는 더 이상 해당 CLI 나 스키마 문서가 포함되지 않습니다.

자세한 실행 예시는 command.md를 보시면 됩니다. Ragas wrapper 전용 설정과 clone 가이드는 `src/graphrag_ragas_eval/ragas/README.md` 를 보시면 됩니다.

## 파이프라인 스크립트

이 레포는 fixture 복사 없이 외부 입력을 그대로 받아서 도는 쉘 파이프라인을 따로 제공합니다.
각 스크립트는 입력 경로와 출력 경로를 인자로 받고, 실패가 있어도 `summary.jsonl` 과 HTML report 는 끝까지 생성합니다.
하드코딩하지 말것: 모델명, endpoint, key 값은 문서에 박지 말고 `.env` 나 쉘 env 로만 주입합니다.

기능별 최신 성공 여부를 보려면 `test_progress.md` 를 확인하고, 전체 행렬과 pytest 상태를 다시 돌리려면 `scripts/update_test_progress.sh` 를 실행하면 됩니다.

### BenchmarkQED + GraphRAG 파이프라인

입력:

- `SOURCE_DIR` - `.txt` 문서가 들어있는 디렉터리
- `BENCHMARK_JSON` - 질문셋 JSON 또는 JSONL
- `RESULTS_JSON` - GraphRAG 검색 결과 JSON
- `ONTOLOGY_JSON` - GraphRAG ontology JSON
- `OUTPUT_DIR` - 실행 결과를 저장할 디렉터리

실행:

```sh
./scripts/benchmark_pipeline.sh SOURCE_DIR BENCHMARK_JSON RESULTS_JSON ONTOLOGY_JSON OUTPUT_DIR
```

생성물:

- `OUTPUT_DIR/summary.jsonl`
- `OUTPUT_DIR/logs/`
- `OUTPUT_DIR/runs/benchmark-qed/`
- `OUTPUT_DIR/runs/retrieval-smoke/`
- `OUTPUT_DIR/runs/assertion-score/`
- `OUTPUT_DIR/reports/benchmark-pipeline.html`

이 파이프라인은 아래를 순서대로 실행합니다.

- `graphrag normalize`
- `graphrag stage`
- `graphrag init`
- `graphrag index`
- `benchmark generate-questions`
- `benchmark-qed autod`
- `benchmark-qed autoq`
- `benchmark-qed autoe`
- `benchmark-qed smoke`
- `benchmark-qed retrieval-smoke`
- `benchmark-qed retrieval-reference`
- `benchmark-qed retrieval-score`
- `benchmark-qed assertion-score`
- `benchmark-qed assertion-report`
- `evaluate`
- `ragas evaluate`
- `kg-gen mine evaluate`
- `kg-correctness evaluate`
- `ograg2 evaluate`

### Ragas 파이프라인

입력:

- `SOURCE_DIR` - `.txt` 문서가 들어있는 디렉터리
- `BENCHMARK_JSON` - 평가 질문셋 JSON 또는 JSONL
- `RESULTS_JSON` - 검색 결과 JSON
- `OUTPUT_DIR` - 실행 결과를 저장할 디렉터리

실행:

```sh
./scripts/ragas_pipeline.sh SOURCE_DIR BENCHMARK_JSON RESULTS_JSON OUTPUT_DIR
```

생성물:

- `OUTPUT_DIR/summary.jsonl`
- `OUTPUT_DIR/logs/`
- `OUTPUT_DIR/runs/ragas-generate-questions/`
- `OUTPUT_DIR/runs/ragas-evaluate/`
- `OUTPUT_DIR/reports/ragas-pipeline.html`

### 통합 report

BenchmarkQED 파이프라인과 Ragas 파이프라인 summary를 합쳐 하나의 HTML report로 만들 수 있습니다.

```sh
./scripts/integrated_report.sh BENCHMARK_SUMMARY_JSONL RAGAS_SUMMARY_JSONL OUTPUT_HTML
```

### legacy wrapper

기존에 `scripts/ragas_smoke.sh` 를 쓰던 경우에는 같은 인자 형식으로 그대로 호출해도 됩니다.
이제 내부적으로는 `ragas_pipeline.sh` 로 넘깁니다.

### 실행 전 체크

- `GREV_*` env 값이 입력된 모델/endpoint와 맞는지 확인
- `SOURCE_DIR` 에 TXT 문서가 실제로 있는지 확인
- `BENCHMARK_JSON` 과 `RESULTS_JSON` 이 같은 question/sample id 를 쓰는지 확인
- `ONTOLOGY_JSON` 이 필요한 경우 해당 GraphRAG 인덱싱에서 쓸 수 있는지 확인

실행 후에는 각 `summary.jsonl` 을 보고 실패한 단계부터 다시 보면 됩니다.

## 설치

이 프로젝트는 Python 3.11 이상을 기준으로 합니다.

- 개발 설치: `pip install -e ".[dev]"`
- 로컬 CPU 임베딩까지 쓸 거면 `pip install -e ".[dev,cpu]"`
- GraphRAG가 별도 설치 환경이면 `pip install graphrag` 도 필요할 수 있습니다.
- CLI는 설치 후 `grev` 로 실행합니다.

이미 vLLM, MinerU, Chandra 같은 외부 서비스가 따로 있으면 이 저장소에는 추가 GPU 의존성이 없습니다. 이 레포는 그 엔드포인트들을 호출하는 클라이언트 역할입니다.

## 빠른 시작

1. 저장소를 설치합니다.
   - `pip install -e ".[dev]"`
   - GraphRAG CLI도 별도라면 같이 설치합니다.
2. `.env.example`을 `.env`로 복사하고, 아래 값만 환경에 맞게 수정합니다.
   - LLM 모델 이름
   - LLM/embedding BASE_URL
   - API_KEY
   - 필요하면 `EXTRA_BODY`
   - PDF 추출 모드와 OCR/문서 모델 주소
3. 문서를 `examples/sample_docs` 같은 폴더에 둡니다.
4. 한 번에 끝내려면 `grev graphrag index --source <docs> --workspace-root workspaces/graphrag` 를 실행합니다.
   - 이 명령은 내부적으로 canonical TXT를 만들고, GraphRAG 워크스페이스를 초기화한 뒤, 인덱싱까지 수행합니다.
5. canonical TXT만 따로 확인하고 싶으면 `grev graphrag normalize --source <docs> --workspace-root workspaces/graphrag` 를 먼저 실행합니다.
6. GraphRAG 검색 결과 JSON을 저장한 다음 `grev evaluate --benchmark ... --search-results ...` 를 실행합니다.

가장 자주 바꾸는 건 `.env` 의 모델 주소/모델 이름입니다. 아래 섹션만 보면 됩니다.

## LLM 전환

전환할 때는 `.env.example` 기준으로 아래만 바꾸면 됩니다.

- Ragas 평가용: `GREV_RAGAS_PROVIDER`, `GREV_RAGAS_MODEL`, `GREV_RAGAS_BASE_URL`, `GREV_RAGAS_API_KEY`
- Ragas embeddings: `GREV_RAGAS_EMBEDDINGS_PROVIDER`, `GREV_RAGAS_EMBEDDINGS_MODEL`, `GREV_RAGAS_EMBEDDINGS_BASE_URL`, `GREV_RAGAS_EMBEDDINGS_API_KEY`
- upstream benchmark-qed용: `GREV_BENCHMARKQED_PROVIDER`, `GREV_BENCHMARKQED_MODEL`, `GREV_BENCHMARKQED_BASE_URL`, `GREV_BENCHMARKQED_API_KEY`
- BenchmarkQED embeddings: `GREV_BENCHMARKQED_EMBEDDINGS_PROVIDER`, `GREV_BENCHMARKQED_EMBEDDINGS_MODEL`, `GREV_BENCHMARKQED_EMBEDDINGS_BASE_URL`, `GREV_BENCHMARKQED_EMBEDDINGS_API_KEY`
- kg-gen MINE 스타일 판정용: `GREV_KGGEN_MINE_PROVIDER`, `GREV_KGGEN_MINE_MODEL`, `GREV_KGGEN_MINE_BASE_URL`, `GREV_KGGEN_MINE_API_KEY`

엔드포인트를 다른 서버로 옮길 때는 아래를 같이 맞추는 게 핵심입니다.

- `MODEL`: 서버가 실제로 서빙하는 모델 이름
- `BASE_URL`: `/v1` 까지 포함한 OpenAI-compatible 루트 주소
- `API_KEY`: OpenAI 또는 RunPod / gateway 인증 토큰
- `EXTRA_BODY`: chat/completions 요청에만 추가되는 JSON 객체
- `EMBEDDINGS_EXTRA_BODY`: embeddings 요청에만 추가되는 JSON 객체

즉, `messages` 같은 본문 JSON에 `extra_body`가 섞이는 게 아니라, OpenAI client 호출 시 `extra_body` 파라미터로 별도 전달됩니다.

각 영역은 서로 독립적으로 바꿀 수 있습니다. 평가만 vLLM으로 돌리고, BenchmarkQED는 OpenAI로 남겨둘 수도 있습니다.

코드 쪽은 src/graphrag_ragas_eval/llm.py 한 곳만 보면 됩니다.

자세한 변수 설명은 docs/environment.md를 보시면 됩니다.

## env에서 실제로 바꾸는 곳

모델 교체할 때는 아래만 바꾸면 됩니다.

- Ragas LLM: `GREV_RAGAS_PROVIDER`, `GREV_RAGAS_MODEL`, `GREV_RAGAS_BASE_URL`, `GREV_RAGAS_API_KEY`
- Ragas embeddings: `GREV_RAGAS_EMBEDDINGS_PROVIDER`, `GREV_RAGAS_EMBEDDINGS_MODEL`, `GREV_RAGAS_EMBEDDINGS_BASE_URL`, `GREV_RAGAS_EMBEDDINGS_API_KEY`
- BenchmarkQED LLM: `GREV_BENCHMARKQED_PROVIDER`, `GREV_BENCHMARKQED_MODEL`, `GREV_BENCHMARKQED_BASE_URL`, `GREV_BENCHMARKQED_API_KEY`
- BenchmarkQED embeddings: `GREV_BENCHMARKQED_EMBEDDINGS_PROVIDER`, `GREV_BENCHMARKQED_EMBEDDINGS_MODEL`, `GREV_BENCHMARKQED_EMBEDDINGS_BASE_URL`, `GREV_BENCHMARKQED_EMBEDDINGS_API_KEY`
- kg-gen MINE 스타일 판정용: `GREV_KGGEN_MINE_PROVIDER`, `GREV_KGGEN_MINE_MODEL`, `GREV_KGGEN_MINE_BASE_URL`, `GREV_KGGEN_MINE_API_KEY`
- 같은 GPU 서버를 공유하더라도 각 prefix에 값을 복사해서 넣는 방식으로 맞춥니다.
- Qwen 생각 끄기 같은 추가 옵션은 `GREV_*_EXTRA_BODY` 또는 `GREV_*_EMBEDDINGS_EXTRA_BODY` 로 넣습니다.

CPU 테스트를 할 때는 이렇게 생각하면 됩니다.

- LLM: OpenAI-compatible 서버가 있으면 `GREV_RAGAS_BASE_URL` 만 해당 주소로 바꿉니다.
- embeddings: `GREV_RAGAS_EMBEDDINGS_PROVIDER=local` 로 두고 local embedding 모델과 `GREV_RAGAS_EMBEDDINGS_DEVICE=cpu` 를 넣습니다. BenchmarkQED도 같은 방식으로 `GREV_BENCHMARKQED_EMBEDDINGS_PROVIDER=local` 을 쓰면 됩니다.
- E5 계열은 기본으로 `query: ` / `passage: ` 접두사를 자동으로 붙입니다. 필요하면 `GREV_*_EMBEDDINGS_QUERY_PREFIX`, `GREV_*_EMBEDDINGS_DOCUMENT_PREFIX` 로 덮어쓸 수 있습니다.
- 스모크를 안정적으로 돌리려면 `GREV_*_MAX_TOKENS=256`, `GREV_*_EMBEDDINGS_MAX_SEQ_LENGTH=128` 을 권장합니다.

PDF 쪽은 다음만 바꾸면 됩니다.

- `GREV_PDF_EXTRACTOR_MODE`
- `GREV_PDF_OCR_BACKEND`
- `GREV_PDF_DESCRIPTION_BACKEND`
- `GREV_PDF_MINERU_COMMAND`
- `GREV_PDF_MINERU_OUTPUT_ARTIFACT`

## 문서 입력 흐름

1. 문서를 docs 같은 디렉터리에 둡니다.
2. grev graphrag stage로 GraphRAG 워크스페이스 입력 폴더에 복사합니다.
3. grev graphrag init으로 GraphRAG 프로젝트를 초기화합니다.
4. grev graphrag index로 지식 그래프를 생성합니다.
5. GraphRAG 검색 결과를 JSON으로 저장합니다.
6. grev evaluate로 점수화합니다.

샘플 흐름은 docs/sample-workflow.md를 보면 됩니다.

평가 항목과 질문 모드는 docs/evaluation-modes.md를 보면 됩니다.
KG correctness / MINE 스타일 판정은 docs/kg-correctness.md를 보면 됩니다.

질문 생성은 docs/question-generation.md를 보면 됩니다.

TXT 추출과 PDF OCR 흐름은 docs/txt-extraction.md를 보면 됩니다.

GitHub SSH push 절차는 docs/github-push-ssh.md를 보면 됩니다.

upstream benchmark-qed 구조는 docs/benchmark-qed.md를 보면 됩니다.

자세한 설계는 docs/architecture.md, docs/benchmark-schema.md, docs/search-design.md, docs/graphrag-workspace.md, docs/environment.md를 보시면 됩니다.

## GraphRAG 버전

이 레포는 GraphRAG 자체를 vendoring 하지 않고 CLI를 호출하는 wrapper입니다.
현재 코드와 문서는 `graphrag init` / `graphrag index` / `--root` / `--model` / `--embedding` / `--method` / `--skip-validation` 흐름을 기준으로 작성되어 있습니다.
즉, 특정 버전 번호를 pyproject에 고정하지는 않았고, 실제 설치한 GraphRAG CLI가 이 인자들을 지원해야 합니다.
실무적으로는 GraphRAG 0.4.x 계열에서 잘 맞는 구조이지만, 이 저장소가 "0.4.0만" 딱 고정해서 검증된 상태라고 보기는 어렵습니다.
버전이 다르면 `src/graphrag_ragas_eval/graphrag/workspace.py` 의 CLI 인자만 먼저 확인하면 됩니다.

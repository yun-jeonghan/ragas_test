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

자세한 실행 예시는 command.md를 보시면 됩니다. Ragas wrapper 전용 설정과 clone 가이드는 `src/graphrag_ragas_eval/ragas/README.md` 를 보시면 됩니다.

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

현재는 로컬 Ollama를 기본으로 씁니다.

- 테스트와 검증은 로컬 Ollama
- 더 가벼운 chat 모델이 필요하면 `smollm2:135m`
- 나중에 실서빙이나 다른 로컬 추론 엔진으로 옮길 때는 vLLM OpenAI-compatible endpoint

전환할 때는 .env.example 기준으로 아래만 바꾸면 됩니다.

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

- LLM: Ollama나 vLLM CPU처럼 OpenAI-compatible 서버가 있으면 `GREV_RAGAS_BASE_URL` 만 로컬 주소로 바꿉니다.
- embeddings: `GREV_RAGAS_EMBEDDINGS_PROVIDER=local` 로 두고 `GREV_RAGAS_EMBEDDINGS_MODEL=intfloat/multilingual-e5-small`, `GREV_RAGAS_EMBEDDINGS_DEVICE=cpu` 를 넣습니다. BenchmarkQED도 같은 방식으로 `GREV_BENCHMARKQED_EMBEDDINGS_PROVIDER=local` 을 쓰면 됩니다.
- E5 계열은 기본으로 `query: ` / `passage: ` 접두사를 자동으로 붙입니다. 필요하면 `GREV_*_EMBEDDINGS_QUERY_PREFIX`, `GREV_*_EMBEDDINGS_DOCUMENT_PREFIX` 로 덮어쓸 수 있습니다.
- 스모크를 안정적으로 돌리려면 `GREV_*_MAX_TOKENS=256`, `GREV_*_EMBEDDINGS_MAX_SEQ_LENGTH=128` 을 권장합니다.

PDF 쪽은 다음만 바꾸면 됩니다.

- `GREV_PDF_EXTRACTOR_MODE`
- `GREV_PDF_OCR_BACKEND`
- `GREV_PDF_DESCRIPTION_BACKEND`
- `GREV_PDF_MINERU_COMMAND`
- `GREV_PDF_MINERU_OUTPUT_ARTIFACT`

### 최소 `.env` 템플릿

아래 값만 채우면 가장 먼저 돌아가는 구성이 됩니다. 나머지는 `EXTRA_BODY`만 필요할 때 추가하세요.

```env
# Ragas LLM
GREV_RAGAS_PROVIDER=vllm
GREV_RAGAS_MODEL=your-llm-model-name
GREV_RAGAS_BASE_URL=http://your-host:8000/v1
GREV_RAGAS_API_KEY=vllm
GREV_RAGAS_MAX_TOKENS=256

# Ragas embeddings
GREV_RAGAS_EMBEDDINGS_PROVIDER=vllm
GREV_RAGAS_EMBEDDINGS_MODEL=your-embedding-model-name
GREV_RAGAS_EMBEDDINGS_BASE_URL=http://your-host:8001/v1
GREV_RAGAS_EMBEDDINGS_API_KEY=vllm
GREV_RAGAS_EMBEDDINGS_MAX_SEQ_LENGTH=128

# BenchmarkQED LLM
GREV_BENCHMARKQED_PROVIDER=vllm
GREV_BENCHMARKQED_MODEL=your-llm-model-name
GREV_BENCHMARKQED_BASE_URL=http://your-host:8000/v1
GREV_BENCHMARKQED_API_KEY=vllm
GREV_BENCHMARKQED_MAX_TOKENS=256

# BenchmarkQED embeddings
GREV_BENCHMARKQED_EMBEDDINGS_PROVIDER=vllm
GREV_BENCHMARKQED_EMBEDDINGS_MODEL=your-embedding-model-name
GREV_BENCHMARKQED_EMBEDDINGS_BASE_URL=http://your-host:8001/v1
GREV_BENCHMARKQED_EMBEDDINGS_API_KEY=vllm
GREV_BENCHMARKQED_EMBEDDINGS_MAX_SEQ_LENGTH=128

# PDF extraction
GREV_PDF_EXTRACTOR_MODE=chandra_only
GREV_PDF_OCR_BACKEND=chandra
```

여기서 보통 바꾸는 건 `MODEL`, `BASE_URL`, `API_KEY` 입니다.
`MODEL`은 서버가 실제로 서빙하는 이름, `BASE_URL`은 `/v1`까지 포함한 주소, `API_KEY`는 서버 종류에 따라 비워두거나 토큰을 넣으면 됩니다.

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

# GraphRAG Ragas Eval

GraphRAG로 만든 그래프 기반 검색과 생성 결과를 Ragas로 평가하는 프로젝트입니다.

## 목적

- GraphRAG가 만든 parquet 출력물을 기준 데이터로 읽습니다.
- local/global 검색 결과를 같은 형식으로 감싸서 평가합니다.
- Ragas 지표로 검색 품질과 답변 품질을 측정합니다.
- 그래프 특유의 품질은 별도 지표로 보강합니다.

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
- grev benchmark-qed autod/autoq/autoe - BenchmarkQED 스타일 흐름

자세한 실행 예시는 command.md를 보시면 됩니다.

## 설치

이 프로젝트는 Python 3.11 이상을 기준으로 합니다.

- 개발 설치: `pip install -e ".[dev]"`
- GraphRAG가 별도 설치 환경이면 `pip install graphrag` 도 필요할 수 있습니다.
- CLI는 설치 후 `grev` 로 실행합니다.

이미 vLLM, MinerU, Chandra 같은 외부 서비스가 따로 있으면 이 저장소에는 추가 GPU 의존성이 없습니다. 이 레포는 그 엔드포인트들을 호출하는 클라이언트 역할입니다.

## LLM 전환

현재는 OpenAI API를 기본으로 씁니다.

- 테스트와 검증은 OpenAI
- 나중에 실서빙이나 로컬 추론은 vLLM OpenAI-compatible endpoint

전환할 때는 .env.example 기준으로 아래만 바꾸면 됩니다.

- Ragas 평가용: `GREV_RAGAS_PROVIDER`, `GREV_RAGAS_MODEL`, `GREV_RAGAS_BASE_URL`, `GREV_RAGAS_API_KEY`
- Ragas embeddings: `GREV_RAGAS_EMBEDDINGS_PROVIDER`, `GREV_RAGAS_EMBEDDINGS_MODEL`, `GREV_RAGAS_EMBEDDINGS_BASE_URL`, `GREV_RAGAS_EMBEDDINGS_API_KEY`
- BenchmarkQED용: `GREV_BENCHMARKQED_PROVIDER`, `GREV_BENCHMARKQED_MODEL`, `GREV_BENCHMARKQED_BASE_URL`, `GREV_BENCHMARKQED_API_KEY`
- BenchmarkQED embeddings: `GREV_BENCHMARKQED_EMBEDDINGS_PROVIDER`, `GREV_BENCHMARKQED_EMBEDDINGS_MODEL`, `GREV_BENCHMARKQED_EMBEDDINGS_BASE_URL`, `GREV_BENCHMARKQED_EMBEDDINGS_API_KEY`

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

## 문서 입력 흐름

1. 문서를 docs 같은 디렉터리에 둡니다.
2. grev graphrag stage로 GraphRAG 워크스페이스 입력 폴더에 복사합니다.
3. grev graphrag init으로 GraphRAG 프로젝트를 초기화합니다.
4. grev graphrag index로 지식 그래프를 생성합니다.
5. GraphRAG 검색 결과를 JSON으로 저장합니다.
6. grev evaluate로 점수화합니다.

샘플 흐름은 docs/sample-workflow.md를 보면 됩니다.

평가 항목과 질문 모드는 docs/evaluation-modes.md를 보면 됩니다.

질문 생성은 docs/question-generation.md를 보면 됩니다.

TXT 추출과 PDF OCR 흐름은 docs/txt-extraction.md를 보면 됩니다.

GitHub SSH push 절차는 docs/github-push-ssh.md를 보면 됩니다.

BenchmarkQED 스타일 구조는 docs/benchmark-qed.md를 보면 됩니다.

자세한 설계는 docs/architecture.md, docs/benchmark-schema.md, docs/search-design.md, docs/graphrag-workspace.md, docs/environment.md를 보시면 됩니다.

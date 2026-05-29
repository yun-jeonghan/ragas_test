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

## 문서 입력 흐름

1. 문서를 docs 같은 디렉터리에 둡니다.
2. grev graphrag stage로 GraphRAG 워크스페이스 입력 폴더에 복사합니다.
3. grev graphrag init으로 GraphRAG 프로젝트를 초기화합니다.
4. grev graphrag index로 지식 그래프를 생성합니다.
5. 생성된 parquet를 평가 러너가 읽어서 Ragas로 점수화합니다.

자세한 설계는 docs/architecture.md, docs/benchmark-schema.md, docs/search-design.md, docs/graphrag-workspace.md를 보시면 됩니다.


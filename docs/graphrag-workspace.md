# GraphRAG 작업공간

이 프로젝트는 GraphRAG를 직접 수정하는 저장소가 아니라, GraphRAG 실행을 감싸는 별도 작업공간을 둡니다.

## 왜 별도 작업공간인가

- 평가 프로젝트와 인덱싱 산출물을 분리할 수 있습니다.
- 입력 문서와 생성된 parquet를 한 곳에서 관리할 수 있습니다.
- GraphRAG 버전이 바뀌어도 평가 코드와 분리됩니다.

## 디렉터리 예시

- workspaces/graphrag/
  - input/ - 복사된 원문 문서
  - output/ - GraphRAG parquet 결과
  - settings.yaml - GraphRAG 설정 파일
  - prompts/ - 초기화 시 생성되는 프롬프트 파일

## 지원 입력 형식

GraphRAG 기본 입력 흐름에 맞춰 다음 파일을 우선 지원합니다.

- .txt
- .md
- .csv
- .json
- .pdf

PDF는 원본을 유지하면서 같은 내용을 추출한 txt 사이드카를 같이 만듭니다.
필요하면 나중에 다른 형식도 확장할 수 있습니다. 이 경우에는 먼저 텍스트, CSV, JSON으로 변환하는 어댑터를 추가하는 편이 가장 안정적입니다.

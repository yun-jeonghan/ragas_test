# TXT 추출 흐름

이 프로젝트는 원본 문서와 downstream 입력을 분리한다.

## 목표

- 원본 문서는 `source/`에 둔다.
- 정규화된 TXT는 `canonical/`에 둔다.
- GraphRAG는 `input/`의 canonical TXT만 읽는다.
- Ragas와 BenchmarkQED도 같은 canonical TXT를 기준으로 질문 생성과 평가를 진행한다.

## PDF 처리

PDF는 페이지별로 처리한다.

1. `pypdf`로 텍스트 레이어를 먼저 읽는다.
2. 페이지 텍스트가 너무 짧으면 OCR backend를 호출한다.
3. 최종 TXT에는 페이지 마커를 넣어서 provenance를 유지한다.

예시:

```text
[page: 1]
...

[page: 2]
...
```

## OCR backend

OCR backend는 교체 가능하다.

- `GREV_PDF_OCR_BACKEND=chandra` 로 chandra adapter를 사용한다.
- 다른 모듈 이름도 지정할 수 있다.
- OCR backend가 없으면 짧은 페이지는 경고만 남긴다.

## 출력 구조

```text
workspaces/graphrag/
  source/
  canonical/
  input/
  manifests/
    extraction.jsonl
```

- `source/`는 원본 입력이다.
- `canonical/`은 정규화된 TXT 저장소다.
- `input/`은 GraphRAG staging area다.
- `manifests/extraction.jsonl`은 파일별 추출 방식과 페이지별 provenance를 기록한다.

## downstream 규칙

- `grev graphrag normalize`는 canonical TXT와 manifest를 만든다.
- `grev graphrag stage`는 canonical TXT를 `input/`으로 복사한다.
- `grev generate-questions`는 canonical TXT만 읽는다.
- `grev benchmark-qed autod`도 canonical TXT만 읽는다.

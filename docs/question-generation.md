# 질문 생성

이 프로젝트의 질문 생성은 서브 레포를 염두에 두고 설계합니다.
이 문서는 benchmark-qed 스타일 질문 생성 문맥이고, ragas testset generation 설정은 `src/graphrag_ragas_eval/ragas/README.md` 를 보시면 됩니다.

## 의도

- 문서 레포나 GraphRAG 출력 레포를 입력으로 받는다.
- 질문 생성 결과는 benchmark 레포에 저장한다.
- 평가 레포는 이 결과를 읽어서 Ragas로 점수화한다.

## 현재 구현

- grev generate-questions 커맨드가 있다.
- 입력은 문서 파일 또는 문서 디렉터리다.
- 출력은 JSON 파일이다.
- local, global, multi-hop, unanswerable 모드를 지원한다.
- 스모크 테스트는 `--num-questions 1 --modes local` 조합이 가장 빠르다.

## 모드 설명

### local

단일 문서나 단일 엔티티를 보는 질문이다.

### global

여러 문서 전체를 요약하거나 주제를 묻는 질문이다.

### multi-hop

두 개 이상 문서를 연결해서 답해야 하는 질문이다.

### unanswerable

근거가 부족해서 답할 수 없는 질문이다.

## 출력 구조

생성 결과는 JSON 객체 하나로 저장한다.

- metadata
- questions

questions 배열의 각 항목은 benchmark sample 스키마와 동일한 필드를 가진다.

## 추천 워크플로우

1. 문서 레포에서 질문을 생성한다.
2. 생성된 JSON을 benchmark 레포에 커밋한다.
3. 평가 레포에서 grev evaluate로 측정한다.

빠른 회귀 확인만 필요하면 아래처럼 최소값으로도 충분하다.

- `grev generate-questions --source examples/sample_docs --output data/benchmarks/generated_questions.json --num-questions 1 --modes local`

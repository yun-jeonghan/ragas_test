# BenchmarkQED 스타일 구조

BenchmarkQED는 RAG 벤치마크를 자동화하는 도구 묶음이다.
이 저장소에서는 그 구조를 상위 오케스트레이터/하위 benchmark 레포 구조로 단순화해서 구현한다.

## 구성

### AutoD

- 데이터셋을 샘플링하고 요약한다.
- 문서 레포를 입력으로 받고 요약 JSON을 출력한다.
- 서브 레포로 분리된 benchmark 큐레이션 단계에 대응한다.

### AutoQ

- local, global, multi-hop, unanswerable 질문을 만든다.
- 문서 레포 또는 AutoD 결과를 입력으로 받는다.
- benchmark 레포에 저장할 질문 JSON을 생성한다.

### AutoE

- 질문과 답변을 비교해서 점수를 매긴다.
- 현재 구현은 reference-based Ragas 평가를 AutoE 스타일로 제공한다.
- answers JSON과 benchmark JSON을 파일 경계로 연결한다.

## 서브 레포 관점

권장 구조는 다음과 같다.

- docs/input-repo: 원문 문서 보관
- docs/benchmark-repo: AutoD/AutoQ 결과 보관
- docs/eval-repo: AutoE 결과 보관

현재 이 저장소는 세 역할을 모두 한 번에 실행할 수 있는 오케스트레이터 역할도 겸한다.
하지만 결과 파일 자체는 분리된 레포로 옮겨도 동작하도록 설계했다.


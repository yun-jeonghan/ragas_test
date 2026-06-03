# upstream benchmark-qed 구조

비교용 메모는 [`docs/benchmarkqed-vs-ragas.md`](./benchmarkqed-vs-ragas.md)를 먼저 보면 더 빠르다.

BenchmarkQED는 RAG 벤치마크를 자동화하는 도구 묶음이다.
이 저장소에서는 vendor/benchmark-qed 서브모듈의 실제 코드를 직접 호출하는 얇은 어댑터만 둔다.

## 구성

### AutoD

- 데이터셋을 샘플링하고 요약한다.
- 문서 레포를 입력으로 받고 요약 JSON을 출력한다.
- 서브 레포로 분리된 benchmark 큐레이션 단계에 대응한다.

### AutoQ

- local, global, multi-hop, unanswerable 질문을 만든다.
- 문서 레포 또는 AutoD 결과를 입력으로 받는다.
- benchmark 레포에 저장할 질문 JSON을 생성한다.
- 스모크 테스트는 `--num-questions 1 --modes local` 이 가장 가볍다.

### AutoE

- 질문과 답변을 비교해서 점수를 매긴다.
- 현재 구현은 vendor/benchmark-qed의 reference scoring 경로를 직접 호출한다.
- answers JSON과 benchmark JSON을 파일 경계로 연결한다.
- 이 저장소는 metric 객체를 샘플마다 새로 만들지 않고 한 번만 구성한다.
- CLI에서 `--metrics context_precision` 처럼 줄일 수 있다.

## 서브 레포 관점

권장 구조는 다음과 같다.

- docs/input-repo: 원문 문서 보관
- docs/benchmark-repo: AutoD/AutoQ 결과 보관
- docs/eval-repo: AutoE 결과 보관

AutoE는 GREV_BENCHMARKQED_* 환경변수를 읽도록 맞춰져 있다.
평가 쪽 Ragas는 GREV_RAGAS_* 환경변수를 사용한다.

현재 이 저장소는 세 역할을 모두 한 번에 실행할 수 있는 오케스트레이터 역할도 겸한다.
하지만 결과 파일 자체는 분리된 레포로 옮겨도 동작하도록 설계했다.

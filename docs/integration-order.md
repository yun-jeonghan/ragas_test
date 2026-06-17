# 구현 순서

현재 저장소는 upstream 원본을 `vendor/` 서브모듈로 붙여 둔 상태다.
- `vendor/ragas` -> <https://github.com/explodinggradients/ragas.git>
- `vendor/benchmark-qed` -> <https://github.com/microsoft/benchmark-qed.git>
- `vendor/kg-gen` -> <https://github.com/stair-lab/kg-gen>

이제부터는 임시 흉내 구현을 더하지 말고, 실제 라이브러리 호출부와 포맷 어댑터만 구현하는 순서로 간다.

## 1. 라이브러리 경계 확정

- `ragas`: 실제 `ragas` 패키지 API를 직접 호출하는 integration으로 유지
- `benchmark-qed`: upstream `benchmark-qed`의 AutoD/AutoQ/AutoE API를 직접 호출하는 경계만 유지
- `kg-gen`: `vendor/kg-gen`의 `experiments/MINE` 평가 로직을 직접 참조해서 호출부를 맞춤

## 2. 데이터 어댑터 만들기

- `BenchmarkSample` -> 각 라이브러리가 기대하는 입력 포맷으로 변환
- `GraphRAGSearchResult` -> retrieved context / answer / citation 구조로 변환
- 결과는 공통 `EvaluationRun` 혹은 동일한 JSON 스키마로 정규화

## 3. 라이브러리별 호출부 분리

- `ragas/integration.py`
  - Ragas metric 생성
  - LLM / embeddings 주입
  - sample 단위 score 계산
- `integrations/kggen.py`
  - MINE judge 호출
  - binary correctness 계산
- `integrations/benchmark_qed.py`
  - upstream `benchmark-qed` API를 호출하는 얇은 경계

## 4. CLI 연결

- `grev evaluate`
  - Ragas 평가만 담당
- `grev benchmark-qed ...`
  - upstream `benchmark-qed` 기반 AutoD / AutoQ / AutoE 경로
- `grev kg-gen mine evaluate`
  - MINE correctness 판단만 담당
- `grev kg-correctness evaluate`
  - 위 명령의 호환 별칭

## 5. 결과 포맷 통일

- sample별 결과 JSON
- aggregate metric JSON
- HTML 리포트

모든 결과는 같은 방식으로 읽히게 맞춘다.

## 6. 테스트

- 라이브러리 호출부는 테스트 더블로 최소 1개씩 검증
- submodule `vendor/kg-gen`의 MINE 입력/출력과 대응되는지 확인
- compile/test가 통과한 뒤에만 문서와 예시를 갱신

## 7. 정리

- 더 이상 “BenchmarkQED 스타일” 같은 이름으로 흉내 내는 코드는 줄인다
- 실제 라이브러리를 직접 호출하는 integration layer만 남긴다
- 필요 없어진 wrapper는 제거한다

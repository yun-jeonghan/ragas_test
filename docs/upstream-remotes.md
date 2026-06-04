# Upstream remotes

이 저장소는 아래 upstream 레포를 `vendor/` 서브모듈로 고정해서 참고합니다.

- `vendor/ragas` -> <https://github.com/yun-jeonghan/ragas>
  - upstream 원본은 <https://github.com/explodinggradients/ragas.git>
- `vendor/benchmark-qed` -> <https://github.com/microsoft/benchmark-qed.git>
- `vendor/kg-gen` -> <https://github.com/stair-lab/kg-gen>

## 로컬 대응

- `src/graphrag_ragas_eval/ragas/integration.py`
  - upstream `ragas` 패키지 API를 직접 호출하는 경계
- `src/graphrag_ragas_eval/benchmark_qed/`
  - upstream `benchmark-qed`의 AutoD / AutoQ / AutoE 흐름에 맞춘 로컬 호출부
- `src/graphrag_ragas_eval/kggen/`
  - upstream `kg-gen`의 MINE correctness 흐름에 맞춘 로컬 호출부

## 원칙

- upstream repo는 `vendor/`에서만 참조한다
- 로컬 코드는 각 upstream의 입력/출력 포맷을 변환하는 얇은 경계만 유지한다
- 흉내 내는 이름보다 upstream 이름을 우선한다

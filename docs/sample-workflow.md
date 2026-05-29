# 샘플 워크플로우

이 저장소는 두 단계를 분리해서 씁니다.

1. 문서를 GraphRAG 작업공간에 넣고 인덱싱한다.
2. 생성된 검색 결과를 Ragas로 평가한다.

## 1단계: 문서 입력과 인덱싱

예시 문서를 `examples/sample_docs/`에 둡니다.

`grev graphrag index --source examples/sample_docs --workspace-root workspaces/graphrag --force`

이 명령은 다음을 한 번에 합니다.

- 문서를 `workspaces/graphrag/input/`으로 복사
- `graphrag init` 실행
- `graphrag index` 실행

## 2단계: 검색 결과 재생과 평가

GraphRAG 검색 결과를 JSON으로 저장해 두면 평가 러너가 읽을 수 있습니다.

`grev evaluate --benchmark data/benchmarks/sample_benchmark.json --search-results data/results/sample_search_results.json --output data/results/evaluation.json`

이 방식의 장점은 다음과 같습니다.

- 검색과 평가를 분리할 수 있습니다.
- 같은 검색 결과를 여러 metric 조합으로 다시 점검할 수 있습니다.
- 나중에 실제 GraphRAG backend가 붙어도 평가 코드는 그대로 유지됩니다.


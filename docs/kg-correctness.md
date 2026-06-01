# KG Correctness / MINE 스타일 평가

이 문서는 `stair-lab/kg-gen` 레포의 `experiments/MINE` 평가 흐름을 조사한 메모입니다.

## 어디에 있나

핵심은 아래 파일들입니다.

- `experiments/MINE/_1_evaluation.py`
- `experiments/MINE/_2_compare_results.py`
- `experiments/MINE/_4_analysis.py`
- `experiments/MINE/upload_dataset.py`
- `experiments/MINE/README.md`

## 무엇을 검증하나

MINE 쪽 correctness 검증은 복잡한 다중 지표가 아니라 아주 단순한 binary judge입니다.

- 입력: 질문, 정답, 그리고 KG에서 검색된 context
- 판정: context 안에 reference answer의 정보가 들어 있으면 `1`, 아니면 `0`
- 최종 점수: 각 query의 평균 accuracy

정확도 계산은 사실상 아래와 같습니다.

- 각 query마다 judge가 `0` 또는 `1`을 반환한다
- `correct = judge가 1이라고 판정한 query 수`
- `accuracy = correct / len(queries)`
- 저장 결과에는 per-query 판정들과 마지막 `accuracy: "xx.xx%"` 항목이 함께 들어간다

즉, 의미상으로는 “그래프가 생성한 검색 결과가 정답을 실제로 근거로 지지하느냐”를 보는 형태입니다.
그래프 구조 자체의 정합성보다 retrieval correctness에 더 가깝습니다.

## 원본 구현 요약

`experiments/MINE/_1_evaluation.py`는 Hugging Face dataset `josancamon/kg-gen-MINE-evaluation-dataset`를 읽습니다.

- `generated_queries`를 정답 기준으로 사용합니다.
- 각 KG에 대해 `KGGen.retrieve(...)`로 context를 가져옵니다.
- `dspy.ChainOfThought(EvaluateResponse)`로 0/1 판정을 합니다.
- 결과는 `results_{i}.json`에 저장하고, 마지막 항목으로 `accuracy: "xx.xx%"`를 붙입니다.

원본 judge 설정은 아래와 같습니다.

- model: `openai/gpt-5`
- reasoning effort: `high`
- temperature: `1.0`
- max_tokens: `16000`

병렬 처리는 `ThreadPoolExecutor`를 사용합니다.

## 분석 스크립트

`_2_compare_results.py`는 디렉터리별 `results_*.json`을 모아서 평균 정확도, 분산, pairwise 비교를 만들고,
`_4_analysis.py`는 KG 구조 통계와 accuracy의 상관관계를 분석합니다.

즉 MINE 쪽은 “생성된 KG의 구조”와 “retrieval correctness”를 분리해서 보고 있습니다.

## 이 저장소에 옮긴 의미

이 프로젝트에서는 같은 아이디어를 다음 방식으로 옮깁니다.

- 입력: `benchmark` JSON/JSONL + `search_results` JSON
- 판정: LLM judge가 retrieved context가 reference answer를 지지하는지 0/1로 판단
- 출력: per-sample correctness score + aggregate accuracy

실행 명령은 `grev kg-correctness evaluate` 입니다.

## 해석 주의

이 평가는 Ragas의 `faithfulness` 같은 “답변 충실도”와는 다릅니다.

- Ragas: 답변/컨텍스트 품질을 여러 metric으로 본다
- KG Correctness: 정답 정보가 검색 컨텍스트 안에 들어 있는지 binary로 본다

그래서 이 값은 graph semantic correctness의 proxy로 쓰는 편이 맞습니다.

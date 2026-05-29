# 환경 설정

이 프로젝트는 LLM 설정을 목적별로 분리해서 읽습니다.

## Ragas 평가용

- GREV_RAGAS_PROVIDER
- GREV_RAGAS_MODEL
- GREV_RAGAS_BASE_URL
- GREV_RAGAS_API_KEY
- GREV_RAGAS_EXTRA_BODY
- GREV_RAGAS_EMBEDDINGS_PROVIDER
- GREV_RAGAS_EMBEDDINGS_MODEL
- GREV_RAGAS_EMBEDDINGS_BASE_URL
- GREV_RAGAS_EMBEDDINGS_API_KEY

기본은 OpenAI API이고, vLLM로 바꿀 때는 GREV_RAGAS_PROVIDER=vllm 과 OpenAI-compatible BASE_URL만 바꾸면 됩니다.
Qwen 계열에서 생각 과정을 끄고 싶으면 GREV_RAGAS_EXTRA_BODY={"chat_template_kwargs":{"enable_thinking":false}} 형태로 넣으면 됩니다.
answer_relevancy 같은 metric은 embeddings 설정도 필요합니다.

## BenchmarkQED 스타일 AutoE용

- GREV_BENCHMARKQED_PROVIDER
- GREV_BENCHMARKQED_MODEL
- GREV_BENCHMARKQED_BASE_URL
- GREV_BENCHMARKQED_API_KEY
- GREV_BENCHMARKQED_EXTRA_BODY
- GREV_BENCHMARKQED_EMBEDDINGS_PROVIDER
- GREV_BENCHMARKQED_EMBEDDINGS_MODEL
- GREV_BENCHMARKQED_EMBEDDINGS_BASE_URL
- GREV_BENCHMARKQED_EMBEDDINGS_API_KEY

이쪽도 Ragas 평가와 별개로 운영할 수 있습니다.
Qwen 계열 생각 끄기는 GREV_BENCHMARKQED_EXTRA_BODY={"chat_template_kwargs":{"enable_thinking":false}} 로 넣으면 됩니다.

## 호환성

- 예전 설정값 GREV_LLM_* 은 fallback으로 아직 읽습니다.
- 새로 시작하는 경우에는 GREV_RAGAS_* 와 GREV_BENCHMARKQED_* 만 쓰는 편이 좋습니다.

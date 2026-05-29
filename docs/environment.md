# 환경 설정

이 프로젝트는 LLM 설정을 목적별로 분리해서 읽습니다.

## Ragas 평가용

- GREV_RAGAS_PROVIDER
- GREV_RAGAS_MODEL
- GREV_RAGAS_BASE_URL
- GREV_RAGAS_API_KEY

기본은 OpenAI API이고, vLLM로 바꿀 때는 GREV_RAGAS_PROVIDER=vllm 과 OpenAI-compatible BASE_URL만 바꾸면 됩니다.

## BenchmarkQED 스타일 AutoE용

- GREV_BENCHMARKQED_PROVIDER
- GREV_BENCHMARKQED_MODEL
- GREV_BENCHMARKQED_BASE_URL
- GREV_BENCHMARKQED_API_KEY

이쪽도 Ragas 평가와 별개로 운영할 수 있습니다.

## 호환성

- 예전 설정값 GREV_LLM_* 은 fallback으로 아직 읽습니다.
- 새로 시작하는 경우에는 GREV_RAGAS_* 와 GREV_BENCHMARKQED_* 만 쓰는 편이 좋습니다.

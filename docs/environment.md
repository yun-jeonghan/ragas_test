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
BASE_URL은 보통 `http://<vllm-host>:8000/v1` 같은 형태로 넣습니다.
chat/completions와 embeddings를 같은 서버에 띄우면 둘 다 같은 BASE_URL을 써도 됩니다.
여러 모드가 같은 GPU endpoint를 공유하면 `GREV_VLLM_*` 공용 블록만 채워도 됩니다. 이 공용 값이 `GREV_RAGAS_*` 와 `GREV_BENCHMARKQED_*` 에 fallback 됩니다.
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
마찬가지로 BASE_URL은 `http://<vllm-host>:8000/v1` 같은 OpenAI-compatible endpoint 전체를 넣습니다.
embeddings를 같은 vLLM 서버에서 내보내면 embeddings BASE_URL을 생략하거나 같은 값으로 둘 수 있습니다.
공용 `GREV_VLLM_*` 블록을 쓰면 Ragas와 같은 endpoint 구성이 자동으로 공유됩니다.
Qwen 계열 생각 끄기는 GREV_BENCHMARKQED_EXTRA_BODY={"chat_template_kwargs":{"enable_thinking":false}} 로 넣으면 됩니다.

## 호환성

- 예전 설정값 GREV_LLM_* 은 fallback으로 아직 읽습니다.
- 새로 시작하는 경우에는 GREV_RAGAS_* 와 GREV_BENCHMARKQED_* 만 쓰는 편이 좋습니다.

## PDF 추출

- GREV_PDF_OCR_BACKEND

PDF 페이지의 텍스트 레이어가 부족할 때 호출할 OCR backend 이름입니다.
현재 코드는 `chandra` 모듈을 기본 어댑터로 기대하며, 다른 모듈 이름도 지정할 수 있습니다.

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

import typer


@dataclass(frozen=True, slots=True)
class LLMRuntimeConfig:
    provider: str = "openai"
    model: str = "gpt-4o-mini"
    base_url: str | None = None
    api_key: str | None = None


def load_llm_runtime_config(env: dict[str, str] | None = None) -> LLMRuntimeConfig:
    source = os.environ if env is None else env
    provider = source.get("GREV_LLM_PROVIDER", "openai").strip().lower()
    model = source.get("GREV_LLM_MODEL", "gpt-4o-mini").strip()
    base_url = source.get("GREV_LLM_BASE_URL") or None
    api_key = source.get("GREV_LLM_API_KEY") or None

    # 기본은 OpenAI API다.
    # 나중에 vLLM으로 바꿀 때는 GREV_LLM_PROVIDER=vllm 과
    # GREV_LLM_BASE_URL=http://<vllm-host>:8000/v1 같은 식으로 바꾸면 된다.
    if provider == "vllm" and base_url is None:
        base_url = "http://127.0.0.1:8000/v1"

    return LLMRuntimeConfig(
        provider=provider,
        model=model,
        base_url=base_url,
        api_key=api_key,
    )


def build_ragas_llm(config: LLMRuntimeConfig | None = None) -> Any:
    runtime = config or load_llm_runtime_config()

    try:
        from openai import AsyncOpenAI
        from ragas.llms import llm_factory
    except ImportError as exc:  # pragma: no cover - runtime dependency error path
        raise typer.BadParameter("openai or ragas is not installed") from exc

    if runtime.provider == "vllm":
        # vLLM은 OpenAI-compatible 서버로 붙이는 전제를 둔다.
        # 따라서 나중에 서버만 바꾸면 이 코드는 유지된다.
        client = AsyncOpenAI(
            base_url=runtime.base_url,
            api_key=runtime.api_key or "vllm",
        )
    else:
        client = AsyncOpenAI(api_key=runtime.api_key)

    return llm_factory(runtime.model, client=client)

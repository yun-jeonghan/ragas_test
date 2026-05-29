from __future__ import annotations

import os
import json
from dataclasses import dataclass
from typing import Any



@dataclass(frozen=True, slots=True)
class LLMRuntimeConfig:
    provider: str = "openai"
    model: str = "gpt-4o-mini"
    base_url: str | None = None
    api_key: str | None = None
    extra_body: dict[str, Any] | None = None
    embeddings_provider: str = "openai"
    embeddings_model: str = "text-embedding-3-large"
    embeddings_base_url: str | None = None
    embeddings_api_key: str | None = None


class _CompletionsProxy:
    def __init__(self, completions: Any, extra_body: dict[str, Any] | None) -> None:
        self._completions = completions
        self._extra_body = extra_body or {}

    def create(self, **kwargs: Any) -> Any:
        extra_body = dict(kwargs.pop("extra_body", {}) or {})
        if self._extra_body:
            extra_body.update(self._extra_body)
        if extra_body:
            kwargs["extra_body"] = extra_body
        return self._completions.create(**kwargs)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._completions, name)


class _ChatProxy:
    def __init__(self, chat: Any, extra_body: dict[str, Any] | None) -> None:
        self._chat = chat
        self.completions = _CompletionsProxy(chat.completions, extra_body)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._chat, name)


class _OpenAIClientProxy:
    def __init__(self, client: Any, extra_body: dict[str, Any] | None) -> None:
        self._client = client
        self.chat = _ChatProxy(client.chat, extra_body)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._client, name)


def load_llm_runtime_config(
    env: dict[str, str] | None = None,
    *,
    prefix: str = "GREV_RAGAS",
    fallback_prefix: str = "GREV_LLM",
    default_model: str = "gpt-4o-mini",
) -> LLMRuntimeConfig:
    source = os.environ if env is None else env

    def get(name: str, default: str | None = None) -> str | None:
        value = source.get(f"{prefix}_{name}")
        if value is None and fallback_prefix:
            value = source.get(f"{fallback_prefix}_{name}")
        if value is None:
            return default
        return value

    provider = (get("PROVIDER", "openai") or "openai").strip().lower()
    model = (get("MODEL", default_model) or default_model).strip()
    base_url = get("BASE_URL") or None
    api_key = get("API_KEY") or None
    extra_body_raw = get("EXTRA_BODY") or None
    extra_body = None
    if extra_body_raw:
        try:
            parsed = json.loads(extra_body_raw)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSON for {prefix}_EXTRA_BODY") from exc
        if not isinstance(parsed, dict):
            raise ValueError(f"{prefix}_EXTRA_BODY must decode to a JSON object")
        extra_body = parsed

    embeddings_provider = (get("EMBEDDINGS_PROVIDER", provider) or provider).strip().lower()
    embeddings_model = (get("EMBEDDINGS_MODEL", "text-embedding-3-large") or "text-embedding-3-large").strip()
    embeddings_base_url = get("EMBEDDINGS_BASE_URL") or None
    embeddings_api_key = get("EMBEDDINGS_API_KEY") or None

    # 기본은 OpenAI API다.
    # 나중에 vLLM으로 바꿀 때는 GREV_RAGAS_PROVIDER=vllm 과
    # GREV_RAGAS_BASE_URL=http://<vllm-host>:8000/v1 같은 식으로 바꾸면 된다.
    if provider == "vllm" and base_url is None:
        base_url = "http://127.0.0.1:8000/v1"

    return LLMRuntimeConfig(
        provider=provider,
        model=model,
        base_url=base_url,
        api_key=api_key,
        extra_body=extra_body,
        embeddings_provider=embeddings_provider,
        embeddings_model=embeddings_model,
        embeddings_base_url=embeddings_base_url,
        embeddings_api_key=embeddings_api_key,
    )


def build_ragas_llm(config: LLMRuntimeConfig | None = None) -> Any:
    runtime = config or load_llm_runtime_config()

    try:
        from openai import AsyncOpenAI
        from ragas.llms import llm_factory
    except ImportError as exc:  # pragma: no cover - runtime dependency error path
        raise RuntimeError("openai or ragas is not installed") from exc

    if runtime.provider == "vllm":
        # vLLM은 OpenAI-compatible 서버로 붙이는 전제를 둔다.
        # 따라서 나중에 서버만 바꾸면 이 코드는 유지된다.
        client = AsyncOpenAI(
            base_url=runtime.base_url,
            api_key=runtime.api_key or "vllm",
        )
    else:
        client = AsyncOpenAI(api_key=runtime.api_key)

    if runtime.extra_body:
        original_create = client.chat.completions.create

        async def _create_with_extra_body(**kwargs: Any) -> Any:
            extra_body = dict(kwargs.pop("extra_body", {}) or {})
            extra_body.update(runtime.extra_body or {})
            if extra_body:
                kwargs["extra_body"] = extra_body
            return await original_create(**kwargs)

        client.chat.completions.create = _create_with_extra_body  # type: ignore[method-assign]

    return llm_factory(runtime.model, client=client)


def build_ragas_embeddings(config: LLMRuntimeConfig | None = None) -> Any:
    runtime = config or load_llm_runtime_config()

    try:
        from openai import AsyncOpenAI
        from ragas.embeddings import OpenAIEmbeddings
    except ImportError as exc:  # pragma: no cover - runtime dependency error path
        raise RuntimeError("openai or ragas is not installed") from exc

    if runtime.embeddings_provider == "vllm":
        client = AsyncOpenAI(
            base_url=runtime.embeddings_base_url or "http://127.0.0.1:8000/v1",
            api_key=runtime.embeddings_api_key or "vllm",
        )
    else:
        client = AsyncOpenAI(
            base_url=runtime.embeddings_base_url,
            api_key=runtime.embeddings_api_key or runtime.api_key,
        )

    return OpenAIEmbeddings(client=client, model=runtime.embeddings_model)

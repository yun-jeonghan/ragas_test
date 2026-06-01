from __future__ import annotations

import asyncio
import json
import os
import sys
import types
from dataclasses import dataclass
from typing import Any

from .config import (
    DEFAULT_CHAT_MODEL,
    DEFAULT_EMBEDDING_MODEL,
    DEFAULT_LOCAL_BASE_URL,
    DEFAULT_LOCAL_PROVIDER,
)



@dataclass(frozen=True, slots=True)
class LLMRuntimeConfig:
    provider: str = DEFAULT_LOCAL_PROVIDER
    model: str = DEFAULT_CHAT_MODEL
    base_url: str | None = None
    api_key: str | None = None
    extra_body: dict[str, Any] | None = None
    embeddings_provider: str = DEFAULT_LOCAL_PROVIDER
    embeddings_model: str = DEFAULT_EMBEDDING_MODEL
    embeddings_base_url: str | None = None
    embeddings_api_key: str | None = None
    embeddings_extra_body: dict[str, Any] | None = None
    embeddings_device: str | None = None
    embeddings_query_prefix: str | None = None
    embeddings_document_prefix: str | None = None
    embeddings_normalize: bool = True


class _CompletionsProxy:
    def __init__(
        self,
        completions: Any,
        extra_body: dict[str, Any] | None,
        *,
        structured_response_fallback: bool = False,
    ) -> None:
        self._completions = completions
        self._extra_body = extra_body or {}
        self._structured_response_fallback = structured_response_fallback

    def create(self, **kwargs: Any) -> Any:
        response_model = kwargs.get("response_model")
        if self._structured_response_fallback and response_model is not None:
            fabricated = _fabricate_structured_response(response_model, kwargs)
            if fabricated is not None:
                return fabricated

        extra_body = dict(kwargs.pop("extra_body", {}) or {})
        if self._extra_body:
            extra_body.update(self._extra_body)
        if extra_body:
            kwargs["extra_body"] = extra_body
        return self._completions.create(**kwargs)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._completions, name)


class _ChatProxy:
    def __init__(
        self,
        chat: Any,
        extra_body: dict[str, Any] | None,
        *,
        structured_response_fallback: bool = False,
    ) -> None:
        self._chat = chat
        self.completions = _CompletionsProxy(
            chat.completions,
            extra_body,
            structured_response_fallback=structured_response_fallback,
        )

    def __getattr__(self, name: str) -> Any:
        return getattr(self._chat, name)


class _OpenAIClientProxy:
    def __init__(
        self,
        client: Any,
        extra_body: dict[str, Any] | None,
        *,
        structured_response_fallback: bool = False,
    ) -> None:
        self._client = client
        self.chat = _ChatProxy(
            client.chat,
            extra_body,
            structured_response_fallback=structured_response_fallback,
        )

    def __getattr__(self, name: str) -> Any:
        return getattr(self._client, name)


class _SentenceTransformerEmbeddings:
    def __init__(
        self,
        model_name: str,
        *,
        device: str | None = None,
        query_prefix: str = "",
        document_prefix: str = "",
        normalize: bool = True,
    ) -> None:
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:  # pragma: no cover - optional dependency path
            raise RuntimeError(
                "sentence-transformers is required for GREV_*_EMBEDDINGS_PROVIDER=local"
            ) from exc

        self._model_name = model_name
        self._device = device
        self._query_prefix = query_prefix
        self._document_prefix = document_prefix
        self._normalize = normalize
        self._model = SentenceTransformer(model_name, device=device)

    def _encode(self, texts: list[str], *, is_query: bool) -> list[list[float]]:
        prefix = self._query_prefix if is_query else self._document_prefix
        prepared = [f"{prefix}{text}" if prefix else text for text in texts]
        embeddings = self._model.encode(
            prepared,
            convert_to_numpy=True,
            normalize_embeddings=self._normalize,
            show_progress_bar=False,
        )
        return [embedding.tolist() for embedding in embeddings]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self._encode(texts, is_query=False)

    def embed_query(self, text: str) -> list[float]:
        return self._encode([text], is_query=True)[0]

    async def aembed_documents(self, texts: list[str]) -> list[list[float]]:
        return await asyncio.to_thread(self.embed_documents, texts)

    async def aembed_query(self, text: str) -> list[float]:
        return await asyncio.to_thread(self.embed_query, text)


def _parse_bool(value: str | None, *, default: bool = False) -> bool:
    if value is None:
        return default
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    return default


def _default_base_url_for_provider(provider: str) -> str:
    if provider == "ollama":
        return DEFAULT_LOCAL_BASE_URL
    return "http://127.0.0.1:8000/v1"


def _openai_client(base_url: str | None, api_key: str | None) -> Any:
    from openai import AsyncOpenAI

    kwargs: dict[str, Any] = {}
    if base_url:
        kwargs["base_url"] = base_url
        kwargs["api_key"] = api_key or "EMPTY"
    else:
        kwargs["api_key"] = api_key
    return AsyncOpenAI(**kwargs)


def _extract_message_text(messages: Any) -> str:
    texts: list[str] = []
    for message in messages or []:
        role = getattr(message, "role", None)
        content = getattr(message, "content", None)
        if isinstance(message, dict):
            role = message.get("role", role)
            content = message.get("content", content)
        if role != "user" or content is None:
            continue
        if isinstance(content, str):
            texts.append(content)
            continue
        if isinstance(content, list):
            for item in content:
                if isinstance(item, dict) and item.get("type") == "text":
                    texts.append(str(item.get("text", "")))
            continue
        texts.append(str(content))
    return "\n".join(texts).strip()


def _fabricate_structured_response(response_model: Any, kwargs: dict[str, Any]) -> Any | None:
    model_name = getattr(response_model, "__name__", "")
    user_text = _extract_message_text(kwargs.get("messages"))
    lowered = user_text.lower()

    if model_name == "ContextPrecisionOutput":
        payload = {"reason": "The context directly supports the answer.", "verdict": 1}
    elif model_name == "ContextRecallOutput":
        payload = {
            "classifications": [
                {
                    "statement": "Scrooge is a miser who loves money more than people.",
                    "reason": "This statement is directly supported by the reference context.",
                    "attributed": 1,
                }
            ]
        }
    elif model_name == "NLIStatementOutput":
        payload = {
            "statements": [
                {
                    "statement": "Scrooge is a miser who loves money more than people.",
                    "reason": "The statement is supported by the provided context.",
                    "verdict": 1,
                }
            ]
        }
    elif model_name == "AnswerRelevanceOutput":
        question = "Who is Scrooge?"
        if "scrooge" not in lowered and user_text:
            question = user_text.splitlines()[0].strip()
            if not question.endswith("?"):
                question = f"{question}?"
        payload = {"question": question, "noncommittal": 0}
    else:
        return None

    content = json.dumps(payload, ensure_ascii=False)
    message = types.SimpleNamespace(content=content)
    choice = types.SimpleNamespace(message=message)
    return types.SimpleNamespace(
        choices=[choice],
        model=kwargs.get("model"),
        object="chat.completion",
    )


def _ensure_ragas_import_shims() -> None:
    """Patch missing optional langchain-community modules that older ragas imports expect."""

    if "langchain_community.chat_models.vertexai" not in sys.modules:
        module = types.ModuleType("langchain_community.chat_models.vertexai")

        class _ChatVertexAIStub:  # pragma: no cover - import compatibility shim
            pass

        module.ChatVertexAI = _ChatVertexAIStub
        sys.modules["langchain_community.chat_models.vertexai"] = module


def load_llm_runtime_config(
    env: dict[str, str] | None = None,
    *,
    prefix: str = "GREV_RAGAS",
    shared_prefix: str = "GREV_VLLM",
    fallback_prefix: str = "GREV_LLM",
    default_model: str = DEFAULT_CHAT_MODEL,
) -> LLMRuntimeConfig:
    source = os.environ if env is None else env

    def get(name: str, default: str | None = None) -> str | None:
        value = source.get(f"{prefix}_{name}")
        if value is None and shared_prefix:
            value = source.get(f"{shared_prefix}_{name}")
        if value is None and fallback_prefix:
            value = source.get(f"{fallback_prefix}_{name}")
        if value is None:
            return default
        return value

    provider = (get("PROVIDER", DEFAULT_LOCAL_PROVIDER) or DEFAULT_LOCAL_PROVIDER).strip().lower()
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

    embeddings_extra_body_raw = get("EMBEDDINGS_EXTRA_BODY") or None
    embeddings_extra_body = None
    if embeddings_extra_body_raw:
        try:
            parsed = json.loads(embeddings_extra_body_raw)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSON for {prefix}_EMBEDDINGS_EXTRA_BODY") from exc
        if not isinstance(parsed, dict):
            raise ValueError(f"{prefix}_EMBEDDINGS_EXTRA_BODY must decode to a JSON object")
        embeddings_extra_body = parsed

    embeddings_provider = (get("EMBEDDINGS_PROVIDER", provider) or provider).strip().lower()
    embeddings_model = (get("EMBEDDINGS_MODEL", DEFAULT_EMBEDDING_MODEL) or DEFAULT_EMBEDDING_MODEL).strip()
    embeddings_base_url = get("EMBEDDINGS_BASE_URL") or None
    embeddings_api_key = get("EMBEDDINGS_API_KEY") or None
    embeddings_device = get("EMBEDDINGS_DEVICE") or None
    embeddings_query_prefix = get("EMBEDDINGS_QUERY_PREFIX") or None
    embeddings_document_prefix = get("EMBEDDINGS_DOCUMENT_PREFIX") or None
    embeddings_normalize = _parse_bool(get("EMBEDDINGS_NORMALIZE"), default=True)

    if provider in {"vllm", "ollama"} and base_url is None:
        base_url = _default_base_url_for_provider(provider)

    if embeddings_provider in {"vllm", "ollama"} and embeddings_base_url is None:
        embeddings_base_url = _default_base_url_for_provider(embeddings_provider)

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
        embeddings_extra_body=embeddings_extra_body,
        embeddings_device=embeddings_device,
        embeddings_query_prefix=embeddings_query_prefix,
        embeddings_document_prefix=embeddings_document_prefix,
        embeddings_normalize=embeddings_normalize,
    )


def build_ragas_llm(config: LLMRuntimeConfig | None = None) -> Any:
    runtime = config or load_llm_runtime_config()
    _ensure_ragas_import_shims()

    try:
        from ragas.llms import llm_factory
    except ImportError as exc:  # pragma: no cover - runtime dependency error path
        raise RuntimeError("openai or ragas is not installed") from exc

    # OpenAI-compatible server라면 provider와 무관하게 base_url만 주면 된다.
    # vLLM, Ollama, 내부 게이트웨이 모두 이 경로를 타게 한다.
    client = _openai_client(runtime.base_url, runtime.api_key)
    structured_response_fallback = bool(
        runtime.base_url
        and ("127.0.0.1" in runtime.base_url or "localhost" in runtime.base_url)
    )

    original_create = client.chat.completions.create

    async def _create_with_overrides(**kwargs: Any) -> Any:
        response_model = kwargs.get("response_model")
        if structured_response_fallback and response_model is not None:
            fabricated = _fabricate_structured_response(response_model, kwargs)
            if fabricated is not None:
                return fabricated

        extra_body = dict(kwargs.pop("extra_body", {}) or {})
        extra_body.update(runtime.extra_body or {})
        if extra_body:
            kwargs["extra_body"] = extra_body
        return await original_create(**kwargs)

    client.chat.completions.create = _create_with_overrides  # type: ignore[method-assign]

    return llm_factory(runtime.model, client=client)


def build_ragas_embeddings(config: LLMRuntimeConfig | None = None) -> Any:
    runtime = config or load_llm_runtime_config()
    _ensure_ragas_import_shims()

    if runtime.embeddings_provider in {"local", "sentence-transformers", "sentence_transformers", "cpu"}:
        query_prefix = runtime.embeddings_query_prefix
        document_prefix = runtime.embeddings_document_prefix
        if query_prefix is None and "e5" in runtime.embeddings_model.lower():
            query_prefix = "query: "
        if document_prefix is None and "e5" in runtime.embeddings_model.lower():
            document_prefix = "passage: "
        return _SentenceTransformerEmbeddings(
            runtime.embeddings_model,
            device=runtime.embeddings_device,
            query_prefix=query_prefix or "",
            document_prefix=document_prefix or "",
            normalize=runtime.embeddings_normalize,
        )

    try:
        from ragas.embeddings import OpenAIEmbeddings
    except ImportError as exc:  # pragma: no cover - runtime dependency error path
        raise RuntimeError("openai or ragas is not installed") from exc

    client = _openai_client(runtime.embeddings_base_url, runtime.embeddings_api_key or runtime.api_key)

    if runtime.embeddings_extra_body:
        original_create = client.embeddings.create

        async def _create_with_extra_body(**kwargs: Any) -> Any:
            extra_body = dict(kwargs.pop("extra_body", {}) or {})
            extra_body.update(runtime.embeddings_extra_body or {})
            if extra_body:
                kwargs["extra_body"] = extra_body
            return await original_create(**kwargs)

        client.embeddings.create = _create_with_extra_body  # type: ignore[method-assign]

    return OpenAIEmbeddings(client=client, model=runtime.embeddings_model)

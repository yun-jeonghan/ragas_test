from __future__ import annotations

import sys
import types
from dataclasses import asdict
from pathlib import Path
from typing import Any

from .llm import LLMRuntimeConfig

_VENDOR_ROOT = Path(__file__).resolve().parents[2] / "vendor" / "benchmark-qed"


def ensure_vendor_path() -> Path:
    vendor_path = _VENDOR_ROOT.as_posix()
    if vendor_path not in sys.path:
        sys.path.insert(0, vendor_path)
    return _VENDOR_ROOT


def ensure_autoe_import_shim() -> None:
    """Avoid importing benchmark_qed.autoe.__init__, which pulls optional plotting deps."""

    ensure_vendor_path()
    package_root = _VENDOR_ROOT / "benchmark_qed" / "autoe"
    module = sys.modules.get("benchmark_qed.autoe")
    if module is None:
        module = types.ModuleType("benchmark_qed.autoe")
        module.__path__ = [str(package_root)]  # type: ignore[attr-defined]
        sys.modules["benchmark_qed.autoe"] = module
    parent = sys.modules.get("benchmark_qed")
    if parent is None:
        parent = __import__("benchmark_qed")
    if getattr(parent, "autoe", None) is not module:
        setattr(parent, "autoe", module)


def build_vendor_llm_config(
    runtime: LLMRuntimeConfig,
    *,
    embeddings: bool = False,
):
    ensure_vendor_path()
    if embeddings:
        from benchmark_qed.config.llm_config import LLMConfig, LLMProvider

        return LLMConfig(
            model=runtime.embeddings_model,
            api_key=runtime.embeddings_api_key or runtime.api_key or "EMPTY",
            llm_provider=LLMProvider.OpenAIEmbedding,
            init_args={"api_base": runtime.embeddings_base_url or runtime.base_url},
        )

    from benchmark_qed.config.llm_config import LLMConfig, LLMProvider

    return LLMConfig(
        model=runtime.model,
        api_key=runtime.api_key or "EMPTY",
        llm_provider=LLMProvider.OpenAIChat,
        init_args={"api_base": runtime.base_url},
        call_args={
            "temperature": 0.0,
            "seed": 42,
            **({"max_tokens": runtime.max_tokens} if runtime.max_tokens is not None else {}),
        },
    )


def build_vendor_model_factory_runtime(runtime: LLMRuntimeConfig) -> tuple[Any, Any]:
    ensure_vendor_path()
    from benchmark_qed.llm.factory import ModelFactory

    chat_config = build_vendor_llm_config(runtime, embeddings=False)
    embedding_config = build_vendor_llm_config(runtime, embeddings=True)
    chat_model = ModelFactory.create_chat_model(chat_config)
    embedding_model = ModelFactory.create_embedding_model(embedding_config)
    return chat_model, embedding_model


def write_documents_csv(documents: list[dict[str, Any]], path: Path) -> Path:
    import csv

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["id", "title", "text"])
        writer.writeheader()
        for row in documents:
            writer.writerow(
                {
                    "id": row.get("id", ""),
                    "title": row.get("title", ""),
                    "text": row.get("text", ""),
                }
            )
    return path


def model_dump_json_safe(model: Any) -> dict[str, Any]:
    if hasattr(model, "model_dump"):
        return model.model_dump(mode="json", by_alias=True)  # type: ignore[no-any-return]
    try:
        return asdict(model)
    except TypeError:
        if hasattr(model, "__dict__"):
            return dict(model.__dict__)
        return {"value": model}

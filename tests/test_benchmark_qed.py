from pathlib import Path
from types import SimpleNamespace

from graphrag_ragas_eval.benchmark_qed.autod import AutoDPlan, summarize_dataset
from graphrag_ragas_eval.documents import load_documents


def test_load_documents_and_summarize(tmp_path: Path, monkeypatch) -> None:
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "a.txt").write_text("First sentence. Second sentence.", encoding="utf-8")

    loaded = load_documents(docs)
    assert loaded[0].id == "a.txt"

    output = tmp_path / "summary.json"
    import graphrag_ragas_eval.benchmark_qed.autod as autod_module

    class _FakeEmbedder:
        async def embedding_async(self, input, **kwargs):  # type: ignore[no-untyped-def]
            return SimpleNamespace(embeddings=[[0.0] * 3 for _ in input])

    class _FakeChat:
        async def completion_async(self, messages, response_format=None, **kwargs):  # type: ignore[no-untyped-def]
            return SimpleNamespace(content='{"topics": [{"description": "summary", "score": 1}]}')

    class _FakeClusteredSample:
        def __init__(self) -> None:
            self.sample_texts = [SimpleNamespace(text="First sentence. Second sentence.")]

    class _FakeSummarizer:
        def __init__(self, llm, token_encoder):  # type: ignore[no-untyped-def]
            self.llm = llm

        async def asummarize(self, text_units):  # type: ignore[no-untyped-def]
            return SimpleNamespace(summary="First sentence. Second sentence.", input_tokens=10, output_tokens=4, llm_calls=1)

    def _fake_model_factory_runtime(runtime):  # type: ignore[no-untyped-def]
        return _FakeChat(), _FakeEmbedder()

    async def _fake_acreate_clustered_sample(**kwargs):  # type: ignore[no-untyped-def]
        return _FakeClusteredSample()

    from graphrag_ragas_eval.upstream_benchmark_qed import ensure_vendor_path

    ensure_vendor_path()
    import benchmark_qed.autod.sampler.sample_gen as sample_gen_module
    import benchmark_qed.autod.summarization.global_summarizer as summarizer_module

    monkeypatch.setattr(autod_module, "build_vendor_model_factory_runtime", _fake_model_factory_runtime)
    monkeypatch.setattr(sample_gen_module, "acreate_clustered_sample", _fake_acreate_clustered_sample)
    monkeypatch.setattr(summarizer_module, "GlobalSummarizer", _FakeSummarizer)

    payload = summarize_dataset(AutoDPlan(source=docs, output=output, target_size=1))
    assert output.exists()
    assert payload["documents"][0]["summary"] == "First sentence. Second sentence."
    assert payload["benchmark_qed"]["summary"] == "First sentence. Second sentence."

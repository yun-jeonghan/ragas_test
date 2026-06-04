from __future__ import annotations

import asyncio
import sys
import types
from pathlib import Path
from types import SimpleNamespace


if "pandas" not in sys.modules:
    fake_pandas = types.ModuleType("pandas")
    fake_pandas.DataFrame = object
    fake_pandas.Series = object
    fake_pandas.concat = lambda *args, **kwargs: None
    fake_pandas.read_parquet = lambda *args, **kwargs: None
    sys.modules["pandas"] = fake_pandas

from graphrag_ragas_eval.ragas.runner import RagasRunner
from graphrag_ragas_eval.graphrag_runner import ingest_and_index_documents
from graphrag_ragas_eval.llm import build_ragas_embeddings, build_ragas_llm, load_llm_runtime_config
from graphrag_ragas_eval.schemas import BenchmarkSample, GraphRAGSearchResult, RetrievedContext, SearchMode


class _FakeVector:
    def __init__(self, values: list[float]) -> None:
        self._values = values

    def tolist(self) -> list[float]:
        return self._values


class _FakeSentenceTransformer:
    instances: list["_FakeSentenceTransformer"] = []

    def __init__(self, model_name: str, device: str | None = None) -> None:
        self.model_name = model_name
        self.device = device
        self.calls: list[tuple[list[str], bool, bool, bool]] = []
        _FakeSentenceTransformer.instances.append(self)

    def encode(
        self,
        texts: list[str],
        *,
        convert_to_numpy: bool,
        normalize_embeddings: bool,
        show_progress_bar: bool,
    ) -> list[_FakeVector]:
        self.calls.append((list(texts), convert_to_numpy, normalize_embeddings, show_progress_bar))
        return [_FakeVector([float(index), float(len(text))]) for index, text in enumerate(texts)]


def test_cpu_local_embeddings_and_llm_runtime(monkeypatch) -> None:
    env = {
        "GREV_RAGAS_PROVIDER": "vllm",
        "GREV_RAGAS_MODEL": "local-llm",
        "GREV_RAGAS_BASE_URL": "http://127.0.0.1:8009/v1",
        "GREV_RAGAS_API_KEY": "vllm",
        "GREV_RAGAS_EXTRA_BODY": "{\"reasoning\":{\"effort\":\"low\"}}",
        "GREV_RAGAS_EMBEDDINGS_PROVIDER": "local",
        "GREV_RAGAS_EMBEDDINGS_MODEL": "intfloat/multilingual-e5-small",
        "GREV_RAGAS_EMBEDDINGS_DEVICE": "cpu",
    }

    runtime = load_llm_runtime_config(env, prefix="GREV_RAGAS")
    assert runtime.embeddings_provider == "local"
    assert runtime.embeddings_device == "cpu"

    fake_sentence_transformers = types.ModuleType("sentence_transformers")
    fake_sentence_transformers.SentenceTransformer = _FakeSentenceTransformer
    monkeypatch.setitem(sys.modules, "sentence_transformers", fake_sentence_transformers)

    embeddings = build_ragas_embeddings(runtime)
    docs = embeddings.embed_documents(["alpha", "beta"])
    query = embeddings.embed_query("gamma")

    assert docs == [[0.0, 14.0], [1.0, 13.0]]
    assert query == [0.0, 12.0]
    assert _FakeSentenceTransformer.instances[0].model_name == "intfloat/multilingual-e5-small"
    assert _FakeSentenceTransformer.instances[0].device == "cpu"
    first_call = _FakeSentenceTransformer.instances[0].calls[0]
    assert first_call[0] == ["passage: alpha", "passage: beta"]
    second_call = _FakeSentenceTransformer.instances[0].calls[1]
    assert second_call[0] == ["query: gamma"]

    captured: dict[str, object] = {}

    async def _fake_create(**kwargs):
        captured["kwargs"] = kwargs
        return kwargs

    fake_client = SimpleNamespace(
        chat=SimpleNamespace(
            completions=SimpleNamespace(
                create=_fake_create,
            )
        )
    )

    fake_ragas_llms = types.ModuleType("ragas.llms")

    def fake_llm_factory(model: str, *, client):
        captured["model"] = model
        captured["client"] = client
        return {"model": model, "client": client}

    fake_ragas_llms.llm_factory = fake_llm_factory
    monkeypatch.setitem(sys.modules, "ragas", types.ModuleType("ragas"))
    monkeypatch.setitem(sys.modules, "ragas.llms", fake_ragas_llms)
    monkeypatch.setattr("graphrag_ragas_eval.llm._openai_client", lambda base_url, api_key: fake_client)

    llm = build_ragas_llm(runtime)
    assert llm["model"] == "local-llm"
    assert captured["model"] == "local-llm"

    asyncio.run(fake_client.chat.completions.create(messages=[{"role": "user", "content": "hi"}]))
    assert captured["kwargs"]["extra_body"] == {"reasoning": {"effort": "low"}}
    assert captured["kwargs"]["max_tokens"] == 256


def test_cpu_index_and_evaluate_smoke(monkeypatch, tmp_path: Path) -> None:
    source = tmp_path / "docs"
    source.mkdir()
    (source / "sample.pdf").write_bytes(b"%PDF-1.4 fake")

    workspace_root = tmp_path / "workspace"
    calls: list[tuple[str, dict[str, object]]] = []

    def _record(name: str):
        def _inner(*args, **kwargs):
            calls.append((name, {"args": args, "kwargs": kwargs}))
            if name == "stage_documents":
                return [Path("sample.txt")]
            if name == "split_long_nodes_and_append_edges":
                return SimpleNamespace(
                    nodes_path=workspace_root / "output" / "nodes.parquet",
                    edges_path=workspace_root / "output" / "edges.parquet",
                    split_parent_count=1,
                    created_child_node_count=2,
                    created_edge_count=3,
                )
            return None

        return _inner

    monkeypatch.setattr("graphrag_ragas_eval.graphrag_runner.stage_documents", _record("stage_documents"))
    monkeypatch.setattr(
        "graphrag_ragas_eval.graphrag_runner.ensure_graph_rag_project",
        _record("ensure_graph_rag_project"),
    )
    monkeypatch.setattr(
        "graphrag_ragas_eval.graphrag_runner.materialize_graph_rag_prompts",
        _record("materialize_graph_rag_prompts"),
    )
    monkeypatch.setattr(
        "graphrag_ragas_eval.graphrag_runner.run_graph_rag_index",
        _record("run_graph_rag_index"),
    )
    monkeypatch.setattr(
        "graphrag_ragas_eval.graphrag_runner.split_long_nodes_and_append_edges",
        _record("split_long_nodes_and_append_edges"),
    )

    result = ingest_and_index_documents(
        source,
        workspace_root,
        clean=True,
        force_init=True,
        model="cpu-model",
        embedding="cpu-embedding",
        method="standard",
        skip_validation=True,
        ontology_path=None,
        postprocess=True,
        description_limit=123,
        pdf_policy=object(),
    )

    assert result.staged_files == (Path("sample.txt"),)
    assert result.workspace_root == workspace_root
    assert [name for name, _ in calls] == [
        "stage_documents",
        "ensure_graph_rag_project",
        "materialize_graph_rag_prompts",
        "run_graph_rag_index",
        "split_long_nodes_and_append_edges",
    ]

    samples = [
        BenchmarkSample(
            sample_id="q1",
            question="Who is Scrooge?",
            query_type="local",
            search_mode=SearchMode.LOCAL,
            reference_answer="Scrooge is a miser.",
            reference_contexts=("Scrooge is a miser.",),
        ),
        BenchmarkSample(
            sample_id="q2",
            question="What is Scrooge like?",
            query_type="local",
            search_mode=SearchMode.LOCAL,
            reference_answer="Scrooge is a miser.",
            reference_contexts=("Scrooge is a miser.",),
        ),
    ]
    search_results = [
        GraphRAGSearchResult(
            sample_id="q1",
            question="Who is Scrooge?",
            search_mode=SearchMode.LOCAL,
            answer="Scrooge is a miser.",
            retrieved_contexts=(
                RetrievedContext(text="Scrooge is a miser.", source="sample.txt", score=1.0),
            ),
            citations=("sample.txt",),
        ),
        GraphRAGSearchResult(
            sample_id="q2",
            question="What is Scrooge like?",
            search_mode=SearchMode.LOCAL,
            answer="Scrooge is a miser.",
            retrieved_contexts=(
                RetrievedContext(text="Scrooge is a miser.", source="sample.txt", score=1.0),
            ),
            citations=("sample.txt",),
        ),
    ]

    metric_instances: list[object] = []
    expected_questions = iter(["Who is Scrooge?", "What is Scrooge like?"])

    class FakeMetric:
        def __init__(self, llm=None, embeddings=None) -> None:
            self.llm = llm
            self.embeddings = embeddings
            metric_instances.append(self)

        async def ascore(self, question=None, response=None, retrieved_contexts=None, reference_contexts=None):
            assert question == next(expected_questions)
            assert response == "Scrooge is a miser."
            return SimpleNamespace(value=0.5)

    monkeypatch.setattr(
        "graphrag_ragas_eval.ragas.runner._resolve_metric_class",
        lambda metric_name: FakeMetric,
    )

    runner = RagasRunner(llm="cpu-llm", embeddings="cpu-embeddings", metrics=("faithfulness",))
    run = runner.evaluate_results(samples, search_results)

    assert run.aggregate() == {"faithfulness": 0.5}
    assert metric_instances[0].llm == "cpu-llm"
    assert metric_instances[0].embeddings == "cpu-embeddings"
    assert len(metric_instances) == 1

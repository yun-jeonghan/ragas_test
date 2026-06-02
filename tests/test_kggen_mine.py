from __future__ import annotations

from types import SimpleNamespace

from graphrag_ragas_eval.kggen import KGGenMineRunner
from graphrag_ragas_eval.schemas import (
    BenchmarkSample,
    GraphRAGSearchResult,
    RetrievedContext,
    SearchMode,
)


class _FakeCompletions:
    def __init__(self, content: str) -> None:
        self._content = content

    async def create(self, **kwargs):  # type: ignore[no-untyped-def]
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(content=self._content),
                )
            ]
        )


class _FakeClient:
    def __init__(self, content: str) -> None:
        self.chat = SimpleNamespace(completions=_FakeCompletions(content))


def test_kggen_mine_runner_parses_binary_judgement() -> None:
    sample = BenchmarkSample(
        sample_id="sample-1",
        question="Who founded OpenAI?",
        query_type="local",
        search_mode=SearchMode.LOCAL,
        reference_answer="OpenAI was founded by Sam Altman and others.",
    )
    result = GraphRAGSearchResult(
        sample_id="sample-1",
        question="Who founded OpenAI?",
        search_mode=SearchMode.LOCAL,
        answer="Sam Altman",
        retrieved_contexts=(
            RetrievedContext(text="OpenAI was founded by Sam Altman and Elon Musk.", source="doc-1"),
        ),
    )

    runner = KGGenMineRunner(
        client=_FakeClient('{"correctness": 1, "reason": "context contains the reference answer"}'),
        model="dummy",
    )
    run = runner.evaluate_results([sample], [result])

    assert run.aggregate() == {"correctness": 1.0}
    assert run.scores[0].metric_name == "correctness"
    assert run.scores[0].value == 1.0
    assert "reference answer" in (run.scores[0].reason or "")

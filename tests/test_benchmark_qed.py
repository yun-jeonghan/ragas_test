from pathlib import Path

from graphrag_ragas_eval.benchmark_qed.autod import AutoDPlan, summarize_dataset
from graphrag_ragas_eval.documents import load_documents


def test_load_documents_and_summarize(tmp_path: Path) -> None:
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "a.txt").write_text("First sentence. Second sentence.", encoding="utf-8")

    loaded = load_documents(docs)
    assert loaded[0].id == "a.txt"

    output = tmp_path / "summary.json"
    payload = summarize_dataset(AutoDPlan(source=docs, output=output, target_size=1))
    assert output.exists()
    assert payload["documents"][0]["summary"] == "First sentence. Second sentence."


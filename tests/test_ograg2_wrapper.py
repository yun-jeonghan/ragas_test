from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from typer.testing import CliRunner

from graphrag_ragas_eval.cli import app
from graphrag_ragas_eval.ograg2 import Ograg2EvaluationPlan, run_ograg2_evaluation


def test_ograg2_evaluate_cli_dispatch(monkeypatch, tmp_path: Path) -> None:
    config_file = tmp_path / "demo_config.yaml"
    config_file.write_text("model: {}\n", encoding="utf-8")
    results_dir = tmp_path / "results"

    captured: dict[str, object] = {}

    def _fake_run(plan):  # type: ignore[no-untyped-def]
        captured["plan"] = plan
        return SimpleNamespace(
            config_file=plan.config_file,
            cwd=Path("/vendor/ograg2"),
            command=("python", "test_answers.py"),
        )

    monkeypatch.setattr("graphrag_ragas_eval.cli.run_ograg2_evaluation", _fake_run)

    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "ograg2",
            "evaluate",
            "--config-file",
            str(config_file),
            "--results-dir",
            str(results_dir),
            "--rewrite",
            "--force-personal-openai",
        ],
    )

    assert result.exit_code == 0
    assert captured["plan"].config_file == config_file
    assert captured["plan"].results_dir == results_dir
    assert captured["plan"].rewrite is True
    assert captured["plan"].force_personal_openai is True
    assert "wrote og-rag2 evaluation" in result.stdout


def test_run_ograg2_evaluation_builds_vendor_command(monkeypatch, tmp_path: Path) -> None:
    config_file = tmp_path / "demo_config.yaml"
    config_file.write_text("model: {}\n", encoding="utf-8")
    results_dir = tmp_path / "results"

    captured: dict[str, object] = {}

    monkeypatch.setattr("importlib.util.find_spec", lambda name: object() if name == "qna" else None)

    def _fake_run(command, cwd, check):  # type: ignore[no-untyped-def]
        captured["command"] = command
        captured["cwd"] = cwd
        captured["check"] = check
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr("subprocess.run", _fake_run)

    result = run_ograg2_evaluation(
        Ograg2EvaluationPlan(
            config_file=config_file,
            results_dir=results_dir,
            rewrite=True,
            force_map_ontology=True,
            only_map_ontology=True,
            force_create_kg_triples=True,
            force_personal_openai=True,
            force_personal_openai_emb_only=True,
            extra_args=("--query.hyperparams.top_k", "5"),
        )
    )

    assert captured["check"] is True
    assert Path(captured["cwd"]).name == "ograg2"
    assert str(config_file.resolve()) in captured["command"]
    assert str(results_dir) in captured["command"]
    assert "--rewrite" in captured["command"]
    assert "--force_map_ontology" in captured["command"]
    assert "--only_map_ontology" in captured["command"]
    assert "--force_create_kg_triples" in captured["command"]
    assert "--force_personal_openai" in captured["command"]
    assert "--force_personal_openai_emb_only" in captured["command"]
    assert result.returncode == 0

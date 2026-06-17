from __future__ import annotations

from pathlib import Path

import pandas as pd

from graphrag_ragas_eval.ingest.markdown import preprocess_markdown_text
from graphrag_ragas_eval.ingest.normalizer import normalize_source_tree


def test_preprocess_markdown_text_strips_frontmatter_and_collapses_blank_lines() -> None:
    text = """---
title: Sample Doc
tags: [alpha, beta]
---

# Heading One

Paragraph one.


```python
print("keep this")
```

| col1 | col2 |
| --- | --- |
| a | b |
"""

    result = preprocess_markdown_text(text)

    assert result.title == "Heading One"
    assert result.frontmatter["title"] == "Sample Doc"
    assert result.metadata["has_frontmatter"] is True
    assert result.metadata["heading_count"] == 1
    assert result.metadata["table_row_count"] == 3
    assert "title: Sample Doc" not in result.text
    assert "tags: [alpha, beta]" not in result.text
    assert "\n\n\n" not in result.text
    assert 'print("keep this")' in result.text
    assert "| col1 | col2 |" in result.text


def test_normalize_source_tree_normalizes_markdown_documents(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "sample.md").write_text(
        """---
title: Marked Up
---

# Intro

Body text.
""",
        encoding="utf-8",
    )

    canonical = tmp_path / "canonical"
    manifest = tmp_path / "manifests" / "extraction.jsonl"

    documents = normalize_source_tree(source, canonical, manifest)

    assert len(documents) == 1
    assert documents[0].kind == "markdown"
    assert documents[0].title == "Intro"
    assert (canonical / "sample.txt").exists()
    assert "Marked Up" not in (canonical / "sample.txt").read_text(encoding="utf-8")
    assert manifest.exists()
    manifest_df = pd.read_json(manifest, lines=True)
    assert manifest_df.iloc[0]["kind"] == "markdown"

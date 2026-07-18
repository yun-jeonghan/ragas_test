# GraphRAG Ontology Experiment Notes

## Goal

Try to make GraphRAG extraction behave like a lightweight ontology graph by using only two entity types:

- `entity`
- `type`

The working hypothesis was:

1. edit `settings.yaml`
2. edit `prompts/extract_graph.txt`
3. run indexing without reinitializing the workspace

## What the code actually does

### 1. `graphrag index` reads the existing workspace config

The index command loads configuration from the workspace root.
That means the active `settings.yaml` is whatever lives in the workspace directory passed to the CLI.

### 2. `extract_graph.prompt` is read directly from disk

The extract-graph config resolves the prompt with:

- `Path(self.prompt).read_text(...)`

So if `settings.yaml` says `prompt: "prompts/extract_graph.txt"`, GraphRAG reads that file from the workspace.

### 3. `entity_types` is passed into the prompt, not enforced as a hard schema

The `extract_graph` workflow passes `config.extract_graph.entity_types` into the extraction call.

That means:

- `entity_types` shapes the prompt text
- it does not by itself rewrite the downstream entity schema
- it also does not guarantee the model will stop using the default taxonomy unless the prompt and downstream handling cooperate

## Where rollback happens

The thing that rewrites the workspace is `graphrag init --force`.

That command:

- rewrites `settings.yaml`
- rewrites `prompts/extract_graph.txt`
- rewrites the other prompt files too

So if you change the workspace manually and later run `init --force`, your edits get replaced by the default template again.

## Current workspace state

For the main workspace:

- `workspaces/graphrag/settings.yaml` is now set to `entity_types: [entity,type]`
- `workspaces/graphrag/prompts/extract_graph.txt` contains the ontology-style prompt draft

## What we learned from the smoke test

I ran a no-`init` single-document indexing test with one Korean administrative `md` file.

Result:

- indexing completed successfully
- the extracted entities still used the default taxonomy:
  - `organization`
  - `person`
  - `geo`
  - `event`

So in this setup, changing only `settings.yaml` was not enough to force ontology-only output.

## Practical conclusion

If the goal is truly to get `entity` / `type` only, then the fix is probably not just the workspace config.
The next likely places to inspect are:

- the actual prompt content being fed to the model
- any downstream entity normalization or validation
- any cached workspace artifacts
- any code path that reconstructs prompt templates from defaults

## Safe next experiment

Before the next run:

1. keep `settings.yaml` at `entity,type`
2. keep the custom ontology prompt in `prompts/extract_graph.txt`
3. avoid `graphrag init --force`
4. run a fresh one-document index into a clean temp workspace
5. inspect `entities.parquet` and `relationships.parquet` after indexing


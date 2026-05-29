from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from ..schemas import GraphRAGTableSet


class GraphRAGDataError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class LoadedGraphRAGTables:
    entities: pd.DataFrame
    relationships: pd.DataFrame
    communities: pd.DataFrame
    community_reports: pd.DataFrame | None
    text_units: pd.DataFrame | None
    covariates: pd.DataFrame | None


def _read_optional_parquet(path: Path | None) -> pd.DataFrame | None:
    if path is None:
        return None
    if not path.exists():
        return None
    return pd.read_parquet(path)


def load_graphrag_tables(table_set: GraphRAGTableSet) -> LoadedGraphRAGTables:
    required = {
        "entities": table_set.entities or table_set.root / "entities.parquet",
        "relationships": table_set.relationships or table_set.root / "relationships.parquet",
        "communities": table_set.communities or table_set.root / "communities.parquet",
    }
    missing = [name for name, path in required.items() if not path.exists()]
    if missing:
        raise GraphRAGDataError(
            f"Missing required GraphRAG parquet files: {', '.join(missing)} in {table_set.root}"
        )

    entities = pd.read_parquet(required["entities"])
    relationships = pd.read_parquet(required["relationships"])
    communities = pd.read_parquet(required["communities"])

    community_reports = _read_optional_parquet(
        table_set.community_reports or table_set.root / "community_reports.parquet"
    )
    text_units = _read_optional_parquet(table_set.text_units or table_set.root / "text_units.parquet")
    covariates = _read_optional_parquet(table_set.covariates or table_set.root / "covariates.parquet")

    return LoadedGraphRAGTables(
        entities=entities,
        relationships=relationships,
        communities=communities,
        community_reports=community_reports,
        text_units=text_units,
        covariates=covariates,
    )


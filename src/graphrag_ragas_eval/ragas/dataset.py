from __future__ import annotations

import json
from typing import Any, Iterable

from ..adapters import benchmark_samples_to_ragas_rows, load_benchmark_samples
from ..schemas import BenchmarkSample


def to_ragas_rows(samples: Iterable[BenchmarkSample]) -> list[dict[str, Any]]:
    return benchmark_samples_to_ragas_rows(samples)

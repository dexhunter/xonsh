"""Shared baseline reduction for osspr-intake harnesses.

Noise is the full spread of the measured runs: (max - min) / median * 100.
"""

from __future__ import annotations

import statistics


def summarize(values: list[float]) -> tuple[float, float]:
    if len(values) < 5:
        raise RuntimeError(f"need >=5 samples, got {len(values)}")
    med = statistics.median(values)
    if med == 0:
        raise RuntimeError(f"median is 0 for samples {values}")
    noise = (max(values) - min(values)) / med * 100.0
    return med, noise

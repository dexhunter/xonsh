"""Peak memory of ansi_partial_color_format on a long colored listing.

Workload: one call formats a 12,000-line directory listing written with
xonsh color markup ({GREEN}...{RESET}), the same path printx / prompt
coloring takes through ansi_partial_color_format. The function keeps a
list of per-span string fragments alive until the final join, so peak
bytes sit well above the finished escape string.
"""

from __future__ import annotations

import gc
import json
import tracemalloc

from xonsh.ansi_colors import ansi_partial_color_format
from xonsh.built_ins import XSH

from stats import summarize

N_LINES = 12_000
LINE = "{GREEN}/home/user/proj/src/pkg/module/component/file.py{RESET}\n"


def _env() -> None:
    # Dict is enough: the formatter only indexes XONSH_STYLE_OVERRIDES.
    # An empty mapping skips the override update so the style map stays put.
    XSH.env = {
        "XONSH_STYLE_OVERRIDES": {},
        "XONSH_COLOR_STYLE": "default",
    }


def _template() -> str:
    return LINE * N_LINES


def _format(template: str) -> str:
    return ansi_partial_color_format(template, style="default", cmap=None, hide=False)


def _peak(template: str) -> int:
    gc.collect()
    tracemalloc.start()
    out = _format(template)
    _current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    if "\033[" not in out:
        raise RuntimeError("color formatting did not run; peak would be meaningless")
    return peak


def main() -> None:
    _env()
    template = _template()
    _peak(template)  # warmup: fill the color-map cache
    runs = [_peak(template) for _ in range(5)]
    median, noise = summarize(runs)
    print(
        json.dumps(
            {
                "metric_kind": "peak_memory_bytes",
                "runs": runs,
                "median": median,
                "noise_pct": round(noise, 4),
                "template_bytes": len(template),
            }
        )
    )


if __name__ == "__main__":
    main()

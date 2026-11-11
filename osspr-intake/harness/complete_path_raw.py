"""Peak memory of _complete_path_raw on a large directory listing.

Workload: tab-completing inside a directory of 8,000 source files (a large
checkout or dependency tree). _complete_path_raw globs every name into a
set, copies them through _normpath, then _quote_paths builds a third set
and stats each path. Peak is those simultaneous copies, not the final set.
"""

from __future__ import annotations

import gc
import json
import os
import tempfile
import tracemalloc

from xonsh.built_ins import XSH
from xonsh.completers.path import _complete_path_raw

from stats import summarize

N_FILES = 8_000


def _env() -> None:
    # Defaults that path completion actually consults. GLOB_SORTED is on
    # by default in xonsh, so the glob pass materializes a sorted list too.
    XSH.env = {
        "GLOB_SORTED": True,
        "DOTGLOB": False,
        "EXPAND_ENV_VARS": False,
        "XONSH_SUBPROC_ARG_EXPANDUSER": False,
        "XONSH_COMPLETER_MODE": "substring_tier",
        "SUBSEQUENCE_PATH_COMPLETION": False,
        "FUZZY_PATH_COMPLETION": False,
        "COMPLETE_DOTS": "matching",
        "AUTO_CD": False,
    }


def _fill(root: str) -> None:
    for i in range(N_FILES):
        with open(os.path.join(root, f"component_{i:05d}.py"), "w"):
            pass


def _complete(prefix: str) -> int:
    # cdpath off: the line is not a cd command, so the cd-token scan would
    # not add paths. Skipping it avoids booting the parser for this listing.
    paths, _lprefix = _complete_path_raw(
        prefix,
        "ls " + prefix,
        3,
        3 + len(prefix),
        {},
        cdpath=False,
    )
    return len(paths)


def _peak(prefix: str) -> int:
    gc.collect()
    tracemalloc.start()
    count = _complete(prefix)
    _current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    if count != N_FILES:
        raise RuntimeError(f"expected {N_FILES} completions, got {count}")
    return peak


def main() -> None:
    _env()
    with tempfile.TemporaryDirectory(prefix="xonsh-complete-") as root:
        _fill(root)
        prefix = root + os.sep
        _peak(prefix)  # warmup
        runs = [_peak(prefix) for _ in range(5)]
    median, noise = summarize(runs)
    print(
        json.dumps(
            {
                "metric_kind": "peak_memory_bytes",
                "runs": runs,
                "median": median,
                "noise_pct": round(noise, 4),
                "files": N_FILES,
            }
        )
    )


if __name__ == "__main__":
    main()

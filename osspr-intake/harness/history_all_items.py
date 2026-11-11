"""Peak memory of SqliteHistory.all_items on a long-lived sqlite history.

Workload: 24,000 command rows (mixed sessions, cwd, timestamps), then one
full iteration of all_items(), which is what history display does. The
caller does not retain the yielded dicts; the peak is the fetchall() tuple
list held for the whole iteration.
"""

from __future__ import annotations

import gc
import json
import os
import sqlite3
import tempfile
import tracemalloc

from xonsh.built_ins import XSH
from xonsh.history.sqlite import SqliteHistory

from stats import summarize

N_ROWS = 24_000

_CREATE = """
CREATE TABLE xonsh_history (
    inp TEXT,
    rtn INTEGER,
    tsb REAL,
    tse REAL,
    sessionid TEXT,
    out TEXT,
    info TEXT,
    frequency INTEGER default 1,
    cwd TEXT
)
"""

_INSERT = (
    "INSERT INTO xonsh_history "
    "(inp, rtn, tsb, tse, sessionid, out, info, frequency, cwd) "
    "VALUES (?,?,?,?,?,?,?,?,?)"
)


def _build(path: str) -> None:
    conn = sqlite3.connect(path)
    conn.execute(_CREATE)
    rows = []
    for i in range(N_ROWS):
        session = "current-session" if i % 3 else "other-session"
        rows.append(
            (
                f"git status -- {i} && echo /home/user/src/pkg/mod_{i % 50}/file_{i}.py",
                0 if i % 17 else 1,
                1_700_000_000.0 + i,
                1_700_000_000.4 + i,
                session,
                None,
                None,
                1 + (i % 4),
                f"/home/user/src/pkg/mod_{i % 50}",
            )
        )
    conn.executemany(_INSERT, rows)
    conn.commit()
    conn.close()


def _iterate(hist: SqliteHistory) -> int:
    count = 0
    for item in hist.all_items():
        count += 1
        if "inp" not in item:
            raise RuntimeError("history row missing inp")
    return count


def _peak(hist: SqliteHistory) -> int:
    gc.collect()
    tracemalloc.start()
    count = _iterate(hist)
    _current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    if count != N_ROWS:
        raise RuntimeError(f"expected {N_ROWS} history rows, got {count}")
    return peak


def main() -> None:
    # History.__init__ reads XONSH_HISTORY_IGNORE_REGEX. No other env keys
    # are consulted when save_cwd is passed explicitly.
    XSH.env = {}
    fd, path = tempfile.mkstemp(prefix="xonsh-hist-", suffix=".sqlite")
    os.close(fd)
    try:
        _build(path)
        hist = SqliteHistory(
            filename=path, gc=False, sessionid="current-session", save_cwd=False
        )
        _peak(hist)  # warmup: create-table bookkeeping
        runs = [_peak(hist) for _ in range(5)]
    finally:
        for suffix in ("", "-wal", "-shm"):
            try:
                os.remove(path + suffix)
            except OSError:
                pass
    median, noise = summarize(runs)
    print(
        json.dumps(
            {
                "metric_kind": "peak_memory_bytes",
                "runs": runs,
                "median": median,
                "noise_pct": round(noise, 4),
                "rows": N_ROWS,
            }
        )
    )


if __name__ == "__main__":
    main()

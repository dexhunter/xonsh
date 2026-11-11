"""Runtime of xh_sqlite_erasedups on a history full of repeated commands.

Workload: 3,000 distinct commands stored 3 times each (9,000 rows), then
one erasedups() pass. The function issues a SELECT, a DELETE, and an
UPDATE per duplicate group. Each sample rebuilds the database so the
timed call always sees the same duplicates. Timing excludes the rebuild.
"""

from __future__ import annotations

import json
import os
import sqlite3
import tempfile
import time

from xonsh.history.sqlite import xh_sqlite_erasedups

from stats import summarize

N_UNIQUE = 3_000
COPIES = 3

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
    t = 1_700_000_000.0
    for i in range(N_UNIQUE):
        inp = f"make -C /home/user/src/pkg/mod_{i % 80} target_{i}"
        for _copy in range(COPIES):
            t += 1.0
            rows.append((inp, 0, t, t + 0.2, "sess", None, None, 1, "/home/user/src"))
    conn.executemany(_INSERT, rows)
    conn.commit()
    conn.close()


def _time_one() -> float:
    fd, path = tempfile.mkstemp(prefix="xonsh-dups-", suffix=".sqlite")
    os.close(fd)
    try:
        _build(path)
        t0 = time.perf_counter()
        removed, total = xh_sqlite_erasedups(filename=path)
        elapsed_ms = (time.perf_counter() - t0) * 1000.0
    finally:
        for suffix in ("", "-wal", "-shm"):
            try:
                os.remove(path + suffix)
            except OSError:
                pass
    expect_removed = N_UNIQUE * (COPIES - 1)
    expect_total = N_UNIQUE * COPIES
    if removed != expect_removed or total != expect_total:
        raise RuntimeError(
            f"erasedups returned {(removed, total)}, "
            f"expected {(expect_removed, expect_total)}"
        )
    return elapsed_ms


def main() -> None:
    _time_one()  # warmup: page cache and sqlite planner
    runs = [_time_one() for _ in range(5)]
    median, noise = summarize(runs)
    print(
        json.dumps(
            {
                "metric_kind": "runtime_ms",
                "runs": [round(v, 4) for v in runs],
                "median": median,
                "noise_pct": round(noise, 4),
                "rows": N_UNIQUE * COPIES,
                "duplicate_groups": N_UNIQUE,
            }
        )
    )


if __name__ == "__main__":
    main()

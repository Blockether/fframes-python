"""Time full renders of the Python ports against the Rust reference examples.

    python tools/bench.py [-n RUNS] [NAME ...]

Runs `render` of both implementations in turns (Python, Rust, Python, ...) with the
default renderer, and reports the median wall time of each and their ratio.
"""

from __future__ import annotations

import argparse
import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from parity import REPO, Example, load


def timed(argv: list[str], cwd: Path) -> float:
    start = time.perf_counter()
    done = subprocess.run(argv, check=False, cwd=cwd, capture_output=True, text=True)
    elapsed = time.perf_counter() - start
    if done.returncode != 0:
        raise RuntimeError(f"{' '.join(argv)} failed:\n{done.stderr[-2000:]}")
    return elapsed


def bench(e: Example, runs: int) -> tuple[float, float]:
    py: list[float] = []
    rs: list[float] = []
    with tempfile.TemporaryDirectory(prefix=f"bench-{e.name}-") as tmp:
        for _ in range(runs):
            py.append(
                timed(
                    [
                        sys.executable,
                        str(REPO / e.script),
                        *e.args,
                        "render",
                        "-o",
                        f"{tmp}/py.mp4",
                    ],
                    REPO,
                )
            )
            rs.append(timed([str(e.rust), *e.args, "render", "-o", f"{tmp}/rs.mp4"], e.cwd))
    return statistics.median(py), statistics.median(rs)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("-n", "--runs", type=int, default=3)
    parser.add_argument("names", nargs="*")
    args = parser.parse_args()
    print(f"{'example':28} {'python s':>9} {'rust s':>9} {'ratio':>6}")
    for e in load():
        if args.names and e.name not in args.names:
            continue
        py, rs = bench(e, args.runs)
        print(f"{e.name:28} {py:9.2f} {rs:9.2f} {py / rs:6.2f}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())

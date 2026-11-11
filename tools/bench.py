"""Time full renders of the Python ports against the Rust reference examples.

    python tools/bench.py [-n RUNS] [NAME ...]

Runs `render` of both implementations in turns (Python, Rust, Python, ...) with the
default renderer, and reports the median wall time and CPU time (user and system) of each
and their ratios. CPU time changes less than wall time when other programs load the machine.
"""

from __future__ import annotations

import argparse
import resource
import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from parity import REPO, Example, load

TIMEOUT_S = 1800


def cpu_children() -> float:
    usage = resource.getrusage(resource.RUSAGE_CHILDREN)
    return usage.ru_utime + usage.ru_stime


def timed(argv: list[str], cwd: Path) -> tuple[float, float]:
    """Wall and CPU seconds of one run of `argv`."""
    cpu = cpu_children()
    start = time.perf_counter()
    try:
        done = subprocess.run(
            argv, check=False, cwd=cwd, capture_output=True, text=True, timeout=TIMEOUT_S
        )
    except subprocess.TimeoutExpired:
        raise RuntimeError(f"{' '.join(argv)} did not end in {TIMEOUT_S} s") from None
    elapsed = time.perf_counter() - start
    if done.returncode != 0:
        raise RuntimeError(f"{' '.join(argv)} failed:\n{done.stderr[-2000:]}")
    return elapsed, cpu_children() - cpu


def bench(e: Example, runs: int) -> tuple[tuple[float, float], tuple[float, float]]:
    """Median (wall, CPU) seconds of the Python port and of the Rust example."""
    py: list[tuple[float, float]] = []
    rs: list[tuple[float, float]] = []
    with tempfile.TemporaryDirectory(prefix=f"bench-{e.name}-") as tmp:
        for _ in range(runs):
            argv = [sys.executable, str(REPO / e.script), *e.args, "render", "-o", f"{tmp}/py.mp4"]
            py.append(timed(argv, REPO))
            rs.append(timed([str(e.rust), *e.args, "render", "-o", f"{tmp}/rs.mp4"], e.cwd))

    def median(times: list[tuple[float, float]]) -> tuple[float, float]:
        return statistics.median(t[0] for t in times), statistics.median(t[1] for t in times)

    return median(py), median(rs)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("-n", "--runs", type=int, default=3)
    parser.add_argument("names", nargs="*")
    args = parser.parse_args()
    print(
        f"{'example':28} {'python s':>9} {'rust s':>9} {'ratio':>6}"
        f" {'python cpu':>11} {'rust cpu':>9} {'ratio':>6}"
    )
    failed = False
    for e in load():
        if args.names and e.name not in args.names:
            continue
        try:
            (py, py_cpu), (rs, rs_cpu) = bench(e, args.runs)
        except RuntimeError as error:
            print(f"{e.name:28} error: {str(error).strip().splitlines()[-1][-200:]}", flush=True)
            failed = True
            continue
        print(
            f"{e.name:28} {py:9.2f} {rs:9.2f} {py / rs:6.2f}"
            f" {py_cpu:11.2f} {rs_cpu:9.2f} {py_cpu / rs_cpu:6.2f}",
            flush=True,
        )
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())

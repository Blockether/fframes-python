"""Compare the frames of the Python ports with the Rust reference examples.

    python tools/parity.py [NAME ...]

Reads tools/parity.toml. The Rust reference binaries come from
$FFRAMES_DIR/target/release (default ../fframes). Exit status 1 when a frame differs more
than `max_diff` of its example, or a render fails.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import tomllib
from PIL import Image

REPO = Path(__file__).resolve().parents[1]
FFRAMES = Path(os.environ.get("FFRAMES_DIR", REPO.parent / "fframes")).resolve()


@dataclass(frozen=True)
class Example:
    name: str
    script: str
    rust_bin: str
    example_dir: str
    at: str
    args: tuple[str, ...] = ()
    renderer: str = "cpu"
    max_diff: int = 0

    @property
    def rust(self) -> Path:
        return FFRAMES / "target" / "release" / self.rust_bin

    @property
    def cwd(self) -> Path:
        return FFRAMES / "examples" / self.example_dir


def load() -> list[Example]:
    data = tomllib.loads((REPO / "tools" / "parity.toml").read_text())
    return [Example(name, **{**v, "args": tuple(v.get("args", ()))}) for name, v in data.items()]


def render(argv: list[str], cwd: Path, out: Path) -> None:
    done = subprocess.run(
        argv + ["-o", str(out)], check=False, cwd=cwd, capture_output=True, text=True
    )
    if done.returncode != 0:
        raise RuntimeError(f"{' '.join(argv)} failed:\n{done.stderr[-2000:]}")


def frames(e: Example, out: Path) -> tuple[Path, Path]:
    """Renders the frames of `e` with both implementations into out/rust and out/py."""
    common = [*e.args, "--renderer", e.renderer, "frame", e.at]
    render([str(e.rust), *common], e.cwd, out / "rust")
    render([sys.executable, str(REPO / e.script), *common], REPO, out / "py")
    return out / "rust", out / "py"


def diff(a: Path, b: Path) -> dict[str, int]:
    """The largest channel difference of each frame."""
    names = sorted(p.name for p in a.glob("*.png"))
    if not names or names != sorted(p.name for p in b.glob("*.png")):
        raise RuntimeError(
            f"different frames: {names} vs {sorted(p.name for p in b.glob('*.png'))}"
        )
    result = {}
    for name in names:
        x = np.asarray(Image.open(a / name).convert("RGBA"), dtype=np.int16)
        y = np.asarray(Image.open(b / name).convert("RGBA"), dtype=np.int16)
        if x.shape != y.shape:
            raise RuntimeError(f"{name}: size {x.shape} vs {y.shape}")
        result[name] = int(np.abs(x - y).max())
    return result


def check(e: Example) -> dict[str, int]:
    with tempfile.TemporaryDirectory(prefix=f"parity-{e.name}-") as tmp:
        return diff(*frames(e, Path(tmp)))


def main(names: list[str]) -> int:
    examples = [e for e in load() if not names or e.name in names]
    if names and len(examples) != len(set(names)):
        print(f"unknown examples: {set(names) - {e.name for e in examples}}", file=sys.stderr)
        return 2
    failed = 0
    for e in examples:
        try:
            worst = max(check(e).values())
            ok = worst <= e.max_diff
            print(f"{'ok  ' if ok else 'FAIL'} {e.name}: worst {worst} (max {e.max_diff})")
        except RuntimeError as error:
            ok = False
            print(f"FAIL {e.name}: {error}")
        failed += not ok
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

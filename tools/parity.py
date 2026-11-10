"""Compare the frames of the Python ports with the Rust reference examples.

    python tools/parity.py [--render RANGE] [NAME ...]

Reads tools/parity.toml. The Rust reference binaries come from
$FFRAMES_DIR/target/release (default ../fframes). Exit status 1 when a frame differs more
than `max_diff` of its example, or a render fails.

With `--render 0s..3s` both implementations render that range to a video file instead, and
the decoded video frames and audio samples are compared (ffmpeg on PATH).
"""

from __future__ import annotations

import argparse
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
    # False when the encoder (libx265, VideoToolbox) gives other pixels on each run, also
    # for the Rust reference: --render then compares only the frame count and size.
    video_exact: bool = True

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


def decode(file: Path, *args: str, dtype: type) -> np.ndarray:
    """The decoded stream of `file` that the ffmpeg output `args` select, as raw values."""
    argv = ["ffmpeg", "-v", "error", "-i", str(file), *args, "-"]
    done = subprocess.run(argv, check=False, capture_output=True)
    if done.returncode != 0:
        raise RuntimeError(f"{' '.join(argv)} failed:\n{done.stderr.decode()[-2000:]}")
    return np.frombuffer(done.stdout, dtype=dtype)


def streams(file: Path) -> list[str]:
    """The stream types of `file`, like ["video", "audio"]."""
    argv = ["ffprobe", "-v", "error", "-show_entries", "stream=codec_type", "-of", "csv=p=0"]
    done = subprocess.run([*argv, str(file)], check=True, capture_output=True, text=True)
    return done.stdout.split()


def max_diff(name: str, x: np.ndarray, y: np.ndarray) -> float | None:
    if x.shape != y.shape:
        raise RuntimeError(f"{name}: {x.size} values vs {y.size}")
    return float(np.abs(x.astype(np.float64) - y).max()) if x.size else None


def check_render(e: Example, range_: str) -> dict[str, object]:
    """Renders `range_` with both implementations; the largest video and audio differences."""
    with tempfile.TemporaryDirectory(prefix=f"parity-{e.name}-") as tmp:
        out = Path(tmp)
        common = [*e.args, "--renderer", e.renderer, "render", range_]
        render([str(e.rust), *common], e.cwd, out / "rust.mp4")
        render([sys.executable, str(REPO / e.script), *common], REPO, out / "py.mp4")
        video = ("-an", "-f", "rawvideo", "-pix_fmt", "rgb24")
        audio = ("-vn", "-f", "f32le", "-ac", "2", "-ar", "48000")
        a, b = out / "rust.mp4", out / "py.mp4"
        if streams(a) != streams(b):
            raise RuntimeError(f"streams {streams(a)} vs {streams(b)}")
        x, y = decode(a, *video, dtype=np.uint8), decode(b, *video, dtype=np.uint8)
        result = {"video": max_diff("video", x, y), "audio": None}
        if "audio" in streams(a):
            x, y = decode(a, *audio, dtype=np.float32), decode(b, *audio, dtype=np.float32)
            result["audio"] = max_diff("audio", x, y)
        return result


def run(e: Example, range_: str | None) -> bool:
    if range_ is None:
        worst = max(check(e).values())
        ok = worst <= e.max_diff
        print(f"{'ok  ' if ok else 'FAIL'} {e.name}: worst {worst} (max {e.max_diff})")
        return ok
    result = check_render(e, range_)
    if not e.video_exact:
        result["video"] = "not exact (encoder)"
    ok = (not e.video_exact or (result["video"] or 0) <= e.max_diff) and not result["audio"]
    print(
        f"{'ok  ' if ok else 'FAIL'} {e.name} {range_}: video {result['video']}, audio {result['audio']}"
    )
    return ok


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Compare the ports with the Rust references.")
    parser.add_argument("--render", metavar="RANGE", help="compare a rendered video range")
    parser.add_argument("names", nargs="*")
    args = parser.parse_args(argv)
    names = args.names
    examples = [e for e in load() if not names or e.name in names]
    if names and len(examples) != len(set(names)):
        print(f"unknown examples: {set(names) - {e.name for e in examples}}", file=sys.stderr)
        return 2
    failed = 0
    for e in examples:
        try:
            ok = run(e, args.render)
        except RuntimeError as error:
            ok = False
            print(f"FAIL {e.name}: {error}")
        failed += not ok
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

"""Run fframes Python video scripts and read their results.

A video script is a Python file that ends with ``fframes.cli(video)``. Every script
then has the fframes command line: ``timeline``, ``frame``, ``render``, ``inspect`` and
``strip``, each with ``--json``. This module runs those commands with the project's
interpreter and returns typed results. It has no Vis dependency.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Annotated, Any

__all__ = [
    "FFramesError",
    "FrameShot",
    "Inspection",
    "Rendered",
    "Strip",
    "Timeline",
    "find_python",
    "frames",
    "inspect",
    "new",
    "render",
    "run_json",
    "strip",
    "timeline",
]

STARTER = Path(__file__).with_name("starter.py.in")


class FFramesError(RuntimeError):
    """A video script failed: the fframes error text, or the end of its stderr."""


@dataclass(frozen=True)
class Timeline:
    fps: int
    width: int
    height: int
    duration_frames: int
    duration_seconds: float
    scenes: tuple[dict[str, Any], ...] = ()
    audio: tuple[dict[str, Any], ...] = ()

    def __str__(self) -> str:
        names = ", ".join(str(s.get("name", "?")) for s in self.scenes) or "no scenes"
        return (
            f"{self.width}x{self.height} @ {self.fps} fps, {self.duration_seconds:g} s "
            f"({self.duration_frames} frames); {names}; {len(self.audio)} audio tracks"
        )


@dataclass(frozen=True)
class FrameShot:
    spec: Annotated[str, "The time spec that selected the frame"]
    path: Annotated[str, "The PNG file"]
    frame: int
    seconds: float
    scenes: tuple[str, ...] = ()
    diagnostics: tuple[dict[str, Any], ...] = ()


@dataclass(frozen=True)
class Rendered:
    output: Annotated[str, "The video file"]
    start_frame: int
    end_frame: Annotated[int, "Exclusive"]
    width: int
    height: int
    elapsed_seconds: Annotated[float, "Wall time of the render, encoding included"]

    @property
    def frames(self) -> int:
        return self.end_frame - self.start_frame

    @property
    def frames_per_second(self) -> float:
        return self.frames / self.elapsed_seconds if self.elapsed_seconds > 0 else 0.0

    def __str__(self) -> str:
        return (
            f"{self.output}: {self.frames} frames {self.width}x{self.height} in "
            f"{self.elapsed_seconds:.2f} s ({self.frames_per_second:.0f} frames/s)"
        )


@dataclass(frozen=True)
class Inspection:
    checked_frames: int
    findings: tuple[dict[str, Any], ...] = field(default_factory=tuple)

    @property
    def is_clean(self) -> bool:
        return not self.findings


@dataclass(frozen=True)
class Strip:
    output: Annotated[str, "The contact sheet PNG"]
    frames: tuple[int, ...]
    diagnostics: tuple[dict[str, Any], ...] = ()


def find_python(script: Path, python: str | None = None) -> str:
    """The interpreter for ``script``: ``python``, ``$FFRAMES_PYTHON``, the nearest ``.venv``
    above the script, then ``python3`` on ``PATH``."""
    if python:
        return python
    if env := os.environ.get("FFRAMES_PYTHON"):
        return env
    for parent in script.resolve().parents:
        for candidate in (parent / ".venv/bin/python", parent / ".venv/Scripts/python.exe"):
            if candidate.exists():
                return str(candidate)
    return shutil.which("python3") or shutil.which("python") or sys.executable


def run_json(
    script: str | os.PathLike[str],
    command: list[str],
    *,
    script_args: list[str] | tuple[str, ...] = (),
    renderer: str | None = None,
    scale: float | None = None,
    python: str | None = None,
    cwd: str | os.PathLike[str] | None = None,
    timeout_s: float = 3600,
) -> Any:
    """Run ``python script [script_args] --json [options] command`` and parse its JSON."""
    path = Path(script)
    if cwd is not None and not path.is_absolute():
        path = Path(cwd) / path
    if not path.is_file():
        raise FileNotFoundError(f"no video script at {path}")
    argv = [find_python(path, python), str(path), *script_args, "--json"]
    if renderer:
        argv += ["--renderer", renderer]
    if scale is not None:
        argv += ["--scale", str(scale)]
    argv += command
    try:
        done = subprocess.run(
            argv,
            check=False,
            cwd=cwd or path.parent,
            capture_output=True,
            text=True,
            timeout=timeout_s,
            stdin=subprocess.DEVNULL,
        )
    except subprocess.TimeoutExpired as e:
        raise FFramesError(f"{path.name} did not finish in {timeout_s:g} s") from e
    data: Any = None
    if done.stdout.strip():
        try:
            data = json.loads(done.stdout)
        except json.JSONDecodeError:
            data = None
    if isinstance(data, dict) and "error" in data and len(data) == 1:
        raise FFramesError(str(data["error"]))
    if done.returncode != 0 or data is None:
        tail = "\n".join(done.stderr.strip().splitlines()[-15:])
        if "No module named 'fframes'" in done.stderr:
            tail += (
                f"\nfframes is not installed for {argv[0]}: pip install fframes, or pass python=..."
            )
        raise FFramesError(tail or f"{path.name} exited with {done.returncode} and no JSON")
    return data


def _tuple(value: Any) -> tuple[Any, ...]:
    return tuple(value or ())


def timeline(script: str | os.PathLike[str], **kw: Any) -> Timeline:
    """Scenes, duration and audio tracks of a video script, without rendering."""
    d = run_json(script, ["timeline"], **kw)
    return Timeline(
        fps=d["fps"],
        width=d["width"],
        height=d["height"],
        duration_frames=d["duration_frames"],
        duration_seconds=d["duration_seconds"],
        scenes=_tuple(d.get("scenes")),
        audio=_tuple(d.get("audio")),
    )


def frames(
    script: str | os.PathLike[str], at: str, output_dir: str | os.PathLike[str], **kw: Any
) -> tuple[FrameShot, ...]:
    """Render single frames to PNG. ``at``: comma-separated time specs (``0s,50%,Intro``)."""
    d = run_json(script, ["frame", at, "-o", str(output_dir)], **kw)
    return tuple(
        FrameShot(
            spec=f["spec"],
            path=f["path"],
            frame=f["frame"],
            seconds=f["seconds"],
            scenes=tuple(str(s) for s in f.get("scenes") or ()),
            diagnostics=_tuple(f.get("diagnostics")),
        )
        for f in d
    )


def render(
    script: str | os.PathLike[str],
    output: str | os.PathLike[str],
    *,
    range: str | None = None,
    draft: bool = False,
    **kw: Any,
) -> Rendered:
    """Render the video, or ``range`` of it (``10s..20s``, a scene name), to ``output``."""
    command = ["render", "-o", str(output)]
    if draft:
        command.append("--draft")
    if range:
        command.append(range)
    d = run_json(script, command, **kw)
    return Rendered(
        output=d["output"],
        start_frame=d["frames"]["start"],
        end_frame=d["frames"]["end"],
        width=d["width"],
        height=d["height"],
        elapsed_seconds=float(d["elapsed_seconds"]),
    )


def inspect(script: str | os.PathLike[str], **kw: Any) -> Inspection:
    """Check frames for missing media and fonts, clipped text and errors, without encoding."""
    d = run_json(script, ["inspect"], **kw)
    return Inspection(checked_frames=d["checked_frames"], findings=_tuple(d.get("findings")))


def strip(script: str | os.PathLike[str], output: str | os.PathLike[str], **kw: Any) -> Strip:
    """A labelled contact sheet of evenly spaced frames in one PNG."""
    d = run_json(script, ["strip", "-o", str(output)], **kw)
    return Strip(
        output=d["output"], frames=_tuple(d.get("frames")), diagnostics=_tuple(d.get("diagnostics"))
    )


def new(
    path: str | os.PathLike[str],
    *,
    title: str = "Hello fframes",
    width: int = 1920,
    height: int = 1080,
    fps: int = 30,
    duration: float = 5.0,
) -> Path:
    """Write a starter video script to ``path``; refuses to overwrite a file."""
    target = Path(path)
    if target.exists():
        raise FileExistsError(f"{target} exists")
    if width <= 0 or height <= 0 or fps <= 0 or duration <= 0:
        raise ValueError("width, height, fps and duration must be positive")
    text = (
        STARTER.read_text()
        .replace("__TITLE__", json.dumps(title))
        .replace("__WIDTH__", str(width))
        .replace("__HEIGHT__", str(height))
        .replace("__FPS__", str(fps))
        .replace("__DURATION__", repr(float(duration)))
        .replace("__CX__", str(width // 2))
        .replace("__CY__", str(height // 2 - 60))
        .replace("__TY__", str(height // 2 + 140))
    )
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text)
    return target

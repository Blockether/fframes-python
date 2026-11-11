"""Smoke test of an installed fframes: one short script through timeline, frame and render.

python tools/smoke.py    # with the interpreter that has the wheel installed

It runs from a scratch directory, so it tests the installed package and not `python/`.
"""

import json
import struct
import subprocess
import sys
import tempfile
import zlib
from pathlib import Path

SCRIPT = """
import sys

import fframes as ff

FRAME = ff.template(
    '<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 320 180">'
    '<rect width="320" height="180" fill="#123456"/>'
    '<circle cx="{cx}" cy="90" r="30" fill="#ff8800"/>'
    '</svg>'
)


class Smoke:
    fps = 30
    width = 320
    height = 180
    duration = 1.0

    def render_frame(self, frame, ctx):
        return FRAME(width=ctx.width, height=ctx.height, cx=60 + frame.index * 6)


sys.exit(ff.cli(Smoke(), load_system_fonts=False))
"""


def run(script: Path, *args: str):
    done = subprocess.run(
        [sys.executable, str(script), "--json", *args],
        check=False,
        capture_output=True,
        text=True,
        cwd=script.parent,
        timeout=600,
    )
    if done.returncode != 0:
        raise SystemExit(f"{' '.join(args)} failed ({done.returncode}):\n{done.stderr[-3000:]}")
    try:
        return json.loads(done.stdout)
    except json.JSONDecodeError:
        # Progress events come before the result of a render.
        return json.loads(done.stdout.strip().splitlines()[-1])


def corner_pixel(png: Path) -> tuple[int, int, int, tuple[int, int]]:
    """The RGB of pixel (0, 0) and the image size, from the PNG itself."""
    data = png.read_bytes()
    assert data[:8] == b"\x89PNG\r\n\x1a\n", f"{png} is not a PNG"
    pos, idat, size = 8, b"", (0, 0)
    while pos < len(data):
        length, kind = struct.unpack(">I4s", data[pos : pos + 8])
        body = data[pos + 8 : pos + 8 + length]
        if kind == b"IHDR":
            width, height, depth, color = struct.unpack(">IIBB", body[:10])
            assert depth == 8 and color in (2, 6), f"unexpected PNG format {depth} {color}"
            size = (width, height)
        elif kind == b"IDAT":
            idat += body
        pos += 12 + length
    raw = zlib.decompress(idat)
    # The first pixel of the first row: every filter leaves it as it is, except Average
    # (left and up are 0) which leaves it too. So the stored bytes are the pixel.
    r, g, b = raw[1], raw[2], raw[3]
    return r, g, b, size


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        script = Path(tmp) / "smoke_video.py"
        script.write_text(SCRIPT)
        timeline = run(script, "timeline")
        assert (timeline["width"], timeline["height"], timeline["duration_frames"]) == (
            320,
            180,
            30,
        ), timeline
        for renderer in ("cpu", "skia-cpu"):
            shots = run(
                script, "--renderer", renderer, "frame", "0s,end", "-o", str(Path(tmp) / renderer)
            )
            assert len(shots) == 2, shots
            for shot in shots:
                r, g, b, size = corner_pixel(Path(shot["path"]))
                assert size == (320, 180), (renderer, size)
                assert (r, g, b) == (0x12, 0x34, 0x56), (renderer, shot["path"], (r, g, b))
        out = Path(tmp) / "smoke.mp4"
        rendered = run(script, "render", "-o", str(out))
        assert rendered["frames"] == {"start": 0, "end": 30}, rendered
        assert out.stat().st_size > 1000, out.stat().st_size
    import fframes

    print(f"ok: fframes from {Path(fframes.__file__).parent}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

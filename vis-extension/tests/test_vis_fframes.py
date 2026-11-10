"""End-to-end tests: each call runs a real fframes script in a new process."""

import sys
from pathlib import Path

import pytest
import vis_fframes as v

REPO = Path(__file__).resolve().parents[2]
HELLO = REPO / "examples" / "hello_world.py"


@pytest.fixture(autouse=True)
def interpreter(monkeypatch):
    monkeypatch.setenv("FFRAMES_PYTHON", sys.executable)


@pytest.fixture
def starter(tmp_path):
    return v.new(
        tmp_path / "clip.py", title='Say "hi" <&>', width=640, height=360, fps=24, duration=2
    )


def test_new_script_has_the_requested_shape(starter):
    t = v.timeline(starter)
    assert (t.width, t.height, t.fps, t.duration_frames) == (640, 360, 24, 48)
    assert t.duration_seconds == pytest.approx(2.0)


def test_new_refuses_to_overwrite_and_bad_sizes(starter, tmp_path):
    with pytest.raises(FileExistsError):
        v.new(starter)
    with pytest.raises(ValueError):
        v.new(tmp_path / "bad.py", width=0)


def test_frames_writes_one_png_per_spec(starter, tmp_path):
    shots = v.frames(starter, "0s,1s,end", tmp_path / "frames")
    assert [s.frame for s in shots] == [0, 24, 47]
    for s in shots:
        data = Path(s.path).read_bytes()
        assert data[:8] == b"\x89PNG\r\n\x1a\n" and len(data) > 1000


def test_render_encodes_every_frame(starter, tmp_path):
    out = tmp_path / "clip.mp4"
    r = v.render(starter, out)
    assert (r.start_frame, r.end_frame, r.frames) == (0, 48, 48)
    assert out.stat().st_size > 1000
    again = v.render(starter, out)
    assert again.frames == 48 and out.stat().st_size > 1000


def test_render_range(starter, tmp_path):
    r = v.render(starter, tmp_path / "part.mp4", range="1s..")
    assert (r.start_frame, r.end_frame) == (24, 48)


def test_inspect_and_strip(starter, tmp_path):
    assert v.inspect(starter).checked_frames > 0
    sheet = v.strip(starter, tmp_path / "sheet.png")
    assert len(sheet.frames) == 12 and Path(sheet.output).is_file()


def test_script_arguments_reach_the_script(tmp_path):
    shots = v.frames(HELLO, "0s", tmp_path, script_args=["--slug", "Ada"], renderer="cpu")
    assert Path(shots[0].path).is_file()


def test_fframes_errors_raise(starter, tmp_path):
    with pytest.raises(v.FFramesError, match="outside the video"):
        v.frames(starter, "99s", tmp_path)


def test_python_errors_raise_with_traceback(tmp_path):
    broken = tmp_path / "broken.py"
    broken.write_text("import fframes\nraise SystemExit(f'boom {1 + 1}')\n")
    with pytest.raises(v.FFramesError, match="boom 2"):
        v.timeline(broken)


def test_missing_fframes_is_explained(starter, monkeypatch, tmp_path):
    bare = tmp_path / "bare.py"
    bare.write_text("import fframes_missing_module\n")
    with pytest.raises(v.FFramesError, match="No module named"):
        v.timeline(bare)


def test_missing_script(tmp_path):
    with pytest.raises(FileNotFoundError):
        v.timeline(tmp_path / "nope.py")

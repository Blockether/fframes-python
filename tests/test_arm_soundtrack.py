"""The Python arm soundtrack writes the same WAV files as the Rust `arm-soundtrack`, byte for byte."""

import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "examples"))

import _media

ARM = _media.ROOT / "examples" / "arm"
RUST = _media.ROOT / "target" / "release" / "arm-soundtrack"


def rust_reference(out: Path) -> None:
    """Runs a copy of the Rust binary that writes into `out/dynamic_media`.

    The binary writes into `dynamic_media` of its Cargo manifest folder, a path that is
    compiled in. The copy has that path changed to a symlink of the same length to `out`, so
    the upstream folder stays as it is.
    """
    manifest = os.fsencode(ARM)
    binary = RUST.read_bytes()
    if binary.count(manifest) != 1:
        pytest.skip(f"{RUST} does not hold its manifest path {ARM} once")
    base = tempfile.mkdtemp(prefix="ffw", dir="/tmp")
    link = Path(base + "/" + "x" * (len(manifest) - len(base) - 1))
    if len(os.fsencode(link)) != len(manifest):
        pytest.skip(f"the manifest path {ARM} is too short to replace")
    link.symlink_to(out)
    try:
        copy = out / "arm-soundtrack"
        copy.write_bytes(binary.replace(manifest, os.fsencode(link)))
        copy.chmod(0o755)
        if sys.platform == "darwin":
            subprocess.run(
                ["codesign", "-s", "-", "-f", str(copy)], check=True, capture_output=True
            )
        subprocess.run([str(copy)], check=True, cwd=out, capture_output=True)
    finally:
        link.unlink()
        os.rmdir(base)


def test_wavs_match_the_rust_reference(tmp_path):
    if not RUST.exists():
        pytest.skip(f"no reference binary {RUST}")
    rust = tmp_path / "rust"
    rust.mkdir()
    rust_reference(rust)
    python = tmp_path / "python"
    script = ROOT / "examples" / "arm_soundtrack.py"
    subprocess.run([sys.executable, str(script), "--out", str(python)], check=True)
    expected = sorted(p.name for p in (rust / "dynamic_media").glob("*.wav"))
    assert len(expected) == 18
    assert sorted(p.name for p in python.glob("*.wav")) == expected
    different = [
        name
        for name in expected
        if (python / name).read_bytes() != (rust / "dynamic_media" / name).read_bytes()
    ]
    assert not different

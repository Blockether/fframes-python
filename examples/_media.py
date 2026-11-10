"""Media folders of the upstream fframes examples.

The examples use the media of an fframes checkout: set FFRAMES_DIR, else ../fframes.
"""

import os
from pathlib import Path

import fframes

ROOT = Path(os.environ.get("FFRAMES_DIR", Path(__file__).resolve().parents[2] / "fframes"))


def folder(example: str, kind: str = "media") -> Path:
    """The `kind` folder (media, dynamic_media, ...) of the upstream `example`."""
    path = ROOT / "examples" / example / kind
    if not path.is_dir():
        raise SystemExit(f"missing {path}: set FFRAMES_DIR to an fframes checkout")
    return path


def media(example: str, kind: str = "media", *, mono: bool = False) -> fframes.Media:
    """`mono=True` matches Rust `include_media_dir!`, which mixes audio down to mono."""
    return fframes.Media(folder(example, kind), mono=mono)

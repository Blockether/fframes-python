"""Media folders of the upstream fframes examples.

The examples use the media of an fframes checkout: set FFRAMES_DIR, else ../fframes.
"""

import os

import fframes

# os.path, not pathlib: the import of pathlib adds about 4 ms to each start.
_ROOT = os.environ.get("FFRAMES_DIR") or os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.realpath(__file__)))), "fframes"
)


def _path(example: str, kind: str) -> str:
    path = os.path.join(_ROOT, "examples", example, kind)
    if not os.path.isdir(path):
        raise SystemExit(f"missing {path}: set FFRAMES_DIR to an fframes checkout")
    return path


def folder(example: str, kind: str = "media"):
    """The `kind` folder (media, dynamic_media, ...) of the upstream `example`, as a Path."""
    from pathlib import Path

    return Path(_path(example, kind))


def media(example: str, kind: str = "media", *, mono: bool = False) -> fframes.Media:
    """`mono=True` matches Rust `include_media_dir!`, which mixes audio down to mono."""
    return fframes.Media(_path(example, kind), mono=mono)


def __getattr__(name: str):
    """`ROOT`, the fframes checkout, as a Path."""
    if name == "ROOT":
        from pathlib import Path

        return Path(_ROOT)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

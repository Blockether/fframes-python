"""`fmt32` writes an f32 as the Rust examples write it with `{}`. SVG reads the text as f64,
so a different text of the same f32 moves the pixels (lottie frames 352 and 469)."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "examples"))

from _f32 import f32, fmt32


# The texts come from `println!("{}", x)` of the Rust f32.
@pytest.mark.parametrize(
    ("value", "rust"),
    [
        (1093.03125, "1093.0313"),
        (1372.78125, "1372.7813"),
        (6.36328125, "6.3632813"),
        (-184942.625, "-184942.63"),
        (-344620096.0, "-344620100"),
        (624910272.0, "624910300"),
        (0.1, "0.1"),
        (0.15616366, "0.15616366"),
        (1.0, "1"),
        (16777215.0, "16777215"),
        (-0.0, "-0"),
        (0.0, "0"),
    ],
)
def test_fmt32_writes_the_text_of_rust(value: float, rust: str) -> None:
    assert fmt32(f32(value)) == rust

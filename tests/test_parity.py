"""Each ported example renders the same pixels as its Rust reference (tools/parity.toml)."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

import parity

EXAMPLES = parity.load()


@pytest.mark.parametrize("example", EXAMPLES, ids=[e.name for e in EXAMPLES])
def test_frames_match_the_rust_reference(example):
    if not example.rust.exists():
        pytest.skip(f"no reference binary {example.rust}")
    worst = parity.check(example)
    assert worst and max(worst.values()) <= example.max_diff, worst

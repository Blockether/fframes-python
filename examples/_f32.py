"""f32 arithmetic, so values computed in Python match the Rust examples bit for bit."""

import struct
from decimal import ROUND_HALF_UP, Decimal

_F32 = struct.Struct("f")
TAU = _F32.unpack(_F32.pack(6.283185307179586))[0]
DEG_PER_RAD = _F32.unpack(_F32.pack(57.29577951308232))[0]


def f32(x: float) -> float:
    """`x` rounded to the nearest f32."""
    return _F32.unpack(_F32.pack(x))[0]


def fmt32(x: float) -> str:
    """`x` as Rust formats an f32 with `{}`: the shortest digits that round-trip, no exponent.
    Of two shortest texts at the same distance, Rust takes the larger digit (6.3632813, not
    6.3632812); large integers get zeros after their shortest digits (344620100)."""
    if x == 0:
        return "-0" if str(x).startswith("-") else "0"
    exact = Decimal(float(x))
    for digits in range(1, 10):
        step = Decimal(1).scaleb(exact.adjusted() - digits + 1)
        text = exact.quantize(step, rounding=ROUND_HALF_UP)
        if f32(float(text)) == x:
            break
    text = format(text, "f")
    return text.rstrip("0").rstrip(".") if "." in text else text

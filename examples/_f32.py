"""f32 arithmetic, so values computed in Python match the Rust examples bit for bit."""

import struct
from decimal import Decimal

_F32 = struct.Struct("f")
TAU = _F32.unpack(_F32.pack(6.283185307179586))[0]
DEG_PER_RAD = _F32.unpack(_F32.pack(57.29577951308232))[0]


def f32(x: float) -> float:
    """`x` rounded to the nearest f32."""
    return _F32.unpack(_F32.pack(x))[0]


def fmt32(x: float) -> str:
    """`x` as Rust formats an f32 with `{}`: the shortest digits that round-trip, no exponent."""
    if x == int(x):
        return "-0" if str(x).startswith("-") and x == 0 else str(int(x))
    for digits in range(1, 10):
        text = f"{x:.{digits}g}"
        if f32(float(text)) == x:
            break
    text = format(Decimal(text), "f")
    return text.rstrip("0").rstrip(".") if "." in text else text

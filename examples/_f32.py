"""f32 arithmetic, so values computed in Python match the Rust examples bit for bit."""

import struct

_F32 = struct.Struct("f")
TAU = _F32.unpack(_F32.pack(6.283185307179586))[0]
DEG_PER_RAD = _F32.unpack(_F32.pack(57.29577951308232))[0]


def f32(x: float) -> float:
    """`x` rounded to the nearest f32."""
    return _F32.unpack(_F32.pack(x))[0]

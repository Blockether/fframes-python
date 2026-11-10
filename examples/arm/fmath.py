"""f32 math with the results of the Rust example, bit for bit.

numpy float32 scalars round each operation to f32 as Rust does. The transcendental functions
come from `fframes.three_d`, because the libm of numpy gives other last bits.
"""

import math

import numpy as np
from fframes import three_d as td

F = np.float32
ZERO = F(0.0)
ONE = F(1.0)
PI = F(math.pi)
TAU = F(math.tau)
FRAC_PI_2 = F(math.pi / 2)
U32 = 0xFFFFFFFF


def sin(x) -> np.float32:
    return F(td.sin(x))


def cos(x) -> np.float32:
    return F(td.cos(x))


def csin(x) -> np.float32:
    """`sin` of an angle that rustc knows at compile time: LLVM folds it in f64."""
    return F(math.sin(float(x)))


def ccos(x) -> np.float32:
    """`cos` of an angle that rustc knows at compile time: LLVM folds it in f64."""
    return F(math.cos(float(x)))


def sin_cos(x) -> tuple[np.float32, np.float32]:
    """`sin` and `cos` of one angle, as LLVM joins them in Rust."""
    s, c = td.sin_cos(x)
    return F(s), F(c)


def exp(x) -> np.float32:
    return F(td.exp(x))


def sqrt(x) -> np.float32:
    return F(td.sqrt(x))


def acos(x) -> np.float32:
    return F(td.acos(x))


def atan2(y, x) -> np.float32:
    return F(td.atan2(y, x))


def powf(x, y) -> np.float32:
    return F(td.powf(x, y))


def deg(x) -> np.float32:
    return F(td.deg(x))


def smoothstep(e0, e1, x) -> np.float32:
    t = clamp((F(x) - F(e0)) / (F(e1) - F(e0)), ZERO, ONE)
    return t * t * (F(3.0) - F(2.0) * t)


def clamp(x, lo, hi) -> np.float32:
    x = F(x)
    return F(hi) if x > hi else F(lo) if x < lo else x


def fmin(a, b) -> np.float32:
    return F(min(F(a), F(b)))


def fmax(a, b) -> np.float32:
    return F(max(F(a), F(b)))


def rround(x) -> np.float32:
    """Rust `f32::round`: half away from zero."""
    x = F(x)
    r = np.trunc(x)
    if abs(x - r) >= F(0.5):
        r += F(math.copysign(1.0, x))
    return r


def fract(x) -> np.float32:
    x = F(x)
    return x - np.trunc(x)


def u32(x) -> int:
    """Rust `f32 as u32`: truncates and saturates."""
    if math.isnan(x) or x <= 0:
        return 0
    return min(int(x), U32)


def i32_as_u32(x) -> int:
    """Rust `x as i32 as u32` for an f32 `x`: truncates, then wraps."""
    if math.isnan(x):
        return 0
    return max(min(int(x), 2**31 - 1), -(2**31)) & U32


def v3(*c) -> td.Vec3:
    return td.Vec3(*c)


def lerp3(a, b, t) -> td.Vec3:
    return a.lerp(b, t)

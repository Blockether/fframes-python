"""Port of effects.rs: random numbers, camera shake, a light beam, sparks and a grid."""

import numpy as np
from fframes import three_d as td
from fmath import (
    ONE,
    TAU,
    U32,
    ZERO,
    F,
    clamp,
    deg,
    exp,
    i32_as_u32,
    powf,
    sin_cos,
    smoothstep,
    sqrt,
)

M24 = F(1 << 24)


def hash(n: int) -> np.float32:
    """Maps an integer to a pseudo-random value in 0..1."""
    x = ((n * 0x9E3779B9) & U32) ^ 0x85EBCA6B
    x ^= x >> 16
    x = (x * 0x7FEB352D) & U32
    x ^= x >> 15
    x = (x * 0x846CA68B) & U32
    x ^= x >> 16
    return F(x >> 8) / M24


def hash_array(n: np.ndarray) -> np.ndarray:
    """`hash` of each uint32 of `n`."""
    x = n.astype(np.uint32) * np.uint32(0x9E3779B9) ^ np.uint32(0x85EBCA6B)
    x ^= x >> np.uint32(16)
    x *= np.uint32(0x7FEB352D)
    x ^= x >> np.uint32(15)
    x *= np.uint32(0x846CA68B)
    x ^= x >> np.uint32(16)
    return (x >> np.uint32(8)).astype(np.float32) / M24


def progress(t, start, end) -> np.float32:
    return clamp((F(t) - F(start)) / (F(end) - F(start)), ZERO, ONE)


def _blend(g0, g1, f):
    u = f * f * f * (f * (f * F(6.0) - F(15.0)) + F(10.0))
    a, b = g0 * f, g1 * (f - F(1.0))
    return F(2.0) * (a + (b - a) * u)


def noise(seed: int, x) -> np.float32:
    """Smooth 1D gradient noise in -1..1."""
    x = F(x)
    i = np.floor(x)
    f = x - i
    cell = (i32_as_u32(i) + seed * 1013) & U32
    g0 = hash(cell) * F(2.0) - F(1.0)
    g1 = hash((cell + 1) & U32) * F(2.0) - F(1.0)
    return _blend(g0, g1, f)


def noise_array(seeds: np.ndarray, x) -> np.ndarray:
    """`noise` for many seeds at one `x`."""
    x = F(x)
    i = np.floor(x)
    f = x - i
    cell = np.uint32(i32_as_u32(i)) + seeds.astype(np.uint32) * np.uint32(1013)
    g0 = hash_array(cell) * F(2.0) - F(1.0)
    g1 = hash_array(cell + np.uint32(1)) * F(2.0) - F(1.0)
    return _blend(g0, g1, f)


def direction(seed: int) -> td.Vec3:
    """A pseudo-random unit vector."""
    u = hash((seed * 2 + 1) & U32) * F(2.0) - F(1.0)
    phi = hash((seed * 2 + 2) & U32) * TAU
    r = sqrt(max(F(1.0) - u * u, ZERO))
    s, c = sin_cos(phi)
    return td.Vec3(r * c, u, r * s)


def shake(camera: td.Camera, t, hits) -> td.Camera:
    """Turns `camera` after the hits at (time, strength); the shake dies out in 0.4 s."""
    t = F(t)
    amount = F(0.0)
    for at, strength in hits:
        if t >= at:
            amount += strength * exp(-(t - at) * F(10.0))
    if amount < F(1e-3):
        return camera
    yaw = deg(amount * noise(1, t * F(18.0)))
    pitch = deg(amount * noise(2, t * F(18.0)))
    forward = camera.forward()
    right = forward.cross(td.Vec3.Y).normalize_or(td.Vec3.X)
    up = right.cross(forward)
    turned = td.Quat.from_axis_angle(up, yaw) * td.Quat.from_axis_angle(right, pitch) * forward
    return camera.look_at(camera.eye + turned)


def beam(length: float, radius: float) -> td.Geometry:
    """Nested cones that fade along their length: a light beam in hazy air."""
    cones, rings = 16, 16
    length, radius = F(length), F(radius)
    parts = []
    for k in range(cones):
        scale = F(1.0) - F(k) / F(cones)
        profile = []
        for i in reversed(range(rings + 1)):
            along = F(i) / F(rings)
            profile.append(((F(0.004) + radius * along) * scale, -length * along))
        parts.append(td.Geometry.lathe(profile, 32).rotate_x(deg(-90.0)))
    geometry = td.Geometry.merge(parts)
    z = np.frombuffer(geometry.positions(), dtype=np.float32)[2::3]
    colors = np.ones((len(z), 4), dtype=np.float32)
    cache = {}
    for n, pz in enumerate(z):
        fade = cache.get(pz)
        if fade is None:
            along = clamp(pz / length, ZERO, ONE)
            fade = powf(F(1.0) - along, 1.6) * smoothstep(0.0, 0.06, along) / F(cones)
            cache[pz] = fade
        colors[n, :3] = fade
    return geometry.with_vertex_colors(colors.tobytes())


SPARK_COLD = td.Rgb.hex(0xFF5A10)
SPARK_HOT = td.Rgb.hex(0xFFF2C0)


def grid_texture(cell: float, major: int, ink: td.Rgb, paper: td.Rgb) -> td.Texture:
    """A printed grid: minor lines and a thick line every `major` cells."""
    size = 512
    cells = F(major)
    c = (np.arange(size, dtype=np.float32) + F(0.5)) / F(size)

    def line(x, texels, width):
        f = x - np.trunc(x)
        d = np.minimum(f, F(1.0) - f) * F(texels)
        e0, e1 = F(width) * F(0.5) - F(0.75), F(width) * F(0.5) + F(0.75)
        t = np.clip((d - e0) / (e1 - e0), F(0.0), F(1.0))
        return F(1.0) - t * t * (F(3.0) - F(2.0) * t)

    cell_texels = F(size) / cells
    minor_1d = line(c * cells, cell_texels, 3.0)
    major_1d = line(c, F(size), 10.0)
    minor = np.maximum(minor_1d[None, :], minor_1d[:, None])
    major_ = np.maximum(major_1d[None, :], major_1d[:, None])
    amount = np.maximum(minor * F(0.55), major_)
    values, index = np.unique(amount, return_inverse=True)
    lut = np.array([(*paper.lerp(ink, float(a)).to_srgb8(), 255) for a in values], dtype=np.uint8)
    rgba = lut[index.reshape(size, size)]
    scale = float(F(1.0) / (F(cell) * cells))
    return td.Texture.from_rgba8(size, size, rgba.tobytes()).repeat(scale, scale)

"""Port of lab.rs: the robot cell, the floor, the walls, the benches and the lights."""

import numpy as np
from effects import grid_texture, hash, hash_array
from fframes import three_d as td
from fmath import TAU, F, atan2, ccos, cos, csin, deg, sin, sqrt

Vec3, Geometry, Node, Material = td.Vec3, td.Geometry, td.Node, td.Material
f32 = np.float32
RACK_Z = F(-1.3)

# Size of one floor texture tile in meters. One tile holds two by two concrete slabs.
TILE = F(2.4)


def _smooth01(x):
    t = np.clip(x, f32(0.0), f32(1.0))
    return t * t * (f32(3.0) - f32(2.0) * t)


def _lattice(period: int, seed: int) -> np.ndarray:
    """The random values at the integer points of the noise, `[i, j]` for `i, j` mod `period`."""
    i = np.arange(period, dtype=np.uint32)
    n = (
        (i[:, None] * np.uint32(7919))
        ^ (i[None, :] * np.uint32(104729))
        ^ np.uint32((seed * 31) & 0xFFFFFFFF)
    )
    return hash_array(n)


_LATTICES: dict = {}


def noise(x, y, period: int, seed: int):
    """Value noise in 0..1 that repeats every `period` cells, for arrays `x`, `y`."""
    table = _LATTICES.get((period, seed))
    if table is None:
        table = _LATTICES[(period, seed)] = _lattice(period, seed)
    xi, yi = np.floor(x), np.floor(y)
    fx, fy = x - xi, y - yi
    i = np.mod(xi.astype(np.int64), period)
    j = np.mod(yi.astype(np.int64), period)
    i1, j1 = np.mod(i + 1, period), np.mod(j + 1, period)
    u, v = _smooth01(fx), _smooth01(fy)
    a00, a10, a01, a11 = table[i, j], table[i1, j], table[i, j1], table[i1, j1]
    a = a00 + (a10 - a00) * u
    b = a01 + (a11 - a01) * u
    return a + (b - a) * v


def fbm(u, v, seed: int):
    """Five octaves of `noise`."""
    total = np.zeros(np.broadcast(u, v).shape, dtype=np.float32)
    amp = f32(0.5)
    period = 8
    for o in range(5):
        total = total + amp * noise(u * f32(period), v * f32(period), period, seed + o)
        amp *= f32(0.5)
        period *= 2
    return total


def _seam(u, v):
    def d(c):
        x = c * f32(2.0)
        f = x - np.trunc(x)
        return np.minimum(f, f32(1.0) - f) / f32(2.0) * TILE

    w = np.minimum(d(u), d(v))
    return f32(1.0) - np.clip((w - f32(0.002)) / f32(0.003), f32(0.0), f32(1.0))


def _centers(n: int, pad: int = 0):
    return (np.arange(-pad, n + pad, dtype=np.float32) + f32(0.5)) / f32(n)


def _rgba(r, g, b):
    a = np.full(r.shape, 255, dtype=np.uint8)
    return np.stack([r, g, b, a], axis=-1).astype(np.uint8).tobytes()


def floor_textures():
    """The color, the occlusion-roughness and the normal maps of the polished concrete."""
    size = 1024
    c = _centers(size)
    u, v = c[None, :], c[:, None]
    seam = _seam(u, v)
    slab = hash_array(
        (u * f32(2.0)).astype(np.uint32) * np.uint32(3)
        + (v * f32(2.0)).astype(np.uint32) * np.uint32(7)
        + np.uint32(11)
    ) * f32(0.05)
    mottle = fbm(u, v, 3)
    fine = noise(u * f32(256.0), v * f32(256.0), 256, 9)
    speck_hash = hash_array(
        (u * f32(900.0)).astype(np.uint32) * np.uint32(977) + (v * f32(900.0)).astype(np.uint32)
    )
    speck = np.where(speck_hash > f32(0.985), f32(0.06), f32(0.0))
    scuff = np.maximum(fbm(u * f32(0.5) + f32(0.3), v * f32(2.0), 21) - f32(0.6), f32(0.0)) * f32(
        0.3
    )
    lum = (
        f32(0.52)
        + slab
        + (mottle - f32(0.5)) * f32(0.1)
        + (fine - f32(0.5)) * f32(0.04)
        - speck
        - scuff
    )
    lum = lum * (f32(1.0) - f32(0.35) * seam)
    g = np.clip(lum * f32(255.0), f32(0.0), f32(255.0)).astype(np.uint8)
    gf = g.astype(np.float32)
    color = _rgba(
        g,
        np.minimum(gf * f32(1.005), f32(255.0)).astype(np.uint8),
        np.minimum(gf * f32(1.02), f32(255.0)).astype(np.uint8),
    )
    color = td.Texture.from_rgba8(size, size, color).repeat(
        float(F(1.0) / TILE), float(F(1.0) / TILE)
    )

    half = size // 2
    c2 = _centers(half)
    u2, v2 = c2[None, :], c2[:, None]
    wear = fbm(u2 + f32(0.17), v2 + f32(0.41), 13)
    seam2 = _seam(u2, v2)
    rough = np.clip(
        f32(0.32) + (wear - f32(0.5)) * f32(0.35) + seam2 * f32(0.4), f32(0.12), f32(1.0)
    )
    ao = f32(1.0) - f32(0.6) * seam2
    ao_rough = _rgba(
        (ao * f32(255.0)).astype(np.uint8),
        (rough * f32(255.0)).astype(np.uint8),
        np.zeros_like(seam2, dtype=np.uint8),
    )
    ao_rough = td.Texture.from_rgba8(half, half, ao_rough, srgb=False).repeat(
        float(F(1.0) / TILE), float(F(1.0) / TILE)
    )

    # The heights on the texel centers with a border of one texel: u + e is the next texel.
    cp = _centers(size, 1)
    up, vp = cp[None, :], cp[:, None]
    height = f32(-0.004) * _seam(up, vp) + f32(0.0005) * fbm(up, vp, 3)
    e = f32(1.0) / f32(size)
    meters = e * TILE
    dx = (height[1:-1, 2:] - height[1:-1, :-2]) / (f32(2.0) * meters)
    dz = (height[2:, 1:-1] - height[:-2, 1:-1]) / (f32(2.0) * meters)
    nx, ny, nz = -dx, dz, np.ones_like(dx)
    length = np.sqrt(nx * nx + ny * ny + nz * nz)
    recip = f32(1.0) / length

    def byte(c):
        x = (c * recip * f32(0.5) + f32(0.5)) * f32(255.0)
        r = np.trunc(x)
        r = r + np.where(np.abs(x - r) >= f32(0.5), np.sign(x), f32(0.0))
        return r.astype(np.uint8)

    normals = _rgba(byte(nx), byte(ny), byte(nz))
    normals = td.Texture.from_rgba8(size, size, normals, srgb=False).repeat(
        float(F(1.0) / TILE), float(F(1.0) / TILE)
    )
    return color, ao_rough, normals


def hazard_texture() -> td.Texture:
    """Diagonal yellow and black stripes in world space."""
    c = _centers(64)
    s = c[None, :] + c[:, None]
    stripe = (s - np.trunc(s)) < f32(0.5)
    rgba = np.where(
        stripe[..., None],
        np.array([236, 180, 0, 255], np.uint8),
        np.array([22, 22, 24, 255], np.uint8),
    )
    scale = float(F(1.0) / F(0.3))
    return td.Texture.from_rgba8(64, 64, rgba.astype(np.uint8).tobytes()).repeat(scale, scale)


def world_uvs(g: td.Geometry) -> td.Geometry:
    """`g` with the UV (x, z) of each vertex."""
    p = np.frombuffer(g.positions(), dtype=np.float32).reshape(-1, 3)
    return g.with_uvs(np.ascontiguousarray(p[:, [0, 2]]).tobytes())


def strip(a, b, width) -> td.Geometry:
    """A strip of floor paint from `a` to `b`, with world space UVs."""
    ax, ay, bx, by = F(a[0]), F(a[1]), F(b[0]), F(b[1])
    dx, dy = bx - ax, by - ay
    length = sqrt(dx * dx + dy * dy)
    angle = atan2(dy / length, dx / length)
    mx, my = (ax + bx) * F(0.5), (ay + by) * F(0.5)
    return world_uvs(Geometry.floor(length, width).rotate_y(-angle).translate(mx, 0.003, my))


def screen_texture() -> td.Texture:
    """A lab monitor: a grid, a level meter and a trace."""
    w, h = 256, 160
    u, v = _centers(w)[None, :], _centers(h)[:, None]

    def line(d, width):
        return f32(1.0) - _smooth01(np.abs(d) / f32(width))

    def frac(x):
        return x - np.trunc(x)

    grid = np.maximum(
        line(frac(u * f32(8.0)) - f32(0.5), 0.06), line(frac(v * f32(5.0)) - f32(0.5), 0.06)
    )
    u1 = _centers(w)
    wave = np.array(
        [F(0.5) + F(0.18) * sin(x * F(19.0)) * cos(x * F(3.0) + F(1.0)) for x in u1],
        dtype=np.float32,
    )[None, :]
    trace = line(v - wave, 0.012)
    bar = np.where((u > f32(0.86)) & (v > f32(0.4)), f32(0.8), f32(0.0))
    lum = np.minimum(np.maximum(f32(0.1) * grid + trace, bar), f32(1.0))
    rgba = _rgba(
        (f32(40.0) * lum).astype(np.uint8),
        (f32(190.0) * lum).astype(np.uint8),
        (f32(255.0) * lum).astype(np.uint8),
    )
    return td.Texture.from_rgba8(w, h, rgba)


def environment(level) -> td.Environment:
    """The studio environment of the lab at the light `level`."""
    return td.Environment.custom_studio(
        td.Rgb.hex(0xEEF0F2),
        td.Rgb.hex(0xC9CCD0),
        td.Rgb.hex(0x6A6C70),
        SOFTBOXES,
        intensity=F(0.6) * F(level),
    )


SOFTBOXES = [
    ((-0.35, 1.0, 0.0), 12.0, 70.0, td.Rgb.WHITE * 3.2),
    ((0.35, 1.0, 0.0), 12.0, 70.0, td.Rgb.WHITE * 3.2),
    ((0.0, 0.5, 0.85), 70.0, 10.0, td.Rgb.hex(0xFFF1E0) * 1.6),
    ((-1.0, 0.18, -0.3), 8.0, 40.0, td.Rgb.hex(0xDDE8FF) * 1.4),
]
AIR_DARK = td.Rgb.hex(0x0C1220)
AIR_LIT = td.Rgb.hex(0xBFC3C7)


class Lab:
    """The lab nodes that `set_lights` changes."""

    def __init__(self, scene: td.Scene, font: bytes):
        color, ao_rough, normals = floor_textures()
        # The scene reflects in the polished concrete. The roughness map blurs the reflection.
        scene.set_reflector_floor()
        floor = (
            Material.standard(0xFFFFFF)
            .roughness(1.0)
            .env_intensity(0.9)
            .reflection(0.85)
            .map(color)
            .normal_map(normals)
            .ao_map(ao_rough)
            .metal_rough_map(ao_rough)
        )
        scene.add(Node.mesh(Geometry.floor(60.0, 60.0), floor).shadows(False, True))
        # The hazard border of the cell.
        hazard = Material.standard(0xFFFFFF).roughness(0.55).map(hazard_texture())
        x0, x1, z0, z1 = F(-2.9), F(2.9), F(-2.15), F(2.35)
        h = F(0.07)
        border = Geometry.merge(
            [
                strip((x0, z0), (x1, z0), 0.14),
                strip((x0, z1), (x1, z1), 0.14),
                strip((x0, z0 - h), (x0, z1 + h), 0.14),
                strip((x1, z0 - h), (x1, z1 + h), 0.14),
            ]
        )
        scene.add(Node.mesh(border, hazard).shadows(False, True))
        # The reach of the arm: a dashed circle and a ring around the base.
        paint = Material.standard(0xF3F3F0).roughness(0.6)
        dashes = []
        for i in range(0, 48, 2):
            a0 = F(i) / F(48.0) * TAU
            a1 = (F(i) + F(1.0)) / F(48.0) * TAU
            dashes.append(
                strip(
                    (csin(a0) * F(2.05), ccos(a0) * F(2.05)),
                    (csin(a1) * F(2.05), ccos(a1) * F(2.05)),
                    0.035,
                )
            )
        scene.add(Node.mesh(Geometry.merge(dashes), paint).shadows(False, True))
        ring = Geometry.ring(0.62, 0.66, 96).rotate_x(deg(-90.0)).translate(0.0, 0.003, 0.0)
        scene.add(Node.mesh(ring, paint).shadows(False, True))

        def stencil(text, size, at, yaw):
            try:
                g = Geometry.text(font, text, size, 0.002, 0.0)
            except ValueError:
                return []
            lo, hi = g.bounds()
            c = (lo + hi) * 0.5
            return [
                g.translate(-c.x, -c.y, 0.0)
                .rotate_x(deg(-90.0))
                .rotate_y(yaw)
                .translate(at[0], 0.003, at[2])
            ]

        stencils = []
        stencils += stencil("R-07", 0.22, (1.15, 0.0, -0.75), deg(-30.0))
        stencils += stencil("OUTPUT", 0.13, (1.95, 0.0, 1.95), 0.0)
        stencils += stencil("PARTS", 0.13, (2.1, 0.0, -1.85), 0.0)
        stencils += stencil("KEEP CLEAR", 0.11, (0.0, 0.0, 2.6), 0.0)
        scene.add(Node.mesh(Geometry.merge(stencils), paint).shadows(False, True))
        # The output tray: a painted outline.
        tray = Geometry.merge(
            [
                strip((-1.75, 0.95), (1.75, 0.95), 0.025),
                strip((-1.75, 1.55), (1.75, 1.55), 0.025),
                strip((-1.75, 0.94), (-1.75, 1.56), 0.025),
                strip((1.75, 0.94), (1.75, 1.56), 0.025),
            ]
        )
        scene.add(Node.mesh(tray, paint).shadows(False, True))
        # A calibration grid printed in the tray: 5 cm cells, a thick line every 25 cm.
        mat = world_uvs(Geometry.floor(3.45, 0.55).translate(0.0, 0.0025, 1.25))
        grid = grid_texture(0.05, 5, td.Rgb.hex(0x50545A), td.Rgb.hex(0xA8AAA7))
        scene.add(
            Node.mesh(mat, Material.standard(0xFFFFFF).roughness(0.7).map(grid)).shadows(
                False, True
            )
        )

        # Walls far away, with panel seams and light strips.
        wall = Material.standard(0xC9CCD0).roughness(0.8)
        scene.add(
            Node.mesh(Geometry.cuboid(30.0, 7.0, 0.3).translate(0.0, 3.5, -9.0), wall).shadows(
                False, True
            )
        )
        scene.add(
            Node.mesh(Geometry.cuboid(0.3, 7.0, 30.0).translate(-9.0, 3.5, 0.0), wall).shadows(
                False, True
            )
        )
        seams = Geometry.merge(
            [
                Geometry.cuboid(0.03, 7.0, 0.04).translate(F(i) * F(2.4), 3.5, -8.84)
                for i in range(-6, 7)
            ]
        )
        scene.add(
            Node.mesh(seams, Material.standard(0xB9BCC0).roughness(0.7)).shadows(False, False)
        )
        light_strips = Geometry.merge(
            [
                Geometry.rounded_box(16.0, 0.12, 0.05, 0.02, 1).translate(0.0, 2.6, -8.82),
                Geometry.rounded_box(0.05, 0.12, 16.0, 0.02, 1).translate(-8.82, 2.6, 0.0),
            ]
        )
        self.light_strips = scene.add(
            Node.mesh(light_strips, Material.standard(0xFFFFFF).emissive(0xFFF4E6, 0.0)).shadows(
                False, False
            )
        )
        # Benches along the back wall, with monitors.
        screen = screen_texture()
        bench = Material.standard(0xD7D9DC).roughness(0.5)
        for x in (F(-4.5), F(3.2)):
            scene.add(
                Node.mesh(
                    Geometry.rounded_box(2.6, 0.06, 0.8, 0.02, 2).translate(x, 0.92, -7.9), bench
                )
            )
            scene.add(
                Node.mesh(
                    Geometry.rounded_box(2.5, 0.85, 0.7, 0.03, 2).translate(x, 0.44, -7.95),
                    Material.standard(0xB4B8BD).roughness(0.6),
                )
            )
            scene.add(
                Node.mesh(
                    Geometry.rounded_box(0.5, 0.35, 0.05, 0.02, 2).translate(x - F(0.6), 1.2, -8.1),
                    Material.standard(0x1B1C1F)
                    .roughness(0.15)
                    .emissive(0xFFFFFF, 1.2)
                    .emissive_map(screen),
                )
            )

        # Shelves with parts bins against the back wall: one instanced mesh, a color per copy.
        shelf_y = [F(0.3), F(0.82), F(1.34), F(1.86)]
        shelves = Geometry.merge(
            [Geometry.cuboid(4.5, 0.03, 0.5).translate(-0.6, y, -8.58) for y in shelf_y]
            + [
                Geometry.cuboid(0.04, 2.0, 0.5).translate(x, 1.0, -8.58)
                for x in (-2.85, -0.6, 1.65)
            ]
        )
        scene.add(Node.mesh(shelves, Material.metal(0x8D9196, 0.45)).shadows(False, True))
        bin_colors = [0x2F6FD0, 0x2F6FD0, 0x2F6FD0, 0xF2BD00, 0xD8422B, 0x9EA3A8]
        transforms, colors = [], []
        for row in range(4):
            for i in range(10):
                if hash(row * 31 + i * 7 + 3) > 0.12:
                    x = F(-2.6) + F(i) * F(0.445) + (F(0.04) if i >= 5 else F(0.0))
                    y = shelf_y[row] + F(0.015) + F(0.13)
                    pick = int(hash(row * 13 + i * 5 + 1) * F(len(bin_colors)))
                    transforms.append(td.Mat4.from_translation((x, y, -8.55)))
                    colors.append(td.Rgb.hex(bin_colors[pick]))
        scene.add(
            Node.instanced(
                Geometry.rounded_box(0.4, 0.26, 0.42, 0.02, 2),
                Material.standard(0xFFFFFF).roughness(0.55),
                transforms,
                colors,
            ).shadows(False, True)
        )

        # The letter rack: an aluminium frame on a base plate.
        alu = Material.metal(0xC9CCD1, 0.32)
        scene.add(
            Node.mesh(
                Geometry.rounded_box(4.3, 0.02, 0.36, 0.008, 2).translate(0.0, 0.01, RACK_Z),
                Material.metal(0x34363B, 0.45),
            )
        )
        for z in (RACK_Z - F(0.14), RACK_Z + F(0.14)):
            scene.add(
                Node.mesh(
                    Geometry.rounded_box(4.2, 0.04, 0.04, 0.006, 2).translate(0.0, 0.12, z), alu
                )
            )
            scene.add(
                Node.mesh(
                    Geometry.rounded_box(4.2, 0.006, 0.012, 0.002, 1).translate(0.0, 0.142, z),
                    Material.metal(0x5B5E64, 0.5),
                )
            )
        posts = []
        for i in range(8):
            x = F(-1.82) + F(i) * F(0.52)
            for z in (RACK_Z - F(0.14), RACK_Z + F(0.14)):
                posts.append(Geometry.rounded_box(0.04, 0.12, 0.04, 0.006, 1).translate(x, 0.06, z))
        scene.add(Node.mesh(Geometry.merge(posts), alu))

        self.key = scene.add(
            Node.light(
                td.Light.sun(td.Rgb.hex(0xFFF6EA), 0.0, (1.8, 7.0, 4.0)).with_shadow(
                    map_size=3072,
                    softness=3.5,
                    strength=0.95,
                    bounds=(Vec3(-3.2, 0.0, -2.2), Vec3(3.2, 3.2, 2.6)),
                )
            )
        )
        self.fill = scene.add(
            Node.light(td.Light.directional(td.Rgb.hex(0xCFE0FF), 0.0, (-4.0, 3.0, -2.0)))
        )
        self.ambient = scene.add(Node.light(td.Light.hemisphere(0xF2F4F6, 0x8A8680, 0.0)))

    def set_lights(self, scene: td.Scene, level):
        """Sets the light level of the lab: 0 is dark blue, 1 is fully lit."""
        level = F(level)
        scene.set_environment(environment(max(level, F(0.04))))
        scene.set_light_intensity(self.key, F(2.4) * level)
        scene.set_light_intensity(self.fill, F(0.6) * level)
        scene.set_light_intensity(self.ambient, level + F(0.25))
        air = AIR_DARK.lerp(AIR_LIT, level)
        scene.set_background(air)
        scene.set_fog_exp2(air, 0.045)
        scene.set_emissive_intensity(self.light_strips, F(2.2) * level)

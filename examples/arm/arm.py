"""Port of arm.rs: a six axis industrial arm with a camera eye, and its inverse kinematics."""

from itertools import pairwise

import numpy as np
from fframes import three_d as td
from fmath import (
    FRAC_PI_2,
    PI,
    TAU,
    ZERO,
    F,
    acos,
    atan2,
    ccos,
    clamp,
    csin,
    deg,
    rround,
    sin,
    sin_cos,
    sqrt,
)

Vec3, Quat, Mat4, Geometry, Node, Material = (
    td.Vec3,
    td.Quat,
    td.Mat4,
    td.Geometry,
    td.Node,
    td.Material,
)

BASE_H = F(0.45)
J2_UP = F(0.42)
A1 = F(0.16)
L2 = F(1.05)
A3 = F(0.12)
L3 = F(1.0)
J4_AT = F(0.62)
J6_OFFSET = F(0.15)
GRIP = F(0.24)
TIP = J6_OFFSET + GRIP
OPEN = F(0.12)
EYE = (F(0.0), F(0.068), F(0.1))
EYE_LIGHT = 0xFFD6A8


def joints(*q) -> np.ndarray:
    return np.array(q, dtype=np.float32)


def chain(q) -> list:
    return [
        Mat4.from_translation((0.0, BASE_H, 0.0)) * Mat4.from_rotation_y(q[0]),
        Mat4.from_translation((0.0, J2_UP, A1)) * Mat4.from_rotation_x(q[1]),
        Mat4.from_translation((0.0, L2, 0.0)) * Mat4.from_rotation_x(q[2]),
        Mat4.from_translation((0.0, A3, J4_AT)) * Mat4.from_rotation_z(q[3]),
        Mat4.from_translation((0.0, 0.0, L3 - J4_AT)) * Mat4.from_rotation_x(q[4]),
        Mat4.from_translation((0.0, 0.0, J6_OFFSET)) * Mat4.from_rotation_z(q[5]),
    ]


def flange(q) -> td.Mat4:
    m = Mat4.IDENTITY
    for j in chain(q):
        m = m * j
    return m


GRIP_MAT = Mat4.from_translation((0.0, 0.0, GRIP))


def tip(q) -> td.Mat4:
    return flange(q) * GRIP_MAT


def eye(q) -> td.Vec3:
    return flange(q).transform_point3(EYE)


def unwrap(a, near):
    return a + rround((near - a) / TAU) * TAU


L3_DIAG = sqrt(L3 * L3 + A3 * A3)
PHI = atan2(A3, L3)


def solve(position: td.Vec3, rotation: td.Quat, hint) -> np.ndarray:
    """The joints that put the tool tip at `position` with `rotation`, nearest `hint`."""
    axis = rotation * Vec3.Z
    wrist = position - axis * TIP
    wx, wy, wz = F(wrist.x), F(wrist.y), F(wrist.z)
    q1 = unwrap(atan2(wx, wz), hint[0])
    r = sqrt(wx * wx + wz * wz) - A1
    h = wy - (BASE_H + J2_UP)
    d = clamp(sqrt(r * r + h * h), 0.05, L2 + L3_DIAG - F(1e-3))
    gamma = atan2(h, r)
    psi = acos(clamp((L2 * L2 + d * d - L3_DIAG * L3_DIAG) / (F(2.0) * L2 * d), -1.0, 1.0))
    theta2 = gamma + psi
    s, c = sin_cos(theta2)
    ex, ey = L2 * c, L2 * s
    theta3 = atan2(h - ey, r - ex) - PHI
    q2 = FRAC_PI_2 - theta2
    q3 = -theta3 - q2
    r3 = Quat.from_rotation_y(q1) * Quat.from_rotation_x(q2 + q3)
    m = r3.inverse() * rotation
    z = m * Vec3.Z
    zx, zy, zz = F(z.x), F(z.y), F(z.z)
    b = acos(clamp(zz, -1.0, 1.0))
    if abs(sin(b)) < F(1e-4):
        candidates = [(hint[3], ZERO if zz > 0.0 else PI)]
    else:
        a = atan2(zx, -zy)
        candidates = [(a, b), (a + PI, -b)]
    best = None
    for a, b in candidates:
        a = unwrap(a, hint[3])
        n = (Quat.from_rotation_z(a) * Quat.from_rotation_x(b)).inverse() * m
        x = n * Vec3.X
        c = unwrap(atan2(F(x.y), F(x.x)), hint[5])
        cost = abs(a - hint[3]) + F(0.5) * abs(c - hint[5]) + F(0.3) * abs(b - hint[4])
        if best is None or cost < best[0]:
            best = (cost, joints(q1, q2, q3, a, b, c))
    return best[1]


def frame(x: td.Vec3, z: td.Vec3) -> td.Quat:
    """The rotation with the axes `x` (made orthogonal) and `z`."""
    z = z.normalize()
    y = z.cross(x).normalize()
    return Quat.from_cols(y.cross(z), y, z)


def tool_down(fingers: td.Vec3) -> td.Quat:
    return frame(fingers, Vec3.NEG_Y)


def looking(look: td.Vec3, roll) -> td.Quat:
    z = look.normalize()
    side = Vec3.Y.cross(z).normalize_or(Vec3.X)
    return Quat.from_axis_angle(z, roll) * frame(side, z)


class Palette:
    def __init__(self):
        self.white = Material.standard(0xEEEEEA).roughness(0.36).clearcoat(0.7)
        self.graphite = Material.metal(0x2C2D31, 0.38)
        self.chrome = Material.metal(0xE0E3E7, 0.1)
        self.rubber = Material.standard(0x151517).roughness(0.85)
        self.dark = Material.metal(0x18191B, 0.55)
        self.yellow = Material.standard(0xF2BD00).roughness(0.45)
        self.glass = Material.standard(0x05070A).roughness(0.03).clearcoat(1.0).env_intensity(1.6)


def hull(circles) -> list:
    """The convex hull of circles (center, radius), counterclockwise."""
    points = []
    for (cx, cy), r in circles:
        cx, cy, r = F(cx), F(cy), F(r)
        for i in range(48):
            a = F(i) / F(48.0) * TAU
            points.append((cx + ccos(a) * r, cy + csin(a) * r))
    points.sort()

    def cross(o, a, b):
        ax, ay = a[0] - o[0], a[1] - o[1]
        bx, by = b[0] - o[0], b[1] - o[1]
        return ax * by - ay * bx

    def half(pts):
        out = []
        for p in pts:
            while len(out) >= 2 and cross(out[-2], out[-1], p) <= 0.0:
                out.pop()
            out.append(p)
        return out

    lower, upper = half(points), half(reversed(points))
    return lower[:-1] + upper[:-1]


def side_plate(shape, thickness, bevel, x) -> td.Geometry:
    flipped = [(-px, py) for px, py in shape]
    return Geometry.extrude(flipped, thickness, bevel).rotate_y(deg(90.0)).translate(x, 0.0, 0.0)


def axle(radius, length, x, y, z) -> td.Geometry:
    return Geometry.cylinder(radius, radius, length, 48).rotate_z(deg(90.0)).translate(x, y, z)


def rod(radius, length, center, axis, segments) -> td.Geometry:
    return (
        Geometry.cylinder(radius, radius, length, segments)
        .rotate(Quat.from_rotation_arc(Vec3.Y, axis))
        .translate(center.x, center.y, center.z)
    )


def bolt_circle(count, radius, bolt, center, normal) -> td.Geometry:
    bolt, radius = F(bolt), F(radius)
    head = Geometry.merge(
        [
            Geometry.cylinder(bolt * F(1.35), bolt * F(1.35), bolt * F(0.25), 16).translate(
                0.0, bolt * F(0.12), 0.0
            ),
            Geometry.cylinder(bolt, bolt, bolt * F(0.8), 6).translate(0.0, bolt * F(0.62), 0.0),
        ]
    )
    to_normal = Quat.from_rotation_arc(Vec3.Y, normal)
    parts = []
    for i in range(count):
        a = F(i) / F(count) * TAU
        parts.append(
            head.translate(ccos(a) * radius, 0.0, csin(a) * radius)
            .rotate(to_normal)
            .translate(center.x, center.y, center.z)
        )
    return Geometry.merge(parts)


def fins(count, radius, start, end) -> td.Geometry:
    axis = (end - start).normalize_or(Vec3.Y)
    ring = Geometry.torus(radius, 0.008, 6, 40).rotate_x(deg(90.0))
    to_axis = Quat.from_rotation_arc(Vec3.Y, axis)
    parts = []
    for i in range(count):
        p = start.lerp(end, (F(i) + F(0.5)) / F(count))
        parts.append(ring.rotate(to_axis).translate(p.x, p.y, p.z))
    return Geometry.merge(parts)


def conduit(path, radius):
    """A hose along `path` and the rings of its corrugation."""
    radius = F(radius)
    tube = Geometry.tube(path, radius, 14)
    rings = []
    along = F(0.0)
    for a, b in pairwise(path):
        length = F(a.distance(b))
        direction = (b - a).normalize_or(Vec3.Y)
        s = max(F(0.035) - along, ZERO)
        while s < length:
            p = a + direction * s
            rings.append(
                Geometry.torus(radius * F(1.02), radius * F(0.18), 6, 18)
                .rotate_x(deg(90.0))
                .rotate(Quat.from_rotation_arc(Vec3.Y, direction))
                .translate(p.x, p.y, p.z)
            )
            s += F(0.035)
        along = s - length
    return tube, Geometry.merge(rings)


def warning(scene, parent, p, at, normal, size):
    """A yellow warning triangle with an exclamation mark."""
    size = F(size)
    to_normal = Quat.from_rotation_arc(Vec3.Z, normal)

    def place(g, out):
        out = F(out)
        return g.rotate(to_normal).translate(
            F(at.x) + F(normal.x) * out, F(at.y) + F(normal.y) * out, F(at.z) + F(normal.z) * out
        )

    tri = Geometry.polygon(size, 3)
    scene.add_to(parent, Node.mesh(place(Geometry.extrude(tri, 0.003, 0.0), 0.0), p.dark))
    inner = Geometry.extrude(Geometry.polygon(size * F(0.78), 3), 0.003, 0.0).translate(
        0.0, -size * F(0.04), 0.0
    )
    scene.add_to(parent, Node.mesh(place(inner, 0.002), p.yellow))
    mark = Geometry.merge(
        [
            Geometry.rounded_box(
                size * F(0.12), size * F(0.42), 0.003, size * F(0.03), 1
            ).translate(0.0, size * F(0.02), 0.0),
            Geometry.cylinder(size * F(0.07), size * F(0.07), 0.003, 12)
            .rotate_x(deg(90.0))
            .translate(0.0, -size * F(0.32), 0.0),
        ]
    )
    scene.add_to(parent, Node.mesh(place(mark, 0.004), p.dark))


def centered(g: td.Geometry):
    lo, hi = g.bounds()
    c = (lo + hi) * 0.5
    return g.translate(-c.x, -c.y, 0.0)


def lettering(scene, parent, material, font, text, size, at, rotation):
    """Raised letters on a surface."""
    try:
        g = Geometry.text(font, text, size, 0.006, 0.0012)
    except ValueError:
        return
    scene.add_to(
        parent, Node.mesh(centered(g).rotate(rotation).translate(at.x, at.y, at.z), material)
    )


def motor(scene, parent, p, at, axis, radius, length):
    """A servo motor with cooling fins, a cap, bolts and a plug."""
    radius, length = F(radius), F(length)
    to_axis = Quat.from_rotation_arc(Vec3.Y, axis)
    center = at + axis * (length * F(0.5))
    scene.add_to(
        parent,
        Node.mesh(
            Geometry.cylinder(radius, radius, length, 48)
            .rotate(to_axis)
            .translate(center.x, center.y, center.z),
            p.white,
        ),
    )
    scene.add_to(
        parent,
        Node.mesh(
            fins(
                7, radius + F(0.004), at + axis * (length * F(0.15)), at + axis * (length * F(0.75))
            ),
            p.graphite,
        ),
    )
    cap_at = at + axis * (length + F(0.015))
    scene.add_to(
        parent,
        Node.mesh(
            Geometry.cylinder(radius * F(0.92), radius * F(0.92), 0.03, 48)
            .rotate(to_axis)
            .translate(cap_at.x, cap_at.y, cap_at.z),
            p.graphite,
        ),
    )
    scene.add_to(
        parent,
        Node.mesh(
            bolt_circle(6, radius * F(0.7), 0.008, at + axis * (length + F(0.03)), axis), p.chrome
        ),
    )
    side = Vec3.Z if abs(axis.y) > 0.5 else Vec3.Y
    plug_at = at + axis * (length * F(0.85)) + side * radius
    scene.add_to(
        parent,
        Node.mesh(
            Geometry.rounded_box(0.05, 0.05, 0.05, 0.012, 2).translate(
                plug_at.x, plug_at.y, plug_at.z
            ),
            p.dark,
        ),
    )
    nut = at + axis * (length * F(0.85)) + side * (radius + F(0.035))
    scene.add_to(parent, Node.mesh(rod(0.016, 0.03, nut, side, 6), p.chrome))


def signum(x) -> float:
    return 1.0 if x > 0 else -1.0


class Expression:
    """The face of the arm: glow levels of the ring, status light and eye, the lid, the beam."""

    __slots__ = ("beam", "eye", "lid", "ring", "status")

    def __init__(self, ring, status, eye, lid, beam):
        self.ring, self.status, self.eye, self.lid, self.beam = ring, status, eye, lid, beam


def v(x, y, z) -> td.Vec3:
    return Vec3(x, y, z)


class Arm:
    """The node ids of the arm that `apply` moves."""

    def __init__(self, scene: td.Scene, p: Palette, font: bytes):
        add = scene.add_to
        base = scene.add(Node.group().named("base"))
        add(
            base,
            Node.mesh(
                Geometry.rounded_box(1.0, 0.05, 1.0, 0.02, 3).translate(0.0, 0.025, 0.0), p.graphite
            ),
        )
        corners = [(-1, -1), (1, -1), (-1, 1), (1, 1), (0, -1), (0, 1), (-1, 0), (1, 0)]
        anchors = Geometry.merge(
            [
                bolt_circle(1, 0.0, 0.026, v(F(x) * F(0.43), 0.05, F(z) * F(0.43)), Vec3.Y)
                for x, z in corners
            ]
        )
        add(base, Node.mesh(anchors, p.chrome))
        column = [
            (0.0, 0.05),
            (0.36, 0.05),
            (0.36, 0.09),
            (0.31, 0.13),
            (0.3, 0.37),
            (0.335, 0.405),
            (0.335, 0.45),
            (0.0, 0.45),
        ]
        add(base, Node.mesh(Geometry.lathe(column, 96), p.white))
        ribs = Geometry.merge(
            [
                Geometry.rounded_box(0.014, 0.2, 0.045, 0.005, 1)
                .translate(0.0, 0.25, 0.3)
                .rotate_y(F(i) / F(28.0) * TAU)
                for i in range(28)
            ]
        )
        add(base, Node.mesh(ribs, p.graphite))
        ring = add(
            base,
            Node.mesh(
                Geometry.torus(0.336, 0.008, 8, 128).rotate_x(deg(90.0)).translate(0.0, 0.385, 0.0),
                Material.standard(0x111111).emissive(0xFF4A00, 0.0),
            ),
        )
        ring_light = add(base, Node.light(td.Light.point(0xFF4A00, 0.0, 1.6)).at(0.0, 0.385, 0.0))
        add(
            base,
            Node.mesh(
                Geometry.rounded_box(0.18, 0.14, 0.1, 0.02, 2).translate(0.0, 0.2, -0.32), p.dark
            ),
        )
        chain_path = []
        for i in range(41):
            t = F(i) / F(40.0)
            a = t * PI
            chain_path.append(
                v(
                    F(-0.9) * t,
                    F(0.06) + F(0.16) * csin(a) * (F(1.0) - t * F(0.5)),
                    F(-0.45) - F(0.55) * t,
                )
            )
        links = []
        for i, (a, b) in enumerate(pairwise(chain_path)):
            if i % 2 == 0:
                d = (b - a).normalize_or(Vec3.X)
                mid = (a + b) * 0.5
                links.append(
                    Geometry.rounded_box(0.09, 0.05, 0.06, 0.01, 1)
                    .rotate(Quat.from_rotation_arc(Vec3.Z, d))
                    .translate(mid.x, mid.y, mid.z)
                )
        add(base, Node.mesh(Geometry.merge(links), p.dark))
        add(
            base,
            Node.mesh(
                Geometry.rounded_box(0.32, 0.16, 0.24, 0.03, 2).translate(-0.98, 0.08, -1.02),
                p.graphite,
            ),
        )
        add(
            base,
            Node.mesh(
                Geometry.rounded_box(0.2, 0.004, 0.12, 0.002, 1).translate(-0.98, 0.162, -1.02),
                p.yellow,
            ),
        )

        # J1: the turret.
        j1 = add(base, Node.group())
        add(
            j1,
            Node.mesh(
                Geometry.cylinder(0.34, 0.345, 0.07, 96).translate(0.0, 0.035, 0.0), p.graphite
            ),
        )
        add(j1, Node.mesh(bolt_circle(16, 0.3, 0.011, v(0.0, 0.07, 0.0), Vec3.Y), p.chrome))
        cheek = hull([((A1, J2_UP), 0.235), ((-0.08, 0.13), 0.22), ((0.18, 0.1), 0.2)])
        inner = hull([((A1, J2_UP), 0.17), ((-0.04, 0.16), 0.15)])
        for x in (F(-0.25), F(0.25)):
            add(j1, Node.mesh(side_plate(cheek, 0.09, 0.025, x), p.white))
            add(j1, Node.mesh(side_plate(inner, 0.02, 0.006, x * F(1.24)), p.graphite))
        add(
            j1,
            Node.mesh(
                Geometry.rounded_box(0.42, 0.18, 0.44, 0.05, 3).translate(0.0, 0.13, 0.02), p.white
            ),
        )
        vents = Geometry.merge(
            [
                Geometry.rounded_box(0.22, 0.012, 0.01, 0.004, 1).translate(
                    0.0, F(0.08) + F(i) * F(0.022), 0.245
                )
                for i in range(6)
            ]
        )
        add(j1, Node.mesh(vents, p.dark))
        motor(scene, j1, p, v(0.0, 0.1, -0.33), Vec3.Y, 0.1, 0.3)
        motor(scene, j1, p, v(-0.33, J2_UP, A1), Vec3.NEG_X, 0.125, 0.22)
        add(j1, Node.mesh(axle(0.2, 0.42, 0.0, J2_UP, A1), p.graphite))
        for x in (F(-0.302), F(0.302)):
            add(j1, Node.mesh(axle(0.12, 0.02, x, J2_UP, A1), p.chrome))
            add(
                j1,
                Node.mesh(
                    bolt_circle(10, 0.155, 0.01, v(x * F(1.03), J2_UP, A1), Vec3.X * signum(x)),
                    p.chrome,
                ),
            )
        warning(scene, j1, p, v(0.30, 0.17, -0.02), Vec3.X, 0.045)
        lettering(
            scene,
            j1,
            p.dark,
            font,
            "07",
            0.11,
            v(-0.30, 0.18, -0.03),
            Quat.from_rotation_y(-FRAC_PI_2),
        )

        # J2: the upper arm.
        j2 = add(j1, Node.group())
        beam = hull([((0.0, 0.0), 0.19), ((0.0, L2), 0.15)])
        add(j2, Node.mesh(side_plate(beam, 0.3, 0.035, 0.0), p.white))
        panel = hull([((0.0, 0.25), 0.1), ((0.0, L2 - F(0.25)), 0.08)])
        for x in (F(-0.155), F(0.155)):
            add(j2, Node.mesh(side_plate(panel, 0.016, 0.005, x), p.graphite))
            side = FRAC_PI_2 if x > 0.0 else -FRAC_PI_2
            lettering(
                scene,
                j2,
                p.chrome,
                font,
                "FFRAMES",
                0.06,
                v(x * F(1.06), L2 * F(0.52), 0.0),
                Quat.from_rotation_y(side) * Quat.from_rotation_z(FRAC_PI_2),
            )
        add(
            j2,
            Node.mesh(
                Geometry.rounded_box(0.004, L2 * F(0.5), 0.012, 0.002, 1).translate(
                    0.165, L2 * F(0.5), 0.11
                ),
                Material.standard(0x111111).emissive(0xFF4A00, 1.6),
            ),
        )
        cable = []
        for i in range(17):
            t = F(i) / F(16.0)
            cable.append(v(0.09, F(0.08) + t * (L2 - F(0.16)), F(-0.2) - F(0.05) * csin(t * PI)))
        hose, rings = conduit(cable, 0.024)
        add(j2, Node.mesh(hose, p.rubber))
        add(j2, Node.mesh(rings, p.rubber))
        cable2 = [c + v(-0.07, 0.0, 0.005) for c in cable]
        add(j2, Node.mesh(Geometry.tube(cable2, 0.014, 12), p.dark))
        clamps = Geometry.merge(
            [
                Geometry.rounded_box(0.16, 0.03, 0.07, 0.01, 2).translate(
                    0.055,
                    F(0.08) + F(i) * F(0.25),
                    F(-0.2) - F(0.05) * csin(F(i) * F(0.25) / F(0.9) * PI),
                )
                for i in range(1, 4)
            ]
        )
        add(j2, Node.mesh(clamps, p.chrome))
        for y in (0.35, 0.75):
            add(
                j2, Node.mesh(Geometry.torus(0.022, 0.006, 8, 20).translate(0.0, y, 0.17), p.chrome)
            )
        add(j2, Node.mesh(axle(0.16, 0.36, 0.0, L2, 0.0), p.graphite))
        for x in (F(-0.19), F(0.19)):
            add(j2, Node.mesh(axle(0.09, 0.02, x, L2, 0.0), p.chrome))
            add(
                j2,
                Node.mesh(
                    bolt_circle(8, 0.12, 0.009, v(x * F(1.06), L2, 0.0), Vec3.X * signum(x)),
                    p.chrome,
                ),
            )
        motor(scene, j2, p, v(0.18, L2, 0.0), Vec3.X, 0.1, 0.16)

        # J3: the elbow and the forearm.
        j3 = add(j2, Node.group())
        add(
            j3,
            Node.mesh(
                Geometry.rounded_box(0.3, 0.3, 0.34, 0.07, 4).translate(0.0, A3, -0.18), p.white
            ),
        )
        grille = Geometry.merge(
            [
                Geometry.rounded_box(0.012, 0.16, 0.01, 0.004, 1).translate(
                    0.152, A3, F(-0.26) + F(i) * F(0.03)
                )
                for i in range(5)
            ]
        )
        add(j3, Node.mesh(grille, p.dark))
        add(j3, Node.mesh(grille.scale(-1.0, 1.0, 1.0), p.dark))
        for x, y in ((-0.07, 0.07), (0.07, 0.07), (0.0, -0.07)):
            motor(scene, j3, p, v(x, A3 + F(y), -0.35), Vec3.NEG_Z, 0.05, 0.12)
        add(
            j3,
            Node.mesh(
                Geometry.cylinder(0.105, 0.13, 0.5, 64)
                .rotate_x(deg(90.0))
                .translate(0.0, A3, 0.27),
                p.white,
            ),
        )
        add(
            j3,
            Node.mesh(
                Geometry.torus(0.11, 0.012, 10, 64).translate(0.0, A3, 0.535).rotate_x(0.0),
                p.graphite,
            ),
        )
        leds = Geometry.merge(
            [
                Geometry.sphere(0.007, 12, 6).translate(0.0, A3 + F(0.12), F(0.2) + F(i) * F(0.03))
                for i in range(3)
            ]
        )
        add(j3, Node.mesh(leds, Material.standard(0x111111).emissive(0x7DFFB0, 3.0)))
        warning(scene, j3, p, v(0.118, A3 + F(0.02), 0.35), Vec3.X, 0.035)

        # J4: the wrist roll.
        j4 = add(j3, Node.group())
        add(
            j4,
            Node.mesh(
                Geometry.torus(0.1, 0.01, 10, 64).translate(0.0, 0.0, -0.06).rotate_x(0.0),
                p.graphite,
            ),
        )
        add(
            j4,
            Node.mesh(
                Geometry.cylinder(0.095, 0.1, 0.24, 64)
                .rotate_x(deg(90.0))
                .translate(0.0, 0.0, 0.06),
                p.white,
            ),
        )
        add(
            j4,
            Node.mesh(
                Geometry.torus(0.092, 0.008, 8, 64).rotate_x(deg(90.0)).translate(0.0, 0.0, 0.19),
                p.graphite,
            ),
        )
        add(j4, Node.mesh(bolt_circle(8, 0.075, 0.006, v(0.0, 0.0, 0.18), Vec3.Z), p.chrome))
        fork = hull([((0.2, 0.0), 0.06), ((L3 - J4_AT, 0.0), 0.075)])
        for x in (-0.085, 0.085):
            add(j4, Node.mesh(side_plate(fork, 0.03, 0.008, x), p.graphite))

        # J5: the wrist pitch.
        j5 = add(j4, Node.group())
        add(j5, Node.mesh(axle(0.065, 0.14, 0.0, 0.0, 0.0), p.white))
        for x in (F(-0.104), F(0.104)):
            add(j5, Node.mesh(axle(0.045, 0.012, x, 0.0, 0.0), p.chrome))
            add(
                j5,
                Node.mesh(
                    bolt_circle(5, 0.032, 0.005, v(x * F(1.08), 0.0, 0.0), Vec3.X * signum(x)),
                    p.dark,
                ),
            )
        add(
            j5,
            Node.mesh(
                Geometry.cylinder(0.055, 0.06, 0.13, 48)
                .rotate_x(deg(90.0))
                .translate(0.0, 0.0, 0.08),
                p.white,
            ),
        )

        # J6: the tool flange, the gripper and the camera eye.
        j6 = add(j5, Node.group())
        add(
            j6,
            Node.mesh(
                Geometry.cylinder(0.068, 0.068, 0.022, 48)
                .rotate_x(deg(90.0))
                .translate(0.0, 0.0, 0.011),
                p.chrome,
            ),
        )
        add(j6, Node.mesh(bolt_circle(6, 0.05, 0.007, v(0.0, 0.0, 0.022), Vec3.Z), p.dark))
        add(
            j6,
            Node.mesh(
                Geometry.cylinder(0.058, 0.058, 0.03, 48)
                .rotate_x(deg(90.0))
                .translate(0.0, 0.0, 0.04),
                p.graphite,
            ),
        )
        add(
            j6,
            Node.mesh(
                Geometry.torus(0.058, 0.004, 6, 48).rotate_x(deg(90.0)).translate(0.0, 0.0, 0.056),
                p.chrome,
            ),
        )
        add(
            j6,
            Node.mesh(
                Geometry.rounded_box(0.26, 0.085, 0.08, 0.02, 3).translate(0.0, 0.0, 0.104),
                p.graphite,
            ),
        )
        for y in (0.035, -0.035):
            add(
                j6,
                Node.mesh(
                    Geometry.rounded_box(0.24, 0.016, 0.014, 0.005, 1).translate(0.0, y, 0.15),
                    p.chrome,
                ),
            )
        screws = Geometry.merge(
            [
                rod(0.006, 0.006, v(x, -0.044, 0.104), Vec3.NEG_Y, 6)
                for x in (-0.1, -0.05, 0.05, 0.1)
            ]
        )
        add(j6, Node.mesh(screws, p.chrome))
        for x in (F(-0.07), F(0.07)):
            add(j6, Node.mesh(rod(0.011, 0.03, v(x, -0.05, 0.08), Vec3.NEG_Y, 12), p.chrome))
            hose = Geometry.tube(
                [
                    v(x, -0.06, 0.08),
                    v(x * F(0.8), -0.1, 0.03),
                    v(x * F(0.4), -0.1, -0.05),
                    v(0.0, -0.08, -0.12),
                ],
                0.007,
                8,
            )
            add(j6, Node.mesh(hose, p.rubber))
        status = add(
            j6,
            Node.mesh(
                Geometry.sphere(0.008, 16, 8).translate(0.11, -0.043, 0.09),
                Material.standard(0x111111).emissive(0xFF4A00, 0.0),
            ),
        )
        ex, ey, ez = EYE
        cam = Geometry.rounded_box(0.11, 0.06, 0.09, 0.018, 3).translate(
            ex, ey - F(0.002), ez - F(0.04)
        )
        add(j6, Node.mesh(cam, p.white))
        add(
            j6,
            Node.mesh(
                Geometry.cylinder(0.026, 0.03, 0.03, 40)
                .rotate_x(deg(90.0))
                .translate(ex, ey, ez + F(0.015)),
                p.graphite,
            ),
        )
        add(
            j6,
            Node.mesh(
                Geometry.torus(0.024, 0.004, 8, 40).translate(ex, ey, ez + F(0.03)), p.chrome
            ),
        )
        add(
            j6,
            Node.mesh(
                Geometry.sphere_partial(0.021, 32, 12, 0.0, deg(60.0))
                .rotate_x(deg(90.0))
                .translate(ex, ey, ez + F(0.02)),
                p.glass,
            ),
        )
        iris = add(
            j6,
            Node.mesh(
                Geometry.circle(0.008, 24), Material.standard(0x111111).emissive(0xFFB070, 0.0)
            ).at(ex, ey, ez + F(0.0325)),
        )
        lid = add(
            j6,
            Node.mesh(Geometry.rounded_box(0.056, 0.03, 0.006, 0.003, 1), p.graphite).at(
                ex, ey + F(0.03), ez + F(0.036)
            ),
        )
        lens = v(ex, ey, ez + F(0.034))
        eye_light = add(
            j6,
            Node.light(
                td.Light.spot(EYE_LIGHT, 0.0, deg(17.0), 0.55).pointing(Vec3.Z)
            ).with_position(lens),
        )
        from effects import beam as beam_geometry

        beam_node = add(
            j6,
            Node.mesh(beam_geometry(2.6, 0.8), Material.glow(EYE_LIGHT, 0.0))
            .with_position(lens)
            .shadows(False, False),
        )
        fingers = []
        for x in (F(-1.0), F(1.0)):
            finger = add(j6, Node.group())
            add(
                finger,
                Node.mesh(
                    Geometry.rounded_box(0.03, 0.06, 0.07, 0.008, 2).translate(
                        x * F(0.015), 0.0, 0.155
                    ),
                    p.graphite,
                ),
            )
            add(
                finger,
                Node.mesh(
                    Geometry.rounded_box(0.024, 0.055, 0.12, 0.007, 2).translate(
                        x * F(0.012), 0.0, 0.215
                    ),
                    p.white,
                ),
            )
            add(
                finger,
                Node.mesh(
                    Geometry.rounded_box(0.008, 0.05, 0.06, 0.003, 1).translate(
                        -x * F(0.003), 0.0, 0.245
                    ),
                    p.rubber,
                ),
            )
            bolts = Geometry.merge(
                [rod(0.005, 0.004, v(x * F(0.031), 0.0, z), Vec3.X * x, 6) for z in (0.14, 0.17)]
            )
            add(finger, Node.mesh(bolts, p.chrome))
            fingers.append(finger)

        # The gas spring from the turret to the upper arm.
        spring_body = scene.add(Node.group())
        add(
            spring_body,
            Node.mesh(
                Geometry.cylinder(0.045, 0.045, 0.42, 32).translate(0.0, 0.21, 0.0), p.graphite
            ),
        )
        add(
            spring_body,
            Node.mesh(Geometry.torus(0.046, 0.005, 6, 32).translate(0.0, 0.4, 0.0), p.chrome),
        )
        add(spring_body, Node.mesh(Geometry.sphere(0.05, 24, 12), p.chrome))
        spring_rod = scene.add(Node.group())
        add(
            spring_rod,
            Node.mesh(
                Geometry.cylinder(0.018, 0.018, 0.45, 16).translate(0.0, 0.225, 0.0), p.chrome
            ),
        )
        add(spring_rod, Node.mesh(Geometry.sphere(0.035, 24, 12), p.chrome))

        self.joints = [j1, j2, j3, j4, j5, j6]
        self.fingers = fingers
        self.spring_body, self.spring_rod = spring_body, spring_rod
        self.status, self.ring, self.iris, self.lid = status, ring, iris, lid
        self.eye_light, self.beam, self.ring_light = eye_light, beam_node, ring_light

    def apply(self, scene: td.Scene, q, gap, face: Expression):
        """Poses the arm in `scene`: joints, finger gap and face."""
        for node, local in zip(self.joints, chain(q)):
            _, rotation, translation = local.to_scale_rotation_translation()
            scene.set_position(node, translation)
            scene.set_rotation(node, rotation)
        gap = clamp(gap, 0.0, OPEN)
        scene.set_position(self.fingers[0], (-gap, 0.0, 0.0))
        scene.set_position(self.fingers[1], (gap, 0.0, 0.0))
        a = scene.local_to_world(self.joints[0], (0.0, 0.16, -0.27))
        b = scene.local_to_world(self.joints[1], (0.0, 0.42, -0.19))
        d = (b - a).normalize_or(Vec3.Y)
        scene.set_position(self.spring_body, a)
        scene.set_rotation(self.spring_body, Quat.from_rotation_arc(Vec3.Y, d))
        scene.set_position(self.spring_rod, b)
        scene.set_rotation(self.spring_rod, Quat.from_rotation_arc(Vec3.Y, -d))
        scene.set_emissive_intensity(self.ring, face.ring)
        scene.set_emissive_intensity(self.status, face.status)
        scene.set_emissive_intensity(self.iris, face.eye)
        lid = clamp(face.lid, 0.0, 1.0)
        ex, ey, ez = EYE
        scene.set_scale(self.iris, (1.0, max(lid, F(0.05)), 1.0))
        scene.set_position(self.lid, (ex, ey + F(0.012) + F(0.018) * lid, ez + F(0.036)))
        scene.set_scale(self.lid, (1.0, F(1.0) - F(0.7) * lid, 1.0))
        eye = F(face.eye) * lid
        scene.set_light_intensity(self.eye_light, eye * F(0.55))
        scene.set_light_intensity(self.ring_light, F(face.ring) * F(0.08))
        beam = eye * F(face.beam)
        scene.set_visible(self.beam, bool(beam > 0.0))
        scene.set_color(self.beam, BEAM_COLOR * beam * 0.05)


BEAM_COLOR = td.Rgb.hex(EYE_LIGHT)

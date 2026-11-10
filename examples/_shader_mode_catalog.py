"""The ShaderLibrary panel wall of shader_mode: textured cards in camera space.

Geometry is prepared once per frame in float32, so it matches the Rust example bit for bit.
"""

import math

import fframes as ff
import numpy as np

F = np.float32
PIXELS_PER_UNIT = F(768.0)
FOCAL = F(1.6) * F(1080.0)
PORTAL_TILE = 85
PORTAL = (F(2605.0), F(1088.0))
FRAMES = 51

# Card rectangles in media/catalog.png.
RECTS = np.array(
    [
        (-175, 5, 438, 114),
        (275, 5, 518, 114),
        (805, 5, 438, 114),
        (1255, 5, 438, 114),
        (1705, 5, 452, 114),
        (2169, 5, 438, 114),
        (2619, 5, 438, 114),
        (3069, 5, 438, 114),
        (3519, 5, 438, 114),
        (3969, 5, 518, 114),
        (-15, 133, 438, 114),
        (435, 133, 438, 114),
        (885, 133, 438, 114),
        (1335, 133, 562, 114),
        (1909, 133, 438, 114),
        (2359, 133, 438, 114),
        (2809, 133, 438, 114),
        (3259, 133, 438, 114),
        (3709, 133, 438, 114),
        (-240, 261, 438, 114),
        (210, 261, 496, 114),
        (718, 261, 438, 114),
        (1168, 261, 438, 114),
        (1618, 261, 438, 114),
        (2068, 261, 438, 114),
        (2518, 261, 438, 114),
        (2968, 261, 438, 114),
        (3418, 261, 438, 114),
        (3868, 261, 496, 114),
        (-80, 389, 438, 114),
        (370, 389, 438, 114),
        (820, 389, 438, 114),
        (1270, 389, 438, 114),
        (1720, 389, 518, 114),
        (2250, 389, 438, 114),
        (2700, 389, 438, 114),
        (3150, 389, 452, 114),
        (3614, 389, 438, 114),
        (4064, 389, 438, 114),
        (-175, 517, 438, 114),
        (275, 517, 438, 114),
        (725, 517, 438, 114),
        (1175, 517, 438, 114),
        (1625, 517, 438, 114),
        (2075, 517, 438, 114),
        (2525, 517, 562, 114),
        (3099, 517, 438, 114),
        (3549, 517, 438, 114),
        (3999, 517, 438, 114),
        (-15, 645, 438, 114),
        (435, 645, 438, 114),
        (885, 645, 438, 114),
        (1335, 645, 438, 114),
        (1785, 645, 496, 114),
        (2293, 645, 438, 114),
        (2743, 645, 438, 114),
        (3193, 645, 438, 114),
        (3643, 645, 438, 114),
        (4093, 645, 438, 114),
        (-240, 773, 438, 114),
        (210, 773, 438, 114),
        (660, 773, 452, 114),
        (1124, 773, 438, 114),
        (1574, 773, 438, 114),
        (2024, 773, 438, 114),
        (2474, 773, 438, 114),
        (2924, 773, 518, 114),
        (3454, 773, 438, 114),
        (3904, 773, 438, 114),
        (-80, 901, 438, 114),
        (370, 901, 562, 114),
        (944, 901, 438, 114),
        (1394, 901, 438, 114),
        (1844, 901, 438, 114),
        (2294, 901, 438, 114),
        (2744, 901, 438, 114),
        (3194, 901, 438, 114),
        (3644, 901, 438, 114),
        (4094, 901, 562, 114),
        (-175, 1029, 438, 114),
        (275, 1029, 438, 114),
        (725, 1029, 438, 114),
        (1175, 1029, 438, 114),
        (1625, 1029, 438, 114),
        (2075, 1029, 438, 114),
        (2525, 1029, 518, 114),
        (3055, 1029, 496, 114),
        (3563, 1029, 438, 114),
        (4013, 1029, 438, 114),
        (-15, 1157, 438, 114),
        (435, 1157, 438, 114),
        (885, 1157, 518, 114),
        (1415, 1157, 438, 114),
        (1865, 1157, 438, 114),
        (2315, 1157, 452, 114),
        (2779, 1157, 438, 114),
        (3229, 1157, 438, 114),
        (3679, 1157, 438, 114),
        (-240, 1285, 438, 114),
        (210, 1285, 438, 114),
        (660, 1285, 438, 114),
        (1110, 1285, 438, 114),
        (1560, 1285, 562, 114),
        (2134, 1285, 438, 114),
        (2584, 1285, 438, 114),
        (3034, 1285, 438, 114),
        (3484, 1285, 438, 114),
        (3934, 1285, 438, 114),
        (-80, 1413, 438, 114),
        (370, 1413, 438, 114),
        (820, 1413, 496, 114),
        (1328, 1413, 438, 114),
        (1778, 1413, 438, 114),
        (2228, 1413, 438, 114),
        (2678, 1413, 438, 114),
        (3128, 1413, 438, 114),
        (3578, 1413, 438, 114),
        (4028, 1413, 438, 114),
        (-175, 1541, 452, 114),
        (289, 1541, 438, 114),
        (739, 1541, 438, 114),
        (1189, 1541, 438, 114),
        (1639, 1541, 438, 114),
        (2089, 1541, 518, 114),
        (2619, 1541, 438, 114),
        (3069, 1541, 438, 114),
        (3519, 1541, 452, 114),
        (3983, 1541, 438, 114),
        (-15, 1669, 438, 114),
        (435, 1669, 438, 114),
        (885, 1669, 438, 114),
        (1335, 1669, 438, 114),
        (1785, 1669, 438, 114),
        (2235, 1669, 438, 114),
        (2685, 1669, 438, 114),
        (3135, 1669, 562, 114),
        (3709, 1669, 438, 114),
        (-240, 1797, 438, 114),
        (210, 1797, 438, 114),
        (660, 1797, 438, 114),
        (1110, 1797, 438, 114),
        (1560, 1797, 438, 114),
        (2010, 1797, 496, 114),
        (2518, 1797, 438, 114),
        (2968, 1797, 438, 114),
        (3418, 1797, 438, 114),
        (3868, 1797, 438, 114),
        (-80, 1925, 518, 114),
        (450, 1925, 438, 114),
        (900, 1925, 438, 114),
        (1350, 1925, 452, 114),
        (1814, 1925, 438, 114),
        (2264, 1925, 438, 114),
        (2714, 1925, 438, 114),
        (3164, 1925, 438, 114),
        (3614, 1925, 518, 114),
    ],
    dtype=F,
)
X, Y, W, H = RECTS.T
INDEX = np.arange(len(RECTS))


def sincos(angle):
    """sinf and cosf, correctly rounded like libm."""
    angle = np.asarray(angle, dtype=np.float64)
    return np.sin(angle).astype(F), np.cos(angle).astype(F)


def add(a, b):
    return tuple(x + y for x, y in zip(a, b))


def sub(a, b):
    return tuple(x - y for x, y in zip(a, b))


def mul(a, s):
    return tuple(x * s for x in a)


def turn(p, a, b, angle):
    s, c = sincos(angle)
    p = list(p)
    p[a], p[b] = c * p[a] - s * p[b], s * p[a] + c * p[b]
    return tuple(p)


def smooth(start, end, value):
    t = np.clip((value - start) / (end - start), F(0.0), F(1.0))
    return t * t * (F(3.0) - F(2.0) * t)


def random(index, salt):
    return ((index * 73 + salt * 151 + index * index * 17) % 997).astype(F) / F(997.0)


class Pose:
    __slots__ = ("center", "down", "right")

    def __init__(self, center, right, down):
        self.center, self.right, self.down = center, right, down

    @staticmethod
    def world(index, frame):
        """The poses of the cards `index` (an array) at `frame`."""
        x, y, w, h = X[index], Y[index], W[index], H[index]
        amount = smooth(F(23.0) + random(index, 1) * F(3.0), F(38.0), frame)
        drift = smooth(F(36.0), F(49.0), frame)

        def r(salt):
            return random(index, salt) * F(2.0) - F(1.0)

        angles = [r(2) * F(0.24), r(3) * F(0.28), r(4) * F(0.060)]
        offset = [r(5) * F(0.042), r(6) * F(0.035), r(7) * F(0.19) - F(0.035)]
        offset[1] = offset[1] + drift * (F(0.018) + random(index, 8) * F(0.035))
        portal = index == PORTAL_TILE
        for k, value in enumerate((0.10, -0.13, 0.045)):
            angles[k] = np.where(portal, F(value), angles[k])
        for k, value in enumerate((-0.01, 0.015, -0.13)):
            offset[k] = np.where(portal, F(value), offset[k])

        def rotate(p):
            p = turn(p, 1, 2, angles[0] * amount)
            p = turn(p, 0, 2, angles[1] * amount)
            return turn(p, 0, 1, angles[2] * amount)

        zero, one = np.zeros_like(x), np.ones_like(x)
        center = add(
            ((x + w * F(0.5)) / PIXELS_PER_UNIT, (y + h * F(0.5)) / PIXELS_PER_UNIT, zero),
            mul(offset, amount),
        )
        return Pose(center, rotate((one, zero, zero)), rotate((zero, one, zero)))

    def point(self, x, y):
        return add(self.center, add(mul(self.right, x), mul(self.down, y)))


class Camera:
    def __init__(self, frame):
        entering = F(1.0) - np.clip(frame / F(18.0), F(0.0), F(1.0))
        entering = entering * entering
        leaving = smooth(F(39.0), F(47.0), frame) * (F(1.0) - smooth(F(48.0), F(50.0), frame))
        if frame < 18.0:
            distance = F(2.25) - F(2.01) * entering
        elif frame < 43.0:
            distance = F(2.25)
        elif frame < 48.0:
            ramp = F(math.pow(float((frame - F(43.0)) / F(5.0)), float(F(1.6))))
            distance = F(2.25) - F(1.80) * ramp
        elif frame < 49.0:
            distance = F(0.45) - F(0.19) * (frame - F(48.0))
        else:
            distance = F(0.26) - F(0.155) * np.clip(frame - F(49.0), F(0.0), F(1.0))
        tile = np.array([PORTAL_TILE])
        x, y, w, h = X[PORTAL_TILE], Y[PORTAL_TILE], W[PORTAL_TILE], H[PORTAL_TILE]
        hero = Pose.world(tile, frame).point(
            (PORTAL[0] - x - w * F(0.5)) / PIXELS_PER_UNIT,
            (PORTAL[1] - y - h * F(0.5)) / PIXELS_PER_UNIT,
        )
        hero = tuple(v[0] for v in hero)
        base = (
            (F(2360.0) - F(100.0) * entering) / PIXELS_PER_UNIT,
            F(1100.0) / PIXELS_PER_UNIT,
            F(0.0),
        )
        target = add(base, mul(sub(hero, base), smooth(F(40.0), F(49.0), frame)))
        self.angles = (
            F(0.20) * entering - F(0.10) * leaving,
            F(-0.48) * entering + F(0.25) * leaving,
            F(0.12) * entering - F(0.025) * leaving,
        )
        forward = turn(turn((F(0.0), F(0.0), F(1.0)), 0, 2, self.angles[1]), 1, 2, self.angles[2])
        self.origin = sub(target, mul(forward, distance))

    def direction(self, p):
        p = turn(p, 1, 2, -self.angles[2])
        p = turn(p, 0, 2, -self.angles[1])
        return turn(p, 0, 1, -self.angles[0])

    def pose(self, pose):
        return Pose(
            self.direction(sub(pose.center, self.origin)),
            self.direction(pose.right),
            self.direction(pose.down),
        )


def project(p):
    return F(960.0) + FOCAL * p[0] / p[2], F(540.0) + FOCAL * p[1] / p[2]


def cards(start, end):
    """The visible cards between `start` and `end`, farthest first: (index, pose, motion, bounds)."""
    pose = Camera(start).pose(Pose.world(INDEX, start))
    last = Camera(end).pose(Pose.world(INDEX, end))
    lo = [np.full(len(INDEX), F(1920.0)), np.full(len(INDEX), F(1080.0))]
    hi = [np.zeros(len(INDEX), F), np.zeros(len(INDEX), F)]
    near = F(0.01)
    with np.errstate(all="ignore"):
        for sample in (pose, last):
            corners = [
                sample.point(F(cx) * W / F(2.0 * 768.0), F(cy) * H / F(2.0 * 768.0))
                for cx, cy in ((-1.0, -1.0), (1.0, -1.0), (1.0, 1.0), (-1.0, 1.0))
            ]
            for i in range(4):
                a, b = corners[i], corners[(i + 1) % 4]
                inside_a, inside_b = a[2] >= near, b[2] >= near
                cut = add(a, mul(sub(b, a), (near - a[2]) / (b[2] - a[2])))
                for valid, point in ((inside_a, a), (inside_a != inside_b, cut)):
                    p = project(point)
                    for axis in range(2):
                        lo[axis] = np.where(valid, np.minimum(lo[axis], p[axis]), lo[axis])
                        hi[axis] = np.where(valid, np.maximum(hi[axis], p[axis]), hi[axis])
    x = np.maximum(np.floor(lo[0] - F(5.0)), F(0.0))
    y = np.maximum(np.floor(lo[1] - F(5.0)), F(0.0))
    w = np.minimum(np.ceil(hi[0] + F(5.0)), F(1920.0)) - x
    h = np.minimum(np.ceil(hi[1] + F(5.0)), F(1080.0)) - y
    visible = np.flatnonzero((w > 0.0) & (h > 0.0))
    visible = visible[np.argsort(-pose.center[2][visible], kind="stable")]
    motion = Pose(
        sub(last.center, pose.center), sub(last.right, pose.right), sub(last.down, pose.down)
    )
    return visible, pose, motion, (x, y, w, h)


CARD = ff.template('<image href="{href}" x="{x}" y="{y}" width="{width}" height="{height}" />')
TITLE = ff.template("""
<g>
    <defs><clipPath id="catalog-portal-title"><path d="{clip}" /></clipPath></defs>
    <text x="960" y="576" text-anchor="middle" clip-path="url(#catalog-portal-title)"
        font-family="DM Sans" font-weight="500" font-size="64" letter-spacing="-1.8"
        fill="#fcf5ff">SkSL + SHADERTOY</text>
</g>
""")
WALL = ff.template('<g><rect width="1920" height="1080" fill="#08080a" />{cards}{title}</g>')


def _vec(v, k):
    return (float(v[0][k]), float(v[1][k]), float(v[2][k]))


class Catalog:
    """Each of the 51 frames is prepared on first use: card bounds and shader uniforms."""

    def __init__(self):
        self.frames = {}

    def prepare(self, index):
        from _f32 import fmt32

        frame = F(index)
        shutter = index < 7 or 44 <= index < 49
        exposure = F(0.35) if shutter else F(0.0)
        visible, pose, motion, (x, y, w, h) = cards(
            max(frame - exposure * F(0.5), F(0.0)), frame + exposure * F(0.5)
        )
        clock = float(F(index * 1001) / F(30000.0))
        progress = float(F(index) / F(51.0))
        cards_ = []
        for k in visible:
            ax, ay, aw, ah = (float(v) for v in RECTS[k])
            uniforms = {
                "uClock": clock,
                "uProgress": progress,
                "uVariant": 0.0,
                "uBeat": 0.0,
                "uShutter": 1.0 if shutter else 0.0,
                "uHero": 1.0 if k == PORTAL_TILE else 0.0,
                "uOrigin": (float(x[k]), float(y[k])),
                "uPortal": (float(PORTAL[0]), float(PORTAL[1])),
                "uAtlas": (ax, ay, aw, ah),
                "uCenter": _vec(pose.center, k),
                "uRight": _vec(pose.right, k),
                "uDown": _vec(pose.down, k),
                "uCenterMotion": _vec(motion.center, k),
                "uRightMotion": _vec(motion.right, k),
                "uDownMotion": _vec(motion.down, k),
            }
            cards_.append((uniforms, float(x[k]), float(y[k]), float(w[k]), float(h[k])))
        title = None
        if index >= 49:
            tile = np.array([PORTAL_TILE])
            portal = Camera(frame).pose(Pose.world(tile, frame))
            tx, ty, tw, th = X[PORTAL_TILE], Y[PORTAL_TILE], W[PORTAL_TILE], H[PORTAL_TILE]
            angle = np.arange(96).astype(F) * F(2.0 * math.pi) / F(96.0)
            sin, cos = sincos(angle)
            px, py = project(
                portal.point(
                    (PORTAL[0] - tx - tw * F(0.5) + F(23.0) * cos) / PIXELS_PER_UNIT,
                    (PORTAL[1] - ty - th * F(0.5) + F(23.0) * sin) / PIXELS_PER_UNIT,
                )
            )
            clip = "".join(
                f"{'M' if i == 0 else 'L'}{fmt32(float(px[i]))} {fmt32(float(py[i]))} "
                for i in range(96)
            )
            title = TITLE(clip=clip + "Z")
        return cards_, title

    def render(self, frame: ff.Frame, ctx: ff.Context, shader: ff.Shader) -> ff.Svgr:
        atlas = ctx.image("catalog.png")
        if atlas is None or frame.index >= FRAMES:
            return ff.Svgr.empty()
        state = self.frames.get(frame.index)
        if state is None:
            state = self.frames[frame.index] = self.prepare(frame.index)
        cards_, title = state
        layers = [
            CARD(href=shader.draw(frame, {**uniforms, "uMask": atlas}), x=x, y=y, width=w, height=h)
            for uniforms, x, y, w, h in cards_
        ]
        return WALL(cards=layers, title=title)

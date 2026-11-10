"""Beat grid, easing, palette and shared HUD pieces of the fframes-intro port.

All arithmetic runs on numpy float32 scalars, so every value matches the Rust f32 code bit for bit
(NumPy 2 keeps `float32 op python-number` in float32).
"""

import ctypes
import math

import fframes as ff
import numpy as np
from _f32 import fmt32

F = np.float32
FPS = 60
BEAT = F(0.454_522)
DOWNBEAT0 = F(2.148_51)
TOTAL_SECONDS = F(127.5)


def s32(x) -> str:
    """`x` as Rust formats an f32 with `{}`."""
    return fmt32(float(x))


def usize(x) -> int:
    """Rust `x as usize`: truncate, saturate at 0."""
    return max(0, int(x))


def beat_time(beat):
    return DOWNBEAT0 + F(beat) * BEAT


def beat_frame(beat) -> int:
    return int(math.floor(float(beat_time(beat) * F(FPS)) + 0.5))


def gsec(frame):
    return F(frame.global_index) / F(FPS)


def gbeat(frame):
    return (gsec(frame) - DOWNBEAT0) / BEAT


def span_frames(start, end) -> int:
    a = 0 if start is None else beat_frame(start)
    b = int(math.floor(float(TOTAL_SECONDS * F(FPS)) + 0.5)) if end is None else beat_frame(end)
    return b - a


def clamp01(x):
    return min(max(F(x), F(0.0)), F(1.0))


def prog(x, a, b):
    return clamp01((F(x) - F(a)) / (F(b) - F(a)))


def lerp(a, b, t):
    return F(a) + (F(b) - F(a)) * F(t)


def expo_out(t):
    t = clamp01(t)
    return F(1.0) if t >= 1.0 else F(1.0) - F(2.0 ** float(F(-10.0) * t))


def expo_in(t):
    t = clamp01(t)
    return F(0.0) if t <= 0.0 else F(2.0 ** float(F(10.0) * t - F(10.0)))


def powi3(x):
    return x * x * x


def cubic_in_out(t):
    t = clamp01(t)
    if t < 0.5:
        return F(4.0) * t * t * t
    return F(1.0) - powi3(F(-2.0) * t + F(2.0)) / F(2.0)


def quart_out(t):
    u = F(1.0) - clamp01(t)
    u2 = u * u
    return F(1.0) - u2 * u2


def exp32(x):
    return F(math.exp(float(x)))


def spring(t, stiffness, damping):
    t = F(t)
    if t <= 0.0:
        return F(0.0)
    w0 = F(math.sqrt(float(F(stiffness))))
    zeta = F(damping) / (F(2.0) * w0)
    if zeta < 1.0:
        wd = w0 * F(math.sqrt(float(F(1.0) - zeta * zeta)))
        a = F(math.cos(float(wd * t)))
        b = F(math.sin(float(wd * t)))
        return F(1.0) - exp32(-zeta * w0 * t) * (a + zeta * w0 / wd * b)
    return F(1.0) - (F(1.0) + w0 * t) * exp32(-w0 * t)


def snap(beats):
    return spring(F(beats) * BEAT, 320.0, 22.0)


def soft(beats):
    return spring(F(beats) * BEAT, 170.0, 15.0)


def pulse(beat, sharpness):
    beat = F(beat)
    return exp32(-(beat - F(math.floor(beat))) * F(sharpness))


# Rust f32::sin is the C library sinf; for large arguments it can differ by one ulp from a
# rounded double sin, which the 43758 factor of the hash makes visible.
_libm = ctypes.CDLL(None)
_libm.sinf.argtypes = [ctypes.c_float]
_libm.sinf.restype = ctypes.c_float
_libm.cosf.argtypes = [ctypes.c_float]
_libm.cosf.restype = ctypes.c_float
sinf = np.frompyfunc(_libm.sinf, 1, 1)


def sin32(x):
    """Rust `f32::sin`."""
    return F(_libm.sinf(F(x)))


def cos32(x):
    """Rust `f32::cos`."""
    return F(_libm.cosf(F(x)))


def hash32(n):
    x = F(_libm.sinf(F(n) * F(127.1) + F(311.7))) * F(43_758.547)
    return x - F(math.floor(x))


def hash_array(n):
    """`hash32` over a float32 array."""
    x = sinf(n * F(127.1) + F(311.7)).astype(F) * F(43_758.547)
    return x - np.floor(x)


def fract(x):
    return x - F(math.trunc(float(x)))


def rem_euclid(a, b):
    r = F(math.fmod(float(a), float(b)))
    return r + F(abs(float(b))) if r < 0 else r


# --- palette and type

BG = "#0b0b0b"
BONE = "#ece8e1"
ORANGE = "#fb6a22"
EMBER = "#8a3712"
GREY = "#76726c"
DIM = "#2b2926"
PAPER = "#e8e4db"
INK = "#121110"

DISPLAY = "Archivo Black"
COND = "Anton"
MONO = "IBM Plex Mono"
SERIF = "Instrument Serif"

CONSTS = {
    "BG": BG, "BONE": BONE, "ORANGE": ORANGE, "EMBER": EMBER, "GREY": GREY, "DIM": DIM,
    "PAPER": PAPER, "INK": INK, "DISPLAY": DISPLAY, "COND": COND, "MONO": MONO, "SERIF": SERIF,
}  # fmt: skip


def T(markup: str):
    """A template whose upper-case holes are filled from the palette, like Rust `{CONST}` holes."""
    template = ff.template(markup)
    fixed = {k: v for k, v in CONSTS.items() if k in template.holes}
    return lambda **values: template(**fixed, **values)


def text(value: str):
    return ff.Svgr.text(value)


_WIDTHS: dict = {}


def measure(frame, ctx, family, size, weight, italic, value) -> float:
    """Width of a string in pixels as f32, measured once per (font, text) and cached."""
    key = (family, size, weight, italic, value)
    width = _WIDTHS.get(key)
    if width is not None:
        return width
    w = frame.text_width(
        ctx, value, family=family, size=size, weight=weight, style="italic" if italic else "normal"
    )
    if w is None:
        return F(len(value)) * F(size) * F(0.6)
    _WIDTHS[key] = F(w)
    return _WIDTHS[key]


CORNERS = T('<path d="{d}" fill="none" stroke="{color}" stroke-width="{width}" />')


def corners(x, y, w, h, arm, color, width):
    x, y, w, h, arm = F(x), F(y), F(w), F(h), F(arm)
    x1, x2, x3 = x + arm, x + w - arm, x + w
    y1, y2, y3 = y + arm, y + h - arm, y + h
    x, y, x1, x2, x3, y1, y2, y3 = map(s32, (x, y, x1, x2, x3, y1, y2, y3))
    d = (
        f"M{x} {y1} V{y} H{x1} M{x2} {y} H{x3} V{y1} M{x3} {y2} V{y3} H{x2} M{x1} {y3} H{x} V{y2}"
    )
    return CORNERS(d=d, color=color, width=float(F(width)))


LABEL = T(
    '<text x="{x}" y="{y}" font-family="{MONO}" font-weight="500" font-size="{size}" '
    'letter-spacing="2.5" fill="{color}" text-anchor="{anchor}">{text}</text>'
)


def label(x, y, value, color, size, anchor):
    return LABEL(
        x=float(F(x)), y=float(F(y)), size=float(F(size)), color=color, anchor=anchor,
        text=text(value),
    )  # fmt: skip


CALLOUT = T("""
<g>
    <circle cx="{tx}" cy="{ty}" r="5" fill="{color}" opacity="{dot}" />
    <circle cx="{tx}" cy="{ty}" r="12" fill="none" stroke="{color}" stroke-width="1.5" opacity="{ring}" />
    <path d="{path}" fill="none" stroke="{color}" stroke-width="1.5" stroke-dasharray="{dash}" />
    <text x="{text_x}" y="{text_y}" font-family="{MONO}" font-weight="500" font-size="20" letter-spacing="2"
          fill="{color}" text-anchor="{anchor}" opacity="{text_opacity}">{text}</text>
</g>
""")


def callout(tx, ty, lx, ly, value, color, progress):
    if progress <= 0.0:
        return None
    tx, ty, lx, ly = F(tx), F(ty), F(lx), F(ly)
    p = min(max(F(progress), F(0.0)), F(1.0))
    mx, my = lx, ty
    l1 = abs(mx - tx) + F(0.01)
    l2 = abs(ly - my) + F(0.01)
    total = l1 + l2
    drawn = total * p
    return CALLOUT(
        tx=float(tx), ty=float(ty), color=color, dot=float(min(p, F(1.0))), ring=float(p * F(0.6)),
        path=f"M{s32(tx)} {s32(ty)} H{s32(mx)} V{s32(ly)}", dash=f"{s32(drawn)} {s32(total)}",
        text_x=float(lx + F(10.0) if lx >= tx else lx - F(10.0)), text_y=float(ly + F(6.0)),
        anchor="start" if lx >= tx else "end",
        text_opacity=float(min(max((p - F(0.6)) / F(0.4), F(0.0)), F(1.0))), text=text(value),
    )  # fmt: skip


def timecode(seconds) -> str:
    total = usize(max(F(seconds) * F(60.0), F(0.0)))
    return f"00:{total // 3600:02}:{(total // 60) % 60:02}:{total % 60:02}"


def thousands(n: int) -> str:
    return f"{n:,}"


LETTER = T(
    '<text transform="{t}" font-family="{family}" font-weight="{weight}" font-size="{size}" '
    'fill="{fill}" opacity="{opacity}">{ch}</text>'
)
GROUP = T("<g>{content}</g>")


def letters(frame, ctx, x, y, value, family, size, weight, fill, tracking, f):
    """Text drawn letter by letter; `f(i) -> (dx, dy, opacity, scale)` for every character."""
    out = []
    for i, c in enumerate(value):
        px = measure(frame, ctx, family, size, weight, False, value[:i]) + F(tracking) * F(i)
        dx, dy, o, s = f(i)
        if o <= 0.001:
            continue
        cw = measure(frame, ctx, family, size, weight, False, c)
        cx = F(x) + px + cw / F(2.0)
        t = (
            f"translate({s32(cx + dx)} {s32(F(y) + dy)}) scale({s32(max(s, F(0.001)))}) "
            f"translate({s32(-cw / F(2.0))} 0)"
        )
        out.append(
            LETTER(t=t, family=family, weight=weight, size=size, fill=fill, opacity=float(o), ch=text(c))
        )
    return GROUP(content=out)


SLAM = T(
    '<text x="{x}" y="{y}" text-anchor="{anchor}" font-family="{family}" font-style="{style}" '
    'font-size="{size}" letter-spacing="{spacing}" fill="{fill}" opacity="{opacity}">{text}</text>'
)
TRAIL = ((F(0.16), EMBER, F(0.35)), (F(0.10), "#c4531c", F(0.5)), (F(0.05), ORANGE, F(0.65)))


class Slam:
    """A word that slams in with a spring and leaves a trail of ember copies while it moves."""

    def __init__(self, x, y, value, family, size, fill):
        self.x, self.y, self.text, self.family = F(x), F(y), value, family
        self.size, self.fill = F(size), fill
        self.spacing = -self.size * F(0.035)
        self.anchor = "start"
        self.italic = False

    def anchored(self, anchor):
        self.anchor = anchor
        return self

    def italicized(self):
        self.italic = True
        self.spacing = F(0.0)
        return self

    def draw(self, since, dx, dy):
        since, dx, dy = F(since), F(dx), F(dy)
        if since < 0.0:
            return None

        def off(t):
            s = snap(max(t, F(0.0)))
            return (F(1.0) - s) * dx, (F(1.0) - s) * dy

        style = "italic" if self.italic else "normal"
        node = text(self.text)

        def layer(ox, oy, fill, opacity):
            return SLAM(
                x=float(self.x + ox), y=float(self.y + oy), anchor=self.anchor, family=self.family,
                style=style, size=float(self.size), spacing=float(self.spacing), fill=fill,
                opacity=float(opacity), text=node,
            )  # fmt: skip

        layers = []
        cx, cy = off(since)
        for lag, color, o in TRAIL:
            ox, oy = off(since - lag)
            moving = F(math.sqrt(float((ox - cx) * (ox - cx) + (oy - cy) * (oy - cy))))
            if moving > 2.0 and since > lag * F(0.5):
                layers.append(layer(ox, oy, color, o * min(moving / F(40.0), F(1.0))))
        layers.append(layer(cx, cy, self.fill, prog(since, 0.0, 0.06)))
        return GROUP(content=layers)

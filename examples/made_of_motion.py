"""Port of fframes/examples/made-of-motion: a 489-frame analog / pixel collage film.

Needs the final media in fframes/examples/made-of-motion/dynamic_media (portrait-clean.mp4,
soundtrack.wav); see that example's README.md.

python examples/made_of_motion.py render -o made-of-motion.mp4
python examples/made_of_motion.py --ink-only frame 4s -o frames
"""

import argparse
import gzip
import math
import sys
from pathlib import Path
from typing import NamedTuple

import _made_of_motion_capture as capture
import _made_of_motion_objects as objects
import _media
import fframes as ff
import numpy as np
from _f32 import fmt32
from fframes import Easing, Transform

F = np.float32
EXAMPLE = "made-of-motion"
SOURCE = _media.ROOT / "examples" / EXAMPLE / "src"
QUESTION = "how do you turn a few lines of code into a feeling?"


def shader(name: str) -> ff.Shader:
    return ff.Shader.sksl((SOURCE / "shaders" / name).read_text())


def rem_euclid(a, b):
    r = F(math.fmod(a, b))
    return r + F(abs(b)) if r < 0 else r


# Source frame boundaries (end exclusive), aligned to the music edit.
EDIT = (
    ("Question", 48, "question"),
    ("Signal", 93, "signal"),
    ("Portrait", 153, "portrait"),
    ("ThermalCut", 157, "thermal"),
    ("Orbit", 200, "ring"),
    ("Code", 220, "code"),
    ("CarouselA", 237, "carousel"),
    ("Motion", 253, "motion"),
    ("CarouselB", 265, "carousel"),
    ("Feeling", 286, "feeling"),
    ("OrbitReturn", 302, "ring"),
    ("Scatter", 331, "scatter"),
    ("Human", 382, "hand"),
    ("M", 389, ("pulse", 0)),
    ("O", 397, ("pulse", 1)),
    ("V", 403, ("pulse", 2)),
    ("E", 413, ("pulse", 3)),
    ("Fframes", 489, "signature"),
)

IMAGE = ff.template('<image href="{layer}" width="1440" height="1080" />')
PLACED = ff.template('<image href="{layer}" x="{x}" y="{y}" width="{width}" height="{height}" />')
GROUP = ff.template("<g>{content}</g>")
FADE = ff.template('<g opacity="{opacity}">{content}</g>')
MOVE = ff.template('<g transform="{transform}">{content}</g>')
LABEL = ff.template(
    '<text x="{x}" y="{y}" font-family="Inter 24pt" font-weight="700" font-size="{size}"'
    ' letter-spacing="-1.25" fill="{color}" text-anchor="{anchor}">{copy}</text>'
)


def label(copy, x, y, size, color, center):
    return LABEL(
        x=float(F(x)),
        y=float(F(y)),
        size=float(F(size)),
        color=color,
        anchor="middle" if center else "start",
        copy=copy,
    )


# --- Vector ink: per-exposure contours, measured at the reference's native cadence.

PIGMENTS = (
    "#0a0907", "#40220f", "#c91c14", "#fffbea", "#ff2414", "#ffd155", "#c91c14", "#c91c14",
    "#c91c14", "#c91c14", "#b91613",
)  # fmt: skip
INK_PATH = ff.template('<path d="{d}" fill="{fill}" fill-rule="evenodd" opacity="{opacity}"/>')
INK = ff.template("<g>{base}{marks}</g>")
GATHER_SCALE = ff.timeline(
    ((2.541667, 2.666667), Transform.scale(1.0), Transform.scale(2.8), Easing.EASE_IN)
)
INK_FADE = ff.timeline(((2.541667, 2.708333), 1.0, 0.0, Easing.EASE_OUT))
PULLBACK = ff.timeline(
    (
        (2.666667, 2.833333),
        Transform.scale(1.0),
        Transform.scale(1.0 / 2.8),
        Easing.cubic_bezier(0.12, 0.92, 0.20, 1.0),
    )
)
LETTER_MARK = ff.template("""
<g transform="{position}">
    <g transform="{scale}">
        <g transform="{origin}">{shape}</g>
    </g>
</g>
""")
SIGNATURE_INK = ff.template("""
<g>
    <g opacity="{fade}">{base}</g>
    <g transform="translate(720 540)">
        <g transform="{pullback}">
            <g transform="translate(-720 -540)">{marks}</g>
        </g>
    </g>
</g>
""")


class VectorInk:
    """Soft ink as stacks of translucent outlines, decompressed once."""

    def __init__(self):
        frames = [[] for _ in range(489)]
        marks = [[[] for _ in range(4)] for _ in range(489)]
        for chunk in ("000", "100", "200", "300", "400"):
            text = gzip.decompress((SOURCE / "vector_ink" / f"{chunk}.paths.gz").read_bytes())
            for line in text.decode().splitlines():
                fields = line.split("|", 3)
                if len(fields) < 4 or not fields[0].isdigit() or not fields[1].isdigit():
                    continue
                index, pigment = int(fields[0]), int(fields[1])
                if pigment >= len(PIGMENTS) or index >= 489:
                    continue
                path = INK_PATH(d=fields[3], fill=PIGMENTS[pigment], opacity=float(F(fields[2])))
                if 6 <= pigment < 10:
                    marks[index][pigment - 6].append(path)
                else:
                    frames[index].append(path)
        self.frames = [ff.Svgr.concat(paths) for paths in frames]
        self.letter_marks = [[ff.Svgr.concat(paths) for paths in four] for four in marks]
        self.drawn = [INK(base=self.frames[i], marks=self.letter_marks[i]) for i in range(489)]

    def draw(self, frame):
        index = frame.global_index
        return self.drawn[index] if index < 489 else INK(base=None, marks=None)

    def draw_signature(self, frame, letters):
        """Source nib shapes through the seven brand flights and the final camera pullback."""
        n = min(frame.global_index, 488)
        source = capture.LETTERS[min(max(n - 413, 0), len(capture.LETTERS) - 1)]
        scale = frame.animate(GATHER_SCALE)
        marks = []
        for i, letter in enumerate(letters):
            sx, sy = source[i % 4]
            x, y = letter.position
            marks.append(
                LETTER_MARK(
                    position=Transform.translate(float(x), float(y)),
                    scale=scale,
                    origin=Transform.translate(float(-F(sx)), float(-F(sy))),
                    shape=self.letter_marks[n][i % 4],
                )
            )
        return SIGNATURE_INK(
            fade=frame.animate(INK_FADE),
            base=self.frames[n],
            pullback=frame.animate(PULLBACK),
            marks=marks,
        )


# --- Ink: dust and collision illumination.

DUST = ff.template('<circle cx="{x}" cy="{y}" r="{r}" fill="{fill}" opacity="0.32" />')


def dust(frame, light):
    t = F(frame.global_index) / F(24.0)
    fill = "#ded7c9" if light else "#2c2825"
    particles = []
    for i in range(10):
        p = F(i)
        x = F(135.0) + rem_euclid(p * F(431.0) + t * (F(11.0) + p), F(1170.0))
        y = F(110.0) + rem_euclid(p * F(197.0) - t * (F(5.0) + p * F(2.0)), F(860.0))
        particles.append(DUST(x=float(x), y=float(y), r=1.7 if i % 3 == 0 else 0.8, fill=fill))
    return GROUP(content=particles)


QUESTION_MOVE = ff.timeline(
    (
        (1.125, 1.291667),
        Transform(),
        Transform(translate=(206.125, -3.0), scale=(0.875, 1.0)),
        Easing.EASE_IN_OUT,
    ),
    (
        (1.458333, 1.541667),
        Transform(translate=(206.125, -3.0), scale=(0.875, 1.0)),
        Transform(),
        Easing.EASE_IN,
    ),
)


class Ink:
    def __init__(self, impacts):
        self.impact_shader = shader("impact.sksl")
        self.impacts = impacts
        self.vectors = VectorInk()

    def impacts_at(self, frame):
        bursts = []
        for hit in self.impacts:
            age = F(frame.global_index) - F(hit.at)
            if not 0.0 <= age < 7.0:
                continue
            layer = self.impact_shader.draw(
                frame,
                {
                    "uAge": float(age),
                    "uSeed": float(hit.at),
                    "uDirection": (float(hit.direction[0]), float(hit.direction[1])),
                },
            )
            x, y = hit.position
            bursts.append(
                PLACED(
                    layer=layer,
                    x=float(x - F(170.0)),
                    y=float(y - F(170.0)),
                    width="340",
                    height="340",
                )
            )
        return GROUP(content=bursts)

    def draw(self, frame):
        return self.vectors.draw(frame)

    def draw_question(self, frame):
        """Retarget the reference's "you're" loop to "code" in the opening copy."""
        return MOVE(transform=frame.animate(QUESTION_MOVE), content=self.vectors.draw(frame))


# --- Opening typography: source-timed rulers, lateral camera moves and selection collapse.


def prefix(count):
    spaces = [i for i, ch in enumerate(QUESTION) if ch == " "]
    nth = max(count - 1, 0)
    return QUESTION[: spaces[nth]] if nth < len(spaces) else QUESTION


SELECTION = ff.template("""
<g opacity="{opacity}">
    <path d="{rule}" stroke="#553424" stroke-width="2.3" stroke-dasharray="6 7" fill="none"/>
    <path d="{caps}" stroke="#38241b" stroke-width="6" fill="none"/>
</g>
""")
FLASHES = {
    1: ff.svgr('<rect width="1440" height="1080" fill="#ce101c"/>'),
    2: ff.svgr('<rect width="1440" height="1080" fill="#e8b900"/>'),
}
WIDE_RULERS = ff.svgr(
    '<path d="M0 108 H1440 M0 957 H1440" fill="none" stroke="#654020" stroke-width="8"'
    ' stroke-dasharray="44 44"/>'
)
RULERS = ff.template(
    '<path d="M0 444 H1440 M0 620 H1440" fill="none" stroke="#633b25" stroke-width="4"'
    ' stroke-dasharray="44 44" stroke-dashoffset="{offset}" opacity="0.86"/>'
)
TYPE_PATH = (SOURCE / "opening-type.path").read_text()
TYPE = ff.template('<g>{rulers}<path d="{d}" fill="#211914"/></g>')
CURSORS = {
    8: ff.svgr('<rect x="506" y="369" width="934" height="257" fill="#191716"/>'),
    9: ff.svgr('<rect x="890" y="369" width="456" height="257" fill="#191716"/>'),
    10: ff.svgr('<rect x="1252" y="369" width="9" height="257" fill="#38241b"/>'),
}
PAN = ff.timeline(
    ((0.208333, 0.25), Transform.translate(421, 0), Transform.translate(366, 0), Easing.LINEAR),
    ((0.25, 0.291667), Transform.translate(366, 0), Transform.translate(-125, 0), Easing.LINEAR),
    (
        (0.291667, 0.375),
        Transform.translate(-125, 0),
        Transform.translate(-176, 0),
        Easing.EASE_OUT,
    ),
    ((0.375, 0.416667), Transform.translate(-176, 0), Transform.translate(-500, 0), Easing.LINEAR),
    (
        (0.416667, 0.458333),
        Transform.translate(-500, 0),
        Transform.translate(-705, 0),
        Easing.EASE_OUT,
    ),
    ((0.458333, 0.5), Transform.translate(-705, 0), Transform.translate(-722, 0), Easing.EASE_OUT),
)
OPENING = ff.template("""
<g>
    {flash}{rulers}
    <g transform="{pan}">
        <g transform="{zoom}">{copy}</g>
    </g>
    {cursor}
</g>
""")
TALL = Transform(translate=(0.0, 1130.0), scale=(6.0, 30.0))
WIDE = Transform(translate=(0.0, 620.0), scale=(6.0, 6.5))
COLLAPSE = ff.template("""
<g>
    <defs>
        <filter id="opening-focus" x="-20%" y="-100%" width="140%" height="300%">
            <feGaussianBlur stdDeviation="{blur}"/>
        </filter>
    </defs>
    <g filter="url(#opening-focus)" opacity="0.82">
        <path d="{streaks}" fill="none" stroke="#211914" stroke-width="13" stroke-linecap="round"/>
        <path d="{cursor}" fill="none" stroke="#38241b" stroke-width="12"/>
    </g>
</g>
""")
COLLAPSES = {
    14: (
        "M220 548 L223 516 L240 526 L230 536 L250 550 M281 528 L301 543 M330 526 L344 516 L335 541 M374 523 L365 541 M409 528 L427 544 M465 526 L454 544 M501 529 L511 545 M538 529 L551 543 M578 537 H777 M830 542 L853 530 M881 540 L899 523",
        "M0 0",
        5.0,
    ),
    15: (
        "M144 517 V540 H175 M212 540 H257 M286 540 H302 M329 540 H342 M377 540 H389 M408 540 H430 M500 540 H507 M549 540 H647 M709 540 L723 520 L739 540 H759",
        "M1100 448 H1115 M1107 490 V519 M1107 563 V586",
        4.0,
    ),
    16: (
        "M178 539 H218 M292 539 H303 M325 539 H394 M513 539 H557 M577 539 H587 M628 539 H638 M681 539 H691 M710 539 H733",
        "M905 470 V508 M905 551 V581",
        2.5,
    ),
    17: (
        "M114 539 H122 M143 539 H161 M221 539 H250 M276 539 H292 M320 539 H350 M377 539 H419 M454 539 H472 M491 539 H528 M571 539 H593 M641 539 H659 M686 539 H704",
        "M793 431 H825 M809 472 V494 M809 550 V590",
        4.0,
    ),
}  # fmt: skip


def opening(frame, ctx):
    n = frame.index
    if n >= 18:
        copy = prefix(min(4 + (n - 13) * 8 // 32, 12))
        selection = None
        if n in (18, 19, 20, 22):
            width = frame.text_width(ctx, copy, family="Inter 24pt", size=54, weight=700)
            width = F(450.0) if width is None else F(width) - F(1.25) * F(max(len(copy) - 1, 0))
            right = F(106.25) + width + F(24.0)
            r, lo, hi = fmt32(right), fmt32(right - F(10.0)), fmt32(right + F(10.0))
            selection = SELECTION(
                opacity=0.40 if n == 18 else 0.78 if n == 22 else 0.58,
                rule=f"M82 444 H{r} M82 628 H{r}",
                caps=f"M72 444 H92 M82 444 V628 M72 628 H92 M{lo} 444 H{hi} M{r} 444 V628 M{lo} 628 H{hi}",
            )
        return GROUP(content=[selection, label(copy, 106.25, 554.0, 54.0, "#171611", False)])
    if n >= 14:
        streaks, cursor, blur = COLLAPSES[min(n, 17)]
        return COLLAPSE(blur=blur, streaks=streaks, cursor=cursor)
    count = 1 if n <= 4 else 2 if n <= 7 else 3 if n <= 12 else 4
    copy = prefix(count)
    rulers = WIDE_RULERS if n == 2 else RULERS(offset=float(F(n) * F(3.0))) if n >= 3 else None
    if n == 13:
        return TYPE(rulers=rulers, d=TYPE_PATH)
    return OPENING(
        flash=FLASHES.get(n),
        rulers=rulers,
        pan=frame.animate(PAN),
        zoom=TALL if n == 1 else WIDE,
        copy=label(copy, 0.0, 0.0, 54.0, "#211914", False),
        cursor=CURSORS.get(n),
    )


# --- Flight: reference-derived letter flights of the signature.


class Letter(NamedTuple):
    position: tuple
    angle: float
    scale: float


def flight():
    """Letter poses of the 76 signature frames: three frames to assemble, four to pull back."""
    gather = ff.timeline(((2.541667, 2.666667), 0.0, 1.0, Easing.EASE_IN))
    target = [F(v) for v in (-229.0, -181.0, -124.0, -47.5, 66.0, 167.5, 226.0)]
    last = len(capture.LETTERS) - 1

    def path(index, i):
        phase = rem_euclid(index * (F(0.80) + F(i) * F(0.025)) + F(i) * F(3.1), F(52.0))
        phase = phase if phase <= 26.0 else F(52.0) - phase
        sample = F(3.0) + phase
        a = math.floor(sample)
        b = min(a + 1, last)
        f = sample - F(math.floor(sample))
        aa, bb = capture.LETTERS[a][i % 4], capture.LETTERS[b][i % 4]
        x = F(aa[0]) + (F(bb[0]) - F(aa[0])) * f
        y = F(aa[1]) + (F(bb[1]) - F(aa[1])) * f
        if i >= 4:
            x, y = F(1440.0) - x, F(1080.0) - y
        return (
            F(60.0) + min(max(x, F(0.0)), F(1440.0)) * (F(1320.0) / F(1440.0)),
            F(85.0) + min(max(y, F(0.0)), F(1080.0)) * (F(910.0) / F(1080.0)),
        )

    angles = [F(0.0)] * 7
    letters = []
    for index in range(76):
        g = F(ff.Frame(index, index + 413, 24).animate(gather))
        poses = []
        for i in range(7):
            x, y = path(F(index), i)
            px, py = path(F(index) - F(0.5), i)
            speed = F(math.sqrt((x - px) * (x - px) + (y - py) * (y - py))) * F(2.0)
            direction = F(1.0) if i % 2 == 0 else F(-1.0)
            angles[i] += direction * (speed * F(0.34) + F(3.1))
            margin = F(52.0) + F(270.0) * F(4.0) * g * (F(1.0) - g)
            px = x * (F(1.0) - g) + (F(720.0) + target[i] * F(2.8)) * g
            poses.append(
                Letter(
                    (
                        min(max(px, margin), F(1440.0) - margin),
                        y * (F(1.0) - g) + (F(540.0) + F(39.0) * F(2.8)) * g,
                    ),
                    angles[i] * (F(1.0) - g),
                    (F(1.05) + min(speed / F(170.0), F(0.65))) * (F(1.0) - g)
                    + (F(194.0) / F(54.0) * F(2.8)) * g,
                )
            )
        letters.append(poses)
    return letters


# --- Studio: shaders and prepared choreography, shared by all shots.


class Studio:
    def __init__(self):
        frames, impacts = objects.choreography()
        self.ink = Ink(impacts)
        self.heroes = objects.heroes(frames, capture.CAMERA_POSE)
        self.objects = frames
        self.letters = flight()
        self.paper = shader("paper.sksl")
        self.signal_shader = shader("signal.sksl")
        self.print_shader = shader("print.sksl")
        self.object = shader("object.sksl")
        self.performance_shader = shader("performance.sksl")
        self.hand_shader = shader("hand.sksl")
        self.thermal_shader = shader("thermal_cut.sksl")

    def background(self, frame, mode, vignette):
        return IMAGE(layer=self.paper.draw(frame, {"uMode": mode, "uVignette": vignette}))

    def signal(self, frame):
        n = frame.index
        if n == 0:
            pose = (1240.0, 540.0, 170.0, 670.0, 0.0, 0.42)
        elif n == 1:
            pose = (550.0, 540.0, 680.0, 660.0, 0.17, 0.42)
        elif n == 2:
            pose = (350.0, 540.0, 740.0, 950.0, -0.68, 0.38)
        else:
            pose = capture.STAR[min(n - 3, 37)]
        layer = self.signal_shader.draw(
            frame, {"uPose": tuple(pose[:4]), "uAngle": pose[4], "uPower": pose[5]}
        )
        return IMAGE(layer=layer)

    def print(self, frame, strength):
        return IMAGE(layer=self.print_shader.draw(frame, {"uStrength": strength}))

    def draw_object(self, obj, frame, ctx):
        atlas = ctx.image("objects.png")
        x, y, w, h = obj.bounds
        if atlas is None or w <= 0 or h <= 0:
            return None
        layer = self.object.draw(frame, obj.uniforms(atlas))
        return PLACED(layer=layer, x=float(x), y=float(y), width=float(w), height=float(h))

    def objects_at(self, frame, ctx):
        group = self.objects[min(frame.global_index, 488)]
        return GROUP(content=[self.draw_object(o, frame, ctx) for o in group])

    def performance(self, frame, ctx, file):
        video = frame.video_frame(ctx, file)
        if video is None:
            return self.background(frame, 1.0, 0.0)
        return IMAGE(layer=self.performance_shader.draw(frame, {"uSource": video.image}))

    def hand(self, frame, ctx):
        field = ctx.image("hand-field.png")
        if field is None:
            return self.background(frame, 1.0, 0.0)
        ax, ay, x, y, w, h = capture.HAND[min(frame.index, 50)]
        layer = self.hand_shader.draw(
            frame, {"uField": field, "uAtlas": (ax, ay), "uRect": (x, y, w, h)}
        )
        return IMAGE(layer=layer)

    def thermal_cut(self, frame, ctx):
        layer = self.thermal_shader.draw(frame, {})
        return THERMAL(
            layer=layer, opacity=frame.animate(THERMAL_FADE), objects=self.objects_at(frame, ctx)
        )


THERMAL = ff.template("""
<g>
    <image href="{layer}" width="1440" height="1080" />
    <g opacity="{opacity}">{objects}</g>
</g>
""")
THERMAL_FADE = ff.timeline(((0.0, 0.125), 0.0, 0.94, Easing.EASE_OUT))

# --- Hero cards: the selected ring object in front of the type.

CARD_SLIDE = ff.timeline(
    (
        (0.0, 0.166667),
        Transform.translate(48, 18),
        Transform.translate(0, 0),
        Easing.cubic_bezier(0.12, 1.0, 0.25, 1.0),
    )
)
CURSOR_WIDTH = ff.timeline(((0.0, 0.125), 76.0, 6.0, Easing.EASE_OUT))
SUBTITLE_SLIDE = ff.timeline(
    (
        (0.041667, 0.25),
        Transform.translate(0, 24),
        Transform.translate(0, 0),
        Easing.cubic_bezier(0.16, 1.0, 0.3, 1.0),
    )
)
SUBTITLE_FADE = ff.timeline(((0.041667, 0.166667), 0.0, 1.0, Easing.EASE_OUT))
SUBTITLES = {
    "feeling": ff.svgr("""<g>
        <text x="807" y="617" font-family="Instrument Serif" font-style="italic" font-size="35" fill="#d4cabb">every frame matters.</text>
        <path d="M811 653 C905 641 970 662 1045 647" fill="none" stroke="#ed3d27" stroke-width="2"/>
    </g>"""),
    "code": ff.svgr(
        '<text x="807" y="611" font-family="JetBrains Mono" font-size="23" fill="#bce788">Rust + SVG</text>'
    ),
    "motion": ff.svgr(
        '<text x="807" y="611" font-family="JetBrains Mono" font-size="23" fill="#c0a1ef">timeline!</text>'
    ),
}  # fmt: skip
TYPE_BLOCK = ff.template("""
<g>
    <g transform="{slide}">
        {title}
        <rect x="{cursor}" y="477" height="86" fill="#ed3d27" width="{width}"/>
    </g>
    <g transform="{subtitle_slide}" opacity="{subtitle_fade}">{subtitle}</g>
</g>
""")
CARD_COPY = {
    "code": ("code.", 1120.0),
    "motion": ("motion.", 1256.0),
    "feeling": ("feeling.", 1246.0),
}
HERO = ff.template('<g>{background}{ink}{object}<g opacity="{opacity}">{type}</g></g>')


def type_block(frame, card):
    copy, cursor = CARD_COPY[card]
    return TYPE_BLOCK(
        slide=frame.animate(CARD_SLIDE),
        title=label(copy, 800.0, 559.0, 112.0, "#f4efe4", False),
        cursor=cursor,
        width=frame.animate(CURSOR_WIDTH),
        subtitle_slide=frame.animate(SUBTITLE_SLIDE),
        subtitle_fade=frame.animate(SUBTITLE_FADE),
        subtitle=SUBTITLES[card],
    )


def hero_card(frame, ctx, s, card):
    exposures = s.heroes[card]
    pose = exposures[min(frame.index, len(exposures) - 1)]
    return HERO(
        background=s.background(frame, 1.0, 0.0),
        ink=s.ink.draw(frame),
        object=s.draw_object(pose.object, frame, ctx),
        opacity=pose.title_opacity,
        type=type_block(frame, card),
    )


# --- Shots.

SIGNAL = ff.template("""
<g>
    {signal}
    <g opacity="{opacity}">{objects}</g>
    {ink}
    <text x="720" y="554" font-family="Inter 24pt" font-weight="700" font-size="54"
        letter-spacing="-1.25" fill="{color}" text-anchor="middle">how do <tspan fill="{you}">you</tspan> turn a few lines of code into a feeling?</text>
</g>
""")
SIGNAL_FADE = ff.timeline(((1.25, 1.375), 1.0, 0.0, Easing.EASE_IN))
STACK = ff.template(
    '<g>{background}<ellipse cx="720" cy="535" rx="76" ry="184" fill="url(#stack-light)"/>{stack}</g>'
)
HAND = ff.template('<g>{performance}{ink}{copy}<g opacity="{opacity}">{coda}</g></g>')
HAND_FADE = ff.timeline(((0.416667, 0.625), 0.0, 1.0, Easing.EASE_OUT))
SHOT = ff.template("<g>{content}{dust}{print}</g>")
ORBIT_FADE = ff.timeline(((2.625, 2.666667), 1.0, 0.0, Easing.EASE_OUT))
WORDMARK_FADE = ff.timeline(((2.625, 2.666667), 0.0, 1.0, Easing.EASE_OUT))
WORDMARK_SCALE = ff.timeline(
    (
        (2.666667, 2.833333),
        Transform.scale(2.8),
        Transform.scale(1.0),
        Easing.cubic_bezier(0.12, 0.92, 0.20, 1.0),
    )
)
TAGLINE_FADE = ff.timeline(((2.833333, 3.083333), 0.0, 1.0, Easing.EASE_OUT))
TAGLINE_SLIDE = ff.timeline(
    ((2.833333, 3.083333), Transform.translate(0, 12), Transform.translate(0, 0), Easing.EASE_OUT)
)
ORBIT_LETTER = ff.template("""
<g transform="{transform}">
    <text x="0" y="0" text-anchor="middle" font-family="Instrument Serif" font-style="italic"
          font-size="54" fill="#35221b" stroke="#35221b" stroke-width="0.35">{letter}</text>
</g>
""")
SIGNATURE = ff.template("""
<g>
    {background}
    {ink}
    <g opacity="{orbit_fade}">{orbit}</g>
    <g opacity="{wordmark_fade}">
        <g transform="translate(720 540)">
            <g transform="{wordmark_scale}">
                <text x="0" y="39" text-anchor="middle" font-family="Instrument Serif" font-style="italic"
                      font-size="194" letter-spacing="-5" fill="#24201b">fframes</text>
            </g>
        </g>
        <g opacity="{tagline_fade}" transform="{tagline_slide}">
            <text x="720" y="643" text-anchor="middle" font-family="JetBrains Mono" font-size="19"
                  letter-spacing="1" fill="#4b4136">video, written in code.</text>
            <circle cx="720" cy="703" r="4.5" fill="#eb6c35"/>
        </g>
    </g>
</g>
""")
PULSE = ff.template("<g>{background}{object}{letters}</g>")
QUESTION_SHOT = ff.template("<g>{background}{opening}{ink}</g>")
RING = ff.template("<g>{background}{objects}{impacts}{ink}{label}</g>")
PORTRAIT = ff.template("<g>{performance}{ink}{label}</g>")


def pulse(frame, ctx, s, index):
    mode = 1.0 if index == 1 or (index == 3 and frame.index < 3) else 2.0 if index == 2 else 0.0
    color = "#27221c" if index == 0 else "#ede9df"
    icon = (3, 0, 7, 4)[index]
    obj = objects.hero(icon, 720.0, 540.0, 370.0, F(frame.global_index) * F(0.13))
    letters = [
        label(ch, F(250.0) + F(i) * F(312.0), 552.0, 32.0, color, True)
        for i, ch in enumerate("MOVE"[: index + 1])
    ]
    return PULSE(
        background=s.background(frame, mode, 1.35 if index == 3 else 0.5),
        object=s.draw_object(obj, frame, ctx),
        letters=letters,
    )


def signature(frame, s):
    poses = s.letters[min(frame.index, 75)]
    orbit = [
        ORBIT_LETTER(
            transform=f"translate({fmt32(p.position[0])} {fmt32(p.position[1])}) "
            f"rotate({fmt32(p.angle)}) scale({fmt32(p.scale)})",
            letter=ch,
        )
        for ch, p in zip("fframes", poses)
    ]
    return SIGNATURE(
        background=s.background(frame, 0.0, 0.025),
        ink=s.ink.vectors.draw_signature(frame, poses),
        orbit_fade=frame.animate(ORBIT_FADE),
        orbit=orbit,
        wordmark_fade=frame.animate(WORDMARK_FADE),
        wordmark_scale=frame.animate(WORDMARK_SCALE),
        tagline_fade=frame.animate(TAGLINE_FADE),
        tagline_slide=frame.animate(TAGLINE_SLIDE),
    )


STACK_X = [F(720.0) + objects.cos(F(i) * F(0.55)) * F(130.0) for i in range(12)]


class Shot:
    def __init__(self, name, length, kind, studio):
        self.name = name
        self.duration = ff.Duration.frames(length)
        self.kind = kind
        self.studio = studio

    def content(self, frame, ctx):
        s, kind, n = self.studio, self.kind, frame.index
        if kind == "question":
            return QUESTION_SHOT(
                background=s.background(frame, 0.0, 0.0),
                opening=None if n == 0 else opening(frame, ctx),
                ink=s.ink.draw_question(frame),
            )
        if kind == "signal":
            color = "#f4eee0" if n == 0 else "#161616"
            return SIGNAL(
                signal=s.signal(frame),
                opacity=frame.animate(SIGNAL_FADE),
                objects=s.objects_at(frame, ctx),
                ink=s.ink.draw(frame),
                color=color,
                you="#fff4df" if n >= 39 else color,
            )
        if kind == "portrait":
            copy = (
                "you don’t."
                if n <= 34
                else "you give"
                if n <= 38
                else "you give it"
                if n <= 42
                else "you give it fframes."
            )
            return PORTRAIT(
                performance=s.performance(frame, ctx, "portrait-clean.mp4"),
                ink=s.ink.draw(frame),
                label=label(copy, 208.0, 554.0, 46.0, "#181714" if n >= 51 else "#f3eee1", False),
            )
        if kind == "thermal":
            return s.thermal_cut(frame, ctx)
        if kind in ("ring", "carousel", "scatter"):
            return RING(
                background=s.background(frame, 0.0, 0.08),
                objects=s.objects_at(frame, ctx),
                impacts=s.ink.impacts_at(frame),
                ink=s.ink.draw(frame),
                label=label("from your mind", 720.0, 552.0, 32.0, "#1d1916", True)
                if kind == "scatter" and n > 23
                else None,
            )
        if kind in ("code", "motion", "feeling"):
            return hero_card(frame, ctx, s, kind)
        if kind == "hand":
            if n == 0:
                stack = [
                    s.draw_object(
                        objects.hero(
                            i, STACK_X[i], F(150.0) + F(i) * F(65.0), 170.0, F(i) * F(0.13)
                        ),
                        frame,
                        ctx,
                    )
                    for i in range(12)
                ]
                performance = STACK(background=s.background(frame, 1.0, 0.0), stack=stack)
            else:
                performance = s.hand(frame, ctx)
            copy = "from" if n <= 2 else "from your" if n <= 5 else "from your mind"
            return HAND(
                performance=performance,
                ink=s.ink.draw(frame),
                copy=label(copy, 208.0, 554.0, 42.0, "#f1ecdf", False),
                opacity=frame.animate(HAND_FADE),
                coda=label("to every frame.", 1050.0, 554.0, 42.0, "#f1ecdf", False),
            )
        if kind == "signature":
            return signature(frame, s)
        return pulse(frame, ctx, s, kind[1])

    def render_frame(self, frame, ctx):
        content = self.content(frame, ctx)
        live = self.kind in ("portrait", "thermal", "hand") or (
            self.kind == "question" and frame.index == 0
        )
        if live:
            return SHOT(content=content, dust=None, print=None)
        light = self.kind in ("code", "motion", "feeling")
        return SHOT(content=content, dust=dust(frame, light), print=self.studio.print(frame, 0.045))


FRAME = ff.template("""
<svg xmlns="http://www.w3.org/2000/svg" width="1440" height="1080" viewBox="0 0 1440 1080">
    <defs>
    <radialGradient id="stack-light"><stop offset="0" stop-color="#e8e8df"/>
        <stop offset="1" stop-color="#e8e8df" stop-opacity="0"/>
    </radialGradient></defs>
    {content}
</svg>
""")
INK_ONLY = ff.template('<g><rect width="1440" height="1080" fill="#e4e4e4"/>{ink}</g>')


class MadeOfMotion:
    """The complete source-timed film."""

    fps = 24
    width = 1440
    height = 1080
    background_color = ff.Color.BLACK
    duration = ff.Duration.frames(489)
    audio = (ff.AudioTrack("soundtrack.wav", 0.0, ff.Timestamp.EOF),)

    def __init__(self, ink_only: bool = False):
        self.studio = Studio()
        self.ink_only = ink_only
        start = 0
        self.scenes = []
        for name, end, kind in EDIT:
            self.scenes.append(Shot(name, end - start, kind, self.studio))
            start = end

    def render_frame(self, frame: ff.Frame, ctx: ff.Context) -> ff.Svgr:
        if self.ink_only:
            return FRAME(content=INK_ONLY(ink=self.studio.ink.draw(frame)))
        return FRAME(content=ctx.render_scenes(frame))


def main() -> int:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--ink-only", action="store_true")
    args, rest = parser.parse_known_args()
    folder = _media.folder(EXAMPLE, "dynamic_media")
    for file in ("portrait-clean.mp4", "soundtrack.wav"):
        if not (folder / file).is_file():
            print(
                f"made-of-motion: Missing {folder / file}. Restore the final media supplied "
                "with this example; see README.md.",
                file=sys.stderr,
            )
            return 1
    return ff.cli(
        MadeOfMotion(ink_only=args.ink_only),
        [sys.argv[0], *rest],
        media=ff.Media(_media.folder(EXAMPLE), folder),
        load_system_fonts=False,
        codec_params={"crf": "16", "preset": "medium"},
        limiter=False,
        default_output=Path(__file__).parent / "output" / "made-of-motion.mp4",
        renderer="gpu",
    )


if __name__ == "__main__":
    sys.exit(main())

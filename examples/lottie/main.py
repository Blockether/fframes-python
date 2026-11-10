"""An 18 second vertical launch video for Lottie support in fframes.

Port of the upstream `lottie` example. All timing uses the beat of the whole video
(`global_beat`). The scenes overlap for their cross-fades, and this keeps the overlaps on the
beat. The math is f32, like in the Rust example, so that every frame is the same.
"""

import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE))

import _media
import fframes as ff
import numpy as np
import soundtrack
from beat import (
    BEAT,
    CAPTION,
    CHARS_PER_BEAT,
    CODE,
    CODE_LINES,
    END,
    FEATURE_CHARS_PER_BEAT,
    FEATURE_LINE,
    FEATURE_TYPE_START,
    GRID,
    HOOK,
    KEY,
    LETTER_STEP,
    LETTERS,
    METHOD,
    OUTRO,
    PLAIN,
    PUNCT,
    STR,
    TILE_POP,
    TILE_STEP,
    TYPE,
    TYPE_START,
    WORD_NOW,
    WORD_PLAYS,
    ZOOM,
    F,
    beat_frames,
    beat_time,
    global_beat,
)

WIDTH = 1080
HEIGHT = 1920
TAU = F(2.0 * math.pi)

# The Rust example writes these as `{CONST}` holes, so they stay holes here: a fully static
# subtree takes the renderer's static cache, which anti-aliases differently.
P = {
    "bone": "#ece8e1",
    "orange": "#fb6a22",
    "ember": "#8a3712",
    "soot": "#4a2010",
    "muted": "#a8a39b",
    "display": "Anton",
    "mono": "IBM Plex Mono",
    "serif": "Instrument Serif",
}
TOKEN_COLORS = {
    PLAIN: P["bone"],
    PUNCT: P["muted"],
    METHOD: P["orange"],
    KEY: P["orange"],
    STR: "#ffb37a",
    TYPE: "#f4d7b8",
}

# Phone apps cover the top and the bottom. Content stays inside x 8-92 % and y 12-78 %.
SAFE_LEFT = F(86.0)
SAFE_TOP = F(230.0)
INF = F(math.inf)


def f32_text(x) -> str:
    """`x` as Rust prints an f32 with `{}`: the shortest text that reads back to the same f32."""
    x = F(x)
    for digits in range(1, 10):
        text = f"{float(x):.{digits}g}"
        if F(float(text)) == x:
            return text
    return repr(float(x))


def sin(x) -> np.float32:
    """`f32::sin`: correctly rounded, which `np.sin` on float32 is not always."""
    return F(math.sin(float(x)))


# ------------------------------------------------------------------ Motion

ENTER = ff.AnimationRuntime(3.0, ff.Easing.spring(1.0, 150.0, 18.0))
FADE = ff.AnimationRuntime(0.3, ff.Easing.EASE_OUT)
EXIT = ff.AnimationRuntime(0.2, ff.Easing.EASE_IN)
DIVE = ff.AnimationRuntime(float((OUTRO - ZOOM) * BEAT), ff.Easing.EASE_IN_OUT)


def scene_start(frame: ff.Frame) -> np.float32:
    """The second of the video when the scene of `frame` starts, with its overlap."""
    return F(frame.frame_to_second(frame.global_index - frame.index))


def progress(frame: ff.Frame, runtime: ff.AnimationRuntime, at) -> np.float32:
    """Progress 0 -> 1 of `runtime` that starts at beat `at` of the video."""
    return F(runtime.animate(frame, float(beat_time(at) - scene_start(frame)), 0.0, 1.0))


MOVE = ff.template('<g transform="{transform}" opacity="{opacity}">{content}</g>')


def enter_exit(frame: ff.Frame, at, out, xy, content: ff.Svgr) -> ff.Svgr:
    """An element that enters at beat `at` (rises 60 px, scales up from 0.92 and fades in) and
    leaves at beat `out` (rises 60 px more and fades out in 0.2 s). `xy` is its center."""
    x, y = F(xy[0]), F(xy[1])
    enter = progress(frame, ENTER, at)
    exit_ = progress(frame, EXIT, out)
    opacity = progress(frame, FADE, at) * (F(1.0) - exit_)
    if opacity <= 0.0:
        return ff.Svgr.empty()
    dy = (F(1.0) - enter) * F(60.0) - exit_ * F(60.0)
    scale = F(0.92) + F(0.08) * enter
    transform = (
        f"translate({f32_text(x)} {f32_text(y + dy)}) scale({f32_text(scale)}) "
        f"translate({f32_text(-x)} {f32_text(-y)})"
    )
    return MOVE(transform=transform, opacity=float(opacity), content=content)


def lottie(frame: ff.Frame, ctx: ff.Context, file: str, box, at) -> ff.Svgr:
    """A Lottie file in a square box that starts playing at beat `at`."""
    x, y, size = box
    return frame.play_lottie(
        ctx,
        file,
        start=float(beat_time(at) - scene_start(frame)),
        looping=True,
        x=float(x),
        y=float(y),
        width=float(size),
        height=float(size),
    )


def text_width(frame: ff.Frame, ctx: ff.Context, text: str, size: int, **font) -> np.float32:
    """Width of a text in pixels. Without the font it gives an estimate."""
    if not text:
        return F(0.0)
    width = frame.text_width(ctx, text, size=size, **font)
    return F(len(text)) * F(size) * F(0.5) if width is None else F(width)


# ------------------------------------------------------------------ Scenes

WORD = ff.template(
    '<text x="{x}" y="580" font-family="{display}" font-size="170" letter-spacing="-2" '
    'fill="{bone}">{word}</text>'
)
LETTER = ff.template(
    '<text x="{x}" y="860" font-family="{display}" font-size="300" fill="{orange}">{letter}</text>'
)
GROUP = ff.template("<g>{items}</g>")
# The beginnings of "LOTTIE". Each letter goes after the measured width of the letters before it.
PREFIXES = ["", "L", "LO", "LOT", "LOTT", "LOTTI", "LOTTIE"]


class Hook:
    """The first frame shows the wordmark and the party popper."""

    duration = ff.Duration.frames(beat_frames(GRID - HOOK))

    def render_frame(self, frame: ff.Frame, ctx: ff.Context) -> ff.Svgr:
        out = GRID - F(0.5)
        mark = wordmark(frame, ctx, 540.0, 330.0, 96, F(1.0))
        popper = lottie(frame, ctx, "party.json", (290.0, 930.0, 520.0), HOOK)

        # "NOW PLAYS" is one centered line with 40 px between the words. The letter-spacing
        # takes 2 px per letter, and the measured width does not include it.
        font = {"family": P["display"]}
        now = text_width(frame, ctx, "NOW", 170, **font) - F(2.0) * F(3.0)
        plays = text_width(frame, ctx, "PLAYS", 170, **font) - F(2.0) * F(5.0)
        left = F(540.0) - (now + F(40.0) + plays) / F(2.0)
        words = [
            enter_exit(
                frame, at, out, (x + width / F(2.0), 520.0), WORD(x=float(x), word=word, **P)
            )
            for word, at, x, width in (
                ("NOW", WORD_NOW, left, now),
                ("PLAYS", WORD_PLAYS, left + now + F(40.0), plays),
            )
        ]

        total = text_width(frame, ctx, "LOTTIE", 300, **font)
        letters = []
        for i, letter in enumerate("LOTTIE"):
            x = F(540.0) - total / F(2.0) + text_width(frame, ctx, PREFIXES[i], 300, **font)
            letters.append(
                enter_exit(
                    frame,
                    LETTERS + F(i) * LETTER_STEP,
                    out,
                    (x, 760.0),
                    LETTER(x=float(x), letter=letter, **P),
                )
            )

        return GROUP(
            items=[
                enter_exit(frame, HOOK - F(1.0), out, (540.0, 300.0), mark),
                *words,
                *letters,
                enter_exit(frame, HOOK - F(1.0), out, (550.0, 1190.0), popper),
            ]
        )


TILE_FILES = [
    "fire.json",
    "rocket.json",
    "unicorn.json",
    "earth.json",
    "cool.json",
    "mind_blown.json",
    "switch.json",
    "rainbow.json",
    "cat.json",
    "watermelon.json",
    "popcorn.json",
    "clapper.json",
]
# The grid: 3 x 4 animations between the title and the bottom of the safe area.
TILE = F(220.0)
COLUMN = F(300.0)
ROW = F(255.0)
GRID_TOP = F(490.0)
GRID_TITLE = ff.template(
    '<text x="540" y="340" text-anchor="middle" font-family="{display}" font-size="130" '
    'letter-spacing="-2" fill="{bone}">ANY LOTTIE FILE</text>'
)
GRID_SUBTITLE = ff.template(
    '<text x="540" y="420" text-anchor="middle" font-family="{serif}" font-style="italic" '
    'font-size="56" fill="{muted}">from After Effects or LottieFiles</text>'
)


class Grid:
    """Twelve animations pop in, one per sixteenth note, and float."""

    duration = ff.Duration.frames(beat_frames(CODE - GRID))
    # the title enters while the hook leaves
    overlap = (0.3, 0.0)

    def render_frame(self, frame: ff.Frame, ctx: ff.Context) -> ff.Svgr:
        b = global_beat(frame) - GRID
        out = CODE - F(0.5)
        tiles = []
        for i, file in enumerate(TILE_FILES):
            at = TILE_POP + F(i) * TILE_STEP
            x = F(540.0) + (F(i % 3) - F(1.0)) * COLUMN - TILE / F(2.0)
            # a slow float, with a different phase for each tile
            float_ = sin(b * BEAT * TAU / F(6.0) + F(i) * F(1.7)) * F(8.0)
            y = GRID_TOP + F(i // 3) * ROW + float_
            animation = lottie(frame, ctx, file, (x, y, TILE), at)
            tiles.append(
                enter_exit(frame, at, out, (x + TILE / F(2.0), y + TILE / F(2.0)), animation)
            )
        return GROUP(
            items=[
                enter_exit(frame, GRID - F(0.4), out, (540.0, 300.0), GRID_TITLE(**P)),
                enter_exit(frame, GRID + F(0.3), out, (540.0, 400.0), GRID_SUBTITLE(**P)),
                *tiles,
            ]
        )


# The position of the tiger in the code scene. The zoom starts from this position.
TIGER_BOX = (F(240.0), SAFE_TOP, F(600.0))
# The tiger loop (5.1 s) starts again when the zoom starts. The zoom freezes that first frame,
# so the cut does not show.
TIGER_START = ZOOM - F(5.1) / BEAT
CAPTION_TEXT = ff.template(
    '<text x="{x}" y="1440" font-family="{serif}" font-style="italic" font-size="96" '
    'fill="{bone}">one call.</text>'
)


class Code:
    """The tiger plays above the code that plays it."""

    duration = ff.Duration.frames(beat_frames(ZOOM - CODE))
    # the tiger enters while the grid leaves
    overlap = (0.3, 0.0)

    def render_frame(self, frame: ff.Frame, ctx: ff.Context) -> ff.Svgr:
        b = global_beat(frame) - CODE
        x, y, size = TIGER_BOX
        tiger = frame.play_lottie(
            ctx,
            "tiger.json",
            start=float(beat_time(TIGER_START) - scene_start(frame)),
            looping=True,
            x=float(x),
            y=float(y),
            width=float(size),
        )
        # the tiger stays for the zoom, the text leaves before the zoom
        tiger = enter_exit(frame, CODE - F(0.4), INF, (x + size / F(2.0), y + size / F(2.0)), tiger)
        out = ZOOM - F(0.5)
        typed = int(max((b - (TYPE_START - CODE)) * CHARS_PER_BEAT, F(0.0)))
        return GROUP(
            items=[
                tiger,
                enter_exit(frame, CODE, out, (540.0, 1050.0), code_block(typed, b)),
                enter_exit(
                    frame,
                    CAPTION,
                    out,
                    (540.0, 1410.0),
                    CAPTION_TEXT(x=float(SAFE_LEFT + F(22.0)), **P),
                ),
            ]
        )


SPAN = ff.template('<tspan fill="{color}">{text}</tspan>')
CODE_LINE = ff.template(
    '<text x="{x}" y="{y}" font-family="{mono}" font-weight="500" font-size="{size}">{spans}</text>'
)
CURSOR = ff.template(
    '<rect x="{x}" y="{y}" width="{width}" height="{height}" fill="{orange}" opacity="{opacity}" />'
)


def code_block(typed: int, beat) -> ff.Svgr:
    """The code with the first `typed` characters visible and a blinking cursor after them."""
    size = F(40.0)
    char = size * F(0.6)  # IBM Plex Mono advances 0.6 em per character
    x0 = SAFE_LEFT + F(22.0)
    left = typed
    cursor = None
    lines = []
    for row, line in enumerate(CODE_LINES):
        y = F(960.0) + F(row) * F(64.0)
        indent = len(line[0][0]) - len(line[0][0].lstrip()) if line else 0
        chars_in_line = 0
        spans = []
        for column, (text, token) in enumerate(line):
            # the first token of a line holds the indentation, which is not typed
            text = text.lstrip() if column == 0 else text
            if not text or left == 0:
                continue
            shown = text[: min(left, len(text))]
            left -= len(shown)
            chars_in_line += len(shown)
            spans.append(SPAN(color=TOKEN_COLORS[token], text=shown))
        if chars_in_line > 0:
            x = x0 + F(indent) * char
            cursor = (x + F(chars_in_line) * char, y)
            lines.append(CODE_LINE(x=float(x), y=float(y), size=float(size), spans=spans, **P))
    blink = 1.0 if beat - np.trunc(beat) < 0.5 else 0.0
    if cursor is None:
        return GROUP(items=lines)
    x, y = cursor
    rect = CURSOR(
        x=float(x + F(2.0)),
        y=float(y - size * F(0.8)),
        width=float(char * F(0.9)),
        height=float(size),
        opacity=blink,
        **P,
    )
    return GROUP(items=[*lines, rect])


# The pupil of the tiger in its own units (the file is 1024 x 1024).
PUPIL = (F(160.0), F(440.0))
# The pupil covers the whole screen from about 70x. That is just before the outro.
ZOOM_MAX = F(80.0)
CAMERA = ff.template('<g transform="{transform}" opacity="{opacity}">{tiger}</g>')
VECTOR = ff.template(
    '<text x="540" y="1450" text-anchor="middle" font-family="{display}" font-size="260" '
    'letter-spacing="-3" fill="{bone}">VECTOR.</text>'
)


class Zoom:
    """The camera dives into the tiger's eye until the pupil fills the screen."""

    duration = ff.Duration.frames(beat_frames(OUTRO - ZOOM))

    def render_frame(self, frame: ff.Frame, ctx: ff.Context) -> ff.Svgr:
        x, y, size = TIGER_BOX
        base = size / F(1024.0)
        pupil = (x + PUPIL[0] * base, y + PUPIL[1] * base)
        dive = progress(frame, DIVE, ZOOM)
        zoom = F(math.pow(float(ZOOM_MAX), float(dive)))
        # the pupil travels to the middle of the safe area while the camera dives
        target = (
            F(540.0) + (pupil[0] - F(540.0)) * (F(1.0) - dive),
            F(865.0) + (pupil[1] - F(865.0)) * (F(1.0) - dive),
        )
        camera = (
            f"translate({f32_text(target[0])} {f32_text(target[1])}) scale({f32_text(zoom)}) "
            f"translate({f32_text(-pupil[0])} {f32_text(-pupil[1])}) "
            f"translate({f32_text(x)} {f32_text(y)}) scale({f32_text(base)})"
        )
        # the first frame of the loop, frozen, because the code scene ends on it
        tiger = ff.lottie_frame(ctx, "tiger.json", 0.0)
        # the dark pupil fills the screen, then fades out for the outro
        fade = F(1.0) - progress(frame, FADE, OUTRO - F(0.4))
        return GROUP(
            items=[
                CAMERA(transform=camera, opacity=float(fade), tiger=tiger),
                enter_exit(frame, ZOOM + F(0.5), OUTRO - F(0.8), (540.0, 1350.0), VECTOR(**P)),
            ]
        )


FEATURE = ff.template(
    "<g>"
    '<text x="540" y="930" text-anchor="middle" font-family="{mono}" font-weight="600" '
    'font-size="30" letter-spacing="6" fill="{orange}">NEW: LOTTIE FILES</text>'
    '<text x="540" y="1010" text-anchor="middle" font-family="{mono}" font-weight="500" '
    'font-size="42" fill="{bone}">{feature}</text>'
    "</g>"
)
ADDRESS = ff.template(
    "<g>"
    '<text x="540" y="1220" text-anchor="middle" font-family="{serif}" font-style="italic" '
    'font-size="92" fill="{bone}">fframes.studio</text>'
    '<text x="540" y="1290" text-anchor="middle" font-family="{mono}" font-weight="500" '
    'font-size="30" fill="{muted}">github.com/dmtrkovalenko/fframes</text>'
    "</g>"
)
CREDIT = ff.template(
    '<text x="540" y="1470" text-anchor="middle" font-family="{mono}" font-weight="500" '
    'font-size="28" fill="{muted}">Emoji: Noto Animated Emoji, CC BY 4.0</text>'
)


class Outro:
    """The wordmark, the feature flag and the address."""

    duration = ff.Duration.frames(beat_frames(END - OUTRO))
    # the wordmark rises while the pupil fades
    overlap = (0.3, 0.0)

    def render_frame(self, frame: ff.Frame, ctx: ff.Context) -> ff.Svgr:
        b = global_beat(frame) - OUTRO
        star = lottie(frame, ctx, "star_struck.json", (400.0, SAFE_TOP + F(20.0), 280.0), OUTRO)
        sparkle = lottie(frame, ctx, "sparkles.json", (820.0, 520.0, 150.0), OUTRO + F(0.5))
        fan = progress(frame, ENTER, OUTRO - F(0.5))
        mark = wordmark(frame, ctx, 540.0, 800.0, 200, fan)
        typed = int(max((b - (FEATURE_TYPE_START - OUTRO)) * FEATURE_CHARS_PER_BEAT, F(0.0)))
        feature = FEATURE_LINE[:typed]
        return GROUP(
            items=[
                enter_exit(frame, OUTRO + F(0.2), INF, (540.0, 390.0), star),
                enter_exit(frame, OUTRO + F(0.6), INF, (895.0, 595.0), sparkle),
                enter_exit(frame, OUTRO - F(0.5), INF, (540.0, 740.0), mark),
                enter_exit(
                    frame, OUTRO + F(0.75), INF, (540.0, 950.0), FEATURE(feature=feature, **P)
                ),
                enter_exit(frame, OUTRO + F(3.0), INF, (540.0, 1200.0), ADDRESS(**P)),
                enter_exit(frame, OUTRO + F(3.5), INF, (540.0, 1460.0), CREDIT(**P)),
            ]
        )


MARK_F = ff.template(
    '<text x="{x}" y="{y}" font-family="{serif}" font-style="italic" font-size="{size}" '
    'fill="{color}">f</text>'
)
MARK_WORD = ff.template(
    '<text x="{x}" y="{y}" font-family="{serif}" font-style="italic" font-size="{size}" '
    'fill="{bone}">fframes</text>'
)


def wordmark(frame: ff.Frame, ctx: ff.Context, x, y, size: int, appear) -> ff.Svgr:
    """ "fframes" in Instrument Serif centered on `x`, with a trail of three f's on its left.
    `appear` 0 -> 1 fans the trail out."""
    font = {"family": P["serif"], "weight": 400, "style": "italic"}
    word = text_width(frame, ctx, "fframes", size, **font)
    f = text_width(frame, ctx, "f", size, **font)
    step = f * F(0.62)
    # center the visible part, "fframes" and the orange f. The two dark f's are on the left.
    x0 = F(x) - (word + step) / F(2.0) + step
    trail = [
        MARK_F(
            x=float(x0 - k * step * appear),
            y=y,
            size=size,
            color=P[color],
            **{k_: v for k_, v in P.items() if k_ != "color"},
        )
        for k, color in ((F(3.0), "soot"), (F(2.0), "ember"), (F(1.0), "orange"))
    ]
    return GROUP(items=[*trail, MARK_WORD(x=float(x0), y=y, size=size, **P)])


# ------------------------------------------------------------------ Video

SVG = ff.template(
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1080 1920" width="{width}" '
    'height="{height}">{rings}{scenes}</svg>'
)
RING = ff.template(
    '<ellipse cx="540" cy="960" rx="{rx}" ry="{ry}" fill="none" stroke="{ember}" '
    'stroke-width="2" opacity="{opacity}" />'
)
RINGS = ff.template('<g transform="{transform}">{rings}</g>')


def rings(beat) -> ff.Svgr:
    """Contour rings behind everything. They drift, and one turn of the wobble takes 8 s."""
    items = []
    for i in range(1, 26):
        i = F(i)
        r = i * F(62.0)
        wobble = sin(i * F(0.9) + beat * BEAT * TAU / F(8.0)) * F(10.0)
        opacity = max(F(0.32) - i * F(0.012), F(0.0))
        items.append(
            RING(rx=float(r + wobble), ry=float(r * F(0.86) - wobble), opacity=float(opacity), **P)
        )
    return RINGS(transform=f"rotate({f32_text(beat * BEAT * F(3.0))} 540 960)", rings=items)


class LaunchVideo:
    fps = 60
    width = WIDTH
    height = HEIGHT
    background_color = "#0b0b0b"
    duration = None

    def __init__(self):
        self.scenes = [Hook(), Grid(), Code(), Zoom(), Outro()]
        self.audio = [("music", 0.0, None)]

    def render_frame(self, frame: ff.Frame, ctx: ff.Context) -> ff.Svgr:
        return SVG(
            width=WIDTH,
            height=HEIGHT,
            rings=rings(global_beat(frame)),
            scenes=ctx.render_scenes(frame),
        )


if __name__ == "__main__":
    media = ff.Media(_media.folder("lottie"), mono=True, audio={"music": soundtrack.music()})
    sys.exit(
        ff.cli(
            LaunchVideo(),
            media=media,
            load_system_fonts=False,
            codec_params={"crf": "17", "preset": "medium", "tune": "animation"},
            # The synthesized mix measures about -17.3 LUFS. This lifts it to about -14 for social
            # feeds, and the limiter keeps the true peak below -1 dBTP.
            master_gain_db=3.5,
            limiter={"ceiling_db": -1.3},
        )
    )

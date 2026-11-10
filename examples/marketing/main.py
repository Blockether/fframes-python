"""Port of fframes/examples/marketing: an audio spectrum, subtitles and Ferris.

python examples/marketing/main.py render -o marketing.mp4
"""

import math
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import _media
import fframes as ff

_F32 = struct.Struct("f")


def f32(x: float) -> float:
    """`x` rounded to f32, like the f32 math of the Rust example."""
    return _F32.unpack(_F32.pack(x))[0]


def f32_text(x: float) -> str:
    """`x` as Rust prints an f32 with `{}`: the shortest text that reads back to the same f32."""
    x = f32(x)
    for digits in range(1, 10):
        text = f"{x:.{digits}g}"
        if f32(float(text)) == x:
            return text
    return repr(x)


SPRING = ff.Easing.spring(1.85, 130.0, 16.0)
SPRING_RUNTIME = ff.AnimationRuntime(10.0, SPRING)
CODE_SPRING = ff.Easing.spring(0.85, 80.0, 16.0)

# (position, spectrum_index, from_color, to_color), in stacking order.
PRETTY_SPECTRUM = (
    (6, 6, "#ec4899", "#f43f5e"),
    (0, 3, "#d946ef", "#9333ea"),
    (5, 5, "#facc15", "#f97316"),
    (1, 7, "#38bdf8", "#6366f1"),
    (4, 4, "#4ade80", "#06b6d4"),
    (2, 2, "#22d3ee", "#0ea5e9"),
    (3, 1, "#fff", "#fff"),
)
BAR_SIZE = 96
BAR_MARGIN = 20
BAR_WIDTH_WITH_MARGIN = BAR_SIZE + BAR_MARGIN
SPECTRUM_LEN = 1920 - BAR_WIDTH_WITH_MARGIN * len(PRETTY_SPECTRUM) - BAR_MARGIN

EYE_RIGHT = ff.timeline(
    ((3.4, 3.65), 727.0, 777.0, "linear"), ((4.1, 4.35), 777.0, 727.0, "linear")
)
EYE_LEFT = ff.timeline(((3.4, 3.65), 520.0, 570.0, "linear"), ((4.1, 4.35), 570.0, 520.0, "linear"))
FERRIS_Y = ff.timeline((2.3, 1400.0, 770.0, SPRING), (4.8, 770.0, 1400.0, SPRING))
ARROW_OPACITY = ff.timeline((5.8, 0.0, 1.0, SPRING), (9.0, 1.0, 0.0, SPRING))
CODE_X = ff.timeline((5.8, -1000.0, 40.0, CODE_SPRING), (9.0, 40.0, -1200.0, CODE_SPRING))
CIRCLE_R = ff.timeline(((16.2, 16.5), 0.0, 1200.0, "linear"))
WAVE_OFFSET = ff.timeline(((16.3, 18.8), -700.0, 41.0, "linear"))
SPARK_OPACITY = ff.timeline(((18.6, f32(f32(18.6) + f32(0.3))), 1.0, 0.55, "linear"))
SPARK_OFFSET = ff.timeline(((18.7, f32(f32(18.7) + f32(0.3))), -40.0, 0.0, "linear"))
SPARK_DASH = ff.timeline(((18.7, f32(f32(18.7) + f32(0.3))), 30.0, 12.0, "linear"))

FERRIS = ff.template(
    """
<svg viewBox="0 0 1200 800" width="400" height="400" x="1456" y="{y}"
     xmlns="http://www.w3.org/2000/svg" fill-rule="evenodd" clip-rule="evenodd"
     stroke-linejoin="round" stroke-miterlimit="1.41421">
"""
    + (Path(__file__).with_name("ferris.svg")).read_text()
    + "</svg>"
)

BAR = ff.template("""
<filter id="{shadow_id}" x="-100%" y="-100%" width="300%" height="300%">
    <feGaussianBlur in="SourceAlpha" stdDeviation="10.4"/>
    <feOffset dx="0" dy="3" result="offsetblur"/>
    <feFlood flood-color="{to_color}" flood-opacity="0.5" />
    <feComposite in2="offsetblur" operator="in"/>
    <feMerge>
        <feMergeNode/>
        <feMergeNode in="SourceGraphic"/>
    </feMerge>
</filter>
<linearGradient id="{gradient_id}" y2="1">
    <stop stop-color="{from_color}"/>
    <stop offset="1" stop-color="{to_color}" />
</linearGradient>
<rect y="{y}" x="{x}" transform-origin="center center" height="{outline_height}"
      fill="transparent" stroke="white" stroke-width="4" width="{outline_width}"
      rx="{radius}" ry="{radius}" />
<rect y="{y}" x="{x}" transform-origin="center center" fill="{fill}" filter="{filter}"
      height="{height}" width="{width}" rx="{radius}" ry="{radius}" />
""")

OUTRO = ff.template("""
<g>
    <text x="960" y="570" font-family="Bubble Bobble" font-size="154" text-anchor="middle"><tspan fill="{ff_fill}">ff</tspan>rames</text>
    <text x="960" y="610" font-family="Fredoka One" font-size="30" text-anchor="middle">Write some code. Get video. Enjoy!</text>
    <g y="540" transform="scale(2.7) translate(-218, 110)">
        <path fill="none" stroke="url(#anim)" stroke-width="10" stroke-linecap="round"
              stroke-linejoin="round" stroke-miterlimit="10" stroke-dashoffset="{wave_offset}"
              stroke-dasharray="40.4579px, 796.447px"
              d="M505,55c0-27.6-22.4-50-50-50s-50,22.4-50,50c0-27.6-22.4-50-50-50s-50,22.4-50,50c0-27.6-22.4-50-50-50s-50,22.4-50,50c0-27.6-22.4-50-50-50s-50,22.4-50,50c0-27.6-22.4-50-50-50S5,27.4,5,55" />
        <path fill="none" stroke="#4F46E5" stroke-width="6" stroke-linecap="round"
              stroke-linejoin="round" opacity="{spark_opacity}" stroke-dashoffset="{spark_offset}"
              stroke-dasharray="{spark_dash}"
              d="M549.7,46.6l-21.8,12.6 M531.9,25.8l-12.6,21.8 M504.2,18.3v25.1 M476.4,25.8L489,47.6 M458.7,46.6l21.8,12.6" />
    </g>
</g>
""")

FRAME = ff.template("""
<svg xmlns="http://www.w3.org/2000/svg" width="1920" height="1080">
    <defs>
        <linearGradient id="gradient-test" x1="1" y1="1">
            <stop stop-color="#3a1c71" />
            <stop offset=".5" stop-color="#d76d77" />
            <stop offset="1" stop-color="#ffaf7b" />
        </linearGradient>
        <linearGradient id="cover" gradientUnits="userSpaceOnUse" x1="14.66%" y1="108.81%" x2="85.34%" y2="-8.81%">
            <stop stop-color="#ffa69e" />
            <stop offset="1" stop-color="#7351d8" />
        </linearGradient>
        <linearGradient id="anim">
            <stop stop-color="#ec77ab" />
            <stop offset="1" stop-color="#4F46E5" />
        </linearGradient>
        <linearGradient id="g1" x1="1" y1="1" x2="0">
            <stop stop-color="#2d3436" />
            <stop offset=".74" stop-color="#000000" />
        </linearGradient>
    </defs>
    <rect x="0" y="0" width="100%" height="100%" fill="#111827" />
    {bars}
    <svg x="200" y="290" xmlns="http://www.w3.org/2000/svg"
         viewBox="0 0 598.3520004127504 417.989493060112" width="298" opacity="{arrow_opacity}">
        <g stroke-linecap="round" transform="translate(12.76795062351539 11.630295608565234) rotate(0 286.4080495828598 197.36445092149077)">
            <path d="M-2.19 -1.63 C8.29 53.64, -34.21 264.71, 62.09 331.05 C158.39 397.38, 490.59 385.91, 575.58 396.36" stroke="#fff" stroke-width="4.5" fill="none" stroke-dasharray="8 12"></path>
        </g>
        <g transform="translate(12.76795062351539 11.630295608565234) rotate(0 286.4080495828598 197.36445092149077)">
            <path d="M544.61 406.42 C552.39 404.4, 562.6 396.92, 572.02 395.84" stroke="#fff" stroke-width="4.5" fill="none"></path>
        </g>
        <g transform="translate(12.76795062351539 11.630295608565234) rotate(0 286.4080495828598 197.36445092149077)">
            <path d="M545.58 385.92 C553.02 389.43, 562.97 387.49, 572.02 395.84" stroke="#fff" stroke-width="4.5" fill="none"></path>
        </g>
    </svg>
    <text font-size="64" y="87%" x="50%" text-anchor="middle" fill="white" font-family="Fredoka One">{subtitle}</text>
    <image width="900" height="900" href="{code}" x="{code_x}" y="10" />
    {ferris}
    <circle cx="{cx}" fill="#fff" cy="500" r="{circle_r}" />
    {outro}
</svg>
""")

# The parts of a bar that do not change between frames.
BAR_PARTS = [
    {
        "shadow_id": f"{position}-shadow",
        "gradient_id": f"{position}-gradient",
        "from_color": from_color,
        "to_color": to_color,
        "fill": f"url(#{position}-gradient)",
        "filter": f"url(#{position}-shadow)",
        "outline_width": BAR_SIZE + 8,
        "width": BAR_SIZE,
        "radius": BAR_SIZE // 2,
        "index": index,
        "from_x": float(SPECTRUM_LEN // 2 + position * BAR_WIDTH_WITH_MARGIN),
    }
    for position, index, from_color, to_color in PRETTY_SPECTRUM
]


def bar_height(value: float) -> float:
    height = f32(value * 60.0)
    if math.isnan(height) or height < BAR_SIZE:
        return float(BAR_SIZE)
    return min(height, 720.0)


class MarketingVideo:
    fps = 60
    width = 1920
    height = 1080
    duration = None

    def __init__(self, audio_track: str = "marketing.mp3"):
        self.audio_track = audio_track
        self.audio = [
            ("marketing.mp3", 0.0, None),
            ("woosh.mp3", 6.0, None),
            ("end.mp3", 16.0, None),
        ]

    def render_frame(self, frame: ff.Frame, ctx: ff.Context) -> ff.Svgr:
        spectrum = frame.visualize_audio(
            ctx, "marketing.mp3", sample_size=16, smooth_level=3, window="hamming"
        )
        bars = []
        for part in BAR_PARTS:
            h = bar_height(spectrum[part["index"]])
            x = SPRING_RUNTIME.animate(frame, 16.0, part["from_x"], 944.0)
            bars.append(
                BAR(
                    y=f32(500.0 - f32(h / 2.0)),
                    x=x,
                    outline_height=f32(h + 8.0),
                    height=h,
                    **{k: v for k, v in part.items() if k not in ("index", "from_x")},
                )
            )
        seconds = frame.seconds
        outro = None
        if seconds > 16.25:
            outro = OUTRO(
                ff_fill="#7351d8" if seconds > 18.8 else "#000",
                wave_offset=frame.animate(WAVE_OFFSET),
                spark_opacity=frame.animate(SPARK_OPACITY),
                spark_offset=frame.animate(SPARK_OFFSET),
                spark_dash=f"{f32_text(frame.animate(SPARK_DASH))}, 137px",
            )
        return FRAME(
            bars=bars,
            arrow_opacity=frame.animate(ARROW_OPACITY),
            subtitle=frame.subtitle_phrase(ctx, "subtitles.vtt") or "",
            code=ctx.image("code.png"),
            code_x=frame.animate(CODE_X),
            ferris=FERRIS(
                y=frame.animate(FERRIS_Y),
                eye_right=f32_text(frame.animate(EYE_RIGHT)),
                eye_left=f32_text(frame.animate(EYE_LEFT)),
            )
            if 2.3 <= seconds < 5.0
            else None,
            cx=960,
            circle_r=frame.animate(CIRCLE_R),
            outro=outro,
        )


if __name__ == "__main__":
    sys.exit(
        ff.cli(MarketingVideo(), media=_media.media("marketing", mono=True), encoder="libx265")
    )

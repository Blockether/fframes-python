"""Port of fframes/examples/shaders: an SkSL background, a Shadertoy card and text on top.

python examples/shaders.py render -o shaders.mp4 [--video-codec libx264]
"""

import argparse
import sys
from pathlib import Path

import _media
import fframes as ff
from fframes import Color, Easing, Transform

SOURCES = Path(__file__).parent / "sksl"
AURORA = ff.Shader.sksl((SOURCES / "aurora.sksl").read_text())
TORUS = ff.Shader.shadertoy((SOURCES / "torus.glsl").read_text())

COLOR_A = ff.timeline(((0, 8), Color.hex("#22d3ee"), Color.hex("#a855f7"), Easing.EASE_IN_OUT))
COLOR_B = Color.hex("#f472b6")
CARD_SLIDE = ff.timeline(
    (0.3, Transform.translate(0, 140), Transform.translate(0, 0), Easing.spring(1.0, 180.0, 20.0)),
)
CARD_OPACITY = ff.timeline(((0.3, 0.9), 0.0, 1.0, Easing.EASE_OUT))
TITLE_OPACITY = ff.timeline(((0.6, 1.4), 0.0, 1.0, Easing.EASE_OUT))

FRAME = ff.template("""
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1920 1080" width="1920" height="1080">
    <defs>
        <clipPath id="card">
            <rect x="1040" y="160" width="760" height="760" rx="40" />
        </clipPath>
    </defs>
    <image href="{background}" x="0" y="0" width="1920" height="1080" />
    <g transform="{card_slide}" opacity="{card_opacity}">
        <g clip-path="url(#card)">
            <image href="{torus}" x="1040" y="160" width="760" height="760" />
        </g>
        <rect x="1040" y="160" width="760" height="760" rx="40"
              fill="none" stroke="#ffffff" stroke-opacity="0.2" stroke-width="2" />
    </g>
    <g opacity="{title_opacity}">
        <text x="120" y="500" font-family="DM Sans" font-weight="500" font-size="128"
              fill="#ffffff">GPU shaders</text>
        <text x="126" y="580" font-family="DM Sans" font-weight="500" font-size="40"
              fill="#f5f3ff" fill-opacity="0.8">SkSL and Shadertoy, drawn by Skia</text>
    </g>
</svg>
""")


class ShadersVideo:
    """GPU shader layers composed with regular SVG."""

    fps = 30
    width = 1920
    height = 1080
    duration = 8.0

    def render_frame(self, frame: ff.Frame, ctx: ff.Context) -> ff.Svgr:
        background = AURORA.draw(
            frame, {"uColorA": frame.animate(COLOR_A), "uColorB": COLOR_B, "uSpeed": 0.6}
        )
        return FRAME(
            background=background,
            torus=TORUS.draw(frame),
            card_slide=frame.animate(CARD_SLIDE),
            card_opacity=frame.animate(CARD_OPACITY),
            title_opacity=frame.animate(TITLE_OPACITY),
        )


def main() -> int:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--video-codec", default="libx264")
    args, rest = parser.parse_known_args()
    return ff.cli(
        ShadersVideo(),
        [sys.argv[0], *rest],
        media=_media.media("shaders"),
        encoder=args.video_codec,
        codec_params={"crf": "20", "preset": "slow"},
        renderer="gpu",
    )


if __name__ == "__main__":
    sys.exit(main())

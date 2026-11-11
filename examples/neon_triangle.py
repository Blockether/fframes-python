"""Port of fframes/examples/neon-triangle: one neon triangle rotating on black.

python examples/neon_triangle.py render -o neon.mp4 [--video-codec libx264]
"""

import argparse
import sys
from pathlib import Path

import _media
import fframes as ff
from _f32 import DEG_PER_RAD, TAU, f32
from fframes import Color, Easing, Transform

TRIANGLE = ff.Shader.sksl((Path(__file__).parent / "sksl" / "neon_triangle.sksl").read_text())
MAGENTA = Color.hex("#ff2bd6")

# The title switches on like a neon tube: a few quick flickers, then steady.
TITLE = ff.timeline(
    ((0.20, 0.24), 0.0, 1.0, Easing.LINEAR),
    ((0.30, 0.33), 1.0, 0.15, Easing.LINEAR),
    ((0.40, 0.43), 0.15, 1.0, Easing.LINEAR),
    ((0.56, 0.58), 1.0, 0.4, Easing.LINEAR),
    ((0.66, 0.80), 0.4, 1.0, Easing.LINEAR),
)
SUBTITLE = ff.timeline(((0.9, 1.5), 0.0, 1.0, Easing.EASE_OUT))
SUBTITLE_SLIDE = ff.timeline(
    (0.9, Transform.translate(-40, 0), Transform.translate(0, 0), Easing.spring(1.0, 140.0, 20.0)),
)

FRAME = ff.template("""
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1920 1080" width="1920" height="1080">
    <defs>
        <filter id="neon" x="-20%" y="-50%" width="140%" height="200%">
            <feGaussianBlur in="SourceAlpha" stdDeviation="5" result="tight" />
            <feGaussianBlur in="SourceAlpha" stdDeviation="18" result="wide" />
            <feMerge result="blur">
                <feMergeNode in="tight" />
                <feMergeNode in="wide" />
            </feMerge>
            <feFlood flood-color="#ff2bd6" result="tint" />
            <feComposite in="tint" in2="blur" operator="in" result="glow" />
            <feMerge>
                <feMergeNode in="glow" />
                <feMergeNode in="glow" />
                <feMergeNode in="SourceGraphic" />
            </feMerge>
        </filter>
    </defs>
    <image href="{triangle}" x="820" y="0" width="1100" height="1080" />
    <g opacity="{title}" filter="url(#neon)" font-family="DM Sans" font-weight="500" fill="#ffffff">
        <text x="140" y="480" font-size="190" letter-spacing="6">NEON</text>
        <text x="146" y="620" font-size="104" letter-spacing="14">TRIANGLE</text>
    </g>
    <g opacity="{subtitle}" transform="{subtitle_slide}" font-family="JetBrains Mono">
        <text x="148" y="720" font-size="30" fill="#f5d0fe">one SkSL shader, drawn by Skia on the GPU</text>
    </g>
    <text x="148" y="1000" font-family="JetBrains Mono" font-size="24" fill="#a78bfa"
          opacity="{subtitle}">{readout}</text>
</svg>
""")


class NeonTriangle:
    """A minimal shader test clip: smooth glow on black shows banding and motion defects."""

    fps = 60
    width = 1920
    height = 1080
    background_color = Color.BLACK
    duration = 6.0

    def render_frame(self, frame: ff.Frame, ctx: ff.Context) -> ff.Svgr:
        # Constant angular speed: one turn every 4 s, a slow roll on top.
        turn = f32(frame.seconds * TAU)
        yaw = turn / 4.0
        roll = f32(turn / 12.0)
        triangle = TRIANGLE.draw(frame, {"uYaw": yaw, "uRoll": roll, "uColor": MAGENTA})
        subtitle = frame.animate(SUBTITLE)
        readout = (
            f"yaw {f32(yaw * DEG_PER_RAD) % 360.0:03.0f}°  "
            f"roll {f32(roll * DEG_PER_RAD) % 360.0:03.0f}°  frame {frame.index:03}"
        )
        return FRAME(
            triangle=triangle,
            title=frame.animate(TITLE),
            subtitle=subtitle,
            subtitle_slide=frame.animate(SUBTITLE_SLIDE),
            readout=readout,
        )


def main() -> int:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--video-codec", default="libx264")
    args, rest = parser.parse_known_args()
    return ff.cli(
        NeonTriangle(),
        [sys.argv[0], *rest],
        media=_media.media("neon-triangle"),
        load_system_fonts=False,
        encoder=args.video_codec,
        codec_params={"crf": "16", "preset": "slow"},
        renderer="gpu",
    )


if __name__ == "__main__":
    sys.exit(main())

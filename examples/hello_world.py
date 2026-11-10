"""Port of fframes/examples/hello-world.

python examples/hello_world.py render -o hello.mp4 [--slug NAME]
"""

import argparse
import sys

import _media
import fframes as ff
from fframes import Color, Transform

BACKGROUND = ff.timeline(
    (0, Color.hex("#fff"), Color.hex("#f8fafc")),
    (5, Color.hex("#f8fafc"), Color.hex("#fff7ed")),
    (10, Color.hex("#fff7ed"), Color.hex("#fef2f2")),
    (15, Color.hex("#fef2f2"), Color.hex("#f7fee7")),
    (20, Color.hex("#f7fee7"), Color.hex("#ecfdf5")),
    ((25, 30), Color.hex("#ecfdf5"), Color.hex("#faf5ff")),
)

BOX = ff.timeline(
    (0, Transform.translate(0, 0), Transform.translate(200, 480)),
    ((2, 6), Transform.translate(200, 480), Transform.translate(750, -400)),
    ((6, 10), Transform.translate(750, -400), Transform.translate(1310, 480)),
)

FRAME = ff.template("""
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1920 1080" width="{width}" height="{height}">
    <rect width="1920" height="1080" fill="{background}"/>
    <rect x="400" y="400" width="200" height="200" fill="blue" transform="{box}"/>
    <text x="99" y="300" font-family="DM Sans" font-size="150" fill="#000">Hello {slug}</text>
    <text x="100" y="440" font-family="JetBrains Mono" font-size="74" font-weight="500"
          fill="#3b5563">{info}</text>
</svg>
""")


class HelloWorld:
    fps = 30
    width = 1920
    height = 1080
    duration = 30.0

    def __init__(self, slug: str):
        self.slug = slug

    def render_frame(self, frame: ff.Frame, ctx: ff.Context) -> ff.Svgr:
        return FRAME(
            width=ctx.width,
            height=ctx.height,
            background=frame.animate(BACKGROUND),
            box=frame.animate(BOX),
            slug=self.slug,
            info=f"This frame index: {frame.index}, second: {frame.seconds:.2f}",
        )


def main() -> int:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--slug", default="Renderer!")
    args, rest = parser.parse_known_args()
    video = HelloWorld(args.slug)
    return ff.cli(video, [sys.argv[0], *rest], media=_media.media("hello-world"))


if __name__ == "__main__":
    sys.exit(main())

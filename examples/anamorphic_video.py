"""Port of fframes/examples/anamorphic-video: a clip with non-square pixels.

`media/anamorphic.mp4` is 480x360 with a 4:3 sample aspect ratio. The decoder stretches it to
640x360, so the red circle lands on the clip's circle.

python examples/anamorphic_video.py render -o anamorphic.mp4
"""

import sys

import _media
import fframes as ff
from _f32 import f32

WIDTH, HEIGHT = 1280, 720

FRAME = ff.template("""
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1280 720" width="{width}" height="{height}">
    <rect width="1280" height="720" fill="#000" />
    {clip}
    <circle cx="640" cy="360" r="280" fill="none" stroke="#f43f5e" stroke-width="4" />
</svg>
""")
CLIP = ff.template('<image href="{href}" x="{x}" width="{width}" height="{height}" />')


class AnamorphicVideo:
    fps = 30
    width = WIDTH
    height = HEIGHT
    duration = 1.0

    def render_frame(self, frame: ff.Frame, ctx: ff.Context) -> ff.Svgr:
        video = frame.video_frame(ctx, "anamorphic.mp4")
        clip = None
        if video is not None:
            width = f32(f32(video.width * HEIGHT) / video.height)
            clip = CLIP(href=video.image, x=f32((WIDTH - width) / 2), width=width, height=HEIGHT)
        return FRAME(width=ctx.width, height=ctx.height, clip=clip)


def main() -> int:
    return ff.cli(
        AnamorphicVideo(),
        media=_media.media("anamorphic-video"),
        codec_params={},
        load_system_fonts=False,
    )


if __name__ == "__main__":
    sys.exit(main())

"""Port of fframes/examples/tiktok: an audio spectrum, subtitles and a goose, 1080x1920.

python examples/tiktok.py render -o out.webm  (VP9 with alpha, Opus audio)
"""

import sys
from array import array

import _media
import fframes as ff
from fframes import Color

BAR_SIZE = 30
BAR_PADDING = 20
WIDTH = 1080
HEIGHT = 1920
SPECTRUM_WIDTH = 16 * (BAR_SIZE + BAR_PADDING) - BAR_PADDING
BAR_X = [i * (BAR_SIZE + BAR_PADDING) + (WIDTH - SPECTRUM_WIDTH) // 2 for i in range(16)]

BAR = ff.template(
    f'<rect x="{{x}}" y="{{y}}" width="{BAR_SIZE}" rx="15" fill="white" height="{{height}}"/>'
)

FRAME = ff.template("""
<svg width="1080" height="1920" fill="none" xmlns="http://www.w3.org/2000/svg">
    <defs>
        <filter id="blur-hard" x="-66.271" y="140.76" width="1031.86" height="1023.68" filterUnits="userSpaceOnUse" color-interpolation-filters="sRGB">
            <feFlood flood-opacity="0" result="BackgroundImageFix"/>
            <feBlend in="SourceGraphic" in2="BackgroundImageFix" result="shape"/>
            <feGaussianBlur stdDeviation="100" result="effect1_foregroundBlur_3_2"/>
        </filter>
        <filter id="blur-purple" x="194.823" y="954.499" width="983.941" height="977.681" filterUnits="userSpaceOnUse" color-interpolation-filters="sRGB">
            <feFlood flood-opacity="0" result="BackgroundImageFix"/>
            <feBlend in="SourceGraphic" in2="BackgroundImageFix" result="shape"/>
            <feGaussianBlur stdDeviation="140" result="effect1_foregroundBlur_3_2"/>
        </filter>
        <filter id="blur-orange" x="26.522" y="550.447" width="759.054" height="753" filterUnits="userSpaceOnUse" color-interpolation-filters="sRGB">
            <feFlood flood-opacity="0" result="BackgroundImageFix"/>
            <feBlend in="SourceGraphic" in2="BackgroundImageFix" result="shape"/>
            <feGaussianBlur stdDeviation="100" result="effect1_foregroundBlur_3_2"/>
        </filter>
        <filter id="blur-blue" x="-15.573" y="578.228" width="1161.46" height="1159.48" filterUnits="userSpaceOnUse" color-interpolation-filters="sRGB">
            <feFlood flood-opacity="0" result="BackgroundImageFix"/>
            <feBlend in="SourceGraphic" in2="BackgroundImageFix" result="shape"/>
            <feGaussianBlur stdDeviation="100" result="effect1_foregroundBlur_3_2"/>
        </filter>
        <clipPath id="screen-clip">
            <path fill="#fff" d="M0 0h1080v1920H0z"/>
        </clipPath>
    </defs>

    <g clip-path="url(#screen-clip)">
        <path fill="#000" d="M0 0h1080v1920H0z"/>
        <g mix-blend-mode="hard-light" filter="url(#blur-hard)">
            <ellipse cx="449.658" cy="652.599" rx="311.126" ry="316.462" transform="rotate(70 449.658 652.599)" fill="#B011E8"/>
        </g>
        <g filter="url(#blur-purple)">
            <ellipse rx="208.812" ry="211.997" transform="matrix(.00844 .99996 -.99984 .01802 686.793 1443.34)" fill="#B310FF"/>
        </g>
        <g mix-blend-mode="lighten" opacity=".5" filter="url(#blur-orange)">
            <ellipse rx="176.773" ry="179.55" transform="matrix(.00844 .99996 -.99984 .01802 406.049 927.243)" fill="#F90"/>
        </g>
        <g mix-blend-mode="hard-light" filter="url(#blur-blue)">
            <ellipse cx="565.155" cy="1157.97" rx="379.483" ry="380.775" transform="rotate(70 565.155 1157.97)" fill="#454ACF"/>
        </g>
    </g>
    {bars}
    {subtitle}
    <image width="950" height="950" href="{goose}" y="970" x="140"/>
</svg>
""")


class GooseVideo:
    fps = 60
    width = WIDTH
    height = HEIGHT
    background_color = Color.TRANSPARENT
    duration = ff.Duration.from_audio("thought.mp3")
    audio = (ff.AudioTrack("thought.mp3", ff.Timestamp.frame(0), ff.Timestamp.EOF),)

    def render_frame(self, frame: ff.Frame, ctx: ff.Context) -> ff.Svgr:
        spectrum = ff.center_spectrum_low_frequencies(
            frame.visualize_audio(ctx, "thought.mp3", sample_size=32, smooth_level=4)
        )
        # f32 arithmetic, as in the Rust example: each step rounds to f32.
        heights = array("f", (min(max(v * 2000.0, 30.0), 400.0) for v in array("f", spectrum)))
        tops = array("f", (300.0 - h / 2.0 for h in heights))
        bars = [BAR(x=x, y=y, height=h) for x, y, h in zip(BAR_X, tops, heights, strict=False)]
        subtitle = frame.text_layout(
            ctx,
            frame.subtitle_phrase(ctx, "thought.vtt") or "",
            width=1000,
            line_height=1.2,
            x="40",
            y="34%",
            size=100,
            weight=400,
            family="JetBrains Mono",
            align="center",
            fill="white",
        )
        return FRAME(
            bars=bars,
            subtitle=subtitle.svgr() if subtitle else None,
            goose=ctx.image("goose2.png"),
        )


def main() -> int:
    return ff.cli(
        GooseVideo(),
        media=_media.media("tiktok", "media/files"),
        load_system_fonts=False,
        tmp_dir="test_render",
        default_output="out.webm",
        encoder="libvpx-vp9",
        video_options={"pixel_format": "yuva420p"},
        audio_options={"encoder": "libopus", "sample_rate": 44100, "bitrate": 128_000},
        cache_capacity=200,
    )


if __name__ == "__main__":
    sys.exit(main())

"""Port of fframes/examples/audio-announce: audio waves, glowing subtitles and an avatar video.

python examples/audio_announce.py render -o announce.mp4 [--font FAMILY]

It renders on the GPU by default, like the Rust example; `--renderer cpu` uses the CPU backend.
"""

import argparse
import sys

import _media
import fframes as ff

FPS = 30
WIDTH = 1920
HEIGHT = 1080
AVATAR_SIZE = 300

GLOWING_SUBTITLES = ff.template("""
<filter id="glow" filterUnits="userSpaceOnUse" color-interpolation-filters="sRGB">
    <feFlood flood-opacity="0" result="BackgroundImageFix" />
    <feColorMatrix in="SourceAlpha" type="matrix" values="0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 127 0" result="hardAlpha" />
    <feOffset />
    <feGaussianBlur stdDeviation="18.3" />
    <feComposite in2="hardAlpha" operator="out" />
    <feColorMatrix type="matrix" values="0 0 0 0 0.654173 0 0 0 0 0.116095 0 0 0 0 0.56808 0 0 0 1 0" />
    <feBlend mode="normal" in2="BackgroundImageFix" result="effect1_dropShadow_8_18" />
    <feBlend mode="normal" in="SourceGraphic" in2="effect1_dropShadow_8_18" result="shape" />
</filter>
<g filter="url(#glow)" stroke="#FF208B" stroke-width="1">{text}</g>
""")

AVATAR = ff.template(f"""
<image filter="url(#glow)" id="avatar" x="80" y="100" width="{AVATAR_SIZE}" height="{AVATAR_SIZE}"
       href="{{href}}"/>
""")

FRAME = ff.template(f"""
<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}">
    <image x="0" y="0" width="{WIDTH}" height="{HEIGHT}" href="{{background}}"/>
    {{subtitles}}
    {{avatar}}
    <g opacity="0.5" stroke="#fff" stroke-width="6">
        <path fill="#4C20A8" d="{{wave1}}"/>
        <path fill="mediumpurple" d="{{wave2}}"/>
        <path fill="#db2777" stroke="#fff" d="{{wave3}}"/>
        <path fill="#ea580c" transform="translate(-1600, 0)" d="{{wave4}}"/>
    </g>
</svg>
""")


class AudioAnnounce:
    fps = FPS
    width = WIDTH
    height = HEIGHT
    duration = ff.Duration.AUTO
    audio = (ff.AudioTrack("video.mp4", ff.Timestamp.second(0.0), ff.Timestamp.EOF),)

    def __init__(self, font: str | None = None):
        self.font = font or "JetBrains Mono"

    def glowing_subtitles(self, frame: ff.Frame, ctx: ff.Context) -> ff.Svgr:
        text = frame.text_layout(
            ctx,
            frame.subtitle_phrase(ctx, "subtitles.vtt") or "",
            width=1400,
            line_height=1.2,
            x=450,
            y=170,
            size=120,
            weight=400,
            family=self.font,
            align="left",
            dominant_baseline="middle",
            fill="white",
        )
        return GLOWING_SUBTITLES(text=text.svgr() if text else None)

    def render_frame(self, frame: ff.Frame, ctx: ff.Context) -> ff.Svgr:
        video = frame.video_frame(
            ctx, "transparent.mov", looping=True, width=AVATAR_SIZE, height=AVATAR_SIZE
        )
        levels = frame.visualize_audio(
            ctx, "video.mp4", sample_size=512, smooth_level=4, window="hann"
        )
        # The wave shapes are tuned by eye, as in the Rust example.
        return FRAME(
            background=ctx.image("background.png"),
            subtitles=self.glowing_subtitles(frame, ctx),
            avatar=AVATAR(href=video.image) if video else None,
            wave1=ff.wave_path(levels[::2], 100, 1200.0),
            wave2=ff.wave_path(levels[::4], 100, 400.0),
            wave3=ff.wave_path(levels[::6], 100, 1200.0),
            wave4=ff.wave_path(levels[::-1][::7], 100, 1200.0),
        )


def main() -> int:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("-f", "--font", help="Font family of the text.")
    args, rest = parser.parse_known_args()
    media = ff.Media(
        _media.folder("audio-announce"), _media.folder("audio-announce", "dynamic_media")
    )
    return ff.cli(
        AudioAnnounce(args.font),
        [sys.argv[0], *rest],
        media=media,
        codec_params={"crf": "25", "preset": "slower", "tune": "film", "bframes": "3"},
        video_options={"qmin": 0, "qmax": 69, "qcompress": 0.6, "max_qdiff": 4, "gop_size": 60},
        renderer="gpu",
        gpu_contexts=4,
        buffer_queue_size=FPS,
    )


if __name__ == "__main__":
    sys.exit(main())

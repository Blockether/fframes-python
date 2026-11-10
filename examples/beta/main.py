"""Port of fframes/examples/beta: the fframes beta announcement.

python examples/beta/main.py render -o beta.mp4

It embeds the hello-world, marketing, podcast and tiktok ports as previews.
"""

import math
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import _media
import fframes as ff
import hello_world
import podcast
import tiktok
from _f32 import f32
from fframes import Easing, Transform
from marketing import main as marketing

LINEAR = Easing.LINEAR


def spring(mass: float, stiffness: float, damping: float) -> Easing:
    return Easing.spring(mass, stiffness, damping)


def after(start: float, duration: float) -> float:
    """`start + duration` in f32, as the Rust constants and `duration` keyframes compute it."""
    return f32(f32(start) + f32(duration))


class F64:
    """A number timeline that interpolates in f64, like a Rust timeline of untyped literals.

    `ff.timeline` interpolates numbers in f32. Two f32 timelines with the same keyframes give the
    active keyframe and its eased progress; the value then interpolates in f64.
    """

    def __init__(self, *keyframes):
        self.values = [(a, b) for _, a, b, _ in keyframes]
        self.index = ff.timeline(
            *((at, float(i), float(i), e) for i, (at, _, _, e) in enumerate(keyframes))
        )
        self.progress = ff.timeline(*((at, 0.0, 1.0, e) for at, _, _, e in keyframes))

    def __call__(self, frame: ff.Frame) -> float:
        a, b = self.values[int(frame.animate(self.index))]
        return a + (b - a) * frame.animate(self.progress)


# HeadingScene

HEADING_SPRING = spring(1.0, 100.0, 16.0)
HEADING_X1 = F64((0.0, -400.0, 260.0, HEADING_SPRING))
HEADING_X2 = F64((0.0, 1000.0, 660.0, HEADING_SPRING))
HEADING = ff.template("""
<text font-family="DM Sans" font-weight="700" x="{x1}" y="40%" font-size="150" fill="#000">Welcome to the beta</text>
<text font-family="DM Sans" font-weight="700" fill="#000" x="{x2}" y="60%" font-size="150">{of}{name}</text>
""")
PLAIN_NAME = ff.svgr("<tspan>fframes</tspan>")
BUBBLE_NAME = ff.svgr(
    '<tspan dy="10" font-size="190" font-weight="normal" font-family="Bubble Bobble">'
    '<tspan fill="#7450d9">ff</tspan>rames</tspan>'
)


class HeadingScene:
    duration = 3.0

    def render_frame(self, frame: ff.Frame, ctx: ff.Context) -> ff.Svgr:
        return HEADING(
            x1=HEADING_X1(frame),
            x2=HEADING_X2(frame),
            of="of ",
            name=PLAIN_NAME if frame.index < 100 else BUBBLE_NAME,
        )


# CodeDemoScene

TILT = F64(((0.3, after(0.3, 3.0)), -0.4, 1.2, LINEAR))
CODE_X = F64(
    (0.2, -500.0, 50.0, LINEAR),
    (0.5, 50.0, 65.0, LINEAR),
    ((3.8, 4.0), 65.0, -2000.0, LINEAR),
)
CODE_OPACITY = F64(((0.3, after(0.3, 0.5)), 0.0, 1.0, LINEAR))
FERRIS_X = F64(
    (0.0, 2444.0, 1245.0, spring(1.45, 130.0, 20.0)),
    ((3.8, 4.0), 1245.0, 3920.0, LINEAR),
)
EYE_RIGHT = F64(
    ((1.4, after(1.4, 0.14)), 727.0, 777.0, LINEAR),
    ((1.7, after(1.7, 0.14)), 777.0, 727.0, LINEAR),
    ((1.9, after(1.9, 0.14)), 727.0, 777.0, LINEAR),
    ((2.1, after(2.1, 0.14)), 777.0, 727.0, LINEAR),
)
EYE_LEFT = F64(
    (1.4, 520.0, 570.0, LINEAR),
    (1.7, 570.0, 520.0, LINEAR),
    (1.9, 520.0, 570.0, LINEAR),
    ((2.1, 2.3), 570.0, 520.0, LINEAR),
)
CODE_DEMO = ff.template(
    """
<image width="1023" x="0" y="50" transform="{transform}" href="{code}" opacity="{opacity}"/>
"""
    + (Path(__file__).parent / "ferris.svg").read_text()
)


class CodeDemoScene:
    duration = ff.Duration.frames(200)

    def render_frame(self, frame: ff.Frame, ctx: ff.Context) -> ff.Svgr:
        tilt = TILT(frame)
        return CODE_DEMO(
            transform=Transform(translate=(CODE_X(frame), 0.0), skew=(tilt, -tilt + 0.4)),
            code=ctx.image("beta_code.png"),
            opacity=CODE_OPACITY(frame),
            ferris_x=FERRIS_X(frame),
            eye_right=EYE_RIGHT(frame),
            eye_left=EYE_LEFT(frame),
        )


# RenderingScene

GPU_SECOND = f32(1.1)
RENDERING_SPRING = spring(0.6, 300.0, 26.0)
BASE_FPS = ff.timeline(((GPU_SECOND, after(GPU_SECOND, 0.8)), 60.0, 100.0, LINEAR))
RENDERING_X1 = F64((0.0, -400.0, 260.0, RENDERING_SPRING), ((0.3, 2.2), 260.0, 310.0, LINEAR))
RENDERING_X2 = F64((0.0, 1900.0, 460.0, RENDERING_SPRING), ((0.3, 2.2), 460.0, 410.0, LINEAR))
PROGRESS_WIDTH = F64(
    ((0.0, 0.8), 900.0, 1000.0, LINEAR),
    ((GPU_SECOND, after(GPU_SECOND, 1.0)), 1000.0, 1350.0, LINEAR),
)
RENDERING = ff.template("""
<text font-family="DM Sans" font-weight="700" x="{x1}" y="30%" font-size="150">With the power of</text>
<text font-family="DM Sans" font-weight="700" x="{x2}" y="50%" font-size="150"><tspan font-weight="{weight}" font-size="{size}" font-family="{family}" fill="#7450d9">{kind}</tspan>{rendering}</text>
<defs>
  <linearGradient id="progress">
    <stop stop-color="#aa83de"/>
    <stop offset="1" stop-color="#00d4ff"/>
  </linearGradient>
</defs>
<text y="70%" x="11%" fill="#4b5563" font-family="JetBrains Mono" font-size="45" font-weight="600">{fps}</text>
<rect fill="url(#progress)" x="10%" y="72%" rx="12" ry="12" height="30" width="{width}"/>
""")


class RenderingScene:
    duration = ff.Duration.frames(140)

    def render_frame(self, frame: ff.Frame, ctx: ff.Context) -> ff.Svgr:
        gpu = frame.seconds > GPU_SECOND
        # Like the Rust example, the counter jitters with a random value on each frame.
        fps = int(f32(frame.animate(BASE_FPS) + f32(f32(random.random()) * 4.0)))
        return RENDERING(
            x1=RENDERING_X1(frame),
            x2=RENDERING_X2(frame),
            weight="400" if gpu else "900",
            size="170" if gpu else "150",
            family="Bubble Bobble" if gpu else "DM Sans",
            kind="  GPU    " if gpu else "native ",
            rendering="     rendering",
            fps=f"Rendering fps: {fps}",
            width=PROGRESS_WIDTH(frame),
        )


# IphoneScene

SEND_MESSAGE_TS = f32(4.8)
EXPAND_ISLAND_TS = f32(6.2)
ISLAND_WIDTH = F64(
    (0.0, 120.0, 180.0, spring(1.6, 400.0, 26.0)),
    (EXPAND_ISLAND_TS, 180.0, 348.0, spring(1.6, 300.0, 26.0)),
)
ISLAND_HEIGHT = F64((EXPAND_ISLAND_TS, 40.0, 80.0, spring(1.6, 300.0, 26.0)))
SCANNER_OPACITY = F64(((1.1, 1.4), 0.0, 1.0, LINEAR))
INVITE_SCALE = F64(((2.5, 2.7), 1.0, 1.04, LINEAR))
DISCORD_UI = ff.timeline(
    (3.0, Transform.translate(0, 1800), Transform.translate(0, 0), spring(0.4, 70.0, 16.0))
)
MESSAGE_Y = F64((SEND_MESSAGE_TS, 200.0, 0.0, spring(1.0, 240.0, 26.0)))
MESSAGE_SCALE = F64((SEND_MESSAGE_TS, 0.4, 1.0, spring(1.0, 220.0, 26.0)))
MESSAGE_OPACITY = F64(((SEND_MESSAGE_TS, after(SEND_MESSAGE_TS, 0.2)), 0.0, 1.0, LINEAR))
ISLAND_TEXT_TS = after(EXPAND_ISLAND_TS, 0.2)

MESSAGE = ff.template("""
<g>
  <image x="{x}" y="{y}" width="80" height="80" href="{avatar}"/>
  <text x="{name_x}" y="{name_y}" font-weight="500" font-size="18" fill="white">{name}</text>
  <text x="{name_x}" y="{content_y}" font-weight="500" font-size="15" fill="#cbd5e1">{content}</text>
</g>
""")

IPHONE = ff.template("""
<clipPath id="iphoneUi">
  <rect width="380" height="820" rx="60" x="780" y="150"/>
</clipPath>
<g clip-path="url(#iphoneUi)">
  <rect width="370" height="819" rx="60" x="790" y="154" fill="url(#pattern1)"/>
  <image href="{camera_ui}" width="370" height="819" rx="60" x="790" y="154"/>
  <image href="{qr}" width="300" height="300" x="830" y="390"/>
  <g fill="none" opacity="{scanner_opacity}">
    <path d="M832 439V415C832 402.297 842.297 392 855 392H882" stroke="#EBBD1D" stroke-width="2"/>
    <path d="M1086 392H1110C1122.7 392 1133 402.297 1133 415V442" stroke="#EBBD1D" stroke-width="2"/>
    <path d="M1133 650V674C1133 686.703 1122.7 697 1110 697H1083" stroke="#EBBD1D" stroke-width="2"/>
    <path d="M879 697H855C842.297 697 832 686.703 832 674V647" stroke="#EBBD1D" stroke-width="2"/>
    <rect x="884" y="715" fill="#EBBD1D" width="200" height="34" rx="16" transform-origin="center center" transform="scale({scale}, {scale})"/>
    <text font-size="16" font-weight="500" x="905" y="737" fill="#000" transform-origin="center center" transform="scale({scale}, {scale})">fframes discord invite</text>
  </g>
</g>
<g clip-path="url(#iphoneUi)">
  <g transform="{discord_ui}">
    <rect x="790" y="154" width="370" height="819" fill="#292841"/>
    <image href="{discord}" width="370" height="819" rx="60" x="791" y="152"/>
    <text font-weight="500" x="830" y="196" fill="#9ca3af" font-size="16">{clock}</text>
    {messages}
    <g transform-origin="bottom center" transform="{message_transform}" opacity="{message_opacity}">{my_message}</g>
  </g>
</g>
<image href="{iphone_frame}" x="30%" y="10%" width="800"/>
<rect x="916" y="170" width="{island_width}" transform="{island_shift}" height="{island_height}" ry="{island_ry}" fill="#000"/>
{island}
""")

ISLAND_BAR = ff.template(
    '<rect x="{x}" y="{y}" width="3" height="{height}" ry="1" fill="#6366f1"/>'
)
ISLAND_PLAYER = ff.template(
    '<text font-family="Bubble Bobble" fill="#6366f1" font-size="23" x="895" y="197">ff</text>{bars}'
)
ISLAND_INVITE = ff.svgr("""
<svg x="816" y="182" height="56" width="56" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">
  <g fill="#fff">
    <path d="M12 2C6.477 2 2 6.477 2 12c0 4.419 2.865 8.166 6.839 9.489.5.09.682-.218.682-.484 0-.236-.009-.866-.014-1.699-2.782.602-3.369-1.34-3.369-1.34-.455-1.157-1.11-1.465-1.11-1.465-.909-.62.069-.608.069-.608 1.004.071 1.532 1.03 1.532 1.03.891 1.529 2.341 1.089 2.91.833.091-.647.349-1.086.635-1.337-2.22-.251-4.555-1.111-4.555-4.943 0-1.091.39-1.984 1.03-2.682-.103-.254-.447-1.27.097-2.646 0 0 .84-.269 2.75 1.025A9.548 9.548 0 0112 6.836c.85.004 1.705.114 2.504.336 1.909-1.294 2.748-1.025 2.748-1.025.546 1.376.202 2.394.1 2.646.64.699 1.026 1.591 1.026 2.682 0 3.841-2.337 4.687-4.565 4.935.359.307.679.917.679 1.852 0 1.335-.012 2.415-.012 2.741 0 .269.18.579.688.481A9.997 9.997 0 0022 12c0-5.523-4.477-10-10-10z"/>
  </g>
</svg>
<text font-weight="500" font-size="18" x="880" y="208" fill="#fff">New collaboration invite</text>
<text font-weight="500" font-size="14" x="880" y="230" fill="#cbd5e1">dmtrKovalenko invites you to fframes</text>
""")


def discord_message(x: int, y: int, name: str, content: str, avatar: ff.Image | None):
    if avatar is None:
        return None
    return MESSAGE(
        x=x,
        y=y,
        avatar=avatar,
        name_x=x + 80,
        name_y=y + 34,
        content_y=y + 60,
        name=name,
        content=content,
    )


def island_bar_height(freq: float) -> float:
    level = f32(freq * 500.0)
    db = f32(10.0 * f32(math.log10(level))) if level > 0 else -math.inf
    return min(max(db, 4.0), 18.0)


class IphoneScene:
    duration = 8.0

    def __init__(self, hours: int, minutes: int):
        self.clock = f"{hours:02}:{minutes:02}"

    def render_frame(self, frame: ff.Frame, ctx: ff.Context) -> ff.Svgr:
        width = ISLAND_WIDTH(frame)
        height = ISLAND_HEIGHT(frame)
        spectrum = frame.visualize_audio(ctx, "beta.mp3", sample_size=16, smooth_level=3)
        seconds = frame.seconds
        island = None
        if frame.index > 8 and seconds < EXPAND_ISLAND_TS:
            bars = []
            for i in range(1, 7):
                db = island_bar_height(spectrum[i])
                bars.append(
                    ISLAND_BAR(x=1025.0 + i * 3.5 + i, y=f32(190.0 - f32(db / 2.0)), height=db)
                )
            island = ISLAND_PLAYER(bars=bars)
        elif seconds > ISLAND_TEXT_TS:
            island = ISLAND_INVITE
        return IPHONE(
            camera_ui=ctx.image("camera_ui.png"),
            qr=ctx.image("qr.png"),
            scanner_opacity=SCANNER_OPACITY(frame),
            scale=INVITE_SCALE(frame),
            discord_ui=frame.animate(DISCORD_UI),
            discord=ctx.image("discord_ui.png"),
            clock=self.clock,
            messages=[
                discord_message(
                    800,
                    370,
                    "John Doe",
                    "Hey, How I can export the .webm video?",
                    ctx.image("john.png"),
                ),
                discord_message(
                    800,
                    450,
                    "Dmitriy Kovalenko",
                    "Just change out file extension to .webm",
                    ctx.image("dmitriy.png"),
                ),
                discord_message(
                    800,
                    530,
                    "Linus Torvalds",
                    "https://github.com/torvalds",
                    ctx.image("torvalds.png"),
                ),
            ],
            message_transform=Transform(
                translate=(0.0, MESSAGE_Y(frame)), scale=MESSAGE_SCALE(frame)
            ),
            message_opacity=MESSAGE_OPACITY(frame),
            my_message=discord_message(
                800, 620, "Me", "https://github.com/theawesome", ctx.image("me.png")
            ),
            iphone_frame=ctx.image("iphone_frame.png"),
            island_width=width,
            island_shift=Transform.translate(-(width - 120.0) / 2.0, 0),
            island_height=height,
            island_ry=height / 2.0,
            island=island,
        )


# GithubScene

GITHUB_X = F64((0.0, 1920.0, 0.0, spring(0.3, 90.0, 26.0)))
GITHUB_Y = F64(((0.8, 6.3), 0.0, -1700.0, LINEAR))
GITHUB = ff.template('<image width="1920" href="{image}" transform="{transform}"/>')


class GithubScene:
    duration = 5.0
    overlap = (0.3, 0.0)

    def render_frame(self, frame: ff.Frame, ctx: ff.Context) -> ff.Svgr | None:
        image = ctx.image("github_screenshot.png")
        if image is None:
            return None
        return GITHUB(image=image, transform=Transform.translate(GITHUB_X(frame), GITHUB_Y(frame)))


# BetaExamples

VIDEO_SCALE = f32(0.62)
VIDEO_OFFSET_Y = 320
VIDEO_OFFSET_X = f32(f32(1920.0 - f32(1920.0 * VIDEO_SCALE)) / 2.0)
MARKETING_TS = f32(2.6)
PODCAST_TS = f32(4.8)
TIKTOK_TS = f32(6.8)
LIST_SPRING = spring(1.0, 140.0, 16.0)
EXAMPLES_SPRING = spring(1.0, 100.0, 16.0)
SUBTITLE_X = F64((0.0, 200.0, 960.0, EXAMPLES_SPRING))
FIRST_X = F64((0.0, 1700.0, 960.0, EXAMPLES_SPRING))
LIST = ff.timeline(
    (MARKETING_TS, Transform.translate(0, 0), Transform.translate(0, -180), LIST_SPRING),
    (PODCAST_TS, Transform.translate(0, -180), Transform.translate(0, -380), LIST_SPRING),
    (TIKTOK_TS, Transform.translate(0, -380), Transform.translate(0, -580), LIST_SPRING),
)
PREVIEW = Transform(translate=(VIDEO_OFFSET_X, VIDEO_OFFSET_Y), rotate=0.0, scale=VIDEO_SCALE)
TIKTOK_PREVIEW = Transform(
    translate=(f32(VIDEO_OFFSET_X + 1188.0), VIDEO_OFFSET_Y), rotate=90.0, scale=VIDEO_SCALE
)
EXAMPLES = ff.template(
    """
<defs>
  <linearGradient id="text">
    <stop stop-color="#4338ca"/>
    <stop offset="1" stop-color="#a21caf"/>
  </linearGradient>
  <clipPath id="text-clip">
    <rect fill="red" width="100%" height="135" y="115"/>
  </clipPath>
  <filter id="shadow" width="200%" height="200%" color-interpolation-filters="sRGB">
    <feDropShadow stdDeviation="40" flood-opacity="0.3"/>
  </filter>
  <clipPath id="preview-clip">
    <rect x="@X" y="@Y" height="@H" width="@W" rx="50" ry="50"/>
  </clipPath>
</defs>
<text font-family="DM Sans" font-weight="700" text-anchor="middle" x="{subtitle_x}" y="8%" font-size="60" fill="url(#text)">to help you get started</text>
<g clip-path="url(#text-clip)">
  <g font-family="DM Sans" font-weight="700" fill="#000" text-anchor="middle" font-size="120" transform="{list}">
    <text x="{first_x}" y="220">"Hello world" video</text>
    <text x="960" y="394">Marketing Pitch Video</text>
    <text x="960" y="594">Podcast Visualization</text>
    <text x="960" y="794">TikTok-like video</text>
  </g>
</g>
<rect filter="url(#shadow)" width="@W" height="@H" x="@X" y="@Y" rx="50" ry="50" stroke="#4338ca" stroke-width="8"/>
<g clip-path="url(#preview-clip)">
  <g transform="{preview}">{video}</g>
</g>
""".replace("@X", repr(VIDEO_OFFSET_X))
    .replace("@Y", str(VIDEO_OFFSET_Y))
    .replace("@H", repr(f32(1080.0 * VIDEO_SCALE)))
    .replace("@W", repr(f32(1920.0 * VIDEO_SCALE)))
)


class BetaExamples:
    duration = ff.Duration.frames(500)

    def __init__(self):
        self.hello_world = hello_world.HelloWorld("Hello, Beta!")
        self.marketing = marketing.MarketingVideo("beta.mp3")
        self.podcast = podcast.PodcastVideo(
            goose_audio="beta.mp3", duck_audio="beta.mp3", guest_audio="beta.mp3"
        )
        self.tiktok = tiktok.GooseVideo()

    def render_frame(self, frame: ff.Frame, ctx: ff.Context) -> ff.Svgr:
        seconds = frame.seconds
        if seconds < MARKETING_TS:
            video = self.hello_world.render_frame(frame, ctx)
        elif seconds < PODCAST_TS:
            video = self.marketing.render_frame(frame, ctx)
        elif seconds < TIKTOK_TS:
            video = self.podcast.render_frame(frame.into_global(), ctx)
        else:
            video = self.tiktok.render_frame(frame.into_global(), ctx)
        return EXAMPLES(
            subtitle_x=SUBTITLE_X(frame),
            list=frame.animate(LIST),
            first_x=FIRST_X(frame),
            preview=TIKTOK_PREVIEW if seconds >= TIKTOK_TS else PREVIEW,
            video=video,
        )


# EndScene

END_NAME_OPACITY = F64(((0.1, 0.2), 0.0, 1.0, LINEAR))
END_BETA_OPACITY = F64(((0.6, 0.8), 0.0, 1.0, LINEAR))
END_BETA = ff.timeline(
    (
        (0.6, 0.8),
        Transform.rotate(-60.0, (1300.0, 590.0)),
        Transform.rotate(-25.0, (1300.0, 590.0)),
        LINEAR,
    )
)
END = ff.template("""
<linearGradient id="text">
  <stop stop-color="#4338ca"/>
  <stop offset="1" stop-color="#a21caf"/>
</linearGradient>
<text font-size="190" font-family="Bubble Bobble" x="50%" y="50%" text-anchor="middle" opacity="{name_opacity}" fill="black"><tspan fill="#7450d9">ff</tspan>rames</text>
<text font-size="80" x="1220" y="605" fill="url(#text)" font-family="Fredoka One" opacity="{beta_opacity}" transform="{beta}">beta</text>
""")


class EndScene:
    duration = 2.0

    def render_frame(self, frame: ff.Frame, ctx: ff.Context) -> ff.Svgr:
        return END(
            name_opacity=END_NAME_OPACITY(frame),
            beta_opacity=END_BETA_OPACITY(frame),
            beta=frame.animate(END_BETA),
        )


# BetaVideo

VIDEO = ff.template("""
<svg xmlns="http://www.w3.org/2000/svg" width="1920" height="1080">
  <image width="1920" height="1080" x="0" y="0" fill="#fff" href="{background}"/>
  {scenes}
</svg>
""")


class BetaVideo:
    fps = 60
    width = 1920
    height = 1080
    duration = None

    def __init__(self, hours: int, minutes: int):
        self.audio = [
            ("beta.mp3", ff.Timestamp.frame(0), None),
            ("pop.mp3", ff.Timestamp.frame(95), None),
            ("pop.mp3", ff.Timestamp.frame(440), None),
        ]
        self.scenes = [
            HeadingScene(),
            CodeDemoScene(),
            RenderingScene(),
            IphoneScene(hours, minutes),
            GithubScene(),
            BetaExamples(),
            EndScene(),
        ]

    def render_frame(self, frame: ff.Frame, ctx: ff.Context) -> ff.Svgr:
        return VIDEO(background=ctx.image("background.png"), scenes=ctx.render_scenes(frame))


def main() -> int:
    # Like the Rust CombinedMediaProvider: tiktok, marketing and hello-world media are
    # include_media_dir! (mono audio); ./media is read from disk (stereo).
    media = ff.Media(
        _media.folder("tiktok", "media/files"),
        _media.folder("marketing"),
        _media.folder("hello-world"),
        _media.folder("beta"),
        mono=[True, True, True, False],
    )
    return ff.cli(
        BetaVideo(hours=12, minutes=4),
        media=media,
        encoder="libx264",
        default_font="Inter",
        cache_capacity=200,
    )


if __name__ == "__main__":
    sys.exit(main())

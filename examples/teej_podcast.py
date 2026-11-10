"""Port of fframes/examples/teej-podcast: two camera recordings and an animated chapter list.

python examples/teej_podcast.py render -o teej.mp4
"""

import sys

import _media
import fframes as ff
from fframes import Easing, Transform

FRAME_PADDING = 40
FRAME_WIDTH = 640
FRAME_HEIGHT = 1000
CHAPTERS_START_X = FRAME_WIDTH * 2 + FRAME_PADDING * 3
CHAPTERS_START_Y = 145
CHAPTER_HEIGHT = 60
CHAPTER_WIDTH = 490
CHAPTER_PADDING = 15
CHAPTER_TEXT_PADDING = 10
FONT = {"family": "Sofia Sans Semi Condensed", "size": 26, "weight": 400}
CHAPTER_EASING = Easing.spring(0.45, 130.0, 20.0)

CHAPTERS = [
    ("Introduction to Lunch Bites Podcast", "00:00"),
    ("Tech Sponsorships and Streaming Quality", "01:51"),
    ("Flexing in LA: The Casa Bonita Experience", "02:33"),
    ("Viral Moments: The Post-It Note Debate", "03:00"),
    ("Zuckerberg's Rebranding and Tech Culture", "04:51"),
    ("The Intersection of Geek Culture and Popularity", "14:55"),
    ("Psychedelic Fantasy Baseball and AI", "16:48"),
    ("The Rise of Meme Coins", "17:52"),
    ("Trump Coin and the Crypto Circus", "19:13"),
    ("Fart Coin: The AI Millionaire", "21:50"),
    ("OpenAI and the Future of AI Models", "25:46"),
    ("Influencers and the Coding Landscape", "30:10"),
]


def parse_duration_to_seconds(time: str) -> int:
    """Seconds of "mm:ss" or "hh:mm:ss"."""
    parts = [int(part) for part in time.split(":")]
    if len(parts) == 2:
        return parts[0] * 60 + parts[1]
    if len(parts) == 3:
        return parts[0] * 3600 + parts[1] * 60 + parts[2]
    raise ValueError("Invalid time format string, expected either HH:MM:SS or MM:SS")


def chapter_y(index: int) -> int:
    return CHAPTERS_START_Y + index * (CHAPTER_HEIGHT + CHAPTER_PADDING)


def chapters_timeline(starts: list[int]) -> ff.Timeline:
    """The highlighter moves to each chapter at its start. The spring sets the real length."""
    keyframes, position = [], 0
    for index, start in enumerate(starts):
        target = chapter_y(index) - CHAPTERS_START_Y
        keyframes.append(((start, start + 1.0), position, target, CHAPTER_EASING))
        position = target
    return ff.timeline(*keyframes)


def frame_template(count: int) -> ff.Template:
    """The frame markup; the chapter rectangles are static, so they are built once here."""
    rects = "".join(
        f'<rect x="{CHAPTERS_START_X}" y="{chapter_y(i)}" width="{CHAPTER_WIDTH}" '
        f'height="{CHAPTER_HEIGHT}" fill="#404040" rx="5" ry="5" />'
        for i in range(count)
    )
    texts = "".join(
        f'<text x="{CHAPTERS_START_X + CHAPTER_TEXT_PADDING}" '
        f'y="{chapter_y(i) + CHAPTER_HEIGHT // 2 + 5}" dominant-baseline="middle" '
        f'fill="{{fill_{i}}}" font-family="{FONT["family"]}" font-weight="{FONT["weight"]}" '
        f'font-size="{FONT["size"]}"><tspan>{{start_{i}}}</tspan><tspan>{{separator}}</tspan>'
        f"<tspan>{{title_{i}}}</tspan></text>"
        for i in range(count)
    )
    right_x = FRAME_WIDTH + FRAME_PADDING * 2
    markup = f"""
<svg xmlns="http://www.w3.org/2000/svg" width="1920" height="1080">
    <rect x="0" y="0" width="1920" height="1080" fill="#1A191B" />
    <defs>
        <clipPath id="clip-left-frame">
            <rect id="left-video-frame" x="{FRAME_PADDING}" y="{FRAME_PADDING}"
                  width="{FRAME_WIDTH}" height="{FRAME_HEIGHT}" />
        </clipPath>
        <clipPath id="clip-right-frame">
            <rect id="right-video-frame" x="{right_x}" y="{FRAME_PADDING}"
                  width="{FRAME_WIDTH}" height="{FRAME_HEIGHT}" />
        </clipPath>
    </defs>
    <use href="#left-video-frame" fill="none" stroke="#000" stroke-width="10" />
    <image id="avatar" x="-600" y="0" width="1920" stroke-width="6" stroke="#fff"
           clip-path="url(#clip-left-frame)" preserveAspectRatio="xMidYMid meet" href="{{left}}" />
    <use href="#right-video-frame" fill="none" stroke="#000" stroke-width="10" />
    <image id="avatar" x="8" y="0" width="1920" clip-path="url(#clip-right-frame)"
           preserveAspectRatio="xMidYMid meet" href="{{right}}" />
    <text x="1400" y="40" alignment-baseline="text-before-edge" font-size="75" fill="#fff"
          font-family="JetBrains Mono">2D: Rust</text>
    <g>
        {rects}
        <rect x="{CHAPTERS_START_X}" y="{CHAPTERS_START_Y}" width="{CHAPTER_WIDTH}"
              height="{CHAPTER_HEIGHT}" fill="#ff6900" rx="5" ry="5" transform="{{highlight}}" />
        {texts}
    </g>
</svg>
"""
    return ff.template(markup)


class TeejPodcast:
    fps = 24
    width = 1920
    height = 1080
    duration = None  # the length of the recordings
    audio = (("left.mp4", 0, None), ("right.mp4", 0, None))

    def __init__(self, chapters: list[tuple[str, str]]):
        self.titles = [title for title, _ in chapters]
        self.starts = [start for _, start in chapters]
        self.start_seconds = [parse_duration_to_seconds(start) for start in self.starts]
        self.highlight = chapters_timeline(self.start_seconds)
        self.frame = frame_template(len(chapters))
        self.left = ff.Clip("left.mp4", 0.0)
        self.right = ff.Clip("right.mp4", 0.0)
        self.fitted_titles: list[str] | None = None
        # The parts of the frame that never change.
        self.static = {"separator": "  "} | {f"start_{i}": s for i, s in enumerate(self.starts)}

    def fit_titles(self, frame: ff.Frame, ctx: ff.Context) -> list[str] | None:
        """Titles cut with an ellipsis to fit after the "mm:ss" prefix; None without the font."""
        separator = frame.text_width(ctx, "  ", **FONT)
        if separator is None:
            return None
        max_width = CHAPTER_WIDTH - CHAPTER_TEXT_PADDING * 2
        titles = []
        for title, start in zip(self.titles, self.starts):
            prefix = frame.text_width(ctx, start, **FONT)
            if prefix is None:
                return None
            fitted = frame.text_fit(ctx, title, max(0, max_width - prefix - separator), **FONT)
            if fitted is None:
                return None
            titles.append(fitted)
        return titles

    def render_frame(self, frame: ff.Frame, ctx: ff.Context) -> ff.Svgr:
        left = self.left.image(frame, ctx) or ctx.image("left.jpg")
        right = self.right.image(frame, ctx) or ctx.image("right.jpg")

        # The chapter that contains this frame; the last one stays active until the end.
        t = int(frame.seconds)
        starts = self.start_seconds
        active = next(
            (i for i in range(len(starts) - 1) if starts[i] <= t < starts[i + 1]),
            len(starts) - 1,
        )
        if self.fitted_titles is None:
            self.fitted_titles = self.fit_titles(frame, ctx)
        titles = self.fitted_titles or self.titles

        values = dict(self.static)
        for i, title in enumerate(titles):
            values[f"title_{i}"] = title
            values[f"fill_{i}"] = "#000" if i == active else "#fff"
        return self.frame(
            left=left,
            right=right,
            highlight=Transform.translate(0, frame.animate(self.highlight)),
            **values,
        )


def main() -> int:
    macos = sys.platform == "darwin"
    return ff.cli(
        TeejPodcast(CHAPTERS),
        media=_media.media("teej-podcast", "dynamic_media"),
        encoder="hevc_videotoolbox" if macos else "libx265",
        codec_params={"crf": "23", "preset": "slow", "bframes": "3"},
        video_options={"qmin": 0, "qmax": 69, "qcompress": 0.6, "max_qdiff": 4, "gop_size": 24},
        renderer="gpu",
        gpu_contexts="max",
        buffer_queue_size=20,
    )


if __name__ == "__main__":
    sys.exit(main())

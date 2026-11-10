"""Port of fframes/examples/captions: one media track, four presets and a typed word highlight.

python examples/captions.py render -o captions.mp4
"""

import sys

import _media
import fframes as ff

MODES = [("highlight", 90, 230), ("karaoke", 1010, 230), ("reveal", 90, 660), ("word", 1010, 660)]

UNDERLINE = ff.template(
    '<path d="M 0 {y} H {width}" stroke="{color}" stroke-width="4" stroke-linecap="round" />'
)
CIRCLE = ff.template(
    '<ellipse cx="{cx}" cy="{cy}" rx="{rx}" ry="{ry}" fill="none" stroke="{color}" stroke-width="3" />'
)
WORD = ff.template("<g>{decoration}{text}</g>")

FRAME = ff.template("""
<svg xmlns="http://www.w3.org/2000/svg" width="1920" height="1080" viewBox="0 0 1920 1080">
    <rect width="1920" height="1080" fill="#0c1423" />
    <path d="M 960 180 V 980 M 70 570 H 1850" stroke="#253248" stroke-width="2" />
    <g font-family="DM Sans" font-weight="500" fill="#f4f7fb">
        <text x="90" y="110" font-size="54">One transcript, four treatments</text>
        <g font-size="26" fill="#91a3b9">
            <text x="90" y="210">HIGHLIGHT + TYPED WORD EFFECTS</text>
            <text x="1010" y="210">KARAOKE</text>
            <text x="90" y="640">REVEAL</text>
            <text x="1010" y="640">WORD</text>
        </g>
    </g>
    {highlight}{karaoke}{reveal}{word}
</svg>
""")


def highlight(word: ff.CaptionWord, text: ff.Svgr) -> ff.Svgr:
    meta = word.metadata
    effect, color = meta.get("effect"), meta.get("color")
    if effect == "underline" and isinstance(color, str):
        decoration = UNDERLINE(y=word.height - 3.0, width=word.width, color=color)
    elif effect == "circle" and isinstance(color, str):
        w, h = word.width, word.height
        decoration = CIRCLE(cx=w / 2, cy=h / 2, rx=w / 2 + 10, ry=h / 2 + 5, color=color)
    else:
        decoration = None
    return WORD(decoration=decoration, text=text)


class CaptionVideo:
    fps = 30
    width = 1920
    height = 1080
    duration = 8.0
    audio = None

    def __init__(self):
        self.modes = [
            ff.Captions("speech.json", x, y, 820, 240)
            .font("DM Sans", 58)
            .font_weight(500)
            .mode(mode)
            .active_fill("#77e6cf")
            .upcoming_fill("#64748b")
            .outline("#0c1423", 2.0)
            for mode, x, y in MODES
        ]

    def render_frame(self, frame: ff.Frame, ctx: ff.Context) -> ff.Svgr:
        first, karaoke, reveal, word = self.modes
        return FRAME(
            highlight=first.highlight_with(frame, ctx, highlight),
            karaoke=karaoke.render(frame, ctx),
            reveal=reveal.render(frame, ctx),
            word=word.render(frame, ctx),
        )


if __name__ == "__main__":
    sys.exit(ff.cli(CaptionVideo(), media=_media.media("captions", mono=True)))

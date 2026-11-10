"""Port of fframes/examples/conference-splash-screen.

python examples/conference_splash_screen.py render -o talk.mp4 [--talk 0|NAME]
"""

import argparse
import json
import re
import sys

import _media
import fframes as ff
from fframes import Easing, Transform

EXAMPLE = "conference-splash-screen"
FPS = 24
TITLE_Y = 350
SPRING = Easing.spring(mass=4.0, stiffness=30.0, damping=25.0)
DASH_SPRING = Easing.spring(mass=4.0, stiffness=80.0, damping=55.0)


SPONSOR_TEXT_OPACITY = ff.timeline(((2.0, 2.2), 0.0, 1.0, Easing.LINEAR))
SPONSOR_YEAR = ff.timeline((0.4, Transform.translate(0, 0), Transform.translate(0, 200), SPRING))
SPONSOR_TITLE = ff.timeline(
    (0.4, Transform.translate(0, 0), Transform.translate(320, -350), SPRING)
)
SPONSOR_SHAPE_OPACITY = ff.timeline(((1.0, 2.5), 0.0, 1.0, Easing.LINEAR))
SPONSOR_HEADING_OPACITY = ff.timeline(((1.2, 1.4), 0.0, 1.0, Easing.LINEAR))
SPONSOR_LOGOS = ff.timeline(
    (
        1.2,
        Transform.translate(0, 600),
        Transform.translate(0, 0),
        Easing.spring(mass=0.8, stiffness=100.0, damping=16.0),
    )
)

# The Rust tilt is an f64 timeline (0.4 => 1.2 at 0.3, 1.2 => 0.8 at 2.3..4.1). Timelines
# interpolate in f32, so these give the eased progress of each keyframe and `tilt` interpolates
# in f64, as Rust does.
TILT_IN = ff.timeline((0.3, 0.0, 1.0, Easing.LINEAR), ((2.3, 4.1), 1.0, 1.0, Easing.LINEAR))
TILT_OUT = ff.timeline((0.3, 0.0, 0.0, Easing.LINEAR), ((2.3, 4.1), 0.0, 1.0, Easing.LINEAR))


def tilt(frame: ff.Frame) -> float:
    if frame.seconds < 2.3:
        return 0.4 + (1.2 - 0.4) * frame.animate(TILT_IN)
    return 1.2 + (0.8 - 1.2) * frame.animate(TILT_OUT)


SPEAKER_DASH = ff.timeline((0.0, 300.0, 0.0, DASH_SPRING))

SHAPE = "M663.134 750.24C660.25 738.885 666.014 724.693 660.25 713.341C657.367 701.986 648.72 701.986 645.84 693.471C634.31 670.763 619.899 645.219 619.899 616.833C619.899 594.125 611.252 571.418 608.372 548.711C608.372 537.356 608.372 526.004 608.372 514.648C608.372 508.972 608.372 503.296 605.489 497.62C605.489 494.781 605.489 489.105 602.605 489.105L605.489 480.589C605.489 477.749 631.429 477.749 640.076 477.749C654.487 477.749 666.014 477.749 680.424 480.589C709.248 480.589 732.305 480.589 761.126 477.749C821.651 469.234 847.592 443.69 862.002 435.174C916.764 398.275 942.704 332.99 942.704 332.99C951.351 313.122 951.351 276.22 971.525 262.028C994.583 242.16 1032.05 244.997 1057.99 233.645C1072.4 227.969 1083.93 222.29 1101.23 225.129C1112.75 227.969 1132.93 242.16 1138.69 222.29C1135.81 219.453 1132.93 216.613 1130.05 213.774C1153.1 210.937 1130.05 162.683 1121.4 151.331C1106.99 137.136 1086.81 128.621 1063.75 122.945C1034.93 114.429 1009 105.913 983.055 111.593C936.941 120.108 939.821 94.5612 913.884 94.5612C882.179 94.5612 824.535 97.4008 813.004 128.621C807.241 142.815 804.361 142.815 795.714 154.168C789.947 162.683 795.714 171.199 792.831 182.551C789.947 193.906 784.184 233.645 778.42 247.836C769.773 270.544 758.243 298.927 738.069 298.927C709.248 301.767 686.191 304.606 663.134 296.091C648.72 290.415 625.663 281.899 614.136 279.059C559.374 256.352 550.727 233.645 550.727 233.645C544.964 225.129 530.553 208.098 524.787 188.23C519.023 165.523 507.493 148.492 504.613 137.136C498.849 125.784 490.202 105.913 481.555 86.0456C470.025 60.4987 455.615 40.6309 444.088 32.1153C426.794 17.9236 412.383 -4.7837 377.796 0.892351C372.032 0.892351 348.975 3.73194 331.681 17.9236C320.151 26.4393 317.271 46.307 305.741 63.3383C299.977 71.8539 288.447 100.237 279.803 122.945C274.037 139.976 271.156 151.331 262.509 157.007C256.743 162.683 250.979 168.359 242.332 165.523C236.569 162.683 230.805 159.844 225.042 157.007C216.394 151.331 199.1 120.108 187.572 100.237C178.925 80.3695 158.75 51.983 147.221 37.7914C129.928 15.084 121.282 9.40799 95.342 9.40799C43.4626 9.40799 37.6982 37.7914 14.6409 80.3695C3.11221 100.237 0.22982 128.621 -19.9454 151.331C-28.592 162.683 -66.0603 216.613 -92 225.129V616.833V613.996C-89.1178 608.317 -89.1178 602.641 -86.2356 599.802C-74.7069 579.934 -51.6496 560.066 -40.1206 537.356C-34.3564 526.004 -25.7099 514.648 -19.9454 500.457C-17.0633 491.941 -14.1809 474.913 -8.41675 466.397C-2.65227 455.042 8.87639 452.205 20.4053 449.366C40.5806 446.526 54.9913 474.913 78.0489 486.265C86.6955 491.941 132.81 506.136 147.221 508.972C170.279 514.648 193.336 517.488 216.394 523.164C227.922 526.004 239.452 526.004 253.863 528.843C265.39 528.843 308.624 531.68 308.624 534.519C288.447 545.871 274.037 574.258 265.39 596.965C256.743 619.672 250.979 645.219 242.332 665.087C230.805 687.794 207.747 699.15 210.629 727.533C210.629 738.885 213.512 750.24 210.629 761.592C207.747 775.787 201.983 784.303 199.1 798.495C193.336 815.523 187.572 869.453 181.807 883.648L227.922 877.969C233.685 866.617 236.569 815.523 239.452 809.847C248.099 784.3 259.626 764.432 276.92 744.564C294.214 724.693 294.214 701.986 302.861 679.279C314.388 653.732 328.798 636.704 343.208 613.996C369.149 574.258 386.443 520.327 438.321 508.972C444.088 508.972 475.792 531.68 490.202 545.871C507.493 562.903 524.787 579.934 536.317 602.641C556.491 645.219 576.668 707.662 582.431 738.885C585.315 758.756 588.195 758.756 602.605 775.787C608.372 781.463 619.899 804.171 625.663 812.686C628.546 821.202 637.193 841.07 640.076 852.425C642.956 858.101 651.603 877.969 657.367 895H700.601C683.308 846.746 668.897 798.495 663.134 750.24Z"

SPONSOR = ff.template(
    """
<image width="1920" height="1080" x="0" y="0" href="{background}"/>
<text x="70%" y="12%" font-size="70" fill="#FFFFFF" opacity="{year_opacity}" transform="{year}"><tspan font-weight="600" font-family="Montserrat">Warsaw </tspan><tspan font-family="JetBrains Mono">2025</tspan></text>
<text font-family="Montserrat" font-weight="400" x="50%" y="50%" text-anchor="middle" dominant-baseline="middle" font-size="200" fill="#fff" transform="{title}">FUN <tspan fill="#C24F1E">OCaml</tspan></text>
<svg y="250" width="1140" height="828" viewBox="0 0 1140 828" fill="none" xmlns="http://www.w3.org/2000/svg">
  <path id="{index}" fill="#562F1F" opacity="{shape_opacity}" d="SHAPE"/>
</svg>
<text x="50%" y="620" font-size="60" font-family="Inter 18pt" font-weight="600" fill="#d43f00" dominant-baseline="middle" opacity="{heading_opacity}">Sponsors and Partners</text>
<image x="720" y="670" width="1150" transform="{logos}" href="{sponsors}"/>
""".replace("SHAPE", SHAPE)
)

SPEAKER = ff.template(
    """
<image width="1920" x="0" y="0" href="{background}"/>
{title}
<svg x="1000" y="250" width="140" height="134" viewBox="0 0 140 134" fill="none" xmlns="http://www.w3.org/2000/svg">
  <path d="M-4.94719e-06 2H134.8C136.567 2 138 3.43269 138 5.2V134" stroke="#FFFBFB" stroke-width="3" stroke-dasharray="300" stroke-dashoffset="{dash}"/>
</svg>
<svg x="40" y="{corner_y}" width="140" height="134" viewBox="0 0 140 134" fill="none" xmlns="http://www.w3.org/2000/svg">
  <path d="M137.2 132H5.19999C3.43268 132 2 130.567 2 128.8V0" stroke="#FFFBFB" stroke-width="3" stroke-dasharray="300" stroke-dashoffset="{dash}"/>
</svg>
{abstract}
<pattern id="speaker" x="0%" y="0%" height="100%" width="100%" viewBox="0 0 480 480">
  <image x="0%" y="0%" width="480" height="480" href="{avatar}"/>
</pattern>
<filter id="shadow">
  <feDropShadow dx="3" dy="3" stdDeviation="8" flood-color="#000" flood-opacity="0.5"/>
</filter>
<g transform="{tilt}">
  <rect filter="url(#shadow)" rx="60" ry="60" x="1200" y="162" width="661" height="770" fill="#525764"/>
  <circle r="220" cx="1540" cy="470" fill="url(#speaker)"/>
  <rect x="{name_x}" y="773" width="{name_width}" height="90" rx="20" ry="20" fill="white"/>
  <text dominant-baseline="middle" fill="#D54000" text-anchor="middle" x="1534" y="820" font-weight="700" font-family="Inter 24pt" font-size="54">{name}</text>
</g>
"""
)

FRAME = ff.template(
    """
<svg xmlns="http://www.w3.org/2000/svg" width="1920" height="1080">{scenes}</svg>
"""
)


class SponsorScene:
    duration = 3.8

    def render_frame(self, frame: ff.Frame, ctx: ff.Context) -> ff.Svgr:
        return SPONSOR(
            background=ctx.image("background_gradient.jpg"),
            year_opacity=frame.animate(SPONSOR_TEXT_OPACITY),
            year=frame.animate(SPONSOR_YEAR),
            title=frame.animate(SPONSOR_TITLE),
            index=frame.index,
            shape_opacity=frame.animate(SPONSOR_SHAPE_OPACITY),
            heading_opacity=frame.animate(SPONSOR_HEADING_OPACITY),
            logos=frame.animate(SPONSOR_LOGOS),
            sponsors=ctx.image("sponsors.png"),
        )


class SpeakerScene:
    duration = 4.0

    def __init__(self, talk: dict):
        self.speaker_name = talk["speaker_name"]
        self.talk_title = talk["proposal_title"]
        self.talk_description = talk["abstract"]
        self.avatar = talk.get("avatar")
        # Rust compares byte lengths.
        title_len = len(self.talk_title.encode())
        description_len = len(self.talk_description.encode())
        self.title_size = 70 if title_len < 50 or description_len <= 300 else 56
        self.abstract_size = 32 if description_len > 600 else 36 if description_len > 300 else 48

    def render_frame(self, frame: ff.Frame, ctx: ff.Context) -> ff.Svgr:
        angle = tilt(frame)
        title = frame.text_layout(
            ctx,
            self.talk_title,
            width=970,
            line_height=1.2,
            x=90,
            y=TITLE_Y,
            size=self.title_size,
            family="Inter 18pt",
            weight=800,
            align="left",
            fill="white",
        )
        if title is None:
            raise RuntimeError("failed to wrap the title")
        name_width = frame.text_width(
            ctx, self.speaker_name, family="Inter 24pt", size=54, weight=700
        )
        if name_width is None:
            raise RuntimeError("Failed to calculate speaker name text width")
        name_width += 32
        abstract_y = TITLE_Y + int(title.height)
        abstract = frame.text_layout(
            ctx,
            self.talk_description,
            width=1000,
            line_height=1.2,
            x=90,
            y=abstract_y,
            size=self.abstract_size,
            family="Inter 24pt",
            weight=400,
            align="left",
            fill="white",
        )
        if abstract is None:
            raise RuntimeError("failed to wrap the abstract text")
        avatar = (self.avatar and ctx.image(self.avatar)) or ctx.image("speaker_placeholder.png")
        return SPEAKER(
            background=ctx.image("background_2025.png"),
            title=title.svgr(),
            dash=frame.animate(SPEAKER_DASH),
            corner_y=abstract_y + int(abstract.height) - 110,
            abstract=abstract.svgr(),
            avatar=avatar,
            tilt=Transform.skew(angle, -angle + 0.4),
            name_x=1534 - name_width // 2,
            name_width=name_width,
            name=self.speaker_name,
        )


class ConferenceVideo:
    fps = FPS
    width = 1920
    height = 1080
    duration = ff.Duration.from_audio("track.mp3")
    audio = (("track.mp3", ff.Timestamp.frame(0), ff.Timestamp.EOF),)

    def __init__(self, talk: dict):
        self.scenes = [SponsorScene(), SpeakerScene(talk)]

    def render_frame(self, frame: ff.Frame, ctx: ff.Context) -> ff.Svgr:
        return FRAME(scenes=ctx.render_scenes(frame))


def load_talks() -> list[dict]:
    return json.loads((_media.ROOT / "examples" / EXAMPLE / "sessions.json").read_text())


def find_talk(talks: list[dict], query: str) -> dict:
    """A talk by index (`3`) or by a case-insensitive part of the speaker's name."""
    if re.fullmatch(r"\+?[0-9]+", query):
        index = int(query)
        if index >= len(talks):
            raise SystemExit(f"error: there are {len(talks)} talks, index {index} is out of range")
        return talks[index]
    query = query.lower()
    for talk in talks:
        if query in talk["speaker_name"].lower():
            return talk
    raise SystemExit(f'error: no talk by a speaker matching "{query}"')


def main() -> int:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument(
        "--talk", default="0", help="An index into sessions.json or part of the speaker's name."
    )
    args, rest = parser.parse_known_args()
    talk = find_talk(load_talks(), args.talk)
    media = ff.Media(_media.folder(EXAMPLE), _media.folder(EXAMPLE, "dynamic_media"))
    return ff.cli(
        ConferenceVideo(talk),
        [sys.argv[0], *rest],
        media=media,
        tmp_dir="test_video",
        encoder="libx265",
        video_options={"qmin": 0, "qmax": 69, "qcompress": 0.6, "max_qdiff": 4, "gop_size": 250},
        concurrency=1,
        cache_capacity=200,
    )


if __name__ == "__main__":
    sys.exit(main())

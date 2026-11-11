"""Port of fframes/examples/signal-lab: a 24-second motion study with a synthesized soundtrack.

python examples/signal_lab.py render -o signal-lab.mp4
"""

import struct
import sys
from typing import ClassVar

import _media
import fframes as ff
from fframes import Transform

SCENE_SECONDS = 6.0
PAPER = "#eeeae2"
INK = "#152c2b"
MUTED = "#53645e"
LIME = "#d2f87a"
EASE = ff.AnimationRuntime(0.8, ff.Easing.cubic_bezier(0.16, 1.0, 0.3, 1.0))
SPRING = ff.AnimationRuntime(3.0, ff.Easing.spring(1.0, 180.0, 20.0))
_F32 = struct.Struct("f")
# The Rust example writes these as `{CONST}` holes, so they stay holes here: a fully static
# subtree takes the renderer's static cache, which anti-aliases differently.
PALETTE = {"ink": INK, "paper": PAPER, "lime": LIME, "muted": MUTED}


def f32(x: float) -> float:
    """`x` rounded to f32, so text and geometry match the f32 math of the Rust example."""
    return _F32.unpack(_F32.pack(x))[0]


def ramp(frame: ff.Frame, start: float) -> float:
    return EASE.animate(frame, start, 0.0, 1.0)


def rise(frame: ff.Frame, start: float) -> float:
    return SPRING.animate(frame, start, 56.0, 0.0)


def stagger(base: float, i: int, step: float) -> float:
    return f32(f32(base) + f32(i * f32(step)))


LABEL = ff.template("""
<g font-family="DM Sans" font-size="30" font-weight="500" fill="{ink}">
    <circle cx="209" cy="147" r="17" fill="#709542" />
    <text x="252" y="158">{title}</text>
    <text x="1728" y="158" text-anchor="end">{number}</text>
</g>
""")

HEADING = ff.template(
    '<text x="192" y="314" font-family="DM Sans" font-weight="500" font-size="108" '
    'letter-spacing="-4" fill="{ink}">{text}</text>'
)


def heading(frame: ff.Frame, ctx: ff.Context, text: str) -> ff.Svgr:
    fitted = frame.text_fit(ctx, text, 1536, family="DM Sans", size=108, weight=500)
    return HEADING(**PALETTE, text=fitted if fitted is not None else text)


VIDEO = ff.template("""
<svg xmlns="http://www.w3.org/2000/svg" width="1920" height="1080" viewBox="0 0 1920 1080">
    <rect width="1920" height="1080" fill="{paper}" />
    {scenes}
    <path d="M192 946 H1728" stroke="#b4bdb1" stroke-width="2" />
    <rect x="192" y="945" width="{progress}" height="3" fill="#709542" />
    <text x="192" y="1002" font-family="DM Sans" font-weight="500" font-size="28"
          fill="{muted}">FFRAMES / MOTION STUDIES</text>
    <text x="1728" y="1002" text-anchor="end" font-family="DM Sans" font-weight="500"
          font-size="28" fill="{muted}">24 SECONDS / SVG + RUST</text>
</svg>
""")

PRODUCT_ROW = ff.template("""
<g opacity="{p}" transform="{shift}">
    <rect x="1088" y="{top}" width="540" height="82" rx="14" fill="#29403d" />
    <text x="1124" y="{base}" font-size="38" fill="{paper}">{name}</text>
    <text x="1586" y="{base}" text-anchor="end" font-size="30" fill="{lime}">{status}</text>
</g>
""")

PRODUCT = ff.template("""
<g font-family="DM Sans" font-weight="500">
    {label}
    <text x="183" y="445" font-size="208" letter-spacing="-10" fill="{ink}">Signal.</text>
    <text x="192" y="543" font-size="52" fill="{ink}">Your next release,</text>
    <text x="192" y="610" font-size="52" fill="{ink}">in motion.</text>
    <g opacity="{badge}">
        <rect x="192" y="703" width="380" height="76" rx="38" fill="{ink}" />
        <text x="382" y="753" text-anchor="middle" font-size="32" fill="{lime}">A FICTIONAL PRODUCT</text>
    </g>
    <g transform="{shift}">
        <rect x="1000" y="262" width="728" height="576" rx="32" fill="{ink}" />
        <circle cx="1095" cy="352" r="14" fill="{lime}" />
        <text x="1138" y="365" font-size="38" fill="{paper}">Release / 01</text>
        {rows}
        <g transform="translate(1650 278) rotate({angle})">
            <circle r="73" fill="{lime}" />
            <path d="M-34 0 H34 M0 -34 V34 M-24 -24 L24 24 M-24 24 L24 -24" stroke="{ink}" stroke-width="7" />
        </g>
    </g>
</g>
""")

DATA_BAR = ff.template("""
<g>
    <rect x="{x}" y="{top}" width="126" height="{h}" rx="8" fill="{fill}" />
    <text x="{cx}" y="{value_y}" text-anchor="middle" font-size="36" fill="{ink}">{value}</text>
    <text x="{cx}" y="851" text-anchor="middle" font-size="30" fill="{muted}">{name}</text>
</g>
""")

DATA = ff.template("""
<g font-family="DM Sans" font-weight="500">
    {label}
    {heading}
    <text x="180" y="646" font-size="248" letter-spacing="-12" fill="{ink}">{count}</text>
    <text x="192" y="734" font-size="46" fill="{ink}">Weekly activations</text>
    <text x="192" y="802" font-size="30" fill="{muted}">ILLUSTRATIVE DATA / WEEKS 01–04</text>
    {bars}
</g>
""")

SYSTEM_CARD = ff.template("""
<g opacity="{p}" transform="{shift}">
    <rect x="{x}" y="440" width="440" height="302" rx="24" fill="{ink}" />
    <text x="{tx}" y="505" font-size="30" fill="{lime}">{n}</text>
    <text x="{tx}" y="612" font-size="64" fill="{paper}">{title}</text>
    <text x="{tx}" y="684" font-size="32" fill="#b4bdb1">{subtitle}</text>
</g>
""")

SYSTEM = ff.template("""
<g font-family="DM Sans" font-weight="500">
    {label}
    {heading}
    <g opacity="{arrows}">
        <path d="M632 591 H740 M1180 591 H1288" stroke="#709542" stroke-width="5" />
        <path d="M718 577 L740 591 L718 605 M1266 577 L1288 591 L1266 605" stroke="#709542" stroke-width="5" fill="none" />
    </g>
    {cards}
    <g opacity="{loop}">
        <path d="M412 780 V824 H1508 V780" stroke="#b4bdb1" stroke-width="3" fill="none" />
        <circle cx="{x}" cy="824" r="12" fill="#709542" />
        <text x="960" y="894" text-anchor="middle" font-size="30" fill="{muted}">REVISE AND REPEAT</text>
    </g>
</g>
""")

FINAL = ff.template("""
<g font-family="DM Sans" font-weight="500">
    {label}
    <g transform="{shift}">
        <text x="183" y="457" font-size="146" letter-spacing="-6" fill="{ink}">Built from code.</text>
        <text x="183" y="631" font-size="146" letter-spacing="-6" fill="{ink}">Ready to revise.</text>
    </g>
    <g opacity="{p}">
        <rect x="192" y="750" width="1536" height="90" rx="16" fill="{ink}" />
        <text x="240" y="809" font-size="34" fill="{paper}">PRODUCT DEMOS</text>
        <circle cx="664" cy="797" r="7" fill="{lime}" />
        <text x="716" y="809" font-size="34" fill="{paper}">DATA STORIES</text>
        <circle cx="1100" cy="797" r="7" fill="{lime}" />
        <text x="1152" y="809" font-size="34" fill="{paper}">VISUAL EXPLAINERS</text>
    </g>
</g>
""")


class ProductScene:
    duration = SCENE_SECONDS
    label = LABEL(**PALETTE, number="01 / 04", title="PRODUCT ANNOUNCEMENT")
    rows = (("Build", "Ready"), ("Review", "Ready"), ("Publish", "Ready"))

    def render_frame(self, frame: ff.Frame, ctx: ff.Context) -> ff.Svgr:
        rows = []
        for i, (name, status) in enumerate(self.rows):
            y = 470 + i * 105
            start = stagger(0.7, i, 0.12)
            rows.append(
                PRODUCT_ROW(
                    **PALETTE,
                    p=ramp(frame, start),
                    shift=Transform.translate(0, rise(frame, start)),
                    top=y - 46,
                    base=y + 8,
                    name=name,
                    status=status,
                )
            )
        return PRODUCT(
            **PALETTE,
            label=self.label,
            badge=ramp(frame, 0.4),
            shift=Transform.translate(0, rise(frame, 0.0)),
            rows=rows,
            angle=f32(frame.seconds * 8.0),
        )


class DataScene:
    duration = SCENE_SECONDS
    label = LABEL(**PALETTE, number="02 / 04", title="DATA STORY")
    bars = (("01", 24.0), ("02", 41.0), ("03", 58.0), ("04", 76.0))

    def render_frame(self, frame: ff.Frame, ctx: ff.Context) -> ff.Svgr:
        bars = []
        for i, (name, value) in enumerate(self.bars):
            p = ramp(frame, stagger(0.25, i, 0.1))
            h = max(f32(f32(value * f32(4.3)) * p), 0.5)
            x = 982 + i * 188
            bars.append(
                DATA_BAR(
                    **PALETTE,
                    x=x,
                    top=f32(798.0 - h),
                    h=h,
                    fill="#709542" if i == 3 else "#b4bdb1",
                    cx=x + 63,
                    value_y=f32(775.0 - h),
                    value=f"{f32(value * p):.0f}",
                    name=name,
                )
            )
        count = f32(76.0 * ramp(frame, 0.55))
        return DATA(
            **PALETTE,
            label=self.label,
            heading=heading(frame, ctx, "Give numbers a rhythm."),
            count=f"{count:.0f}",
            bars=bars,
        )


class SystemScene:
    duration = SCENE_SECONDS
    label = LABEL(**PALETTE, number="03 / 04", title="TECHNICAL EXPLAINER")
    cards = (
        ("01", "Describe", "Rust + SVG"),
        ("02", "Inspect", "Frames + sound"),
        ("03", "Render", "Video file"),
    )

    def render_frame(self, frame: ff.Frame, ctx: ff.Context) -> ff.Svgr:
        cards = []
        for i, (n, title, subtitle) in enumerate(self.cards):
            x = 192 + i * 548
            start = stagger(0.12, i, 0.1)
            cards.append(
                SYSTEM_CARD(
                    **PALETTE,
                    p=ramp(frame, start),
                    shift=Transform.translate(0, rise(frame, start)),
                    x=x,
                    tx=x + 36,
                    n=n,
                    title=title,
                    subtitle=subtitle,
                )
            )
        travel = min(f32(max(f32(frame.seconds - f32(1.2)), 0.0) / f32(2.8)), 1.0)
        return SYSTEM(
            **PALETTE,
            label=self.label,
            heading=heading(frame, ctx, "Make the process visible."),
            arrows=ramp(frame, 0.4),
            cards=cards,
            loop=ramp(frame, 0.65),
            x=f32(1508.0 - f32(1096.0 * travel)),
        )


class FinalScene:
    duration = SCENE_SECONDS
    label = LABEL(**PALETTE, number="04 / 04", title="CREATED WITH FFRAMES")

    def render_frame(self, frame: ff.Frame, ctx: ff.Context) -> ff.Svgr:
        return FINAL(
            **PALETTE,
            label=self.label,
            shift=Transform.translate(0, rise(frame, 0.2)),
            p=ramp(frame, 0.2),
        )


class SignalLabVideo:
    fps = 30
    width = 1920
    height = 1080
    background_color = ff.Color.WHITE
    duration = None
    audio: ClassVar = [
        ff.AudioTrack("pulse.wav", 0.0, ff.Timestamp.EOF).gain_db(6.5).fade_in(0.08).fade_out(0.6)
    ]
    scenes: ClassVar = [ProductScene(), DataScene(), SystemScene(), FinalScene()]

    def render_frame(self, frame: ff.Frame, ctx: ff.Context) -> ff.Svgr:
        progress = max(f32(f32(frame.seconds / 24.0) * 1536.0), 0.5)
        return VIDEO(scenes=ctx.render_scenes(frame), progress=progress, **PALETTE)


if __name__ == "__main__":
    sys.exit(
        ff.cli(
            SignalLabVideo(),
            media=_media.media("signal-lab", mono=True),
            load_system_fonts=False,
            codec_params={"crf": "20", "preset": "medium", "tune": "animation"},
            renderer="gpu",
            gpu_contexts="max",
        )
    )

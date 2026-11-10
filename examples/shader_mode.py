"""Port of fframes/examples/shader-mode: 932 source frames of 18 Skia shaders, a 3D panel wall
and the fframes wordmark.

Place the soundtrack at fframes/examples/shader-mode/dynamic_media/reference-audio.wav.

python examples/shader_mode.py render -o shader-mode.mp4
"""

import math
import sys
from dataclasses import dataclass
from pathlib import Path

import _media
import fframes as ff
from _f32 import f32, fmt32
from _shader_mode_catalog import Catalog

SOURCES = Path(__file__).parent / "sksl" / "shader_mode"
SOURCE_FRAMES = 932
SOURCE_FPS_NUM = 30000
SOURCE_FPS_DEN = 1001


def source(name: str) -> str:
    return (SOURCES / name).read_text()


COMMON = source("common.sksl")
SOURCE_EFFECTS = source("source-effects.sksl")
EFFECT_SOURCES = {
    "Ascii": "ascii.sksl",
    "Glass": "glass.sksl",
    "Material": "material.sksl",
    "LiquidChrome": "liquid-chrome.sksl",
    "Tunnel": "tunnel.glsl",
    "Halftone": "halftone.sksl",
    "Gradient": "gradient.sksl",
    "Particles": "particles.sksl",
    "Obsidian": "obsidian.sksl",
    "Aurora": "aurora.sksl",
    "Flow": "flow.sksl",
    "Emboss": "emboss.sksl",
    "Rays": "rays.sksl",
    "Spectral": "spectral.sksl",
    "Eclipse": "eclipse.sksl",
    "Catalog": "catalog.sksl",
    "Preview": "preview.sksl",
    "Binary": "binary-intro.sksl",
}
MASKS = {
    "Ascii": "glyph-atlas.png",
    "Binary": "binary-atlas.png",
    "Halftone": "fframes-sdf.png",
    "Emboss": "fframes-sdf.png",
    "Catalog": "catalog.png",
}


def effect_shader(effect: str) -> ff.Shader:
    code = source(EFFECT_SOURCES[effect])
    if effect == "Tunnel":
        return ff.Shader.shadertoy("uniform float uClock;\n" + code.replace("iTime", "uClock"))
    sculpture = source("sculpture.sksl") if effect in ("LiquidChrome", "Obsidian") else ""
    gradient = source("gradient-shared.sksl") if effect in ("Gradient", "Catalog") else ""
    full = f"{COMMON}\n{SOURCE_EFFECTS}\n{sculpture}\n{gradient}\n{code}"
    return ff.Shader.sksl(full.replace("iTime", "uClock"))


SHADERS = {effect: effect_shader(effect) for effect in EFFECT_SOURCES}


@dataclass(frozen=True)
class Shot:
    """One shot of the reference edit, in source frames."""

    name: str
    start: int
    end: int
    effect: str | None
    variant: int
    clock_start: int

    @property
    def frames(self) -> int:
        return self.end - self.start


# The reference edit. Color hard cuts are shots; camera moves stay inside a shot.
SHOTS = [
    Shot("BlackLead", 0, 6, None, 0, 0),
    Shot("Boot", 6, 26, "Binary", 0, 6),
    Shot("Glass", 26, 57, "Glass", 0, 26),
    Shot("GlassAmber", 57, 82, "Glass", 1, 26),
    Shot("Chrome", 82, 91, "Material", 0, 82),
    Shot("Crystal", 91, 97, "Material", 4, 82),
    Shot("Gold", 97, 104, "Material", 1, 82),
    Shot("Ceramic", 104, 111, "Material", 5, 82),
    Shot("Carbon", 111, 119, "Material", 2, 82),
    Shot("ChromeSoft", 119, 126, "Material", 0, 82),
    Shot("Pixels", 126, 132, "Material", 3, 82),
    Shot("PrismGlass", 132, 141, "Material", 6, 82),
    Shot("OpenSource", 141, 209, "LiquidChrome", 0, 141),
    Shot("OpenSourceHold", 209, 222, "LiquidChrome", 0, 141),
    Shot("Rose", 222, 229, "Obsidian", 1, 222),
    Shot("Tunnel", 229, 238, "Tunnel", 0, 229),
    Shot("Halftone", 238, 256, "Halftone", 0, 238),
    Shot("ShaderLibrary", 256, 307, "Catalog", 0, 256),
    Shot("Gradient", 307, 344, "Gradient", 0, 307),
    Shot("Ascii", 344, 357, "Ascii", 1, 344),
    Shot("Particles", 357, 377, "Particles", 0, 357),
    Shot("Obsidian", 377, 391, "Obsidian", 0, 377),
    Shot("Silver", 391, 397, "Spectral", 2, 391),
    Shot("AuroraGreen", 397, 400, "Aurora", 1, 391),
    Shot("AuroraPurple", 400, 403, "Aurora", 2, 391),
    Shot("AuroraAqua", 403, 407, "Aurora", 3, 391),
    Shot("AuroraOrange", 407, 410, "Aurora", 4, 391),
    Shot("BlackBreak", 410, 417, None, 0, 410),
    Shot("Flow", 417, 447, "Flow", 0, 417),
    Shot("EmbossBlue", 447, 459, "Emboss", 0, 447),
    Shot("EmbossGreen", 459, 471, "Emboss", 1, 447),
    Shot("EmbossOrange", 471, 483, "Emboss", 2, 447),
    Shot("EmbossPearl", 483, 496, "Emboss", 3, 447),
    Shot("NativePreview", 496, 567, "Preview", 0, 496),
    Shot("ShaderModeEditor", 567, 586, "Spectral", 0, 567),
    Shot("ShaderModeZoom", 586, 610, "Spectral", 0, 567),
    Shot("ShaderMode", 610, 626, "Spectral", 0, 567),
    Shot("ShaderModeWide", 626, 640, "Spectral", 0, 567),
    Shot("BlackPause", 640, 654, None, 0, 640),
    Shot("Eclipse", 654, 849, "Eclipse", 0, 654),
    Shot("BlackTail", 849, 932, None, 0, 849),
]


# --- titles ------------------------------------------------------------------------------------


# Every attribute of a centered title is a hole, as in the Rust example: the renderer then never
# caches the text as a static picture across the zoom of the Glass shot.
CENTER = ff.template(
    '<text x="960" y="{y}" text-anchor="middle" font-family="DM Sans" font-weight="500" '
    'font-size="{size}" letter-spacing="-1.8" fill="{color}">{text}</text>'
)
GLASS = ff.template("""
<g>
    <g transform="translate(1.2 1.4)">{orange}</g>
    <g transform="translate(-1 -1)">{blue}</g>
    {white}
</g>
""")


def center(text: str, y: int, size: int, color: str) -> ff.Svgr:
    return CENTER(text=text, y=y, size=size, color=color)


SHADER_MODE_TITLE = ff.svgr("""
<g>
    <text x="960" y="381" text-anchor="middle" font-family="JetBrains Mono"
          font-size="27" letter-spacing="4" fill="#c9c4df">FFRAMES</text>
    <text x="960" y="554" text-anchor="middle" font-family="DM Sans" font-weight="500"
          font-size="152" letter-spacing="-6" fill="#f6f4ff">shader mode</text>
    <text x="960" y="637" text-anchor="middle" font-family="DM Sans"
          font-size="32" letter-spacing="0.5" fill="#c9c4df">Your code. In motion.</text>
</g>
""")
TITLES = {
    "Glass": GLASS(
        orange=center("FFRAMES HAS SHADERS", 638, 68, "#ff7c51"),
        blue=center("FFRAMES HAS SHADERS", 638, 68, "#6989ff"),
        white=center("FFRAMES HAS SHADERS", 638, 68, "#f8f8f8"),
    ),
    "Gradient": center("SkSL + SHADERTOY", 576, 64, "#fcf5ff"),
    "OpenSource": ff.svgr("""
<g>
    <text x="152" y="278" font-family="JetBrains Mono" font-size="26"
          letter-spacing="3" fill="#565967">YOURS TO CREATE.</text>
    <text x="142" y="478" font-family="DM Sans" font-weight="500"
          font-size="174" letter-spacing="-7" fill="#171922">open</text>
    <text x="142" y="645" font-family="DM Sans" font-weight="500"
          font-size="174" letter-spacing="-7" fill="#171922">source</text>
    <path d="M154 722H222" stroke="#79758b" stroke-width="2" />
    <text x="152" y="785" font-family="DM Sans" font-size="32"
          fill="#565967">Made with fframes.</text>
</g>
"""),
    "ShaderMode": SHADER_MODE_TITLE,
    "SpectralCut": SHADER_MODE_TITLE,
}
TITLE_NAMES = {
    "GlassAmber": "Glass",
    "OpenSourceHold": "OpenSource",
    "ShaderModeEditor": "ShaderMode",
    "ShaderModeZoom": "ShaderMode",
    "ShaderModeWide": "ShaderMode",
}


# --- outro: the vector wordmark of fframes-intro ---------------------------------------------

FONT = "Instrument Serif"
WORD_SIZE = 300
BEAT = f32(0.454522)
ECHO = ff.template(
    '<text x="{x}" y="530" font-family="Instrument Serif" font-style="italic" '
    'font-weight="400" font-size="300" fill="{fill}" opacity="{opacity}">f</text>'
)
OUTRO = ff.template("""
<g>
    {echoes}
    <g transform="{transform}" opacity="{word_opacity}">
        <text x="{x}" y="530" font-family="Instrument Serif" font-style="italic"
              font-weight="400" font-size="300" fill="#ece8e1">fframes</text>
    </g>
    <text x="960" y="636" text-anchor="middle" font-family="JetBrains Mono"
          font-size="30" letter-spacing="3" fill="#c6b4ef" opacity="{tag}">SHADER MODE</text>
</g>
""")
ECHO_COLORS = ("#fb6a22", "#c4531c", "#8a3712")


def spring(seconds: float, stiffness: float, damping: float) -> float:
    """The damped spring of fframes-intro/beat.rs, in f32."""
    if seconds <= 0.0:
        return 0.0
    natural = f32(math.sqrt(stiffness))
    ratio = f32(damping / f32(2.0 * natural))
    damped = f32(natural * f32(math.sqrt(f32(1.0 - f32(ratio * ratio)))))
    decay = f32(math.exp(f32(f32(-ratio * natural) * seconds)))
    angle = f32(damped * seconds)
    wave = f32(
        f32(math.cos(angle)) + f32(f32(f32(ratio * natural) / damped) * f32(math.sin(angle)))
    )
    return f32(1.0 - f32(decay * wave))


def expo_out(progress: float) -> float:
    progress = min(max(progress, 0.0), 1.0)
    return 1.0 if progress >= 1.0 else f32(1.0 - f32(2.0 ** f32(-10.0 * progress)))


class Outro:
    def __init__(self):
        self.widths = None

    def measure(self, frame: ff.Frame, ctx: ff.Context) -> tuple[float, float]:
        if self.widths is not None:
            return self.widths
        font = {"family": FONT, "size": WORD_SIZE, "weight": 400, "style": "italic"}
        word = frame.text_width(ctx, "fframes", **font)
        letter = frame.text_width(ctx, "f", **font)
        if word is None or letter is None:
            # Do not cache a fallback if fonts are temporarily unavailable.
            return 840.0, 84.0
        self.widths = (float(word), float(letter))
        return self.widths

    def render(self, frame: ff.Frame, ctx: ff.Context) -> ff.Svgr:
        seconds = frame.seconds
        beats = f32(seconds / BEAT)
        width, letter_width = self.measure(frame, ctx)
        step = f32(letter_width * f32(0.78))
        total = f32(width + f32(step * 3.0))
        x = f32(f32(960.0 - f32(total / 2.0)) + f32(step * 3.0))
        word_opacity = min(spring(seconds, 260.0, 20.0), 1.0)
        word_scale = f32(1.0 + f32(f32(1.0 - expo_out(f32(beats / 0.5))) * f32(0.25)))
        echoes = []
        for index in (2, 1, 0):
            amount = spring(f32(f32(f32(beats - 0.5) - f32(index * 0.5)) * BEAT), 170.0, 15.0)
            dx = f32(f32(f32(-step) * (index + 1.0)) * amount)
            opacity = f32(min(max(amount, 0.0), 1.0) * f32(1.0 - f32(index * f32(0.18))))
            echoes.append(ECHO(x=f32(x + dx), fill=ECHO_COLORS[index], opacity=opacity))
        tag = min(max(f32(f32(beats - 4.0) / f32(0.6)), 0.0), 1.0)
        return OUTRO(
            echoes=echoes,
            transform=f"translate(960 530) scale({fmt32(word_scale)}) translate(-960 -530)",
            word_opacity=word_opacity,
            x=x,
            tag=tag,
        )


# --- transitions: camera gestures in source frames --------------------------------------------


def cube(x: float) -> float:
    """`x.powi(3)` in f32: LLVM multiplies `(x * x) * x`."""
    return f32(f32(x * x) * x)


def progress(index: int, start: int, end: int) -> float:
    return min(max(f32(f32(index - start) / (end - start)), 0.0), 1.0)


BAR = ff.template('<rect x="0" y="{y}" width="1920" height="{height}" fill="#000" />')
SHOT_CANVAS = ff.template("""
<g>
    <defs><clipPath id="shot-canvas"><rect width="1920" height="1080" /></clipPath></defs>
    <g clip-path="url(#shot-canvas)">
        <g opacity="{opacity}" transform="{transform}">{composition}</g>
        {bars}
        <rect width="1920" height="1080" fill="#fffcf2" opacity="{flash}" />
    </g>
</g>
""")
ROW_HEIGHT = f32(1080.0 / 28.0)


def apply(index: int, name: str, composition: ff.Svgr) -> ff.Svgr:
    scale, rotation, skew, dx, dy, opacity = 1.0, 0.0, 0.0, 0.0, 0.0, 1.0
    if name == "Glass":
        scale = f32(1.0 + f32(3.0 * cube(f32(1.0 - progress(index, 26, 35)))))
    elif name == "Halftone":
        scale = f32(1.0 + f32(cube(progress(index, 253, 256)) * f32(1.3)))
    elif name == "Flow":
        scale = f32(1.0 + f32(cube(progress(index, 443, 447)) * 8.0))
    elif name == "ShaderModeEditor":
        scale, skew, rotation = f32(0.85), -3.0, f32(-0.6)
    elif name == "ShaderModeZoom":
        scale, skew = f32(1.14), -3.0
        dx = f32(-60.0 * f32(1.0 - progress(index, 586, 610)))
    elif name == "ShaderModeWide":
        scale, skew = f32(0.86), -2.0
    elif name == "Eclipse":
        p = progress(index, 836, 849)
        p = f32(p * p)
        scale = f32(1.0 - f32(p * f32(0.97)))
        rotation = f32(p * 14.0)
        dy = f32(p * 170.0)
        fade = progress(index, 654, 680)
        opacity = f32(f32(fade * fade) * f32(1.0 - p))
    if 137 <= index < 148:
        t = f32(f32(index - 141.0) / f32(2.7))
        flash = f32(math.exp(f32(-f32(t * t))))
    elif 445 <= index < 450:
        t = f32(f32(index - 446.0) / f32(1.3))
        flash = f32(f32(math.exp(f32(-f32(t * t)))) * f32(0.45))
    else:
        flash = 0.0
    if 608 <= index < 610:
        glitch = f32(0.18)
    elif 636 <= index < 640:
        glitch = progress(index + 1, 636, 640)
    else:
        glitch = 0.0
    bars = None
    if glitch > 0.0:
        bars = []
        for row in range(28):
            hash_ = f32(((row * 73 + index * 19) % 101) / f32(101.0))
            fill = min(max(f32(f32(glitch * 1.5) - f32(hash_ * f32(0.45))), f32(0.02)), 1.0)
            bars.append(BAR(y=f32(f32(row * 1080.0) / 28.0), height=f32(ROW_HEIGHT * fill)))
    transform = (
        f"translate({fmt32(f32(960.0 + dx))} {fmt32(f32(540.0 + dy))}) rotate({fmt32(rotation)}) "
        f"skewX({fmt32(skew)}) scale({fmt32(scale)}) translate(-960 -540)"
    )
    return SHOT_CANVAS(
        opacity=opacity, transform=transform, composition=composition, bars=bars, flash=flash
    )


# --- shots ------------------------------------------------------------------------------------

LAYER = ff.template("""
<g>
    <image href="{layer}" x="0" y="0" width="1920" height="1080" />
    {titles}
</g>
""")
FADE = ff.template('<g opacity="{opacity}">{content}</g>')
OPENING = ff.template("""
<g>
    {composition}
    <image href="{layer}" width="1920" height="1080" />
</g>
""")
RECORDING = "native-scrubbing.mp4"


class ShotScene:
    def __init__(self, spec: Shot, has_recording: bool):
        self.spec = spec
        self.name = spec.name
        self.duration = ff.Duration.frames(spec.frames)
        self.shader = SHADERS[spec.effect] if spec.effect else None
        self.mask = MASKS.get(spec.effect)
        self.variant = float(spec.variant)
        self.outro = Outro() if spec.name == "Eclipse" else None
        self.opening = SHADERS["Binary"] if spec.name == "Glass" else None
        self.catalog = Catalog() if spec.effect == "Catalog" else None
        self.titles = TITLES.get(TITLE_NAMES.get(spec.name, spec.name))
        self.has_recording = has_recording

    def render_frame(self, frame: ff.Frame, ctx: ff.Context) -> ff.Svgr:
        spec, shader = self.spec, self.shader
        if shader is None:
            return ff.Svgr.empty()
        source_index = frame.global_index
        # Geometry stays continuous through color cuts; progress is local to the shot.
        progress_ = f32(frame.index / spec.frames)
        frame = frame.with_index(source_index - spec.clock_start)
        if self.catalog is not None:
            return apply(source_index, spec.name, self.catalog.render(frame, ctx, shader))
        seconds = f32(f32(frame.index * SOURCE_FPS_DEN) / SOURCE_FPS_NUM)
        uniforms = {
            "uClock": seconds,
            "uProgress": progress_,
            "uVariant": self.variant,
            "uBeat": f32(math.exp(f32(-math.fmod(seconds, 0.5) * 12.0))),
        }
        if self.mask is not None:
            mask = ctx.image(self.mask)
            if mask is None:
                return ff.Svgr.empty()
            uniforms["uMask"] = mask
        if spec.effect == "Preview":
            recording = None
            if self.has_recording:
                recording = frame.with_index(source_index - 496).video_frame(ctx, RECORDING)
            if recording is not None:
                uniforms["uRecording"] = recording.image
                uniforms["uRecordingSize"] = (float(recording.width), float(recording.height))
            else:
                # Use the bundled poster when the recording is unavailable.
                poster = ctx.image("native-preview-poster.jpg")
                if poster is None:
                    return ff.Svgr.empty()
                uniforms["uRecording"] = poster
                uniforms["uRecordingSize"] = (1920.0, 1124.0)
        layer = shader.draw(frame, uniforms)
        titles = self.outro.render(frame, ctx) if self.outro else self.titles
        if spec.name == "Glass" and source_index < 35:
            fade = min(max(f32(f32(source_index - 31.0) / 4.0), 0.0), 1.0)
            titles = FADE(opacity=fade, content=titles)
        composition = apply(source_index, spec.name, LAYER(layer=layer, titles=titles))
        if source_index < 33 and self.opening is not None:
            atlas = ctx.image("binary-atlas.png")
            if atlas is not None:
                overlay = self.opening.draw(
                    frame,
                    {
                        "uClock": f32(f32((source_index - 6) * 1001.0) / 30000.0),
                        "uVariant": 1.0,
                        "uMask": atlas,
                    },
                )
                return OPENING(composition=composition, layer=overlay)
        return composition


FRAME = ff.template("""
<svg xmlns="http://www.w3.org/2000/svg" width="1920" height="1080" viewBox="0 0 1920 1080">
    <rect width="1920" height="1080" fill="#000" />
    {scenes}
</svg>
""")


class ShaderMode:
    """Native Skia showcase: 932 source frames, 1920x1080."""

    fps = 30
    width = 1920
    height = 1080
    background_color = ff.Color.BLACK
    duration = ff.Duration.frames(SOURCE_FRAMES)
    audio = (ff.AudioTrack("reference-audio.wav", 0.0, ff.Timestamp.EOF),)

    def __init__(self, has_recording: bool = False):
        self.scenes = [ShotScene(spec, has_recording) for spec in SHOTS]

    def render_frame(self, frame: ff.Frame, ctx: ff.Context) -> ff.Svgr:
        return FRAME(scenes=ctx.render_scenes(frame))


def main() -> int:
    media = ff.Media(_media.folder("shader-mode"), _media.folder("shader-mode", "dynamic_media"))
    return ff.cli(
        ShaderMode(has_recording=RECORDING in media.videos),
        sys.argv,
        media=media,
        codec_params={"crf": "17", "preset": "medium"},
        # Play the source soundtrack in stereo, without gain or limiting.
        limiter=False,
        default_output=Path(__file__).parent / "output" / "shader-mode.mp4",
        renderer="gpu",
    )


if __name__ == "__main__":
    sys.exit(main())

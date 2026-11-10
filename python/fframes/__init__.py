"""Python bindings for fframes: render videos from SVG, fast.

A video is any object with ``width``, ``height``, ``fps`` (default 30), ``duration``
(seconds, a ``Duration`` or ``None`` for automatic) and a ``render_frame(frame, ctx)``
method that returns an ``Svgr`` tree. Instead of ``render_frame`` a video can have
``scenes``. Run it with ``fframes.cli(video)``.
"""

import sys as _sys

from fframes._fframes import (
    AnimationRuntime,
    AudioTrack,
    Captions,
    CaptionWord,
    Clip,
    Color,
    Context,
    Duration,
    Easing,
    Frame,
    Image,
    Media,
    Noise,
    Path,
    Rng,
    Shader,
    Svgr,
    Template,
    TextLayout,
    TextLine,
    Timeline,
    Timestamp,
    Transform,
    VideoFrame,
    biquad,
    center_spectrum_low_frequencies,
    cli,
    exif,
    f32_math,
    lottie_frame,
    saw,
    svgr,
    template,
    three_d,
    timeline,
    wave_path,
)

_sys.modules["fframes.three_d"] = three_d

__all__ = [
    "AnimationRuntime",
    "AudioTrack",
    "CaptionWord",
    "Captions",
    "Clip",
    "Color",
    "Context",
    "Duration",
    "Easing",
    "Frame",
    "Image",
    "Media",
    "Noise",
    "Path",
    "Rng",
    "Shader",
    "Svgr",
    "Template",
    "TextLayout",
    "TextLine",
    "Timeline",
    "Timestamp",
    "Transform",
    "VideoFrame",
    "biquad",
    "center_spectrum_low_frequencies",
    "cli",
    "exif",
    "f32_math",
    "lottie_frame",
    "saw",
    "svgr",
    "template",
    "three_d",
    "timeline",
    "wave_path",
]

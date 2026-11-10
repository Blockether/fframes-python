"""Type stubs for the native fframes module."""

from collections.abc import Iterable, Sequence
from typing import Any, ClassVar, Literal, Protocol, TypeAlias

ColorLike: TypeAlias = Color | str
Number: TypeAlias = int | float
DurationLike: TypeAlias = Duration | Number | None
TimestampLike: TypeAlias = Timestamp | Number
Animatable: TypeAlias = Number | tuple[Number, ...] | ColorLike | Transform
AtLike: TypeAlias = Number | tuple[Number, Number]
Keyframe: TypeAlias = (
    tuple[AtLike, Animatable, Animatable] | tuple[AtLike, Animatable, Animatable, Easing | str]
)
AudioLike: TypeAlias = AudioTrack | tuple[str, TimestampLike, TimestampLike | None]
Uniform: TypeAlias = Number | tuple[Number, ...] | Color | Image

class Scene(Protocol):
    duration: DurationLike
    def render_frame(self, frame: Frame, ctx: Context) -> Svgr: ...

class Video(Protocol):
    width: int
    height: int
    duration: DurationLike

class Color:
    BLACK: ClassVar[Color]
    WHITE: ClassVar[Color]
    TRANSPARENT: ClassVar[Color]
    r: int
    g: int
    b: int
    a: int
    def __init__(self, r: int, g: int, b: int, a: int = 255) -> None: ...
    @staticmethod
    def hex(value: str) -> Color: ...
    @staticmethod
    def parse(value: ColorLike) -> Color: ...
    @staticmethod
    def rgb(r: int, g: int, b: int) -> Color: ...
    @staticmethod
    def rgba(r: int, g: int, b: int, a: int) -> Color: ...
    def with_alpha(self, a: int) -> Color: ...
    def is_opaque(self) -> bool: ...
    def is_transparent(self) -> bool: ...

class Transform:
    translate_x: float
    translate_y: float
    rotation: float
    rotation_origin: tuple[float, float] | None
    scale_x: float
    scale_y: float
    skew_x: float
    skew_y: float
    def __init__(
        self,
        *,
        translate: tuple[float, float] | None = None,
        rotate: float | tuple[float, tuple[float, float]] | None = None,
        scale: float | tuple[float, float] | None = None,
        skew: tuple[float, float] | None = None,
    ) -> None: ...
    @staticmethod
    def translate(x: float, y: float) -> Transform: ...
    @staticmethod
    def rotate(angle: float, origin: tuple[float, float] | None = None) -> Transform: ...
    @staticmethod
    def scale(x: float, y: float | None = None) -> Transform: ...
    @staticmethod
    def skew(x: float, y: float) -> Transform: ...
    def replace(
        self,
        *,
        translate: tuple[float, float] | None = None,
        rotate: float | tuple[float, tuple[float, float]] | None = None,
        scale: float | tuple[float, float] | None = None,
        skew: tuple[float, float] | None = None,
    ) -> Transform: ...

class Image:
    width: int
    height: int

class Path:
    def __init__(self, d: str) -> None: ...
    def __len__(self) -> int: ...

class Svgr:
    @staticmethod
    def empty() -> Svgr: ...
    @staticmethod
    def concat(items: Iterable[Any]) -> Svgr: ...
    @staticmethod
    def text(value: str) -> Svgr: ...
    def to_svg(self) -> str: ...
    def __add__(self, other: Svgr) -> Svgr: ...
    def __len__(self) -> int: ...

class Template:
    holes: list[str]
    def __call__(self, *args: Any, **kwargs: Any) -> Svgr: ...

def svgr(markup: Any, /, **values: Any) -> Svgr: ...
def template(markup: Any) -> Template: ...

class Easing:
    LINEAR: ClassVar[Easing]
    EASE_IN: ClassVar[Easing]
    EASE_OUT: ClassVar[Easing]
    EASE_IN_OUT: ClassVar[Easing]
    @staticmethod
    def cubic_bezier(x1: float, y1: float, x2: float, y2: float) -> Easing: ...
    @staticmethod
    def spring(mass: float = 1.0, stiffness: float = 100.0, damping: float = 10.0) -> Easing: ...

class Timeline:
    duration: float

def timeline(*keyframes: Keyframe) -> Timeline: ...

class Duration:
    AUTO: ClassVar[Duration]
    @staticmethod
    def seconds(seconds: float) -> Duration: ...
    @staticmethod
    def frames(frames: int) -> Duration: ...
    @staticmethod
    def from_audio(file: str) -> Duration: ...
    @staticmethod
    def from_video(file: str) -> Duration: ...
    def __add__(self, other: DurationLike) -> Duration: ...
    def __sub__(self, other: DurationLike) -> Duration: ...

class Timestamp:
    EOF: ClassVar[Timestamp]
    @staticmethod
    def second(second: float) -> Timestamp: ...
    @staticmethod
    def frame(frame: int) -> Timestamp: ...
    @staticmethod
    def time(minutes: int, seconds: float) -> Timestamp: ...
    @staticmethod
    def duration_of_audio(file: str) -> Timestamp: ...
    def __add__(self, other: TimestampLike) -> Timestamp: ...
    def __sub__(self, other: TimestampLike) -> Timestamp: ...

class AudioTrack:
    file: str
    def __init__(
        self, file: str, start: TimestampLike | None = None, end: TimestampLike | None = None
    ) -> None: ...
    def gain_db(self, gain_db: float) -> AudioTrack: ...
    def volume(self, volume: float) -> AudioTrack: ...
    def pan(self, pan: float) -> AudioTrack: ...
    def fade_in(self, seconds: float) -> AudioTrack: ...
    def fade_out(self, seconds: float) -> AudioTrack: ...
    def fade_curve(self, curve: str) -> AudioTrack: ...
    def offset(self, seconds: float) -> AudioTrack: ...
    def voice(self) -> AudioTrack: ...
    def duck_under_voice(self) -> AudioTrack: ...
    def duck(
        self,
        depth_db: float = ...,
        attack: float = 0.2,
        hold: float = 0.3,
        release: float = 0.8,
        merge_gap: float = 0.8,
    ) -> AudioTrack: ...
    def rate(self, rate: float) -> AudioTrack: ...
    def normalize_lufs(self, lufs: float) -> AudioTrack: ...
    def highpass(self, hz: float) -> AudioTrack: ...
    def lowpass(self, hz: float) -> AudioTrack: ...
    def low_shelf(self, hz: float, db: float) -> AudioTrack: ...
    def high_shelf(self, hz: float, db: float) -> AudioTrack: ...
    def peak(self, hz: float, db: float, q: float) -> AudioTrack: ...
    def width(self, width: float) -> AudioTrack: ...

class TextLine:
    words: list[str]
    width: float
    dx: float
    dy: float
    text: str

class TextLayout:
    lines: list[TextLine]
    height: float
    def svgr(self) -> Svgr: ...
    def __len__(self) -> int: ...

class VideoFrame:
    image: Image
    width: int
    height: int
    timestamp_seconds: float
    stream_fps: float
    stream_duration: float

class Frame:
    index: int
    global_index: int
    fps: int
    seconds: float
    def frame_to_second(self, frame: int) -> float: ...
    def second_to_frame(self, second: float) -> int: ...
    def animate(self, timeline: Timeline) -> Any: ...
    def animate_loop(self, timeline: Timeline) -> Any: ...
    def into_global(self) -> Frame: ...
    def text_width(
        self,
        ctx: Context,
        text: str,
        *,
        family: str = ...,
        size: float = 16,
        weight: int = 500,
        style: str = "normal",
        stretch: str = "normal",
    ) -> float: ...
    def text_fit(
        self,
        ctx: Context,
        text: str,
        max_width: float,
        *,
        family: str = ...,
        size: float = 16,
        weight: int = 500,
        style: str = "normal",
        stretch: str = "normal",
        overflow: Literal["ellipsis", "clip"] = "ellipsis",
    ) -> str: ...
    def text_layout(
        self,
        ctx: Context,
        text: str,
        *,
        width: float,
        family: str = ...,
        size: float = 16,
        weight: int = 500,
        style: str = "normal",
        stretch: str = "normal",
        line_height: float = 1.1,
        x: float | None = None,
        y: float | None = None,
        align: Literal["left", "center", "right"] = "left",
        fill: ColorLike = ...,
        dominant_baseline: str = ...,
        text_anchor: str = ...,
        opacity: float = 1.0,
    ) -> TextLayout | None: ...
    def video_frame(
        self,
        ctx: Context,
        file: str,
        *,
        start_from: float = 0.0,
        looping: bool = False,
        speed: float = 1.0,
        width: int | None = None,
        height: int | None = None,
    ) -> VideoFrame | None: ...
    def video_frame_at(
        self,
        ctx: Context,
        file: str,
        seconds: float,
        *,
        width: int | None = None,
        height: int | None = None,
    ) -> VideoFrame | None: ...
    def visualize_audio(
        self,
        ctx: Context,
        audio: str,
        *,
        sample_size: int = 512,
        smooth_level: int = 0,
        window: Literal["hann", "hamming"] | None = None,
    ) -> list[float]: ...
    def subtitle_phrase(self, ctx: Context, file: str) -> str | None: ...
    def play_lottie(
        self,
        ctx: Context,
        file: str,
        *,
        start: float = 0.0,
        speed: float = 1.0,
        looping: bool = False,
        x: float = 0.0,
        y: float = 0.0,
        width: float | None = None,
        height: float | None = None,
    ) -> Svgr: ...

class Context:
    width: int
    height: int
    fps: int
    sample_rate: int
    duration_in_frames: int
    mode: str
    def image(self, name: str) -> Image | None: ...
    def render_svgr(self, svgr: Svgr, width: int, height: int) -> Image | None: ...
    def render_scenes(self, frame: Frame) -> Svgr: ...

class Clip:
    seconds: float
    def __init__(self, video: str, start: float = 0.0, end: float | None = None) -> None: ...
    def at(self, seconds: float) -> Clip: ...
    def speed(self, speed: float) -> Clip: ...
    def reverse(self) -> Clip: ...
    def looping(self) -> Clip: ...
    def frames(self, fps: int) -> int: ...
    def image(self, frame: Frame, ctx: Context, width: int | None = None) -> Image | None: ...

class Shader:
    source: str
    @staticmethod
    def sksl(source: str) -> Shader: ...
    @staticmethod
    def shadertoy(source: str) -> Shader: ...
    def draw(self, frame: Frame, uniforms: dict[str, Uniform] | None = None) -> Svgr: ...

def center_spectrum_low_frequencies(spectrum: Sequence[float]) -> list[float]: ...

class Media:
    images: list[str]
    audio: list[str]
    videos: list[str]
    subtitles: list[str]
    lottie: list[str]
    fonts: list[str]
    def __init__(self, *folders: str) -> None: ...

def cli(
    video: Any,
    argv: Sequence[str] | None = None,
    *,
    media: Media | None = None,
    load_system_fonts: bool = True,
    default_font: str = ...,
    encoder: str = ...,
    codec_params: dict[str, str] | None = None,
    tmp_dir: str | None = None,
    default_output: str | None = None,
    video_options: dict[str, Any] | None = None,
    audio_options: dict[str, Any] | None = None,
    cache_capacity: int | None = None,
    concurrency: int | None = None,
    text_cache_capacity: int | None = None,
    renderer: Literal["cpu", "skia-cpu", "gpu"] | None = None,
    gpu_contexts: int | Literal["max"] | None = None,
    buffer_queue_size: int | None = None,
    master_gain_db: float = 0.0,
    limiter: bool | dict[str, float] | None = None,
    declick: bool = True,
) -> int: ...

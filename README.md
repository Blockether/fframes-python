# fframes for Python

Python bindings for [fframes](https://fframes.studio), the Rust framework that renders
videos from SVG — and is actually fast. Write the video in Python; the Rust engine
parses your templates once, renders the frames in parallel on the CPU or GPU, mixes the
audio and encodes the file.

```python
import sys
import fframes as ff
from fframes import Color, Easing, Transform

SLIDE = ff.timeline(((0, 1), Transform.translate(-600, 0), Transform.translate(0, 0), Easing.spring()))
FADE = ff.timeline(((0.3, 1.3), 0.0, 1.0, "ease-out"))
FRAME = ff.template("""
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1920 1080" width="{width}" height="{height}">
  <rect width="1920" height="1080" fill="#0f172a"/>
  <text x="960" y="560" text-anchor="middle" font-size="140" fill="#fff"
        transform="{slide}" opacity="{fade}">{title}</text>
</svg>
""")

class Hello:
    width, height, fps, duration = 1920, 1080, 30, 4.0

    def render_frame(self, frame: ff.Frame, ctx: ff.Context) -> ff.Svgr:
        return FRAME(width=ctx.width, height=ctx.height, title="Hello, Python",
                     slide=frame.animate(SLIDE), fade=frame.animate(FADE))

if __name__ == "__main__":
    sys.exit(ff.cli(Hello()))
```

```bash
python hello.py render -o hello.mp4          # the whole video
python hello.py frame 0s,50%,end -o frames/  # single frames as PNG, with diagnostics
python hello.py strip -o sheet.png           # a contact sheet of the motion
python hello.py inspect                      # missing media, clipped text, errors
python hello.py timeline --json              # scenes, duration, audio tracks
```

## Install

Build from source with [maturin](https://www.maturin.rs). You need Rust (stable) and the
system encoders that fframes links (see the build notes in the
[fframes README](https://github.com/Blockether/fframes)):

```bash
# macOS
brew install pkg-config ffmpeg x264 x265 opus nasm ninja
# Debian / Ubuntu
sudo apt-get install -y yasm nasm ffmpeg libx264-dev libx265-dev libopus-dev libclang-dev clang ninja-build libvpx-dev libasound2-dev

pip install "git+https://github.com/Blockether/fframes-python"
# or, in a checkout:
pip install maturin && maturin develop --release
```

To build against a local fframes checkout, copy `.cargo/config.toml.example` to
`.cargo/config.toml`.

## How it works

A video is any Python object with `width`, `height`, `fps` (default 30), `duration`
(seconds, a `Duration`, or `None` for automatic) and either `render_frame(frame, ctx)` or
`scenes`. `fframes.cli(video)` reads that description once and hands it to the Rust
engine. For each frame the engine calls `render_frame`, which fills a template that was
parsed once: static subtrees are built once and shared by every frame, so Python only
computes the values that change.

| Topic | API |
| --- | --- |
| Templates | `template(markup)` with `{holes}` in attributes and children, `svgr(markup, **values)`, `Svgr.concat`, `Svgr.text` |
| Values | `Color`, `Transform`, `Path`, `Image` (all usable as hole values) |
| Animation | `timeline((at, from, to, easing), ...)`, `Easing` (CSS names, `cubic_bezier`, `spring`), `frame.animate`, `frame.animate_loop` |
| Time | `Duration` (`seconds`, `frames`, `from_audio`, `from_video`, `AUTO`), `Timestamp` |
| Scenes | `scenes = [...]` with `name`, `duration`, `overlap`, `audio`, `render_frame`; `frame.into_global()` |
| Audio | `AudioTrack(file, start, end)` with gain, fades, pan, ducking, EQ, loudness normalization |
| Media | `Media(*folders)`: images, audio, video, subtitles, Lottie and fonts, loaded once |
| Text | `frame.text_width`, `frame.text_fit`, `frame.text_layout` (wrapped lines) |
| Video | `frame.video_frame`, `frame.video_frame_at`, `Clip(file, start, end)` with speed, reverse, loop |
| Audio data | `frame.visualize_audio` (spectrum), `center_spectrum_low_frequencies` |
| Subtitles, Lottie | `frame.subtitle_phrase`, `frame.play_lottie` |
| Shaders | `Shader.sksl(src)`, `Shader.shadertoy(src)`, `shader.draw(frame, uniforms)` |
| Command line | `cli(video, argv, media=..., encoder=..., codec_params=...)`: `render`, `frame`, `strip`, `onion`, `svg`, `timeline`, `inspect`, `audio`, `preview` |

The full signatures are in [`python/fframes/_fframes.pyi`](python/fframes/_fframes.pyi).
A Python exception in `render_frame` stops the render and is raised by `cli` with its
traceback.

## Examples

`examples/` has a Python port of every [fframes example](https://github.com/Blockether/fframes/tree/main/examples).
They read their media from a fframes checkout (`$FFRAMES_DIR`, default `../fframes`).

| Example | Python port | Renderer | Every-frame parity |
|---|---|---|---|
| [`hello-world`](https://github.com/Blockether/fframes/tree/main/examples/hello-world) | [`examples/hello_world.py`](examples/hello_world.py) | cpu | every frame equal |
| [`captions`](https://github.com/Blockether/fframes/tree/main/examples/captions) | [`examples/captions.py`](examples/captions.py) | cpu | every frame equal |
| [`signal-lab`](https://github.com/Blockether/fframes/tree/main/examples/signal-lab) | [`examples/signal_lab.py`](examples/signal_lab.py) | cpu | every frame equal |
| [`marketing`](https://github.com/Blockether/fframes/tree/main/examples/marketing) | [`examples/marketing/main.py`](examples/marketing/main.py) | cpu | every frame equal |
| [`tiktok`](https://github.com/Blockether/fframes/tree/main/examples/tiktok) | [`examples/tiktok.py`](examples/tiktok.py) | cpu | every frame equal |
| [`podcast`](https://github.com/Blockether/fframes/tree/main/examples/podcast) | [`examples/podcast.py`](examples/podcast.py) | cpu | every frame equal |
| [`audio-announce`](https://github.com/Blockether/fframes/tree/main/examples/audio-announce) | [`examples/audio_announce.py`](examples/audio_announce.py) | cpu | every frame equal |
| [`neon-triangle`](https://github.com/Blockether/fframes/tree/main/examples/neon-triangle) | [`examples/neon_triangle.py`](examples/neon_triangle.py) | skia-cpu | every frame equal |
| [`shaders`](https://github.com/Blockether/fframes/tree/main/examples/shaders) | [`examples/shaders.py`](examples/shaders.py) | skia-cpu | every frame equal |
| [`anamorphic-video`](https://github.com/Blockether/fframes/tree/main/examples/anamorphic-video) | [`examples/anamorphic_video.py`](examples/anamorphic_video.py) | cpu | every frame equal |
| [`teej-podcast`](https://github.com/Blockether/fframes/tree/main/examples/teej-podcast) | [`examples/teej_podcast.py`](examples/teej_podcast.py) | cpu | every frame equal |
| [`conference-splash-screen`](https://github.com/Blockether/fframes/tree/main/examples/conference-splash-screen) | [`examples/conference_splash_screen.py`](examples/conference_splash_screen.py) | cpu | every frame equal |
| [`low-poly-art`](https://github.com/Blockether/fframes/tree/main/examples/low-poly-art) | [`examples/low_poly_art/main.py`](examples/low_poly_art/main.py) | cpu | every frame equal |
| [`beta`](https://github.com/Blockether/fframes/tree/main/examples/beta) | [`examples/beta/main.py`](examples/beta/main.py) | cpu | every frame outside 380..520, where the Rust example draws random content |
| [`lottie`](https://github.com/Blockether/fframes/tree/main/examples/lottie) | [`examples/lottie/main.py`](examples/lottie/main.py) | cpu | every frame equal |
| [`pixel-memory`](https://github.com/Blockether/fframes/tree/main/examples/pixel-memory) | [`examples/pixel_memory/main.py`](examples/pixel_memory/main.py) | cpu | every frame equal |
| [`shader-mode`](https://github.com/Blockether/fframes/tree/main/examples/shader-mode) | [`examples/shader_mode.py`](examples/shader_mode.py) | skia-cpu | every frame equal |
| [`made-of-motion`](https://github.com/Blockether/fframes/tree/main/examples/made-of-motion) | [`examples/made_of_motion.py`](examples/made_of_motion.py) | skia-cpu | every frame equal |
| [`svg-in-3d`](https://github.com/Blockether/fframes/tree/main/examples/svg-in-3d) | [`examples/svg_in_3d.py`](examples/svg_in_3d.py) | cpu | every frame equal |
| [`arm`](https://github.com/Blockether/fframes/tree/main/examples/arm) | [`examples/arm/__main__.py`](examples/arm/__main__.py) | cpu | every frame equal |
| [`fframes-intro`](https://github.com/Blockether/fframes/tree/main/examples/fframes-intro) | [`examples/fframes_intro.py`](examples/fframes_intro.py) | skia-cpu | the full rendered video and audio decode to the same values |
| `arm` (`arm-soundtrack` bin) | [`examples/arm_soundtrack.py`](examples/arm_soundtrack.py) | audio | the 18 WAV files are byte-identical |
| `conference-splash-screen` (`render_all` bin) | `conference_splash_screen.py render-all` | cpu | 11 previews pixel-equal, descriptions byte-equal |

`tools/parity.py --every NAME` checks every frame as PNG; `--render 0s..10s NAME` compares the decoded
video and audio of a rendered range.

## Same pixels, same speed

`tools/parity.py` renders frames of each port and of the Rust reference example and
compares them pixel by pixel; `tests/test_parity.py` runs it under pytest.
`tools/bench.py` times full renders of both, in turns.

```bash
python tools/parity.py              # every example in tools/parity.toml
python tools/bench.py -n 3 hello-world
```

Median of 3 interleaved full renders on an Apple M-series Mac (14 cores), default renderer of each example:

| Example | Python s | Rust s | Ratio | Python CPU s | Rust CPU s | CPU ratio | Note |
|---|---|---|---|---|---|---|---|
| hello-world | 0.54 | 0.51 | 1.05 | 5.38 | 5.33 | 1.01 | |
| captions | 0.20 | 0.19 | 1.06 | 2.00 | 1.99 | 1.01 | |
| signal-lab | 1.02 | 1.05 | 0.97 | 7.74 | 7.72 | 1.00 | |
| marketing | 5.39 | 5.45 | 0.99 | 63.70 | 65.02 | 0.98 | |
| tiktok | 41.06 | 42.52 | 0.97 | 512.46 | 530.14 | 0.97 | |
| podcast | 4.03 | 3.93 | 1.02 | 42.32 | 41.98 | 1.01 | |
| audio-announce | 13.71 | 13.68 | 1.00 | 147.04 | 143.97 | 1.02 | |
| neon-triangle | 1.59 | 1.61 | 0.99 | 14.71 | 15.10 | 0.97 | |
| shaders | 2.18 | 2.18 | 1.00 | 16.15 | 16.23 | 1.00 | |
| anamorphic-video | 0.20 | 0.19 | 1.01 | 1.01 | 1.01 | 1.00 | |
| teej-podcast | 24.76 | 25.55 | 0.97 | 33.27 | 34.30 | 0.97 | |
| conference-splash-screen | 2.59 | 2.52 | 1.03 | 7.93 | 7.84 | 1.01 | |
| low-poly-art | 1.33 | 1.26 | 1.05 | 16.21 | 16.05 | 1.01 | |
| beta | 4.31 | 4.32 | 1.00 | 50.42 | 51.14 | 0.99 | |
| lottie | 6.62 | 6.51 | 1.02 | 68.48 | 67.75 | 1.01 | |
| pixel-memory | 32.74 | 33.49 | 0.98 | 295.09 | 331.26 | 0.89 | |
| shader-mode | 5.64 | 6.40 | 0.88 | 54.49 | 55.12 | 0.99 | |
| made-of-motion | 10.60 | 10.60 | 1.00 | 90.14 | 86.96 | 1.04 | |
| svg-in-3d | 7.60 | 7.66 | 0.99 | 71.02 | 71.15 | 1.00 | |
| fframes-intro | 64.71 | 61.41 | 1.05 | 648.02 | 654.78 | 0.99 | |
| arm | 323.09 | 311.57 | 1.04 | 3871.44 | 3869.10 | 1.00 | 1 run, load average 21 |

The Python interpreter starts in about 12 ms. That is most of the difference in the examples that
render in less than a second.

## Vis extension

[`vis-extension/`](vis-extension) is a [Vis](https://github.com/Blockether/vis) extension:
the agent writes a video script with the `vis-fframes/fframes` skill and checks it with
the `fframes` tools: `new`, `timeline`, `frames` (attached PNGs), `inspect`, `strip` and
`render`.

```bash
vis-agent extension install ./vis-extension --global --trust   # then /reload
```

## License

MIT, like fframes.

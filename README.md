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

<!-- examples-table -->

## Same pixels, same speed

`tools/parity.py` renders frames of each port and of the Rust reference example and
compares them pixel by pixel; `tests/test_parity.py` runs it under pytest.
`tools/bench.py` times full renders of both, in turns.

```bash
python tools/parity.py              # every example in tools/parity.toml
python tools/bench.py -n 3 hello-world
```

<!-- bench-table -->

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

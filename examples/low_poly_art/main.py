"""Port of fframes/examples/low-poly-art: a low-poly eagle owl with audio bars.

python examples/low_poly_art/main.py render -o owl.mp4

The 2,394 polygons of the owl are static data in owl.svg (tools/convert_low_poly_art.py). The
template is parsed once and its static subtrees are prebuilt, so a frame costs only the noise
offset and the audio bars.
"""

import sys
from array import array
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import _media
import fframes as ff
from fframes import Transform

EXAMPLE = "low-poly-art"
MASK = (1 << 64) - 1

VIDEO = ff.template(
    """
<svg xmlns="http://www.w3.org/2000/svg" width="1920" height="1080">
  <defs>
    <pattern id="scratch-pattern" patternUnits="userSpaceOnUse" width="230" height="177">
      <image href="{noise}" x="0" y="0" width="230" height="177"/>
    </pattern>
  </defs>
  <rect width="1920" height="1080" x="0" y="0" fill="#000"/>
  {scenes}
</svg>
"""
)

OWL = ff.template(
    """
<defs>
  <clipPath id="clip-text">
    <text x="75%" y="35%" text-anchor="middle" font-size="100" font-family="Fredoka One">EAGLE OWL</text>
  </clipPath>
</defs>
<g clip-path="url(#clip-text)">
  <rect x="-100%" y="-100%" transform="{jitter}" width="300%" height="300%" fill="url(#scratch-pattern)"/>
</g>
<text x="75%" y="26%" text-anchor="middle" fill="#9f8866" font-size="45" font-family="Fredoka One">BUBO BUBO</text>
{bars}
"""
    + (Path(__file__).with_name("owl.svg")).read_text()
)

BAR = ff.template('<rect x="{x}" y="{y}" width="8" height="{height}" fill="white" rx="3" ry="3"/>')


def noise(index: int, seed: int) -> int:
    """Deterministic per-frame jitter in -30..30, as the Rust example computes it."""
    x = ((index ^ seed) * 0x9E37_79B9_7F4A_7C15) & MASK
    x ^= x >> 29
    x = (x * 0xBF58_476D_1CE4_E5B9) & MASK
    x ^= x >> 32
    return x % 60 - 30


class Owl:
    duration = 10.0
    audio = (("owl.mp3", ff.Timestamp.frame(0), ff.Timestamp.second(10.0)),)

    def render_frame(self, frame: ff.Frame, ctx: ff.Context) -> ff.Svgr:
        levels = frame.visualize_audio(
            ctx, "owl.mp3", sample_size=64, smooth_level=4, window="hamming"
        )
        heights = array(
            "f",
            (
                min(max(level, 20.0), 100.0)
                for level in ff.center_spectrum_low_frequencies(levels)[2:]
            ),
        )
        # 550 - height / 2 in f32, as Rust computes it.
        tops = array("f", (550.0 - height / 2.0 for height in heights))
        bars = ff.Svgr.concat(
            BAR(x=1220 + i * 15, y=top, height=height)
            for i, (height, top) in enumerate(zip(heights, tops, strict=True))
        )
        jitter = Transform.translate(
            noise(frame.index, 0x5EED_0001), noise(frame.index, 0x5EED_0002)
        )
        return OWL(jitter=jitter, bars=bars)


class LowPolyVideo:
    fps = 60
    width = 1920
    height = 1080
    duration = ff.Duration.AUTO

    def __init__(self):
        self.scenes = [Owl()]

    def render_frame(self, frame: ff.Frame, ctx: ff.Context) -> ff.Svgr:
        return VIDEO(noise=ctx.image("white_noise.png"), scenes=ctx.render_scenes(frame))


def main() -> int:
    # The Rust example embeds its media with include_media_dir!, which mixes audio to mono.
    media = ff.Media(_media.folder(EXAMPLE), _media.folder(EXAMPLE, "media/owl"), mono=True)
    return ff.cli(
        LowPolyVideo(),
        media=media,
        load_system_fonts=False,
        encoder=None,
        # The whole animal scene is cached as one subtree, so a small cache is enough.
        cache_capacity=5,
    )


if __name__ == "__main__":
    sys.exit(main())

"""Port of fframes/examples/svg-in-3d.

An svgr UI on the screen of a turning 3D monitor. The UI shows a 3D render of its own: a cube
with an svgr logo on its faces. So the frame nests four levels:

    logo svgr -> cube (3D) -> UI svgr -> monitor (3D) -> frame svgr

python examples/svg_in_3d.py render -o out.mp4 [--cpu]
"""

import argparse
import sys

import _media
import fframes as ff
import numpy as np
from fframes import three_d as td

f32 = np.float32

WIDTH = 1920
HEIGHT = 1080
FPS = 30
SECONDS = f32(8.0)
TAU = f32(6.2831855)

# The size of the UI texture: the 16:10 screen at 1280 x 800.
UI = (1280, 800)
# The size of the cube render in the UI.
CUBE = 480

LOGO = ff.svgr("""
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 256 256" width="256" height="256">
    <rect x="0" y="0" width="256" height="256" fill="#2f81f7" />
    <rect x="14" y="14" width="228" height="228" rx="28" fill="none" stroke="#ffffff" stroke-width="10" />
    <text x="128" y="168" text-anchor="middle" font-family="DM Sans" font-size="116" fill="#ffffff">ff</text>
</svg>
""")

SCREEN_UI = ff.template("""
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1280 800" width="1280" height="800">
    <rect x="0" y="0" width="1280" height="800" fill="#0d1117" />
    <rect x="0" y="0" width="1280" height="96" fill="#161b22" />
    <circle cx="52" cy="48" r="12" fill="#ff5f56" />
    <circle cx="88" cy="48" r="12" fill="#ffbd2e" />
    <circle cx="124" cy="48" r="12" fill="#27c93f" />
    <text x="168" y="62" font-family="DM Sans" font-size="38" fill="#e6edf3">ctx.render_svgr</text>
    <text x="1232" y="64" text-anchor="end" font-family="JetBrains Mono" font-size="40" fill="#ff7b72">{timer}</text>
    <rect x="64" y="148" width="528" height="528" rx="24" fill="#161b22" />
    <image href="{cube}" x="88" y="172" width="480" height="480" />
    <text x="660" y="236" font-family="JetBrains Mono" font-size="34" fill="#7ee787">svg  -&gt; 3D</text>
    <text x="660" y="296" font-family="JetBrains Mono" font-size="34" fill="#79c0ff">3D   -&gt; svg</text>
    <text x="660" y="356" font-family="JetBrains Mono" font-size="34" fill="#d2a8ff">svg  -&gt; 3D</text>
    <text x="660" y="416" font-family="JetBrains Mono" font-size="34" fill="#ffa657">3D   -&gt; frame</text>
    <text x="660" y="520" font-family="DM Sans" font-size="30" fill="#8b949e">frame {index}</text>
    <rect x="660" y="600" width="540" height="18" rx="9" fill="#30363d" />
    <rect x="660" y="600" width="{progress}" height="18" rx="9" fill="#2f81f7" />
</svg>
""")

FRAME = ff.template("""
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1920 1080" width="1920" height="1080">
    <defs>
        <radialGradient id="room" cx="50%" cy="38%" r="75%">
            <stop offset="0%" stop-color="#3a4150" />
            <stop offset="100%" stop-color="#0b0d12" />
        </radialGradient>
    </defs>
    <rect x="0" y="0" width="1920" height="1080" fill="url(#room)" />
    <image href="{monitor}" x="0" y="0" width="1920" height="1080" />
    <text x="96" y="1010" font-family="DM Sans" font-size="34" fill="#8b949e">An svgr UI on a 3D screen. The UI holds a 3D render with an svgr logo.</text>
</svg>
""")


def timer(t: np.float32) -> str:
    """`m:ss.cc` of `t` seconds."""
    centis = int(np.round(t * f32(100.0)))
    return f"{centis // 6000}:{centis // 100 % 60:02}.{centis % 100:02}"


class Monitor:
    """The monitor, the cube and their renderers. Built once, posed in each frame."""

    fps = FPS
    width = WIDTH
    height = HEIGHT
    background_color = ff.Color.BLACK
    duration = float(SECONDS)

    def __init__(self, cpu: bool = False):
        scene = td.Scene(td.Environment.studio())
        frame = td.Material.metal(0x2A2D33, 0.35).clearcoat(0.6)
        self.body = scene.add(
            td.Node.mesh(td.Geometry.rounded_box(1.84, 1.2, 0.09, 0.035, 4), frame).at(
                0.0, 1.32, 0.0
            )
        )
        # The UI shows as it is: an unlit screen with the UI texture, set in each frame.
        self.screen = scene.add_to(
            self.body,
            td.Node.mesh(td.Geometry.plane(1.68, 1.05), td.Material.unlit(0xFFFFFF)).at(
                0.0, 0.0, 0.0455
            ),
        )
        scene.add(
            td.Node.mesh(td.Geometry.cylinder(0.05, 0.06, 0.62, 24), frame).at(0.0, 0.5, -0.06)
        )
        scene.add(
            td.Node.mesh(td.Geometry.rounded_box(0.8, 0.04, 0.42, 0.02, 3), frame).at(
                0.0, 0.2, -0.06
            )
        )
        scene.add(
            td.Node.mesh(td.Geometry.floor(20.0, 20.0), td.Material.shadow_catcher(0.55))
            .at(0.0, 0.18, 0.0)
            .shadows(False, True)
        )
        scene.add(td.Node.light(td.Light.sun(td.Rgb.WHITE, 2.5, (2.5, 6.0, 4.0))))
        self.scene = scene

        cube_scene = td.Scene(td.Environment.studio())
        self.cube_node = cube_scene.add(
            td.Node.mesh(
                td.Geometry.cuboid(1.0, 1.0, 1.0), td.Material.standard(0xFFFFFF).roughness(0.35)
            )
        )
        cube_scene.add(td.Node.light(td.Light.sun(td.Rgb.WHITE, 2.0, (2.0, 3.0, 4.0))))
        self.cube_scene = cube_scene

        self.renderer = td.Renderer(WIDTH, HEIGHT).tone_mapping("neutral")
        self.cube_renderer = td.Renderer(CUBE, CUBE).tone_mapping("neutral")
        if cpu:
            # Renders the 3D on the CPU, also with a GPU.
            self.renderer = self.renderer.cpu()
            self.cube_renderer = self.cube_renderer.cpu()
        self.cube_camera = td.Camera.perspective(35.0).at(0.0, 0.0, 3.4)
        self.monitor_camera = td.Camera.perspective(30.0)
        self.camera_target = td.Vec3(0.0, 1.1, 0.0)
        self.turn = f32(td.deg(52.0))

    def cube(self, logo: ff.Image, t: np.float32) -> ff.Image:
        """The cube with `logo` on its faces at `t` seconds."""
        scene = self.cube_scene.clone()
        scene.set_rotation(self.cube_node, td.euler(t * f32(0.7), t * f32(1.1), 0.25))
        scene.set_map_image(self.cube_node, logo)
        return self.cube_renderer.render(scene, self.cube_camera)

    def monitor(self, ui: ff.Image, t: np.float32) -> ff.Image:
        """The monitor with `ui` on its screen at `t` seconds."""
        scene = self.scene.clone()
        # turns far enough that the text on the screen is seen at a low angle
        swing = f32(td.sin(t / SECONDS * TAU)) * self.turn
        scene.set_rotation(self.body, td.euler(0.0, swing, 0.0))
        scene.set_map_image(self.screen, ui)
        azimuth = f32(12.0) * f32(td.sin(t * f32(0.4)))
        camera = self.monitor_camera.orbit(self.camera_target, 4.6, azimuth, 9.0)
        return self.renderer.render(scene, camera)

    def render_frame(self, frame: ff.Frame, ctx: ff.Context) -> ff.Svgr:
        t = f32(frame.seconds)
        # level 1: a static svgr logo
        logo = ctx.render_svgr(LOGO, 256, 256)
        if logo is None:
            return ff.svgr("")
        # level 2: the logo on a turning cube
        cube = self.cube(logo, t)
        # level 3: the UI with a live timer and the cube render
        progress = t / SECONDS
        ui = ctx.render_svgr(
            SCREEN_UI(
                timer=timer(t),
                cube=cube,
                index=frame.index,
                progress=float(f32(18.0) + f32(522.0) * progress),
            ),
            *UI,
        )
        if ui is None:
            return ff.svgr("")
        # level 4: the UI on the screen of the monitor, in the frame
        return FRAME(monitor=self.monitor(ui, t))


def main() -> int:
    parser = argparse.ArgumentParser(add_help=False)
    # Render everything on the CPU: the 3D with the software rasterizer, the svgr images and
    # the frame with the tiny-skia backend.
    parser.add_argument("--cpu", action="store_true")
    args, rest = parser.parse_known_args()
    video = Monitor(cpu=args.cpu)
    return ff.cli(
        video,
        [sys.argv[0], *rest],
        media=_media.media("svg-in-3d"),
        load_system_fonts=False,
        default_output="out.mp4",
        # Like the Rust example: Skia on the GPU unless --cpu.
        renderer=None if args.cpu else "gpu",
        gpu_contexts="max",
    )


if __name__ == "__main__":
    sys.exit(main())

"""A robot arm in a dark lab builds the word "fframes" from 3D letters, drops one and recovers.

Port of the Rust `arm` example. The `arm-soundtrack` program writes the sounds first:
python examples/arm/soundtrack.py, then python examples/arm render -o out.mp4 [--cpu | --readback]
"""

import argparse
import sys
from pathlib import Path

import fframes as ff
import numpy as np
from fframes import three_d as td

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import _media
import arm
import lab
import story
from arm import Arm, Expression, Palette
from effects import direction, hash, hash_array, noise_array, progress, shake
from fmath import ONE, ZERO, F, clamp, cos, deg, fmax, fract, sin, smoothstep, u32
from story import Sound, Story

Vec3 = td.Vec3
WIDTH, HEIGHT, FPS = 1920, 1080, 60
FONT = (_media.folder("arm") / "Inter_18pt-ExtraBold.ttf").read_bytes()
WORD = "fframes"
WORD_Z = story.WORD_Z
MONO = "IBM Plex Mono"
INK = "#1c1d20"
ORANGE = "#ff4a00"
# The part of a frame that the shutter is open in motion blur.
SHUTTER = F(0.5)

DUST = 4000
DUST_COLOR = td.Rgb.hex(0xFFD6A8)
CONE = (cos(deg(17.0)), cos(deg(9.0)))
# Dots in the trail of one spark.
DOTS = 8
SPARK_TRAIL = F(1.5) / F(FPS)
COLD, HOT = td.Rgb.hex(0xFF5A10), td.Rgb.hex(0xFFF2C0)
FLICK = [F(x) for x in (0.0, 0.06, 0.12, 0.2, 0.27)]

EFFECTS = {
    Sound.LIGHTS_ON: ("lights.wav", -4.0),
    Sound.BOOT: ("boot.wav", -16.0),
    Sound.BLINK: ("blink.wav", -16.0),
    Sound.CURIOUS: ("curious.wav", -15.0),
    Sound.HAPPY: ("happy.wav", -16.0),
    Sound.GRIP: ("grip.wav", -10.0),
    Sound.PLACE: ("place.wav", -5.0),
    Sound.WHOOSH: ("whoosh.wav", -16.0),
    Sound.SCRATCH: ("scratch.wav", -4.0),
    Sound.UH_OH: ("uhoh.wav", -13.0),
    Sound.SIGH: ("sigh.wav", -14.0),
    Sound.PAT: ("pat.wav", -9.0),
    Sound.PROUD: ("proud.wav", -15.0),
    Sound.TA_DA: ("tada.wav", -14.0),
}


def effect(sound) -> tuple[str, float]:
    """The file and gain of a sound. A clatter is louder for a faster hit."""
    if isinstance(sound, tuple):
        _, speed = sound
        return "clatter.wav", float(F(-14.0) + F(4.0) * min(F(speed), F(4.0)))
    return EFFECTS[sound]


def rs(x) -> str:
    """Rust `{}` of an f32."""
    return np.format_float_positional(F(x), unique=True, trim="-")


FRAME = ff.template("""
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1920 1080" width="{width}" height="{height}">
    <image href="{image}" x="0" y="0" width="1920" height="1080" />
    {marker}
    {overlay}
</svg>
""")

MARKER = ff.template("""
<g opacity="{shown}" font-family="{mono}" fill="{orange}">
    <path d="{corners}" fill="none" stroke="{orange}" stroke-width="2.5" />
    <text x="{x}" y="{y0}" font-weight="600" font-size="15" letter-spacing="2">{label}</text>
    <text x="{x}" y="{y1}" font-weight="400" font-size="13" letter-spacing="1.5">{away}</text>
</g>
""")

LOG_LINE = ff.template('<text x="96" y="{y}" fill="{color}" opacity="{fade}">{text}</text>')

OVERLAY = ff.template("""
<g>
    <g opacity="{ui}" font-family="{mono}" font-weight="600" font-size="14" letter-spacing="3" fill="{ink}">
        <text x="96" y="100">OD-ARM 7.2</text>
        <text x="96" y="122" opacity="0.5">LAB 3  /  CELL R-07</text>
        <text x="1824" y="100" text-anchor="end">{placed}</text>
        <text x="1824" y="122" text-anchor="end" opacity="0.5">PIECES IN PLACE</text>
        <g font-weight="400" font-size="15" letter-spacing="1.5">{lines}</g>
    </g>
    <g opacity="{caption}" font-family="{mono}" fill="{ink}">
        <rect x="938" y="968" width="44" height="2" fill="{orange}" />
        <text x="960" y="1004" text-anchor="middle" font-weight="400" font-size="13" letter-spacing="6" opacity="0.6">BUILT WITH FFRAMES-3D</text>
    </g>
    <rect x="0" y="0" width="1920" height="1080" fill="#000000" opacity="{black}" />
</g>
""")

EMPTY = ff.svgr("")


class Sparks:
    """The sparks of one hard hit: fixed velocities and lives, computed once."""

    def __init__(self, at: Vec3, start, speed, count: int, seed: int):
        self.at, self.start = at, F(start)
        ids = [(seed * 7919 + i) & 0xFFFFFFFF for i in range(count)]
        v = np.empty((count, 3), dtype=np.float32)
        for n, id in enumerate(ids):
            d = direction(id) * speed * (F(0.35) + F(0.65) * hash(id ^ 0x5BD1))
            v[n] = d.x, d.y, d.z
        v[:, 1] = np.abs(v[:, 1]) * F(0.8) + F(0.3)
        self.v = v[:, None, :]
        ids = np.array(ids, dtype=np.uint32)
        self.life = (F(0.35) + F(0.6) * hash_array(ids ^ np.uint32(0x2C1B)))[:, None]
        self.tail = (np.arange(DOTS, dtype=np.float32) / F(DOTS))[None, :]

    def at_time(self, t):
        """(positions, sizes, colors, opacities) at `t`, in the order of the Rust example."""
        since = t - self.start
        if not (ZERO <= since < ONE + SPARK_TRAIL):
            return None
        age = since - self.tail * SPARK_TRAIL
        x = age / self.life
        age = np.broadcast_to(age, x.shape)
        keep = (age >= ZERO) & (x < ONE)
        age, x, tail = age[keep], x[keep], np.broadcast_to(self.tail, keep.shape)[keep]
        v = np.broadcast_to(self.v, (*keep.shape, 3))[keep]
        at = self.at
        p = np.empty((len(age), 3), dtype=np.float32)
        p[:, 0] = F(at.x) + v[:, 0] * age
        p[:, 1] = F(at.y) + v[:, 1] * age + F(-4.9) * age * age
        p[:, 2] = F(at.z) + v[:, 2] * age
        low = p[:, 1] < F(0.005)
        p[low, 1] = F(0.005) + (F(0.005) - p[low, 1]) * F(0.25)
        heat = ONE - x
        s = heat * heat
        gain = F(2.0) + F(10.0) * heat
        fade = ONE - tail
        color = np.empty_like(p)
        for c, (a, b) in enumerate(((COLD.r, HOT.r), (COLD.g, HOT.g), (COLD.b, HOT.b))):
            color[:, c] = (F(a) * (ONE - s) + F(b) * s) * gain * fade
        return p, F(0.003) + F(0.004) * heat, color, heat * fade


class Show:
    """The lab, the arm and the story, built once. Each frame poses a clone of the scene."""

    width, height, fps = WIDTH, HEIGHT, FPS
    background_color = ff.Color.BLACK

    def __init__(self, cpu: bool = False, read_back: bool = False):
        scene = td.Scene()
        self.lab = lab.Lab(scene, FONT)
        self.arm = Arm(scene, Palette(), FONT)
        self.story = Story(FONT, WORD)
        lacquer = td.Material.standard(0x111113).roughness(0.2).clearcoat(1.0)
        self.letter_nodes = [
            scene.add(td.Node.mesh(l.geometry, lacquer)) for l in self.story.letters
        ]
        self.dust = scene.add(td.Node.particles("additive"))
        self.sparks = scene.add(td.Node.particles("additive"))
        self.scene = scene
        renderer = (
            td.Renderer(WIDTH, HEIGHT)
            .gpu()
            .tone_mapping("neutral")
            .exposure(0.92)
            .bloom(0.4, 0.45, 1.2)
        )
        self.renderer = renderer.cpu() if cpu else renderer
        self.read_back = read_back and not cpu
        self.shutter = [F(o) for o in td.Renderer.shutter_offsets(3)]
        b = self.story.beats
        self.duration = float(b.end + F(0.6))
        self.audio = self.tracks()

        self.dust_home = self.dust_homes()
        seeds = np.arange(DUST, dtype=np.uint32)
        self.dust_seeds = (seeds, seeds + np.uint32(7919), seeds + np.uint32(15485))
        self.dust_size = F(0.006) + F(0.004) * hash_array(seeds * np.uint32(4) + np.uint32(3))
        self.hit_sparks = self.all_sparks()
        self.hits = [(at, F(0.35) * speed) for f in self.story.falls for at, speed in f.impacts]

        self.r_start = self.placed_time(2) - F(1.2)
        self.show_off = self.placed_time(2) + F(0.45)
        self.reaction = b.drop + F(1.25)
        self.last = self.placed_time(6)

    def tracks(self) -> list:
        tracks = [
            ff.AudioTrack("music.wav").gain_db(-4.0),
            ff.AudioTrack("room.wav").gain_db(-18.0).fade_in(0.5),
            ff.AudioTrack("servos.wav").gain_db(-11.0),
        ]
        for t, sound in self.story.sounds:
            file, gain = effect(sound)
            tracks.append(ff.AudioTrack(file, float(fmax(t, ZERO))).gain_db(gain))
        return tracks

    @staticmethod
    def dust_homes() -> np.ndarray:
        i = np.arange(DUST, dtype=np.uint32) * np.uint32(4)
        r = [hash_array(i + np.uint32(k)) for k in range(3)]
        return np.stack(
            [F(-1.4) + F(3.4) * r[0], F(0.05) + F(2.4) * r[1], F(-0.8) + F(3.4) * r[2]],
            axis=1,
        )

    def all_sparks(self) -> list:
        letter = self.story.letters[self.story.dropped]
        impacts = [hit for f in self.story.falls for hit in f.impacts]
        out = []
        for i, (at, speed) in enumerate(impacts):
            if speed > F(0.8):
                center = letter.world(at, self.story.track, self.story.falls).w_axis
                hit = Vec3(center.x, 0.01, center.z)
                out.append(Sparks(hit, at, speed * F(0.9), u32(speed * F(12.0)), i))
        return out

    def placed_time(self, i: int):
        """When letter `i` reaches its slot for the last time."""
        letter = self.story.letters[i]
        for t, (kind, m) in reversed(letter.phases):
            if kind == "still" and m == letter.slot:
                return t
        return ZERO

    def motion_blur(self, t) -> bool:
        return self.show_off <= t < self.reaction

    def lights(self, t):
        on = self.story.beats.lights
        if t < on:
            return ZERO
        x = t - on
        if x < F(0.35):
            # fluorescent tubes that flicker on
            lit = sum(x >= f for f in FLICK) % 2 == 1
            return F(0.75) if lit else F(0.08)
        return smoothstep(0.35, 0.6, x) * F(0.25) + F(0.75)

    def lagged(self, t, point) -> Vec3:
        """The mean of `point` over the last 0.2 s: a camera that follows with a lag."""
        total = Vec3.ZERO
        for k in range(5):
            total = total + point(self.story.track.sample(fmax(t - F(k) * F(0.05), ZERO))[0])
        return total / 5.0

    def lagged_tip(self, t) -> Vec3:
        return self.lagged(t, lambda q: arm.tip(q).w_axis)

    def lagged_eye(self, t) -> Vec3:
        return self.lagged(t, arm.eye)

    def camera(self, t) -> td.Camera:
        b = self.story.beats
        lens = td.Camera.perspective(32.0)
        if t < b.work:
            # hello: close on the face of the arm
            x = progress(t, ZERO, b.work)
            eye = self.lagged_eye(t)
            offset = Vec3(F(0.25) * (ONE - x), F(0.05) * x, F(0.35) * (ONE - x))
            return (
                lens.fov(30.0)
                .position(story.HELLO_CAMERA + offset)
                .look_at(eye.lerp(Vec3(0.0, 0.9, 0.6), 0.35))
                .focus_on(eye, 5.0)
            )
        if t < self.r_start:
            # work: a slow orbit that follows the tool
            x = progress(t, b.work, self.r_start)
            tip = self.lagged_tip(t)
            return lens.orbit(
                Vec3(0.0, 0.75, 0.2).lerp(tip, 0.25),
                F(5.4) - F(0.4) * x,
                F(-42.0) + F(24.0) * x,
                13.0,
            ).focus_on(tip, 8.0)
        if t < self.show_off:
            # the word grows: low and close on the letters
            target = Vec3(-0.35, 0.33, WORD_Z)
            return (
                lens.fov(30.0)
                .position(Vec3(1.35, 0.42, 3.15))
                .look_at(target)
                .focus_on(target, 12.0)
            )
        if t < self.reaction:
            # show-off and the drop: wide, with a shake at each hit
            x = progress(t, self.show_off, self.reaction)
            camera = (
                lens.fov(36.0)
                .position(Vec3(F(3.7) - F(0.3) * x, 1.75, F(4.4) - F(0.3) * x))
                .look_at(Vec3(-0.25, 0.75, 0.25))
                .focus(5.6, 5.0)
            )
            return shake(camera, t, self.hits)
        if t < b.recover:
            # guilty: on the face
            eye = self.lagged_eye(t)
            return (
                lens.fov(28.0)
                .position(story.GUILTY_CAMERA)
                .look_at(eye.lerp(Vec3(-0.2, 0.6, 0.6), 0.15))
                .focus_on(eye, 14.0)
            )
        if t < b.finish:
            # recover: the tool and the lost letter
            tip = self.lagged_tip(t)
            s = self.story
            letter = s.letters[s.dropped].world(t, s.track, s.falls).w_axis
            target = letter.lerp(tip, 0.4)
            return (
                lens.fov(34.0)
                .position(Vec3(2.9, 0.75, 2.9))
                .look_at(target + Vec3(0.0, 0.1, 0.0))
                .focus_on(target, 9.0)
            )
        if t < self.last + F(0.3):
            # finish: an orbit around the work
            x = progress(t, b.finish, self.last + F(0.3))
            return lens.orbit(
                Vec3(0.0, 0.55, 0.35), 6.4, F(28.0) - F(18.0) * x, F(24.0) - F(4.0) * x
            ).focus(6.4, 4.0)
        # ta-da: back out to the whole word
        x = smoothstep(self.last + F(0.3), b.end, t)
        return (
            lens.fov(30.0)
            .position(story.FINAL_CAMERA + Vec3(0.0, F(-0.05) * x, F(-0.5) * x))
            .look_at(Vec3(0.0, 0.92, 0.55))
            .focus(F(story.FINAL_CAMERA.z) - WORD_Z - F(0.5) * x, 6.0)
        )

    def set_dust(self, scene: td.Scene, t, q, beam) -> None:
        """Dust in the light beam of the eye."""
        if beam <= ZERO:
            return
        eye = arm.eye(q)
        axis = arm.flange(q).z_axis
        a, b, c = self.dust_seeds
        home = self.dust_home
        p = np.empty_like(home)
        p[:, 0] = home[:, 0] + noise_array(a, t * F(0.25)) * F(0.08)
        p[:, 1] = home[:, 1] + noise_array(b, t * F(0.2)) * F(0.08) - F(0.01) * t
        p[:, 2] = home[:, 2] + noise_array(c, t * F(0.25)) * F(0.08)
        to = p - np.array([eye.x, eye.y, eye.z], dtype=np.float32)
        tx, ty, tz = to[:, 0], to[:, 1], to[:, 2]
        distance = np.sqrt(tx * tx + ty * ty + tz * tz)
        along = (tx * F(axis.x) + ty * F(axis.y) + tz * F(axis.z)) / distance
        s = np.clip((along - CONE[0]) / (CONE[1] - CONE[0]), ZERO, ONE)
        cone = s * s * (F(3.0) - F(2.0) * s)
        light = beam * cone / (ONE + distance * distance)
        keep = light > F(0.01)
        light = light[keep]
        glow = F(3.0) * light
        colors = np.stack(
            [F(DUST_COLOR.r) * glow, F(DUST_COLOR.g) * glow, F(DUST_COLOR.b) * glow], axis=1
        )
        scene.set_particles(
            self.dust,
            p[keep].tobytes(),
            self.dust_size[keep].tobytes(),
            colors.tobytes(),
            np.minimum(light, ONE).tobytes(),
        )

    def set_sparks(self, scene: td.Scene, t) -> None:
        parts = [p for s in self.hit_sparks if (p := s.at_time(t)) is not None]
        if not parts:
            return
        scene.set_particles(self.sparks, *(np.concatenate(col).tobytes() for col in zip(*parts)))

    def carrying(self, t) -> bool:
        return any(l.phase(t)[0] == "carried" for l in self.story.letters)

    def scene_at(self, t) -> tuple:
        s = self.story
        scene = self.scene.clone()
        level = self.lights(t)
        self.lab.set_lights(scene, level)
        q, gap = s.track.sample(t)
        wake = s.beats.wake
        booting = smoothstep(wake, wake + F(0.5), t)
        # the eye flickers while it starts
        flicker = F(1.0)
        if wake + F(0.5) <= t < wake + F(0.8) and hash(u32((t - wake) * F(40.0)) + 5) > F(0.5):
            flicker = F(0.3)
        beam = clamp(ONE - level, ZERO, ONE)
        face = Expression(
            ring=F(0.8)
            + booting * (F(2.2) + F(0.8) * fmax(sin(t * F(2.0)), ZERO))
            + F(3.0) * smoothstep(s.beats.tada, s.beats.tada + F(0.3), t),
            status=F(7.0) if self.carrying(t) else F(0.5) * booting,
            eye=F(7.0) * smoothstep(wake + F(0.5), wake + F(0.8), t) * flicker,
            lid=s.lid(t),
            beam=beam,
        )
        self.arm.apply(scene, q, gap, face)
        self.set_dust(scene, t, q, beam * face.eye / F(7.0) * face.lid)
        self.set_sparks(scene, t)
        for letter, node in zip(s.letters, self.letter_nodes):
            _, rotation, position = letter.world(
                t, s.track, s.falls
            ).to_scale_rotation_translation()
            scene.set_position(node, position)
            scene.set_rotation(node, rotation)
        return scene, self.camera(t)

    def image(self, t):
        if self.motion_blur(t):
            moments = [self.scene_at(t + o * SHUTTER / F(FPS)) for o in self.shutter]
            return self.renderer.render_motion_blur(moments, read_back=self.read_back)
        scene, camera = self.scene_at(t)
        return self.renderer.render(scene, camera, read_back=self.read_back)

    def marker(self, t, camera: td.Camera):
        """A frame around the lost letter, with its distance from its slot."""
        s = self.story
        letter = s.letters[s.dropped]
        kind, m = letter.phase(t)
        lost = kind == "falling" or (kind == "still" and m != letter.slot)
        shown = smoothstep(s.beats.drop + F(0.3), s.beats.drop + F(0.5), t)
        if not lost or shown <= ZERO:
            return EMPTY
        world = letter.world(t, s.track, s.falls)
        center = world.transform_point3(letter.center)
        at = camera.project(center, WIDTH, HEIGHT)
        if at is None:
            return EMPTY
        size = F(camera.pixel_size(center, 0.42, HEIGHT))
        x0, y0 = F(at.x) - size * F(0.5), F(at.y) - size * F(0.5)
        x1, y1 = x0 + size, y0 + size
        corner = fmax(size * F(0.22), F(8.0))
        x0s, y0s, x1s, y1s = rs(x0), rs(y0), rs(x1), rs(y1)
        corners = (
            f"M{x0s} {rs(y0 + corner)} V{y0s} H{rs(x0 + corner)} M{rs(x1 - corner)} {y0s} H{x1s} V{rs(y0 + corner)} "
            f"M{x1s} {rs(y1 - corner)} V{y1s} H{rs(x1 - corner)} M{rs(x0 + corner)} {y1s} H{x0s} V{rs(y1 - corner)}"
        )
        slot = letter.slot.transform_point3(letter.center)
        name = WORD[s.dropped] if s.dropped < len(WORD) else "?"
        return MARKER(
            shown=float(shown),
            mono=MONO,
            orange=ORANGE,
            corners=corners,
            x=float(x1 + F(12.0)),
            y0=float(y0 + F(14.0)),
            y1=float(y0 + F(34.0)),
            label=f'PIECE {s.dropped + 1:02}  "{name}"',
            away=f"{float(F(center.distance(slot))):.2f} M FROM SLOT",
        )

    def overlay(self, t):
        """The lab screen: the arm name, the count of placed letters and the log."""
        s, b = self.story, self.story.beats
        placed = sum(1 for l in s.letters if (p := l.phase(t))[0] == "still" and p[1] == l.slot)
        ui = smoothstep(b.lights, b.lights + F(0.4), t) * (
            ONE - smoothstep(b.end - F(0.6), b.end, t)
        )
        shown = [line for line in s.log if line[0] <= t]
        tail = shown[max(len(shown) - 5, 0) :]
        lines = []
        for i, (at, text, alert) in enumerate(tail):
            chars = min(u32((t - at) * F(45.0)), len(text))
            cursor = "_" if i == len(tail) - 1 and fract(t * F(2.5)) < F(0.5) else ""
            lines.append(
                LOG_LINE(
                    y=float(F(1000.0) - F(len(tail) - 1 - i) * F(24.0)),
                    color=ORANGE if alert else INK,
                    fade=float(F(0.35) + F(0.65) * (F(i) + ONE) / F(len(tail))),
                    text=f"> {text[:chars]}{cursor}",
                )
            )
        caption = smoothstep(b.tada + F(0.3), b.tada + F(0.8), t)
        d = F(self.duration)
        black = fmax(ONE - smoothstep(0.0, 0.4, t), smoothstep(d - F(0.5), d, t))
        return OVERLAY(
            ui=float(ui),
            mono=MONO,
            ink=INK,
            orange=ORANGE,
            placed=f"{placed:02} / {len(s.letters):02}",
            lines=lines,
            caption=float(caption),
            black=float(black),
        )

    def render_frame(self, frame: ff.Frame, ctx: ff.Context) -> ff.Svgr:
        t = F(frame.seconds)
        image = self.image(t)
        return FRAME(
            width=WIDTH,
            height=HEIGHT,
            image=image,
            marker=self.marker(t, self.camera(t)),
            overlay=self.overlay(t),
        )


def main() -> int:
    parser = argparse.ArgumentParser(add_help=False)
    # Render the 3D with the software rasterizer and the frame on the CPU.
    parser.add_argument("--cpu", action="store_true")
    # Read the GPU render back to memory (to measure the GPU readback path).
    parser.add_argument("--readback", action="store_true")
    args, rest = parser.parse_known_args()
    video = Show(cpu=args.cpu, read_back=args.readback)
    media = ff.Media(_media.folder("arm"), _media.folder("arm", "dynamic_media"))
    return ff.cli(
        video,
        [sys.argv[0], *rest],
        media=media,
        codec_params={"crf": "17", "preset": "medium", "tune": "film"},
        default_output="out.mp4",
        renderer=None if args.cpu else "gpu",
        gpu_contexts="max",
        master_gain_db=6.5,
        limiter={"ceiling_db": -1.3},
    )


if __name__ == "__main__":
    sys.exit(main())

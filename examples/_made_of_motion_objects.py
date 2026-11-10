"""Rotating pixel objects of made_of_motion in camera space (objects.rs, hero.rs).

Choreography is sampled once, when the video is built, in float32 so it matches the Rust example.
"""

import math
from dataclasses import dataclass, replace

import fframes as ff
import numpy as np
from fframes import Easing

F = np.float32
PI = F(math.pi)
TAU = F(math.tau)
ZERO = F(0.0)
ONE = F(1.0)


def sin(a):
    return F(math.sin(a))


def cos(a):
    return F(math.cos(a))


def turn(p, a, b, angle):
    s, c = sin(angle), cos(angle)
    p = list(p)
    p[a], p[b] = c * p[a] - s * p[b], s * p[a] + c * p[b]
    return p


@dataclass(frozen=True)
class Excursion:
    start: int
    departure: int
    arrival: int
    return_start: int
    return_end: int


# Each return finishes before the next object leaves.
EXCURSIONS = (
    Excursion(200, 190, 205, 214, 225),
    Excursion(237, 227, 242, 249, 259),
    Excursion(265, 261, 270, 280, 294),
)


@dataclass
class Object:
    icon: int
    center: tuple
    right: tuple
    down: tuple
    size: F
    stretch: tuple
    heat: F
    soot: F
    pixels: F
    angles: tuple
    bounds: tuple

    @staticmethod
    def new(icon, center, size, angles, heat):
        center = tuple(F(v) for v in center)
        angles = tuple(F(v) for v in angles)

        def rotate(p):
            return tuple(turn(turn(turn(p, 0, 2, angles[0]), 1, 2, angles[1]), 0, 1, angles[2]))

        right = rotate([ONE, ZERO, ZERO])
        down = rotate([ZERO, ONE, ZERO])
        obj = Object(
            icon, center, right, down, F(size), (ONE, ONE), F(heat), ZERO, F(32.0), angles, ()
        )
        return obj.with_stretch((ONE, ONE))

    def with_stretch(self, stretch):
        stretch = tuple(F(v) for v in stretch)
        low = [F(1440.0), F(1080.0)]
        high = [ZERO, ZERO]
        half = F(0.5)
        for x, y in ((-1.0, -1.0), (1.0, -1.0), (1.0, 1.0), (-1.0, 1.0)):
            x, y = F(x), F(y)
            p = [
                self.center[i]
                + (x * self.right[i] * stretch[0] + y * self.down[i] * stretch[1])
                * self.size
                * half
                for i in range(3)
            ]
            screen = (F(720.0) + F(1250.0) * p[0] / p[2], F(540.0) + F(1250.0) * p[1] / p[2])
            for i in range(2):
                low[i] = min(low[i], screen[i])
                high[i] = max(high[i], screen[i])
        x = max(F(math.floor(low[0] - F(2.0))), ZERO)
        y = max(F(math.floor(low[1] - F(2.0))), ZERO)
        w = min(F(math.ceil(high[0] + F(2.0))), F(1440.0)) - x
        h = min(F(math.ceil(high[1] + F(2.0))), F(1080.0)) - y
        return replace(self, stretch=stretch, bounds=(x, y, w, h))

    def handoff(self, target, progress, lift):
        progress = F(progress)

        def mix(a, b):
            return a + (b - a) * progress

        center = [mix(a, b) for a, b in zip(self.center, target.center)]
        center[1] -= sin(progress * PI) * F(lift)
        obj = Object.new(
            self.icon,
            center,
            mix(self.size, target.size),
            [mix(a, b) for a, b in zip(self.angles, target.angles)],
            mix(self.heat, target.heat),
        )
        obj = replace(obj, soot=mix(self.soot, target.soot), pixels=mix(self.pixels, target.pixels))
        return obj.with_stretch([mix(a, b) for a, b in zip(self.stretch, target.stretch)])

    def continued(self, previous, elapsed):
        elapsed = F(elapsed)

        def extend(a, b):
            return a + (a - b) * elapsed

        obj = Object.new(
            self.icon,
            [extend(a, b) for a, b in zip(self.center, previous.center)],
            extend(self.size, previous.size),
            [extend(a, b) for a, b in zip(self.angles, previous.angles)],
            self.heat,
        )
        return replace(obj, soot=self.soot, pixels=self.pixels).with_stretch(self.stretch)

    def foreground(self, amount):
        z = self.center[2]
        ratio = ONE + (min(F(550.0), z) / z - ONE) * F(amount)
        obj = Object.new(
            self.icon, [v * ratio for v in self.center], self.size * ratio, self.angles, self.heat
        )
        return replace(obj, soot=self.soot, pixels=self.pixels).with_stretch(self.stretch)

    def uniforms(self, atlas):
        """The shader uniforms of this pose."""
        x, y, _, _ = self.bounds
        return {
            "uAtlas": atlas,
            "uOrigin": (float(x), float(y)),
            "uCenter": tuple(float(v) for v in self.center),
            "uRight": tuple(float(v) for v in self.right),
            "uDown": tuple(float(v) for v in self.down),
            "uSize": float(self.size),
            "uStretch": tuple(float(v) for v in self.stretch),
            "uCell": (float(self.icon % 4 * 64), float(self.icon // 4 * 64)),
            "uHeat": float(self.heat),
            "uSoot": float(self.soot),
            "uPixels": float(self.pixels),
        }


def by_depth(objects):
    return sorted(objects, key=lambda o: o.center[2], reverse=True)


def hero(icon, x, y, size, time):
    time = F(time)
    return Object.new(
        icon,
        [F(x) - F(720.0), F(y) - F(540.0), F(1250.0)],
        size,
        [
            sin(time * F(6.0) + F(0.4)) * F(0.8),
            F(0.15) * cos(time * F(4.0)),
            F(-0.10) + sin(time * F(2.7)) * F(0.25),
        ],
        0.0,
    )


def frame_value(timeline, index, global_index):
    return F(ff.Frame(index, global_index, 24).animate(timeline))


def ring_excursion(frames, heroes, schedule, keep_spinning):
    """Replace one ring slot's occupant with a complete excursion, including the feature hold."""
    s = schedule
    smooth = Easing.cubic_bezier(0.42, 0.0, 0.58, 1.0)
    pull = ff.timeline(((0.0, float(F(s.arrival - s.departure) / F(24.0))), 0.0, 1.0, smooth))
    rejoin = ff.timeline(
        ((0.0, float(F(s.return_end - s.return_start) / F(24.0))), 0.0, 1.0, smooth)
    )
    original = [pose.foreground(1.0) for pose in heroes]
    target = original[s.arrival - s.start]
    icon = target.icon
    end = s.start + len(heroes)
    destination = next((o for o in frames[s.return_end] if o.icon == icon), None)
    if destination is None:
        return
    roll_offset = ZERO
    if keep_spinning:
        turns = F(
            math.ceil((original[s.return_start - s.start].angles[2] - destination.angles[2]) / TAU)
        )
        roll_offset = turns * TAU
    for index in range(s.departure, min(s.return_end + 1, len(frames))):
        objects = frames[index]
        position = next((k for k, o in enumerate(objects) if o.icon == icon), None)
        if position is None:
            continue
        slot = objects[position]
        if index <= s.arrival:
            pose = slot.handoff(target, frame_value(pull, index - s.departure, index), 90.0)
        elif index < s.return_start:
            pose = original[index - s.start]
        else:
            if index < end:
                source = original[index - s.start]
            else:
                source = original[-1].continued(original[-2], F(index + 1 - end))
            angles = (*slot.angles[:2], slot.angles[2] + roll_offset)
            slot = replace(slot, angles=angles)
            pose = source.handoff(slot, frame_value(rejoin, index - s.return_start, index), -55.0)
        objects[position] = pose
        if s.start <= index < end:
            heroes[index - s.start] = pose
        frames[index] = by_depth(objects)


TARGETS = (
    (0.0, -420.0), (150.0, -100.0), (420.0, -280.0), (350.0, 140.0), (530.0, 100.0),
    (520.0, 340.0), (-80.0, 30.0), (-360.0, 350.0), (-480.0, -130.0), (-360.0, -50.0),
    (-240.0, 70.0), (180.0, 200.0),
)  # fmt: skip
ORDER = (10, 7, 0, 6, 11, 9, 3, 2, 1, 4, 8, 5)
OPENING_POSITIONS = ((735.0, 351.0), (1060.0, 348.0), (960.0, 665.0), (1120.0, 869.0))


def opening_pixels(index):
    if 48 <= index <= 54:
        return F(16.0)
    if 75 <= index <= 77:
        return F(12.0)
    if 78 <= index <= 81:
        return F(6.0)
    if 82 <= index <= 84:
        return F(10.0)
    return F(32.0)


def base_choreography():
    tilt = ff.timeline(
        ((6.541667, 7.291667), 0.34, 0.63, Easing.cubic_bezier(0.65, 0.0, 0.35, 1.0)),
        ((7.291667, 7.833333), 0.63, 0.50, Easing.EASE_IN_OUT),
        ((7.833333, 8.333333), 0.50, 0.48, Easing.EASE_IN_OUT),
        ((11.916667, 12.5), 0.48, 0.98, Easing.cubic_bezier(0.16, 1.0, 0.3, 1.0)),
    )
    explode = ff.timeline(((12.583333, 13.0), 0.0, 1.0, Easing.cubic_bezier(0.16, 1.0, 0.3, 1.0)))
    front_angle = F(1.95)
    departure_rotation = front_angle + PI * F(0.5) - F(2.0) * TAU / F(12.0)
    scatter_rotation = departure_rotation + (F(302.0) - F(190.0)) / F(24.0)
    spin = ff.timeline(
        (
            (float(F(153.0) / F(24.0)), float(F(302.0) / F(24.0))),
            float(departure_rotation + (F(153.0) - F(190.0)) / F(24.0)),
            float(scatter_rotation),
            Easing.LINEAR,
        )
    )
    radius = F(355.0)
    frames = []
    for index in range(489):
        objects = []
        if 48 <= index < 93:
            local = F(index - 48)
            for i, icon in enumerate((7, 1, 11, 0)):
                phase = local * F(0.11) + F(i) * F(2.3)
                x = F(OPENING_POSITIONS[i][0]) + sin(phase) * F(15.0)
                y = F(OPENING_POSITIONS[i][1]) + cos(phase * F(0.8)) * F(13.0)
                obj = Object.new(
                    icon,
                    [x - F(720.0), y - F(540.0), F(1250.0)],
                    104.0,
                    [sin(phase * F(0.82)) * F(0.68), F(0.12), sin(phase) * F(0.16)],
                    0.0,
                )
                objects.append(replace(obj, pixels=opening_pixels(index)))
        elif 153 <= index < 331:
            frame = ff.Frame(index, index, 24)
            t = F(frame.seconds)
            opened = F(frame.animate(explode))
            plane = F(frame.animate(tilt))
            rotation = F(frame.animate(spin))
            for i, icon in enumerate(ORDER):
                fi = F(i)
                a = fi * TAU / F(12.0) + rotation - PI * F(0.5)
                s, c = sin(a), cos(a)
                x = c * radius
                y = s * radius * plane
                z = F(1250.0) - s * F(600.0) * F(math.sqrt(ONE - plane * plane))
                if opened > 0:
                    a0 = fi * TAU / F(12.0) + scatter_rotation - PI * F(0.5)
                    drift = max(t - F(13.0), ZERO)
                    tx, ty = F(TARGETS[i][0]), F(TARGETS[i][1])
                    x = cos(a0) * radius * (ONE - opened) + tx * opened + drift * F(45.0) * sin(a0)
                    y = (
                        sin(a0) * radius * F(0.98) * (ONE - opened)
                        + ty * opened
                        + drift * F(32.0) * cos(a0)
                    )
                    z = F(1250.0) + opened * sin(fi * F(3.7)) * F(140.0)
                roll = sin(t * F(0.9) + fi) * F(0.12) + opened * (t - F(12.58)) * (fi - F(5.0)) * F(
                    0.17
                )
                yaw = sin(t * F(1.05) + fi * F(1.7)) * F(0.35) + opened * (t - F(12.58)) * F(0.75)
                if index < 157:
                    heat = ONE - F(index - 153) * F(0.14)
                elif icon in (3, 5):
                    heat = max(sin(t * F(3.0) + fi) - F(0.85), ZERO) * F(4.0)
                else:
                    heat = ZERO
                objects.append(
                    Object.new(
                        icon, [x, y, z], F(195.0) - opened * F(35.0), [yaw, F(0.1), roll], heat
                    )
                )
        frames.append(by_depth(objects))
    return frames


@dataclass(frozen=True)
class Impact:
    at: int
    position: tuple
    direction: tuple
    icon: int
    approach: tuple


CONTACTS = (
    (172, (1045.0, 592.0), (0.65, 0.6)),
    (177, (767.0, 659.0), (0.0, 1.0)),
    (182, (425.0, 671.0), (-0.75, 0.65)),
    (188, (340.0, 487.0), (-0.91, -0.41)),
    (312, (1080.0, 575.0), (0.45, 0.9)),
    (318, (400.0, 878.0), (-0.9, -0.1)),
)


def choreography():
    """Object poses of each of the 489 frames and the impacts that hit them."""
    frames = base_choreography()
    impacts = []
    for at, desired, direction in CONTACTS:
        dx, dy = F(desired[0]), F(desired[1])

        def distance(o, dx=dx, dy=dy):
            x = F(720.0) + o.center[0] * F(1250.0) / o.center[2]
            y = F(540.0) + o.center[1] * F(1250.0) / o.center[2]
            return (x - dx) * (x - dx) + (y - dy) * (y - dy)

        candidates = [o for o in frames[at] if not impacts or impacts[-1].icon != o.icon]
        if not candidates:
            continue
        nearest = min(candidates, key=distance)
        impacts.append(
            Impact(
                at,
                (dx, dy),
                (F(direction[0]), F(direction[1])),
                nearest.icon,
                (
                    (dx - F(720.0)) * nearest.center[2] / F(1250.0) - nearest.center[0],
                    (dy - F(540.0)) * nearest.center[2] / F(1250.0) - nearest.center[1],
                ),
            )
        )
    response = ff.timeline(
        ((0.0, 0.083333), 0.0, 1.0, Easing.EASE_OUT),
        (0.083333, 1.0, 0.0, Easing.spring(1.0, 190.0, 14.0)),
    )
    approach = ff.timeline(
        ((0.0, 0.125), 0.0, 1.0, Easing.EASE_IN_OUT),
        ((0.125, 0.75), 1.0, 0.0, Easing.EASE_OUT),
    )
    for index, objects in enumerate(frames):
        updated = []
        for obj in objects:
            center = list(obj.center)
            angles = list(obj.angles)
            heat = obj.heat
            soot = ZERO
            for hit in impacts:
                if hit.icon != obj.icon or index + 3 < hit.at or index > hit.at + 25:
                    continue
                arrive = frame_value(approach, index + 3 - hit.at, index)
                center[0] += hit.approach[0] * arrive
                center[1] += hit.approach[1] * arrive
                if index < hit.at:
                    continue
                elapsed = index - hit.at
                kick = frame_value(response, elapsed, index)
                center[0] += hit.direction[0] * F(98.0) * kick
                center[1] += hit.direction[1] * F(72.0) * kick
                center[2] -= F(85.0) * kick
                angles[0] += kick * F(0.84)
                angles[2] += kick * hit.direction[0] * F(0.43)
                e = F(elapsed)
                heat = max(heat, max(ONE - e / F(5.0), ZERO) * F(0.83))
                soot = max(
                    soot,
                    min(max((e - F(3.0)) / F(4.0), ZERO), ONE)
                    * max(ONE - max(e - F(11.0), ZERO) / F(12.0), ZERO)
                    * F(0.92),
                )
            new = Object.new(obj.icon, center, obj.size, angles, heat)
            updated.append(replace(new, soot=soot, pixels=obj.pixels))
        frames[index] = by_depth(updated)
    return frames, impacts


@dataclass
class Exposure:
    object: Object
    title_opacity: float


def build_exposures(feeling):
    arrival = ff.timeline(((0.0, 0.208333), 0.0, 1.0, Easing.cubic_bezier(0.12, 0.9, 0.22, 1.0)))
    push = ff.timeline(
        ((0.208333, 0.583333), 0.0, 0.25, Easing.LINEAR),
        ((0.583333, 0.875), 0.25, 1.0, Easing.EASE_IN),
    )
    yaw = ff.timeline(
        ((0.0, 0.166667), -0.85, -0.28, Easing.cubic_bezier(0.16, 1.0, 0.3, 1.0)),
        ((0.166667, 0.833333), -0.28, 0.40, Easing.EASE_IN_OUT),
    )
    spin = ff.timeline(((0.0, 0.875), -0.38, 2.95, Easing.LINEAR))
    exposures = []
    for index in range(21 if feeling else 20):
        frame = ff.Frame(index, index, 24)
        entry = F(frame.animate(arrival))
        pushed = F(frame.animate(push))
        turned = F(frame.animate(yaw))
        obj = Object.new(
            4 if feeling else 0,
            [
                F(442.0) - F(720.0) - (ONE - entry) * F(74.0),
                F(-9.0) + (ONE - entry) * F(68.0),
                F(1250.0) - pushed * F(70.0),
            ],
            (F(555.0) if feeling else F(530.0)) * (F(0.82) + entry * F(0.18)),
            [
                turned * F(0.6) if feeling else turned,
                F(0.16) - pushed * F(0.20),
                F(frame.animate(spin))
                if feeling
                else F(-0.15) + entry * F(0.05) + pushed * F(0.13),
            ],
            0.0,
        )
        exposures.append(Exposure(obj, 1.0))
    return exposures


def motion_exposures(camera_pose):
    arrive = ff.timeline(((0.0, 0.166667), 0.0, 1.0, Easing.cubic_bezier(0.12, 0.9, 0.22, 1.0)))
    normal, tall, flat = camera_pose[5], camera_pose[12], camera_pose[17]
    smooth = Easing.cubic_bezier(0.42, 0.0, 0.58, 1.0)
    deformation = [
        ff.timeline(
            ((5.0 / 24.0, 10.0 / 24.0), normal[axis], tall[axis], smooth),
            ((10.0 / 24.0, 15.0 / 24.0), tall[axis], flat[axis], smooth),
        )
        for axis in range(3)
    ]
    exposures = []
    for index in range(16):
        frame = ff.Frame(index, index, 24)
        entry = F(frame.animate(arrive))
        sx, sy, roll = (F(frame.animate(curve)) for curve in deformation)
        wide = min(max((sx - ONE) / F(1.2), ZERO), ONE)
        obj = Object.new(
            5,
            [
                F(-296.0) + wide * F(25.0) - (ONE - entry) * F(60.0),
                F(-8.0) + (ONE - entry) * F(74.0),
                F(1250.0),
            ],
            F(470.0) * (F(0.83) + entry * F(0.17)),
            [F(0.10), F(0.035), roll],
            0.0,
        ).with_stretch((sx, sy))
        exposures.append(Exposure(obj, 1.0))
    return exposures


def heroes(frames, camera_pose):
    """Feature exposures of the code, motion and feeling cards; moves their ring slots."""
    cards = {
        "code": build_exposures(False),
        "feeling": build_exposures(True),
        "motion": motion_exposures(camera_pose),
    }
    for (card, keep_spinning), s in zip(
        (("code", False), ("motion", False), ("feeling", True)), EXCURSIONS
    ):
        exposures = cards[card]
        poses = [exposure.object for exposure in exposures]
        ring_excursion(frames, poses, s, keep_spinning)
        arrival = F(s.arrival - s.start) / F(24.0)
        leave = F(s.return_start - s.start) / F(24.0)
        caption = ff.timeline(
            ((float(arrival - F(2.0) / F(24.0)), float(arrival)), 0.0, 1.0, Easing.EASE_OUT),
            ((float(leave), float(leave + F(3.0) / F(24.0))), 1.0, 0.0, Easing.EASE_IN_OUT),
        )
        for index, (exposure, pose) in enumerate(zip(exposures, poses)):
            exposure.object = pose
            exposure.title_opacity = ff.Frame(index, s.start + index, 24).animate(caption)
    return cards

"""Port of story.rs: the performance of the arm, built once."""

from bisect import bisect_right

import arm
import numpy as np
from arm import OPEN, joints, looking, solve, tool_down
from fframes import three_d as td
from fmath import ONE, TAU, ZERO, F, clamp, sin, smoothstep, sqrt

Vec3, Quat, Mat4 = td.Vec3, td.Quat, td.Mat4
RACK_Z = F(-1.3)
WORD_Z = F(1.25)

GUILTY_CAMERA = Vec3(0.55, 1.32, 3.25)
FINAL_CAMERA = Vec3(0.0, 1.25, 7.2)
HELLO_CAMERA = Vec3(3.2, 1.25, 4.9)

# Eases: (kind, overshoot).
SMOOTH, OUT, IN = ("smooth", 0.0), ("out", 0.0), ("in", 0.0)


def out_back(s):
    return ("out_back", F(s))


def in_back(s):
    return ("in_back", F(s))


def ease(e, x):
    kind, s = e
    x = clamp(x, 0.0, 1.0)
    if kind == "smooth":
        return x * x * x * (x * (x * F(6.0) - F(15.0)) + F(10.0))
    if kind == "out":
        y = ONE - x
        return ONE - y * y * y
    if kind == "in":
        return x * x * x
    y = x - ONE
    if kind == "out_back":
        return ONE + (s + ONE) * (y * y * y) + s * (y * y)
    return (s + ONE) * x * x * x - s * x * x


IDLE = [
    (0.035, 1.3, 0.0),
    (0.03, 1.7, 1.0),
    (0.04, 2.1, 2.0),
    (0.05, 0.9, 3.0),
    (0.07, 1.1, 0.5),
    (0.04, 0.7, 1.5),
]
IDLE = [(F(a), F(f), F(p)) for a, f, p in IDLE]


class Key:
    __slots__ = ("alive", "ease", "gap", "q", "t")

    def __init__(self, t, q, gap, e, alive):
        self.t, self.q, self.gap, self.ease, self.alive = F(t), q, F(gap), e, F(alive)


class Track:
    """The keys of the arm, in time order."""

    def __init__(self, keys):
        self.keys = keys
        self.times = [float(k.t) for k in keys]

    def push(self, key):
        self.keys.append(key)
        self.times.append(float(key.t))

    def sample(self, t):
        """(joints, gap) at `t`, with the idle motion."""
        t = F(t)
        keys = self.keys
        k = bisect_right(self.times, t)
        if k == 0:
            f = keys[0]
            q, gap, alive = f.q, f.gap, f.alive
        elif k >= len(keys):
            last = keys[-1]
            q, gap, alive = last.q, last.gap, last.alive
        else:
            a, b = keys[k - 1], keys[k]
            s = (t - a.t) / max(b.t - a.t, F(1e-6))
            x = ease(b.ease, s)
            linear = clamp(s, 0.0, 1.0)
            q = a.q + (b.q - a.q) * x
            gap = a.gap + (b.gap - a.gap) * x
            alive = a.alive + (b.alive - a.alive) * linear
        idle = np.array(
            [amp * sin(t * f + p) if p else amp * sin(t * f) for amp, f, p in IDLE],
            dtype=np.float32,
        )
        return q + idle * alive, gap


class Fall:
    """A precomputed tumble of a dropped letter."""

    RATE = F(480.0)

    def __init__(self, start, frames, impacts):
        self.start, self.frames, self.impacts = F(start), frames, impacts
        self.srt = [m.to_scale_rotation_translation() for m in frames]

    def at(self, t):
        x = max((F(t) - self.start) * self.RATE, ZERO)
        n = len(self.frames)
        i = min(int(x), n - 1)
        j = min(i + 1, n - 1)
        f = clamp(x - F(i), 0.0, 1.0)
        sa, ra, ta = self.srt[i]
        _, rb, tb = self.srt[j]
        return Mat4.from_scale_rotation_translation(sa, ra.slerp(rb, f), ta.lerp(tb, f))

    def end(self):
        return self.start + F(len(self.frames)) / self.RATE


# Phases of a letter: ("still", Mat4), ("carried", Mat4) or ("falling", fall index).


class Letter:
    def __init__(self, geometry, bounds, rack, slot, top, stem):
        self.geometry, self.bounds = geometry, bounds
        self.center = (bounds[0] + bounds[1]) * 0.5
        self.rack, self.slot, self.top, self.stem = rack, slot, top, stem
        self.phases = [(F(0.0), ("still", rack))]
        self.starts = [0.0]

    def push(self, t, phase):
        self.phases.append((F(t), phase))
        self.starts.append(float(F(t)))

    def phase(self, t):
        i = max(bisect_right(self.starts, F(t)) - 1, 0)
        return self.phases[i][1]

    def placed(self, t) -> bool:
        kind, m = self.phase(t)
        return kind == "still" and m is self.slot

    def world(self, t, track, falls) -> td.Mat4:
        kind, value = self.phase(t)
        if kind == "still":
            return value
        if kind == "carried":
            return arm.tip(track.sample(t)[0]) * value
        return falls[value].at(t)


class Director:
    """Adds the keys one after the other. The last key is the hint for the next solve."""

    def __init__(self, first: Key):
        self.track = Track([first])
        self.t = F(0.0)

    def last(self) -> Key:
        return self.track.keys[-1]

    def key(self, dt, q, gap, e, alive):
        self.t += F(dt)
        self.track.push(Key(self.t, q, gap, e, alive))

    def pose(self, dt, tip, rotation, gap, e, alive):
        q = solve(tip, rotation, self.last().q)
        self.key(dt, q, gap, e, alive)
        return q

    def look(self, dt, at, target, roll, e, alive):
        return self.pose(dt, at, looking(target - at, roll), self.last().gap, e, alive)

    def hold(self, dt, alive):
        k = self.last()
        self.key(dt, k.q, k.gap, SMOOTH, alive)

    def gap(self, dt, gap):
        k = self.last()
        self.key(dt, k.q, gap, OUT, 0.0)

    def joints(self, dt, offsets, e, alive):
        k = self.last()
        self.key(dt, k.q + np.array(offsets, dtype=np.float32), k.gap, e, alive)


def spans(shapes, y):
    """The inside spans of a glyph at height `y`, by the even-odd rule."""
    y = F(y)
    xs = []
    for outer, holes in shapes:
        for contour in [outer, *holes]:
            n = len(contour)
            for i in range(n):
                (ax, ay), (bx, by) = contour[i], contour[(i + 1) % n]
                ax, ay, bx, by = F(ax), F(ay), F(bx), F(by)
                if (ay > y) != (by > y):
                    xs.append(ax + (y - ay) * (bx - ax) / (by - ay))
    xs.sort()
    return [(xs[i], xs[i + 1]) for i in range(0, len(xs) - 1, 2)]


def corners(bounds):
    lo, hi = bounds
    return [Vec3(x, y, z) for x in (lo.x, hi.x) for y in (lo.y, hi.y) for z in (lo.z, hi.z)]


def simulate_fall(start, m0, v0, w0, bounds) -> Fall:
    """The tumble of a rigid letter: gravity and bounces that lose energy, then it settles."""
    start = F(start)
    cs = corners(bounds)
    _, rot, pos = m0.to_scale_rotation_translation()
    v, w = v0, w0
    dt = F(1.0) / Fall.RATE
    g = F(9.81) * dt
    frames, impacts = [], []
    t = F(0.0)
    settling = None
    while True:
        frames.append(Mat4.from_rotation_translation(rot, pos))
        if settling is not None:
            since, from_rot, from_pos = settling
            x = min((t - since) / F(0.45), ONE)
            up = rot * Vec3.Y
            heading = Vec3(up.x, 0.0, up.z).normalize_or(Vec3.NEG_Z)
            target_rot = Quat.from_cols(heading.cross(Vec3.Y).normalize(), heading, Vec3.Y)
            y = ONE - x
            e = ONE - y * y * y
            rot = from_rot.slerp(target_rot, e)
            slide = from_pos + v * 0.12 * e
            lowest = min(F((rot * c).y) for c in cs)
            pos = Vec3(slide.x, -lowest + (ONE - e) * F(0.03) * abs(sin(x * F(20.0))), slide.z)
            if x >= ONE:
                frames.append(Mat4.from_rotation_translation(rot, pos))
                break
        else:
            v = v.with_y(F(v.y) - g)
            pos = pos + v * dt
            rot = (Quat.from_scaled_axis(w * dt) * rot).normalize()
            lowest = min(F((rot * c + pos).y) for c in cs)
            if lowest < 0.0 and v.y < 0.0:
                pos = pos.with_y(F(pos.y) - lowest)
                vy = F(v.y)
                impacts.append((start + t, -vy))
                v = Vec3(F(v.x) * F(0.55), -vy * F(0.32), F(v.z) * F(0.55))
                w = w * 0.45 + Vec3(v.z, 0.0, -F(v.x)) * 3.0
                if len(impacts) >= 2 or F(v.y) < F(0.7):
                    settling = (t, rot, pos)
        t += dt
        if t > F(4.0):
            break
    return Fall(start, frames, impacts)


class Sound:
    LIGHTS_ON, BOOT, BLINK, CURIOUS, HAPPY, GRIP, PLACE, WHOOSH = range(8)
    SCRATCH, UH_OH, SIGH, PAT, PROUD, TA_DA = range(8, 14)
    CLATTER = 14  # with a speed: (CLATTER, speed)


class Beats:
    lights = wake = work = drop = recover = finish = tada = end = F(0.0)


def center_x(bounds):
    return (bounds[0] + bounds[1]) * 0.5


def midpoint(a, b):
    """Rust `f32::midpoint` on 64-bit targets."""
    return F((float(a) + float(b)) / 2.0)


class Story:
    """The whole performance, built once."""

    def __init__(self, font: bytes, word: str):
        size, depth, tracking = F(0.68), F(0.1), F(0.035)
        glyphs = td.Geometry.text_glyphs(font, word, size, depth, 0.012)
        shapes = td.Geometry.text_shapes(font, word, size, 0.0)
        count = len(glyphs)
        last = glyphs[-1]
        width = F(last.origin[0]) + F(last.advance) + tracking * F(count - 1)
        rack_order = [4, 1, 6, 0, 3, 5, 2]
        letters = []
        for i, (glyph, outline) in enumerate(zip(glyphs, shapes)):
            bounds = glyph.geometry.bounds()
            lo, hi = bounds
            top_y = F(hi.y)
            p = np.frombuffer(glyph.geometry.positions(), dtype=np.float32).reshape(-1, 3)
            near = p[p[:, 1] > top_y - F(0.03), 0]
            total = np.cumsum(near, dtype=np.float32)[-1] if len(near) else F(0.0)
            grip_x = total / F(max(len(near), 1))
            stem_y = F(0.32) * (F(hi.y) - F(lo.y)) + F(lo.y)
            found = spans(outline[3], stem_y)
            cx = F(center_x(bounds).x)
            if found:
                a, b = found[-1]
                stem = (Vec3(midpoint(a, b), stem_y, 0.0), (b - a) * F(0.5))
            else:
                stem = (Vec3(cx, stem_y, 0.0), F(0.05))
            slot_index = F(rack_order.index(i) if i in rack_order else i)
            rack_x = F(-1.56) + slot_index * F(0.52) - cx
            rack = Mat4.from_translation((rack_x, 0.02, RACK_Z))
            slot = Mat4.from_translation(
                (F(glyph.origin[0]) + F(i) * tracking - width * F(0.5), 0.0, WORD_Z)
            )
            top = Vec3(grip_x, top_y - F(0.035), 0.0)
            letters.append(Letter(glyph.geometry, bounds, rack, slot, top, stem))

        sounds, log, blinks, falls = [], [], [], []
        beats = Beats()

        def say(t, text, alert=False):
            log.append((F(t), text, alert))

        # Asleep: the eye looks at the floor.
        asleep = solve(
            Vec3(0.05, 0.24, 0.95),
            looking(Vec3(0.05, -1.0, 0.45), 0.25),
            joints(0.0, 0.4, 1.0, 0.0, 0.8, 0.0),
        )
        d = Director(Key(0.0, asleep, 0.03, SMOOTH, 0.15))
        beats.wake = F(0.8)
        sounds.append((F(0.75), Sound.BOOT))
        say(0.8, "BOOT  OD-ARM 7.2 ...... OK")
        d.hold(2.0, 0.15)
        # It wakes up and stretches.
        d.look(0.9, Vec3(0.1, 0.62, 0.95), Vec3(0.2, 0.0, 2.2), 0.15, in_back(0.4), 0.3)
        d.joints(0.35, [0.0, 0.08, 0.1, 0.0, 0.25, 0.0], SMOOTH, 0.2)
        blinks.append(d.t + F(0.1))
        sounds.append((d.t + F(0.1), Sound.BLINK))
        d.look(0.75, Vec3(0.0, 2.15, 0.55), Vec3(0.0, 3.5, 1.4), 0.0, out_back(1.6), 0.0)
        beats.lights = d.t - F(0.2)
        sounds.append((beats.lights, Sound.LIGHTS_ON))
        d.gap(0.2, OPEN)
        d.look(0.55, Vec3(0.25, 1.35, 1.05), HELLO_CAMERA, 0.35, out_back(1.2), 0.5)
        sounds.append((d.t - F(0.2), Sound.CURIOUS))
        say(d.t - F(0.2), "VISION ONLINE  FACE DETECTED")
        d.look(0.25, Vec3(0.25, 1.35, 1.05), HELLO_CAMERA, -0.25, SMOOTH, 0.4)
        blinks.append(d.t)
        sounds.append((d.t, Sound.BLINK))
        d.hold(0.3, 0.6)
        rack_center = Vec3(0.0, 0.3, RACK_Z)
        d.look(0.45, Vec3(-0.2, 1.4, -0.35), rack_center, 0.0, SMOOTH, 0.3)
        d.look(0.2, Vec3(0.2, 1.4, 0.7), HELLO_CAMERA, 0.2, OUT, 0.2)
        d.look(0.3, Vec3(-0.15, 1.45, -0.4), rack_center, -0.1, out_back(1.3), 0.3)
        sounds.append((d.t, Sound.HAPPY))
        say(d.t, 'TASK  SPELL "fframes"')
        d.hold(0.25, 0.5)
        beats.work = d.t

        carry = F(0.68)
        rot = tool_down(Vec3.Z)
        up = Vec3.Y

        def pick_place(i, pace, flourish):
            pace = F(pace)
            letter = letters[i]
            grab = letter.rack.transform_point3(letter.top)
            place = letter.slot.transform_point3(letter.top)
            d.pose(F(0.62) * pace, grab + up * carry, rot, OPEN, SMOOTH, 0.0)
            d.pose(F(0.24) * pace, grab, rot, OPEN, SMOOTH, 0.0)
            d.gap(F(0.12) * pace, 0.057)
            t_grab = d.t - F(0.04) * pace
            sounds.append((t_grab - F(0.05), Sound.GRIP))
            tip = arm.tip(d.track.sample(t_grab)[0])
            letters[i].push(t_grab, ("carried", tip.inverse() * letters[i].rack))
            d.pose(F(0.24) * pace, grab + up * carry, rot, 0.057, out_back(0.6), 0.0)
            sounds.append((d.t, Sound.WHOOSH))
            d.pose(
                F(0.62) * pace,
                place + up * carry,
                rot,
                0.057,
                out_back(1.0) if flourish else SMOOTH,
                0.0,
            )
            d.pose(F(0.24) * pace, place, rot, 0.057, IN, 0.0)
            t_place = d.t
            letters[i].push(t_place, ("still", letters[i].slot))
            sounds.append((t_place, Sound.PLACE))
            d.gap(F(0.1) * pace, OPEN)
            d.pose(F(0.22) * pace, place + up * F(0.35), rot, OPEN, OUT, 0.2)
            return t_place

        say(pick_place(0, 1.05, False), "PLACE  f ............. OK")
        say(pick_place(1, 0.8, False), "PLACE  f ............. OK")
        say(pick_place(2, 0.68, True), "PLACE  r ............. OK")
        d.joints(0.12, [0.0, 0.0, 0.0, 0.0, 0.0, 0.5], OUT, 0.0)
        d.joints(0.12, [0.0, 0.0, 0.0, 0.0, 0.0, -1.0], SMOOTH, 0.0)
        d.joints(0.14, [0.0, 0.0, 0.0, 0.0, 0.0, 0.5], out_back(1.0), 0.0)
        sounds.append((d.t, Sound.HAPPY))

        # The show-off: it swings "a" high and lets it go.
        a = 3
        letter = letters[a]
        grab = letter.rack.transform_point3(letter.top)
        d.pose(0.5, grab + up * carry, rot, OPEN, SMOOTH, 0.0)
        d.pose(0.2, grab, rot, OPEN, SMOOTH, 0.0)
        d.gap(0.1, 0.057)
        t_grab = d.t - F(0.03)
        sounds.append((t_grab - F(0.05), Sound.GRIP))
        rel = arm.tip(d.track.sample(t_grab)[0]).inverse() * letter.rack
        letter.push(t_grab, ("carried", rel))
        say(d.t, "PLACE  a  WITH STYLE")
        high = grab + Vec3(0.0, 1.05, 0.25)
        d.pose(0.3, high, rot, 0.057, out_back(0.8), 0.0)
        d.joints(0.25, [0.12, -0.1, -0.1, 0.0, 0.0, -0.6], SMOOTH, 0.0)
        swing_from = d.t
        target_above = letter.slot.transform_point3(letter.top) + up * carry
        q = solve(target_above + Vec3(0.25, 0.25, 0.0), rot, d.last().q).copy()
        q[5] += TAU * F(1.5)
        d.key(0.95, q, 0.057, in_back(0.25), 0.0)
        sounds.append((swing_from + F(0.15), Sound.WHOOSH))

        t_drop = swing_from + F(0.62)
        beats.drop = t_drop
        dt = F(1.0) / F(240.0)

        def at(t):
            return arm.tip(d.track.sample(t)[0]) * rel

        m0, ma, mb = at(t_drop), at(t_drop - dt), at(t_drop + dt)
        v0 = (mb.w_axis - ma.w_axis) / (F(2.0) * dt)
        _, ra, _ = ma.to_scale_rotation_translation()
        _, rb, _ = mb.to_scale_rotation_translation()
        axis, angle = (rb * ra.inverse()).to_axis_angle()
        w0 = (axis * angle) / (F(2.0) * dt)
        # Aim the throw at the landing spot.
        landing = Vec3(1.3, 0.0, 0.4)
        p0 = m0.w_axis
        vy = clamp(v0.y, -0.5, 1.5)
        flight = (vy + sqrt(vy * vy + F(2.0) * F(9.81) * F(p0.y))) / F(9.81)
        reach = (landing - p0) * 0.85 / flight
        v0 = Vec3(reach.x, vy, reach.z)
        fall = simulate_fall(t_drop, m0, v0, w0 * 0.6, letter.bounds)
        lying = fall.frames[-1]
        for t, speed in fall.impacts:
            sounds.append((t, (Sound.CLATTER, speed)))
        fall_end = fall.end()
        falls.append(fall)
        letter.push(t_drop, ("falling", 0))
        letter.push(fall_end, ("still", lying))
        sounds.append((t_drop, Sound.SCRATCH))
        say(t_drop + F(0.05), "ERR 0x7A  GRIP LOST", True)
        sounds.append((t_drop - F(0.05), Sound.GRIP))

        # It looks at the letter, then at the camera.
        d.gap(0.15, OPEN)
        d.hold(0.55, 0.0)
        letter_at = lying.transform_point3(letter.center)
        head = d.last()
        head_pos = arm.tip(head.q).w_axis
        d.look(0.8, head_pos + Vec3(0.0, -0.1, 0.0), letter_at, 0.2, SMOOTH, 0.1)
        sounds.append((d.t - F(0.1), Sound.UH_OH))
        say(d.t, "STATUS  NOBODY SAW THAT")
        d.hold(0.5, 0.2)
        guilty = Vec3(0.3, 1.3, 1.25)
        d.look(0.7, guilty, GUILTY_CAMERA, -0.25, SMOOTH, 0.0)
        blinks.append(d.t + F(0.5))
        sounds.append((d.t + F(0.5), Sound.BLINK))
        d.hold(1.0, 0.3)
        d.look(0.16, guilty, letter_at, 0.1, OUT, 0.0)
        d.hold(0.18, 0.0)
        d.look(0.16, guilty, GUILTY_CAMERA, -0.2, OUT, 0.0)
        d.hold(0.35, 0.2)
        blinks.append(d.t - F(0.1))
        say(d.t, "SOMEBODY SAW THAT", True)
        d.joints(0.75, [0.0, 0.18, 0.28, 0.0, 0.45, 0.0], SMOOTH, 0.0)
        sounds.append((d.t - F(0.6), Sound.SIGH))
        d.hold(0.35, 0.2)
        beats.recover = d.t

        # It picks the letter up by its stem and puts it in its slot.
        say(d.t, "RETRY  a  (CAREFULLY)")
        stem_center, stem_half = letter.stem
        stem_world = lying.transform_point3(stem_center)
        _, lying_rot, _ = lying.to_scale_rotation_translation()
        grab_rot = lying_rot * arm.frame(Vec3.X, Vec3.NEG_Z)
        d.look(0.75, stem_world + Vec3(0.0, 0.55, 0.25), stem_world, 0.3, SMOOTH, 0.1)
        d.hold(0.3, 0.2)
        d.pose(0.6, stem_world + up * 0.3, grab_rot, OPEN, SMOOTH, 0.0)
        d.pose(0.45, stem_world, grab_rot, OPEN, SMOOTH, 0.0)
        stem_gap = stem_half + F(0.007)
        d.gap(0.2, stem_gap)
        t_regrab = d.t - F(0.05)
        sounds.append((t_regrab - F(0.05), Sound.GRIP))
        rel2 = arm.tip(d.track.sample(t_regrab)[0]).inverse() * lying
        letter.push(t_regrab, ("carried", rel2))
        d.pose(0.55, stem_world + up * 0.4, grab_rot, stem_gap, SMOOTH, 0.0)
        slot_tip = letter.slot * rel2.inverse()
        _, slot_rot, slot_pos = slot_tip.to_scale_rotation_translation()
        d.pose(1.0, slot_pos + up * 0.35, slot_rot, stem_gap, SMOOTH, 0.0)
        d.pose(0.5, slot_pos, slot_rot, stem_gap, SMOOTH, 0.0)
        t_place = d.t
        letter.push(t_place, ("still", letter.slot))
        sounds.append((t_place, Sound.PLACE))
        say(t_place, "PLACE  a ............. OK")
        d.gap(0.12, OPEN)
        back = slot_rot * Vec3.NEG_Z
        d.pose(0.35, slot_pos + back * 0.2 + up * 0.05, slot_rot, OPEN, OUT, 0.0)
        # It pats the letter twice.
        top = letter.slot.transform_point3(letter.top)
        d.pose(0.45, top + up * 0.16, rot, 0.03, SMOOTH, 0.0)
        for _ in range(2):
            d.pose(0.1, top + up * 0.05, rot, 0.03, IN, 0.0)
            sounds.append((d.t, Sound.PAT))
            d.pose(0.14, top + up * 0.16, rot, 0.03, OUT, 0.0)
        d.joints(0.25, [0.0, -0.05, -0.05, 0.0, -0.3, 0.0], out_back(1.5), 0.3)
        sounds.append((d.t - F(0.1), Sound.HAPPY))
        beats.finish = d.t

        # The rest of the word, fast.
        for i, pace in ((4, 0.62), (5, 0.58), (6, 0.56)):
            t = pick_place(i, pace, False)
            say(
                t,
                {4: "PLACE  m ............. OK", 5: "PLACE  e ............. OK"}.get(
                    i, "PLACE  s ............. OK"
                ),
            )
        say(d.t + F(0.1), "TASK COMPLETE  1 INCIDENT")

        # It admires the word and bows.
        word_center = Vec3(0.0, 0.25, WORD_Z)
        d.look(0.7, Vec3(0.0, 1.55, 0.55), word_center, 0.0, SMOOTH, 0.3)
        d.hold(0.5, 0.5)
        d.look(0.5, Vec3(0.0, 1.5, 0.75), FINAL_CAMERA, 0.25, out_back(1.2), 0.3)
        sounds.append((d.t - F(0.1), Sound.PROUD))
        d.hold(0.35, 0.4)
        d.joints(0.45, [0.0, 0.22, 0.3, 0.0, 0.65, 0.0], SMOOTH, 0.0)
        d.hold(0.25, 0.0)
        d.joints(0.4, [0.0, -0.24, -0.32, 0.0, -0.7, 0.0], out_back(1.3), 0.2)
        beats.tada = d.t
        sounds.append((d.t, Sound.TA_DA))
        say(d.t, "HUMILITY  NOT FOUND")
        for _ in range(2):
            d.gap(0.09, 0.02)
            d.gap(0.09, OPEN)
        blinks.append(d.t + F(0.2))
        d.hold(1.7, 0.6)
        beats.end = d.t

        sounds.sort(key=lambda s: s[0])
        self.track, self.letters, self.falls = d.track, letters, falls
        self.sounds, self.log, self.blinks, self.beats, self.dropped = sounds, log, blinks, beats, a

    def lid(self, t):
        """How open the eye is: 0 closed, 1 open."""
        t = F(t)
        awake = smoothstep(self.beats.wake + F(0.6), self.beats.wake + F(1.0), t)
        blink = F(0.0)
        for b in self.blinks:
            blink = max(blink, ONE - smoothstep(0.0, 0.07, abs(t - b)))
        return awake * (ONE - blink)

"""Synthesizes the sound of FFRAMES, ASSEMBLED into `dynamic_media/` of the arm example. The
music follows the story beats, and the servo sound follows the joint speeds of the animation.

A port of `arm-soundtrack` (`examples/arm/src/bin/soundtrack.rs`): it writes the same WAV files,
byte for byte. All math is numpy float32, which rounds each step as Rust f32 does. Transcendental
functions come from `fframes.f32_math` (the libm of Rust), and the recursive parts (noise, filters,
phases, strings, reverb) run one whole buffer per call in the fframes DSP helpers.

    python examples/arm_soundtrack.py [--out DIR]
"""

import argparse
import math
import sys
from concurrent.futures import ThreadPoolExecutor
from functools import cache
from pathlib import Path

import fframes as ff
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent / "arm"))

import _media
from effects import hash_array
from fmath import F, powf, sin_cos
from story import IDLE, Story

PI = F(math.pi)
TAU = F(math.tau)

# Samples per second.
RATE = F(48_000.0)

ZERO, ONE = F(0.0), F(1.0)

# The comb filters of a reverb run at the same time. They release the GIL.
COMBS = ThreadPoolExecutor()


def buf(data: bytes) -> np.ndarray:
    return np.frombuffer(data, dtype=np.float32)


def f32(op: str, x, y=None) -> np.ndarray:
    """Rust `f32::sin`, `exp`, `tanh` or `powf` of each value, bit for bit."""
    x = x.tobytes() if isinstance(x, np.ndarray) else float(x)
    if y is not None:
        y = y.tobytes() if isinstance(y, np.ndarray) else float(y)
    return buf(ff.f32_math(op, x, y))


def fsin(x) -> np.ndarray:
    return f32("sin", x)


# ------------------------------------------------------------------ Building blocks


def noise(seed: int, n: int) -> np.ndarray:
    """White noise from a fixed seed (xorshift)."""
    return buf(ff.Noise(seed).take(n))


def biquad(kind: str, x: np.ndarray, freq, q: float) -> np.ndarray:
    """An RBJ biquad filter. `freq` is one cutoff or one per sample to sweep the filter."""
    freq = freq.tobytes() if isinstance(freq, np.ndarray) else float(freq)
    return buf(ff.biquad(kind, x.tobytes(), freq, float(q)))


def saw(freq) -> np.ndarray:
    """A band limited sawtooth (polyBLEP) for each frequency of `freq`."""
    dt = np.minimum(np.asarray(freq, dtype=np.float32) / RATE, F(0.5))
    t = before(buf(ff.phasor(dt.tobytes(), len(dt))))
    return F(2.0) * t - ONE - blep(t, dt)


def blep(t: np.ndarray, dt: np.ndarray) -> np.ndarray:
    """The polyBLEP correction near the jump of the sawtooth."""
    u = t / dt
    v = (t - ONE) / dt
    return np.where(
        t < dt, u + u - u * u - ONE, np.where(t > ONE - dt, v * v + v + v + ONE, ZERO)
    ).astype(np.float32)


def before(after: np.ndarray) -> np.ndarray:
    """The phase before each step, from the phase after it. The first phase is 0."""
    out = np.empty_like(after)
    out[0:1] = ZERO
    out[1:] = after[:-1]
    return out


def sine(freq, n: int | None = None) -> np.ndarray:
    """A sine oscillator: one frequency for `n` samples or one frequency per sample."""
    if n is None:
        return buf(ff.sine(np.asarray(freq, dtype=np.float32).tobytes(), len(freq)))
    return buf(ff.sine(float(freq), n))


def note(midi) -> np.float32:
    """The frequency of a MIDI note in Hz."""
    return F(440.0) * powf(F(2.0), (F(midi) - F(69.0)) / F(12.0))


@cache
def _exp_decay(n: int, rate: np.float32) -> np.ndarray:
    return f32("exp", -times(n) * rate)


def decay(n: int, rate) -> np.ndarray:
    """Exponential decay from `t = 0` over the first `n` samples."""
    return _exp_decay(n, F(rate))


@cache
def _attack_decay(n: int, attack: np.float32, rate: np.float32) -> np.ndarray:
    t = times(n)
    return np.where(t < attack, t / attack, f32("exp", -(t - attack) * rate)).astype(np.float32)


def attack_decay(n: int, attack, rate) -> np.ndarray:
    """A linear attack of `attack` seconds, then exponential decay."""
    return _attack_decay(n, F(attack), F(rate))


def smoothstep(e0, e1, x: np.ndarray) -> np.ndarray:
    t = np.clip((x - F(e0)) / (F(e1) - F(e0)), ZERO, ONE)
    return t * t * (F(3.0) - F(2.0) * t)


@cache
def times(n: int) -> np.ndarray:
    """`t = i / RATE` of each sample."""
    return np.arange(n).astype(np.float32) / RATE


def length_of(seconds) -> int:
    return int(F(seconds) * RATE)


def rust_round(x) -> int:
    """`f32::round`: halves round away from zero."""
    x = float(x)
    return int(math.copysign(math.floor(abs(x) + 0.5), x))


class Track:
    """A stereo buffer at `RATE`."""

    def __init__(self, seconds=None, *, l=None, r=None):
        if l is None:
            n = length_of(seconds)
            l, r = np.zeros(n, dtype=np.float32), np.zeros(n, dtype=np.float32)
        self.l, self.r = l, r

    def __len__(self) -> int:
        return len(self.l)

    def copy(self) -> "Track":
        return Track(l=self.l.copy(), r=self.r.copy())

    def add(self, start, signal: np.ndarray, gain, pan) -> None:
        """Adds a mono signal at `start` seconds. `pan` goes from -1 (left) to 1 (right) with
        equal power."""
        angle = (min(max(F(pan), F(-1.0)), ONE) + ONE) * PI / F(4.0)
        s, c = sin_cos(angle)
        gl, gr = c * F(gain), s * F(gain)
        offset = rust_round(F(start) * RATE)
        a, b = max(0, -offset), min(len(signal), len(self.l) - offset)
        if a < b:
            part = signal[a:b]
            self.l[offset + a : offset + b] += part * gl
            self.r[offset + a : offset + b] += part * gr

    def mix(self, other: "Track", gain) -> None:
        """Adds `other`, scaled by `gain`."""
        n = min(len(self), len(other))
        self.l[:n] += other.l[:n] * F(gain)
        self.r[:n] += other.r[:n] * F(gain)

    def normalize(self, peak_db) -> None:
        """Scales the track so that its peak is at `peak_db`."""
        peak = max(np.abs(self.l).max(initial=ZERO), np.abs(self.r).max(initial=ZERO))
        if peak > ZERO:
            gain = powf(F(10.0), F(peak_db) / F(20.0)) / peak
            self.l *= gain
            self.r *= gain

    def write(self, path: Path) -> None:
        """Writes a 16 bit stereo WAV file."""
        n = len(self)
        data = n * 4
        rate = int(RATE)
        header = b"".join(
            [
                b"RIFF",
                (36 + data).to_bytes(4, "little"),
                b"WAVEfmt ",
                (16).to_bytes(4, "little"),
                (1).to_bytes(2, "little"),
                (2).to_bytes(2, "little"),
                rate.to_bytes(4, "little"),
                (rate * 4).to_bytes(4, "little"),
                (4).to_bytes(2, "little"),
                (16).to_bytes(2, "little"),
                b"data",
                data.to_bytes(4, "little"),
            ]
        )
        pcm = np.empty((n, 2), dtype="<i2")
        for k, channel in enumerate((self.l, self.r)):
            pcm[:, k] = np.clip(channel, F(-1.0), ONE) * F(32767.0)
        path.write_bytes(header + pcm.tobytes())


def reverb(input: Track, room, damp, wet) -> Track:
    """A stereo reverb in the style of Freeverb."""
    combs = [1116, 1188, 1277, 1356, 1422, 1491, 1557, 1617]
    allpasses = [556, 441, 341, 225]
    out = input.copy()
    room, damp, wet = float(room), float(damp), F(wet)
    for src, dst, spread in ((input.l, out.l, 0), (input.r, out.r, 23)):
        data = src.tobytes()
        acc = np.zeros(len(src), dtype=np.float32)
        delayed = [
            COMBS.submit(ff.comb, data, (size + spread) * 48 // 44, room, damp, 0.015)
            for size in combs
        ]
        for y in delayed:
            acc += buf(y.result())
        acc_bytes = acc.tobytes()
        for size in allpasses:
            acc_bytes = ff.allpass(acc_bytes, (size + spread) * 48 // 44, 0.5)
        dst *= ONE - wet * F(0.3)
        dst += buf(acc_bytes) * wet
    return out


def mono(signal: np.ndarray, peak_db) -> Track:
    """A centered track from a mono signal, normalized to `peak_db`."""
    t = Track(F(len(signal)) / RATE)
    t.add(0.0, signal, 1.0, 0.0)
    t.normalize(peak_db)
    return t


# ------------------------------------------------------------------ Instruments


def modal(freq, partials, length, mallet, seed: int) -> np.ndarray:
    """Modal percussion. Each partial is (frequency ratio, amplitude, decay per second)."""
    n = length_of(length)
    tone = np.zeros(n, dtype=np.float32)
    for r, a, d in partials:
        tone += sine(F(freq) * F(r), n) * F(a) * decay(n, d)
    hit = biquad("low", noise(seed, n), 3000.0, 0.7) * decay(n, 400.0) * F(mallet)
    return (tone + hit) * smoothstep(0.0, 0.002, times(n))


@cache
def marimba(midi, velocity) -> np.ndarray:
    v = F(velocity)
    partials = [(1.0, 1.0, 5.0), (3.93, F(0.28) * v, 14.0), (9.2, F(0.08) * v, 30.0)]
    return modal(note(midi), partials, 1.0, F(0.5) * v, int(midi)) * v


@cache
def glock(midi, velocity) -> np.ndarray:
    partials = [(1.0, 1.0, 1.4), (2.756, 0.45, 2.8), (5.404, 0.2, 4.5), (8.933, 0.08, 7.0)]
    return modal(note(midi), partials, 2.2, 0.3, int(midi) + 7) * F(velocity)


def music_box(midi) -> np.ndarray:
    partials = [(1.0, 1.0, 1.8), (3.0, 0.15, 5.0), (4.2, 0.08, 7.0)]
    return modal(note(midi), partials, 2.0, 0.1, int(midi) + 13)


def pluck(midi, length, damping, seed: int) -> np.ndarray:
    """Karplus-Strong plucked string."""
    freq = note(midi)
    n = int(max(RATE / freq, F(2.0)))
    excitation = biquad("low", noise(seed, n), freq * F(6.0), 0.7)
    count = length_of(length)
    return buf(ff.karplus_strong(excitation.tobytes(), count, float(damping))) * decay(count, 2.0)


def pizz(midi, velocity, seed: int) -> np.ndarray:
    """A short pizzicato: a pluck that stops quickly."""
    s = pluck(midi, 0.45, 0.995, seed)
    return s * F(velocity) * decay(len(s), 7.0)


def bassoon(midi, length, slide) -> np.ndarray:
    """A funny double reed: FM synthesis with a small vibrato."""
    n = length_of(length)
    t = times(n)
    length = F(length)
    midis = F(midi) + F(slide) * (t / length)
    notes = F(440.0) * f32("powf", 2.0, (midis - F(69.0)) / F(12.0))
    f = notes * (ONE + F(0.008) * fsin(t * F(31.0)) * smoothstep(0.1, 0.3, t))
    modulator = buf(ff.phasor((f * F(2.0) / RATE).tobytes(), n))
    index = F(1.8) * (F(0.6) + F(0.4) * decay(n, 3.0))
    carrier = buf(ff.phasor((f / RATE).tobytes(), n))
    y = fsin(carrier * TAU + index * fsin(modulator * TAU))
    return (
        biquad("low", y, 1400.0, 0.8)
        * attack_decay(n, 0.03, 0.8)
        * (ONE - smoothstep(length - F(0.08), length, t))
    )


@cache
def soft_kick() -> np.ndarray:
    n = length_of(0.4)
    osc = sine(F(48.0) + F(70.0) * decay(n, 35.0))
    return f32("tanh", osc * F(1.4)) * decay(n, 9.0)


@cache
def brush(seed: int) -> np.ndarray:
    n = length_of(0.25)
    return biquad("band", noise(seed, n), 3500.0, 0.6) * attack_decay(n, 0.012, 14.0) * F(0.8)


@cache
def shaker(seed: int) -> np.ndarray:
    n = length_of(0.08)
    return biquad("high", noise(seed, n), 6500.0, 0.7) * attack_decay(n, 0.008, 60.0) * F(0.5)


@cache
def pad(notes: tuple, length, attack) -> np.ndarray:
    n = length_of(length)
    t = times(n)
    raw = np.zeros(n, dtype=np.float32)
    for midi in notes:
        f = note(midi)
        raw += (
            saw(np.full(n, f * F(0.997), dtype=np.float32))
            + saw(np.full(n, f, dtype=np.float32))
            + saw(np.full(n, f * F(1.003), dtype=np.float32))
        )
    length = F(length)
    return (
        biquad("low", raw, 1400.0, 0.6)
        * smoothstep(0.0, attack, t)
        * (ONE - smoothstep(length - F(0.4), length, t))
        * F(0.06)
    )


def crickets(length, seed: int) -> np.ndarray:
    n = length_of(length)
    t = times(n)
    # Each 0.7 s cycle has a chirp of three pulses. Some cycles are silent.
    cycle = np.floor(t / F(0.7))
    within = t - cycle * F(0.7)
    on = hash_array(cycle.astype(np.uint32) + np.uint32(seed)) > F(0.25)
    x = within * F(32.0)
    pulse = ((x - np.trunc(x)) < F(0.5)) & (within < F(0.09))
    env = np.where(on & pulse, ONE, ZERO).astype(np.float32)
    return (sine(F(4600.0) + F(60.0) * noise(seed, n)) * env) * F(0.4)


# ------------------------------------------------------------------ The score

# One beat at 120 BPM, in seconds.
BEAT = F(0.5)


def tape_stop(track: Track, at, length) -> None:
    """Slows `track` down to a stop in `length` seconds from `at`, as a tape machine without
    power does. Everything after the stop is silent."""
    start = int(F(at) * RATE)
    n = int(F(length) * RATE)
    count = max(len(track) - start, 0)
    i = np.arange(min(count, n))
    s = i.astype(np.float32) / F(n)
    # The read position moves with the speed (1 - s)^2.
    u = ONE - s
    pos = F(start) + F(n) / F(3.0) * (ONE - u * u * u)
    k = pos.astype(np.int64)
    f = pos - k.astype(np.float32)
    fade = ONE - s * s
    for v in (track.l, track.r):
        source = np.append(v, [ZERO, ZERO])
        k0 = np.minimum(k, len(v))
        k1 = np.minimum(k + 1, len(v))
        get = source[k0] * (ONE - f) + source[k1] * f
        v[start : start + len(i)] = get * fade
        v[start + len(i) : start + count] = ZERO


# The marimba melody: eight eighth notes for each of the four bars.
PROGRESSION = [
    [72.0, 69.0, 65.0, 69.0, 72.0, 74.0, 72.0, 69.0],
    [74.0, 69.0, 65.0, 69.0, 74.0, 76.0, 74.0, 69.0],
    [74.0, 70.0, 65.0, 70.0, 74.0, 77.0, 74.0, 70.0],
    [76.0, 72.0, 67.0, 72.0, 76.0, 79.0, 76.0, 72.0],
]
# The bass note of each bar.
ROOTS = [41.0, 38.0, 34.0, 36.0]
# The pad chord of each bar.
CHORDS = [
    (65.0, 69.0, 72.0),
    (62.0, 65.0, 69.0),
    (58.0, 62.0, 65.0),
    (60.0, 64.0, 67.0),
]


def groove(music: Track, start, to, energy, seed: int) -> None:
    """The groove from `start` to `to`. More `energy` (0 to 1) makes the drums louder and adds
    layers."""
    eighth = BEAT / F(2.0)
    steps = int((F(to) - F(start)) / eighth)
    energy = F(energy)
    k = soft_kick()
    for s in range(steps):
        t = F(start) + F(s) * eighth
        bar = (s // 8) % 4
        pos = s % 8
        accent = F(1.0) if pos in (0, 3, 6) else F(0.7)
        # The melody skips one note in odd bars. This gives it bounce.
        if not (pos == 5 and bar % 2 == 1):
            music.add(
                t,
                marimba(PROGRESSION[bar][pos], accent * F(0.55)),
                1.0,
                -0.25 if pos % 2 == 0 else 0.25,
            )
        if pos in (0, 3):
            music.add(t, pizz(ROOTS[bar], 0.9, seed + s), 1.0, -0.1)
        if pos == 4:
            music.add(t, pizz(F(ROOTS[bar]) + F(7.0), 0.7, seed + s + 99), 1.0, -0.1)
        if pos in (0, 4):
            music.add(t, k, F(0.55) + F(0.25) * energy, 0.0)
        if pos in (2, 6):
            music.add(t, brush(seed + s), F(0.35) + F(0.25) * energy, 0.15)
        music.add(t, shaker(seed + 700 + s), 0.3 if pos % 2 == 1 else 0.18, 0.4)
        if energy > F(0.5) and pos == 0:
            top = F(CHORDS[bar][2]) + F(12.0)
            music.add(t, glock(top + F(12.0), 0.25), 1.0, 0.3)
            music.add(t, pad(CHORDS[bar], BEAT * F(4.0), 0.3), 1.0, 0.0)


def score(story: Story, length) -> Track:
    b = story.beats
    music = Track(length)
    # Waking up: a music box over a soft pad.
    arp = [77.0, 81.0, 84.0, 88.0, 84.0, 81.0, 82.0, 86.0, 89.0, 86.0, 82.0, 81.0]
    t = b.wake + F(0.1)
    i = 0
    while t < b.work - F(0.1):
        music.add(t, music_box(arp[i % len(arp)]), 0.22, -0.3 if i % 2 == 0 else 0.3)
        t += BEAT / F(2.0)
        i += 1
    music.add(b.wake, pad((53.0, 57.0, 60.0, 64.0), b.work - b.wake + F(0.3), 1.2), 1.0, 0.0)
    # Work: the groove. It gets more energy when the robot gets too confident.
    cocky = b.drop - F(2.0)
    groove(music, b.work, cocky, 0.0, 10)
    groove(music, cocky, b.drop + F(1.0), 1.0, 400)
    # A fast run of notes up into the drop.
    for k, n in enumerate([72.0, 74.0, 76.0, 77.0, 79.0, 81.0, 82.0, 84.0]):
        music.add(b.drop - F(0.5) + F(k) * F(0.055), marimba(n, 0.6), 1.0, 0.0)
    tape_stop(music, b.drop + F(0.04), 0.55)

    # The awkward silence: crickets.
    crickets_from = b.drop + F(1.3)
    crick = crickets(b.recover - crickets_from - F(0.3), 5)
    music.add(crickets_from, crick, 0.35, -0.6)
    music.add(crickets_from + F(0.37), crickets(b.recover - crickets_from - F(0.6), 9), 0.25, 0.6)
    # A sad slide down, like a trombone, under the sigh.
    music.add(b.recover - F(1.25), bassoon(46.0, 0.9, -3.0), 0.5, 0.0)

    # The careful recovery: quiet, short plucks and a low reed.
    sneak = [53.0, 56.0, 60.0, 56.0, 55.0, 58.0, 61.0, 58.0]
    t = b.recover + F(0.15)
    k = 0
    while t < b.finish - F(0.6):
        if k % 4 != 3:
            music.add(
                t, pizz(sneak[k % len(sneak)], 0.55, 900 + k), 1.0, -0.3 if k % 2 == 0 else 0.3
            )
        if k % 4 == 0:
            music.add(t, bassoon(F(sneak[k % len(sneak)]) - F(12.0), 0.22, 0.0), 0.35, 0.0)
        t += BEAT
        k += 1

    # Confident again, then the ta-da.
    groove(music, b.finish, b.tada - F(0.25), 1.0, 1200)
    music.add(b.tada - F(0.25), glock(84.0, 0.7), 1.0, 0.0)
    for n in [65.0, 69.0, 72.0, 77.0]:
        music.add(b.tada, marimba(n, 0.6), 1.0, 0.0)
    music.add(b.tada, glock(89.0, 0.8), 1.0, 0.2)
    music.add(b.tada, glock(84.0, 0.6), 1.0, -0.2)
    music.add(b.tada, pad((53.0, 57.0, 60.0, 65.0), 3.0, 0.05), 0.8, 0.0)
    music.add(b.tada, soft_kick(), 1.0, 0.0)
    music.add(b.tada, pizz(29.0, 1.0, 77), 1.0, 0.0)

    wet = reverb(music, 0.78, 0.4, 0.22)
    out = Track(length)
    out.mix(music, 1.0)
    out.mix(wet, 0.6)
    out.normalize(-1.0)
    return out


# ------------------------------------------------------------------ The voice of the robot


def chirp(length, pitch, wobble) -> Track:
    """A chirp that follows `pitch` (Hz over 0..1, of an array). A little FM makes it sound
    like a synthetic voice."""
    n = length_of(length)
    t = times(n)
    length = F(length)
    f = pitch(t / length).astype(np.float32)
    m = buf(ff.phasor((f * F(2.01) / RATE).tobytes(), n))
    step = f * (ONE + F(wobble) * fsin(t * F(38.0))) / RATE
    phase = buf(ff.phasor(step.tobytes(), n))
    s = (
        fsin(phase * TAU + F(0.6) * fsin(m * TAU))
        * smoothstep(0.0, 0.01, t)
        * (ONE - smoothstep(length - F(0.03), length, t))
    )
    track = reverb(mono(s, -3.0), 0.6, 0.5, 0.15)
    track.normalize(-2.0)
    return track


def sequence(parts) -> Track:
    """Mixes the parts at their start times and normalizes the result."""
    length = ZERO
    for t, p in parts:
        length = max(length, F(t) + F(len(p)) / RATE)
    out = Track(length)
    for t, p in parts:
        offset = int(F(t) * RATE)
        m = max(0, min(len(p), len(out) - offset))
        out.l[offset : offset + m] += p.l[:m]
        out.r[offset : offset + m] += p.r[:m]
    out.normalize(-2.0)
    return out


def constant(hz):
    return lambda x: np.full(len(x), F(hz), dtype=np.float32)


def curious() -> Track:
    def pitch(x):
        return np.where(
            x < F(0.3),
            F(700.0) + F(800.0) * x / F(0.3),
            np.where(
                x < F(0.6),
                F(1500.0) - F(400.0) * (x - F(0.3)) / F(0.3),
                F(1100.0) + F(700.0) * ((x - F(0.6)) / F(0.4)) ** 2,
            ),
        )

    return chirp(0.55, pitch, 0.02)


def happy() -> Track:
    def pitch(x):
        even = (x * F(12.0)).astype(np.uint32) % 2 == 0
        return np.where(
            x < F(0.75),
            np.where(even, F(1300.0), F(1750.0)),
            F(1500.0) + F(1200.0) * (x - F(0.75)) * F(4.0),
        )

    return chirp(0.4, pitch, 0.0)


def uh_oh() -> Track:
    return sequence(
        [
            (0.0, chirp(0.2, lambda x: F(900.0) - F(100.0) * x, 0.01)),
            (0.26, chirp(0.4, lambda x: F(640.0) - F(180.0) * x, 0.03)),
        ]
    )


def sigh() -> Track:
    out = chirp(1.0, lambda x: F(560.0) - F(380.0) * f32("powf", x, 0.7), 0.015)
    n = length_of(1.0)
    breath = biquad("band", noise(3, n), 900.0, 1.0) * attack_decay(n, 0.25, 2.5) * F(0.4)
    out.add(0.0, breath, 1.0, 0.0)
    out.normalize(-2.0)
    return out


def proud() -> Track:
    return sequence(
        [
            (0.0, chirp(0.08, constant(800.0), 0.0)),
            (0.09, chirp(0.08, constant(1000.0), 0.0)),
            (0.18, chirp(0.08, constant(1200.0), 0.0)),
            (0.27, chirp(0.3, lambda x: F(1600.0) + F(300.0) * x, 0.03)),
        ]
    )


def tada() -> Track:
    return sequence(
        [
            (0.0, chirp(0.1, constant(1200.0), 0.0)),
            (0.14, chirp(0.45, lambda x: F(1800.0) + F(100.0) * fsin(x * F(20.0)), 0.0)),
        ]
    )


def boot() -> Track:
    sweep = chirp(0.5, lambda x: F(300.0) + F(900.0) * x * x, 0.0)
    return sequence(
        [
            (0.0, sweep),
            (0.55, chirp(0.06, constant(1400.0), 0.0)),
            (0.66, chirp(0.06, constant(1400.0), 0.0)),
            (0.77, chirp(0.1, constant(1900.0), 0.0)),
        ]
    )


# ------------------------------------------------------------------ Foley


def click(seed: int, freq, decay_rate, length) -> np.ndarray:
    """A short click of band passed noise."""
    n = length_of(length)
    return biquad("band", noise(seed, n), freq, 3.0) * decay(n, decay_rate) * F(4.0)


def blink() -> Track:
    track = mono(click(5, 5200.0, 300.0, 0.05), -6.0)
    track.add(0.04, click(6, 4200.0, 400.0, 0.04), 0.6, 0.0)
    return track


def grip() -> Track:
    n = length_of(0.35)
    t = times(n)
    x = noise(51, n)
    late = np.where(t > F(0.07), x * f32("exp", -(t - F(0.07)) * F(900.0)), ZERO)
    s = biquad("high", x, 4000.0, 0.7) * attack_decay(n, 0.01, 18.0) * F(0.5) + biquad(
        "band", late.astype(np.float32), 2800.0, 8.0
    ) * F(5.0)
    return reverb(mono(s, -2.0), 0.6, 0.5, 0.12)


def place() -> Track:
    """A lacquered letter that the robot puts down on concrete."""
    n = length_of(0.6)
    x = noise(77, n)
    s = biquad("band", x * decay(n, 160.0), 520.0, 4.0) * F(7.0) * decay(n, 22.0) + sine(
        F(70.0) + F(40.0) * decay(n, 40.0)
    ) * decay(n, 14.0) * F(0.8)
    track = reverb(mono(s, -1.0), 0.75, 0.45, 0.15)
    track.normalize(-1.0)
    return track


def clatter() -> Track:
    """A hard hit with the ring of a thin plate."""
    modes = [(1250.0, 9.0), (2930.0, 14.0), (4710.0, 22.0)]
    n = length_of(0.5)
    x = noise(31, n) * decay(n, 500.0)
    ring = np.zeros(n, dtype=np.float32)
    for f, d in modes:
        ring += biquad("band", x, f, 25.0) * decay(n, d) * F(9.0)
    s = ring + x * F(0.6) + sine(90.0, n) * decay(n, 25.0) * F(0.6)
    track = reverb(mono(s, -1.0), 0.7, 0.4, 0.18)
    track.normalize(-1.0)
    return track


def pat() -> Track:
    track = mono(click(8, 900.0, 60.0, 0.15), -3.0)
    track.add(0.0, click(9, 2400.0, 200.0, 0.05), 0.4, 0.0)
    return track


def whoosh() -> Track:
    n = length_of(0.5)
    t = times(n)
    swell = fsin(t / F(0.5) * PI)
    s = biquad("band", noise(12, n), F(300.0) + F(1500.0) * swell, 1.2) * (swell * swell)
    return mono(s, -3.0)


def scratch() -> Track:
    n = length_of(0.42)
    # The record moves back and forward two times. The second time is slower.
    x = times(n) / F(0.42)
    pitch = np.where(
        x < F(0.35), fsin(x / F(0.35) * PI), fsin((x - F(0.35)) / F(0.65) * PI) * F(0.7)
    ).astype(np.float32)
    band = biquad("band", noise(44, n), F(400.0) + F(2600.0) * pitch, 5.0)
    s = (band * F(2.0) + saw(F(80.0) + F(300.0) * pitch) * F(0.3)) * np.sqrt(np.abs(pitch))
    return mono(s, -1.0)


def lights() -> Track:
    """The lab lights: heavy contactors close, then the tubes start to hum."""
    track = Track(2.0)
    for k, at in enumerate([0.0, 0.06, 0.12, 0.2, 0.27]):
        n = length_of(0.3)
        low = biquad("low", noise(100 + k, n), 700.0, 0.7)
        thunk = low * decay(n, 40.0) * F(2.0) + sine(55.0, n) * decay(n, 20.0)
        track.add(at, thunk, 1.0 if k % 2 == 0 else 0.5, -0.3 if k % 2 == 0 else 0.3)
    n = length_of(1.6)
    t = times(n)
    hum = sine(120.0, n) + sine(240.0, n) + sine(360.0, n)
    buzz = hum * smoothstep(0.3, 0.8, t) * (ONE - smoothstep(1.0, 1.6, t)) * F(0.08)
    track.add(0.3, buzz, 1.0, 0.0)
    track = reverb(track, 0.85, 0.3, 0.3)
    track.normalize(-1.0)
    return track


# ------------------------------------------------------------------ Beds


def room(length) -> Track:
    """The room tone: a low rumble, a little air and a mains hum."""
    track = Track(length)
    n = len(track)
    t = times(n)
    hum = sine(120.0, n) * F(0.02) * (F(0.8) + F(0.2) * fsin(t * F(0.3)))
    channels = []
    for seed in (1, 2):
        x = noise(seed, n)
        channels.append(
            biquad("low", x, 140.0, 0.7) * F(1.5) + biquad("high", x, 5000.0, 0.7) * F(0.04) + hum
        )
    track.l, track.r = channels
    track.normalize(-6.0)
    return track


def ease(e, x: np.ndarray) -> np.ndarray:
    """`story.ease` of each value of `x`."""
    kind, s = e
    x = np.clip(x, ZERO, ONE)
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


def joint_angles(track, t: np.ndarray) -> np.ndarray:
    """`track.sample(t)` joints for each time of `t`, as rows."""
    keys = track.keys
    k = np.searchsorted(np.asarray(track.times), t.astype(np.float64), side="right")
    q = np.empty((len(t), 6), dtype=np.float32)
    alive = np.empty(len(t), dtype=np.float32)
    for seg in np.unique(k):
        at = k == seg
        if seg == 0 or seg >= len(keys):
            key = keys[0] if seg == 0 else keys[-1]
            q[at], alive[at] = key.q, key.alive
            continue
        a, b = keys[seg - 1], keys[seg]
        s = (t[at] - a.t) / max(b.t - a.t, F(1e-6))
        x = ease(b.ease, s)
        q[at] = a.q + (b.q - a.q) * x[:, None]
        alive[at] = a.alive + (b.alive - a.alive) * np.clip(s, ZERO, ONE)
    idle = np.stack(
        [amp * fsin(t * f + p) if p else amp * fsin(t * f) for amp, f, p in IDLE], axis=1
    )
    return q + idle * alive[:, None]


def servos(story: Story, length) -> Track:
    """The motor of each joint: low motors for J1 to J3 and small, high motors for the wrist.
    Their level and pitch follow the joint speeds of the animation."""
    rate = F(240.0)
    samples = int(F(length) * rate) + 2
    step = ONE / rate
    t = np.arange(samples).astype(np.float32) / rate
    speeds = np.abs(joint_angles(story.track, t + step) - joint_angles(story.track, t)) * rate
    base = [70.0, 95.0, 120.0, 330.0, 380.0, 450.0]
    gain = [1.0, 1.0, 0.9, 0.5, 0.55, 0.45]
    track = Track(length)
    n = len(track)
    x = times(n) * rate
    i = np.minimum(x.astype(np.int64), samples - 2)
    frac = x - i.astype(np.float32)
    for j in range(6):
        sp = speeds[:, j]
        speed = sp[i] + (sp[i + 1] - sp[i]) * frac
        target = np.minimum(speed / F(2.5), ONE)
        level = buf(ff.one_pole(target.tobytes(), 0.003))
        f = F(base[j]) * (ONE + F(0.7) * np.minimum(speed / F(3.0), F(1.5)))
        gears = biquad("band", noise(60 + j, n), F(base[j]) * F(6.0), 4.0) * F(0.5)
        s = (sine(f) * F(0.6) + sine(f * F(2.02)) * F(0.3) + gears) * level * F(gain[j])
        track.add(0.0, s, 1.0, (F(j) - F(2.5)) * F(0.08))
    track.normalize(-3.0)
    return track


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--out", type=Path, help="the folder (default: dynamic_media of arm)")
    args = parser.parse_args(argv)
    out = args.out or _media.ROOT / "examples" / "arm" / "dynamic_media"
    out.mkdir(parents=True, exist_ok=True)
    for old in out.glob("*.wav"):
        old.unlink()
    font = (_media.folder("arm") / "Inter_18pt-ExtraBold.ttf").read_bytes()
    story = Story(font, "fframes")
    length = story.beats.end + F(0.6) + F(1.5)
    parts = [
        ("music.wav", lambda: score(story, length)),
        ("room.wav", lambda: room(length)),
        ("servos.wav", lambda: servos(story, length)),
        ("lights.wav", lights),
        ("boot.wav", boot),
        ("blink.wav", blink),
        ("curious.wav", curious),
        ("happy.wav", happy),
        ("grip.wav", grip),
        ("place.wav", place),
        ("whoosh.wav", whoosh),
        ("scratch.wav", scratch),
        ("clatter.wav", clatter),
        ("uhoh.wav", uh_oh),
        ("sigh.wav", sigh),
        ("pat.wav", pat),
        ("proud.wav", proud),
        ("tada.wav", tada),
    ]
    # The DSP helpers release the GIL, so the tracks render at the same time.
    with ThreadPoolExecutor() as pool:
        tracks = [pool.submit(make) for _, make in parts]
        for (name, _), track in zip(parts, tracks):
            track = track.result()
            track.write(out / name)
        print(f"wrote dynamic_media/{name} ({F(len(track)) / RATE:.2f} s)")


if __name__ == "__main__":
    main()

"""The music of the video, synthesized when the video starts: a 120 BPM track in A minor.
Its hits, plucks and keystrokes use the timing in `beat.py`.

All math is f32 with the operation order of the Rust example, so the track is bit for bit
the same. numpy does the per-sample arithmetic; `fframes.f32_math` gives the Rust f32
`sin`, `exp` and the others, and `fframes.Noise`, `fframes.saw` and `fframes.biquad` run
the recursive parts (noise, oscillators and filters) in Rust.
"""

import fframes as ff
import numpy as np
from beat import (
    BEAT,
    CODE,
    END,
    GRID,
    HOOK,
    LETTER_STEP,
    LETTERS,
    OUTRO,
    TILE_POP,
    TILE_STEP,
    TILES,
    WORD_NOW,
    ZOOM,
    beat_time,
    key_beats,
)

F = np.float32
RATE = F(48_000.0)
TAU = F(2.0 * np.pi)
PI = F(np.pi)


def arg(values):
    """A number or a buffer of f32 for the Rust helpers."""
    if np.ndim(values) == 0:
        return float(F(values))
    return np.ascontiguousarray(values, dtype="<f4").tobytes()


def floats(data: bytes) -> np.ndarray:
    return np.frombuffer(data, dtype="<f4")


def math(op: str, x, y=None):
    """Rust f32 `op` of `x` (and `y`); a scalar for scalar input."""
    out = floats(ff.f32_math(op, arg(x), None if y is None else arg(y)))
    return out[0] if np.ndim(x) == 0 and np.ndim(y) == 0 else out


def exp(x):
    return math("exp", x)


def sample(seconds) -> int:
    return int(F(seconds) * RATE)


def times(n: int) -> np.ndarray:
    return np.arange(n, dtype=F) / RATE


def filtered(kind: str, values, freq, q) -> np.ndarray:
    """`values` (f32 bytes or array) through an RBJ biquad; `freq` is one cutoff or one per sample."""
    values = values if isinstance(values, bytes) else arg(values)
    return floats(ff.biquad(kind, values, arg(freq), float(F(q)), float(RATE)))


def saw(freq, n: int, phase) -> np.ndarray:
    """A saw oscillator without aliasing (polyBLEP); `freq` is one value or one per sample."""
    return floats(ff.saw(arg(freq), n, float(F(phase)), float(RATE)))


def midi(note):
    return F(440.0) * math("powf", F(2.0), (F(note) - F(69.0)) / F(12.0))


class Mix:
    """The stereo mix."""

    def __init__(self, n: int):
        self.left = np.zeros(n, dtype=F)
        self.right = np.zeros(n, dtype=F)

    def add(self, at: int, values: np.ndarray, pan) -> None:
        values = values[: max(0, len(self.left) - at)]
        if np.ndim(pan):
            pan = pan[: len(values)]
        angle = (np.minimum(np.maximum(pan, F(-1.0)), F(1.0)) + F(1.0)) * PI / F(4.0)
        self.left[at : at + len(values)] += values * math("cos", angle)
        self.right[at : at + len(values)] += values * math("sin", angle)

    def voice(self, start, length, pan, voice) -> None:
        """Renders `length` seconds of `voice(t)` from `start` seconds."""
        self.add(sample(start), voice(times(sample(length))), F(pan))


# ------------------------------------------------------------------ Score

AM = (45, (57, 60, 64, 69))
CHORD_F = (41, (57, 60, 65, 69))
CHORD_C = (48, (55, 60, 64, 67))
CHORD_G = (43, (55, 59, 62, 67))
# the chord of each bar (4 beats); bars 0, 4 and from the outro on are A minor
BARS = {1: CHORD_F, 5: CHORD_F, 2: CHORD_C, 3: CHORD_G, 6: CHORD_G}


def chord(beat):
    """Root and the notes of the pad of the bar at `beat`, as MIDI notes."""
    return BARS.get(int(F(beat) / F(4.0)), AM)


def pentatonic(step: int) -> np.float32:
    """A minor pentatonic from A4, for plucks that always fit."""
    return F(69.0) + F((0, 3, 5, 7, 10)[step % 5]) + F(12.0) * F(step // 5)


KICKS = [F(b) for b in [*range(24), *range(28, 34)]]


def kick(mix: Mix, at, gain) -> None:
    gain = F(gain)

    def voice(t):
        # the integral of a pitch that falls from 155 Hz to 45 Hz
        phase = TAU * (F(45.0) * t + F(110.0) / F(32.0) * (F(1.0) - exp(-t * F(32.0))))
        body = math("sin", phase) * exp(-t * F(7.0))
        click = np.where(t < F(0.004), (F(1.0) - t / F(0.004)) * F(0.6), F(0.0))
        return math("tanh", body + click) * gain

    mix.voice(at, 0.5, 0.0, voice)


def clap(mix: Mix, noise, at, gain) -> None:
    n = sample(0.3)
    t = times(n)
    # three quick bursts, then the tail
    bursts = np.zeros(n, dtype=F)
    for s in (F(0.0), F(0.011), F(0.022)):
        bursts = bursts + np.where(t >= s, exp(-(t - s) * F(180.0)), F(0.0))
    env = bursts * F(0.5) + exp(-t * F(18.0)) * F(0.6)
    mix.add(sample(at), filtered("band", noise.take(n), 1400.0, 1.2) * env * F(gain), F(0.1))


def hat(mix: Mix, noise, at, gain, pan) -> None:
    n = sample(0.06)
    values = filtered("high", noise.take(n), 8000.0, 0.8) * exp(-times(n) * F(70.0)) * F(gain)
    mix.add(sample(at), values, F(pan))


def impact(mix: Mix, noise, at, gain) -> None:
    """A boom with a burst of noise for the big cuts."""
    gain = F(gain)

    def voice(t):
        phase = TAU * (F(38.0) * t + F(70.0) / F(9.0) * (F(1.0) - exp(-t * F(9.0))))
        return math("tanh", math("sin", phase) * exp(-t * F(2.2)) * F(1.2)) * gain

    mix.voice(at, 2.5, 0.0, voice)
    n = sample(1.5)
    t = times(n)
    cutoff = F(300.0) + F(5000.0) * exp(-t * F(4.0))
    values = filtered("low", noise.take(n), cutoff, 0.7) * exp(-t * F(3.0)) * gain * F(0.5)
    mix.add(sample(at), values, np.where(np.arange(n) % 2 == 0, F(-0.3), F(0.3)))


def whoosh(mix: Mix, noise, end, length, gain) -> None:
    """Noise that sweeps up into a cut."""
    n = sample(length)
    p = np.arange(n, dtype=F) / F(n)
    freq = F(300.0) * math("powf", F(20.0), p)
    values = filtered("band", noise.take(n), freq, 1.5) * p * p * F(gain)
    pan = math("sin", times(n) * F(3.0)) * F(0.6)
    mix.add(sample(F(end) - F(length)), values, pan)


def pluck(mix: Mix, at, note, gain, pan) -> None:
    """A plucked note: two detuned saws through a closing filter."""
    freq = midi(note)
    gain = F(gain)

    def voice(t):
        x = saw(freq, len(t), 0.0) + saw(freq * F(1.006), len(t), 0.37)
        cutoff = F(400.0) + F(5000.0) * exp(-t * F(14.0))
        return filtered("low", x, cutoff, 2.0) * exp(-t * F(5.0)) * gain

    mix.voice(at, 0.8, pan, voice)


def key(mix: Mix, noise, at, gain, pan) -> None:
    """A key of a mechanical keyboard."""
    n = sample(0.025)
    values = filtered("band", noise.take(n), 3500.0, 2.0) * exp(-times(n) * F(250.0)) * F(gain)
    mix.add(sample(at), values, F(pan))


def bed(mix: Mix, n: int) -> None:
    """Bass on the offbeats, pad on every beat, both pumping with the kick."""
    t = times(n)
    b = t / BEAT
    bars = [chord(F(4 * bar)) for bar in range(int(END / F(4.0)) + 1)]
    bar = (b / F(4.0)).astype(np.int64)
    root = np.array([midi(r) for r, _ in bars], dtype=F)[bar]
    notes = np.array([[midi(x) for x in ns] for _, ns in bars], dtype=F)[bar]

    # the gain under every kick
    kicks = np.array([beat_time(k) for k in KICKS], dtype=F)
    last = np.searchsorted(kicks, t, side="right") - 1
    ago = t - kicks[np.maximum(last, 0)]
    duck = np.where(last >= 0, F(1.0) - F(0.7) * exp(-ago * F(9.0)), F(1.0))
    # a short gap of silence right before the outro hit
    silent = (b >= OUTRO - F(0.05)) & (b < OUTRO)

    # bass: eighth notes on the offbeats, silent under the zoom
    double = b * F(2.0)
    eighth = double - np.trunc(double)
    bass_env = np.where(double.astype(np.int64) % 2 == 1, exp(-eighth * F(2.5)), F(0.0))
    bass_on = (b < ZOOM) | ((b >= OUTRO) & (b < END - F(2.0)))
    bass = saw(root, n, 0.0) + saw(root * F(2.0), n, 0.5) * F(0.4)
    bass = filtered("low", bass, 500.0, 1.0) * bass_env * np.where(bass_on, F(0.32), F(0.0))

    # pad: rises with a filter sweep under the zoom
    sweep = np.where((b >= ZOOM) & (b < OUTRO), (b - ZOOM) / (OUTRO - ZOOM), F(0.0))
    cutoff = np.where(b < GRID, F(1400.0), F(2200.0)) + F(5000.0) * sweep * sweep
    pad_gain = np.select(
        [b < GRID, b < ZOOM, b < OUTRO, b < END - F(2.0)],
        [F(0.05), F(0.07), F(0.05) + F(0.08) * sweep, F(0.08)],
        F(0.0),
    ).astype(F)
    left = np.zeros(n, dtype=F)
    right = np.zeros(n, dtype=F)
    for i in range(4):
        left = left + saw(notes[:, i] * F(0.997), n, F(i) * F(0.21))
        right = right + saw(notes[:, i] * F(1.003), n, F(i) * F(0.13) + F(0.5))
    loud = ~silent
    for channel, pad in ((mix.left, left), (mix.right, right)):
        pad = filtered("low", pad, cutoff, 0.9) * pad_gain * duck
        channel[loud] += (pad + bass * duck)[loud]


def music() -> tuple[bytes, bytes]:
    """The whole track, stereo, with its peak at -1 dBFS: `(left, right)` f32 bytes."""
    n = sample(beat_time(END))
    mix = Mix(n)
    noise = ff.Noise(0x9E37_79B9)

    # drums
    for b in KICKS:
        kick(mix, beat_time(b), 0.9)
    for b in [b for b in [*range(8, 24), *range(29, 34)] if b % 2 == 1]:
        clap(mix, noise, beat_time(b), 0.55)
    for i in range(int(END * F(4.0))):
        b = F(i) / F(4.0)
        fract = b - np.trunc(b)
        offbeat = abs(fract - F(0.5)) < F(0.01)
        sixteenth = F(16.0) <= b < F(24.0) and fract != F(0.0)
        if (F(4.0) <= b < F(24.0) or F(28.0) <= b < F(34.0)) and (offbeat or sixteenth):
            hat(mix, noise, beat_time(b), 0.22 if offbeat else 0.08, 0.25 if offbeat else -0.25)
    # the build under the zoom: a snare roll that gets faster
    b = ZOOM
    while b < OUTRO - F(0.1):
        progress = (b - ZOOM) / (OUTRO - ZOOM)
        clap(mix, noise, beat_time(b), F(0.15) + F(0.35) * progress)
        b += F(0.5 if progress < F(0.5) else 0.25 if progress < F(0.75) else 0.125)

    bed(mix, n)

    # the hook: hit, word thumps, a rising note per letter
    impact(mix, noise, beat_time(HOOK), 0.8)
    # "NOW PLAYS" gets one hit, because its two words are only 50 ms apart
    kick(mix, beat_time(WORD_NOW), 0.5)
    pluck(mix, beat_time(WORD_NOW), 57.0, 0.25, 0.0)
    for i, note in enumerate((69.0, 72.0, 74.0, 76.0, 79.0, 81.0)):
        at = beat_time(LETTERS + F(i) * LETTER_STEP)
        pluck(mix, at, note, 0.18, F(-0.5) + F(i) * F(0.2))

    # transitions
    for cut in (GRID, CODE):
        whoosh(mix, noise, beat_time(cut), 0.6, 0.35)
    whoosh(mix, noise, beat_time(OUTRO), beat_time(OUTRO - ZOOM), 0.3)
    impact(mix, noise, beat_time(OUTRO), 1.0)
    impact(mix, noise, beat_time(END - F(2.0)), 0.7)

    # a pluck for every tile of the grid, panned by its column
    for i in range(TILES):
        at = beat_time(TILE_POP + F(i) * TILE_STEP)
        pluck(mix, at, pentatonic(i + 2), 0.16, (F(i % 3) - F(1.0)) * F(0.6))
    # soft arpeggio under the code
    for i in range(int((ZOOM - CODE) * F(2.0))):
        b = CODE + F(i) * F(0.5)
        pluck(mix, beat_time(b), F(chord(b)[1][i % 4]) + F(12.0), 0.05, -0.4 if i % 2 == 0 else 0.4)
    # keystrokes, every third one
    for i, b in enumerate(key_beats()):
        if i % 3 == 0:
            key(mix, noise, beat_time(b), 0.25, -0.2 if i % 4 == 0 else 0.2)
    # "VECTOR."
    kick(mix, beat_time(ZOOM + F(0.5)), 0.6)
    # the outro: the last chord rings out
    for i, note in enumerate((57.0, 60.0, 64.0, 69.0, 72.0)):
        at = beat_time(END - F(2.0)) + F(i) * F(0.02)
        pluck(mix, at, note, 0.12, F(-0.4) + F(i) * F(0.2))

    # fade out the last 0.3 s, then normalize the peak to -1 dBFS
    fade = sample(0.3)
    ramp = F(1.0) - np.arange(fade, dtype=F) / F(fade)
    mix.left[n - fade :] *= ramp
    mix.right[n - fade :] *= ramp
    peak = max(np.abs(mix.left).max(), np.abs(mix.right).max())
    gain = math("powf", F(10.0), F(-1.0) / F(20.0)) / peak
    return (mix.left * gain).astype("<f4").tobytes(), (mix.right * gain).astype("<f4").tobytes()

"""The music of the video, synthesized when the video starts: a 120 BPM track in A minor.
Its hits, plucks and keystrokes use the timing in `beat.py`.

numpy does the per-sample math; `fframes.Noise` and `fframes.biquad` run the recursive parts
(the noise generator and the filters) in Rust.
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

RATE = 48_000.0
TAU = 2.0 * np.pi


def sample(seconds) -> int:
    return int(np.float32(seconds) * np.float32(RATE))


def times(n: int) -> np.ndarray:
    return np.arange(n) / RATE


def floats(data: bytes) -> np.ndarray:
    return np.frombuffer(data, dtype="<f4").astype(np.float64)


def f4(values: np.ndarray) -> bytes:
    return values.astype("<f4").tobytes()


def filtered(kind: str, values: np.ndarray, freq, q: float) -> np.ndarray:
    """`values` through an RBJ biquad; `freq` is one cutoff or one per sample."""
    freq = freq if np.isscalar(freq) else f4(np.asarray(freq))
    return floats(ff.biquad(kind, f4(values), freq, q, RATE))


def saw(freq, n: int, phase: float) -> np.ndarray:
    """A saw oscillator without aliasing (polyBLEP); `freq` is one value or one per sample."""
    dt = np.broadcast_to(np.asarray(freq, dtype=np.float64) / RATE, (n,))
    t = np.mod(phase + np.cumsum(dt), 1.0)
    blep = np.zeros(n)
    low = t < dt
    x = t[low] / dt[low]
    blep[low] = x + x - x * x - 1.0
    high = ~low & (t > 1.0 - dt)
    x = (t[high] - 1.0) / dt[high]
    blep[high] = x * x + x + x + 1.0
    return 2.0 * t - 1.0 - blep


def midi(note):
    return 440.0 * 2.0 ** ((np.asarray(note) - 69.0) / 12.0)


class Mix:
    """The stereo mix."""

    def __init__(self, n: int):
        self.left = np.zeros(n)
        self.right = np.zeros(n)

    def add(self, at: int, values: np.ndarray, pan) -> None:
        values = values[: max(0, len(self.left) - at)]
        angle = (np.clip(pan, -1.0, 1.0) + 1.0) * np.pi / 4.0
        if not np.isscalar(angle):
            angle = angle[: len(values)]
        self.left[at : at + len(values)] += values * np.cos(angle)
        self.right[at : at + len(values)] += values * np.sin(angle)


# ------------------------------------------------------------------ Score

AM = (45.0, (57.0, 60.0, 64.0, 69.0))
F_MAJOR = (41.0, (57.0, 60.0, 65.0, 69.0))
C_MAJOR = (48.0, (55.0, 60.0, 64.0, 67.0))
G_MAJOR = (43.0, (55.0, 59.0, 62.0, 67.0))
# Chord of each bar (4 beats); bars 0, 4 and from the outro on are A minor.
BARS = {1: F_MAJOR, 5: F_MAJOR, 2: C_MAJOR, 3: G_MAJOR, 6: G_MAJOR}


def chord(beat):
    return BARS.get(int(beat / 4.0), AM)


def pentatonic(step: int) -> float:
    """A minor pentatonic from A4, for plucks that always fit."""
    return 69.0 + (0.0, 3.0, 5.0, 7.0, 10.0)[step % 5] + 12.0 * (step // 5)


KICKS = [float(b) for b in [*range(24), *range(28, 34)]]


def kick(mix: Mix, at, gain: float) -> None:
    t = times(sample(0.5))
    # the integral of a pitch that falls from 155 Hz to 45 Hz
    phase = TAU * (45.0 * t + 110.0 / 32.0 * (1.0 - np.exp(-t * 32.0)))
    body = np.sin(phase) * np.exp(-t * 7.0)
    click = np.where(t < 0.004, (1.0 - t / 0.004) * 0.6, 0.0)
    mix.add(sample(at), np.tanh(body + click) * gain, 0.0)


def clap(mix: Mix, noise: ff.Noise, at, gain: float) -> None:
    n = sample(0.3)
    t = times(n)
    # three quick bursts, then the tail
    bursts = sum(np.where(t >= s, np.exp(-(t - s) * 180.0), 0.0) for s in (0.0, 0.011, 0.022))
    env = bursts * 0.5 + np.exp(-t * 18.0) * 0.6
    mix.add(sample(at), filtered("band", floats(noise.take(n)), 1400.0, 1.2) * env * gain, 0.1)


def hat(mix: Mix, noise: ff.Noise, at, gain: float, pan: float) -> None:
    n = sample(0.06)
    values = filtered("high", floats(noise.take(n)), 8000.0, 0.8)
    mix.add(sample(at), values * np.exp(-times(n) * 70.0) * gain, pan)


def impact(mix: Mix, noise: ff.Noise, at, gain: float) -> None:
    """A boom with a burst of noise for the big cuts."""
    t = times(sample(2.5))
    phase = TAU * (38.0 * t + 70.0 / 9.0 * (1.0 - np.exp(-t * 9.0)))
    mix.add(sample(at), np.tanh(np.sin(phase) * np.exp(-t * 2.2) * 1.2) * gain, 0.0)
    n = sample(1.5)
    t = times(n)
    values = filtered("low", floats(noise.take(n)), 300.0 + 5000.0 * np.exp(-t * 4.0), 0.7)
    pan = np.where(np.arange(n) % 2 == 0, -0.3, 0.3)
    mix.add(sample(at), values * np.exp(-t * 3.0) * gain * 0.5, pan)


def whoosh(mix: Mix, noise: ff.Noise, end, length, gain: float) -> None:
    """Noise that sweeps up into a cut."""
    n = sample(length)
    p = np.arange(n) / n
    values = filtered("band", floats(noise.take(n)), 300.0 * 20.0**p, 1.5) * p * p * gain
    mix.add(sample(np.float32(end) - np.float32(length)), values, np.sin(times(n) * 3.0) * 0.6)


def pluck(mix: Mix, at, note: float, gain: float, pan: float) -> None:
    """A plucked note: two detuned saws through a closing filter."""
    n = sample(0.8)
    t = times(n)
    freq = midi(note)
    x = saw(freq, n, 0.0) + saw(freq * 1.006, n, 0.37)
    values = filtered("low", x, 400.0 + 5000.0 * np.exp(-t * 14.0), 2.0)
    mix.add(sample(at), values * np.exp(-t * 5.0) * gain, pan)


def key(mix: Mix, noise: ff.Noise, at, gain: float, pan: float) -> None:
    """A key of a mechanical keyboard."""
    n = sample(0.025)
    values = filtered("band", floats(noise.take(n)), 3500.0, 2.0)
    mix.add(sample(at), values * np.exp(-times(n) * 250.0) * gain, pan)


def bed(mix: Mix, n: int) -> None:
    """Bass on the offbeats and pad on every beat, both pumping with the kick."""
    t = times(n)
    b = t / BEAT
    bars = [chord(x * 4.0) for x in range(int(b[-1] / 4.0) + 1)]
    bar = (b / 4.0).astype(int)
    root = np.array([c[0] for c in bars])[bar]
    notes = np.array([c[1] for c in bars])[bar]
    # sidechain: the gain ducks under every kick
    kicks = np.array([float(beat_time(k)) for k in KICKS])
    last = np.searchsorted(kicks, t, side="right") - 1
    duck = np.where(last >= 0, 1.0 - 0.7 * np.exp(-(t - kicks[np.maximum(last, 0)]) * 9.0), 1.0)
    # a short gap of silence right before the outro hit
    silent = (b >= OUTRO - 0.05) & (b < OUTRO)

    # bass: eighth notes on the offbeats, silent under the zoom
    eighth = np.mod(b * 2.0, 1.0)
    bass_env = np.where((b * 2.0).astype(int) % 2 == 1, np.exp(-eighth * 2.5), 0.0)
    bass_on = (b < ZOOM) | ((b >= OUTRO) & (b < END - 2.0))
    f = midi(root)
    bass = saw(f, n, 0.0) + saw(f * 2.0, n, 0.5) * 0.4
    bass = filtered("low", bass, 500.0, 1.0) * bass_env * np.where(bass_on, 0.32, 0.0)

    # pad: rises with a filter sweep under the zoom
    sweep = np.where((b >= ZOOM) & (b < OUTRO), (b - ZOOM) / (OUTRO - ZOOM), 0.0)
    cutoff = np.where(b < GRID, 1400.0, 2200.0) + 5000.0 * sweep * sweep
    pad_gain = np.select(
        [b < GRID, b < ZOOM, b < OUTRO, b < END - 2.0],
        [0.05, 0.07, 0.05 + 0.08 * sweep, 0.08],
        0.0,
    )
    freq = midi(notes)
    left = sum(saw(freq[:, i] * 0.997, n, i * 0.21) for i in range(4))
    right = sum(saw(freq[:, i] * 1.003, n, i * 0.13 + 0.5) for i in range(4))
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
    for i in range(int(END * 4.0)):
        b = np.float32(i) / np.float32(4.0)
        fract = b - np.floor(b)
        offbeat = abs(fract - 0.5) < 0.01
        sixteenth = 16.0 <= b < 24.0 and fract != 0.0
        if (4.0 <= b < 24.0 or 28.0 <= b < 34.0) and (offbeat or sixteenth):
            hat(mix, noise, beat_time(b), 0.22 if offbeat else 0.08, 0.25 if offbeat else -0.25)
    # the build under the zoom: a snare roll that gets faster
    b = ZOOM
    while b < OUTRO - np.float32(0.1):
        progress = (b - ZOOM) / (OUTRO - ZOOM)
        clap(mix, noise, beat_time(b), 0.15 + 0.35 * float(progress))
        b += np.float32(0.5 if progress < 0.5 else 0.25 if progress < 0.75 else 0.125)

    bed(mix, n)

    # the hook: hit, word thumps, a rising note per letter
    impact(mix, noise, beat_time(HOOK), 0.8)
    # "NOW PLAYS" gets one hit, because its two words are only 50 ms apart
    kick(mix, beat_time(WORD_NOW), 0.5)
    pluck(mix, beat_time(WORD_NOW), 57.0, 0.25, 0.0)
    for i, note in enumerate((69.0, 72.0, 74.0, 76.0, 79.0, 81.0)):
        pluck(mix, beat_time(LETTERS + i * LETTER_STEP), note, 0.18, -0.5 + i * 0.2)

    # transitions
    for cut in (GRID, CODE):
        whoosh(mix, noise, beat_time(cut), 0.6, 0.35)
    whoosh(mix, noise, beat_time(OUTRO), beat_time(OUTRO - ZOOM), 0.3)
    impact(mix, noise, beat_time(OUTRO), 1.0)
    impact(mix, noise, beat_time(END - 2.0), 0.7)

    # a pluck for every tile of the grid, panned by its column
    for i in range(TILES):
        at = beat_time(TILE_POP + i * TILE_STEP)
        pluck(mix, at, pentatonic(i + 2), 0.16, ((i % 3) - 1.0) * 0.6)
    # soft arpeggio under the code
    for i in range(int((ZOOM - CODE) * 2.0)):
        b = CODE + i * np.float32(0.5)
        pluck(mix, beat_time(b), chord(b)[1][i % 4] + 12.0, 0.05, -0.4 if i % 2 == 0 else 0.4)
    # keystrokes, every third one
    for i, b in enumerate(key_beats()):
        if i % 3 == 0:
            key(mix, noise, beat_time(b), 0.25, -0.2 if i % 4 == 0 else 0.2)
    # "VECTOR."
    kick(mix, beat_time(ZOOM + 0.5), 0.6)
    # the outro: the last chord rings out
    for i, note in enumerate((57.0, 60.0, 64.0, 69.0, 72.0)):
        pluck(mix, beat_time(END - 2.0) + i * 0.02, note, 0.12, -0.4 + i * 0.2)

    # fade out the last 0.3 s, then normalize the peak to -1 dBFS
    fade = sample(0.3)
    ramp = 1.0 - np.arange(fade) / fade
    mix.left[n - fade :] *= ramp
    mix.right[n - fade :] *= ramp
    peak = max(np.abs(mix.left).max(), np.abs(mix.right).max())
    gain = 10.0 ** (-1.0 / 20.0) / peak
    return f4(mix.left * gain), f4(mix.right * gain)
